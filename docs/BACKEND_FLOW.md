# How FinPulse runs behind the screen

This file follows what happens **when you click something**: which part of the system is called, which model
runs, what is read from or written to the database, and what comes back. For what each page *shows*, read
`docs/APP_GUIDE.md` first. For measured results and commands, see `docs/BACKEND.md`.

---

## 1. The parts, and who talks to whom

These parts work together. `make live` starts the database, Ollama, the API, the worker and the web server; the browser is yours:

```
 Browser  -->  Web server (Next.js :3000)  -->  API (FastAPI :8000)  -->  Database (:5433)
    |                                               ^                           ^
    +--- questions, uploads, voice (direct) --------+                           |
                                                                                |
 Worker  ------------ reads and writes jobs and results -----------------------+
    |-- Ollama (:11435, GPU): Qwen 2.5 7B, Llama 3.1 8B
    +-- inside Python: FinBERT, bge embedder, DeBERTa NLI, Whisper, Tesseract
```

| Part | Where it lives | What it does |
|---|---|---|
| **Browser** | your screen | Shows the pages. For slow jobs (an answer, an analysis, a voice question) it talks **straight to the API**. |
| **Web server** (Next.js) | `web/`, port 3000 | Builds each page. When a page needs data, this server asks the API for it, then sends the finished page to the browser. |
| **API** (FastAPI) | `server/src/finpulse/api/`, port 8000 | The only door to the data. Answers "give me X" by reading the database. Starts slow jobs by putting a row in the `jobs` table. |
| **Database** | Postgres with pgvector, port 5433 | Everything we know: documents, sentences, companies, sentiment, events, summaries, claims, jobs, results. |
| **Worker** | `finpulse worker` (a separate program) | Picks queued jobs (an *ask* or an *analyze*) one at a time and runs the models. |
| **Ollama** | port 11435 (our own copy) | Runs the two big language models on the GPU: **Qwen 2.5 7B** and **Llama 3.1 8B**. |

`scripts/live.sh` (run by `make live`) starts the database, Ollama, the API, the worker and the web server.
Logs: `data/logs/api.log` and `data/logs/worker.log`.

**Two ways the app gets data**

1. **Reading what is already stored.** Almost every page. The models did their work earlier and saved the
   results in the database. Opening a page only runs database queries. **No model runs when you open a page.**
2. **Live jobs.** Only three things run models at the moment you click: **Ask**, **Analyze**, and the
   **microphone**.

When there is no database, `scripts/live.sh preview` serves fake data built into the web server, and the API is
never called. That is the yellow "Synthetic preview" banner.

---

## 2. How the data got into the database in the first place (the "pipeline")

Before anyone opens the app, a batch run (`finpulse pipeline`) takes every collected document through these
steps in order. Each step writes its results to the database. The pages are just windows onto those results.

| # | Step | What it does | Tool or model | Saved in |
|---|---|---|---|---|
| 1 | **Collect** | SEBI and NCLT orders are downloaded politely (one request a second) and RBI press releases are read from RBI's feed. Each document is identified by a SHA-256 hash of its content, so the same file is never stored twice. | plain downloads | `documents`, raw files in `data/raw/` |
| 2 | **Parse** | Get the text out. PDFs are read with their text layer; a page with fewer than 20 words is treated as a scan and read with OCR. | PyMuPDF, **Tesseract** | `documents.clean_text` |
| 3 | **Clean and split** | Repair the text, turn ₹ amounts and dates into exact values, split into sentences with a rule-based splitter built for legal text, remove near-duplicate documents. | rules, MinHash | `sentences` |
| 4 | **Find companies** (link) | Find company names in the text as exact character positions and link each to the right company. Uses a list of NSE-listed companies and aliases, plus the parties named in an order's title. | rule-based matcher (a word trie, longest match wins) | `entities`, `entity_aliases`, `mentions` |
| 5 | **Events by rules** | Find events with hand-written patterns (SEBI penalties and settlements, NCLT admissions, RBI actions). | rules | `events` (extractor "rules") |
| 6 | **Sentiment** | For each mention, read about 800 characters around it and give probabilities for positive, negative, neutral. The score is *P(positive) − P(negative)*. | **FinBERT, fine-tuned** with the company marked in the text, then calibrated (the baseline is TF-IDF + logistic regression) | `mention_sentiment`; then the view `entity_daily` is refreshed |
| 7 | **Embed** | Turn every sentence into a list of 768 numbers so that sentences with similar meaning sit close together. | **bge-base-en-v1.5** | `sentences.embedding` (pgvector) |
| 8 | **Events by LLM** | Read the most useful sentences of a document and write the events as structured JSON, each pointing at the sentence that triggered it. The output is forced to match a schema. | **Qwen 2.5 7B** through Ollama | `events` (extractor "llm") |
| 9 | **Summaries** | Write 3 to 5 short claims for a document, or for a company over a time window, each naming the numbered sentences it rests on. It may use nothing else. | **Llama 3.1 8B** through Ollama | `summaries`, `claims` |
| 10 | **Verify** | For every claim, find the best evidence sentences, then ask an NLI model whether the evidence *entails*, *contradicts* or says nothing about the claim. | search (BM25 + embeddings, fused), **DeBERTa-v3 NLI** | `claims.verification`, scores, evidence sentence |
| 11 | **Evaluate** | Train and test the models and record scores. | `finpulse sentiment train`, `finpulse ask --eval`, and so on | `eval_results` |

Every step that runs a model also writes a row in `runs` (which model, which prompt version, how long it took).

**One model on the GPU at a time.** The GPU has 8 GB. The batch run does steps in an order that never puts two
models on it together: small models first, then Qwen alone, then Llama alone, then the checker. A step that
cannot run (a model is missing, Ollama is off) is skipped with a reason and the run carries on.

**Roughly who owns what:** Sania, steps 1 to 4 (data, cleaning, integration); Hasini, steps 5 and 8 to 10
(events, summaries, checking claims); Shruhath, steps 6 and 11 (sentiment and evaluation).

**What is *not* in the default run:** the two company-name models (a CRF and a DeBERTa token classifier) were
trained and measured but are left out of the default run, because on legal text they also pick up roles such
as "Financial Creditor". No page calls them.

**How a score turns into what you see**

- A company's **sentiment score on a day** = the average of *P(positive) − P(negative)* over its mentions that
  day (`entity_daily`).
- **Sentiment over a window** = those daily averages weighted by how many mentions each day had.
- **Neutral / positive / negative label:** the score is called positive above +0.15, negative below −0.15,
  neutral in between.
- **Change** = the score in this window minus the score in the window of the same length just before it.
- **Confidence** = the average of the model's highest probability across the mentions.
- "The window" ends on the date of the newest document, not today.

---

## 3. What each page does when it opens

The **web server** asks the API (in `web/src/lib/api/client.ts`). Every call below is a read from the database.

**Every app page** also asks for two small things for the menu:

| Call | What it returns | Used for |
|---|---|---|
| `GET /api/status` | counts of documents, companies, events | the line at the bottom of the left menu |
| `GET /api/search/index` | the 800 busiest companies and 500 newest filings (names only) | the Ctrl K search; the matching is done in the browser, with no call per keystroke |

| Page | Calls (made by the web server) | What the API reads | Model run? |
|---|---|---|---|
| **Start page** `/` | `/api/status`, `/api/eval` | counts; `eval_results` (the bars compare the best model with the best baseline per dataset) | no |
| **Home** | `/api/overview?window=`, `/api/ask/suggestions` | overview: `documents` (30 newest in the window), `entity_daily` (market line and the top 40 companies with their change), `events` (up to 200), source counts. Suggestions: the newest SEBI Penalty, NCLT Admission and RBI Action events, turned into question templates | no |
| **Companies** | `/api/entities?window=`, `/api/overview?window=` | companies with a scored mention in the window (up to 200), with daily series; the overview supplies the market strip and event outlines for the map | no |
| **A company** | `/api/entities/{name}?window=` | `entity_daily` (score, change, chart), `entity_aliases`, `events` for that company, the 40 newest `mentions` with their sentence and `mention_sentiment`, and the latest company `summaries` with `claims` | no |
| **Filings** | `/api/documents` | the 50 newest documents and the companies and sentiment found in each | no |
| **A filing** | `/api/documents/{id}` | the whole text (PAN numbers masked, same length, so positions still line up), every mention as start and end positions with its sentiment, the events, the latest document summary with its claims and evidence | no |
| **Events** | `/api/events?window=` | `events` in the window. For a document that has events from both Qwen and the rules, the Qwen ones are shown; otherwise the rule ones | no |
| **Evaluation** | `/api/eval` | `eval_results`: the newest run of each model on each dataset, plus the confusion matrix and calibration of the main sentiment model | no |
| **Method** | none | nothing (the page is written text) | no |
| **Ask** (on opening) | `/api/ask/suggestions`, `/api/health` | suggestions as above; health tells whether the speech model is installed (so the microphone is enabled) | no |
| **Analyze** (on opening) | none | nothing until you press Run | no |

**How the filing page's marks are made.** The API sends the text and a list of positions
("characters 412 to 431 are a company mention"). The browser cuts the text at exactly those positions to draw
the underlines. It never searches for the name, so a wrong position would show up as a visibly wrong mark.

**How "Show source" finds the sentence.** Each claim stores the position of its evidence sentence in the
document. Pointing at a claim tells the page "highlight characters a to b of document d"; the text on the left
highlights that range and scrolls to it. Opening a source from another page uses `?at=a-b` in the address.

---

## 4. What happens when you press things

### 4.1 Ask: a question, from click to answer

You type a question on **Ask** (or on **Home**, or in the search box, which hand it to Ask).

```
 1. BROWSER   POST /api/ask {question}                                   (straight to the API)
 2. API       checks: 3 to 500 characters; fewer than 50 jobs waiting
              inserts a row in  jobs  (kind "ask", status "queued", three stages) -> returns {jobId}
 3. BROWSER   asks  GET /api/ask/{jobId}  about every 1 second; draws the three stations from job.stages
 4. WORKER    (checks the table every 2 s) claims the oldest queued job, then runs three stages:

    STAGE 1  retrieve  ("Find sentences")
       a. read the question: look for company names (the same matcher used for linking) and for
          words such as SEBI, RBI, NCLT. These narrow the search to documents that mention that
          company or come from that publisher.
       b. turn the question into numbers with the bge embedder (on the CPU)
       c. two searches over the sentences in those documents, each keeping its best 40:
            - by words: BM25
            - by meaning: pgvector cosine distance on sentences.embedding
       d. merge the two lists (reciprocal rank fusion) and keep the best 8 different sentences
       -> nothing found? the answer is "No collected filing mentions <company>." and stages 2 and 3 are skipped

    STAGE 2  answer  ("Write the answer")
       Llama 3.1 8B (Ollama) gets the question and the 8 numbered sentences, and must reply as JSON:
       whether the sentences answer the question, and 1 to 4 short claims, each listing the sentence
       numbers it used. It has up to 3 tries to give valid JSON.
       -> "not answerable"? the answer is "The retrieved sentences do not answer this question."

    STAGE 3  verify  ("Check each claim")
       The DeBERTa NLI model (CPU) compares each claim with the sentences it cited and the 2 best
       retrieved sentences. The sentence is given together with its filing's title, because the title
       names the party that "the Noticee" would otherwise hide.
         entailed       if the support score >= 0.7 and is not lower than the conflict score
         contradicted   else if the conflict score >= 0.7
         not verified   otherwise
       If no claim is entailed, the answer is held back and shown only as "the draft".

 5. WORKER    stores the whole answer as JSON in  jobs.result , marks the job done, writes a row in  runs
 6. BROWSER   sees "done" on its next check and draws the claims, the sources and the sentences it read
```

Models used: the bge embedder, Llama 3.1 8B, DeBERTa NLI. Reads: `documents`, `mentions`, `sentences`.
Writes: `jobs`, `runs`. Nothing is added to the corpus. The conversation you see is kept in the browser tab
only.

### 4.2 Analyze: your own document, from click to result

```
 1. BROWSER   paste text:  POST /api/analyze {text, source}
              web address: POST /api/analyze {url, source}
              PDF file:    POST /api/analyze/file  (the file itself)
 2. API       text: makes the document row right away (flagged is_submission, so it stays out of the
                    corpus; the same text sent twice reuses the same row)
              URL:  only queues the job (the worker will download it)
              file: checks it is a PDF or HTML file of at most 15 MB, saves it in data/raw/uploads/,
                    makes the document row
              then inserts a row in  jobs  (kind "analyze", seven stages) -> returns {jobId}
 3. BROWSER   asks  GET /api/jobs/{jobId}  every second; fills in the seven stations with times and notes
 4. WORKER    runs the seven stations:

    Ingest      URL: a careful download (web links only, public addresses only even after redirects,
                robots.txt obeyed, 15 MB limit). Text or file: just loads the row.
                (A document that was analysed before skips everything else.)
    Parse       text is used as it is; PDF: text layer, with Tesseract OCR on pages that have under 20
                words; HTML: the main text is extracted. Then cleaning and sentence splitting.
    Companies   the rule-based matcher plus the parties in the title -> mentions
    Sentiment   FinBERT (fine-tuned) on the CPU, keeping the GPU free for the language models; if no
                FinBERT is trained it uses the TF-IDF baseline; then the daily view is refreshed
    Events      by rules (SEBI, NCLT and RBI documents), and by Qwen 2.5 7B if Ollama has it
    Summary     Llama 3.1 8B writes 3 to 5 claims
    Verify      for each claim, BM25 over the document's own sentences plus the sentences it cited,
                then the NLI model. (No embeddings in this live path, so search is by words only.)

 5. WORKER    marks the document "analysed" and the job done
 6. BROWSER   on "done" calls  GET /api/documents/{documentId}  and draws the result with the same
              page layout as a filing
```

A stage that cannot run says why instead of pretending (for example "the summary model is not available").
If a stage crashes, the job goes back in the queue once; after that it is marked failed and the stage shows the
reason.

Models used: Tesseract (scans), the matcher, FinBERT, Qwen, Llama, DeBERTa NLI. Writes: `documents`,
`sentences`, `mentions`, `mention_sentiment`, `events`, `summaries`, `claims`, `jobs`, `runs`.

### 4.3 Microphone: a spoken question

```
 1. BROWSER   records from the microphone; stops after you pause; converts the sound to
              16 kHz mono WAV (in the browser)
 2. BROWSER   POST /api/transcribe   (the WAV file, straight to the API)
 3. API       refuses files over about 12 MB or over 60 seconds, or that are not WAV
              checks that someone actually spoke (a very quiet recording is answered with empty text)
              builds a hint: the names of about 70 companies (the ones with the newest events plus the
              ones named in the most filings) so the model spells them right
              runs Whisper base.en on the CPU
 4. API       returns {text}. Nothing is saved: the sound is decoded in memory and dropped.
 5. BROWSER   puts the text in the question box (or sends it, if "Send when I stop talking" is ticked);
              from here it is an ordinary Ask (4.1)
```

The browser's own speech recognition is *not* used, because that streams your voice to another company.
The **Listen** button uses only the voices already installed on your computer.

### 4.4 Search (Ctrl K), time windows, tabs, sorting, expanding

These do **not** call a model, and most do not call the API:

| You do | What happens |
|---|---|
| Ctrl K, type a name | the browser filters the list it already has (companies and filings loaded with the page) |
| Type a sentence of 3+ words, press Enter on "Ask the filings" | goes to Ask with the question in the address; Ask sends it as in 4.1 |
| Click 7 / 30 / 90 days | the address changes to `?w=7d` (or `90d`); the page is rebuilt by the web server with new API calls |
| Switch a tab, sort a table, search in a list, press "Show more" | done in the browser on data already loaded |
| Click a company or filing | opens the next page, which makes its own calls (section 3) |
| Dark theme | saved in the browser only |

---

## 5. Which model is used for what

| Model | Job | Runs on | Used by |
|---|---|---|---|
| **FinBERT**, fine-tuned (`finbert-entity`, from `ProsusAI/finbert`) | sentiment for one company in a sentence | GPU in the batch run, CPU in Analyze | pipeline step 6, Analyze |
| TF-IDF + logistic regression | the simple sentiment baseline (and the fallback) | CPU | Evaluation page comparisons |
| **bge-base-en-v1.5** | sentence meaning as 768 numbers, for search | GPU in the batch run, CPU in Ask | pipeline step 7, Ask |
| **Qwen 2.5 7B** (`qwen2.5:7b-instruct`) | events as structured JSON | GPU, through Ollama | pipeline step 8, Analyze |
| **Llama 3.1 8B** (`llama3.1:8b-instruct-q4_K_M`) | summaries and answers, each claim citing sentences | GPU, through Ollama | pipeline step 9, Ask, Analyze |
| **DeBERTa-v3 NLI** (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`) | does a sentence support or contradict a claim | GPU in the batch run, CPU in Ask and Analyze | pipeline step 10, Ask, Analyze |
| **Whisper base.en** (`openai/whisper-base.en`) | speech to text | CPU | microphone |
| **Tesseract 5** | reading scanned pages | CPU | pipeline step 2, Analyze |
| CRF and DeBERTa token classifier | company-name finding (trained and measured, not in the default run) | - | Evaluation page only |

All of them run on this laptop. Nothing is sent to an outside service. During `make live`, models are loaded
from the local cache only.

---

## 6. The database, in one glance

| Table | One row is | Written by |
|---|---|---|
| `documents` | one filing (or one analysed document, flagged `is_submission`) | collect, Analyze |
| `sentences` | one sentence of a document, with its positions and its embedding | parse, embed |
| `entities`, `entity_aliases` | a company or person, and the names it is written as | gazetteer, link |
| `mentions` | one place a company is named: exact start and end positions | link |
| `mention_sentiment` | the model's reading for one mention, per model version | sentiment |
| `entity_daily` *(a view)* | one company, one day: average score, spread, count, confidence | refreshed after sentiment |
| `events` | one extracted event: type, trigger sentence, party, details, who extracted it | rules, Qwen |
| `summaries`, `claims` | a summary, and each claim in it with its verdict, scores and evidence sentence | Llama, verify |
| `jobs` | one Ask or Analyze request: status, stages with timings, result | API, worker |
| `runs` | one execution of a pipeline stage: model, prompt version, time taken | every stage |
| `eval_results` | one measured score of one model on one dataset | evaluation |
| `annotations`, `agreements`, `gold_passages` | human labelling (not filled yet) | gold tools |

Rule of thumb: **machine labels and human labels never share a table row**. Nothing on the Evaluation page can
appear without a stored run behind it.

---

## 7. When something looks wrong, where to look

| Symptom | Check |
|---|---|
| Pages say "Nothing to show yet" | the API is down: `curl http://127.0.0.1:8000/api/health` |
| Ask or Analyze never leaves "Waiting for the worker" | the worker is not running; see `data/logs/worker.log` |
| An answer says "the answer model is not running" | Ollama on port 11435 is down or the model is missing (`scripts/ollama-local.sh`); `/api/health` lists the models it has |
| The microphone is greyed out | not on `localhost`, no microphone, or the speech model is missing (`scripts/fetch_models.py asr`); `/api/health` shows `asrModel` |
| A stage says "skipped" in Analyze | the note on the station says why (model not trained, not pulled, or extra not installed) |
| Numbers on a page look old | the models ran earlier; new documents need `finpulse pipeline` (or Analyze for a single document) |
| "The queue is full" | 50 jobs are waiting; there is one GPU worker, so it is a wait, not a bug |

`/api/health` reports the database, Ollama and its models, the GPU, Tesseract, the active sentiment model, the
speech model and how many jobs are queued. `/api/runs` lists the recent pipeline runs with their models and
timings.
