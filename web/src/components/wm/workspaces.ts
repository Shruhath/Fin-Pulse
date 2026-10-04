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

export interface WorkspaceDef {
  n: number;
  key: string;
  label: string;
  href: string;
  icon: LucideIcon;
  hint: string;
  /** default layout and master width for this workspace */
  layout: "tile" | "grid" | "monocle";
  ratio: number;
}

export const WORKSPACES: WorkspaceDef[] = [
  { n: 1, key: "overview", layout: "tile", ratio: 0.62, label: "overview", href: "/", icon: Activity, hint: "Market spread, latest filings, movers" },
  { n: 2, key: "companies", layout: "tile", ratio: 0.42, label: "companies", href: "/companies", icon: Building2, hint: "Sentiment, events and claims per company" },
  { n: 3, key: "filings", layout: "tile", ratio: 0.58, label: "filings", href: "/filings", icon: FileText, hint: "Read a disclosure with the model's reading on top" },
  { n: 4, key: "events", layout: "tile", ratio: 0.6, label: "events", href: "/events", icon: CalendarClock, hint: "Extracted events by type and date" },
  { n: 5, key: "analyze", layout: "tile", ratio: 0.4, label: "analyze", href: "/analyze", icon: ScanSearch, hint: "Run the pipeline on text, a URL or a PDF" },
  { n: 6, key: "evaluation", layout: "tile", ratio: 0.55, label: "eval", href: "/evaluation", icon: FlaskConical, hint: "Models against baselines, India transfer gap" },
  { n: 7, key: "method", layout: "tile", ratio: 0.5, label: "method", href: "/method", icon: BookOpenText, hint: "How the pipeline works, data and team" },
];

export function workspaceFor(pathname: string): WorkspaceDef {
  return (
    WORKSPACES.find((w) => w.href !== "/" && (pathname === w.href || pathname.startsWith(`${w.href}/`))) ?? WORKSPACES[0]
  );
}
