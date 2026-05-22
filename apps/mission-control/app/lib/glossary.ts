/** 6A — Domain term definitions used by the <Tooltip> component throughout the shell. */
export type GlossaryEntry = {
  term: string;
  definition: string;
};

export const GLOSSARY: Record<string, GlossaryEntry> = {
  // ── Smelt-Cycle phases ──────────────────────────────────────────────────
  INTAKE: {
    term: "Intake",
    definition:
      "The PM Agent processes the mission request, generates a Feature Contract and Mission Charter, and validates scope before any code work begins.",
  },
  GATING: {
    term: "Gating",
    definition:
      "Quality and compliance gates validate the mission against Pod Group Standards and depth-mode constraints before execution is authorised.",
  },
  ROUTING: {
    term: "Routing",
    definition:
      "The chain-of-command resolver selects which agent pods and LogicNode clusters will handle the mission and assigns work packages.",
  },
  EXECUTION: {
    term: "Execution",
    definition:
      "Active agent pods process LogicNode clusters in parallel, producing code artefacts, test results, and build outputs.",
  },
  VERIFICATION: {
    term: "Verification",
    definition:
      "Equivalence checking, RQCA analysis, and runtime QC validate all artefacts against the original Feature Contract.",
  },
  DELIVERY: {
    term: "Delivery",
    definition:
      "Verified artefacts are packaged and made available for download. The mission transitions to COMPLETE.",
  },
  AUDIT: {
    term: "Audit",
    definition:
      "An immutable audit-evidence chain is produced linking every decision back to the originating Feature Contract and Mission Charter.",
  },
  // ── MissionFlow V2 phases ───────────────────────────────────────────────
  PM_INTAKE: {
    term: "PM Intake",
    definition:
      "The PM Agent conducts a structured intake conversation, extracting requirements, acceptance criteria, and constraint bounds.",
  },
  ARCHITECT: {
    term: "Architect",
    definition:
      "The architecture phase generates the technical design, selects technology stack, and creates the initial LogicNode graph.",
  },
  BUILD: {
    term: "Build",
    definition:
      "Agent pods implement the architecture plan, producing code, tests, and configuration artefacts for each LogicNode.",
  },
  REVIEW: {
    term: "Review",
    definition:
      "Automated code review, linting, and security scans validate all generated artefacts before integration.",
  },
  INTEGRATE: {
    term: "Integrate",
    definition:
      "Reviewed artefacts are merged into the working baseline and end-to-end integration tests are executed.",
  },
  // ── Domain terms ────────────────────────────────────────────────────────
  LogicNode: {
    term: "Logic Node",
    definition:
      "A discrete unit of work in the mission graph. Each LogicNode maps to a code module, test suite, or analysis task and tracks its own completion state.",
  },
  Pod: {
    term: "Pod",
    definition:
      "A named group of specialised agents that collaborate on a LogicNode cluster. Pods are assigned by the Routing phase.",
  },
  "Mission Charter": {
    term: "Mission Charter",
    definition:
      "A structured brief generated during Intake that captures scope, constraints, acceptance criteria, depth mode, and timeline.",
  },
  "Feature Contract": {
    term: "Feature Contract",
    definition:
      "A formal specification of the feature being built — inputs, outputs, edge cases, and integration points. The contract is the source of truth for Verification.",
  },
  "Chain Trace": {
    term: "Chain Trace",
    definition:
      "The complete record of routing decisions, agent assignments, and artefact lineage for a mission. Used for audit and debugging.",
  },
  RQCA: {
    term: "RQCA",
    definition:
      "Runtime Quality & Compliance Analysis — automatically validates generated code against security, style, correctness, and coverage rules.",
  },
  AIM: {
    term: "Application Intelligence Map",
    definition:
      "A structured representation of the target codebase's architecture, call graph, and dependency topology, extracted during repo import.",
  },
  "Smelt-Cycle": {
    term: "Smelt-Cycle",
    definition:
      "The 7-phase lifecycle every HolyGrail mission follows: Intake → Gating → Routing → Execution → Verification → Delivery → Audit.",
  },
  "Depth Mode": {
    term: "Depth Mode",
    definition:
      "Controls how deeply the mission analyses the codebase: SURFACE (fast scan), STANDARD (module level), DEEP (full AST + cross-file), or EXHAUSTIVE.",
  },
  "Logic Clusters": {
    term: "Logic Clusters",
    definition:
      "Groups of related LogicNodes identified by the routing algorithm. Clusters are processed by the same pod to preserve context.",
  },
  "Pod Group Standards": {
    term: "Pod Group Standards",
    definition:
      "Per-pod quality benchmarks generated during Gating. Each pod must meet its standards before artefacts are accepted into Verification.",
  },
  Fusion: {
    term: "Fusion",
    definition:
      "The master logic stream that merges outputs from all LogicNodes into a coherent, ordered sequence of changes.",
  },
};
