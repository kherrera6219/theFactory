import { readFileSync } from "node:fs";

/** @type {import('next').NextConfig} */

// Electron previously used static export ('output: export'), which cannot
// serve any of this app's app/api/* routes (vault, session, gateway proxy,
// repo import, etc.) -- see docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md §7.1.
// Electron now runs the same kind of self-contained Node server Docker runs,
// via Next's 'standalone' output, spawned as a child process by
// electron/main.ts instead of loading a static file:// bundle. Docker's own
// build (NEXT_BUILD_TARGET=docker) is untouched -- it still runs `next start`
// against a regular build.
const isElectronBuild = process.env.NEXT_BUILD_TARGET === "electron";

// Settings > Software Version showed "dev" everywhere except inside the Electron
// window (which asks the main process). Bake the package version into the build.
const packageVersion = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf-8"),
).version;

const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_APP_VERSION: process.env.NEXT_PUBLIC_APP_VERSION || packageVersion,
  },
  poweredByHeader: false,
  images: {
    unoptimized: true,
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

if (isElectronBuild) {
  nextConfig.output = "standalone";
}

export default nextConfig;
