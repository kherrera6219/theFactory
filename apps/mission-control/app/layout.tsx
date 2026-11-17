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
  const isProd = process.env.NODE_ENV === "production";
  const scriptSrc = isProd ? "script-src 'self' 'unsafe-inline'" : "script-src 'self' 'unsafe-inline' 'unsafe-eval'";
  const cspContent = [
    "default-src 'self' http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*",
    scriptSrc,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "connect-src 'self' http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
  ].join("; ") + ";";

  return (
    <html lang="en">
      <head>
        {/* CSP for standalone/Electron builds. */}
        <meta
          httpEquiv="Content-Security-Policy"
          content={cspContent}
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
