import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const displayFont = Inter({
  subsets: ["latin"],
  variable: "--font-display",
  preload: false,
  display: "optional",
});
const monoFont = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "700"],
  preload: false,
  display: "optional",
});

export const metadata: Metadata = {
  title: "Holy Grail Refinery — Mission Control",
  description: "Multi-agent AI software manufacturing system — mission intake, orchestration, and operator control.",
};

type RootLayoutProps = {
  children: ReactNode;
};

import { DialogProvider } from "./components/dialog-provider";

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <head>
        {/* CSP for the Electron static build. next.config headers() are ignored
            under `output: export`, so the policy ships as a meta tag instead. */}
        <meta
          httpEquiv="Content-Security-Policy"
          content="default-src 'self' http://localhost:* ws://localhost:*; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' http://localhost:* ws://localhost:*;"
        />

      </head>
      <body className={`${displayFont.variable} ${monoFont.variable}`}>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <DialogProvider>
          {children}
        </DialogProvider>
      </body>
    </html>
  );
}
