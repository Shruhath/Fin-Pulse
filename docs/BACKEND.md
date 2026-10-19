# FinPulse backend

What exists in `server/` today, how to run it, and where it differs from `PLAN.md`. Numbers
below were produced by running the commands on the layer 2 corpus (`data-set/layer2`) on
19 Oct 2026.

## Run it

```bash
docker compose -f infra/docker-compose.yml up -d db     # PostgreSQL 16 + pgvector on :5433
cd server && uv sync --extra ml                         # Python 3.11
uv run alembic upgrade head
uv run finpulse gazetteer seed                          # NSE security master + SEntFiN aliases
uv run finpulse ingest corpus                           # layer 2 documents -> documents table
uv run finpulse parse --workers 12                      # text layer, OCR for scans, sentences
uv run finpulse link                                    # title parties + gazetteer aliases -> mentions
uv run finpulse events                                  # rule baseline -> events
uv run finpulse sentiment train                         # TF-IDF baseline, writes ml/results/
uv run finpulse sentiment score                         # score linked mentions
uv run finpulse serve                                   # API on :8000, docs at /docs
uv run finpulse worker                                  # job queue worker for /api/analyze
uv run pytest && uv run ruff check . && uv run ruff format --check .
```

## Pipeline

| Stage | Module | Output |
|---|---|---|
| ingest | `ingest/corpus.py` | `documents` row per collected file, keyed by SHA-256, so it is idempotent |
| parse | `parse/`, `pipeline/parse.py` | PyMuPDF text layer; a page under 20 words is rendered and read with Tesseract (`ocr_used`); paragraphs are rebuilt from line spacing; `clean_text` and `sentences` with exact offsets |
| clean | `preprocess/clean.py` | mojibake repair, NFKC, running headers, footers and page numbers removed, hyphenated line breaks repaired |
| normalise | `preprocess/normalize.py` | ₹ amounts to exact INR (crore, lakh, lakh crore), day-first dates, CIN, ISIN (check digit validated), PAN masking, statute references |
| dedup | `preprocess/dedup.py` | MinHash LSH clusters (Jaccard 0.85) |
| entities | `entities/`, `pipeline/link.py` | gazetteer of 2,683 NSE and SEntFiN companies; token-trie matcher; resolver (normalised alias, then fuzzy); parties read from titles |
| sentiment | `sentiment/`, `pipeline/sentiment.py` | TF-IDF + logistic regression over a ±10-word window with the entity masked |
| events | `events/`, `pipeline/events.py` | 16-type taxonomy with typed argument models; rule extractor for SEBI penalties, restraints, settlements and NCLT admissions |
| eval | `eval/sentiment.py` | trains, evaluates on the held-out splits, writes `ml/results/sentiment/*.json` and `eval_results` rows with git SHA and data hash |
| api | `api/` | read endpoints, `/api/analyze`, `/api/jobs/{id}`, `/api/health` |
| queue | `pipeline/jobs.py`, `pipeline/worker.py` | `FOR UPDATE SKIP LOCKED`, retries, per-stage progress on the job row |

## Results on the real corpus

| | |
|---|---|
| Documents | 253 (SEBI 198, NCLT 55); 217 read from the text layer, 36 scans read with OCR |
| Text | 1.1 million words, 40,715 sentences (median 22 words) |
| Near-duplicates | 6 documents repeat an earlier one |
| Entities | 2,683 gazetteer entities plus 282 created from order titles |
| Mentions | 4,653 (3,563 gazetteer matches, 1,090 title parties); 89 left unresolved, not guessed |
| Events (rules) | 141: 62 SEBI penalties, 14 settlements, 13 restraints, 52 NCLT admissions; 0 fail their schema |
| Sentiment baseline | FinEntity test (n=219) macro-F1 0.754, ECE 0.040; SEntFiN test (n=1,405) macro-F1 0.801, ECE 0.024 |

Two things these numbers do not say, on purpose:

- **Event recall is unmeasured.** The rule baseline finds an operative sentence in 52 of 55 NCLT
  orders and 62 of 120 adjudication orders. Some of the rest correctly contain no penalty
  ("no penalty is imposed", abated proceedings), but how many were missed is only known once the
  gold slice exists.
- **The baseline does not transfer to regulatory prose.** Trained on news headlines, it labels
  94% of the corpus's mentions neutral (4,283 of 4,564 scored). That is a finding about the
  domain gap (research question 4), not a model to present as working on orders.

## API contract

Response models are in `api/schemas.py` and the OpenAPI document at `/openapi.json` is the
contract. Fields are camelCase on the wire. A value the pipeline has not produced is `null`
(scores before a sentiment model has run, `confidence` of a rule event), and an empty corpus
returns empty lists.

| Endpoint | Notes |
|---|---|
| `GET /api/overview?window=` | `7d`, `30d`, `90d`, `365d`, `all`. Windows are anchored on the newest document date (`asOf`), not on today |
| `GET /api/entities`, `/api/entities/{slug}` | companies and banks with a scored mention in the window; `delta` compares with the window before |
| `GET /api/documents`, `/api/documents/{id}` | detail has `clean_text` with PANs masked to the same length, spans, events and summary |
| `GET /api/events` | filter by `window`, `type`, `entity` |
| `GET /api/eval` | newest run per model and dataset, as recorded by the harness |
| `GET /api/search/index`, `/api/wallpaper`, `/api/status` | what the launcher and desktop read |
| `POST /api/analyze` | `{text}` or `{url}`, returns `{jobId}` |
| `POST /api/analyze/file` | multipart PDF or HTML, up to 15 MB |
| `GET /api/jobs/{id}` | status and seven stages with timings and notes |
| `GET /api/health`, `/api/pipeline/config` | database, Ollama, GPU, Tesseract, active model |

URL analysis fetches one page at the user's request: http(s) only, public addresses only
(also after redirects), robots.txt honoured (an unreadable one counts as a refusal), 15 MB cap.

## Differences from `PLAN.md`

- **Sentence splitting** is a rule-based splitter with an abbreviation list, not spaCy. It is
  deterministic, has no model dependency and is unit-tested on the legal cases.
- **Entity rule layer** is a token-trie matcher, not a spaCy `EntityRuler`.
- **Fuzzy linking** uses `token_sort_ratio >= 92`, not `token_set_ratio`: the set variant scores a
  subset as 100, so "Yes Bank" would match "Yes Bank of America".
- **SEntFiN entities** are filtered to company-like names. Its list also holds groups and
  institutions ("Supreme Court", "Stock exchanges", "hotel companies") that flooded the matcher
  with thousands of false mentions on the first run.
- **`eval_results.detail`** (migration 0002) holds the confusion matrix and reliability bins.
- **The LLM stages are not built.** `summary` and `verify` are reported as skipped, with the
  reason, in every job. No Qwen or Llama model is pulled yet.

## Next

1. Pull `qwen2.5:7b-instruct` and `llama3.1:8b-instruct` into Ollama and build the extractor and
   the summary stage on the taxonomy in `events/taxonomy.py`.
2. Retrieval plus NLI verification of summary claims (pgvector HNSW and BM25 are in the schema).
3. Fine-tune `ProsusAI/finbert` with entity markers and compare it with the baseline in `ml/results/`.
4. Select the 120 gold passages, OCR and freeze them, annotate, and report event and entity
   recall against gold.
5. Collectors for BSE and RBI once the permission emails are answered.
