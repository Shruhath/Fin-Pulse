import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Providers } from "@/components/providers";
import { PreviewBanner } from "@/components/shell/preview-banner";
import { Rail } from "@/components/shell/rail";
import { TopBar } from "@/components/shell/topbar";
import { getStatus, isPreview } from "@/lib/api/client";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
const mono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: { default: "FinPulse", template: "%s · FinPulse" },
  description:
    "Entity-level sentiment, event extraction and source-verified summaries over Indian financial disclosures.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#0c1a30" },
    { media: "(prefers-color-scheme: dark)", color: "#070c15" },
  ],
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const status = await getStatus();
  return (
    <html lang="en-IN" className={`${inter.variable} ${mono.variable}`} suppressHydrationWarning>
      <body>
        <Providers>
          <div className="flex min-h-dvh">
            <Rail />
            <div className="flex min-w-0 flex-1 flex-col">
              <TopBar corpus={status.state === "ok" ? status.data : null} />
              {isPreview() && <PreviewBanner />}
              <main id="main" className="flex-1">
                {children}
              </main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
