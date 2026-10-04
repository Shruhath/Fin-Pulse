import {
  Activity,
  BookOpenText,
  Building2,
  CalendarClock,
  FileText,
  FlaskConical,
  ScanSearch,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** short description used by the command palette */
  hint: string;
}

export const NAV: NavItem[] = [
  { href: "/", label: "Overview", icon: Activity, hint: "Market spread, latest filings and companies" },
  { href: "/companies", label: "Companies", icon: Building2, hint: "Sentiment, events and summaries per company" },
  { href: "/filings", label: "Filings", icon: FileText, hint: "Read disclosures with the model's reading on top" },
  { href: "/events", label: "Events", icon: CalendarClock, hint: "Extracted events by type and date" },
  { href: "/analyze", label: "Analyze", icon: ScanSearch, hint: "Run the pipeline on text, a URL or a PDF" },
  { href: "/evaluation", label: "Evaluation", icon: FlaskConical, hint: "Model results against baselines" },
  { href: "/method", label: "Method", icon: BookOpenText, hint: "How the pipeline works and where data comes from" },
];

export const isActive = (pathname: string, href: string) =>
  href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
