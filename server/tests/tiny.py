"""Tiny randomly initialised BERT models saved to disk, so the neural code is tested without downloads."""

from __future__ import annotations

import string
from pathlib import Path

import torch
from transformers import BertConfig, BertForSequenceClassification, BertModel, BertTokenizerFast

_CHARS = list(string.ascii_lowercase + string.digits)
_PUNCT = list(".,-/%$()'\"&:;[]")
VOCAB = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", *_CHARS, *("##" + c for c in _CHARS), *_PUNCT]


def _tokenizer(directory: Path) -> BertTokenizerFast:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "vocab.txt").write_text("\n".join(VOCAB) + "\n")
    return BertTokenizerFast(vocab_file=str(directory / "vocab.txt"), do_lower_case=True)


def _config(**extra) -> BertConfig:
    return BertConfig(
        vocab_size=len(VOCAB), hidden_size=32, num_hidden_layers=2, num_attention_heads=2,
        intermediate_size=64, max_position_embeddings=256, **extra,
    )  # fmt: skip


def classifier(directory: Path, id2label: dict[int, str]) -> Path:
    """A 3-way BERT classifier whose head names its labels the way the real checkpoints do."""
    torch.manual_seed(0)  # the same random weights on every run, so tests do not depend on luck
    tok = _tokenizer(directory)
    model = BertForSequenceClassification(
        _config(num_labels=3, id2label=id2label, label2id={v: k for k, v in id2label.items()})
    )
    model.save_pretrained(directory)
    tok.save_pretrained(directory)
    return directory


def encoder(directory: Path) -> Path:
    torch.manual_seed(0)
    tok = _tokenizer(directory)
    BertModel(_config()).save_pretrained(directory)
    tok.save_pretrained(directory)
    return directory
