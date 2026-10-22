"use client";

import { Suspense } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { Segmented } from "./segmented";

function Inner() {
  const pathname = usePathname();
  const params = useSearchParams();
  const current = (params.get("w") ?? "30d") as "7d" | "30d" | "90d";
  const href = (w: string) => {
    const next = new URLSearchParams(params);
    if (w === "30d") next.delete("w");
    else next.set("w", w);
    const qs = next.toString();
    return qs ? `${pathname}?${qs}` : pathname;
  };
  return (
    <Segmented
      label="Time window"
      value={current}
      items={[
        { value: "7d", label: "7 days", href: href("7d") },
        { value: "30d", label: "30 days", href: href("30d") },
        { value: "90d", label: "90 days", href: href("90d") },
      ]}
    />
  );
}

/** The time window lives in the URL (?w=), so a link to a view keeps its window. */
export function WindowSelect() {
  return (
    <Suspense fallback={<div className="skeleton h-9 w-60 rounded-full" />}>
      <Inner />
    </Suspense>
  );
}
