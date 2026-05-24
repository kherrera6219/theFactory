/** @type {import('next').NextConfig} */

// Docker builds use server mode (supports API routes); Electron uses static export.
const isDockerBuild = process.env.NEXT_BUILD_TARGET === "docker";

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    unoptimized: true,
  },
  async headers() {
    // Note: async headers() are ignored in static export mode ('output: export').
    // Electron relies on the local file system and CSP meta tags.
    return [];
  },
};

if (!isDockerBuild) {
  nextConfig.output = "export";
}

export default nextConfig;
