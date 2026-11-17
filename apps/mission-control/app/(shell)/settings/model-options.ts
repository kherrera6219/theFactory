export type ModelOption = {
  label: string;
  provider: "openai" | "anthropic" | "gemini";
  model:
    | "gpt-6.1-terrea"
    | "gpt-5.6"
    | "claude-opus-5-5"
    | "claude-ops-5.5"
    | "claude-opus-5.5"
    | "claude-opus-4-8"
    | "gemini-4-argon"
    | "gemini-3.8-flash";
  endpoint: string;
  effort: "high";
};

export const MODEL_OPTIONS: ModelOption[] = [
  {
    label: "Gemini 4 Argon",
    provider: "gemini",
    model: "gemini-4-argon",
    endpoint: "POST /v1beta/models/gemini-4-argon:generateContent",
    effort: "high",
  },
  {
    label: "ChatGPT 6.1 Terrea",
    provider: "openai",
    model: "gpt-6.1-terrea",
    endpoint: "POST /v1/responses",
    effort: "high",
  },
  {
    label: "Claude Opus 5.5",
    provider: "anthropic",
    model: "claude-opus-5-5",
    endpoint: "POST /v1/messages",
    effort: "high",
  },
];

export const DEFAULT_MODEL_OPTION = MODEL_OPTIONS[0];

// NOTE: a stored model that is not in MODEL_OPTIONS renders as the default
// rather than as itself, so this page can show "Gemini 3.8 Flash" while the
// vault holds something else entirely — which is exactly how a stale 3.5 pin
// went unnoticed while it routed every live mission. The vault now migrates
// superseded revisions on read (see normalizeModel), so this fallback should
// only ever see genuinely unknown values; keep that migration in step with
// MODEL_OPTIONS whenever an option is retired.
export function modelOptionFor(model: string | null | undefined): ModelOption {
  return MODEL_OPTIONS.find((option) => option.model === model) ?? DEFAULT_MODEL_OPTION;
}

// Static agent registry — fallback when orchestrator is offline.
export const STATIC_AGENT_SLOTS: Array<{
  agentId: string;
  name: string;
  provider: string;
  model: string;
}> = [
  ["AGENT-01-PM", "PM Agent"],
  ["AGENT-02-CEO", "CEO Agent"],
  ["AGENT-03-BROKER", "API Broker"],
  ["AGENT-04-ACCOUNTANT", "Accountant"],
  ["AGENT-05-SECURITY", "Security Agent"],
  ["AGENT-06-IS", "IS Agent"],
  ["AGENT-07-VC", "Version Control Agent"],
  ["AGENT-08-COMPLIANCE", "Compliance Agent"],
  ["AGENT-09-HW", "Hardware-Mapping Injector"],
  ["AGENT-10-TESTER", "System Integration Tester"],
  ["AGENT-11-DEPLOY", "Deployment Agent"],
  ["AGENT-12-PODA-MGR", "Pod A Sub-Manager"],
  ["AGENT-13-PODA-AUDIT", "Pod A QC/Audit"],
  ["AGENT-14-PYTHON", "Python Specialist"],
  ["AGENT-15-JAVASCRIPT", "JavaScript Specialist"],
  ["AGENT-16-RUBY", "Ruby Specialist"],
  ["AGENT-17-PHP", "PHP Specialist"],
  ["AGENT-18-PODB-MGR", "Pod B Sub-Manager"],
  ["AGENT-19-PODB-AUDIT", "Pod B QC/Audit"],
  ["AGENT-20-C", "C Specialist"],
  ["AGENT-21-CPP", "C++ Specialist"],
  ["AGENT-22-RUST", "Rust Specialist"],
  ["AGENT-23-ZIG", "Zig Specialist"],
  ["AGENT-24-PODC-MGR", "Pod C Sub-Manager"],
  ["AGENT-25-PODC-AUDIT", "Pod C QC/Audit"],
  ["AGENT-26-JAVA", "Java Specialist"],
  ["AGENT-27-CSHARP", "C# Specialist"],
  ["AGENT-28-SCALA", "Scala Specialist"],
  ["AGENT-29-KOTLIN", "Kotlin Specialist"],
  ["AGENT-30-PODD-MGR", "Pod D Sub-Manager"],
  ["AGENT-31-PODD-AUDIT", "Pod D QC/Audit"],
  ["AGENT-32-MATLAB", "MATLAB Specialist"],
  ["AGENT-33-R", "R Specialist"],
  ["AGENT-34-JULIA", "Julia Specialist"],
  ["AGENT-35-MATHEMATICA", "Mathematica Specialist"],
  ["AGENT-36-GO", "Go Specialist"],
  ["AGENT-37-HASKELL", "Haskell Specialist"],
  ["AGENT-38-OCAML", "OCaml Specialist"],
  ["AGENT-39-DEPABS", "Dependency Absorption Agent"],
  ["AGENT-40-TESTDATA", "Database and Test Data Agent"],
  ["AGENT-41-RQCA", "Runtime QC Agent"],
].map(([agentId, name]) => ({
  agentId,
  name,
  provider: DEFAULT_MODEL_OPTION.provider,
  model: DEFAULT_MODEL_OPTION.model,
}));
