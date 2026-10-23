# FinPulse app guide: what is where, and what it does

This guide is for anyone opening the app for the first time. It starts from zero. You do not need to know
how the models work to read it. (How the app works inside is in `docs/BACKEND_FLOW.md`.)

Open the app at **http://localhost:3000** after running `make live`.

---

## 1. What FinPulse is, in three sentences

FinPulse reads Indian regulatory documents (SEBI orders, NCLT orders, RBI press releases). For every company
it finds in them, it works out how the text leans (good news, bad news, or neither), pulls out the important
events (a penalty, an insolvency admission), and writes short summaries. **Every claim in a summary is
checked against the exact sentence in the document that supports it**, so you can see what is backed up and
what is not.

---

## 2. Words you will see

| Word | What it means here |
|---|---|
| **Filing** | One document: a SEBI order, an NCLT order or an RBI press release. |
| **Company** | A company or bank that the system found in the documents. |
| **Mention** | One place in a document where a company is named. |
| **Sentiment** | How the text leans for one company. Shown as a number from **−1** (bad news) to **+1** (good news). Between −0.15 and +0.15 it is called *neutral*. |
| **Change** | How much a company's sentiment moved compared with the period just before. |
| **Confidence** | How sure the model is about a sentiment reading. Shown as four small bars and a percentage. |
| **Event** | Something that happened, pulled out of a document as a short record: "SEBI Penalty", "NCLT Admission", a dividend, and so on. There are 16 kinds. |
| **Claim** | One sentence in a generated summary or an answer. |
| **Source sentence** | The sentence in a filing that a claim is based on. |
| **Supported / Contradicted / Not verified** | The result of checking a claim against its source sentence. **Supported** (green tick): the source says it. **Contradicted** (red cross): the source says something different. **Not verified** (grey question mark): no sentence backs it up. Contradicted claims are never hidden. |
| **Time window** | The 7, 30 or 90 days that some pages look at. The window ends on the date of the newest document, not on today's date. |

**Colour is never the only signal.** A green tick, a red cross and a grey question mark always carry a shape
as well, and sentiment always has an arrow or a dash next to the number.

---

## 3. Finding your way around

**On a laptop:** a blue bar on the left is the menu. It stays in place on every page.

```
 FinPulse
 [ Search            Ctrl K ]

 Home
 Companies
 Filings
 Ask

 Insights
   Events
   Analyze
   Evaluation
   Method

 Dark theme
 263 filings, 453 companies
```

- **Search** (or press **Ctrl K**, or just press **/**): type a company or filing name to jump to it. If you
  type a whole question (three words or more) the first result is "Ask the filings: …".
- The logo at the top goes back to the start page.
- **Dark theme / Light theme** switches the colours.
- The line at the bottom is a quick count of what is loaded.

**On a phone:** the menu is a bar at the bottom: Home, Companies, Filings, Ask, and **More** (which opens
Events, Analyze, Evaluation, Method and the theme switch).

**Yellow banner at the top:** if you ever see "Synthetic preview", every number on screen is invented. That
is the backup mode that needs no database. Real runs never show it.

---

## 4. Page by page

### 4.1 The start page (`/`)

The front door. It is for someone who has never seen FinPulse. It has no menu on the left.

- **Top bar:** the logo, links to the sections below, a light/dark button and **Open the app**.
- **Big headline and the example box:** a made-up SEBI order with one sentence highlighted, and a claim
  about it. Click **Supported / Contradicted / Not verified** under the box and watch the mark next to the
  claim change. It is an example with an invented company ("Illustrative example, not a real order"); it is
  there to show the idea, not real data.
- **From a forty-page order to claims you can check:** the five steps in one line.
- **Three feature rows:** ask a question, sentiment per company, events traced back to the filing. Each has a
  small illustrative picture and a link into the app.
- **Measured, not claimed:** real scores of our sentiment model against a simpler baseline, read from the
  evaluation results every time the page loads. Under it is a short list of what is **not** measured yet.
- **Last band:** "Ask your first question", then **Open the app**.

### 4.2 Home (`/home`)

A quick look at what is new. Think of it as the front page of the app.

- **Time window switch (7 / 30 / 90 days)**, top right. It changes the "moves" and "events" parts below.
- **Ask box:** type a question and press Enter. This takes you to the **Ask** page and asks it there. The
  one or two grey chips under it are ready-made questions built from recent events; click one to ask it.
- **Latest filings:** the newest documents. Filings the system has already read come first. A line that says
  **Waiting for analysis** means the document is stored but has not been through the models yet. Company names
  with a small arrow or dash show who is mentioned and how the document leans for them. Click a row to open
  the filing.
- **Biggest sentiment moves:** companies whose sentiment changed the most in the window (among the busiest
  40 companies). The bar goes left (worse) or right (better); the number has an arrow and a sign.
- **Latest events:** the newest extracted events with their type, company and date. Click one to open the
  filing it came from.

### 4.3 Companies (`/companies`)

All the companies the system tracks. It has the same 7 / 30 / 90 day switch. Two tabs:

**Tab: Companies**
- A table of companies. Type in the box to find one by name, ticker or sector.
- Columns: **Company**, **Sentiment** (a coloured pill with the score), **Size of change** (an arrow and the
  amount it moved), **Mentions** (how many times it was named), **Confidence**. Narrow screens show fewer
  columns. (Sector is hidden when no company has one.)
- Click a column heading to sort. By default the biggest movers are on top.
- Click a row to open that company's page.
- 25 rows at a time; press **Show … more** for the rest.

**Tab: Sentiment map**
- One picture of everything: **each row is a company, each column is a day**.
- Colour is the sentiment that day, from red (−1) through pale grey (0) to green (+1). Very pale squares mean
  "close to neutral". A blue outline on a square means an **event** happened to that company on that day.
- The thin strip at the top is the average for the whole market, with its spread.
- Point at a square to see the numbers; click a row to open the company.

### 4.3b A company's page (`/companies/<name>`)

Opens when you click a company. A **← Companies** link at the top goes back.

- The title is the company name; under it, its ticker, sector and other names it is written as.
- **The strip of four numbers:** *Reads as* (sentiment pill), *Change in the window*, *Mentions*, *Confidence*.
- Three tabs:
  - **Overview:** a line chart of the company's sentiment day by day (the scale is always −1 to +1, so a
    quiet company looks quiet), with small marks for events. Below it, **What the filings say**: a short
    summary of the company where every claim has a tick, cross or question mark. Press **Show source** under
    a claim to read the sentence it was checked against, highlighted in yellow.
  - **Events:** every event extracted for this company, as cards (what happened, the amounts and dates, who
    extracted it, how sure it is, and a link to the filing).
  - **Mentions:** the actual sentences where the company is named, with its name marked in the colour of its
    sentiment, the date, the confidence and a link to the whole filing.

### 4.4 Filings (`/filings`)

The library of documents.

- **Search box:** finds filings by title or by a company named in them.
- **Publisher buttons:** All, SEBI, NCLT, RBI (and others if present), each with a count.
- A list of filings. Each row shows the publisher, the title, the date and the companies mentioned. Click a
  row to read it.
- 25 at a time; **Show … more** for the rest.
- *Good to know:* this list loads the **newest 50** filings, and search and the publisher buttons work on
  those 50.

### 4.4b A filing's page (`/filings/<id>`)

The most important page. It shows a document **with the system's reading marked on top of it**.

**Left side: the text.** Marks you will see:

| Mark | Meaning |
|---|---|
| Green underline and arrow up | A company, and the text is **positive** for it. |
| Red underline and arrow down | A company, and the text is **negative** for it. |
| Grey underline | A company with neutral (or no) sentiment. |
| Blue background with a small blue label | An **event** (the label says which kind). |
| **Yellow highlight** | The **source sentence** for a claim you are pointing at. Yellow is used for this and nothing else. |

A small legend under the title repeats this. A line above the title may say **Scanned page, read by OCR**
(the text came from a picture of a page) and has an **Original** link to the source document.

Point at a company mark and the same company lights up in the right-hand list.

**Right side: the checks** (a box with three tabs):
- **Summary:** a short summary of the document, claim by claim, with a count at the top (for example "4
  supported · 0 not verified · 1 contradicted"). Contradicted claims come first. Point at a claim (or press
  **Show source**) and its source sentence is highlighted in the text on the left, and the text scrolls to
  it.
- **Companies:** each company found, how many times it was mentioned, the confidence and its sentiment.
- **Events:** each event found, as a card.

**Why this score.** Click a company in the text (any company with a sentiment). The fourth tab, **Why this score**,
opens and shows the words around the company shaded by how much each one pushed the sentiment toward the label the
model chose (solid underline) or away from it (dotted underline), the biggest influences as chips, and the model's
confidence. It is Integrated Gradients, an explainability method; the small print under it says how closely the
influences add up to the model's score (the smaller the gap, the better the approximation).

**On a phone** there is not enough room for two columns, so a switch at the top, **Read | Checks**, flips
between them. **Show in text** under a claim jumps back to the text.

### 4.5 Ask (`/ask`)

Ask the documents a question in plain English. Example: *What action did SEBI take against Wipro Limited?*

- **Question box:** type and press **Enter** (**Shift+Enter** for a new line).
- **Microphone button:** speak instead of typing. It listens, stops when you pause, turns your voice into
  text (on your own computer, nothing is sent anywhere) and puts it in the box. Tick **Send when I stop
  talking** to skip the Enter. The button is greyed out if there is no microphone, the page is not on
  `localhost`, or the speech model is not installed (hover for the reason).
- **Try asking:** ready-made questions built from recent events.
- **How an answer is made:** three steps, shown as a line: **Find sentences → Write the answer → Check each
  claim**.

When you ask, the answer card shows those same three steps as they finish. Then you get:
- A line such as **"2 of 3 claims confirmed by a cited sentence"**.
- The claims, each with a tick, cross or question mark. If the first claim is confirmed, its source opens by
  itself, with the sentence **highlighted in yellow**. Open any other with **Show source**.
- A footer: how many sentences from how many documents it read, which company and publisher it narrowed to,
  how long it took, and a **Listen** link that reads the answer aloud (only if your browser has a built-in
  voice).
- **Sentences it read:** every sentence it had in front of it. The ones the answer cited have a yellow
  **Cited** label.

**When the answer is "The filings do not answer this":** either no document mentions that company, or the
sentences found do not answer the question, or none of the claims could be confirmed. The system would rather
say so than guess. If claims were written but none confirmed, they sit under "The draft, which no filing
confirmed".

Good to know: each question is answered on its own (it does not remember the one before). The conversation is
kept only in this browser tab and is gone when you close the tab. **Clear** empties it.

### 4.6 Events (`/events`)

Every extracted event. Same 7 / 30 / 90 day switch.

- **Kind buttons:** All, Regulatory, Insolvency, Governance, Corporate action, Dividend, each with a count.
- **Timeline picture:** one row per kind, time running left to right, one mark per event. A triangle pointing
  up is a positive event, down is negative, a circle is neutral. Click a mark to jump to that event below.
- **List by month:** each row is one event (publisher, kind, date, company, a one-line headline). **Click a
  row to open it** and see the full record: type, amounts and dates, who extracted it (a language model or
  simple rules), confidence, and a link to the filing at the sentence that triggered it.
- When several filings give the very same event on the same day, they are folded into one row with a count
  ("6 filings"); open it to see each one.
- A company shown as **Unresolved party** means the order is about someone who is not in our list of
  companies (often a person).

### 4.7 Analyze (`/analyze`)

Try the whole pipeline on **your own** document.

1. Choose a tab: **Paste text**, **Web address** (a public link, for example a SEBI order) or **PDF file**.
2. In **Where it is from**, say what kind of document it is (the event rules depend on the publisher).
3. Press **Run the pipeline**.
4. Watch the line of seven stations fill in as each finishes, with the time each took: **Ingest → Parse →
   Companies → Sentiment → Events → Summary → Verify**.
5. The result appears below in the same layout as a filing page: the marked-up text and the checks.

**Analyze another** starts over. Documents analysed here are kept apart from the collected documents: they do
not change the counts, the company pages, the events list or search.

### 4.8 Evaluation (`/evaluation`)

The report card: how well each stage works, measured against a simpler method it should beat. One tab per
stage (a tab only appears when there are results for it).

- **Sentiment:**
  - *Public benchmark against Indian data:* one row per model. A **circle** is its score on a public test
    set, a **diamond** is its score on Indian data. The line between them is how much it loses on Indian text.
    Higher is better (1.0 is perfect). Bold rows are our models; grey rows are baselines.
  - *Where it goes wrong:* a table of what the model said (columns) against what was true (rows).
  - *Calibration:* when the model says "80% sure", is it right about 80% of the time? A lower number (ECE) is
    better, and the picture shows before and after a correction.
  - A table of every number.
- **Companies:** how well company names are found and linked.
- **Events:** how well events and their details are extracted.
- **Summaries:** how well summaries match reference summaries, and how many claims are supported.
- **Questions:** how well the Ask feature retrieves the right filing and declines when it should. These
  questions were generated by the computer from our own data, so the numbers are a guide, not final.

At the bottom, **Every model** lists each model in the pipeline (FinBERT, the DeBERTa company finder, the DeBERTa claim
checker, the search embedder, Qwen, Llama, Whisper) with the figure that measures it, the best simpler baseline on the
same data, and which data it was measured on. A dash means that measure has not been run.

The grey pill at the top says when the run happened. Every number on the page comes from the stored
evaluation results.

### 4.9 Method (`/method`)

A plain reading page that needs no data: the seven stages and which model does each, the four research
questions, the datasets used, the rules on sources and ethics, and the team.

---

## 5. Things that look odd but are normal

- **Sentiment is close to zero for most companies.** The sentiment model learned from news headlines, and
  court and regulator orders are written in a very flat style, so most of it reads as neutral. This is a known
  limit, reported on the start page.
- **"Waiting for analysis" on many filings** (especially RBI press releases). They are stored and readable, but
  the models have not run on them yet.
- **"Unresolved party" in Events.** The order is about someone who is not on our company list.
- **Nothing shows or the page says "Nothing to show yet".** The API is not running. Start everything with
  `make live`.
- **Some numbers differ between pages.** For example a company's *Mentions* in the window (a count of scored
  mentions) is not the same as the length of the *Mentions* tab (the 40 newest sentences).
- **`make live` takes a minute or so to open the app.** It builds the web app once, then serves that build,
  which is what makes moving between pages quick.

---

## 6. A five-minute tour

1. Open the **start page**. Click through Supported, Contradicted and Not verified in the example.
2. Press **Open the app**. On **Home**, click one of the grey question chips.
3. On **Ask**, wait for the three steps to finish. Open **Show source** on a claim and see the yellow
   highlight.
4. Click **Companies**, open the **Sentiment map** tab, then click a company.
5. On the company page, open **Events** and **Mentions**, then click **Open filing** on a mention.
6. In the filing, point at a claim in the **Summary** tab and watch the text on the left highlight.
7. Open **Evaluation** and read the Sentiment tab.
8. Try **Analyze** with some pasted text and watch the stations fill in.
