import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { SITE_URL } from "@/lib/mcp";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "Open source experimental tool for discovering relevant hedges using event contracts and prediction markets",
  description:
    "Inspired by Blanket (https://tryblanket.app/). Install the hosted MCP in Grok, Cursor, Codex, or Claude. openhedge does not hold money or place trades.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-background font-sans text-foreground">
        {children}
      </body>
    </html>
  );
}
