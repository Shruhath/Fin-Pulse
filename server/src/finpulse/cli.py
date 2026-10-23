"""`finpulse` command line: run the pipeline stages and serve the API."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from sqlalchemy import func, select, text

from finpulse.core.logging import configure_logging
from finpulse.core.settings import get_settings
from finpulse.db.models import Document, Entity, Event, Mention, Sentence
from finpulse.db.session import session_scope


def _status(_: argparse.Namespace) -> int:
    with session_scope() as s:
        s.execute(text("select 1"))
        counts = {
            "documents": s.scalar(select(func.count()).select_from(Document)),
            "parsed": s.scalar(select(func.count()).select_from(Document).where(Document.status == "parsed")),
            "failed": s.scalar(select(func.count()).select_from(Document).where(Document.status == "failed")),
            "ocr": s.scalar(select(func.count()).select_from(Document).where(Document.ocr_used)),
            "sentences": s.scalar(select(func.count()).select_from(Sentence)),
            "entities": s.scalar(select(func.count()).select_from(Entity)),
            "mentions": s.scalar(select(func.count()).select_from(Mention)),
            "events": s.scalar(select(func.count()).select_from(Event)),
        }
    print("  ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def _gazetteer_seed(_: argparse.Namespace) -> int:
    from finpulse.entities.gazetteer import seed_gazetteer

    with session_scope() as s:
        st = seed_gazetteer(s, get_settings().benchmark_dir)
    print(
        f"entities +{st.entities} (nse {st.from_nse}, sentfin {st.from_sentfin}, "
        f"{st.skipped} sentfin rows skipped as non-companies), aliases +{st.aliases}"
    )
    return 0


def _ingest_corpus(a: argparse.Namespace) -> int:
    if a.what == "rbi":
        from finpulse.ingest.rbi import collect_rbi

        with session_scope() as s:
            st = collect_rbi(s)
        print(f"RBI feed: {st.seen} items, {st.created} new, {st.existing} already stored, {st.empty} empty")
        return 0
    from finpulse.ingest.corpus import ingest_corpus

    with session_scope() as s:
        st = ingest_corpus(s, get_settings().corpus_dir, sources=set(a.source) or None, limit=a.limit)
    print(f"seen {st.seen}, new {st.created}, already stored {st.existing}, missing file {st.missing_file}")
    return 0


def _parse(a: argparse.Namespace) -> int:
    from finpulse.pipeline.parse import parse_pending

    def progress(done: int, total: int, doc: Document) -> None:
        flag = " [OCR]" if doc.ocr_used else ""
        print(f"[{done}/{total}] {doc.n_pages or 0}p {doc.n_words}w{flag}  {doc.title[:70]}", flush=True)

    with session_scope() as s:
        st = parse_pending(
            s, workers=a.workers, limit=a.limit, ocr=not a.no_ocr, redo=a.redo, progress=progress
        )
    print(f"parsed {st.parsed}, failed {st.failed}, scanned documents read with OCR {st.ocr_documents}")
    return 0 if st.failed == 0 else 1


def _link(a: argparse.Namespace) -> int:
    from finpulse.pipeline.link import link_pending

    with session_scope() as s:
        st = link_pending(s, limit=a.limit, relink=a.relink)
    print(
        f"documents {st.documents}, mentions {st.mentions} ({st.unresolved} unresolved), "
        f"new entities {st.created_entities}"
    )
    return 0


def _events(a: argparse.Namespace) -> int:
    if a.revalidate:
        from finpulse.pipeline.llm_events import revalidate_llm_events

        with session_scope() as s:
            checked, changed = revalidate_llm_events(s)
        print(f"{checked} LLM events checked against the current schema, {changed} changed")
        return 0
    from finpulse.pipeline.events import extract_pending

    with session_scope() as s:
        st = extract_pending(s, limit=a.limit)
    print(
        f"documents {st.documents}, events {st.events} ({st.without_entity} without an entity, "
        f"{st.invalid} failing their schema)"
    )
    return 0


def _sentiment(a: argparse.Namespace) -> int:
    if a.action == "train":
        from finpulse.eval.sentiment import train_and_evaluate

        with session_scope() as s:
            run = train_and_evaluate(s, kind=a.model, epochs=a.epochs)
        print(f"trained {run.version}  ->  {run.model_path}\nresults -> {run.result_path}")
        for row in run.rows:
            m = row["metrics"]
            print(
                f"  {row['model'][:34]:<34} {row['dataset']:<16} n={int(m['n'])}  "
                f"macro-F1 {m['macroF1']:.3f}  "
                f"weighted-F1 {m['weightedF1']:.3f}  ECE {m['ece']:.3f}"
            )
        return 0

    from finpulse.pipeline.sentiment import load_scoring_model, score_pending

    model = load_scoring_model(device=a.device)
    if model is None:
        print("no trained model found: run `finpulse sentiment train` first", file=sys.stderr)
        return 1
    with session_scope() as s:
        refresh = score_pending(s, model, limit=a.limit)
        s.execute(text("refresh materialized view entity_daily"))
    print(f"scored {refresh.mentions} mentions with {refresh.version}")
    return 0


def _ner(a: argparse.Namespace) -> int:
    if a.action == "train":
        from finpulse.eval.ner import train_and_evaluate

        with session_scope() as s:
            run = train_and_evaluate(s, kind=a.model, epochs=a.epochs)
        print(f"trained {run.version}  ->  {run.model_path}\nresults -> {run.result_path}")
        for row in run.rows:
            m = row["metrics"]
            print(
                f"  {row['model'][:38]:<38} {row['dataset']:<16} n={int(m['n'])}  "
                f"P {m['spanPrecision']:.3f}  "
                f"R {m['spanRecall']:.3f}  F1 {m['spanF1']:.3f}"
            )
        return 0
    from finpulse.pipeline.ner import load_ner_model, ner_pending

    model = load_ner_model(device=a.device)
    if model is None:
        print("no trained NER model found: run `finpulse ner train` first", file=sys.stderr)
        return 1
    with session_scope() as s:
        st = ner_pending(s, model, limit=a.limit)
    print(f"{st.mentions} new mentions in {st.sentences} sentences ({st.linked} linked)")
    return 0


def _dedup(a: argparse.Namespace) -> int:
    from finpulse.pipeline.dedup import dedup_documents

    with session_scope() as s:
        total, dupes = dedup_documents(s, a.threshold)
    print(f"{total} documents, {dupes} near-duplicates of an earlier one")
    return 0


def _worker(a: argparse.Namespace) -> int:
    from finpulse.pipeline.worker import run_worker

    run_worker(poll_seconds=a.poll, once=a.once)
    return 0


def _parse_quotas(text: str | None) -> dict[str, int] | None:
    if not text:
        return None
    return {k.strip(): int(v) for k, v in (part.split("=") for part in text.split(","))}


def _gold(a: argparse.Namespace) -> int:
    import json
    from pathlib import Path

    from finpulse.gold import labelstudio

    repo = Path(__file__).resolve().parents[3]
    if a.action == "config":
        out = Path(a.out or repo / "annotation" / "label_config.xml")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(labelstudio.label_config())
        print(f"wrote {out}")
        return 0
    with session_scope() as s:
        if a.action == "select":
            from finpulse.gold.select import select_passages

            st = select_passages(s, _parse_quotas(a.quota), calibration=a.calibration, seed=a.seed)
            print(
                f"selected {st.selected} new passages ({st.existing} already frozen); "
                f"short of quota: {st.short_of_quota}"
            )
        elif a.action == "tasks":
            out = Path(a.out or repo / "annotation" / "tasks.json")
            out.parent.mkdir(parents=True, exist_ok=True)
            print(f"wrote {labelstudio.dump(out, s)} tasks to {out}")
        elif a.action == "import":
            names = {int(k): v for k, v in (p.split("=") for p in (a.annotators or "").split(",") if p)}
            st = labelstudio.import_export(s, json.loads(Path(a.file).read_text()), names)
            print(
                f"{st.annotations} annotations -> {st.rows} rows; {st.skipped_spans} spans skipped; "
                f"by annotator {st.by_annotator}"
            )
        elif a.action == "references":
            from finpulse.eval.summaries import import_references

            rows = [json.loads(line) for line in Path(a.file).read_text().splitlines() if line.strip()]
            print(f"{import_references(s, rows)} reference summaries imported")
        elif a.action == "agreement":
            from finpulse.eval.agreement import compute_agreement

            rows = compute_agreement(s)
            if not rows:
                print("no calibration passage has been labelled by two or more people yet")
            for r in rows:
                print(
                    f"  {r.task:<10} {r.measure:<12} {r.value:6.3f}  items {r.items:<4} "
                    f"{'PASS' if r.passed else 'BELOW GATE'}  ({', '.join(r.annotators)})"
                )
        elif a.action == "eval":
            from finpulse.eval.gold_run import run_gold_eval
            from finpulse.pipeline.sentiment import load_scoring_model

            llm = judge = None
            if a.llm:
                from finpulse.llm.client import OllamaClient

                llm = OllamaClient()
            run = run_gold_eval(s, scorer=load_scoring_model(device=a.device), llm=llm, judge=judge)
            if not run.rows:
                print("there are no gold annotations yet, so nothing was evaluated")
            for r in run.rows:
                m = r["metrics"]
                shown = {
                    k: round(v, 3)
                    for k, v in m.items()
                    if k in {"typeF1", "argF1", "spanF1", "linkAcc", "macroF1", "rougeL"}
                }
                print(f"  {r['stage']:<10} {r['model'][:42]:<42} {shown}")
    return 0


def _export(a: argparse.Namespace) -> int:
    from pathlib import Path

    from finpulse.export.dataport import export_dataport

    out = Path(a.out)
    with session_scope() as s:
        names = Path(a.names).read_text(encoding="utf-8").splitlines() if a.names else []
        m = export_dataport(s, out, include_text=a.include_text, extra_names=names, words=not a.no_words)
    print(f"wrote {out} ({'with' if m.include_text else 'without'} document text)")
    print("  " + ", ".join(f"{k}={v}" for k, v in m.counts.items()))
    return 0


def _openapi(a: argparse.Namespace) -> int:
    import json
    from pathlib import Path

    from finpulse.api.app import app

    spec = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    out = Path(a.out)
    if a.check:
        ok = out.is_file() and out.read_text() == spec
        print(
            "openapi.json is current" if ok else f"{out} is out of date: run `finpulse openapi`",
            file=sys.stderr if not ok else sys.stdout,
        )
        return 0 if ok else 1
    out.write_text(spec)
    print(f"wrote {out}")
    return 0


def _ectsum(a: argparse.Namespace) -> int:
    from finpulse.core.settings import get_settings as settings
    from finpulse.eval.ectsum import run_ectsum_eval
    from finpulse.llm.client import OllamaClient

    model = settings().summary_model
    client = OllamaClient()
    if not client.has_model(model):
        print(
            f"{model} is not available at {client.base_url} (scripts/ollama-local.sh pull)", file=sys.stderr
        )
        return 1
    judge = None
    if not a.no_nli:
        from finpulse.verify.nli import Nli

        judge = Nli(device=a.device)
    with session_scope() as s:
        scores = run_ectsum_eval(s, client, model, judge, n=a.n)
    client.unload(model)
    for name, m in scores.items():
        shown = {k: round(v, 3) for k, v in m.items()}
        print(f"  {name:<8} {shown}")
    return 0


def _components(a: argparse.Namespace) -> int:
    import json

    from finpulse.core.settings import get_settings as settings
    from finpulse.eval.components import record_components

    nli = None
    if not a.no_nli:
        from finpulse.verify.nli import Nli

        nli = Nli(device=a.device)
    with session_scope() as s:
        report = record_components(s, nli, settings().benchmark_dir)
    print(json.dumps(report, indent=2))
    return 0


def _baselines(a: argparse.Namespace) -> int:
    import json

    from finpulse.core.settings import get_settings as settings

    cfg = settings()
    if a.extend:
        from finpulse.eval.modelpapers import extend_sentiment_metrics

        with session_scope() as s:
            for line in extend_sentiment_metrics(s, cfg.benchmark_dir, device=a.device):
                print("  extended", line)
        return 0
    from finpulse.eval.modelpapers import run_model_papers

    report = run_model_papers(cfg.benchmark_dir, cfg.results_dir, device=a.device)
    print(json.dumps({k: v for k, v in report.items() if k in ("sizes", "so_pmi_sentfin_test")}, indent=2))
    return 0


def _ablation(a: argparse.Namespace) -> int:
    import json

    from finpulse.core.settings import get_settings as settings
    from finpulse.eval.ablation import run_ablation

    which = set(a.which)
    encoder = None
    if "retrieval" in which:
        from finpulse.embed.encoder import Embedder

        encoder = Embedder(device="cpu")
    with session_scope() as s:
        report = run_ablation(s, settings().results_dir, which=which, encoder=encoder)
    print(json.dumps(report, indent=2))
    return 0


def _explain_stats(a: argparse.Namespace) -> int:
    import json
    from pathlib import Path

    from finpulse.core.settings import get_settings as settings
    from finpulse.pipeline.sentiment import load_scoring_model
    from finpulse.sentiment.explain import explanation_stats
    from finpulse.sentiment.finbert import FinBert

    model = load_scoring_model(device=a.device)
    if not isinstance(model, FinBert):
        print("explanations need the fine-tuned FinBERT", file=sys.stderr)
        return 1
    with session_scope() as s:
        stats = explanation_stats(s, model, n=a.n)
    out = Path(settings().results_dir) / "xai"
    out.mkdir(parents=True, exist_ok=True)
    (out / "integrated-gradients.json").write_text(
        json.dumps({"model": model.version, **stats}, indent=2) + "\n"
    )
    print(json.dumps(stats, indent=2))
    return 0


def _ask(a: argparse.Namespace) -> int:
    from finpulse.pipeline.ask import answer_question, load_runtime

    runtime = load_runtime()
    if a.eval:
        from finpulse.eval.qa import run_qa_eval

        with session_scope() as s:
            system, baseline = run_qa_eval(s, runtime, n_each=a.n_each)
        if runtime.llm is not None:
            runtime.llm.unload(runtime.model)
        print("  system  ", {k: round(v, 3) for k, v in system.items()})
        print("  baseline", {k: round(v, 3) for k, v in baseline.items()})
        return 0
    if not a.question:
        print("give a question, or --eval to measure question answering", file=sys.stderr)
        return 2

    def show(key: str, status: str, ms: int | None, note: str | None) -> None:
        if status != "running":
            print(f"  [{status:^7}] {key:<9} {'' if ms is None else f'{ms / 1000:5.1f}s'}  {note or ''}")

    with session_scope() as s:
        out = answer_question(s, a.question, runtime, on_stage=show)
    if out.abstained:
        print(f"\nNo answer: {out.reason}")
    for claim in out.claims:
        print(f"\n[{claim.verification}] {claim.text}")
        if claim.evidence is not None:
            print(f'    "{claim.evidence.text[:160]}" ({claim.evidence.title})')
    return 0


def _embed(a: argparse.Namespace) -> int:
    from finpulse.pipeline.batch import run_pipeline

    return (
        0
        if all(
            r.status != "failed"
            for r in run_pipeline(("embed",), limit=a.limit, device=a.device, report=lambda r: print(r.note))
        )
        else 1
    )


def _pipeline(a: argparse.Namespace) -> int:
    from finpulse.pipeline.batch import DEFAULT_STAGES, run_pipeline

    stages = tuple(a.stages) if a.stages else DEFAULT_STAGES

    def show(r) -> None:
        print(f"  [{r.status:^7}] {r.stage:<11} {r.seconds:6.1f}s  {r.note}", flush=True)

    results = run_pipeline(stages, limit=a.limit, device=a.device, window=a.window, top=a.top, report=show)
    return 1 if any(r.status == "failed" for r in results) else 0


def _llm(a: argparse.Namespace) -> int:
    from finpulse.core.settings import get_settings as settings
    from finpulse.llm.client import OllamaClient

    client = OllamaClient()
    cfg = settings()
    try:
        have = client.models()
    except Exception as exc:
        print(f"no Ollama server at {client.base_url}: {exc}", file=sys.stderr)
        return 1
    for role, name in (("events", cfg.event_model), ("summaries", cfg.summary_model)):
        print(f"  {role:<10} {name:<32} {'installed' if client.has_model(name) else 'MISSING'}")
    print(f"  server at {client.base_url} has: {', '.join(have) or 'no models'}")
    return 0


def _serve(a: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("finpulse.api.app:app", host=a.host, port=a.port, reload=a.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="finpulse", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name: str, fn: Callable[[argparse.Namespace], int], help: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help)
        sp.set_defaults(fn=fn)
        return sp

    add("status", _status, "database counts")
    g = add(
        "gazetteer", _gazetteer_seed, "seed entities from the NSE master and SEntFiN (alias: gazetteer seed)"
    )
    g.add_argument("action", nargs="?", default="seed", choices=["seed"])

    ing = add("ingest", _ingest_corpus, "load the layer 2 corpus into the database")
    ing.add_argument("what", nargs="?", default="corpus", choices=["corpus", "rbi"])
    ing.add_argument("--source", action="append", default=[], help="sebi_orders or ibbi_nclt (repeatable)")
    ing.add_argument("--limit", type=int)

    ps = add("parse", _parse, "parse ingested documents (OCR for scans)")
    ps.add_argument("--workers", type=int, default=4)
    ps.add_argument("--limit", type=int)
    ps.add_argument("--no-ocr", action="store_true")
    ps.add_argument(
        "--redo", action="store_true", help="parse documents again, replacing their text and sentences"
    )

    ln = add("link", _link, "find and link entity mentions")
    ln.add_argument("--limit", type=int)
    ln.add_argument("--relink", action="store_true", help="redo documents that already have mentions")

    ev = add("events", _events, "extract events with the rule baseline")
    ev.add_argument("--limit", type=int)
    ev.add_argument("--revalidate", action="store_true", help="re-check stored LLM events against the schema")

    se = add("sentiment", _sentiment, "train the TF-IDF baseline, or score linked mentions with it")
    se.add_argument("action", choices=["train", "score"])
    se.add_argument("--limit", type=int)
    se.add_argument("--model", choices=["tfidf", "finbert"], default="tfidf", help="which model `train` fits")
    se.add_argument("--epochs", type=int, default=4, help="FinBERT epochs")
    se.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])

    nr = add("ner", _ner, "train a NER model (CRF or transformer) or run it to find unlisted company names")
    nr.add_argument("action", choices=["train", "run"])
    nr.add_argument("--model", choices=["crf", "transformer"], default="crf")
    nr.add_argument("--epochs", type=int, default=4)
    nr.add_argument("--limit", type=int)
    nr.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])

    dd = add("dedup", _dedup, "cluster near-duplicate documents")
    dd.add_argument("--threshold", type=float, default=0.85)

    wk = add("worker", _worker, "run the job queue worker")
    wk.add_argument("--poll", type=float, default=2.0, help="seconds to wait when the queue is empty")
    wk.add_argument("--once", action="store_true", help="drain the queue, then exit")

    pl = add("pipeline", _pipeline, "run the stages in order, one model on the GPU at a time")
    pl.add_argument(
        "--stages",
        nargs="*",
        help="a subset of: parse dedup link ner events sentiment embed events-llm summaries verify",
    )
    pl.add_argument("--limit", type=int)
    pl.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    pl.add_argument("--window", default="365d", help="window for company summaries")
    pl.add_argument("--top", type=int, default=25, help="how many companies get a summary")

    add("llm", _llm, "check that the local LLM server and both models are available")

    gd = add("gold", _gold, "freeze passages, round-trip Label Studio, agreement and gold evaluation")
    gd.add_argument(
        "action", choices=["select", "config", "tasks", "import", "references", "agreement", "eval"]
    )
    gd.add_argument("file", nargs="?", help="the Label Studio export (import) or the references .jsonl")
    gd.add_argument(
        "--quota", help='per document type, e.g. "SEBI adjudication order=40,NCLT admission order=50"'
    )
    gd.add_argument("--calibration", type=int, default=30)
    gd.add_argument("--seed", type=int, default=7)
    gd.add_argument("--annotators", help="Label Studio user ids to names, e.g. 1=asha,2=ben")
    gd.add_argument("--out")
    gd.add_argument(
        "--llm", action="store_true", help="also score the LLM summaries (needs Ollama and the models)"
    )
    gd.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])

    ex = add("export", _export, "build the IEEE DataPort package (annotations only unless --include-text)")
    ex.add_argument("--out", default="data/export/finpulse-corpus-v1")
    ex.add_argument(
        "--include-text", action="store_true", help="include document text (needs the publishers' permission)"
    )
    ex.add_argument(
        "--no-words",
        action="store_true",
        help="also leave out titles, event arguments and claim text, so nothing quotes an order",
    )
    ex.add_argument(
        "--names",
        help="a text file, one name per line, of individuals to remove from titles, events and claims "
        "(besides the person entities); keep it out of the repository",
    )

    oa = add("openapi", _openapi, "write or check the OpenAPI contract the web app is generated from")
    oa.add_argument("--out", default="openapi.json")
    oa.add_argument("--check", action="store_true", help="fail if the file is out of date")

    ec = add("ectsum", _ectsum, "score the summariser on a sample of ECTSum transcripts (ROUGE, attribution)")
    ec.add_argument("--n", type=int, default=60)
    ec.add_argument("--no-nli", action="store_true")
    ec.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])

    cp = add(
        "components",
        _components,
        "measure the claim checker, event extraction and speech, and add rows to the Evaluation page",
    )
    cp.add_argument("--no-nli", action="store_true")
    cp.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])

    bl = add(
        "baselines",
        _baselines,
        "compare with the two model papers, or --extend the stored sentiment rows",
    )
    bl.add_argument(
        "--extend", action="store_true", help="add precision, recall and AUC to the stored sentiment rows"
    )
    bl.add_argument("--device", default="cpu", choices=["cpu", "cuda"])

    xs = add("explain-stats", _explain_stats, "measure Integrated Gradients on a sample of real mentions")
    xs.add_argument("--n", type=int, default=120)
    xs.add_argument("--device", default="cpu", choices=["cpu", "cuda"])

    ab = add("ablation", _ablation, "remove one design choice at a time (retrieval variants, entity marking)")
    ab.add_argument("which", nargs="+", choices=["retrieval", "marking"])

    ask = add("ask", _ask, "ask a question of the corpus, or --eval to measure question answering")
    ask.add_argument("question", nargs="?")
    ask.add_argument("--eval", action="store_true", help="score retrieval, answers and abstention")
    ask.add_argument("--n-each", type=int, default=20, help="questions per kind for --eval")

    em = add("embed", _embed, "embed sentences for dense retrieval")
    em.add_argument("--limit", type=int)
    em.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])

    sv = add("serve", _serve, "run the API")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--reload", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
