import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Manrope, Newsreader } from "next/font/google";

import "./globals.css";

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  display: "swap",
});

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Clarion",
    template: "%s | Clarion",
  },
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  description:
    "Clarion visualizes AI-generated legal reports as a cinematic evidence sequence with live chronology, media, and citations.",
  openGraph: {
    title: "Clarion",
    description:
      "A cinematic report viewer for live legal chronology, multimodal evidence, and courtroom-ready storytelling.",
    images: ["/opengraph-image"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Clarion",
    description:
      "A cinematic report viewer for live legal chronology, multimodal evidence, and courtroom-ready storytelling.",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0d0b09",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${newsreader.variable} ${manrope.variable} ${plexMono.variable}`}
    >
      <head>
        <link rel="preconnect" href="https://storage.googleapis.com" />
      </head>
      <body className="min-h-screen bg-ink antialiased">
        <a
          href="#main-content"
          className="skip-link fixed left-4 top-4 z-50 rounded-full bg-amber px-4 py-2 text-sm font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-paper focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
        >
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
