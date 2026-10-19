"""Natural-language inference: does an evidence sentence entail, contradict or say nothing about a claim."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from finpulse.neural.device import pick_device

MODEL_NAME = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
ORDER = ("entailment", "neutral", "contradiction")


class Nli:
    def __init__(
        self, name: str = MODEL_NAME, *, device: str = "auto", max_length: int = 512, batch_size: int = 16
    ):
        self.name, self.max_length, self.batch_size = name, max_length, batch_size
        self.device = pick_device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(name)
        self.model = AutoModelForSequenceClassification.from_pretrained(name)
        self.model.to(self.device).eval()
        names = {int(i): str(n).lower() for i, n in self.model.config.id2label.items()}
        # column of the model output for each of (entailment, neutral, contradiction)
        self._columns = [
            next(i for i, n in names.items() if n.startswith(prefix))
            for prefix in ("entail", "neutral", "contra")
        ]

    def predict(self, pairs: Sequence[tuple[str, str]]) -> np.ndarray:
        """Probabilities (entailment, neutral, contradiction) for each (premise, hypothesis)."""
        out = np.zeros((len(pairs), 3), dtype=np.float32)
        with torch.inference_mode():
            for lo in range(0, len(pairs), self.batch_size):
                chunk = pairs[lo : lo + self.batch_size]
                enc = self.tokenizer(
                    [p for p, _ in chunk], [h for _, h in chunk],
                    padding=True, truncation=True, max_length=self.max_length, return_tensors="pt",
                ).to(self.device)  # fmt: skip
                probs = torch.softmax(self.model(**enc).logits.float(), dim=-1).cpu().numpy()
                out[lo : lo + len(chunk)] = probs[:, self._columns]
        return out
