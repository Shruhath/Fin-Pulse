# FinPulse: dataset and source research

*Researched 15–16 Oct 2026 from live web sources. Every claim carries a source URL in the working notes; anything the research could not confirm is marked **UNVERIFIED** here, with what was tried. This is desk research, not legal advice.*

---

## 1. Bottom line

| Question | Answer |
|---|---|
| Do public benchmark datasets exist for our tasks? | **Yes for entity sentiment, events and summaries, but none are Indian except SEntFiN** (headlines only). Licences vary widely (§3). |
| Is SEntFiN actually obtainable? | **Yes.** MIT-licensed CSV on GitHub (`pyRis/SEntFiN`), no request form. Earlier doubt was unfounded. |
| Is there an Indian gold set we could just use? | **No.** No public Indian financial NER set, no labelled NSE/BSE announcement corpus, no NCLT/IBBI NLP corpus, no Indian event-labelled corpus was found. Our annotated set fills a real gap. |
| Does IEEE DataPort already hold something like ours? | **No.** Nothing on SEBI orders, NCLT, MCA, financial events or entity-level financial sentiment. Closest: an unlabelled BSE earnings-call transcripts set (BITS Pilani, 2025). |
| Is MCA a usable source for filings? | **No.** Use MCA **company master data** (via data.gov.in) for entity resolution only. |
| Are court / tribunal documents worth including? | **Yes, two sources:** SEBI orders and NCLT orders (through IBBI's mirror). Skip the rest. |
| Can we scrape every planned source? | **No.** NSE, ET, Business Standard and Moneycontrol terms restrict collection itself, not only redistribution (§8). |
| What can we publish? | Annotations (labels, offsets, hashes, URLs) always; full text only where the source's own terms allow it. |

---

## 2. What changed from the earlier plan

| Earlier assumption | Verified finding |
|---|---|
| "MCA filings, about ₹100 per document" | Fee is reported as **₹100 per company** (not per document), login required. MCA's own pages could not be read (every request returned 403), so this rests on secondary guides and is partly UNVERIFIED. |
| NSE as a stretch scraping target | NSE's terms ban "any systematic or automated data collection activities (including scraping…)". It has an **academic data-sharing route** instead. |
| News via RSS, publish offsets only | Fixes *publication*, not *collection*: ET, Business Standard and Moneycontrol terms bar building datasets / ML use. Moneycontrol's RSS is also dead. |
| NCLT from nclt.gov.in | Search needs a captcha. **IBBI mirrors about 32,000 NCLT orders with no captcha** and labels (Admission, Liquidation, …). |
| SEntFiN availability uncertain | Available on GitHub under MIT. |
| FiQA: use any HF mirror | The most-found HF repos (`mteb/fiqa`, `BeIR/fiqa`) are the **retrieval task, not aspect sentiment**. Official Drive links are dead. |
| kdave/Indian_Financial_News as silver data | Labels came from a spreadsheet add-on calling GPT; classes are perfectly balanced and the file is sorted by label. **Weak supervision only, never evaluation.** |

---

## 3. Public benchmark datasets (verified)

| Dataset | Source / access | Size, labels | Licence (as found) | Caveats |
|---|---|---|---|---|
| **FinEntity** | HF `yixuantt/FinEntity`, GitHub `yixuantt/FinEntity`; direct | 979 paragraphs, 2,131 entity spans (pos 503 / neg 498 / neu 1,130); one split | ODC-BY | Reuters text; relicensing rights unaddressed. No official test split. Encoding artefacts, some doubtful labels. |
| **SEntFiN 1.0** | GitHub `pyRis/SEntFiN` (`SEntFiN.csv`, `entity_list_comprehensive.csv`); direct | 10,753 headlines, 14,404 entity labels (pos 5,074 / neg 3,814 / neu 5,516); Economic Times 2011–15 | MIT (© 2021 Sinha, Kedas, Kumar, Malo) | Headlines only, no splits. `Decisions` column is a single-quoted dict string, not JSON. Paper says larger news-flow data is available only on request. **Cite the repo; do not re-host the CSV.** |
| **Financial PhraseBank** | HF `takala/financial_phrasebank` (raw zip) | 2,264 / 3,453 / 4,217 / 4,846 sentences by agreement level | CC BY-NC-SA 3.0 | Non-commercial and share-alike. HF loader script broken under current `datasets`. |
| **FiQA 2018 Task 1** | `sites.google.com/view/fiqa` (links dead); mirrors `TheFinAI/en-fiqa-absa` (gated), `pauri32/fiqa-2018` | 1,173–1,213 rows depending on mirror; score in [−1, 1] | None stated for Task 1 | Row counts differ across mirrors. Mirror licence tags are uploader-assigned. |
| **EDT (Trade the Event)** | GitHub `Zhihan1996/TradeTheEvent` + public Drive | 9,721 articles (2,266 with events); 303,893 trading-benchmark articles; 11 event types | None | US press releases 2020–21. Last push Sep 2021; link-rot risk. |
| **ECTSum** | GitHub `rajdeep345/ECTSum` | 2,425 pairs, 70/10/20 split | GPL-3.0 (repo) | Summaries derive from Reuters articles. Unclear whether GPL covers the data. |
| **FNS (2020–23)** | `wp.lancs.ac.uk/cfie/fns20xx`; registration or email | FNS 2021: 3,000 / 363 / 500 UK annual reports | None stated | FNS 2021 public Drive file 404s; original PDFs withheld for copyright. |
| **kdave/Indian_Financial_News** | HF; direct | 26,961 rows: URL, Content, Summary, Sentiment | None (null) | See §2. No date column. |
| **Twitter Financial News Sentiment** | HF `zeroshot/...` | 11,932 tweets, no test split | MIT tag | Annotation undocumented. `LABEL_0` = Bearish, `LABEL_2` = Neutral. |

**Licence compatibility.** Financial PhraseBank (NC-SA), ECTSum (GPL-3.0) and MiMIC (NC-SA) cannot be folded into a differently licensed release. Use them for training and benchmarking, cite them, and never bundle them into the DataPort or Zenodo upload.

---

## 4. India-specific and gap-filling datasets found

| Dataset | Where | Size / licence | Use for FinPulse |
|---|---|---|---|
| **IndiaFinBench** | HF `Rajveer-code/IndiaFinBench` | 406 QA pairs over 192 SEBI/RBI documents; CC BY 4.0 (data), MIT (code) | **High.** 62 contradiction-detection items test the claim verifier on Indian regulatory text. |
| **SEBI Circulars Dataset** | HF `opnsrcntrbtrian/sebi-circulars` (also on AIKosh) | 728 circulars, 78,585 chunks, supersession pairs; annotations CC-BY-4.0 | **High.** Retrieval and claim-to-evidence testing on SEBI text. |
| **TickerTruth NSE security master** | HF `tickertruthorg/nse-india-security-master` | 2,389 symbols with ISIN; CC BY 4.0 | **High.** Seed list for the alias matcher. No alias field; pair with SEntFiN's entity list. |
| **Securities law enforcement in India** | `data.mendeley.com/datasets/ppdk9pzfdp/2` | Metadata for about 8,032 SEBI orders (2011–20), 818 hand-coded; CC BY 4.0 | **Medium–High.** Seeds a SEBI-enforcement event type. Contents of the coded archive UNVERIFIED. |
| **FinDVer** | GitHub `yilunzhao/FinDVer` | 4,000 claims over financial documents; MIT (repo) | **High.** Best open claim-versus-evidence test. |
| **SENTiVENT** | OSF `enu2k` | 288 documents, 6,203 events; no licence set | **Medium–High.** Argument-level event schema model. |
| **MiMIC / InFiNITE** | HF `sohomghosh/MiMIC_Multi-Modal_Indian_Earnings_Calls_Dataset` | 1,042 instances, 133 companies; CC BY-NC-SA 4.0 | **Medium.** Only open Indian earnings-call set, but labels are price direction. |
| **pranali96/indian_financial_news_42k** | HF | 42,214 headlines, 2,979 with a 95-event taxonomy; Apache-2.0 per card | **Medium–Low.** Only Indian event-tagged headlines, but model-labelled. |
| **IndicFinNLP** | HF `sohomghosh/IndicFinNLP_…` | Hindi/Bengali/Telugu; CC BY-NC-SA 4.0 | **Medium–Low.** Numeral task relates to the crore/lakh normaliser. |
| **FinNLI** | arXiv 2504.16188 | 21,304 pairs | **Medium.** No public download; email authors. |
| **GLEIF LEI** | gleif.org | CC0 | **High for entity resolution.** Indian coverage UNVERIFIED. |

**Name traps and mis-citations to avoid:** HF "NIFTY" is a US news-and-stock-movement set, not the Indian index. arXiv 2512.20082 mis-describes SEntFiN (wrong name, count and columns).

---

## 5. IEEE DataPort

### 5.1 Existing datasets to cite or differentiate from

| Dataset (DOI 10.21227/…) | Relevance |
|---|---|
| Preprocessed Quarterly Earnings Call Transcripts: Indian BSE-Listed Companies 2015–2025 (`57hq-gm60`) | **Highest overlap.** BSE disclosure text, unlabelled. |
| Financial Annual Reports Insights (`hpt6-8r75`) | Nifty-50 directors' reports with summaries; document-level sentiment only. |
| MC-GAN Master Dataset (`tkvx-aw90`), Stock Data with semantic context (`nv64-jg63`) | Numeric sentiment scores from BSE announcements / news. |
| Nifty-50 multimodal data sources (`ycjd-7487`), NSE and BSE data set 2023–25 (`91g5-d880`) | Prices plus news, no labels. |
| Indian Legal Documents With Summaries (`3qjh-9v79`) | Split matches IN-Abs, so it looks like a **re-host** (UNVERIFIED). Cite the original. |
| Business Insider + Financial PhraseBank (`sn6s-ye12`) | Re-hosts FPB. Cite Malo et al. |
| COPOM-Inflation (`zd8v-z019`) | Closest method analogue (central-bank minutes); best-structured page seen. |
| Stock Market Tweets Data (Open Access, `g8vy-5w61`) | Most-viewed finance sentiment set. |

No page found for SEBI orders, NCLT/IBC, MCA filings, financial event extraction or entity-level financial sentiment.

### 5.2 Publishing rules (IEEE's own pages)

- **Account and cost:** a free IEEE account is enough. **Standard** upload is free, but file downloads need a paid subscription ($40/month; free for IEEE Society members; student eligibility UNVERIFIED). **Open Access** costs $1,950, with no discounts found.
- **Limits and formats:** up to 2 TB per dataset; zip, csv, json, txt, sql, xml, tsv; documentation as pdf, txt, docx, doc or md.
- **Required fields:** authors, title, category, abstract, instructions, files. No abstract length limit.
- **Licence:** no picker. Terms §2(g) release uploads under CC-BY, and §3(e) makes the uploader **warrant they hold the rights**. Nothing that cannot be licensed CC-BY may be uploaded.
- **Review:** "IEEE does not review Content prior to its inclusion" (Terms §3c). Peer pages went live within roughly 15–40 minutes.
- **DOI:** generated on save; the page slug is **fixed from the title at first save**, so choose the title carefully.
- **Updates:** entries can be updated and the DOI stays; there is no formal versioning (UNVERIFIED), so put the version in the filename.
- **What graders see:** when logged out, pages show the abstract, instructions and DOI but **lock the files**. A Zenodo mirror is the only free way to give open download.

### 5.3 Recommended page

- **Title:** "FinPulse-India: Entity-Level Sentiment, Corporate Events and Evidence-Linked Summaries for Indian Financial and Regulatory Disclosures".
- **Abstract:** 150–190 words: sources, date range, counts, the three annotation layers, how much is human gold, intended use, "not investment advice".
- **Files:** `FinPulse_v1.0.zip` plus `README.md`, `DATA_DICTIONARY.md`, `LICENSE_AND_SOURCES.md` as separate files so they show on the public page; loader and evaluation scripts as optional Scripts.
- **Licence line:** "CC BY 4.0 for our annotations; source texts keep their publishers' terms."
- **Related:** link the GitHub repo, the Zenodo DOI, the paper, and the BSE-transcripts and Annual Reports Insights datasets.

---

## 6. MCA (Ministry of Corporate Affairs)

**Verdict: not a source for documents. Use only the company master data.**

Caveat: every request to mca.gov.in and data.gov.in returned 403, so no page was read directly; facts below come from search summaries and secondary guides.

- **Fee:** ₹100 per company (LLP: ₹50 or ₹100, sources conflict), login required, access time-limited. Whether one fee covers every category and year is UNVERIFIED.
- **Master data (free, captcha):** CIN, name, class, capital, address, listed status, status. Login requirement conflicts across sources.
- **Open data:** data.gov.in "Company Master Data" published by MCA, about 3.6 million rows, GODL-India licence per an AIKosh mirror (one mirror says CC0; check the live licence field). Currency UNVERIFIED (mirror shows coverage to Apr 2025). No directors, charges, ISIN or ticker.
- **Researcher access:** API Setu needs organisation PAN/GST/CoI; MCA's researcher data scheme costs ₹5,000–1,00,000 and targets registered institutions. Neither suits a course project.
- **XBRL:** reachable only through the paid per-company route. Exchange XBRL (BSE/NSE) is free.
- **Content for NLP:** mostly structured e-forms; narrative text only in attachments (e.g. AOC-4 board and auditor reports). Listed companies' annual reports are free on the exchanges.
- **Legal:** MCA claims copyright and requires written consent to reproduce. Aggregators (Zauba Corp, Tofler, Falcon eBiz) ban scraping and derivative use. Do not publish raw MCA text.
- **Wording to use:** "MCA company master data (via data.gov.in, GODL-India), used for entity resolution only." **Avoid:** "MCA filings", "scraped from MCA", "AOC-4/MGT-7 corpus".
- **Check in a normal browser:** MCA fee page, robots.txt and website policy, Master Data login requirement, data.gov.in licence and last-updated date.

---

## 7. Courts and tribunals

**Verdict: include SEBI orders and NCLT orders via IBBI. Treat Supreme Court / High Court judgments as an optional demo extra. Skip the rest.**

| Source | What it offers | Access | Reuse terms | Use |
|---|---|---|---|---|
| **IBBI (NCLT mirror)** | **31,962 NCLT orders** (about Jan 2017 to Oct 2026), each labelled Admission / Liquidation / Appointment of Liquidator / Dissolution. 14,943 public announcements. | No captcha; no robots.txt (404); PDFs at `/uploads/order/<hash>.pdf` | "may be reproduced free of charge in any format or media without requiring specific permission", with accuracy and attribution; orders are "not certified copies" | **High.** Best NCLT route. |
| **NCLT** (nclt.gov.in) | Orders by date | Captcha search, no API; robots.txt 403 | Similar free-reproduction wording (paraphrase only) | Low (use IBBI instead). |
| **NCLAT** | Appeals; about 4.7k legacy judgments | No captcha on legacy list | Same wording | Low–Med. PDFs not tested for text vs scan. |
| **SEBI orders** | 12,013 adjudication, 6,432 WTM/CM, 2,004 settlement, 1,118 court orders; newest Oct 2026 | HTML listings, no captcha; robots.txt blocks only js/css. Sampled orders were text PDFs. | Free reproduction "after taking proper permission by sending a mail" | **High.** Individuals' PANs appear; mask them. |
| **SAT** | Securities Appellate Tribunal orders | Four captcha forms, no listing; SEBI mirror ends Jul 2015 | Personal, non-commercial use only | Low. URLs only. |
| **Supreme Court (AWS Open Data)** | About 35K reported judgments, 1950–2026, CC-BY-4.0; High Courts: 25 courts, about 17.8M judgments | Bulk S3 | CC-BY-4.0 (headnote copyright UNVERIFIED) | Low–Med. General litigation, not events. |
| **eCourts / Indian Kanoon** | Judgments | eCourts: captchas, no API. Indian Kanoon: blocks about 9,600 document IDs; prepaid API | Redistribution of derived datasets unstated | Skip (lookup only). |

**Labelled legal datasets:** none matches our event schema and no NCLT/IBC corpus exists on Hugging Face. Closest: the Mendeley SEBI enforcement dataset (§4). IN-Abs (Zenodo, CC-BY 4.0, about 7,130 Supreme Court judgments with headnote summaries) suits summarisation sanity checks only. ILDC's licence is inconsistent (CC-BY-NC vs GPL-3.0).

**Realistic 10-day volume:** about 200 SEBI orders (60–80 annotated as gold for the SEBI penalty event) and about 60 NCLT "Admission – Final Order" PDFs (about 40 annotated for the NCLT admission event). Pair each NCLT admission with the company's own BSE/NSE disclosure: the filing is the news-style input, the order is the evidence document.

**OCR reality:** of 7 recent IBBI orders sampled, 5 were text, 1 hybrid, 1 image-only. A listing size over about 2 MB suggests scan or hybrid. Check per-page word counts with `pdftotext` and OCR only pages under about 20 words. Tesseract 5.5.3 gave clean prose on one 300 dpi page (n=1). The only published numbers are a receipt benchmark (CER 0.191 Surya, 0.204 PaddleOCR, 0.335 Tesseract), not legal text. Surya's weights are free only for research and startups under $5M.

**Copyright and privacy:** Copyright Act s.52(1)(q)(iv) permits reproducing a judgment or order of a court, tribunal or other judicial authority unless prohibited. No prohibition notice was found on NCLT, NCLAT, IBBI, SEBI or SAT (absence is not proof), and whether SEBI counts as a "judicial authority" is UNVERIFIED. Right-to-be-forgotten rulings conflict (Delhi and Kerala High Courts have ordered masking; the Supreme Court stayed the Madras order in 2024). Exclude victim, juvenile and matrimonial matters, mask personal identifiers, and ask the faculty guide.

---

## 8. Source terms and access (collection, not just publication)

| Source | robots.txt | Terms on reuse / automation | Best access route | Publish full text? |
|---|---|---|---|---|
| **BSE** | UNVERIFIED (403) | Redistribution "strictly prohibited"; written consent needed | JSON endpoint `api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w` (params `pageno`, dates, `strCat`, scrip code); bodies are PDF attachments. Endpoint detail from an unofficial client library, so secondary. | **Risky.** IDs, URLs, labels only |
| **NSE** | Allows all but `/market-data-test` | **Bans** "systematic or automated data collection (including scraping)", copying, republishing. **Academic data-sharing route** via its Economic Policy Research Department (confidentiality declaration, so not republishable). | `/api/corporate-announcements` exists but is against the terms; ask NSE | **Risky.** IDs, URLs, labels only |
| **SEBI** | Allows all but `/js`, `/css` | Free reuse after permission email, with attribution | Server-rendered listings, AJAX POST to `/sebiweb/ajax/home/getnewslistinfo.jsp`, PDFs under `/sebi_data/attachdocs/`; `sebirss.xml` has only the latest 30 | Yes **after permission**, else URLs and labels |
| **RBI** | UNVERIFIED (HTTP 418) | No reuse licence; "© All Rights Reserved"; bars caching and framing | `pressreleases_rss.xml` (10 items, full HTML); archive pages are ASP.NET WebForms | **Risky.** Ask RBI |
| **IBBI** | None (404) | Free reproduction with attribution | `/uploads/order/*.pdf` | **Yes**, with attribution and pseudonymised persons |
| **ET** | Articles allowed | Terms (21 Sep 2026) bar scraping or indexing to build datasets or for machine-learning use without written licence | RSS (50 items, snippets) | **No.** URLs and labels only |
| **Business Standard** | UNVERIFIED (403) | Bans scraping, ML and RAG; says robots.txt is not consent | RSS (35 items) | **No** |
| **Moneycontrol** | UNVERIFIED (403) | Bans machine-readable / database / LLM use | RSS dead (410; stale feeds) | **No** |
| **Mint** | Allows `/` with listed disallows | UNVERIFIED | UNVERIFIED | Assume **No** |
| **GDELT** | Main host disallows `/data/`; API/data hosts none | "unlimited and unrestricted use… for any academic, commercial, or governmental use" with citation | DOC 2.0 API (up to 250 records, last 3 months) or 15-minute bulk files | **Yes, metadata only.** Licence does not cover publishers' text |

**DPDP Act 2023.** A "penalised person" who is an individual is personal data (s.2(t)); companies are not. Whether publication under SEBI/RBI/NCLT/IBBI counts as a legal obligation to publish (s.3(c)(ii)(B)) is UNVERIFIED. The research exemption (s.17(2)(b)) applies only if data is not used for decisions about a specific person. Secondary sources put the operative sections into force around May 2027 (UNVERIFIED). A public CC-BY upload outlives that date, so pseudonymise natural persons now and drop PAN, DIN and addresses.

---

## 9. Recommended strategy

**Collect**
1. **Backbone:** IBBI (NCLT orders) and SEBI orders, polite rate limit, identifying user agent.
2. **BSE:** the site's own JSON endpoint at minimal volume for the research sample, only while written permission is pending. Treat as the highest-risk collection and keep raw text private.
3. **NSE:** do not scrape. Request the academic data-sharing route.
4. **RBI:** RSS plus detail pages at minimal volume; ask for permission.
5. **News:** GDELT metadata as the backbone. Use RSS titles from ET and Business Standard as private inputs only; do not build a dataset from article text.
6. **Entity resolution:** TickerTruth NSE master + SEntFiN entity list + data.gov.in MCA master data (+ GLEIF if Indian coverage checks out).

**Train and benchmark:** FinEntity + SEntFiN (sentiment), Financial PhraseBank (warm-up), EDT + SENTiVENT (event schema), ECTSum (summaries), FinDVer + IndiaFinBench + SEBI Circulars (claim verification and retrieval). Respect §3 licence compatibility.

**Publish (IEEE DataPort + Zenodo mirror)**
1. Annotations only by default: source ID or URL, date, span offsets, hash of the span, labels, retrieval metadata, plus a re-fetch script.
2. Add full text only where the source's own terms allow: IBBI orders now; SEBI after permission.
3. Mask PAN, phone, email, address; pseudonymise individuals; no person-level decision tasks; add a takedown contact.
4. Licence line: CC BY 4.0 for our annotations; source texts keep their publishers' terms.

## 10. Actions to take now

| # | Action | Who |
|---|---|---|
| 1 | Email NSE (academic data-sharing, Economic Policy Research Department) | Sania |
| 2 | Email SEBI for reproduction permission for orders | Sania |
| 3 | Ask BSE and RBI for written permission to use disclosures for research | Sania |
| 4 | Open in a normal browser and record: MCA fee page and robots.txt, BSE/RBI/NCLT/Moneycontrol/Business Standard robots.txt, data.gov.in licence and last-updated date | Sania |
| 5 | Ask the faculty guide / college ethics cell about publishing named individuals from public orders | Hasini |
| 6 | Download and verify SEntFiN, FinEntity, TickerTruth, IndiaFinBench, SEBI Circulars; check the Mendeley archive's coded fields | Shruhath |
| 7 | Change project wording from "MCA filings" to "MCA company master data" in decks and the paper | all |

## 11. Unverified, and what was tried

- **robots.txt** for BSE, RBI, NCLT, Moneycontrol and Business Standard returned 403/418; read in a normal browser.
- **mca.gov.in and data.gov.in** returned 403 to every request: fees, Master Data login, licence and currency all rest on secondary sources.
- **BSE** PDF URL pattern, date format and archive depth; **NSE** archive depth.
- **NCLT** exact policy wording; **NCLAT** policy page not re-read raw; **SAT** site unreachable.
- **Copyright Act s.52(1)(q)** applicability to SEBI orders.
- **DPDP** commencement dates and s.3(c)(ii)(B) applicability.
- **Mint** terms and RSS.
- **IEEE DataPort:** student subscription eligibility, formal versioning, public visibility of draft pages.
- **Mendeley** SEBI archive contents; **GLEIF** Indian coverage; **Indian Legal Documents With Summaries** being a re-host.

---

## 12. Getting files from IEEE DataPort (observed 19 Oct 2026)

Order, cheapest first:

1. **Free IEEE accounts.** Stock Market Tweets Data is Open Access (files for any logged-in user). Several public DataPort profiles show "Subscriber Organization: Amrita Vishwa Vidyapeetham - Coimbatore", which suggests an institutional plan (unconfirmed on any official page). If a Standard dataset page then shows download links instead of "LOGIN TO ACCESS DATASET FILES", the college plan works for you.
2. **Zenodo instead of DataPort for the legal set:** IN-Abs, CC BY 4.0, `zenodo.org/record/7151679` (the DataPort copy has the same 7,030/100 split, very likely a re-upload).
3. **Ask the college:** Central Library (is there a DataPort institutional subscription? DataPort is sold separately from IEEE Xplore; who is the admin; how do students link accounts?), the department (can it fund one month, $40?), and the IEEE student branch counselor (current dues; can a Society member test the free subscription?). IEEE publishes no list of subscribing institutions; institutional pricing is "$4,500 to $29,995 per year" on request.
4. **Message the dataset authors** (every page has "Send Author a Private Message"; free account is enough).
5. **One teammate pays $40 for one month**, downloads everything in one sitting, and cancels the same day. Do not buy three accounts: Terms §2(c)(ii) forbid sharing credentials.
6. **Student membership plus a Society is not recommended first.** The free subscription is for "All IEEE Society members"; student eligibility is unconfirmed; IEEE's own dues could not be read.

| Dataset | Access | Size | Mirror |
|---|---|---|---|
| BSE earnings-call transcripts 2015–25 (`57hq-gm60`) | Standard | 249 MB | none (transcripts are public exchange filings) |
| Financial Annual Reports Insights (`hpt6-8r75`) | Standard | about 7 MB | none |
| MC-GAN Master Dataset (`tkvx-aw90`) | Standard | 22 MB | none |
| COPOM-Inflation (`zd8v-z019`) | Standard | 50 MB | none (Portuguese, weak fit) |
| Stock Market Tweets (`g8vy-5w61`) | **Open Access** | 56 MB | none |
| Indian Legal Documents With Summaries (`3qjh-9v79`) | Standard | 93 MB | **Zenodo IN-Abs** |

- **Open Access list:** `ieee-dataport.org/datasets?type=open_access` (about 1,080 datasets, 7 in Financial, none Indian finance).
- **Downloaded files:** the terms don't say whether files may be passed to teammates, and IEEE can suspend accounts for "unauthorized public sharing". Keep raw IEEE files out of the public repo.
- **Download method for subscribers:** web Download tab or `aws s3 cp` with keys from the Account page. No public API found.
- **Author message template (4 lines):** "Subject: Research copy request - '<title>' (DOI <doi>). Hello <Name>, we are undergraduate NLP students at Amrita School of Computing, Coimbatore, building FinPulse, a non-commercial course project on Indian financial text. We would like to use '<title>' for <specific use>; the files are behind a paid subscription. Could you share the files or a mirror link for academic use? We will cite the DOI and credit your team."
- **Unverified:** student eligibility for the free subscription; how Amrita accounts link to an institutional plan; whether a free login really unlocks Open Access files (the page also shows "requires an IEEE DataPort Subscription" template text); IEEE student dues for India.
- **If none works:** rebuild the transcripts and annual-reports sets from public BSE/NSE filings, and use Zenodo for the legal set.
