import type { Metadata } from "next";

import { MethodWorkspace } from "@/components/workspaces/method";

export const metadata: Metadata = { title: "Method" };

export default function MethodPage() {
  return <MethodWorkspace />;
}
