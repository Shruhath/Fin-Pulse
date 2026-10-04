# FinPulse — Build Plan (Review 3 / Final Build)

*Team 6 · 23CSE471 NLP · Sania S, Hasini K, Shruhath Reddy*
*Plan date: 2026-10-04 · Demo / review: 2026-10-14 (10 working days)*

This plan turns what the Review 1, CS-3 and Review 2 submissions promised into a working
system: a real UI, API, database, ingestion pipeline and models. Section 11 traces every
promise in the decks to the place it gets built, so nothing a reviewer saw goes missing.

---

## 1. What "done" looks like on 14 October

A reviewer can:

1. Open the dashboard and see a **real corpus**: roughly 1,500–2,500 public Indian disclosures
   from BSE, RBI and SEBI (plus a small NCLT sample), with no fixture numbers left.
2. Open any document and see **entity spans highlighted at character offsets**, each with
   its own sentiment and confidence.
3. Open an entity and see its **sentiment time series**, its **events**, and a **verified
   summary** where every claim is marked entailed, contradicted or unverified, with a link
   to the source sentence.
4. **Paste text, a URL or upload a PDF** and watch it go through the full pipeline live
   (`/analyze`).
5. Open **`/evaluation`** and see real, reproducible numbers: FinBERT vs TF-IDF baseline,
   neural NER vs CRF, LLM events vs rules, and the summarizer vs Lead-3. That includes the
   **transfer gap** between public benchmarks and the Indian gold slice (research
   question 4).
6. Download the **IEEE DataPort package**, with gold and silver labels in separate files.

Minimum defensible core (the part that cannot slip): **ingestion → entities → entity
sentiment with baseline → UI on real data → evaluation page.** Events and summaries are
the second priority, and their simpler fallbacks are listed in §9.

---

## 2. Repository and folder layout

New folder: `/mnt/Data-Share/Academcs/SEM-5/NLP/FinPulse` → pushed to
`github.com/Shruhath/Fin-Pulse` (currently empty).

**The old UI is abandoned (decision 2026-10-04).** The earlier Next.js prototype is
neither imported nor copied. `web/` is built from scratch, with d3 for every
visualization and GSAP for motion (see §13). The old
prototype counts only as evidence of which product behaviours were worth keeping (§13.3),
not as a visual reference.

```
FinPulse/
├── web/                     NEW UI, built from scratch (§13): React + d3 + GSAP
│   └── src/lib/api/         generated TS types from OpenAPI + fetch client
├── server/                  Python 3.11 project (uv)
│   ├── pyproject.toml
│   ├── alembic/             DB migrations
│   └── src/finpulse/
│       ├── core/            settings, logging, ids, offsets utilities
│       ├── db/              SQLAlchemy 2.0 models, session, repositories
│       ├── ingest/          bse.py, rbi.py, sebi.py, nclt.py, rss.py, robots, rate-limit
│       ├── parse/           pdf (PyMuPDF), OCR fallback (Tesseract), HTML (trafilatura)
│       ├── preprocess/      clean, normalize (₹ crore/lakh, dates, CIN), sentences, dedup, prune
│       ├── entities/        gazetteer, EntityRuler, fuzzy resolver, CRF baseline, neural NER
│       ├── sentiment/       entity-aware FinBERT, TF-IDF baseline, calibration
│       ├── events/          Pydantic taxonomy, Qwen extractor, rule baseline
│       ├── summarize/       LexRank pruning, Llama summarizer, Lead-3 baseline
│       ├── verify/          BM25 + dense retrieval, RRF, NLI verifier
│       ├── pipeline/        stage runner, job queue worker, run records
│       ├── api/             FastAPI app + routers
│       ├── eval/            metric harness → results JSON + DB
│       └── export/          IEEE DataPort package builder
│   └── tests/
├── ml/                      training scripts + notebooks (explore only; ship in server/)
│   ├── train_ner.py  train_sentiment.py  baselines.py
│   └── results/             committed metric JSON/CSV per run
├── annotation/              Label Studio configs, guideline.md, kappa script
├── infra/                   docker-compose.yml (postgres+pgvector, label-studio)
├── data/                    git-ignored: raw/, processed/, models/, benchmarks/
├── docs/                    PLAN.md, ARCHITECTURE.md, API.md, DATASET_CARD.md
├── Makefile                 make up / ingest / pipeline / train / eval / web
└── .github/workflows/ci.yml ruff + pytest + bun lint + bun build
```

---

## 3. System architecture

```
                ┌──────────────────────── web (Next.js 16, :3000) ───────────────────────┐
                │ overview · entities · documents · events · summaries · analyze · eval  │
                └───────────────────────────────┬────────────────────────────────────────┘
                                                │ REST (typed from OpenAPI)
                ┌───────────────────────────────▼────────────────────────────────────────┐
                │ FastAPI (:8000)   read endpoints · /analyze · /jobs · /search · /eval    │
                └──────────┬─────────────────────────────────────────────┬───────────────┘
                           │ SQLAlchemy                                  │ enqueue job
                ┌──────────▼──────────────┐                ┌─────────────▼─────────────────┐
                │ PostgreSQL 16 + pgvector│◄──── writes ───│ GPU worker (1 process)          │
                │ docs, sentences+vectors,│                │ claims jobs with SKIP LOCKED    │
                │ entities, mentions,     │                │ runs stages in batches:         │
                │ events, summaries,      │                │  encoders → unload → LLM        │
                │ claims, runs, labels    │                └─────────────┬─────────────────┘
                └──────────▲──────────────┘                              │ HTTP (OpenAI-compatible)
                           │                                ┌────────────▼──────────────┐
                ┌──────────┴──────────────┐                 │ Ollama (native, CUDA)     │
                │ Ingest CLI / cron        │                 │ qwen2.5:7b-instruct  Q4   │
                │ BSE · RBI · SEBI · NCLT  │                 │ llama3.1:8b-instruct Q4   │
                └─────────────────────────┘                 │ MAX_LOADED_MODELS=1       │
                                                            └───────────────────────────┘
```

**Why a Postgres job queue and no Redis or Celery:** there is exactly one GPU, so only one
worker should touch it. `SELECT … FOR UPDATE SKIP LOCKED` on a `jobs` table gives us
retries and status for `/jobs/{id}` with zero extra services.

**Everything runs locally** (decision from 2026-10-04): no hosted LLM APIs. See §3.2 for how both LLMs share the 8 GB GPU.

### 3.1 GPU memory budget (RTX 5060 Laptop, 8 GB)

| Component | Model | VRAM (approx.) | Resident? |
|---|---|---|---|
| NER | `microsoft/deberta-v3-base` fine-tuned (fallback `bert-base-cased`) | ~0.6 GB fp16 | encoder phase |
| Sentiment | `ProsusAI/finbert` fine-tuned, entity-marked | ~0.5 GB fp16 | encoder phase |
| Embeddings | `BAAI/bge-m3` (1024-d) | ~1.2 GB fp16 | encoder phase |
| NLI | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` | ~0.5 GB fp16 | verify phase |
| LLM-1 events | `qwen2.5:7b-instruct` Q4_K_M | ~4.7 GB + KV | LLM phase, alone |
| LLM-2 summary | `llama3.1:8b-instruct` Q4_K_M | ~4.9 GB + KV | LLM phase, alone |

### 3.2 Running the two local LLMs on one 8 GB GPU

**The problem:** with an 8k context each model needs about 5–6 GB including its KV cache
(Qwen 2.5 7B ≈ 4.7 GB weights + ~0.5 GB KV; Llama 3.1 8B ≈ 4.9 GB + ~1.1 GB KV at fp16).
Together that is about 11 GB, which does not fit in 8 GB.

**The solution: time-share the GPU, one model at a time.**

1. **Runtime:** Ollama installed natively with CUDA (`ollama-cuda` on CachyOS), serving
   both GGUF models at Q4_K_M. Settings:

   ```
   OLLAMA_MAX_LOADED_MODELS=1   # never two models on the GPU
   OLLAMA_NUM_PARALLEL=1        # one request at a time, so no duplicated KV cache
   OLLAMA_FLASH_ATTENTION=1
   OLLAMA_KV_CACHE_TYPE=q8_0    # halves KV memory (Llama 8k: ~1.1 GB → ~0.55 GB)
   OLLAMA_KEEP_ALIVE=10m
   ```

   With these settings, Qwen at 8k needs about 5.0 GB and Llama about 5.5 GB, leaving room
   for the CUDA context and the desktop.
2. **Swaps are cheap:** both GGUF files (~9.6 GB) stay in the OS page cache (30 GB RAM),
   so moving from Qwen to Llama means re-uploading weights from RAM to VRAM. That should
   take a few seconds, not a cold disk read (to be measured on Day 1).
3. **The worker owns a GPU lease.** A single worker process runs phases in order and never
   overlaps them:

   | Phase | What runs | Where |
   |---|---|---|
   | A. Encoders | NER, FinBERT, bge-m3 embeddings over the batch | GPU, then freed (`del` + `torch.cuda.empty_cache()`) |
   | B. LLM-1 | Qwen event extraction for every document in the batch | GPU via Ollama |
   | C. LLM-2 | Llama summaries for every document in the batch | GPU via Ollama (one swap) |
   | D. Verify | retrieval + DeBERTa NLI over the claims | GPU (small) or CPU |

   **Batch mode** (the corpus) pays one model swap per batch of 50–100 documents.
   **Live mode** (`/analyze`, one document) runs the encoders on **CPU** (FinBERT and NER
   are fast on 32 cores for a single document). The GPU then only does Qwen, a swap, and
   Llama, for an expected end-to-end time of about 20–40 seconds, streamed to the UI stage
   by stage.
4. **One interface:** LiteLLM (`ollama_chat/qwen2.5:7b-instruct`,
   `ollama_chat/llama3.1:8b-instruct`) with `instructor` for Pydantic validation, plus
   Ollama's JSON-schema `format` for constrained decoding on the event stage. Responses
   are cached in `diskcache`.
5. **Throughput estimate:** about 40–60 tokens/s generation for a 7–8B Q4 model on this
   GPU (estimate, to be measured on Day 1), so roughly 10–20 s per document per LLM stage.
   A 500-document LLM batch then takes about 3–4 hours and runs overnight.
6. **Fallbacks, in order:** reduce `num_ctx` to 4096 (inputs are pruned anyway). If
   memory still runs out, Ollama automatically offloads a few layers to CPU (slower but
   works). The last resort is Qwen2.5-3B / Llama-3.2-3B, disclosed in the report.

The dual-LLM design in the R2 deck (Qwen for structured events, Llama for grounded
summaries) is kept exactly. The only change is that the two models take turns on the GPU
instead of running side by side.

**Blackwell gotcha:** the RTX 5060 is `sm_120`, so it needs **PyTorch ≥ 2.7 with CUDA 12.8
wheels** (`--index-url https://download.pytorch.org/whl/cu128`). Older wheels install
fine and then fail at the first kernel launch. This is checked on Day 1.

---

## 4. Database schema (PostgreSQL + pgvector, Alembic-managed)

| Table | Key columns | Notes |
|---|---|---|
| `sources` | `kind` (BSE/NSE/SEBI/RBI/NCLT/NEWS), `base_url`, `robots_ok` | |
| `documents` | `id`, `source_kind`, `url`, `title`, `doc_type`, `published_at`, `retrieved_at`, `raw_sha256`, `raw_path`, `clean_text`, `n_words`, `lang`, `ocr_used`, `status` (ingested/parsed/analysed/failed), `minhash_cluster` | `raw_sha256` unique → idempotent re-scrapes |
| `sentences` | `doc_id`, `idx`, `char_start`, `char_end`, `text`, `embedding vector(1024)`, `tsv tsvector`, `kept_after_prune` | HNSW index on embedding; GIN on tsv |
| `entities` | `id`, `canonical_name`, `bse_code`, `nse_symbol`, `isin`, `cin`, `sector`, `kind` (company/regulator/bank/person) | from BSE + NSE scrip lists |
| `entity_aliases` | `alias`, `alias_norm`, `entity_id`, `origin` (bse/nse/sentfin/manual) | trigram index for fuzzy match |
| `mentions` | `id`, `doc_id`, `sentence_id`, `entity_id` (nullable), `char_start`, `char_end`, `surface`, `ner_model`, `ner_score`, `link_method`, `link_score` | offsets are into `documents.clean_text` |
| `mention_sentiment` | `mention_id`, `model_version`, `label`, `p_pos`, `p_neg`, `p_neu`, `confidence` (calibrated) | several models side by side for comparisons |
| `events` | `id`, `doc_id`, `entity_id`, `type`, `trigger_start/end`, `arguments jsonb`, `event_date`, `amount_inr`, `confidence`, `schema_valid`, `extractor` (qwen/rules), `run_id` | |
| `summaries` | `id`, `scope` (document/entity_window), `doc_id`, `entity_id`, `window_start/end`, `model`, `prompt_version`, `run_id` | |
| `claims` | `summary_id`, `idx`, `text`, `verification` (entailed/contradicted/unverified), `nli_entail`, `nli_contra`, `evidence_sentence_id`, `retrieval_rank` | contradicted claims are **kept** (UI decision) |
| `runs` | `id`, `stage`, `model`, `prompt_version`, `params jsonb`, `started_at`, `latency_ms`, `status`, `error` | the "recorded evidence" promised on R2 slide 14 |
| `ingest_failures` | `url`, `source_kind`, `failure_class`, `attempts jsonb`, `at` | dead-letter for scrapes that never yielded content |
| `jobs` | `id`, `kind`, `payload`, `status`, `attempts`, `result`, `created_at` | queue for `/analyze` and batch runs |
| `annotations` | `id`, `task` (ner/sentiment/event/summary), `doc_id`, `payload jsonb`, `label_source` (**gold**/**silver**), `annotator`, `created_at` | gold and silver never share a row type → separate exports |
| `eval_results` | `id`, `stage`, `model`, `dataset`, `split`, `metrics jsonb`, `run_id`, `git_sha` | feeds `/evaluation` |
| `entity_daily` (materialized view) | `entity_id`, `day`, `score_mean`, `score_std`, `mentions`, `confidence_mean` | feeds sparklines and the ±1σ aggregate chart |

---

## 5. API contract (FastAPI → `web/`)

The Pydantic response models are the contract. TypeScript types are then
generated from `/openapi.json` with `openapi-typescript`, so the UI and API cannot drift.

| Method & path | Returns | UI consumer |
|---|---|---|
| `GET /api/overview?window=30d` | corpus counts, source mix, aggregate mean ±σ series, top movers | `/` |
| `GET /api/entities?window&sort&q` | `Entity[]` (score, delta, mentions, confidence, series) | `/entities` |
| `GET /api/entities/{id}` | entity + series + recent mentions + `EventRecord[]` + latest `Summary` | `/entities/[id]` |
| `GET /api/documents?source&status&q&page` | `Doc[]` | `/documents`, filing feed |
| `GET /api/documents/{id}` | full `clean_text` + `EntitySpan[]` + events + doc summary | `/documents/[id]` |
| `GET /api/events?type&source&entity&from&to` | `EventRecord[]` | `/events` timeline |
| `GET /api/summaries?entity&window` | `Summary[]` with `Claim[]` | `/summaries` |
| `POST /api/analyze` (text / URL / PDF) | `{job_id}` | `/analyze` (new) |
| `GET /api/jobs/{id}` | status + per-stage progress + result doc id | `/analyze` polling |
| `GET /api/search?q` | hybrid BM25+dense hits (docs, entities) | command palette (cmdk) |
| `GET /api/eval` | `eval_results` grouped by stage | `/evaluation` (new) |
| `GET /api/pipeline/config` | live model names, versions, thresholds | `/settings` |
| `GET /api/health` | db, ollama, gpu status | topbar indicator |

**Contract origin:** the backend's Pydantic models are now the single source of truth,
and the new UI consumes only the generated types. The old `types.ts` contributes its
shapes as a starting point, with these fixes:
- `EventRecord.type`: the **16-type taxonomy** in §6.5, grouped into display categories
  (Corporate action, Dividend, Regulatory, Governance, Insolvency).
- `Sentiment`: model labels are positive/negative/neutral, and the UI chooses its own
  wording.
- `Claim`: carries `evidence: {sentenceId, text, charStart, charEnd}` so the UI can
  highlight the exact supporting sentence.
- New `EvalResult`, `Job` and `JobStage` types for `/analyze` progress and `/evaluation`.

---

## 6. Pipeline: stage by stage

### 6.1 Ingestion (owner area: Sania)

Scrapers are written from scratch on standard, publicly documented scraping practice
(about 300 lines in total):

| Practice (public knowledge) | How FinPulse uses it |
|---|---|
| Tiered fetch ladder: plain HTTP + trafilatura → headless browser only when the cheap tier is empty or blocked | `httpx`/`curl_cffi` first, Playwright only for the NSE stretch goal |
| Retry classification: retry timeouts, 5xx and "blocked"; never retry 4xx, empty or parse errors | `tenacity` predicate in `ingest/http.py` |
| robots.txt denial (or an unreadable robots.txt) is final | checked before every source run |
| Per-source "recipe": API, URL pattern, or follow links | `ingest/bse.py` (JSON API), `sebi.py`/`rbi.py` (listing → detail), `nclt.py` (form) |
| Content-addressed raw storage (`sha256`) + dead-letter table for failures | `documents.raw_sha256` unique; `ingest_failures` table |

| Priority | Source | Method | Target count |
|---|---|---|---|
| P0 | **BSE corporate announcements** | JSON endpoint behind `bseindia.com/corporates/ann.html` (needs Referer/UA headers), attachments as PDF | 1,000–1,500 |
| P0 | **RBI press releases** (penalties on banks/NBFCs) | HTML listing → detail pages | 300–500 |
| P1 | **SEBI enforcement orders** | `sebi.gov.in/enforcement/orders` HTML index → PDF | 200–400 |
| P2 | **NCLT orders** | small sample, scanned → OCR path showcase | 30–50 |
| P2 | News via **RSS only** (ET, Moneycontrol, BS) | store URL, title and extracted text locally; **publish offsets and labels only** | 300 |
| stretch | NSE | `curl_cffi` impersonation, only if time allows | — |

Every scraper checks `robots.txt`, rate-limits to ≤1 request/second, retries with
`tenacity` and backoff, stores the raw file keyed by `sha256`, and is idempotent.

**Entity gazetteer seed (Day 2):** the public BSE "List of Scrips" plus NSE `EQUITY_L.csv`
give scrip code, symbol, ISIN and legal name. SEntFiN's alias list is added if the data is
obtainable.

### 6.2 Parsing and preprocessing (Sania)

- **PDF:** PyMuPDF text layer. If a page has under ~50 characters, it goes through the OCR
  fallback (pdf2image → OpenCV deskew/binarize → Tesseract), and `ocr_used` is recorded.
- **HTML:** trafilatura main-content extraction.
- **Cleaning:** `ftfy` fixes broken characters, then NFKC normalization, whitespace
  repair, and stripping of repeated page headers and footers (lines that recur on ≥50% of
  pages).
- **Regex pre-pass (deterministic, unit-tested):** ₹/Rs. amounts with crore/lakh
  normalized to an INR number, Indian date formats converted to ISO, 21-character CIN,
  ISIN, statute references ("Section 11B of the SEBI Act"), and BSE scrip codes.
- **Sentence splitting:** spaCy plus custom exceptions for "Ltd.", "Pvt.", "No.", "Rs.",
  "Sr.", and abbreviation-heavy legal text. Character offsets are preserved throughout.
- **Deduplication:** `datasketch` MinHash/LSH (Jaccard ≥ 0.85). The same disclosure on BSE
  and in news gets clustered, and the canonical copy is kept.
- **Pruning:** LexRank via `sumy`, plus boilerplate-sentence filters, to choose the
  `kept_after_prune` sentences that feed the LLM stages.

### 6.3 Entities: detection and resolution (Shruhath + Sania)

- **Rule layer:** a spaCy `EntityRuler` built from the gazetteer aliases. It gives high
  precision, and its matches double as silver training data.
- **Neural NER:** `deberta-v3-base` token classifier trained on FinEntity spans plus
  silver gazetteer spans from our corpus. Metric: seqeval span F1.
- **Classical baseline:** `sklearn-crfsuite` CRF with word shape, POS, and
  gazetteer-membership features.
- **Resolution:** exact alias match, then normalized match (lowercase, strip
  Ltd/Limited/Pvt/The, `&`↔and), then `rapidfuzz` token-set ratio ≥ 92, otherwise left
  unresolved and shown as such. Metric: linking accuracy on the gold slice.

### 6.4 Entity-level sentiment (Shruhath)

- **Input format:** the sentence with the target mention wrapped in markers:
  `… [E] Yes Bank [/E] was penalised …`. The marker tokens are added to the tokenizer, so
  one sentence produces one prediction per entity.
- **Model:** fine-tune `ProsusAI/finbert` on FinEntity plus SEntFiN, with Financial
  PhraseBank as auxiliary sentence-level warm-up. Training uses class weights for the
  neutral skew and fp16, and fits on the 8 GB GPU.
- **Baselines:** TF-IDF (word and character n-grams over a ±10-token window around the
  entity) with logistic regression or linear SVM, plus off-the-shelf FinBERT with no
  entity marking (the "document-level label" strawman).
- **Calibration:** temperature scaling on the dev set, reporting ECE before and after. The
  UI's four-segment confidence uses the calibrated value.
- **Metrics:** macro-F1, weighted-F1, confusion matrix, ECE, and a McNemar test between
  FinBERT and the baseline. Reported separately on FinEntity test, SEntFiN test and the
  **Indian gold slice**; the gap between them answers research question 4.

### 6.5 Event extraction: LLM-1, Qwen 2.5 7B (Hasini)

**Taxonomy (16 types, as promised in R2):**

| Group | Types |
|---|---|
| EDT corporate (11) | Acquisition, Clinical Trial, Guidance Change, New Contract, Stock Repurchase, Stock Split, Reverse Split, Regular Dividend, Special Dividend, Dividend Cut, Dividend Increase |
| India-specific (5) | SEBI Penalty / Enforcement, RBI Regulatory Action, NCLT Insolvency Admission, Share-Pledge Invocation, Auditor Resignation |

- Each type is a **Pydantic v2 model** with typed arguments (e.g. `SEBIPenalty: entity,
  amount_inr, regulation_section, order_date, authority`), and they are combined as a
  discriminated union.
- **Extraction:** Ollama's OpenAI-compatible endpoint with JSON-schema structured output,
  wrapped by `instructor` for validation and up to 2 retries. The input is the pruned
  sentences (numbered), the resolved entities, and the taxonomy with one-line definitions.
  The model must return a `trigger_sentence_id`, which is mapped back to character offsets.
- **Rule baseline:** BSE's own announcement category/subcategory field plus keyword/regex
  triggers per type. The BSE category also gives **free silver labels**.
- **Metrics:** event-type F1, argument F1, schema-validity %, latency per document.
- **Cache:** `diskcache` keyed on a hash of (model, prompt_version, input), so re-runs
  cost nothing.

### 6.6 Grounded summarization: LLM-2, Llama 3.1 8B (Hasini)

1. Prune the document to the top-k sentences with LexRank, or for entity summaries, to
   the entity's mention sentences plus its event triggers.
2. Llama 3.1 8B writes 3–5 sentences from **only** the numbered evidence and must cite
   `[S12]`-style IDs.
3. **Baselines:** Lead-3 and pure LexRank (extractive).
4. **Metrics:** ROUGE-1/2/L and BERTScore on a 50–100 transcript ECTSum sample (compute
   bound), plus attribution precision and unsupported-claim rate on our gold summaries.

### 6.7 Verification: retrieval + NLI (Hasini, with Shruhath on evaluation)

- For each claim, retrieve candidates with **BM25** (Postgres full-text search or
  `rank_bm25`) and **dense** search (bge-m3 + pgvector HNSW), then fuse the rankings with
  hand-written **Reciprocal Rank Fusion** (k = 60) and keep the top 5.
- Run NLI (DeBERTa-v3-base MNLI/FEVER/ANLI) on each (evidence, claim) pair and take the
  best evidence. Label the claim entailed if p(entail) ≥ 0.7, contradicted if
  p(contradict) ≥ 0.7, and unverified otherwise. Thresholds are tuned on a dev set.
- Claims and their evidence are stored, and **contradicted claims are shown, never
  dropped**.

### 6.8 Annotation and gold data (all three members)

- **Label Studio** runs in Docker with a single project config covering entity spans,
  per-entity sentiment and event type.
- `annotation/guideline.md` is written on Day 4. Everyone labels the same **30-document
  calibration set** (for Cohen's/Fleiss' κ), then about 40 more each, for roughly 150 gold
  documents. That is smaller than the "50 each plus" in the notes, but honest for 10 days.
- About 30 human-written reference summaries with source sentence IDs, for attribution
  evaluation.
- LLM-produced labels go to `label_source = silver` only. The LLM-vs-human agreement is
  itself reported as a finding.

### 6.9 Evaluation harness

`finpulse eval <stage> --model … --dataset …` writes `ml/results/<stage>/<run>.json`
(committed) and an `eval_results` row, and the `/evaluation` page renders the latest. Every
row carries its git SHA and data snapshot hash. **No number appears in the UI unless it
came from this harness.**

### 6.10 IEEE DataPort export

`finpulse export dataport` builds `finpulse-corpus-v1/`: README, LICENSE (CC BY 4.0),
`documents.parquet` (regulatory text in full; news as URL plus offsets only),
`sentences.parquet`, `entities.parquet`, `entity_gazetteer.csv`, `sentiment_gold.jsonl`,
`sentiment_silver.jsonl`, `events_gold.jsonl`, `summaries_gold.jsonl`, and
`splits/{train,dev,test}.txt`. No third-party benchmark data is bundled.

---

## 7. Benchmark datasets: download on Day 1

| Dataset | Source | Stage | Note |
|---|---|---|---|
| FinEntity | HF `yixuantt/FinEntity` | NER + sentiment | primary Stage-1 benchmark |
| SEntFiN 1.0 | paper / authors / Kaggle mirror | sentiment + aliases | **verify availability Day 1**; if unavailable, say so and use FinEntity + FPB |
| Financial PhraseBank | HF `takala/financial_phrasebank` | sentiment warm-up | CC BY-NC-SA (fine for research, do not redistribute) |
| FiQA Task 1 | HF `TheFinAI/fiqa-sentiment-classification` | sentiment (optional) | score thresholds ±0.1, documented |
| EDT | GitHub `Zhihan1996/TradeTheEvent` | events | taxonomy + eval |
| ECTSum | GitHub `rajdeep345/ECTSum` | summaries | small eval sample |

---

## 8. Day-by-day schedule (5–14 Oct 2026)

**Human tasks** are things only the team can do. Everything else is build work. Every day ends
with a push.

| Day | Date | Backend / ML (commits) | UI from scratch (commits) | Human tasks |
|---|---|---|---|---|
| **1** | Sun 5 Oct | Monorepo skeleton; uv project; docker-compose (pgvector); Alembic schema v1; CI; Makefile; Torch cu128 GPU smoke test; Ollama + both models + swap timing; benchmark downloads | Product brief for the UI; visual direction agreed by the team | Pick the visual direction (one decision) |
| **2** | Mon 6 Oct | BSE + RBI scrapers; raw store; PDF/HTML parsing; gazetteer from BSE/NSE lists | Vite/Next scaffold; design tokens (light/dark); type scale; GSAP + d3 setup; app shell + navigation; reduced-motion policy | — |
| **3** | Tue 7 Oct | Cleaning + regex normalizers with tests; sentence splitter; MinHash dedup; LexRank pruning; SEBI scraper; FastAPI `/documents`, `/health`; OpenAPI → TS types | Document reader: offset-anchored entity spans (d3-free DOM), sentence focus, source metadata; wired to the real API | — |
| **4** | Wed 8 Oct | EntityRuler + fuzzy resolver; CRF NER baseline; TF-IDF sentiment baseline | Entity index + entity page: d3 sentiment series (pinned −1..1 scale, ±1σ band), mention list | Review guideline; start 30-doc calibration labelling |
| **5** | Thu 9 Oct | NER fine-tune; **entity-marked FinBERT + calibration**; GPU worker + job queue; Stage 1 over the corpus; `/entities`, `/overview` | Overview: d3 market dispersion view, source mix, movers; GSAP entrance choreography | Continue labelling |
| **6** | Fri 10 Oct | Event taxonomy; Qwen extractor; rule baseline; event eval; `/events` | Events: d3 timeline (16 types, 5 groups), filters, event detail with trigger highlight | Label events on the calibration set |
| **7** | Sat 11 Oct | Retrieval (BM25 + bge-m3 + RRF); Llama grounded summary; NLI verifier; `/summaries`; `/analyze` jobs | Verified summary (claim → evidence links, contradicted claims visible); `/analyze` live pipeline view with GSAP stage timeline | Write ~30 reference summaries |
| **8** | Sun 12 Oct | κ script; gold import; eval harness across stages; NCLT OCR sample | `/evaluation`: d3 comparison charts (model vs baseline, transfer gap), confusion matrices, reliability diagram | Finish gold slice; resolve disagreements |
| **9** | Mon 13 Oct | Full batch run; error analysis; perf fixes; DataPort export; docs | Accessibility and responsive audit, one polish pass (desktop + mobile), empty/loading/error states | Update review deck with real numbers |
| **10** | Tue 14 Oct | Buffer only: fixes, demo script, tag `v1.0.0` | Buffer | **Review** |

Estimated **10–18 commits per day, about 130 in total** (backend and UI tracks in parallel). Each commit is small, focused and
leaves the build green.

---

## 9. Risks and fallbacks

| Risk | Likelihood | Fallback |
|---|---|---|
| PyTorch/CUDA does not work on Blackwell `sm_120` | Medium | cu128 wheels; worst case, train on Kaggle and infer on CPU (FinBERT runs fine on 32 cores) |
| 8 GB VRAM too tight for a 7B/8B model at 8k context | Medium | Reduce `num_ctx` to 4096 (inputs are pruned anyway); worst case Qwen2.5-3B / Llama-3.2-3B, reported honestly |
| LLM throughput too slow for the full corpus | High | Events and summaries on a 300–500-document subset plus on-demand via `/analyze`; sentiment covers everything |
| BSE/SEBI block or change their endpoints | Medium | Polite rate limits, cached raw files; RBI + RSS as a guaranteed floor |
| SEntFiN not obtainable | Medium | FinEntity + FPB only; the gap claim leans on the Indian gold slice |
| Annotation time runs short | High | Smaller gold slice (≥60 docs) with κ on 20; report it honestly |
| Scope creep in events or summaries | High | Rule baseline + Qwen only, and document-level summaries before entity-window summaries |

**Honesty rule throughout:** the UI shows real outputs or nothing. Leftover fixtures are
removed, not mixed in. Metrics come only from the harness.

---

## 10. Commit conventions

- **Message style:** Conventional Commits (`feat(ingest): …`, `fix(api): …`,
  `test(preprocess): …`, `docs: …`), describing the change itself.
- **Size:** small, focused commits; every commit leaves the build green.
- **Branching:** work lands on `main` in small green commits (CI on every push), with a
  release tag at the end of the project.
- **Never committed:** data, model weights, `.env` files, or anything under `data/`.

---

## 11. Promise traceability (what the decks said → where it is built)

| Promised in | Promise | Built in |
|---|---|---|
| R2 sub-objective 1 | Entity detection + alias/ticker/legal-name merge | `entities/` §6.3 |
| R2 sub-objective 2 | FinBERT entity sentiment vs TF-IDF + LR on macro-F1 | `sentiment/` §6.4 |
| R2 sub-objective 3 | EDT 11 + 5 India event types, Pydantic-validated | `events/` §6.5 |
| R2 sub-objective 4 | Extractive prune → abstractive → NLI-verified summary | `summarize/`, `verify/` §6.6–6.7 |
| R2 sub-objective 5 | DataPort corpus, gold and silver separate | `export/` §6.10, `annotations` table |
| R2 sub-objective 6 / RQ4 | Western → Indian transfer measured | §6.4 metrics on the gold slice |
| R2 slide 7 | OCR, dedup, alias resolution, class imbalance | §6.2, §6.3, §6.4 |
| R2 slide 11 | CRF+gazetteer NER baseline; ECE; trigger/arg F1; ROUGE/BERTScore/attribution | §6.3–6.9 |
| R2 slides 13–16 | Dual LLM: Qwen 2.5 7B events, Llama 3.1 8B summary, LiteLLM/Instructor, NLI | §3.1, §6.5, §6.6 |
| R2 slide 14 | Each run stores model, prompt version, sentence IDs, validity, confidence, latency | `runs` table §4 |
| R2 slide 16 | Weak evidence → flag uncertainty; no investment advice | unverified state + UI disclaimer |
| CSV tech stack | FastAPI, PostgreSQL, PyTorch, HF, FinBERT, CRF, gensim, BM25+FAISS, Pydantic, PyMuPDF, OCR, Label Studio, Docker | throughout (pgvector in place of FAISS for persistence; FAISS kept for offline eval) |
| R1 slide 10 | FiQA score → 3-class thresholding | §7 |
| Syllabus | regex, tokenization, n-grams, edit distance, POS, CRF, TF-IDF, Word2Vec (gensim on our corpus), BM25/VSM, NER, coreference/alias, sentiment, IE, summarization | spread across §6; Word2Vec nearest-neighbour + n-gram perplexity figure in the error-analysis notebook (Day 9) |

---

## 12. Defaults (open to change)

- Project folder `/mnt/Data-Share/Academcs/SEM-5/NLP/FinPulse`. The old UI and its history
  are not imported; the UI is rebuilt from scratch (§13).
- Ollama runs **natively** (better GPU access than Docker on this machine), and Postgres
  plus Label Studio run in Docker.
- Gold slice of about 150 documents; LLM stages run on a 300–500-document subset plus on
  demand.
- No LangChain or LlamaIndex: the plain `instructor` + Ollama/LiteLLM approach the
  tech-stack notes recommend.

---

## 13. The new UI: built from scratch

**Decision (2026-10-04):** the earlier Next.js prototype is abandoned and the UI is rebuilt
from zero. The team pinned the visual direction: **FinPulse looks and behaves like a tiling
window manager.** It has numbered workspaces, tiled windows with gaps and a focused border,
a status bar, a keyboard-first launcher, and retiling layouts. Inside each window, the controls
stay standard and accessible.

| Library | Role |
|---|---|
| **d3** | Every data visualization is hand-built: sentiment series, dispersion band, event timeline, evaluation comparisons, confusion matrix, reliability diagram, and the desktop wallpaper (contours of company sentiment) |
| **GSAP** (with Flip) | Motion with a purpose: windows physically retile between master-stack, grid and monocle; workspaces slide in; the `/analyze` pipeline timeline. `prefers-reduced-motion` is honoured everywhere |

### 13.1 Process

1. Write a product brief (users, job, principles) and agree the visual direction.
2. Build workspace by workspace, in schedule order (§8). Each one is wired to the API from its
   first commit; synthetic preview data exists only behind `FINPULSE_PREVIEW=1`, with a
   permanent banner on screen.
3. Finish with one batched audit (desktop + mobile, accessibility, contrast), one fix
   batch, and a written design-system record.

### 13.2 Workspaces

| # | Workspace | Windows |
|---|---|---|
| 1 | Overview | market sentiment chart (master), latest filings, movers, source mix |
| 2 | Companies | companies table, company sentiment chart, verified summary, events, mentions |
| 3 | Filings | filing list, reader with offset-anchored spans, entity inspector, verified summary |
| 4 | Events | d3 swimlane timeline across 16 types in 5 groups, event log, event inspector |
| 5 | Analyze | input (text, URL, PDF), live pipeline timeline, entities, events, summary |
| 6 | Evaluation | model-vs-baseline comparison and transfer gap, confusion matrix, calibration, all metrics, agreement |
| 7 | Method | pipeline diagram, research questions, datasets, sources and ethics, team |

Keyboard: `1–7` workspaces, `h/j/k/l` focus, `f` maximise, `t` cycle layout, `/` or `Ctrl K`
launcher, `d` day/night, `?` help.

### 13.3 Product principles

- Sentiment scales are pinned to −1..1 and never fitted to the data.
- The aggregate view shows dispersion, not only the mean.
- Contradicted claims stay visible.
- Spans render by slicing the model's character offsets.
- Confidence is shown coarsely (quantised), not as false precision.
- State is encoded by icon and colour together (colour-blind safe).
- Counters are never seeded at zero.

### 13.4 Stack

Next.js (App Router) + TypeScript + Tailwind v4 + d3 v7 + GSAP 3 (`@gsap/react`, Flip), served
by bun. Primary user: Indian retail investors and independent analysts. The UI is a demo-ready
analyst tool, with the Evaluation and Method workspaces serving the reviewers.
