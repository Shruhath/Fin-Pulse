import {
  Activity,
  Building2,
  CalendarClock,
  FileText,
  FlaskConical,
  Home,
  MessageSquareText,
  ScanSearch,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  key: string;
  label: string;
  href: string;
  icon: LucideIcon;
  hint: string;
}

/** The four places people go every day. */
export const PRIMARY: NavItem[] = [
  { key: "home", label: "Home", href: "/home", icon: Home, hint: "What changed lately" },
  { key: "companies", label: "Companies", href: "/companies", icon: Building2, hint: "Sentiment, events and claims per company" },
  { key: "filings", label: "Filings", href: "/filings", icon: FileText, hint: "Read a disclosure with the model's reading on top" },
  { key: "ask", label: "Ask", href: "/ask", icon: MessageSquareText, hint: "Ask the filings a question" },
];

/** Deeper views: what was extracted, a way to try your own document, and the evidence that it works. */
export const INSIGHTS: NavItem[] = [
  { key: "events", label: "Events", href: "/events", icon: CalendarClock, hint: "Extracted events by type and date" },
  { key: "analyze", label: "Analyze", href: "/analyze", icon: ScanSearch, hint: "Run the pipeline on text, a URL or a PDF" },
  { key: "evaluation", label: "Evaluation", href: "/evaluation", icon: FlaskConical, hint: "Models against baselines" },
  { key: "method", label: "Method", href: "/method", icon: Activity, hint: "How the pipeline works, data and team" },
];

export const ALL_NAV: NavItem[] = [...PRIMARY, ...INSIGHTS];

export function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}
