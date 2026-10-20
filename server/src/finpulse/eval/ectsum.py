"""Summary quality on a sample of ECTSum earnings-call transcripts (a public benchmark).

For each sampled transcript the summariser sees the sentences chosen by LexRank within the prompt
budget, writes cited claims, and is scored against the reference bullets with ROUGE-1/2/L F1. Lead-3
and LexRank (top three sentences) are scored the same way. With an NLI model, each claim is also
checked against the five transcript sentences BM25 finds for it: attribution precision is the share
entailed (p >= 0.7), the unsupported-claim rate is the share neither entailed nor contradicted, and
the contradicted rate is reported separately. BERTScore is not computed (it needs a 1.4 GB model).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from sqlalchemy.orm import Session

from finpulse.core.settings import get_settings
from finpulse.db.models import EvalResult
from finpulse.llm.client import Llm, LlmError
from finpulse.pipeline.runs import recorded_run
from finpulse.pipeline.verify import CONTRADICT_MIN, ENTAIL_MIN, Judge
from finpulse.summarize.llm import PROMPT_VERSION, summarise
from finpulse.summarize.prune import lead_n, lexrank, select, usable
from finpulse.verify.bm25 import BM25

from .rouge import rouge
from .sentiment import _git_sha

ECTSUM = Path("ectsum/data/final")
BUDGET_CHARS = 10_000
DATASET = "ECTSum test sample"


@dataclass(frozen=True, slots=True)
class Transcript:
    name: str
    sentences: list[str]
    reference: str


def load_ectsum(root: Path, *, split: str = "test", n: int = 60, seed: int = 7) -> list[Transcript]:
    base = root / ECTSUM / split
    names = sorted(p.stem for p in (base / "ects").glob("*.txt"))
    random.Random(seed).shuffle(names)
    out = []
    for name in names:
        ref = base / "gt_summaries" / f"{name}.txt"
        if not ref.is_file():
            continue
        sentences = [
            s.strip()
            for s in (base / "ects" / f"{name}.txt").read_text(encoding="utf-8").splitlines()
            if s.strip()
        ]
        out.append(
            Transcript(
                name,
                sentences,
                " ".join(ln.strip() for ln in ref.read_text(encoding="utf-8").splitlines() if ln.strip()),
            )
        )
        if len(out) >= n:
            break
    return out


def _check(judge: Judge, claim: str, sentences: list[str], bm25: BM25) -> str:
    top = [sentences[i] for i in bm25.rank(claim, 5)]
    if not top:
        return "unsupported"
    probs = judge.predict([(s, claim) for s in top])
    if float(probs[:, 0].max()) >= ENTAIL_MIN:
        return "entailed"
    return "contradicted" if float(probs[:, 2].max()) >= CONTRADICT_MIN else "unsupported"


def evaluate_ectsum(
    llm: Llm, model: str, transcripts: list[Transcript], judge: Judge | None = None
) -> dict[str, dict[str, float]]:
    scores: dict[str, dict[str, list[float]]] = {
        name: {"rouge1": [], "rouge2": [], "rougeL": []} for name in ("llm", "lead3", "lexrank")
    }
    verdicts: list[str] = []
    skipped = 0
    for t in transcripts:
        sentences = t.sentences
        central = lexrank([s for s in sentences if usable(s)] or sentences)
        usable_idx = [i for i, s in enumerate(sentences) if usable(s)] or list(range(len(sentences)))
        top3 = sorted(sorted(range(len(usable_idx)), key=lambda k: -central[k])[:3])
        baselines = {"lead3": lead_n(sentences, 3), "lexrank": [usable_idx[k] for k in top3]}
        for name, picks in baselines.items():
            r = rouge(" ".join(sentences[i] for i in picks), t.reference)
            for k in scores[name]:
                scores[name][k].append(r[k])
        shown = select(sentences, budget_chars=BUDGET_CHARS)
        try:
            result = summarise(
                llm, model, subject=t.name, scope="document", evidence=[(i, sentences[i]) for i in shown]
            )
        except LlmError:
            skipped += 1
            continue
        r = rouge(" ".join(c.text for c in result.claims), t.reference)
        for k in scores["llm"]:
            scores["llm"][k].append(r[k])
        if judge is not None:
            bm25 = BM25(sentences)
            verdicts += [_check(judge, c.text, sentences, bm25) for c in result.claims]
    out = {name: {k: mean(v) if v else 0.0 for k, v in s.items()} for name, s in scores.items()}
    for name, s in scores.items():
        out[name]["n"] = float(len(s["rouge1"]))
    out["llm"]["skipped"] = float(skipped)
    if verdicts:
        n = len(verdicts)
        out["llm"]["attribution"] = verdicts.count("entailed") / n
        out["llm"]["unsupported"] = verdicts.count("unsupported") / n
        out["llm"]["contradicted"] = verdicts.count("contradicted") / n
    return out


def run_ectsum_eval(
    session: Session,
    llm: Llm,
    model: str,
    judge: Judge | None,
    *,
    n: int = 60,
    benchmark_dir: Path | None = None,
) -> dict[str, dict[str, float]]:
    cfg = get_settings()
    transcripts = load_ectsum(benchmark_dir or cfg.benchmark_dir, n=n)
    if not transcripts:
        raise RuntimeError("ECTSum is not under the benchmark directory; run scripts/fetch_layer1.sh first")
    with recorded_run(
        session,
        "eval-ectsum",
        model=model,
        prompt_version=PROMPT_VERSION,
        params={"transcripts": len(transcripts)},
    ) as run:
        scores = evaluate_ectsum(llm, model, transcripts, judge)
        sha = _git_sha()
        labels = {
            "llm": (f"{model} + NLI check", False),
            "lead3": ("Lead-3", True),
            "lexrank": ("LexRank (extractive)", True),
        }
        for name, (label, baseline) in labels.items():
            session.add(
                EvalResult(
                    stage="summaries",
                    model=label,
                    baseline=baseline,
                    dataset=f"{DATASET} (n={len(transcripts)})",
                    split="test",
                    indian=False,
                    metrics=scores[name],
                    run_id=run.id,
                    git_sha=sha,
                )
            )
        out = cfg.results_dir / "summaries"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"ectsum-{datetime.now(UTC):%Y%m%dT%H%M%S}.json").write_text(
            json.dumps(
                {"git_sha": sha, "model": model, "prompt_version": PROMPT_VERSION, "scores": scores}, indent=2
            )
            + "\n"
        )
    return scores
