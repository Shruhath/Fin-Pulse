"use client";

import * as Tabs from "@radix-ui/react-tabs";
import clsx from "clsx";

import { useSlider } from "./use-slider";

export interface TabItem {
  value: string;
  label: string;
  count?: number;
}

/** Underlined tabs with an indicator that slides. Render the panels with Tabs.Content inside <TabRoot>. */
export function TabBar({ items, active, className }: { items: TabItem[]; active: string; className?: string }) {
  const [ref, box] = useSlider<HTMLDivElement>([active, items.length]);
  return (
    <Tabs.List ref={ref} aria-label="Sections" className={clsx("relative flex gap-1 overflow-x-auto border-b border-line", className)}>
      {items.map((t) => (
        <Tabs.Trigger
          key={t.value}
          value={t.value}
          className={clsx(
            "relative -mb-px inline-flex h-11 items-center gap-1.5 px-3.5 text-sm font-medium whitespace-nowrap transition-colors duration-200",
            "text-ink-3 hover:text-ink data-[state=active]:text-ink",
            !box && "data-[state=active]:border-b-2 data-[state=active]:border-brand",
          )}
        >
          {t.label}
          {t.count !== undefined && <span className="num rounded-full bg-surface-3 px-1.5 text-xs text-ink-2">{t.count}</span>}
        </Tabs.Trigger>
      ))}
      {box && (
        <span
          aria-hidden="true"
          className="absolute bottom-0 left-0 h-0.5 rounded-full bg-brand transition-[transform,width] duration-300 ease-(--ease-out)"
          style={{ width: box.w, transform: `translateX(${box.x}px)` }}
        />
      )}
    </Tabs.List>
  );
}

export const TabRoot = Tabs.Root;
export const TabPanel = ({ value, className, children }: { value: string; className?: string; children: React.ReactNode }) => (
  <Tabs.Content value={value} className={clsx("fade-up pt-5 outline-none", className)}>
    {children}
  </Tabs.Content>
);
