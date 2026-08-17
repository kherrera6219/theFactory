import { defineConfig } from "vitest/config";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      "server-only": path.resolve(rootDir, "app/lib/test/server-only.ts"),
    },
  },
  test: {
    environment: "jsdom",
    include: ["app/**/*.test.ts"],
    clearMocks: true,
    coverage: {
      provider: "v8",
      include: ["app/lib/**/*.{ts,tsx}"],
      exclude: [
        "**/*.test.ts",
        "app/lib/types.ts",
        "app/lib/types/**",
        "app/lib/mock-data.ts",
        "app/lib/test/**",
      ],
      thresholds: {
        lines: 60,
        statements: 60,
        functions: 50,
        branches: 45,
      },
      reporter: ["text", "json-summary"],
    },
  },
});
