"""Neural NER: a transformer token classifier (DeBERTa-v3-base, BERT as the fallback) for company names.

Each word gets one BIO tag from the first sub-token of the word. Training uses FinEntity and SEntFiN
spans; scoring is exact-span F1 on the held-out splits of each.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from transformers import AutoModelForTokenClassification, AutoTokenizer, get_linear_schedule_with_warmup

from finpulse.entities.names import Token, tokenize
from finpulse.neural.device import pick_device

from .data import TAGS, Sentence, spans_from_tags
from .metrics import span_scores

BASE_MODEL = "microsoft/deberta-v3-base"
MODEL_NAME = "deberta-ner"
IGNORE = -100
MAX_LENGTH = 128
AUTOCAST = True  # bfloat16 activations over fp32 weights: the memory an 8 GB GPU needs for DeBERTa-v3


class TransformerNer:
    def __init__(
        self,
        model: nn.Module,
        tokenizer: Any,
        *,
        device: str,
        version: str | None = None,
        batch_size: int = 64,
    ):
        self.model, self.tokenizer, self.device = model, tokenizer, device
        self.version, self.batch_size = version, batch_size
        self.model.to(device)

    @classmethod
    def from_base(cls, name: str = BASE_MODEL, *, device: str = "auto") -> TransformerNer:
        tok = (
            AutoTokenizer.from_pretrained(name, add_prefix_space=True)
            if "roberta" in name
            else AutoTokenizer.from_pretrained(name)
        )
        model = AutoModelForTokenClassification.from_pretrained(
            name,
            dtype=torch.float32,  # the checkpoint ships in fp16, which cannot be trained with AdamW
            num_labels=len(TAGS),
            id2label=dict(enumerate(TAGS)),
            label2id={t: i for i, t in enumerate(TAGS)},
        )
        return cls(model, tok, device=pick_device(device))

    @classmethod
    def load(cls, directory: Path, *, device: str = "auto") -> TransformerNer:
        meta = json.loads((directory / "finpulse.json").read_text())
        return cls(
            AutoModelForTokenClassification.from_pretrained(directory),
            AutoTokenizer.from_pretrained(directory),
            device=pick_device(device),
            version=meta["version"],
        )

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(directory, safe_serialization=True)
        self.tokenizer.save_pretrained(directory)
        (directory / "finpulse.json").write_text(
            json.dumps({"version": self.version, "tags": list(TAGS)}, indent=2)
        )
        return directory

    # ------------------------------------------------------------------ batching

    def _encode(self, words: list[list[str]]) -> Any:
        return self.tokenizer(
            words,
            is_split_into_words=True,
            padding=True,
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt",
        )

    def _first_subtoken_mask(self, enc: Any, n_words: Sequence[int]) -> list[list[int | None]]:
        """Per sentence, the word index of each sub-token that starts a word, else None."""
        out: list[list[int | None]] = []
        for b in range(len(n_words)):
            seen: set[int] = set()
            row: list[int | None] = []
            for w in enc.word_ids(batch_index=b):
                row.append(w if w is not None and w not in seen else None)
                if w is not None:
                    seen.add(w)
            out.append(row)
        return out

    def logits_for(self, token_lists: Sequence[Sequence[Token]]) -> list[np.ndarray]:
        """Per sentence, an array (n_words, n_tags) of logits (words cut off by truncation get 'O')."""
        self.model.eval()
        results: list[np.ndarray | None] = [None] * len(token_lists)
        order = sorted(range(len(token_lists)), key=lambda i: len(token_lists[i]))
        with torch.inference_mode():
            for lo in range(0, len(order), self.batch_size):
                idx = [i for i in order[lo : lo + self.batch_size]]
                words = [[t.text for t in token_lists[i]] for i in idx]
                enc = self._encode(words)
                heads = self._first_subtoken_mask(enc, [len(w) for w in words])
                out = (
                    self.model(**{k: v.to(self.device) for k, v in enc.items()}).logits.float().cpu().numpy()
                )
                for b, i in enumerate(idx):
                    arr = np.zeros((len(token_lists[i]), len(TAGS)), dtype=np.float32)
                    arr[:, 0] = 5.0  # words past the truncation point default to 'O'
                    for pos, w in enumerate(heads[b]):
                        if w is not None:
                            arr[w] = out[b, pos]
                    results[i] = arr
        return [r for r in results if r is not None]

    def predict_batch(self, texts: Sequence[str]) -> list[list[tuple[int, int, float]]]:
        token_lists = [tokenize(t) for t in texts]
        out: list[list[tuple[int, int, float]]] = []
        non_empty = [t for t in token_lists if t]
        logits_iter = iter(self.logits_for(non_empty))
        for tokens in token_lists:
            if not tokens:
                out.append([])
                continue
            logits = next(logits_iter)
            probs = np.exp(logits - logits.max(axis=1, keepdims=True))
            probs /= probs.sum(axis=1, keepdims=True)
            tags = [TAGS[i] for i in probs.argmax(axis=1)]
            spans = []
            for start, end in sorted(spans_from_tags(tokens, tags)):
                inside = [i for i, t in enumerate(tokens) if t.start >= start and t.end <= end]
                spans.append((start, end, float(np.mean([probs[i, TAGS.index(tags[i])] for i in inside]))))
            out.append(spans)
        return out

    # ------------------------------------------------------------------ training

    def fit(
        self,
        train: Sequence[Sentence],
        dev: Sequence[Sentence],
        *,
        epochs: int = 4,
        lr: float = 5e-5,
        batch_size: int = 16,
        seed: int = 13,
    ) -> dict[str, Any]:
        t0 = time.monotonic()
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        optimiser = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=0.01)
        steps = epochs * ((len(train) + batch_size - 1) // batch_size)
        schedule = get_linear_schedule_with_warmup(optimiser, int(0.1 * steps), steps)
        rng = np.random.default_rng(seed)
        history, best_f1, best_state, best_epoch = [], -1.0, None, 0
        for epoch in range(1, epochs + 1):
            self.model.train()
            order = rng.permutation(len(train))
            total = 0.0
            for lo in range(0, len(order), batch_size):
                batch = [train[i] for i in order[lo : lo + batch_size]]
                enc = self._encode([[t.text for t in s.tokens] for s in batch])
                heads = self._first_subtoken_mask(enc, [len(x.tokens) for x in batch])
                labels = torch.full(enc["input_ids"].shape, IGNORE, dtype=torch.long)
                for b, sentence in enumerate(batch):
                    for pos, w in enumerate(heads[b]):
                        if w is not None:
                            labels[b, pos] = TAGS.index(sentence.tags[w])
                with torch.autocast(
                    self.device, dtype=torch.bfloat16, enabled=AUTOCAST and self.device == "cuda"
                ):
                    out = self.model(
                        **{k: v.to(self.device) for k, v in enc.items()}, labels=labels.to(self.device)
                    )
                optimiser.zero_grad(set_to_none=True)
                out.loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimiser.step()
                schedule.step()
                total += float(out.loss.detach()) * len(batch)
            f1 = self.score(dev)["spanF1"]
            history.append({"epoch": float(epoch), "train_loss": total / len(train), "dev_span_f1": f1})
            if f1 > best_f1:
                best_f1, best_epoch = f1, epoch
                best_state = {k: v.detach().cpu().clone() for k, v in self.model.state_dict().items()}
        if best_state is not None:
            self.model.load_state_dict(best_state)
        digest = hashlib.sha1("|".join(sorted(s.text for s in train)).encode()).hexdigest()[:8]
        self.version = f"{MODEL_NAME}@{digest}"
        return {"epochs": history, "best_epoch": best_epoch, "seconds": round(time.monotonic() - t0, 1)}

    def score(self, sentences: Sequence[Sentence]) -> dict[str, float]:
        predicted = self.predict_batch([s.text for s in sentences])
        return span_scores([s.spans() for s in sentences], [{(a, b) for a, b, _ in p} for p in predicted])
