# FinPulse

*Read the market before it moves.*

An India-focused NLP pipeline over regulatory disclosures. It resolves the companies a document
mentions, scores sentiment for each company separately, extracts structured corporate events, and writes
short summaries in which every claim is linked to the sentence that supports it, or marked as unsupported.
Nothing is asserted without evidence.

Built by Team 6 for 23CSE471 Natural Language Processing, Amrita School of Computing.

## What is in it

| Stage | What it does | Models |
|---|---|---|
| Ingest and parse | SEBI orders, NCLT admission orders (via IBBI) and RBI press releases; text layer first, OCR for scans | Tesseract 5 |
| Entities | Company mentions as character offsets, linked to a gazetteer of listed companies and banks | alias matcher; CRF and DeBERTa-v3 token classifier (trained, not on the default path) |
| Sentiment | One label per company mention, not per document | entity-marked FinBERT, fine-tuned and temperature-calibrated; TF-IDF + logistic regression as the baseline |
| Events | 16 typed events (EDT's 11 plus 5 India-specific) with trigger spans and typed arguments | Qwen 2.5 7B (JSON-schema constrained); a rule baseline |
| Summaries | Claims, each checked against retrieved source sentences | Llama 3.1 8B; bge-base-en-v1.5 retrieval; DeBERTa-v3 NLI |
| Ask | Questions answered from the corpus with cited claims, or declined; typed or spoken | the same retrieval, Llama and NLI; Whisper base.en for speech |

Every language model runs on the machine it is started on, through Ollama or Hugging Face. Nothing is sent
to a hosted API, and spoken questions are transcribed locally; the browser's own speech recognition is not
used because it streams audio to a third party.

## Run it

You need Docker, [uv](https://docs.astral.sh/uv/), [bun](https://bun.sh/) and, for the language models, an
NVIDIA GPU with about 8 GB of memory.

```bash
make up && make migrate     # PostgreSQL + pgvector on :5433, a private Ollama on :11435
make llm                    # pull the two local models (once)
cd server && uv sync --extra ml --extra neural --extra export
uv run python ../scripts/fetch_models.py asr    # the speech model, 290 MB (once)
cd .. && make live          # database, models, API, worker and web app: http://localhost:3000
```

`make live` loads models from the local cache only. On a machine that has never downloaded them, run it
once with `FINPULSE_ONLINE=1`. Voice needs a secure page, so open the app on `localhost`, not a LAN address.

Without a backend, `scripts/live.sh preview` serves the web app on clearly labelled synthetic data.

The corpus (`data-set/`) and everything derived from it (`data/`) are git-ignored. `docs/BACKEND.md` lists
the commands that build the database from the collected documents, train the models and run every stage.

## Layout

```
server/   Python package `finpulse`: ingest, parsing, pipeline stages, job queue, FastAPI service, tests
web/      Next.js app, eight workspaces; its API types are generated from server/openapi.json
infra/    docker compose for PostgreSQL + pgvector and the optional annotation tool
scripts/  local model server, model download, one-command stack
docs/     PLAN.md (design), BACKEND.md (how it runs and what it measured), DATASET_CARD.md, ANALYSIS.md
annotation/  Label Studio setup for the gold labels
ml/       results of every training and evaluation run, kept so a number traces to a commit
```

## What has been measured

Full tables, with their conditions, are in `docs/BACKEND.md`.

- **Sentiment**, test split of each public dataset, macro-F1: fine-tuned entity-marked FinBERT 0.920 on FinEntity
  and 0.873 on SEntFiN, against 0.754 and 0.801 for TF-IDF + logistic regression (McNemar p < 1e-5).
- **Company-name NER**, exact-span F1: DeBERTa-v3 0.952 and 0.912; a CRF 0.800 and 0.845.
- **Summaries**, 40 ECTSum transcripts, ROUGE-L: 0.132 for Llama with cited claims, 0.065 for Lead-3.
- **Question answering**, 80 machine-made questions: the right filing is in the top 8 sentences for every
  question that names a company, and the system abstains on every question about a company that is not in the
  corpus. About half of the claims it writes are confirmed by NLI.

## What has not

- **Gold labels do not exist yet.** The 120 frozen passages are still to be annotated, so the recall of the
  entity linker and of the event extractors is unmeasured, and the question-answering figures are silver.
- **Sentiment on regulatory text is weak.** Models trained on news headlines call 96.5% of the mentions in
  SEBI and NCLT orders neutral. Read the sentiment as a domain-gap finding, not as a signal.
- **Linking has no coreference.** `(hereinafter "ACC")` resolves to the listed company even when the order is
  about a different one.
- **Spoken questions** were tested on synthetic speech only.

The collected corpus is small: 263 documents (SEBI and NCLT orders and RBI press releases).

## Data and licences

The corpus is collected from public regulator sources at one request per second with an identifying
User-Agent; `docs/DATASET_CARD.md` lists what is taken from each and under what terms. Order text is not
republished: the dataset package carries offsets, hashes and labels, and includes text only if its manifest
says so. Orders name individuals; see the card's privacy section before reusing anything.

This is a student project and is not investment advice.
