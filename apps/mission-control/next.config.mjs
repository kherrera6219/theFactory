/** @type {import('next').NextConfig} */
const devScriptSources =
  process.env.NODE_ENV === "production"
    ? ["'self'", "'unsafe-inline'"]
    : ["'self'", "'unsafe-inline'", "'unsafe-eval'"];

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // 7E â€” Enable static export for Electron compatibility.
  output: "export",
  // 7E â€” Disable image optimization since we're in a static environment.
  images: {
    unoptimized: true,
  },
  async headers() {
    // Note: async headers() are ignored in static export mode ('output: export').
    // Electron relies on the local file system and CSP meta tags.
    return [];
  },
};

export default nextConfig;
