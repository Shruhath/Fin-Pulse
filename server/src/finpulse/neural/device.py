"""GPU housekeeping for the encoder models.

The GPU has 8 GB and the LLMs need most of it, so the encoders (FinBERT, the embedder, the NLI model)
run in their own phase and are released before an LLM loads. `release()` is what makes that true.
"""

from __future__ import annotations

import gc
import logging

log = logging.getLogger(__name__)


def pick_device(prefer: str = "auto") -> str:
    """'cuda' when asked for or when available (and 'auto'), else 'cpu'."""
    import torch

    if prefer == "cpu":
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if prefer == "cuda":
        log.warning("CUDA was requested but is not available; using the CPU")
    return "cpu"


def release() -> None:
    """Drop cached GPU memory after the caller has deleted its models."""
    gc.collect()
    import torch

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def gpu_summary() -> str | None:
    import torch

    if not torch.cuda.is_available():
        return None
    free, total = torch.cuda.mem_get_info()
    return f"{torch.cuda.get_device_name(0)}: {free / 2**30:.1f} GiB free of {total / 2**30:.1f}"
