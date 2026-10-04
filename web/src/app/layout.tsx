import type { Metadata, Viewport } from "next";
import { Hanken_Grotesk, JetBrains_Mono } from "next/font/google";

import { Providers } from "@/components/providers";
import { KeyHelp } from "@/components/wm/help";
import { Launcher } from "@/components/wm/launcher";
import { PreviewStrip } from "@/components/wm/preview-strip";
import { StatusBar } from "@/components/wm/status-bar";
import { Toasts } from "@/components/wm/toasts";
import { Wallpaper } from "@/components/wm/wallpaper";
import { WMProvider } from "@/components/wm/wm";
import { getSearchIndex, getStatus, getWallpaper, isPreview } from "@/lib/api/client";
import "./globals.css";

const sans = Hanken_Grotesk({ variable: "--font-hanken", subsets: ["latin"], display: "swap" });
const mono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: { default: "FinPulse", template: "%s · FinPulse" },
  description: "Entity-level sentiment, event extraction and source-verified summaries over Indian financial disclosures.",
};

export const viewport: Viewport = { themeColor: "#050608" };

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const [status, index, wall] = await Promise.all([getStatus(), getSearchIndex(), getWallpaper()]);
  const preview = isPreview();
  return (
    <html lang="en-IN" className={`${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <body>
        <Providers>
          <WMProvider>
            <Wallpaper matrix={wall.state === "ok" ? wall.data : null} />
            <div className="relative z-10 flex min-h-dvh flex-col lg:h-dvh lg:min-h-0 lg:overflow-hidden">
              <StatusBar corpus={status.state === "ok" ? status.data : null} preview={preview} />
              {preview && <PreviewStrip />}
              <main id="main" className="min-h-0 flex-1">
                {children}
              </main>
            </div>
            <Launcher index={index.state === "ok" ? index.data : null} />
            <KeyHelp />
            <Toasts />
          </WMProvider>
        </Providers>
      </body>
    </html>
  );
}
