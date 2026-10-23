"""Why did the model score a company that way? Integrated Gradients over the FinBERT input.

Integrated Gradients (Sundararajan, Taly and Yan, 2017) attributes a prediction to the input by
integrating the gradient of the class score along a straight path from a baseline to the input. Here the
input is the embedding of each token and the baseline replaces every word with the padding embedding,
keeping the special tokens and the entity markers, so what is measured is the effect of the words. The
attributions add up to the score difference between the input and the baseline (completeness); the
relative gap is returned as `convergence` so a reader can see how well the integral was approximated.

The explained score is the raw logit of the predicted class, which is what the classifier head produces
before calibration; the calibrated probabilities are returned next to it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from finpulse.sentiment.calibration import softmax
from finpulse.sentiment.data import LABELS
from finpulse.sentiment.finbert import MARK_CLOSE, MARK_OPEN, MAX_LENGTH, FinBert, Item

STEPS = 48


@dataclass(slots=True)
class Word:
    text: str
    weight: float  # relative to the largest absolute weight in the window, so between -1 and 1
    entity: bool  # inside the [E] ... [/E] markers: the company the score is about


@dataclass(slots=True)
class Explanation:
    label: str
    probabilities: dict[str, float]
    words: list[Word]
    steps: int
    convergence: float  # |sum of attributions - (score - baseline score)| / |score - baseline score|


def explain(model: FinBert, item: Item, *, steps: int = STEPS, target: str | None = None) -> Explanation:
    """Integrated Gradients for one mention. `target` defaults to the predicted label."""
    tok, net = model.tokenizer, model.model
    enc = tok(model._text(item), truncation=True, max_length=MAX_LENGTH, return_tensors="pt").to(model.device)
    ids = enc["input_ids"]
    mask = enc["attention_mask"]
    pieces = tok.convert_ids_to_tokens(ids[0])
    keep = torch.tensor(
        [p in (tok.cls_token, tok.sep_token, MARK_OPEN, MARK_CLOSE) for p in pieces], device=model.device
    )

    net.eval()
    with torch.no_grad():
        logits = net(**enc).logits[0].float().cpu().numpy()
    probs = softmax(logits[None, :], model.temperature)[0]
    label = target or LABELS[int(np.argmax(probs))]
    cls = LABELS.index(label)

    embed = net.get_input_embeddings()
    with torch.no_grad():
        x = embed(ids)
        pad = embed(torch.full_like(ids, tok.pad_token_id))
        base = torch.where(keep[None, :, None], x, pad)

    alphas = torch.linspace(1 / steps, 1.0, steps, device=model.device)[:, None, None]
    path = (base + alphas * (x - base)).detach().requires_grad_(True)
    with torch.enable_grad():
        score = net(inputs_embeds=path, attention_mask=mask.expand(steps, -1)).logits[:, cls].float()
        (grads,) = torch.autograd.grad(score.sum(), path)
    attribution = ((x - base)[0] * grads.mean(dim=0)).sum(dim=-1)

    with torch.no_grad():
        f_x = float(net(**enc).logits[0, cls])
        f_base = float(net(inputs_embeds=base, attention_mask=mask).logits[0, cls])
    delta = f_x - f_base
    gap = abs(float(attribution.sum()) - delta)
    convergence = gap / abs(delta) if abs(delta) > 1e-9 else 0.0

    return Explanation(
        label=label,
        probabilities={name: float(p) for name, p in zip(LABELS, probs, strict=True)},
        words=_words(pieces, attribution.detach().cpu().numpy()),
        steps=steps,
        convergence=convergence,
    )


def _words(pieces: list[str], attribution: np.ndarray) -> list[Word]:
    """Merge word pieces into words, drop the special tokens, scale to [-1, 1]."""
    out: list[tuple[str, float, bool]] = []
    inside = False
    for piece, weight in zip(pieces, attribution, strict=True):
        if piece == MARK_OPEN:
            inside = True
            continue
        if piece == MARK_CLOSE:
            inside = False
            continue
        if piece in ("[CLS]", "[SEP]", "[PAD]"):
            continue
        if piece.startswith("##") and out:
            text, w, ent = out[-1]
            out[-1] = (text + piece[2:], w + float(weight), ent)
        else:
            out.append((piece, float(weight), inside))
    peak = max((abs(w) for _, w, _ in out), default=0.0) or 1.0
    return [Word(text=t, weight=w / peak, entity=e) for t, w, e in out]
