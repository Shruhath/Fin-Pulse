# FinPulse Synthetic Filings v1

**This dataset is synthetic.** Every company, amount, date and sentence in it is invented. It contains no real
filing, no real company and no real person, and any resemblance to a real company is coincidental. The filings
are written from templates in the register of SEBI adjudication orders, NCLT admission orders, RBI press
releases and company announcements, and the labels are known by construction: the template that writes a
sentence says which company it is about, how it reads for that company, which event it reports and which
claims follow from it.

## Why it exists

The FinPulse project reads real Indian regulatory disclosures. Those orders cannot be redistributed without
the publishers' permission and they name individuals, so the real corpus is not released. This synthetic set
has the same structure, so anyone can run and test entity-level sentiment, event extraction and claim
verification against exact gold labels. A system that does well on it has shown only that it can read this
style of text. It says nothing about how it would do on real filings, and it is not meant for training a model
that will be used on real ones: the variety is limited because the text comes from templates.

## What is here

| File | One row per | Holds |
|---|---|---|
| documents/*.txt, documents/*.tex | filing | the text, and the same text as a LaTeX source file |
| documents.parquet | filing | source kind, type, title, date, SHA-256, word count, the text |
| sentences.parquet | sentence | character offsets into the filing's text, and the sentence |
| entities.parquet | company or bank | the fictional companies and banks |
| mentions.parquet | mention | where a company is named, as offsets |
| sentiment_gold.jsonl | mention | how the sentence reads for that company: positive, negative or neutral |
| events_gold.jsonl | event | type (from a 16-type taxonomy), trigger offsets, typed arguments |
| summaries_gold.jsonl | summary | claims, each with a verdict and the sentence that decides it |
| splits/{train,dev,test}.txt | filing id | 11 train, 2 dev and 2 test filings, fixed by hand because there are only 15 |
| MANIFEST.json | | counts and a SHA-256 for every file |

There are 15 filings: 4 SEBI orders, 4 NCLT orders, 2 RBI press releases and 5 company announcements.
Offsets are half-open [start, end) character positions into the text of the filing, where sentences are
separated by a newline.

## Verdicts

Each summary has claims of three kinds, written to test a claim checker:

- **entailed**: the evidence sentence says it;
- **contradicted**: the evidence sentence says something different;
- **unverified**: no sentence in the filing speaks to it (the evidence list is empty).

## Load it

```python
import json
import pandas as pd

docs = pd.read_parquet("documents.parquet")
mentions = pd.read_parquet("mentions.parquet")
sentiment = pd.read_json("sentiment_gold.jsonl", lines=True)
claims = [c for line in open("summaries_gold.jsonl") for c in json.loads(line)["claims"]]
print(docs.groupby("source_kind").size(), sentiment.label.value_counts())
```

## Reproduce

`finpulse synthetic --out finpulse-synthetic-v1` in the code repository (github.com/Shruhath/Fin-Pulse)
writes these files again, byte for byte.

## Licence

Creative Commons Attribution 4.0 International. See LICENSE.txt.
