"""Dense sentence embeddings (BAAI/bge-base-en-v1.5 by default: 768 dimensions, L2-normalised, CLS pooling).

Queries (claims being checked) get the model's retrieval instruction; passages (corpus sentences) do not,
which is how the BGE models are trained to be used.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from finpulse.core.settings import get_settings
from finpulse.neural.device import pick_device

QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class Embedder:
    def __init__(
        self, name: str | None = None, *, device: str = "auto", max_length: int = 512, batch_size: int = 64
    ):
        self.name = name or get_settings().embedding_model
        self.max_length, self.batch_size = max_length, batch_size
        self.device = pick_device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(self.name)
        self.model = AutoModel.from_pretrained(
            self.name, torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
        )
        self.model.to(self.device).eval()

    @property
    def dim(self) -> int:
        return int(self.model.config.hidden_size)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """float32 array of shape (n, dim), rows with unit length (for passages)."""
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        with torch.inference_mode():
            for lo in range(0, len(order), self.batch_size):
                idx = order[lo : lo + self.batch_size]
                enc = self.tokenizer(
                    [texts[i] for i in idx],
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                ).to(self.device)
                cls = self.model(**enc).last_hidden_state[:, 0].float()
                out[idx] = torch.nn.functional.normalize(cls, dim=-1).cpu().numpy()
        return out

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self.encode([QUERY_INSTRUCTION + t for t in texts])
