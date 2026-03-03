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
  },
});
