import { randomBytes } from "crypto";
import fs from "fs";

// Generates a working .env for the bundled installer stack from the
// checked-in .env.example template (bundled as an extraResource -- see
// package.json "build.extraResources"). Every CHANGE_ME_* placeholder is
// replaced with a freshly generated random value; secrets that must be
// identical everywhere they appear (e.g. the Postgres password embedded in
// three different connection strings) share one generated value via the
// secretFamily key below, while secrets that happen to share the same
// placeholder *text* in the template but are semantically independent
// (INTERNAL_SERVICE_API_KEY vs MCP_API_KEY) get distinct values.
//
// LLM provider keys (GEMINI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY) are
// intentionally left blank here -- the first-run setup wizard fills in
// whichever the operator provides before the generated .env is written.

function randomHex(bytes: number): string {
  return randomBytes(bytes).toString("hex");
}

// Maps an env var name to a secretFamily id. Vars sharing a family get the
// exact same generated value (required for connection strings that embed a
// password also set as its own separate var); vars with a unique family id
// (even ones sharing template placeholder text) get an independent value.
const SECRET_FAMILY_BY_VAR: Record<string, string> = {
  REDIS_URL: "redis_password",
  REDIS_PASSWORD: "redis_password",
  NEO4J_PASSWORD: "neo4j_password",
  POSTGRES_URL: "postgres_password",
  POSTGRES_PASSWORD: "postgres_password",
  MIGRATION_POSTGRES_URL: "postgres_password",
  LANGGRAPH_CHECKPOINTER_POSTGRES_URL: "postgres_password",
  GRAFANA_ADMIN_PASSWORD: "grafana_admin_password",
  MISSION_CONTROL_ADMIN_KEY: "mission_control_admin_key",
  MISSION_CONTROL_SESSION_SECRET: "mission_control_session_secret",
  VAULT_ADMIN_KEY: "vault_admin_key",
  ORCHESTRATOR_ADMIN_API_KEY: "orchestrator_admin_api_key",
  ORCHESTRATOR_READONLY_API_KEY: "orchestrator_readonly_api_key",
  // The gateway's accepted-key list and Mission Control's fallback caller
  // key (INTERNAL_SERVICE_API_KEY, used when no OPERATOR-API-KEY vault slot
  // is set yet) must be the SAME value, or a fresh install can't
  // authenticate its own first request.
  ORCHESTRATOR_API_KEYS: "operator_key",
  INTERNAL_SERVICE_API_KEY: "operator_key",
  POD_A_SERVICE_API_KEY: "pod_a_service_api_key",
  POD_B_SERVICE_API_KEY: "pod_b_service_api_key",
  POD_C_SERVICE_API_KEY: "pod_c_service_api_key",
  POD_D_SERVICE_API_KEY: "pod_d_service_api_key",
  AUDIT_SERVICE_API_KEY: "audit_service_api_key",
  MCP_API_KEY: "mcp_api_key",
  APPROVAL_HMAC_SECRET: "approval_hmac_secret",
};

export type LlmProviderKeys = {
  gemini?: string;
  openai?: string;
  anthropic?: string;
};

/** Reads the bundled .env.example, substitutes every CHANGE_ME_* placeholder
 * with a generated (or, for LLM keys, operator-supplied) value, and writes
 * the result to outputEnvPath. TLS cert paths are NOT parameterized here --
 * the compose file's volume mounts hardcode ./.local/{postgres,redis}-certs
 * relative to the compose file's own directory, so ensureTlsCertificates()
 * must write into that exact location (see main.ts's use of both). */
export function generateEnvFile(options: {
  templatePath: string;
  outputEnvPath: string;
  llmKeys: LlmProviderKeys;
}): void {
  const template = fs.readFileSync(options.templatePath, "utf-8");
  const secretValues = new Map<string, string>();

  const lines = template.split("\n").map((line) => {
    const eqIndex = line.indexOf("=");
    if (eqIndex === -1 || line.trim().startsWith("#")) {
      return line;
    }
    const key = line.slice(0, eqIndex).trim();

    if (line.includes("CHANGE_ME")) {
      const family = SECRET_FAMILY_BY_VAR[key];
      if (!family) {
        // Unrecognized CHANGE_ME var -- generate a unique value keyed by
        // the var name itself rather than silently leaving a placeholder.
        const value = secretValues.get(key) ?? randomHex(24);
        secretValues.set(key, value);
        // Bounded to letters/digits/underscore/plus so this stops at the
      // placeholder token itself instead of greedily consuming the rest of
      // a connection-string line (e.g. REDIS_URL's trailing @redis:6380/0).
      return line.replace(/CHANGE_ME[A-Za-z0-9_+]*/, value);
      }
      let value = secretValues.get(family);
      if (!value) {
        value = randomHex(24);
        secretValues.set(family, value);
      }
      // Bounded to letters/digits/underscore/plus so this stops at the
      // placeholder token itself instead of greedily consuming the rest of
      // a connection-string line (e.g. REDIS_URL's trailing @redis:6380/0).
      return line.replace(/CHANGE_ME[A-Za-z0-9_+]*/, value);
    }

    if (key === "GEMINI_API_KEY" && options.llmKeys.gemini) {
      return `GEMINI_API_KEY=${options.llmKeys.gemini}`;
    }
    if (key === "OPENAI_API_KEY" && options.llmKeys.openai) {
      return `OPENAI_API_KEY=${options.llmKeys.openai}`;
    }
    if (key === "ANTHROPIC_API_KEY" && options.llmKeys.anthropic) {
      return `ANTHROPIC_API_KEY=${options.llmKeys.anthropic}`;
    }
    if (key === "LLM_PROVIDER") {
      const provider = options.llmKeys.gemini
        ? "gemini"
        : options.llmKeys.openai
          ? "openai"
          : options.llmKeys.anthropic
            ? "anthropic"
            : "gemini";
      return `LLM_PROVIDER=${provider}`;
    }

    return line;
  });

  fs.writeFileSync(options.outputEnvPath, lines.join("\n"), { mode: 0o600 });
}
