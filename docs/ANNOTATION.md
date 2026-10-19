# FinPulse: gold dataset plan

*Derived from how comparable datasets were built (papers and dataset cards read Oct 2026). Per-item times are estimates (about ±30%): time the pilot and re-plan on day 4. Numbers marked "simulation" come from the research notes' own simulations, not from a paper.*

## 1. Target

| Item | Number |
|---|---|
| Gold passages | **120**: 30 each from BSE, SEBI, NCLT/IBBI, RBI. A passage is a full announcement or an excerpt capped at about 700 words (state the excerpt rule in the datasheet) |
| Sampling | Stratified by source and by silver cue so each of the 5 India-specific event types has at least 12 instances; plus about 20 no-event passages as hard negatives. Say plainly that prevalence is not representative |
| Expected yield | about 300 entity mentions (at least 50 per sentiment class), about 150 events, 40 summarised documents, about 100 claim-verification items |
| Minimum floor if hours slip | 100 passages (main double-labelled set cut to 60), about 22 h per person |

## 2. Schedule (days from start)

| Days | Work |
|---|---|
| 1–2 | Set up; guideline v0 with 15 ambiguous cases; Label Studio export round-trip test |
| 3 | Pilot on 12 extra passages, triple-annotated, **excluded from gold** |
| 4–6 | Two reliability rounds of 20 passages each, triple-annotated blind; compute agreement, adjudicate, **freeze the guideline** |
| 7–11 | 80 passages, each labelled blind by 2 of the 3; the third person resolves disagreements |
| 9–12 | Layer 3: each person writes about 13 reference summaries **from scratch** with evidence sentence ids, then verifies a colleague's |
| 12–14 | LLM-versus-gold analysis, a 100-item silver audit, QA, datasheet |

About 24 h per person (72 h total): Layer 1 about 33%, Layer 2 about 25%, Layer 3 about 10%, adjudication about 14%, setup/QA/analysis about 17%.

**Cut order if hours slip:** shrink the double-labelled set → drop relations and attributes → Layer 3 down to 30 documents. **Never cut the second reliability round or the guideline freeze.**

## 3. Three layers on the same passages

1. **Entity spans + per-entity sentiment** (positive / negative / neutral / not applicable).
2. **Corporate events:** EDT's 11 types plus SEBI penalty, RBI action, NCLT admission, share-pledge invocation, auditor resignation; trigger span and arguments.
3. **Reference summary** with the evidence sentence ids, and claim-verification items.

## 4. Guideline rules that matter

- Sentiment is from the investor's view toward the **named entity**, using only what the passage says.
- Neutral covers both "no sentiment" and regulators/government bodies (SEntFiN's rule). Add a separate "not applicable" flag instead of merging it into neutral.
- Entities are limited to companies, organisations and asset classes (FinEntity's rule).
- India-specific example: "SEBI penalises X" makes **X negative and SEBI neutral**.
- Give 15 ambiguous cases with rationale plus 100 worked examples. Annotators work independently.

## 5. How big must the gold set be?

Macro-F1 95% interval (simulation, 3 classes, items treated as independent; resampling by document gives wider intervals):

| n items | ± points (balanced) | ± points (skewed) |
|---|---|---|
| 100 | 7.1 | 9.1 |
| 200 | 5.1 | 6.3 |
| 300 | 4.1 | 5.1 |
| 500 | 3.2 | 4.0 |

- Per-class recall (Wilson): ±14 points at 30 items, ±11 at 50.
- At n=300, a paired test can only detect an accuracy gap of about 5.5–7.5 points: **the test set cannot rank two models closer than that.**
- **Recommended minimums:** at least 300 entity mentions (at least 50 per class); at least 150 events, reporting per-type scores only for types with 15 or more instances; 40–50 summarised documents; 150–300 claim items.
- Published precedents for small gold sets: FinEntity test ≈196 examples; SENTiVENT test 30 documents (984 events); IN-Ext 50 documents; ECTSum human evaluation 75 documents; IndiaFinBench 406 items.

## 6. Agreement

| Layer | Metric | Suggested gate (judgement call) |
|---|---|---|
| Sentiment | Fleiss κ or Krippendorff α, plus Gwet AC1 for skewed classes; report the positive–neutral confusion pair | κ ≥ 0.67 |
| Spans | pairwise F1, exact and overlap | exact F1 ≥ 0.80 |
| Events | trigger F1, then type κ on aligned spans, then argument F1 | trigger+type F1 ≥ 0.70 |
| Evidence links | set F1 over source sentence ids | report only |

Krippendorff's convention: α ≥ 0.8 good, 0.67–0.8 tentative. Real financial datasets scored 0.65–0.75. Use at least 50–100 entity mentions per reliability round: κ's 95% spread is [0.53, 0.95] at n=30, [0.58, 0.91] at 50, [0.64, 0.87] at 100 (simulation).

## 7. How published datasets did it

| Dataset | Annotators and items | Agreement |
|---|---|---|
| FinEntity | 12 finance undergraduates, 3 per item, 4,000 sequences; only 979 (~24%) kept after filtering | span Jaccard 0.754 |
| SEntFiN | 3 MBA students labelled all 10,753 headlines over 2 months; a curator pre-marked entity spans | pairwise only (pos–neu 80.4%) |
| Financial PhraseBank | 16 annotators, 5–8 labels per sentence | average pairwise 74.9%, ICC 0.65–0.67 |
| EDT | 2 annotators, 9,721 articles | none reported |
| SENTiVENT | 288 documents, 18 types; 3-annotator study on 30 test documents | type κ 0.877, subtype κ 0.813 |
| FinDVer | 7 finance professionals; second annotator, third on conflict | 90.3% label agreement |
| IndiaFinBench | 1 expert plus a second annotator on 180 items | κ 0.645 on contradiction items |

No annotated SEBI/NCLT/RBI corpus exists, only structured resources (Mendeley SEBI enforcement metadata, AIKosh SEBI circulars).

## 8. Using local LLMs for pre-labelling without contaminating gold

- Anchoring is real: in a 410-annotator study, assistance did not save time and raised full consensus from 8% to 38%; scoring the same LLM against LLM-assisted labels inflated F1 from 0.47 to 0.79. With 7–8B local models, **plan for no time saving**.
- **Protocol:** annotate gold blind and from scratch. Run the LLM separately with its output hidden. Report LLM-versus-gold next to human-versus-human. Any LLM-assisted pool stays separate from the test set. Write reference summaries from scratch.
- No verified numbers exist for Qwen2.5-7B or Llama-3.1-8B on this task; measure them on the pilot.

## 9. Label Studio

- **Layer 1:** composite labels such as `COMPANY_POS / NEG / NEU` are the safest (mirrors FinEntity). The alternative is `Labels` plus `Choices perRegion="true"`; test it on day 1, since no official NER-plus-sentiment template exists.
- **Layer 2:** trigger and argument span labels; `Relation` tags only if passages hold several events.
- **Export JSON**, not CoNLL (flat BIO cannot carry relations or per-region choices).
- Agreement dashboards are an Enterprise feature, so **compute agreement offline** from the export.
- Normalise `\r\n` before labelling and assert `text[start:end] == value.text` on every span. Check UTF-16 versus Python code-point offsets (an inference, not a documented issue).

## 10. Silver labels (kept separate)

- **Events:** BSE announcement categories, or better the LODR Schedule III Part A items, as document-level silver. Pledge invocation was not in the Part A list read (unverified); BSE's own category list could not be opened.
- **Entities:** gazetteer matches (as SEntFiN did). **Structure:** regex fields from SEBI orders (as in the Mendeley dataset).
- Label every record by provenance (gold / human-verified silver / silver) and audit 100 random silver items for precision. Never mix them in one score table.

## 11. Risks

- Students will disagree most on positive versus neutral: get an outside check on 20–30 hard cases.
- The annotators are also the model builders: freeze the split and stay blind to model outputs.
- Terms of use for BSE/SEBI/NCLT text and named individuals: see `DATASETS.md`.
