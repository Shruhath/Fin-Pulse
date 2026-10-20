# FinPulse backend

What exists in `server/`, how to run it, what it measured on the real corpus, and where it differs from
`PLAN.md`. Figures marked with a date were produced by running the commands on this machine.

## Run it

```bash
docker compose -f infra/docker-compose.yml up -d db     # PostgreSQL 16 + pgvector on :5433
scripts/ollama-local.sh start && scripts/ollama-local.sh pull   # private GPU Ollama on :11435, both models
cd server && uv sync --extra ml --extra neural --extra export  # Python 3.11
uv run alembic upgrade head
uv run finpulse gazetteer seed                          # NSE security master + SEntFiN aliases
uv run finpulse ingest corpus                           # layer 2 documents (SEBI, NCLT) -> documents
uv run finpulse ingest rbi                              # today's RBI press releases (run daily)
uv run finpulse sentiment train --model tfidf           # classical baseline
uv run finpulse sentiment train --model finbert         # entity-marked FinBERT, calibrated
uv run finpulse ner train --model crf                   # and --model transformer
uv run finpulse pipeline                                # every stage, one model on the GPU at a time
uv run finpulse serve                                   # API on :8000, docs at /docs
uv run finpulse worker                                  # job queue worker for /api/analyze and /api/ask
uv run finpulse ask "What action did SEBI take against Rajesh Exports Limited?"
uv run finpulse ask --eval                              # silver question-answering evaluation
uv run python ../scripts/fetch_models.py asr            # the speech model for spoken questions (290 MB, once)
uv run pytest && uv run ruff check . && uv run ruff format --check .
```

`make up`, `make pipeline`, `make train`, `make eval` and `make test` wrap the same commands.

**The whole stack for a demo:** `make live` (`scripts/live.sh`) starts the database, the private Ollama,
the API, the worker and the web app on real data and stops them together on Ctrl-C; API and worker logs
are in `data/logs/`. `scripts/live.sh preview` serves the web app alone on the labelled synthetic preview
data, which is the fallback if the backend cannot be run. Models load from the local cache only
(`HF_HUB_OFFLINE=1`) unless `FINPULSE_ONLINE=1`.

## Pipeline

| Stage | Module | Output |
|---|---|---|
| ingest | `ingest/corpus.py`, `ingest/rbi.py`, `ingest/fetch.py` | `documents`, keyed by SHA-256. RBI comes from its RSS feed (one request per run); `fetch` is the guarded single-URL fetch behind `/api/analyze` |
| parse | `parse/`, `pipeline/parse.py` | PyMuPDF text layer; a page under 20 words is OCR'd with Tesseract; paragraphs rebuilt from line spacing |
| clean, normalise, sentences, dedup | `preprocess/` | repaired text, ₹ amounts as exact INR, day-first dates, identifiers, rule-based sentence spans, MinHash clusters |
| link | `entities/`, `pipeline/link.py` | gazetteer matcher plus the parties named in order titles |
| ner | `ner/`, `pipeline/ner.py` | CRF and DeBERTa token classifier find company names the gazetteer lacks |
| events (rules) | `events/rules.py` | SEBI penalties, restraints and settlements, NCLT admissions, RBI actions |
| sentiment | `sentiment/`, `pipeline/sentiment.py` | TF-IDF baseline or entity-marked FinBERT with temperature scaling |
| embed | `embed/`, `pipeline/embed.py` | bge-base-en-v1.5 vectors (768-d) in pgvector |
| events (LLM) | `events/llm.py`, `pipeline/llm_events.py` | Qwen 2.5 7B, JSON-schema constrained, arguments validated against the taxonomy |
| summaries | `summarize/`, `pipeline/summaries.py` | Llama 3.1 8B writes cited claims for a document or a company over a window |
| verify | `verify/`, `pipeline/verify.py` | BM25 + dense retrieval fused with RRF, DeBERTa NLI: entailed, contradicted or unverified |
| gold, eval, export | `gold/`, `eval/`, `export/` | frozen passages, Label Studio round trip, agreement, scores against gold, the DataPort package |
| orchestration | `pipeline/batch.py` | phases in the order that never puts two models on the GPU together |
| live path | `pipeline/analyze.py`, `pipeline/jobs.py`, `pipeline/worker.py` | one document through every stage, progress on the job row; encoders on the CPU, LLM stages only when the models are available. A document analysed this way is flagged `is_submission` (migration 0006): readable by id, never part of the corpus aggregates, events, search or the window the overview is anchored on |
| voice | `asr/`, `api/routers/voice.py` | a spoken question to text: Whisper (`whisper-base.en`) on the CPU from the local cache, prompted with the companies the corpus mentions most; the browser records and converts to 16 kHz WAV |
| ask | `qa/`, `pipeline/ask.py`, `eval/qa.py` | a question about the corpus: the companies and publishers it names narrow a BM25 + dense search over every sentence (RRF), Llama writes claims that cite numbered sentences or declines, NLI judges each claim; the answer is the job's `result` |

**GPU budget.** 8 GB, so one model at a time. Encoders (FinBERT, the embedder, NLI) run in their own phase and
are released (`neural/device.release`) before Ollama loads Qwen; Qwen is unloaded before Llama; both
are unloaded before the NLI phase. `OLLAMA_MAX_LOADED_MODELS=1` enforces it on the server side.

**Private Ollama.** Another Ollama (CPU-only, in Docker) already owns :11434 on this machine and Docker
has no NVIDIA runtime, so `scripts/ollama-local.sh` copies the Ollama binary and its CUDA 13 runner out of
the `ollama/ollama` image and serves on :11435 with the host driver. No root and no system package.

## Measured results

Figures below are re-generated by the commands above; each run also writes `ml/results/*.json` and
`eval_results` rows with the commit and data hash.

**Corpus (19 Oct 2026).** 263 documents (SEBI 198, NCLT 55, RBI 10), 41,223 sentences, all embedded
(bge-base-en-v1.5). 4,571 mentions of 453 entities; 69 mentions stay unresolved rather than guessed.
(The first full run found 4,676 mentions; a precision rule for bare tickers followed by more capitalised words
("ACC Energy Storage" is not ACC Limited) and three title-parsing fixes removed 105 false ones, and the
corpus was relinked and rescored.)

**Entity-level sentiment** (macro-F1, then expected calibration error; held-out test splits):

| Model | FinEntity (n=219) | SEntFiN, Indian headlines (n=1,405) |
|---|---|---|
| FinBERT off the shelf, sentence-level | 0.697, ECE 0.214 | 0.672, ECE 0.172 |
| TF-IDF + logistic regression, entity window | 0.754, ECE 0.040 | 0.801, ECE 0.024 |
| **Entity-marked FinBERT, fine-tuned and calibrated** | **0.920**, ECE 0.046 | **0.873**, ECE 0.030 |

Fine-tuned FinBERT beats the TF-IDF baseline on both sets (McNemar exact test p = 3e-6 and 3e-10).
Temperature scaling (T = 1.48) cut ECE on SEntFiN from 0.077 to 0.030 and left FinEntity unchanged
(0.045 to 0.046). The off-the-shelf FinBERT, which has neither entity markers nor fine-tuning, is 22 and 20 points behind; separating
the two effects would need a fine-tuned run without markers, which was not done.

**Company-name NER** (exact-span F1; the gazetteer excludes SEntFiN-derived aliases so no test headline
leaks into it):

| Model | FinEntity (n=86 sentences) | SEntFiN (n=1,020) |
|---|---|---|
| Gazetteer rules (NSE master + titles) | 0.011 | 0.274 (P 0.93, R 0.16) |
| CRF + word shape + gazetteer features | 0.800 | 0.845 |
| **DeBERTa-v3-base token classifier** | **0.952** | **0.912** |

**Events.** The rule baseline stores 142 events (62 SEBI penalties, 14 settlements, 13 restraints, 52 NCLT
admissions, 1 RBI action). Qwen 2.5 7B (prompt `events-v3`, JSON-schema constrained) stores 281 events from
the 253 SEBI and NCLT documents in about 19 minutes (about 4.5 s per document): 220 SEBI Penalty, 53 NCLT
Admission, 6 Acquisition, 1 Stock Repurchase, 1 Stock Split. 246 of 281 (87.5%) validate against the typed
argument models. The 35 that do not are mostly orders the model called a "SEBI Penalty" that are consent
orders, abatements or "no action" decisions, which is a precision problem, not a formatting one. Recall of
either extractor is unmeasured until the gold passages are labelled.

**Summaries and verification.** Llama 3.1 8B wrote 57 document summaries and 25 company summaries
(354 claims). Retrieval plus NLI judged them: 207 entailed (58%), 52 unverified (15%), 95 contradicted (27%).
Treat the contradicted share as an upper bound: sentence-level NLI has no coreference, so a claim that says
"Amit Enterprise issued a purchase order" is scored against a sentence that says "The Petitioner issued a
purchase order" and can come out contradicted. The 0.7 thresholds are the plan's, untuned (tuning needs
gold).

**Summary quality on ECTSum** (public earnings-call benchmark, 40 transcripts sampled with a fixed seed,
ROUGE F1 against the reference bullets; BERTScore not computed):

| System | ROUGE-1 | ROUGE-2 | ROUGE-L |
|---|---|---|---|
| Lead-3 | 0.088 | 0.016 | 0.065 |
| LexRank, top 3 sentences | 0.145 | 0.034 | 0.099 |
| **Llama 3.1 8B, cited claims** | **0.196** | **0.068** | **0.132** |

Against the transcript, NLI (five BM25-retrieved sentences per claim) found 65% of Llama's claims entailed,
12% contradicted and 23% unsupported. The references are terse bullets, so every ROUGE figure is low in
absolute terms; the comparison between rows is the point. The model's JSON occasionally truncates and is
retried with the error message (no transcript was skipped).

**What the numbers say about the domain.** Fine-tuned FinBERT calls 96.5% of the 4,502 scored mentions in
SEBI and NCLT orders neutral (the TF-IDF baseline, 94%). Models trained on headlines read legal procedure as
neutral. That is the domain gap behind research question 4, and sentiment on this corpus should not be
presented as a finding until the gold slice measures it.

**Speed (RTX 5060 Laptop, 8 GB).** FinBERT fine-tuning 3.4 minutes for four epochs; DeBERTa NER 4.1 minutes;
embedding 41,223 sentences 93 s; Qwen about 4.5 s per document; verification of 171 claims 14 s.


**Question answering (20 Oct 2026, silver).** `finpulse ask --eval` builds 80 questions from the corpus's own
extracted events (20 each; no human wrote them or their answers, so these are silver figures) and scores the
system against a BM25-only baseline:

| Question kind | What is measured | System | BM25 only |
|---|---|---|---|
| names a company ("What action did SEBI take against X?") | a relevant filing among the 8 retrieved sentences | 1.00 | 0.95 |
| gives only an amount ("Which company was penalised Rs. 4,39,725?") | the same | 0.35 | 0.35 |
| names a listed company no filing mentions | abstains | 1.00 | |
| asks something no filing discusses (a share price target) | abstains | 0.85 | |
| answerable questions (40) | answered rather than abstained | 0.575 | |
| claims in those answers | confirmed / contradicted by NLI | 0.51 / 0.21 | |

Reading it plainly: naming the company does most of the work (it limits the search to that company's
filings), dense search adds nothing for amounts, and about half of the claims the model writes are confirmed
by a cited sentence. An answer none of whose claims is confirmed is shown as a draft and not offered as an
answer, which is why only 57.5% of answerable questions end in one. Claims on questions that name a company
are confirmed 65% of the time, on amount-only questions 34%.

Three things were measured and decided on this set, so they are not independent of it: giving NLI the
filing's title with each sentence lifted confirmed claims from 0.32 to 0.51 (kept, with a known risk: the
title can bridge a party and a sentence that are not about the same person, and one hallucinated claim
about Wipro reached an entailment probability of 0.65, just under the 0.7 threshold); judging a claim also
against all its cited sentences joined added 0.02 (dropped); keeping a grouped amount such as `4,39,725`
as one BM25 token made the baseline worse (0.35 to 0.20) and the system barely better, so the tokenizer
is unchanged. The first version of the amount question printed "₹43.9725 lakh", which no filing says; it
now uses the lakh-grouped rupees an order writes. Latency on the RTX 5060 is 2 to 16 seconds an answer
(retrieval 0.1 to 0.6 s, the model 1 to 5 s, NLI 1 to 11 s on the CPU, longest for NCLT orders); the LLM
cache makes a repeated question instant, so the evaluation does not report latency. One question in 80 made
the model return JSON that stayed invalid after three attempts and ended as a no-answer.

**Spoken questions (20 Oct 2026).** The chat accepts a spoken question. The browser records (it stops by itself
after a pause), converts the audio to 16 kHz mono WAV and posts it to `POST /api/transcribe`; the text lands in
the question box to be checked and sent, or is sent at once if "send the question when I stop talking" is
ticked. The browser's own speech recognition is not used because it streams audio to a third party; this keeps
to the rule that models run locally, and the recording is decoded in memory and never written to disk.

Whisper is told what is being asked: each request carries a prompt that sounds like the questions ("A question
about SEBI, NCLT and RBI filings, such as a penalty of Rs. 25 lakh or Rs. 4,39,725") followed by the spoken
forms of 70 companies (the 25 with the newest extracted events, so every suggested question can be said, then
the 45 in the most filings). Three guards keep a poor recording from becoming a confident wrong question:
a recording whose peak is below -40 dBFS is not sent to the model, a transcript that loops or reads the prompt
back is dropped, and output length is capped by the audio's duration.

On six questions about this corpus spoken by an offline text-to-speech voice (Piper, US English), each heard
three ways (16 kHz, a 22 kHz file resampled by the server, and a 24 kbit/s Opus round trip as the browser's
recorder produces), 18 utterances and 171 words: word error rate 0.205 without the prompt and 0.035 with it,
about 1 s per question on the CPU, 3 to 5 s more on the first request while the model loads. Driven through
the real page with a fake microphone playing the same six questions, two words were wrong in 57 ("Why" heard
as "Hawaii" when the first syllable was clipped, "take" as "tick"). The caveat that matters: this is synthetic
speech in one accent. Indian-accented speech and a real microphone have not been measured, and a company that is
in neither group of 70 gets no help from the prompt (the text is editable before it is sent for that reason;
`FINPULSE_ASR_MODEL=openai/whisper-small.en` is slower and better with accents and names). Listening to an answer
(a "listen" button) uses the operating system's voice and only appears when the browser offers a voice that runs
on this machine; none was available here, so that button is untested.

## API contract

`server/openapi.json` is the contract (CI fails when it is out of date: `uv run finpulse openapi`).
Fields are camelCase on the wire. A value the pipeline has not produced is `null`, and an empty corpus
returns empty lists.

| Endpoint | Notes |
|---|---|
| `GET /api/overview?window=` | `7d`, `30d`, `90d`, `365d`, `all`; windows are anchored on the newest document date (`asOf`) |
| `GET /api/entities`, `/api/entities/{slug}` | companies and banks with a scored mention in the window; `delta` compares with the window before |
| `GET /api/documents`, `/api/documents/{id}` | detail has `clean_text` with PANs masked to the same length, spans, events, summary |
| `GET /api/events` | `window`, `type`, `entity`, `extractor` (`best` shows a document's LLM events when it has any) |
| `GET /api/summaries` | document and company summaries with claims, verification and evidence |
| `GET /api/search?q=` | companies by fuzzy alias match, documents by full-text search with highlighted snippets |
| `GET /api/eval` | newest run per model and dataset, with calibration before and after and McNemar p-values |
| `GET /api/search/index`, `/api/wallpaper`, `/api/status` | what the launcher and desktop read |
| `POST /api/analyze`, `/api/analyze/file` | text, URL or PDF/HTML upload; returns `{jobId}`; 429 when 50 jobs are queued |
| `GET /api/jobs/{id}` | status and seven stages with timings and notes |
| `POST /api/ask` | `{question}` (3 to 500 characters); returns `{jobId}`; the worker answers it |
| `POST /api/transcribe` | a PCM WAV recording (the web app sends 16 kHz mono, up to 60 s) in, `{text, seconds, model}` out; nothing is stored; 415 for other formats, 503 when the speech model is not installed |
| `GET /api/ask/{id}`, `/api/ask/suggestions` | status, three stages (retrieve, answer, verify) and the answer with claims, verdicts, evidence offsets and the sentences read; suggestions are built from the newest extracted events |
| `GET /api/health`, `/api/pipeline/config` | database, Ollama, GPU, Tesseract, active model |

URL analysis fetches one page at the user's request: http(s) only, public addresses only (also after
redirects), robots.txt honoured (an unreadable one counts as a refusal), 15 MB cap.

## Gold data

`finpulse gold select` freezes 120 passages (default quotas: 40 adjudication, 15 whole-time member,
15 settlement, 50 NCLT; half built around a rule-detected event, half around ordinary text; 30 shared
for calibration). `gold config` and `gold tasks` write the Label Studio configuration and tasks;
`gold import` reads the export; `gold agreement` checks the gates; `gold eval` scores rules, the LLM,
NER, sentiment and summaries against it. See `annotation/README.md`. Without gold annotations nothing
is recorded, so no number can appear without human labels behind it.

## Export

`finpulse export` writes `finpulse-corpus-v1/` for IEEE DataPort: annotations, offsets, hashes and URLs
only, never document text, unless `--include-text` is given. Gold and silver are separate files; SEntFiN
aliases and individuals are left out. Publishing it is a human decision. See `docs/DATASET_CARD.md`.

## Differences from `PLAN.md`

- **Sentence splitting** is a rule-based splitter, not spaCy: deterministic, no model, unit-tested on
  the legal cases. The entity rule layer is a token-trie matcher, not a spaCy `EntityRuler`.
- **Fuzzy linking** uses `token_sort_ratio >= 92`, not `token_set_ratio`, which scores a subset as 100
  ("Yes Bank" would match "Yes Bank of America").
- **SEntFiN entities** are filtered to company-like names; its list also holds groups and institutions
  ("Supreme Court", "Stock exchanges") that flooded the matcher with false mentions.
- **LLM client** is a small `httpx` client with JSON-schema `format` and an on-disk cache, not LiteLLM
  plus `instructor`. Retries with the validation error give the same behaviour with fewer dependencies.
- **Event schema** sent to the model is flat (type, trigger sentence, entity, arguments); arguments are
  validated against the per-type Pydantic models afterwards, which is where `schema_valid` comes from.
  Small models handle a flat schema far more reliably than a discriminated union.
- **Embeddings** are BAAI/bge-base-en-v1.5 (768-d, English), not bge-m3 (1024-d, multilingual): the corpus is
  English, the weights were already on this machine and bge-m3 is 2.3 GB at 1.2 MB/s. Queries get BGE's
  retrieval instruction. Changing the model needs a migration (the column dimension).
- **Retrieval** uses a hand-written BM25 over the candidate sentences instead of Postgres full-text
  rank, and pgvector cosine for the dense side; fusion is RRF with k = 60.
- **BSE is not collected.** Its terms prohibit redistribution, its robots.txt is unreadable and the
  endpoint is undocumented. The collector interface and the robots/rate-limit/dead-letter pattern are in
  place (`ingest/fetch.py`, `ingest/rbi.py`); adding BSE needs written permission first. RBI is read
  from its RSS feed only because its robots.txt sits behind a bot wall.
- **`eval_results.detail`, `claims.cited`, `agreements`, `gold_passages`** were added (migrations 0002 to 0004).

## Not done

- Written permission from SEBI, BSE, NSE and RBI, and the ethics check, are human steps (see
  `docs/DATASETS.md` section 10 on the dataset-research branch).
- Gold annotation itself: the tooling is complete, the labels are not.
- Event and entity recall are still unmeasured, and the question-answering numbers are silver (generated from the
  corpus's own events) until gold exists.
- Short forms an order defines for itself (`(hereinafter "ACC")`) still resolve to the listed company; that needs
  coreference, as does the contradicted-claim rate.
