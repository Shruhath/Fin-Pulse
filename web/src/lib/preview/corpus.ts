/**
 * SYNTHETIC PREVIEW CORPUS, not model output.
 *
 * Invented filings used only when FINPULSE_PREVIEW=1 so every workspace can be
 * designed before the pipeline exists. Company names are real listed companies
 * for layout realism; every sentence, figure, label and verdict here is made
 * up and must never be presented as a finding about those companies.
 */

import type { EventType, SentimentLabel, SourceKind, Verification } from "@/lib/api/types";

export const AS_OF = Date.UTC(2026, 9, 3, 6, 0); // 3 Oct 2026, 11:30 IST
export const DAY = 86_400_000;

// [id, name, ticker, sector, drift target, volatility, aliases]
export const COMPANIES: [string, string, string, string, number, number, string[]][] = [
  ["reliance", "Reliance Industries", "RELIANCE", "Energy", 0.18, 0.09, ["RIL", "Reliance Industries Ltd"]],
  ["hdfcbank", "HDFC Bank", "HDFCBANK", "Banking", 0.12, 0.07, ["HDFC Bank Limited"]],
  ["icicibank", "ICICI Bank", "ICICIBANK", "Banking", 0.22, 0.07, ["ICICI Bank Ltd"]],
  ["sbin", "State Bank of India", "SBIN", "Banking", 0.05, 0.08, ["SBI"]],
  ["infy", "Infosys", "INFY", "IT Services", -0.24, 0.1, ["Infosys Limited", "Infosys Ltd"]],
  ["tcs", "Tata Consultancy Services", "TCS", "IT Services", 0.08, 0.06, ["TCS"]],
  ["wipro", "Wipro", "WIPRO", "IT Services", -0.12, 0.09, ["Wipro Limited"]],
  ["yesbank", "Yes Bank", "YESBANK", "Banking", -0.31, 0.12, ["Yes Bank Ltd", "YES BANK"]],
  ["bajfinance", "Bajaj Finance", "BAJFINANCE", "NBFC", -0.18, 0.11, ["Bajaj Finance Limited"]],
  ["paytm", "One 97 Communications", "PAYTM", "Fintech", -0.42, 0.13, ["Paytm", "One 97 Communications Ltd"]],
  ["sunpharma", "Sun Pharmaceutical", "SUNPHARMA", "Pharma", 0.26, 0.08, ["Sun Pharma", "Sun Pharmaceutical Industries Ltd"]],
  ["drreddy", "Dr. Reddy's Laboratories", "DRREDDY", "Pharma", 0.14, 0.09, ["Dr. Reddy's"]],
  ["tatamotors", "Tata Motors", "TATAMOTORS", "Auto", 0.31, 0.1, ["Tata Motors Ltd"]],
  ["maruti", "Maruti Suzuki", "MARUTI", "Auto", 0.09, 0.07, ["Maruti Suzuki India Ltd"]],
  ["adaniports", "Adani Ports & SEZ", "ADANIPORTS", "Infrastructure", -0.08, 0.14, ["Adani Ports"]],
  ["lt", "Larsen & Toubro", "LT", "Infrastructure", 0.27, 0.07, ["L&T", "Larsen & Toubro Ltd"]],
  ["zeel", "Zee Entertainment", "ZEEL", "Media", -0.36, 0.13, ["Zee Entertainment Enterprises Ltd", "ZEEL"]],
  ["vedl", "Vedanta", "VEDL", "Metals", -0.21, 0.12, ["Vedanta Limited"]],
  ["itc", "ITC", "ITC", "FMCG", 0.11, 0.05, ["ITC Limited"]],
  ["hul", "Hindustan Unilever", "HINDUNILVR", "FMCG", 0.02, 0.05, ["HUL"]],
];

export interface DocSeed {
  id: string;
  day: number;
  hour: number;
  title: string;
  source: SourceKind;
  status: "ingested" | "parsed" | "analysed" | "failed";
  ocr?: boolean;
  text: string;
  mentions: [surface: string, entityId: string, sentiment: SentimentLabel, confidence: number][];
  events: [type: EventType, entityId: string, trigger: string, args: Record<string, string>, sentiment: SentimentLabel, confidence: number, extractor: "llm" | "rules"][];
  claims: [text: string, verification: Verification, evidence: string | null, entail: number, contradict: number][];
}

export const DOCS: DocSeed[] = [
  {
    id: "sebi-ao-one97",
    day: 0,
    hour: 0,
    title: "Adjudication order in respect of One 97 Communications Ltd",
    source: "SEBI",
    status: "analysed",
    text: "ADJUDICATION ORDER under Section 15-I of the Securities and Exchange Board of India Act, 1992. In respect of One 97 Communications Ltd (Noticee). The Noticee is a listed entity whose equity shares trade on BSE and NSE. An examination found that the Noticee did not obtain prior approval of the audit committee for certain related-party transactions with an associate entity during FY2024-25. The Noticee submitted that the transactions were in the ordinary course of business and on an arm's-length basis. Having considered the submissions, I find that the disclosure obligations under Regulation 23 of the LODR Regulations were not complied with. A penalty of ₹1.2 crore is hereby imposed on One 97 Communications Ltd, payable within 45 days of receipt of this order. Paytm has stated that it will evaluate its legal options.",
    mentions: [
      ["One 97 Communications Ltd", "paytm", "negative", 0.91],
      ["Paytm", "paytm", "negative", 0.74],
    ],
    events: [
      ["SEBI Penalty", "paytm", "A penalty of ₹1.2 crore is hereby imposed on One 97 Communications Ltd, payable within 45 days of receipt of this order.", { amount: "₹1.2 crore", regulation: "Regulation 23, LODR", authority: "SEBI adjudicating officer", deadline: "45 days" }, "negative", 0.93, "llm"],
    ],
    claims: [
      ["SEBI imposed a ₹1.2 crore penalty on One 97 Communications for related-party transaction lapses.", "entailed", "A penalty of ₹1.2 crore is hereby imposed on One 97 Communications Ltd, payable within 45 days of receipt of this order.", 0.94, 0.02],
      ["The order found that LODR Regulation 23 disclosure obligations were not met.", "entailed", "I find that the disclosure obligations under Regulation 23 of the LODR Regulations were not complied with.", 0.9, 0.03],
      ["The company accepted the order and paid the penalty immediately.", "contradicted", "Paytm has stated that it will evaluate its legal options.", 0.04, 0.86],
    ],
  },
  {
    id: "bse-itc-board",
    day: 0,
    hour: 3,
    title: "Outcome of board meeting: interim dividend and Q2 results",
    source: "BSE",
    status: "analysed",
    text: "ITC Limited hereby informs the Exchange that the Board of Directors at its meeting held today approved the unaudited financial results for the quarter ended 30 September 2026. The Board declared an interim dividend of ₹6.50 per ordinary share of ₹1 each for the financial year 2026-27. The record date for the interim dividend is fixed as 14 October 2026. Gross revenue from operations for the quarter grew 8.4% year on year, led by the cigarettes and FMCG businesses, while the agri business saw lower export volumes. The results have been reviewed by the statutory auditors.",
    mentions: [["ITC Limited", "itc", "positive", 0.84]],
    events: [
      ["Regular Dividend", "itc", "The Board declared an interim dividend of ₹6.50 per ordinary share of ₹1 each for the financial year 2026-27.", { amount: "₹6.50 per share", record_date: "14 Oct 2026", period: "FY2026-27 interim" }, "positive", 0.95, "rules"],
    ],
    claims: [
      ["ITC declared an interim dividend of ₹6.50 per share with a record date of 14 October.", "entailed", "The Board declared an interim dividend of ₹6.50 per ordinary share of ₹1 each for the financial year 2026-27.", 0.93, 0.01],
      ["Quarterly revenue grew 8.4% year on year.", "entailed", "Gross revenue from operations for the quarter grew 8.4% year on year, led by the cigarettes and FMCG businesses, while the agri business saw lower export volumes.", 0.91, 0.02],
      ["Every business segment reported higher volumes this quarter.", "contradicted", "Gross revenue from operations for the quarter grew 8.4% year on year, led by the cigarettes and FMCG businesses, while the agri business saw lower export volumes.", 0.06, 0.78],
    ],
  },
  {
    id: "bse-lt-order",
    day: 1,
    hour: 21,
    title: "Award of order: metro rail elevated viaduct package",
    source: "BSE",
    status: "analysed",
    text: "Larsen & Toubro Ltd is pleased to announce that its Heavy Civil Infrastructure business has secured a significant order for the construction of an elevated viaduct and eleven stations for a metro rail corridor in western India. As per the company's classification, a significant order lies between ₹2,500 crore and ₹5,000 crore. The project is to be completed in 42 months. L&T said the order strengthens its transportation infrastructure order book, which stood at a record level at the end of the previous quarter.",
    mentions: [
      ["Larsen & Toubro Ltd", "lt", "positive", 0.89],
      ["L&T", "lt", "positive", 0.81],
    ],
    events: [
      ["New Contract", "lt", "Larsen & Toubro Ltd is pleased to announce that its Heavy Civil Infrastructure business has secured a significant order for the construction of an elevated viaduct and eleven stations for a metro rail corridor in western India.", { value: "₹2,500–5,000 crore", duration: "42 months", segment: "Heavy Civil Infrastructure" }, "positive", 0.9, "llm"],
    ],
    claims: [
      ["Larsen & Toubro won a metro rail order worth between ₹2,500 crore and ₹5,000 crore.", "entailed", "As per the company's classification, a significant order lies between ₹2,500 crore and ₹5,000 crore.", 0.88, 0.02],
      ["The order is expected to lift quarterly margins by 150 basis points.", "unverified", null, 0.21, 0.12],
    ],
  },
  {
    id: "rbi-yesbank-penalty",
    day: 1,
    hour: 16,
    title: "RBI imposes monetary penalty on Yes Bank Ltd",
    source: "RBI",
    status: "analysed",
    text: "The Reserve Bank of India (RBI) has, by an order dated 30 September 2026, imposed a monetary penalty of ₹91 lakh on Yes Bank Ltd for non-compliance with certain directions issued by RBI on Know Your Customer (KYC). This penalty has been imposed in exercise of powers conferred on RBI under Section 47A(1)(c) read with Section 46(4)(i) of the Banking Regulation Act, 1949. The action is based on deficiencies in regulatory compliance and is not intended to pronounce upon the validity of any transaction or agreement entered into by the bank with its customers.",
    mentions: [["Yes Bank Ltd", "yesbank", "negative", 0.88]],
    events: [
      ["RBI Action", "yesbank", "The Reserve Bank of India (RBI) has, by an order dated 30 September 2026, imposed a monetary penalty of ₹91 lakh on Yes Bank Ltd for non-compliance with certain directions issued by RBI on Know Your Customer (KYC).", { amount: "₹91 lakh", provision: "Section 47A(1)(c), BR Act", grounds: "KYC directions" }, "negative", 0.92, "llm"],
    ],
    claims: [
      ["RBI fined Yes Bank ₹91 lakh for KYC non-compliance.", "entailed", "The Reserve Bank of India (RBI) has, by an order dated 30 September 2026, imposed a monetary penalty of ₹91 lakh on Yes Bank Ltd for non-compliance with certain directions issued by RBI on Know Your Customer (KYC).", 0.95, 0.01],
      ["RBI said the penalty invalidates the affected customer transactions.", "contradicted", "The action is based on deficiencies in regulatory compliance and is not intended to pronounce upon the validity of any transaction or agreement entered into by the bank with its customers.", 0.02, 0.93],
    ],
  },
  {
    id: "bse-infy-guidance",
    day: 2,
    hour: 21,
    title: "Revision of revenue guidance and analyst call transcript",
    source: "BSE",
    status: "analysed",
    text: "Infosys Limited has revised its revenue growth guidance for FY2026-27 to 1%–2% in constant currency, from 2%–4% earlier, citing delayed decision-making by clients in financial services and retail. Operating margin guidance is retained at 20%–22%. On the analyst call, management said large deal wins remained healthy and pointed to an improving pipeline in Europe. Analysts compared the revision with TCS, which retained its outlook last week.",
    mentions: [
      ["Infosys Limited", "infy", "negative", 0.86],
      ["TCS", "tcs", "neutral", 0.63],
    ],
    events: [
      ["Guidance Change", "infy", "Infosys Limited has revised its revenue growth guidance for FY2026-27 to 1%–2% in constant currency, from 2%–4% earlier, citing delayed decision-making by clients in financial services and retail.", { metric: "Revenue growth (cc)", from: "2%–4%", to: "1%–2%", period: "FY2026-27" }, "negative", 0.94, "llm"],
    ],
    claims: [
      ["Infosys cut its FY27 revenue growth guidance to 1–2% in constant currency.", "entailed", "Infosys Limited has revised its revenue growth guidance for FY2026-27 to 1%–2% in constant currency, from 2%–4% earlier, citing delayed decision-making by clients in financial services and retail.", 0.96, 0.01],
      ["Operating margin guidance was also lowered.", "contradicted", "Operating margin guidance is retained at 20%–22%.", 0.03, 0.91],
      ["Management expects deal wins in Europe to accelerate next quarter.", "unverified", "On the analyst call, management said large deal wins remained healthy and pointed to an improving pipeline in Europe.", 0.48, 0.07],
    ],
  },
  {
    id: "bse-zeel-auditor",
    day: 2,
    hour: 16,
    title: "Resignation of statutory auditor: Regulation 30 disclosure",
    source: "BSE",
    status: "analysed",
    text: "Pursuant to Regulation 30 of the SEBI (LODR) Regulations, Zee Entertainment Enterprises Ltd informs that its statutory auditor has tendered its resignation with effect from 1 October 2026. In its resignation letter, the auditor stated that it had not received information requested for the audit of certain inter-company balances in a timely manner. The Audit Committee has noted the resignation and will recommend the appointment of a new auditor to fill the casual vacancy. ZEEL said it had cooperated fully with the auditor.",
    mentions: [
      ["Zee Entertainment Enterprises Ltd", "zeel", "negative", 0.9],
      ["ZEEL", "zeel", "neutral", 0.58],
    ],
    events: [
      ["Auditor Resignation", "zeel", "Pursuant to Regulation 30 of the SEBI (LODR) Regulations, Zee Entertainment Enterprises Ltd informs that its statutory auditor has tendered its resignation with effect from 1 October 2026.", { effective: "1 Oct 2026", reason: "Information not received in time", next_step: "Casual vacancy appointment" }, "negative", 0.91, "llm"],
    ],
    claims: [
      ["Zee's statutory auditor resigned, citing delays in receiving information.", "entailed", "In its resignation letter, the auditor stated that it had not received information requested for the audit of certain inter-company balances in a timely manner.", 0.92, 0.03],
      ["The audit committee disputed the auditor's account.", "unverified", null, 0.18, 0.22],
    ],
  },
  {
    id: "bse-sunpharma-acq",
    day: 3,
    hour: 15,
    title: "Completion of acquisition of specialty portfolio",
    source: "BSE",
    status: "analysed",
    text: "Sun Pharmaceutical Industries Ltd informs that its wholly owned subsidiary has completed the acquisition of a portfolio of specialty dermatology brands in the United States. The acquisition was funded from internal accruals. The portfolio is expected to be accretive to earnings from the next financial year. Sun Pharma said the deal deepens its specialty franchise, which now contributes a growing share of its US revenue. Dr. Reddy's had bid for a part of the same portfolio earlier this year.",
    mentions: [
      ["Sun Pharmaceutical Industries Ltd", "sunpharma", "positive", 0.87],
      ["Sun Pharma", "sunpharma", "positive", 0.8],
      ["Dr. Reddy's", "drreddy", "neutral", 0.66],
    ],
    events: [
      ["Acquisition", "sunpharma", "Sun Pharmaceutical Industries Ltd informs that its wholly owned subsidiary has completed the acquisition of a portfolio of specialty dermatology brands in the United States.", { target: "US specialty dermatology brands", funding: "Internal accruals", status: "Completed" }, "positive", 0.89, "llm"],
    ],
    claims: [
      ["Sun Pharma completed a US specialty dermatology acquisition funded from internal accruals.", "entailed", "The acquisition was funded from internal accruals.", 0.86, 0.02],
      ["The deal is expected to add to earnings from next year.", "entailed", "The portfolio is expected to be accretive to earnings from the next financial year.", 0.89, 0.02],
    ],
  },
  {
    id: "bse-vedl-pledge",
    day: 3,
    hour: 10,
    title: "Disclosure of invocation of pledged shares",
    source: "BSE",
    status: "analysed",
    text: "Disclosure under Regulation 31(1) of the SEBI (Substantial Acquisition of Shares and Takeovers) Regulations. A lender has invoked a pledge over 2.1% of the equity share capital of Vedanta Limited held by a promoter group entity, following a shortfall in the security cover. After the invocation, the promoter group's encumbered holding stands reduced. Vedanta Limited said the invocation does not affect the operations of the company.",
    mentions: [["Vedanta Limited", "vedl", "negative", 0.83]],
    events: [
      ["Pledge Invocation", "vedl", "A lender has invoked a pledge over 2.1% of the equity share capital of Vedanta Limited held by a promoter group entity, following a shortfall in the security cover.", { stake: "2.1%", holder: "Promoter group entity", trigger: "Security cover shortfall" }, "negative", 0.9, "llm"],
    ],
    claims: [
      ["A lender invoked a pledge on 2.1% of Vedanta's equity held by a promoter entity.", "entailed", "A lender has invoked a pledge over 2.1% of the equity share capital of Vedanta Limited held by a promoter group entity, following a shortfall in the security cover.", 0.95, 0.01],
    ],
  },
  {
    id: "nclt-adaniports-s7",
    day: 4,
    hour: 6,
    title: "Order under Section 7 of the Insolvency and Bankruptcy Code",
    source: "NCLT",
    status: "parsed",
    ocr: true,
    text: "IN THE NATIONAL COMPANY LAW TRIBUNAL, AHMEDABAD BENCH. Company Petition (IB) under Section 7 of the Insolvency and Bankruptcy Code, 2016. The petition filed by a financial creditor against a contractor engaged on projects of Adani Ports & SEZ is admitted. The Corporate Insolvency Resolution Process is initiated and an Interim Resolution Professional is appointed. A moratorium under Section 14 is declared. Adani Ports is not a party to the petition.",
    mentions: [
      ["Adani Ports & SEZ", "adaniports", "neutral", 0.55],
      ["Adani Ports", "adaniports", "neutral", 0.6],
    ],
    events: [],
    claims: [],
  },
  {
    id: "bse-auto-sales",
    day: 4,
    hour: 9,
    title: "Press release: monthly sales update for September",
    source: "BSE",
    status: "analysed",
    text: "Tata Motors Ltd reported total domestic sales of 84,920 units in September 2026, up 11% year on year, with passenger vehicle sales at a record high on festive demand. Maruti Suzuki India Ltd, in a separate filing, reported total sales of 1,96,410 units, up 6% year on year, with exports rising faster than domestic volumes.",
    mentions: [
      ["Tata Motors Ltd", "tatamotors", "positive", 0.88],
      ["Maruti Suzuki India Ltd", "maruti", "positive", 0.79],
    ],
    events: [],
    claims: [
      ["Tata Motors' September domestic sales rose 11% year on year.", "entailed", "Tata Motors Ltd reported total domestic sales of 84,920 units in September 2026, up 11% year on year, with passenger vehicle sales at a record high on festive demand.", 0.94, 0.01],
      ["Maruti Suzuki's domestic volumes grew faster than its exports.", "contradicted", "Maruti Suzuki India Ltd, in a separate filing, reported total sales of 1,96,410 units, up 6% year on year, with exports rising faster than domestic volumes.", 0.03, 0.9],
    ],
  },
  {
    id: "sebi-so-bajfinance",
    day: 5,
    hour: 7,
    title: "Settlement order: delayed disclosure of rating action",
    source: "SEBI",
    status: "analysed",
    text: "SETTLEMENT ORDER in respect of Bajaj Finance Limited. Proceedings were initiated for delayed disclosure to the stock exchanges of a revision in the credit rating of certain debt instruments. Bajaj Finance Limited filed a settlement application without admitting or denying the findings of fact and conclusions of law. The application is settled on payment of ₹18.4 lakh towards settlement charges, and the proceedings are disposed of.",
    mentions: [["Bajaj Finance Limited", "bajfinance", "negative", 0.72]],
    events: [
      ["SEBI Penalty", "bajfinance", "The application is settled on payment of ₹18.4 lakh towards settlement charges, and the proceedings are disposed of.", { amount: "₹18.4 lakh", type: "Settlement charges", grounds: "Delayed disclosure of rating action" }, "negative", 0.84, "llm"],
    ],
    claims: [
      ["Bajaj Finance settled SEBI proceedings by paying ₹18.4 lakh.", "entailed", "The application is settled on payment of ₹18.4 lakh towards settlement charges, and the proceedings are disposed of.", 0.93, 0.02],
      ["Bajaj Finance admitted the delayed disclosure.", "contradicted", "Bajaj Finance Limited filed a settlement application without admitting or denying the findings of fact and conclusions of law.", 0.05, 0.84],
    ],
  },
  {
    id: "bse-wipro-buyback",
    day: 5,
    hour: 12,
    title: "Intimation of buyback through tender offer",
    source: "BSE",
    status: "ingested",
    text: "Wipro Limited informs that the Board of Directors has approved a proposal to buy back equity shares through the tender offer route for an aggregate amount not exceeding ₹12,000 crore, subject to shareholder approval.",
    mentions: [],
    events: [],
    claims: [],
  },
];

/** Events that live outside the twelve documents above, for the timeline. */
export const EXTRA_EVENTS: [day: number, type: EventType, entityId: string, headline: string, source: SourceKind, sentiment: SentimentLabel][] = [
  [9, "Dividend Increase", "tcs", "Raises interim dividend to ₹11 per share", "BSE", "positive"],
  [14, "Stock Repurchase", "wipro", "Board approves buyback of up to ₹12,000 crore", "BSE", "positive"],
  [17, "NCLT Admission", "adaniports", "NCLT admits insolvency petition against a project contractor", "NCLT", "neutral"],
  [21, "Clinical Trial", "drreddy", "Phase III biosimilar trial meets its primary endpoint", "BSE", "positive"],
  [26, "RBI Action", "bajfinance", "RBI lifts restrictions on two digital lending products", "RBI", "positive"],
  [33, "SEBI Penalty", "zeel", "SEBI order on diversion of funds by former promoters", "SEBI", "negative"],
  [41, "Special Dividend", "maruti", "Declares special dividend alongside quarterly results", "BSE", "positive"],
  [52, "Dividend Cut", "vedl", "Reduces interim dividend as commodity margins compress", "BSE", "negative"],
  [64, "Acquisition", "reliance", "Acquires a controlling stake in a renewable component maker", "BSE", "positive"],
  [77, "RBI Action", "paytm", "RBI directions on payments bank onboarding", "RBI", "negative"],
  [83, "Stock Split", "hdfcbank", "Board considers sub-division of equity shares", "BSE", "positive"],
  [88, "Guidance Change", "wipro", "Narrows revenue outlook for the quarter", "BSE", "negative"],
];
