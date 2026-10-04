# FinPulse — Project Analysis

*Team 6 · 23CSE471 NLP · written 2026-10-04 from every file in `Submissions/Team`*
*(Review 1 deck + PDF, CS-3 abstract, research paper, R2 deck and its 7 variants in `remade/`, Context notes, team CSV)*

The build plan that follows from this analysis is in [PLAN.md](PLAN.md).

---

## 1. What FinPulse is

**"Read the market before it moves."** FinPulse is an NLP pipeline that turns Indian
financial text (BSE/NSE announcements, SEBI orders, RBI notifications, NCLT orders, news)
into structured, verifiable intelligence:

```
Collect → Prepare → Entities → Sentiment → Events → Grounded summary → Verify
```

| Stage | Promised to reviewers | Baseline | Metric |
|---|---|---|---|
| Collect / Prepare | Scraping, PDF parsing, OCR for scans, dedup, boilerplate pruning | — | — |
| Entities | Token-classifier NER + alias/ticker merging (SEntFiN alias list) | CRF + gazetteer | span F1, alias-linking accuracy |
| Sentiment | Fine-tuned FinBERT, **one sentiment per company**, not per article | TF-IDF + logistic regression | macro-F1, weighted-F1, ECE |
| Events | **Qwen 2.5 7B** fills a strict JSON schema: EDT's 11 types + 5 India types | rules | trigger/argument F1, schema-validity % |
| Summary | LexRank pruning → **Llama 3.1 8B** short brief | Lead-3 | ROUGE, BERTScore |
| Verify | BM25 + dense retrieval → DeBERTa NLI on every summary sentence | — | attribution precision, unsupported-claim rate |

- **Datasets:** train on public labelled sets (FinEntity, SEntFiN, Financial PhraseBank,
  FiQA, EDT, ECTSum). Test on a human-labelled Indian slice and publish the Indian corpus
  to IEEE DataPort, with human (gold) and machine (silver) labels kept in separate files.
- **Research questions:** (1) per-entity sentiment in multi-company text; (2) an event
  schema for Indian regulatory events; (3) summary claims traceable to source sentences;
  (4) how well Western-trained models transfer to Indian disclosure language.
- **SDGs:** 16 (transparent institutions: penalties and misconduct made visible) and
  8 (cheaper financial intelligence for smaller investors and lenders).
- **Related products:** RavenPack/Bigdata.com, Bloomberg Terminal/BloombergGPT,
  AlphaSense, SESAMm, Accern, and FinBERT (open baseline). None combine entity sentiment,
  structured events and source-attributed summaries over Indian regulatory text.

## 2. Team and roles

| Member | Roll no. | Role |
|---|---|---|
| Sania S | CB.SC.U4CSE24046 | Data & pipeline: corpus from BSE/NSE/SEBI/RBI/NCLT, preprocessing, pruning, integration |
| Hasini K | CB.SC.U4CSE24123 | Events & LLM: event schema, LLM extraction and summarization, cite-and-verify |
| Shruhath Reddy | CB.SC.U4CSE24124 | Model & sentiment: FinBERT fine-tuning, classical baselines, evaluation |

All three write the annotation guideline, label the gold slice in Label Studio, and
compute inter-annotator agreement (κ).

## 3. Submission history

| Stage | Artifact | What it established |
|---|---|---|
| Review 1 | `Team_06_R1.pptx`, `Context/NLP_finpulse_doc.pdf` | Product, problem, motivation, research questions, related products, SDG mapping, dataset plan, novelty |
| CS-3 | `CS-3/team_06.pdf`, `Team_06_Title_Abstract_Keywords.tex` | Title, 170-word abstract, keywords, contribution table |
| Literature review | `Team_06_Research_paper.docx` | FinEntity, SEntFiN, Trade the Event (EDT), ECTSum: the gap each leaves, and the build order |
| Review 2 | `Team_06_R2.pptx` + `remade/*dual_llm*_v2.pptx` (18 slides, most detailed) | Sub-objectives, 16-type event taxonomy, evaluation plan, dual-LLM design (Qwen + Llama), workflow, readiness |

The R2 deck said honestly that only a UI and an output contract existed, and that the
first milestone is the entity-sentiment baseline.

## 4. State on 2026-10-04

| Piece | Status |
|---|---|
| GitHub `Shruhath/Fin-Pulse` | Empty. Hasini2108 and SaniaShanmugan added as collaborators with push access on 2026-10-04 |
| Old UI prototype | Next.js 16 + shadcn, mock data only, never pushed. **Abandoned**; the UI is rebuilt from scratch (PLAN §13) |
| Backend, database, scrapers, models, annotations | Not started |
| Hardware | RTX 5060 Laptop GPU (8 GB), 32 cores, 30 GB RAM; docker, bun and uv installed |

## 5. Inconsistencies found (and how the plan resolves them)

| # | Inconsistency | Resolution |
|---|---|---|
| 1 | The old UI had 7 generic event types; the decks promise EDT 11 + 5 India types | The backend uses the 16-type taxonomy, and the new UI is built on it |
| 2 | The stack was described three ways: team CSV (React + FastAPI + PostgreSQL), tech-stack notes (Streamlit + SQLite), prototype (Next.js) | FastAPI + PostgreSQL/pgvector + Docker Compose, with a new React + d3 + GSAP UI |
| 3 | Two 7–8B LLMs don't fit together in 8 GB of VRAM | They take turns on the GPU via Ollama; details in PLAN §3.2 |
| 4 | No scraping code existed for the Indian sources | Written from scratch on standard, publicly documented scraping practice (PLAN §6.1) |
| 5 | Seven R2 deck variants exist in `remade/` | The 18-slide dual-LLM v2 deck is treated as the commitment |
| 6 | R1 claimed "MCA company filings", but MCA documents are paywalled | R2 already dropped MCA. Only BSE, NSE, SEBI, RBI and NCLT are used |
| 7 | The R1 doc and deck disagreed on whether the dataset is scraped or FPB/FiQA | Both, with different jobs: public sets train and benchmark, the scraped Indian corpus is evaluated and published |

## 6. Honest risks

1. **Scraping** is the biggest schedule risk (NSE blocks bots, NCLT PDFs are scanned,
   SEBI orders are long), more than the modelling.
2. **Gold labels need human time.** Without the annotated slice there are no Indian-side
   results, so this has to start by Day 4.
3. **Scope:** three stages × baselines × two data regimes is a lot for 10 days. The core
   that cannot slip is Stage 1 (entity sentiment with its baseline) on real data, shown
   in a working UI.
4. **Honesty:** no fixture or invented metric appears anywhere; every number comes from
   the evaluation harness.
