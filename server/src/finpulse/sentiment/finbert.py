"""Entity-marked FinBERT: one prediction per entity mention, fine-tuned on FinEntity and SEntFiN.

The text around a mention is cut to +/-40 words and the mention is wrapped in `[E]` ... `[/E]`
marker tokens added to the vocabulary, so one sentence with several companies gives each its own
prediction. The pre-trained ProsusAI/finbert head is re-ordered to (negative, neutral, positive)
instead of being thrown away, so fine-tuning starts from what FinBERT already knows. After
training, a single temperature fitted on the dev split calibrates the confidences.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

from finpulse.neural.device import pick_device
from finpulse.sentiment.calibration import fit_temperature, softmax
from finpulse.sentiment.data import LABELS, Example
from finpulse.sentiment.metrics import confusion, f1_scores

log = logging.getLogger(__name__)

BASE_MODEL = "ProsusAI/finbert"
MARK_OPEN, MARK_CLOSE = "[E]", "[/E]"
WINDOW_WORDS = 40
MAX_LENGTH = 160
MODEL_NAME = "finbert-entity"
Item = tuple[str, int, int]  # text, mention start, mention end


def marked(text: str, start: int, end: int, k: int = WINDOW_WORDS) -> str:
    """The k words either side of the mention, with the mention wrapped in marker tokens."""
    before = text[:start].split()[-k:]
    after = text[end:].split()[:k]
    return " ".join([*before, MARK_OPEN, text[start:end], MARK_CLOSE, *after])


def sentence_only(text: str, start: int, end: int, k: int = WINDOW_WORDS * 2) -> str:
    """The strawman input: the sentence with no hint about which entity is meant."""
    words = text.split()
    return " ".join(words[: k * 2])


@dataclass(slots=True)
class TrainReport:
    epochs: list[dict[str, float]] = field(default_factory=list)
    best_epoch: int = 0
    temperature: float = 1.0
    seconds: float = 0.0


class FinBert:
    def __init__(
        self,
        model: nn.Module,
        tokenizer: Any,
        *,
        device: str,
        temperature: float = 1.0,
        version: str | None = None,
        entity_marked: bool = True,
        batch_size: int = 64,
    ):
        self.model, self.tokenizer, self.device = model, tokenizer, device
        self.temperature, self.version = temperature, version
        self.entity_marked, self.batch_size = entity_marked, batch_size
        self.model.to(device)

    # ------------------------------------------------------------------ construction

    @classmethod
    def from_base(
        cls, name_or_path: str = BASE_MODEL, *, device: str = "auto", entity_marked: bool = True
    ) -> FinBert:
        """A trainable model from a pre-trained checkpoint, with the head ordered as `LABELS`."""
        tok = AutoTokenizer.from_pretrained(name_or_path)
        model = AutoModelForSequenceClassification.from_pretrained(
            name_or_path, num_labels=len(LABELS), dtype=torch.float32
        )
        if entity_marked:
            tok.add_special_tokens({"additional_special_tokens": [MARK_OPEN, MARK_CLOSE]})
            model.resize_token_embeddings(len(tok))
        _align_head(model)
        return cls(model, tok, device=pick_device(device), entity_marked=entity_marked)

    @classmethod
    def load(cls, directory: Path, *, device: str = "auto") -> FinBert:
        meta = json.loads((directory / "finpulse.json").read_text())
        tok = AutoTokenizer.from_pretrained(directory)
        model = AutoModelForSequenceClassification.from_pretrained(directory)
        return cls(
            model, tok, device=pick_device(device), temperature=meta["temperature"], version=meta["version"],
            entity_marked=meta.get("entity_marked", True),
        )  # fmt: skip

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(directory, safe_serialization=True)
        self.tokenizer.save_pretrained(directory)
        (directory / "finpulse.json").write_text(
            json.dumps(
                {
                    "version": self.version,
                    "temperature": self.temperature,
                    "labels": list(LABELS),
                    "entity_marked": self.entity_marked,
                    "window_words": WINDOW_WORDS,
                },
                indent=2,
            )
        )
        return directory

    # ------------------------------------------------------------------ inference

    def _text(self, item: Item) -> str:
        return marked(*item) if self.entity_marked else sentence_only(*item)

    def logits(self, items: Sequence[Item]) -> np.ndarray:
        """Raw logits in the order of `LABELS`."""
        self.model.eval()
        out: list[np.ndarray] = []
        order = sorted(range(len(items)), key=lambda i: len(items[i][0]))  # similar lengths pad less
        with torch.inference_mode():
            for lo in range(0, len(order), self.batch_size):
                idx = order[lo : lo + self.batch_size]
                enc = self.tokenizer(
                    [self._text(items[i]) for i in idx],
                    padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt",
                ).to(self.device)  # fmt: skip
                with torch.autocast(self.device, dtype=torch.bfloat16, enabled=self.device == "cuda"):
                    out.append(self.model(**enc).logits.float().cpu().numpy())
        flat = np.concatenate(out) if out else np.zeros((0, len(LABELS)))
        restored = np.empty_like(flat)
        restored[order] = flat
        return restored

    def predict_spans(self, items: Sequence[Item]) -> np.ndarray:
        """Calibrated probabilities in the order of `LABELS`, one row per item."""
        return softmax(self.logits(items), self.temperature)

    # ------------------------------------------------------------------ training

    def fit(
        self,
        train: Sequence[Example],
        dev: Sequence[Example],
        *,
        epochs: int = 4,
        lr: float = 2e-5,
        batch_size: int = 32,
        seed: int = 13,
        on_epoch: Callable[[dict[str, float]], None] | None = None,
    ) -> TrainReport:
        import time

        t0 = time.monotonic()
        _seed_everything(seed)
        gold = np.array([LABELS.index(e.label) for e in train])
        counts = np.bincount(gold, minlength=len(LABELS)).astype(float)
        weights = torch.tensor(
            counts.sum() / (len(LABELS) * np.maximum(counts, 1)), dtype=torch.float32, device=self.device
        )
        loss_fn = nn.CrossEntropyLoss(weight=weights)
        optimiser = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=0.01)
        steps = epochs * ((len(train) + batch_size - 1) // batch_size)
        schedule = get_linear_schedule_with_warmup(optimiser, int(0.1 * steps), steps)
        rng = np.random.default_rng(seed)
        report = TrainReport()
        best_f1, best_state = -1.0, None

        for epoch in range(1, epochs + 1):
            self.model.train()
            order = rng.permutation(len(train))
            total = 0.0
            for lo in range(0, len(order), batch_size):
                batch = [train[i] for i in order[lo : lo + batch_size]]
                enc = self.tokenizer(
                    [self._text((e.text, e.start, e.end)) for e in batch],
                    padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt",
                ).to(self.device)  # fmt: skip
                labels = torch.tensor([LABELS.index(e.label) for e in batch], device=self.device)
                with torch.autocast(self.device, dtype=torch.bfloat16, enabled=self.device == "cuda"):
                    logits = self.model(**enc).logits
                loss = loss_fn(logits.float(), labels)
                optimiser.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimiser.step()
                schedule.step()
                total += float(loss.detach()) * len(batch)
            dev_f1 = self._macro_f1(dev)
            row = {"epoch": float(epoch), "train_loss": total / len(train), "dev_macro_f1": dev_f1}
            report.epochs.append(row)
            log.info("epoch %d: loss %.4f dev macro-F1 %.4f", epoch, row["train_loss"], dev_f1)
            if on_epoch:
                on_epoch(row)
            if dev_f1 > best_f1:
                best_f1, report.best_epoch = dev_f1, epoch
                best_state = {k: v.detach().cpu().clone() for k, v in self.model.state_dict().items()}
        if best_state is not None:
            self.model.load_state_dict(best_state)

        # calibration on the dev split, with the best weights
        dev_logits = self.logits([(e.text, e.start, e.end) for e in dev])
        self.temperature = fit_temperature(dev_logits, np.array([LABELS.index(e.label) for e in dev]))
        report.temperature = self.temperature
        digest = hashlib.sha1(
            ("|".join(sorted(e.text for e in train)) + f"{epochs}{lr}{seed}").encode()
        ).hexdigest()[:8]
        self.version = f"{MODEL_NAME}@{digest}"
        report.seconds = time.monotonic() - t0
        return report

    def _macro_f1(self, examples: Sequence[Example]) -> float:
        probs = softmax(self.logits([(e.text, e.start, e.end) for e in examples]))
        pred = [LABELS[i] for i in probs.argmax(axis=1)]
        return f1_scores(confusion([e.label for e in examples], pred))["macroF1"]


def _align_head(model: nn.Module) -> None:
    """Re-order the head to (negative, neutral, positive) when the checkpoint names its labels."""
    names = {int(i): str(n).lower() for i, n in model.config.id2label.items()}
    if set(names.values()) == set(LABELS):
        perm = [next(i for i, n in names.items() if n == lab) for lab in LABELS]
        with torch.no_grad():
            model.classifier.weight.copy_(model.classifier.weight[perm].clone())
            model.classifier.bias.copy_(model.classifier.bias[perm].clone())
    model.config.id2label = dict(enumerate(LABELS))
    model.config.label2id = {lab: i for i, lab in enumerate(LABELS)}


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
