import type {
  AgentRecord,
  AlertRecord,
  BusEventRecord,
  LogicNodeRecord,
  ProjectRecord,
  TemplateRecord,
} from "./types";

const now = Date.now();

export const AGENTS: AgentRecord[] = [
  {
    id: "PM-001",
    name: "PM Agent",
    role: "Mission planning and orchestration guidance",
    pod: "Executive",
    state: "ACTIVE",
    workloadPct: 62,
    queueDepth: 4,
    lastHeartbeatIso: new Date(now - 8_000).toISOString(),
  },
  {
    id: "CEO-001",
    name: "CEO Agent",
    role: "Task decomposition and cross-pod coordination",
    pod: "Executive",
    state: "RUNNING",
    workloadPct: 71,
    queueDepth: 2,
    lastHeartbeatIso: new Date(now - 11_000).toISOString(),
  },
  {
    id: "AUDIT-001",
    name: "Audit Lead",
    role: "Verification and release quality checks",
    pod: "Support",
    state: "VERIFYING",
    workloadPct: 56,
    queueDepth: 5,
    lastHeartbeatIso: new Date(now - 13_000).toISOString(),
  },
  {
    id: "AGENT-PY-001",
    name: "Python Specialist",
    role: "Dynamic language extraction",
    pod: "Pod A",
    state: "ACTIVE",
    workloadPct: 77,
    queueDepth: 7,
    lastHeartbeatIso: new Date(now - 9_000).toISOString(),
  },
  {
    id: "AGENT-GO-001",
    name: "Go Specialist",
    role: "Systems implementation support",
    pod: "Pod B",
    state: "IDLE",
    workloadPct: 22,
    queueDepth: 1,
    lastHeartbeatIso: new Date(now - 7_000).toISOString(),
  },
  {
    id: "AGENT-JAVA-001",
    name: "Java Specialist",
    role: "Enterprise service extraction",
    pod: "Pod C",
    state: "PAUSED",
    workloadPct: 36,
    queueDepth: 3,
    lastHeartbeatIso: new Date(now - 21_000).toISOString(),
  },
  {
    id: "AGENT-RUST-001",
    name: "Rust Specialist",
    role: "Optimization and safety-focused output",
    pod: "Pod B",
    state: "ERROR",
    workloadPct: 84,
    queueDepth: 8,
    lastHeartbeatIso: new Date(now - 35_000).toISOString(),
  },
];

export const LOGICNODES: LogicNodeRecord[] = [
  {
    id: "ln-payroll-01",
    missionId: "mission-a1",
    domain: "Payroll",
    intent: "Validate overtime accrual eligibility rules",
    confidence: 0.97,
    status: "VERIFIED",
    sourceRef: "registry://missions/mission-a1/extract/payroll.py:42",
  },
  {
    id: "ln-benefits-07",
    missionId: "mission-a1",
    domain: "Benefits",
    intent: "Apply waiting-period constraints for coverage activation",
    confidence: 0.91,
    status: "PENDING",
    sourceRef: "registry://missions/mission-a1/extract/benefits.ts:117",
  },
  {
    id: "ln-eligibility-03",
    missionId: "mission-b3",
    domain: "Eligibility",
    intent: "Resolve union rule precedence and fallback exceptions",
    confidence: 0.88,
    status: "FAILED",
    sourceRef: "registry://missions/mission-b3/extract/rules.cbl:302",
  },
];

export const BUS_EVENTS: BusEventRecord[] = [
  {
    id: "evt-1001",
    ts: new Date(now - 12_000).toISOString(),
    protocol: "ALPHA",
    producer: "api-gateway",
    topic: "intake.feature_contract.created",
    summary: "Mission intake envelope published",
    priority: "NORMAL",
  },
  {
    id: "evt-1002",
    ts: new Date(now - 8_000).toISOString(),
    protocol: "BETA",
    producer: "orchestrator",
    topic: "mission.state.running",
    summary: "Lifecycle transitioned mission-a1 to RUNNING",
    priority: "HIGH",
  },
  {
    id: "evt-1003",
    ts: new Date(now - 4_000).toISOString(),
    protocol: "DELTA",
    producer: "audit-worker",
    topic: "audit.report.generated",
    summary: "Audit summary generated for mission-a1",
    priority: "NORMAL",
  },
];

export const ALERTS: AlertRecord[] = [
  {
    id: "alt-01",
    title: "Rust Specialist Error Spike",
    severity: "high",
    state: "open",
    source: "AGENT-RUST-001",
    createdAt: new Date(now - 65_000).toISOString(),
    recommendation: "Inspect recent extraction payloads and retry failed tasks.",
  },
  {
    id: "alt-02",
    title: "Semantic Bus Backlog Growing",
    severity: "medium",
    state: "acknowledged",
    source: "semantic-bus",
    createdAt: new Date(now - 160_000).toISOString(),
    recommendation: "Scale consumer throughput or throttle low-priority events.",
  },
  {
    id: "alt-03",
    title: "Pod C Memory Near Threshold",
    severity: "low",
    state: "resolved",
    source: "pod-c-runtime",
    createdAt: new Date(now - 340_000).toISOString(),
    recommendation: "Monitor for recurrence during peak load windows.",
  },
];

export const PROJECTS: ProjectRecord[] = [
  {
    id: "prj-hr-modernization",
    name: "HR Rules Modernization",
    status: "active",
    lastUpdatedAt: new Date(now - 35_000).toISOString(),
    missionCount: 8,
  },
  {
    id: "prj-payroll-refinery",
    name: "Payroll Refinery Expansion",
    status: "paused",
    lastUpdatedAt: new Date(now - 210_000).toISOString(),
    missionCount: 5,
  },
  {
    id: "prj-compliance-upgrade",
    name: "Compliance Rule Harmonization",
    status: "completed",
    lastUpdatedAt: new Date(now - 1_400_000).toISOString(),
    missionCount: 16,
  },
];

export const TEMPLATES: TemplateRecord[] = [
  {
    id: "tpl-modernize-legacy",
    title: "Legacy Modernization Plan",
    category: "Modernization",
    summary: "Analyze legacy systems, extract LogicNodes, and build phased migration tasks.",
  },
  {
    id: "tpl-quality-audit",
    title: "Enterprise Quality Audit",
    category: "Audit",
    summary: "Run correctness, security, and performance checks with production-grade reporting.",
  },
  {
    id: "tpl-cross-language",
    title: "Cross-Language Equivalence",
    category: "Verification",
    summary: "Compare implementations across languages and generate equivalence proof artifacts.",
  },
];
