import type { Metadata } from "next";
import { DM_Sans, Playfair_Display, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

const baseUrl = process.env.NEXT_PUBLIC_BASE_URL ?? "https://clarion.ai";

export const metadata: Metadata = {
  title: "Clarion — AI Litigation Analysis",
  description:
    "AI that detects contradictions and evidence gaps in legal cases in seconds. Built for litigators who can't afford to miss anything.",
  metadataBase: new URL(baseUrl),
  openGraph: {
    title: "Clarion — AI Litigation Analysis",
    description:
      "AI that detects contradictions and evidence gaps in legal cases in seconds.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${dmSans.variable} ${playfair.variable} ${jetbrainsMono.variable}`}
    >
      <body className="bg-background text-text-primary antialiased flex flex-col h-screen overflow-hidden">
        <div className="grain-overlay" aria-hidden="true" />
        <header className="shrink-0 border-b border-border px-4 py-2 flex items-center">
          <span className="font-display text-base font-semibold tracking-tight text-text-primary">
            Clarion
          </span>
        </header>
        <div className="flex-1 min-h-0 overflow-hidden">
          {children}
        </div>
      </body>
    </html>
  );
}
