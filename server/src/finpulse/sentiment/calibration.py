"""Temperature scaling: one number, fitted on the dev split, that makes confidences honest."""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar


def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = np.asarray(logits, dtype=float) / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def nll(logits: np.ndarray, labels: np.ndarray, temperature: float) -> float:
    """Mean negative log-likelihood of the gold labels after dividing the logits by `temperature`."""
    p = softmax(logits, temperature)
    return float(-np.log(np.clip(p[np.arange(len(labels)), labels], 1e-12, 1.0)).mean())


def fit_temperature(logits: np.ndarray, labels: np.ndarray) -> float:
    """The temperature in [0.05, 20] that minimises NLL on (logits, integer labels)."""
    logits, labels = np.asarray(logits, dtype=float), np.asarray(labels, dtype=int)
    if len(labels) == 0:
        return 1.0
    res = minimize_scalar(
        lambda log_t: nll(logits, labels, float(np.exp(log_t))), bounds=(-3.0, 3.0), method="bounded"
    )
    return float(np.exp(res.x))
