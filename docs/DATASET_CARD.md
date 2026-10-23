# FinPulse corpus v1: dataset card

Entity-level sentiment, event and summary annotations over Indian regulatory disclosures. This card
describes the package that `finpulse export` builds (`finpulse-corpus-v1/`). Counts are not repeated
here: they are in the package's `MANIFEST.json`, which is generated from the database at export time.

## 1. What it is

A corpus of SEBI enforcement orders, NCLT admission orders (collected through the Insolvency and
Bankruptcy Board of India's mirror) and RBI press releases, with:

- company mentions as character offsets, linked to a gazetteer of listed companies and banks;
- entity-level sentiment (positive, negative, neutral) per mention;
- typed events from a 16-type taxonomy (EDT's 11 corporate types plus SEBI Penalty, RBI Action, NCLT
  Admission, Pledge Invocation, Auditor Resignation), each with a trigger span and typed arguments;
- short summaries made of claims that each carry the sentence they were checked against.

Human (gold) and machine (silver) labels are separate files, never merged.

## Synthetic release

`finpulse synthetic` builds **FinPulse Synthetic Filings v1**, a separate fictional benchmark of 15 filings
with exact gold labels for entity sentiment, events, and claims. It is published at
https://doi.org/10.21227/hhey-hv91. It does not contain the collected corpus described in this card.

## 2. Sources and terms

| Source | What is taken | Terms as understood | In the package |
|---|---|---|---|
| SEBI orders (sebi.gov.in/enforcement/orders) | adjudication, whole-time member and settlement orders | reproduction is allowed after taking permission by mail; robots.txt blocks only scripts and styles | metadata, hashes, URLs, offsets and labels. **No text** unless the manifest says `include_text: true` |
| NCLT orders via IBBI (ibbi.gov.in) | "Admission - Final order" PDFs | IBBI's copyright policy lets its content be reproduced free of charge in any format with accuracy and attribution; orders are not certified copies | same as above |
| RBI press releases | items from RBI's own RSS feed, one request per run | the feed is the publisher's machine-readable offering; the site's robots.txt is behind a bot wall and could not be read, so only the feed is fetched | same as above |
| NSE security master (public listing file) | symbol, ISIN, company name | public reference data | `entities.parquet`, `entity_gazetteer.csv` |

Not included on purpose: SEntFiN aliases (the dataset asks to be cited, not re-hosted), any
Financial PhraseBank or ECTSum text (non-commercial or copyleft licences), news article text.

## 3. Collection and processing

1. Collectors fetch at most one request per second with an identifying User-Agent, stop on a block
   (HTTP 403, 418 or 429), and keep a resumable index. Each file is keyed by its SHA-256.
2. PDFs are read from their text layer. A page with fewer than 20 words is treated as a scan and read
   with Tesseract 5 (English, 200 dpi); `ocr_used` records it per document.
3. Text is repaired (mojibake, NFKC), running headers, footers and page numbers are removed, wrapped
   lines are joined, and sentences are split with a rule-based splitter that knows Indian legal
   abbreviations. All spans are offsets into the resulting `clean_text`.
4. Near-duplicates are clustered with MinHash (Jaccard 0.85); `near_duplicate_of` names the earlier copy.

## 4. Annotations

**Silver (machine).** Mentions come from gazetteer matching and from the parties named in order titles
(`ner_model` says which). Sentiment comes from the model versions listed in `sentiment_silver.jsonl`.
Events come from a rule baseline (`rules`) and a local LLM (`llm`); a rule event carries no confidence
because a rule is not a probability. Summary claims are checked by retrieval plus NLI and marked
`entailed`, `contradicted` or `unverified`; contradicted claims are kept.

**Gold (human).** About 120 passages of up to five sentences, frozen with their SHA-256 and OCR
provenance, are labelled in Label Studio by three annotators; 30 are shared for agreement (Cohen's or
Fleiss' kappa, with gates in `server/src/finpulse/eval/agreement.py`) and a calibration passage is scored
only after adjudication. **Status: the gold files are empty until that annotation is done; any number
reported against gold appears in `eval_results.jsonl` only after it has been.**

## 5. Splits

`splits/{train,dev,test}.txt` list document ids, assigned 80/10/10 by the SHA-256 of the document, so a
document is in exactly one split on every machine.

## 6. Limitations

- **Domain gap.** Public sentiment datasets are news headlines. A model trained on them labels most
  regulatory prose neutral; silver sentiment on orders should be read with that in mind.
- **Event recall is unmeasured** until gold exists. The rule baseline finds an operative sentence in
  most NCLT admission orders and about half of the adjudication orders; some of the rest correctly
  contain no penalty.
- **Title heuristics.** The party an order concerns is read from its title. Titles that name several
  parties or none can yield a wrong or missing subject.
- **OCR.** About one in seven documents is a scan; recognised text has errors that propagate to spans.
- **Coverage.** Old SEBI orders exist only as web pages; RBI items accumulate from the feed's latest
  entries onward, so early history is thin.

## 7. Privacy and ethics

Orders name individuals and can contain PAN numbers and addresses. By default no text is published.
When text is included, PANs are replaced by `X` of equal length (offsets stay valid). Entities of kind
`person` are not exported and their mentions are left out. The team has not yet sought an ethics review;
that, and written permission from SEBI before any republication of order text, are open items.

Three fields still hold words taken from the orders even when no text is included: the document title,
the arguments of an event and the text of a summary claim. They are de-identified before they are
written (`server/src/finpulse/export/privacy.py`): e-mail addresses, phone numbers, PANs and account
numbers are replaced by `[email]`, `[phone]`, `XXXXXXXXXX` and `[account]`; the name of an individual
(after an honorific, before "HUF" or "Investment Adviser", a `person` entity, or a name found by a
reviewer) by `[individual]`; and the party of a title that names no company by `[party withheld]`.
Company, bank and firm names stay, including a firm that carries a partner's surname ("X and Co.").
The counts of what was changed are in `MANIFEST.json` (`titles_redacted`, `event_arguments_redacted`,
`claims_redacted`). This is best effort and is not a guarantee: a name that matches none of these rules
can remain, so read the package before publishing it.

## 8. Licence, citation, contact

Annotations, offsets, labels and derived metadata: CC BY 4.0. The source documents belong to their
publishers. Cite as: *FinPulse corpus v1: entity-level sentiment, events and grounded summaries for Indian
regulatory disclosures* (Team 6, 23CSE471 NLP, Amrita School of Computing, 2026), with the DOI IEEE DataPort
assigns on publication. Issues and questions: github.com/Shruhath/Fin-Pulse.
