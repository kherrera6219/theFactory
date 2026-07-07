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

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    unoptimized: true,
  },
  async headers() {
    return [];
  },
};

if (isElectronBuild) {
  nextConfig.output = "standalone";
}

export default nextConfig;
