from __future__ import annotations

import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    """One plain line per record on stderr, so worker and API logs read the same."""
    root = logging.getLogger()
    if any(getattr(h, "_finpulse", False) for h in root.handlers):
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stderr)
    handler._finpulse = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"))
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
