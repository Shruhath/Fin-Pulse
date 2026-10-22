import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Hanken_Grotesk } from "next/font/google";

import { Providers } from "@/components/providers";
import "./globals.css";

const sans = Hanken_Grotesk({ variable: "--font-hanken", subsets: ["latin"], display: "swap" });
const display = Bricolage_Grotesque({ variable: "--font-bricolage", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: { default: "FinPulse: read the market before it moves", template: "%s · FinPulse" },
  description:
    "Ask Indian regulatory filings a question. FinPulse scores sentiment for each company, extracts events, and checks every claim against the sentence that supports it.",
};

export const viewport: Viewport = { themeColor: "#162a86" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-IN" className={`${sans.variable} ${display.variable}`} suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
