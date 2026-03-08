import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const appRoot = process.cwd();
const sourcePath = path.resolve(appRoot, "../../assets/design-tokens/tokens.css");
const targetPath = path.resolve(appRoot, "app/generated-tokens.css");

if (!existsSync(sourcePath)) {
  if (existsSync(targetPath)) {
    console.log(`Design token source not found at ${sourcePath}; using existing ${targetPath}`);
    process.exit(0);
  }
  throw new Error(`design token source not found and no generated fallback exists: ${sourcePath}`);
}

const sourceCss = readFileSync(sourcePath, "utf8");
const banner =
  "/* Generated from ../../assets/design-tokens/tokens.css. Do not edit manually. */\n";
mkdirSync(path.dirname(targetPath), { recursive: true });
writeFileSync(targetPath, `${banner}${sourceCss}`, "utf8");
console.log(`Synced design tokens: ${sourcePath} -> ${targetPath}`);
