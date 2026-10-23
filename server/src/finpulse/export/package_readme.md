# finpulse-corpus-v1

Entity-level sentiment, event and summary annotations over Indian regulatory disclosures: SEBI orders,
NCLT admission orders (collected through the Insolvency and Bankruptcy Board of India) and RBI press
releases. Licence: CC BY 4.0 for the annotations (see LICENSE.txt). The document text is not included.

## What is here

| File | One row per | Holds |
|---|---|---|
| documents.parquet | document | source, type, title, URL, publication date, SHA-256 of the original file, size, OCR flag, near-duplicate link |
| sentences.parquet | sentence | character offsets into the document's clean text, the SHA-256 of the sentence |
| mentions.parquet | company mention | offsets, the linked company, how it was found |
| entities.parquet, entity_gazetteer.csv | company or bank; alias | the list of listed companies and banks that mentions are linked to |
| sentiment_silver.jsonl | mention | model labels and probabilities |
| events_silver.jsonl | event | type, trigger offsets, arguments, amount, date, extractor |
| summaries_silver.jsonl | summary | claims, each with a verdict from a retrieval + NLI check |
| sentiment_gold.jsonl, events_gold.jsonl, summaries_gold.jsonl | human annotation | empty until the human annotation is done |
| eval_results.jsonl | metric | every reported metric, with the commit and data hash that produced it |
| splits/{train,dev,test}.txt | document id | 80/10/10 by the SHA-256 of the document |
| MANIFEST.json | | counts, flags and a SHA-256 for every file |

Offsets are half-open [start, end) character positions into the document's clean text, which is not
included; the SHA-256 of each original file lets you fetch the same document from its URL and check it.

## Columns

documents.parquet: doc_id, source_kind (SEBI, NCLT or RBI), doc_type, title, url, published_at, sha256,
n_words, n_pages, ocr_used, near_duplicate_of, text (empty in this package).

sentences.parquet: doc_id, idx, char_start, char_end, kept_after_prune (false for boilerplate),
sha256, text (empty).

mentions.parquet: doc_id, char_start, char_end, entity (slug), ner_model (gazetteer-rules or
title-subject), link_method, link_score, surface (empty).

entities.parquet: slug, canonical_name, nse_symbol, isin, sector, kind (company or bank).
entity_gazetteer.csv: alias, slug, origin.

sentiment_silver.jsonl: doc_id, char_start, char_end, entity, model, label (positive, negative or
neutral), p_pos, p_neg, p_neu, confidence.

events_silver.jsonl: doc_id, entity, type, trigger [start, end], arguments, amount_inr, event_date,
extractor (rules or llm), schema_valid.

summaries_silver.jsonl: summary_id, scope, doc_id, entity, model, prompt_version, claims. A claim has
text, verification (entailed, contradicted or unverified), nli_entail, nli_contra,
evidence_sentence_id and cited (sentence ids).

## Silver and gold

Silver labels come from models and rules. Gold labels come from human annotators. They are kept in
separate files and never merged. The gold files are empty until the human annotation is done, so no metric in
this package is measured against human labels.

## What was removed

The document text is not included. Titles, event arguments and claim text are de-identified: e-mail
addresses, phone numbers, PANs, account numbers and the names of individuals are replaced by `[email]`,
`[phone]`, `XXXXXXXXXX`, `[account]` and `[individual]`, and the party of an order that names no
company is shown as `[party withheld]`. MANIFEST.json counts what was changed. This is best effort.

## Load it

```python
import json
import pandas as pd

docs = pd.read_parquet("documents.parquet")
mentions = pd.read_parquet("mentions.parquet")
sentiment = pd.read_json("sentiment_silver.jsonl", lines=True)
events = pd.read_json("events_silver.jsonl", lines=True)
print(docs.groupby("source_kind").size())
```

## Known limits

Public sentiment datasets are news headlines, so a model trained on them reads most regulatory text
as neutral. Event recall is unmeasured without gold labels. The party of an order is read from its title.
About one in seven documents is a scan read with OCR. Old SEBI orders exist only as web pages, and RBI
items start from the latest entries of its feed. See docs/DATASET_CARD.md in the code repository
(github.com/Shruhath/Fin-Pulse) for collection, cleaning and privacy.
