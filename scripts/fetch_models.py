#!/usr/bin/env python3
"""Download the Hugging Face models the pipeline uses into the local cache (once).

  uv run python ../scripts/fetch_models.py            # everything
  uv run python ../scripts/fetch_models.py finbert ner

Only the files `from_pretrained` needs are fetched (no ONNX copies, no duplicate weight formats).
Models are cached under ~/.cache/huggingface and never leave the machine afterwards.
"""
from __future__ import annotations

import sys

from huggingface_hub import snapshot_download

TOKENIZER = ["*.json", "*.txt", "*.model", "*.vocab"]
MODELS = {
    "finbert": ("ProsusAI/finbert", [*TOKENIZER, "*.safetensors", "pytorch_model.bin"]),
    "ner": ("microsoft/deberta-v3-base", [*TOKENIZER, "pytorch_model.bin"]),
    "nli": ("MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli", [*TOKENIZER, "*.safetensors", "pytorch_model.bin"]),
    "embed": ("BAAI/bge-base-en-v1.5", [*TOKENIZER, "*.safetensors"]),
}


def main(names: list[str]) -> int:
    wanted = names or list(MODELS)
    unknown = [n for n in wanted if n not in MODELS]
    if unknown:
        print(f"unknown: {', '.join(unknown)}; choose from {', '.join(MODELS)}", file=sys.stderr)
        return 2
    for name in wanted:
        repo, patterns = MODELS[name]
        print(f"{name}: {repo}", flush=True)
        path = snapshot_download(repo, allow_patterns=patterns)
        print(f"  -> {path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
