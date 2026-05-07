from __future__ import annotations

from typing import Any

from .agent_registry import AgentDefinition

_PROTOCOL_NAMES: dict[str, str] = {
    "alpha": "Directive",
    "beta": "Production",
    "delta": "Audit",
    "sigma": "Knowledge",
    "omega": "User",
    "rho": "Traffic",
}
_PROTOCOL_PURPOSES: dict[str, str] = {
    "alpha": "Strategic command and task assignment messages.",
    "beta": "Work product and LogicNode submission flow.",
    "delta": "Verification, security, and compliance findings.",
    "sigma": "Standards and knowledge dissemination.",
    "omega": "User-intent translation and mission status handoff.",
    "rho": "Runtime events, rate limits, and routing directives.",
}
_PROTOCOL_FORMATS: dict[str, str] = {
    "alpha": "Refined-IR contract directives and assignment envelopes.",
    "beta": "LogicNode payloads, group standards, and progress events.",
    "delta": "Pass/fail evidence reports with remediation detail.",
    "sigma": "Standards manifest updates and knowledge query responses.",
    "omega": "Natural-language mission intake and progress updates.",
    "rho": "Operational telemetry and traffic-control broadcasts.",
}

_LANGUAGE_LABELS: dict[str, str] = {
    "python": "Python",
    "javascript": "JavaScript/TypeScript",
    "ruby": "Ruby",
    "php": "PHP",
    "c": "C",
    "cpp": "C++",
    "rust": "Rust",
    "zig": "Zig",
    "java": "Java",
    "csharp": "C#",
    "scala": "Scala",
    "kotlin": "Kotlin",
    "matlab": "MATLAB",
    "r": "R",
    "julia": "Julia",
    "mathematica": "Mathematica",
}
_LANGUAGE_GUIDANCE: dict[str, str] = {
    "python": "PEP 8 style, typing discipline, and packaging standards.",
    "javascript": "ECMAScript and TypeScript typing with async runtime safety.",
    "ruby": "Ruby object model, conventions, and maintainable Rails patterns.",
    "php": "Modern PHP standards and framework-safe backend conventions.",
    "c": "Deterministic memory handling and low-level systems discipline.",
    "cpp": "RAII, template hygiene, and safe high-performance abstractions.",
    "rust": "Ownership model correctness with explicit lifetime safety.",
    "zig": "Explicit allocation and predictable compile-time behavior.",
    "java": "JVM architecture patterns and enterprise reliability design.",
    "csharp": ".NET architecture, async correctness, and API consistency.",
    "scala": "Functional-object hybrid patterns and type-level correctness.",
    "kotlin": "Null safety and coroutine-driven concurrency design.",
    "matlab": "Numerical method stability and matrix-oriented workflows.",
    "r": "Statistical reproducibility and analytical model integrity.",
    "julia": "High-performance numerical kernels and multiple dispatch design.",
    "mathematica": "Symbolic computation correctness and formal expression handling.",
}
_LANGUAGE_TOOLING: dict[str, str] = {
    "python": "Python runtime and ecosystem references",
    "javascript": "JavaScript/TypeScript runtime and framework references",
    "ruby": "Ruby runtime and Rails/gem ecosystem references",
    "php": "PHP runtime and framework references",
    "c": "C toolchain and systems ABI references",
    "cpp": "C++ toolchain and STL/compiler references",
    "rust": "Rust toolchain and cargo ecosystem references",
    "zig": "Zig compiler and standard library references",
    "java": "JDK/JVM and enterprise framework references",
    "csharp": ".NET runtime and framework references",
    "scala": "Scala/JVM compiler and functional libraries",
    "kotlin": "Kotlin/JVM toolchain and coroutine references",
    "matlab": "MATLAB numerical and engineering references",
    "r": "R language and statistics package references",
    "julia": "Julia language and scientific package references",
    "mathematica": "Wolfram language and symbolic engine references",
}

_CATEGORY_EDUCATION: dict[str, list[str]] = {
    "interface": [
        "Human-computer interaction and product discovery practice.",
        "Requirements engineering and UX communication discipline.",
    ],
    "executive": [
        "Systems architecture and distributed orchestration strategy.",
        "Enterprise delivery management and mission governance.",
    ],
    "support": [
        "Operational reliability engineering and incident management.",
        "Cross-functional software platform operations expertise.",
    ],
    "pod_manager": [
        "Polyglot software architecture and cross-language synthesis.",
        "Refined-IR consolidation and pod-level planning methods.",
    ],
    "pod_audit": [
        "Formal verification, validation strategy, and quality engineering.",
        "Evidence-driven audit methods and defect triage practice.",
    ],
    "specialist": [
        "Advanced language-specific software engineering fundamentals.",
        "Semantic extraction and logic normalization practice.",
    ],
}

_CATEGORY_TRAITS: dict[str, list[str]] = {
    "interface": [
        "Empathetic requirement interpretation.",
        "Clear stakeholder communication.",
        "Outcome-oriented quality validation.",
    ],
    "executive": [
        "Strategic decomposition across pods.",
        "Global optimization and conflict resolution.",
        "High-accountability decision ownership.",
    ],
    "support": [
        "Reliability-first operational mindset.",
        "Cross-agent dependency awareness.",
        "Fast incident triage and escalation.",
    ],
    "pod_manager": [
        "Pattern synthesis across language variants.",
        "Coordination under parallel workloads.",
        "Standards-focused output shaping.",
    ],
    "pod_audit": [
        "Adversarial edge-case analysis.",
        "Strict pass/fail gate discipline.",
        "Traceable evidence reporting.",
    ],
    "specialist": [
        "Language-native pattern recognition.",
        "Precise intent extraction from source constructs.",
        "Low-hallucination, standards-grounded reasoning.",
    ],
}

_CATEGORY_METHODS: dict[str, list[str]] = {
    "interface": [
        "Capture user intent and convert it into structured mission contracts.",
        "Define success criteria and non-functional constraints before execution.",
        "Review delivery outcomes against initial user expectations.",
    ],
    "executive": [
        "Decompose mission scope into pod-level assignments.",
        "Coordinate semantic bus directives and cross-pod dependencies.",
        "Consolidate pod outputs into a unified mission strategy.",
    ],
    "support": [
        "Monitor runtime health, traffic, and quality-control indicators.",
        "Enforce role-specific guardrails and escalate anomalies.",
        "Publish operational status updates to dependent agents.",
    ],
    "pod_manager": [
        "Merge specialist outputs into pod-level group standards.",
        "Resolve overlapping semantics and remove redundant logic.",
        "Route validated artifacts to executive fusion workflows.",
    ],
    "pod_audit": [
        "Generate repeatable verification suites for each submitted artifact.",
        "Compare expected and observed outcomes at strict tolerance levels.",
        "Return clear remediation reports for rejected artifacts.",
    ],
    "specialist": [
        "Extract language intent into Refined-IR compatible structures.",
        "Preserve behavior while removing syntax-specific noise.",
        "Submit artifacts for pod audit with source traceability.",
    ],
}

_CATEGORY_TOOLS: dict[str, list[str]] = {
    "interface": [
        "Mission Control UI",
        "Semantic Bus status streams",
        "Feature contract templates",
    ],
    "executive": [
        "Global mission state graph",
        "Semantic Bus orchestration channels",
        "Cross-pod dependency trackers",
    ],
    "support": [
        "Operational dashboards",
        "Runtime telemetry events",
        "Incident and alert streams",
    ],
    "pod_manager": [
        "Pod coordination channels",
        "Group-standard consolidation templates",
        "Refined-IR normalization references",
    ],
    "pod_audit": [
        "Verification harnesses",
        "Audit evidence records",
        "Regression failure catalogs",
    ],
    "specialist": [
        "Language documentation catalogs",
        "Refined-IR extraction templates",
        "Pod submission channels",
    ],
}

_CATEGORY_CACHE_HINTS: dict[str, list[str]] = {
    "interface": ["product requirement playbooks", "user-story and UX heuristics"],
    "executive": ["system architecture plans", "cross-pod orchestration patterns"],
    "support": ["operations runbooks", "incident response and reliability playbooks"],
    "pod_manager": ["group-standard templates", "cross-language equivalence patterns"],
    "pod_audit": ["formal verification suites", "audit verdict templates"],
    "specialist": ["language standards", "domain concept catalogs"],
}

_SHORT_CODE_TITLE: dict[str, str] = {
    "PM": "Program Manager and UX Lead",
    "CEO": "Executive Orchestrator",
    "BROKER": "API Broker and Traffic Controller",
    "ACCOUNTANT": "FinOps and Budget Assurance Lead",
    "SECURITY": "Security Analysis and Threat Detection Lead",
    "IS": "Intelligence and Standards Curator",
    "VC": "Version Control and Provenance Lead",
    "COMPLIANCE": "Compliance and License Assurance Lead",
    "HW": "Hardware Mapping and Performance Optimization Lead",
    "TESTER": "System Integration and Adversarial Testing Lead",
    "DEPLOY": "Deployment and Release Reliability Lead",
    "PODA-MGR": "Pod A Synthesis Manager",
    "PODA-AUDIT": "Pod A Verification Lead",
    "PODB-MGR": "Pod B Synthesis Manager",
    "PODB-AUDIT": "Pod B Verification Lead",
    "PODC-MGR": "Pod C Synthesis Manager",
    "PODC-AUDIT": "Pod C Verification Lead",
    "PODD-MGR": "Pod D Synthesis Manager",
    "PODD-AUDIT": "Pod D Verification Lead",
    "DEPABS": "Dependency Absorption and Supply-Chain Safety Lead",
    "TESTDATA": "Ephemeral Test Environment and Synthetic Data Lead",
    "RQCA": "Runtime Quality Control and Browser Validation Lead",
}

_SHORT_CODE_SCOPE: dict[str, str] = {
    "PM": "Owns mission intake translation and final user-facing validation.",
    "CEO": "Owns global orchestration state and cross-pod execution planning.",
    "BROKER": "Owns provider routing, API key isolation, and rate-limit governance.",
    "ACCOUNTANT": "Owns mission-level spend control, token budgeting, and FinOps alerts.",
    "SECURITY": "Owns security risk triage, vulnerability discovery, and rejection authority.",
    "IS": "Owns standards indexing, documentation freshness, and knowledge broadcasts.",
    "VC": "Owns repository traceability, commit hygiene, and rollback readiness.",
    "COMPLIANCE": "Owns license compatibility and provenance evidence integrity.",
    "HW": "Owns runtime hardware tuning and host-level performance mapping strategy.",
    "TESTER": "Owns integration evidence and release-blocking failure discovery.",
    "DEPLOY": "Owns packaging, delivery readiness, and post-release stability gates.",
    "DEPABS": "Owns absorption decisions, equivalence evidence, and SBOM delta integrity.",
    "TESTDATA": "Owns per-mission ephemeral environment lifecycle and test data correctness.",
    "RQCA": "Owns runtime quality control verdict authority and sandbox execution safety.",
}

_SHORT_CODE_EDUCATION: dict[str, list[str]] = {
    "BROKER": [
        "Cloud API operations and rate-limiting strategy.",
        "Secure key-management and routing controls.",
    ],
    "ACCOUNTANT": [
        "FinOps cost accounting and token-economics governance.",
        "Budget policy enforcement for AI workloads.",
    ],
    "SECURITY": [
        "Secure software architecture and vulnerability analysis.",
        "Threat modeling and adversarial testing practice.",
    ],
    "IS": [
        "Information architecture and semantic retrieval design.",
        "Technical standards curation and change monitoring.",
    ],
    "VC": [
        "Software configuration management and GitOps practice.",
        "Release provenance and change-control governance.",
    ],
    "COMPLIANCE": [
        "Software licensing and IP provenance assessment.",
        "Auditability controls and enterprise policy interpretation.",
    ],
    "HW": [
        "Computer architecture and performance engineering.",
        "CPU/GPU optimization and systems profiling methods.",
    ],
    "TESTER": [
        "Quality engineering and failure-mode analysis.",
        "Test strategy design for distributed systems.",
    ],
    "DEPLOY": [
        "Release engineering and containerized delivery operations.",
        "Production readiness and rollback orchestration.",
    ],
    "DEPABS": [
        "Software dependency analysis and supply-chain risk assessment.",
        "Equivalence testing design and behavioral verification methods.",
    ],
    "TESTDATA": [
        "Database schema management and migration framework operations.",
        "Synthetic data generation, fixture design, and test isolation strategy.",
    ],
    "RQCA": [
        "Browser automation and end-to-end application validation.",
        "Sandbox orchestration and AI-driven runtime inspection methods.",
    ],
}

_SHORT_CODE_TRAITS: dict[str, list[str]] = {
    "BROKER": ["Latency-aware routing decisions.", "Strict key-isolation discipline."],
    "ACCOUNTANT": ["Cost-anomaly detection rigor.", "Budget-threshold enforcement precision."],
    "SECURITY": ["Assume-breach mindset.", "Zero-tolerance vulnerability gating."],
    "IS": ["Standards-first curation.", "High-context synthesis across sources."],
    "VC": ["Traceability discipline.", "Reversible change planning."],
    "COMPLIANCE": ["Evidence-first policy checks.", "Conservative legal-risk posture."],
    "HW": ["Resource-efficiency bias.", "Deterministic performance tuning."],
    "TESTER": ["Adversarial validation approach.", "Regression containment mindset."],
    "DEPLOY": ["Release safety prioritization.", "Operational rollback readiness."],
    "DEPABS": ["Absorb-first decision discipline.", "Safety-block enforcement rigor."],
    "TESTDATA": ["Isolation-first data strategy.", "Schema-fidelity and fixture accuracy."],
    "RQCA": ["Trust-but-verify runtime inspection.", "Sandbox containment discipline."],
}

_SHORT_CODE_METHODS: dict[str, list[str]] = {
    "BROKER": [
        "Rank inbound tasks by latency sensitivity and complexity.",
        "Route calls to primary/fallback providers with continuity guarantees.",
        "Enforce key-level quotas and publish Rho capacity advisories.",
    ],
    "ACCOUNTANT": [
        "Track per-agent token and cost consumption over mission lifecycle.",
        "Trigger budget alerts and recommend context-window resets on waste.",
        "Publish spend telemetry to support governance and planning decisions.",
    ],
    "SECURITY": [
        "Inspect artifacts for vulnerability signatures and weak trust boundaries.",
        "Return high-confidence rejection reports when exploitability is detected.",
        "Coordinate remediation loops with pod audits and executive control.",
    ],
    "IS": [
        "Maintain a continuously indexed standards and documentation corpus.",
        "Broadcast critical upgrades and deprecations through Sigma channels.",
        "Respond to agent queries with source-grounded technical guidance.",
    ],
    "VC": [
        "Enforce atomic commit boundaries aligned to mission events.",
        "Generate rollback-safe release points and provenance annotations.",
        "Validate branch state before merge or deployment transitions.",
    ],
    "COMPLIANCE": [
        "Map artifacts to license obligations and third-party attribution records.",
        "Detect incompatibilities before packaging and release approval.",
        "Emit compliance verdicts with actionable remediation requirements.",
    ],
    "HW": [
        "Profile mission workloads to identify compute and memory hotspots.",
        "Apply hardware-targeted optimization policies for local host constraints.",
        "Publish runtime tuning recommendations and bottleneck advisories.",
    ],
    "TESTER": [
        "Construct adversarial integration scenarios across pod boundaries.",
        "Measure reliability, performance, and regression impact before release.",
        "Escalate release-blocking defects with reproducible evidence.",
    ],
    "DEPLOY": [
        "Package validated artifacts into reproducible deployment bundles.",
        "Run release checklists before environment handoff.",
        "Coordinate staged rollout and rollback instructions for operators.",
    ],
    "DEPABS": [
        "Classify each dependency against the safety block list before any absorption attempt.",
        "Extract the computational intent of target dependency into equivalent first-party code.",
        "Run shadow equivalence comparison against the original before removing the dependency.",
        "Produce a SBOM delta and absorption report with pass/fail evidence for every decision.",
    ],
    "TESTDATA": [
        "Provision ephemeral per-mission database environments from the migration framework.",
        "Generate synthetic, schema-valid test data covering boundary conditions and edge cases.",
        "Tear down all test environments and purge data after mission completion or failure.",
        "Publish environment-ready and environment-torn-down events to unblock downstream agents.",
    ],
    "RQCA": [
        "Launch the built application in a sandboxed environment and execute the golden-path flow.",
        "Capture screenshots, console errors, and network failures as QC evidence.",
        "Produce a structured runtime QC report with pass/fail verdict and remediation notes.",
        "Block mission promotion when critical runtime failures are detected.",
    ],
}

_SHORT_CODE_TOOLS: dict[str, list[str]] = {
    "BROKER": ["Provider routing policies", "Key vault orchestration"],
    "ACCOUNTANT": ["Token telemetry ledger", "Mission budget reports"],
    "SECURITY": ["Threat intelligence references", "Security findings ledger"],
    "IS": ["Knowledge index and retrieval engine", "Documentation watchlists"],
    "VC": ["Git history and branch control", "Release provenance ledgers"],
    "COMPLIANCE": ["License inventory matrix", "Provenance traceability ledger"],
    "HW": ["Performance profilers", "Hardware capability maps"],
    "TESTER": ["Integration test suites", "Failure and benchmark reports"],
    "DEPLOY": ["Build artifacts and release manifests", "Delivery environment checklists"],
    "DEPABS": ["Dependency absorption plans", "SBOM delta reports", "Safety block list"],
    "TESTDATA": ["Ephemeral environment manifests", "Test data fixture catalog"],
    "RQCA": ["Runtime QC reports", "Browser automation scripts", "Sandbox configuration"],
}

_SHORT_CODE_CACHE_HINTS: dict[str, list[str]] = {
    "BROKER": ["provider routing tables", "rate-limit policies"],
    "ACCOUNTANT": ["token pricing and budget thresholds", "mission spend baselines"],
    "SECURITY": ["security threat catalogs", "hardening checklists"],
    "IS": ["standards manifests", "language/framework release notes"],
    "VC": ["branch governance standards", "commit policy templates"],
    "COMPLIANCE": ["license compatibility matrices", "provenance and attribution policies"],
    "HW": ["host hardware profiles", "performance tuning playbooks"],
    "TESTER": ["integration test matrices", "failure pattern catalogs"],
    "DEPLOY": ["release runbooks", "rollback and recovery procedures"],
    "DEPABS": ["dependency absorption doctrine", "safety block list and equivalence test patterns"],
    "TESTDATA": ["migration framework dispatchers", "synthetic data generation playbooks"],
    "RQCA": ["browser automation playbooks", "runtime QC checklists"],
}

_SHORT_CODE_PRIMARY_PROTOCOL: dict[str, str] = {
    "PM": "omega",
    "CEO": "alpha",
    "BROKER": "rho",
    "ACCOUNTANT": "rho",
    "SECURITY": "delta",
    "IS": "sigma",
    "VC": "rho",
    "COMPLIANCE": "delta",
    "HW": "rho",
    "TESTER": "delta",
    "DEPLOY": "omega",
    "DEPABS": "delta",
    "TESTDATA": "rho",
    "RQCA": "delta",
}

_STANDARDS_SOURCES: dict[str, dict[str, str]] = {
    "nist-csf-2.0": {
        "source_id": "nist-csf-2.0",
        "title": "NIST Cybersecurity Framework (CSF) 2.0",
        "organization": "NIST",
        "version": "2.0",
        "url": "https://www.nist.gov/cyberframework",
        "last_verified": "2026-03-02",
    },
    "nist-ai-rmf-1.0": {
        "source_id": "nist-ai-rmf-1.0",
        "title": "NIST AI Risk Management Framework (AI RMF 1.0)",
        "organization": "NIST",
        "version": "1.0",
        "url": "https://www.nist.gov/itl/ai-risk-management-framework",
        "last_verified": "2026-03-02",
    },
    "nist-sp-800-218": {
        "source_id": "nist-sp-800-218",
        "title": "NIST SP 800-218: Secure Software Development Framework (SSDF)",
        "organization": "NIST",
        "version": "1.1",
        "url": "https://csrc.nist.gov/pubs/sp/800/218/final",
        "last_verified": "2026-03-02",
    },
    "nist-sp-800-53r5": {
        "source_id": "nist-sp-800-53r5",
        "title": "NIST SP 800-53 Rev. 5/5.2: Security and Privacy Controls",
        "organization": "NIST",
        "version": "Rev.5 (Rev.5.2 update)",
        "url": "https://www.nist.gov/news-events/news/2025/09/nist-updates-privacy-and-security-guidelines-safeguard-federal-systems",
        "last_verified": "2026-03-02",
    },
    "nist-sp-800-61r3": {
        "source_id": "nist-sp-800-61r3",
        "title": "NIST SP 800-61 Rev. 3: Incident Response Recommendations",
        "organization": "NIST",
        "version": "Rev.3",
        "url": "https://csrc.nist.gov/pubs/sp/800/61/r3/final",
        "last_verified": "2026-03-02",
    },
    "owasp-top-10-2021": {
        "source_id": "owasp-top-10-2021",
        "title": "OWASP Top 10 Web Application Security Risks",
        "organization": "OWASP",
        "version": "2021",
        "url": "https://owasp.org/www-project-top-ten/",
        "last_verified": "2026-03-02",
    },
    "owasp-asvs-v5": {
        "source_id": "owasp-asvs-v5",
        "title": "OWASP Application Security Verification Standard",
        "organization": "OWASP",
        "version": "5.0",
        "url": "https://owasp.org/www-project-application-security-verification-standard/",
        "last_verified": "2026-03-02",
    },
    "iso-iec-27001-2022": {
        "source_id": "iso-iec-27001-2022",
        "title": "ISO/IEC 27001 Information Security Management",
        "organization": "ISO/IEC",
        "version": "2022",
        "url": "https://www.iso.org/standard/27001",
        "last_verified": "2026-03-02",
    },
    "iso-iec-42001-2023": {
        "source_id": "iso-iec-42001-2023",
        "title": "ISO/IEC 42001 AI Management Systems",
        "organization": "ISO/IEC",
        "version": "2023",
        "url": "https://www.iso.org/standard/81230.html",
        "last_verified": "2026-03-02",
    },
}

_BASELINE_STANDARD_IDS: tuple[str, ...] = (
    "nist-csf-2.0",
    "nist-ai-rmf-1.0",
    "iso-iec-42001-2023",
)
_CATEGORY_STANDARD_IDS: dict[str, tuple[str, ...]] = {
    "support": ("nist-sp-800-53r5",),
    "pod_manager": ("nist-sp-800-218",),
    "pod_audit": ("nist-sp-800-218", "owasp-asvs-v5"),
    "specialist": ("nist-sp-800-218", "owasp-asvs-v5"),
}
_SHORT_CODE_STANDARD_IDS: dict[str, tuple[str, ...]] = {
    "SECURITY": ("owasp-top-10-2021", "nist-sp-800-61r3", "iso-iec-27001-2022"),
    "TESTER": ("owasp-top-10-2021", "nist-sp-800-61r3"),
    "COMPLIANCE": ("iso-iec-27001-2022", "owasp-asvs-v5"),
    "VC": ("nist-sp-800-218",),
    "DEPLOY": ("nist-sp-800-218", "iso-iec-27001-2022"),
    "BROKER": ("iso-iec-27001-2022",),
    "ACCOUNTANT": ("iso-iec-27001-2022",),
    "IS": ("iso-iec-27001-2022",),
    "CEO": ("nist-sp-800-218",),
    "PM": ("nist-sp-800-218",),
    "DEPABS": ("nist-sp-800-218", "owasp-top-10-2021"),
    "TESTDATA": ("nist-sp-800-218",),
    "RQCA": ("nist-sp-800-218", "owasp-asvs-v5"),
}
_STANDARD_FOCUS_AREAS: dict[str, list[str]] = {
    "nist-csf-2.0": ["govern", "identify", "protect", "detect", "respond", "recover"],
    "nist-ai-rmf-1.0": ["govern", "map", "measure", "manage"],
    "nist-sp-800-218": ["secure design", "secure coding", "verification", "release integrity"],
    "nist-sp-800-53r5": ["security controls", "privacy controls", "continuous monitoring"],
    "nist-sp-800-61r3": ["incident preparation", "detection", "analysis", "containment"],
    "owasp-top-10-2021": ["application risk categories", "common exploit patterns"],
    "owasp-asvs-v5": ["verification requirements", "application security controls"],
    "iso-iec-27001-2022": ["isms governance", "risk treatment", "control assurance"],
    "iso-iec-42001-2023": ["ai governance", "ai lifecycle controls", "assurance process"],
}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _specialty_label(agent: AgentDefinition) -> str | None:
    if not agent.specialties:
        return None
    return _LANGUAGE_LABELS.get(agent.specialties[0], agent.specialties[0].title())


def _job_title_for_agent(agent: AgentDefinition) -> str:
    if agent.short_code in _SHORT_CODE_TITLE:
        return _SHORT_CODE_TITLE[agent.short_code]
    if agent.category == "specialist":
        specialty = _specialty_label(agent) or "Language"
        return f"{specialty} Specialist"
    if agent.category == "pod_manager":
        return f"{agent.pod} Coordination Manager"
    if agent.category == "pod_audit":
        return f"{agent.pod} Audit and Verification Lead"
    return agent.name


def _job_scope_for_agent(agent: AgentDefinition) -> str:
    if agent.short_code in _SHORT_CODE_SCOPE:
        return _SHORT_CODE_SCOPE[agent.short_code]
    if agent.category == "specialist":
        specialty = _specialty_label(agent) or "language"
        return (
            f"Owns {specialty} intent extraction and Refined-IR artifact quality for "
            f"{agent.pod} mission assignments."
        )
    if agent.category == "pod_manager":
        return f"Owns {agent.pod} output fusion and delivery to executive orchestration."
    if agent.category == "pod_audit":
        return f"Owns {agent.pod} verification gates and audit sign-off decisions."
    return "Owns scoped mission outcomes aligned to assigned category responsibilities."


def _education_for_agent(agent: AgentDefinition) -> list[str]:
    entries = list(_CATEGORY_EDUCATION.get(agent.category, []))
    entries.extend(_SHORT_CODE_EDUCATION.get(agent.short_code, []))
    if agent.category == "specialist" and agent.specialties:
        specialty = agent.specialties[0]
        language_label = _LANGUAGE_LABELS.get(specialty, specialty.title())
        entries.append(f"{language_label} language internals and ecosystem best practices.")
        entries.append(_LANGUAGE_GUIDANCE.get(specialty, "Language-specific standards discipline."))
    return _dedupe(entries)


def _traits_for_agent(agent: AgentDefinition) -> list[str]:
    entries = list(_CATEGORY_TRAITS.get(agent.category, []))
    entries.extend(_SHORT_CODE_TRAITS.get(agent.short_code, []))
    if agent.category == "specialist" and agent.specialties:
        specialty = _specialty_label(agent) or "assigned"
        entries.append(f"High-confidence reasoning in {specialty} workloads.")
    return _dedupe(entries)


def _methods_for_agent(agent: AgentDefinition) -> list[str]:
    entries = list(_CATEGORY_METHODS.get(agent.category, []))
    entries.extend(_SHORT_CODE_METHODS.get(agent.short_code, []))
    if agent.category == "specialist" and agent.specialties:
        specialty = agent.specialties[0]
        entries.append(
            _LANGUAGE_GUIDANCE.get(specialty, "Maintain language-specific quality controls.")
        )
    return _dedupe(entries)


def _tools_for_agent(
    agent: AgentDefinition,
    *,
    llm_recommendation: dict[str, Any],
    data_systems: list[dict[str, Any]],
) -> list[str]:
    entries = list(_CATEGORY_TOOLS.get(agent.category, []))
    entries.extend(_SHORT_CODE_TOOLS.get(agent.short_code, []))

    for store in data_systems:
        name = store.get("name")
        status = store.get("status")
        if isinstance(name, str):
            if isinstance(status, str) and status:
                entries.append(f"{name} ({status})")
            else:
                entries.append(name)

    provider = llm_recommendation.get("provider")
    model = llm_recommendation.get("model")
    if isinstance(provider, str) and provider and isinstance(model, str) and model:
        entries.append(f"Primary model route: {provider}/{model}")
    if agent.category == "specialist" and agent.specialties:
        specialty = agent.specialties[0]
        entries.append(_LANGUAGE_TOOLING.get(specialty, "Language tooling references"))
    return _dedupe(entries)


def _default_primary_protocol(agent: AgentDefinition) -> str:
    if agent.category == "interface":
        return "omega"
    if agent.category == "executive":
        return "alpha"
    if agent.category == "pod_manager":
        return "alpha"
    if agent.category == "pod_audit":
        return "delta"
    if agent.category == "specialist":
        return "beta"
    return "rho"


def _protocol_profile(agent: AgentDefinition, protocols: list[str]) -> dict[str, Any]:
    normalized = [str(protocol).strip().lower() for protocol in protocols if str(protocol).strip()]
    primary = _SHORT_CODE_PRIMARY_PROTOCOL.get(agent.short_code)
    if primary is None:
        primary = normalized[0] if normalized else _default_primary_protocol(agent)

    supported = _dedupe(normalized if normalized else [primary])
    supported_codes = [protocol.upper() for protocol in supported]
    return {
        "primary_code": primary.upper(),
        "primary_name": _PROTOCOL_NAMES.get(primary, primary.title()),
        "primary_purpose": _PROTOCOL_PURPOSES.get(primary, "Coordinated inter-agent messaging."),
        "message_format": _PROTOCOL_FORMATS.get(primary, "Structured mission event envelope."),
        "supported_codes": supported_codes,
        "supported_names": [
            _PROTOCOL_NAMES.get(protocol, protocol.title()) for protocol in supported
        ],
    }


def _api_key_env_var(agent: AgentDefinition) -> str:
    normalized = agent.short_code.replace("-", "_")
    return f"{normalized}_API_KEY"


def _cache_hints_for_agent(agent: AgentDefinition) -> list[str]:
    entries = list(_CATEGORY_CACHE_HINTS.get(agent.category, []))
    entries.extend(_SHORT_CODE_CACHE_HINTS.get(agent.short_code, []))
    if agent.category == "specialist" and agent.specialties:
        specialty = agent.specialties[0]
        language_label = _LANGUAGE_LABELS.get(specialty, specialty.title())
        entries.append(
            f"{language_label} language references and upgrade notes"
        )
    return _dedupe(entries)


def _model_routing(llm_recommendation: dict[str, Any]) -> dict[str, Any]:
    route: dict[str, Any] = {
        "provider": str(llm_recommendation.get("provider", "openai")),
        "model": str(llm_recommendation.get("model", "gpt-5.2-pro")),
    }
    mode = llm_recommendation.get("mode")
    if isinstance(mode, str) and mode:
        route["mode"] = mode

    for key in ("reasoning_effort", "thinking_mode", "thinking_budget_tokens", "thinking_level"):
        value = llm_recommendation.get(key)
        if value is not None:
            route[key] = value

    fallback_provider = llm_recommendation.get("fallback_provider")
    fallback_model = llm_recommendation.get("fallback_model")
    if isinstance(fallback_provider, str) and fallback_provider:
        route["fallback_provider"] = fallback_provider
    if isinstance(fallback_model, str) and fallback_model:
        route["fallback_model"] = fallback_model
    return route


def _standards_for_agent(agent: AgentDefinition) -> list[str]:
    selected: list[str] = list(_BASELINE_STANDARD_IDS)
    selected.extend(_CATEGORY_STANDARD_IDS.get(agent.category, ()))
    selected.extend(_SHORT_CODE_STANDARD_IDS.get(agent.short_code, ()))
    return _dedupe(selected)


def _role_mapping_for_standard(agent: AgentDefinition, standard_id: str) -> str:
    if standard_id == "nist-csf-2.0":
        return (
            "Maps this role to CSF 2.0 governance and operational risk functions for "
            "mission-level cybersecurity resilience."
        )
    if standard_id == "nist-ai-rmf-1.0":
        return (
            "Maps this role to AI RMF governance, measurement, and management duties "
            "for trustworthy AI operation."
        )
    if standard_id == "nist-sp-800-218":
        return (
            "Maps this role to SSDF secure software lifecycle practices including "
            "design, implementation, verification, and release controls."
        )
    if standard_id == "nist-sp-800-53r5":
        return (
            "Maps this role to control families supporting security/privacy baselines "
            "for enterprise-grade operations."
        )
    if standard_id == "nist-sp-800-61r3":
        return (
            "Maps this role to incident response readiness, analysis, and coordinated "
            "remediation actions."
        )
    if standard_id == "owasp-top-10-2021":
        if agent.short_code in {"SECURITY", "TESTER"}:
            return (
                "Maps this role to direct detection and prevention of the OWASP Top 10 "
                "web application risk classes."
            )
        return (
            "Maps this role to preventive handling of common web application risks "
            "during design and implementation."
        )
    if standard_id == "owasp-asvs-v5":
        return (
            "Maps this role to ASVS-driven verification depth for application security "
            "requirements and release gates."
        )
    if standard_id == "iso-iec-27001-2022":
        return (
            "Maps this role to ISMS governance, risk treatment, and evidence-oriented "
            "security management."
        )
    if standard_id == "iso-iec-42001-2023":
        return (
            "Maps this role to AI management system responsibilities spanning policy, "
            "risk controls, and continuous assurance."
        )
    return "Maps this role to recognized production security and governance standards."


def _standards_alignment_for_agent(agent: AgentDefinition) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for standard_id in _standards_for_agent(agent):
        source = _STANDARDS_SOURCES.get(standard_id)
        if source is None:
            continue
        records.append(
            {
                "standard_id": standard_id,
                "framework": source["title"],
                "version": source["version"],
                "role_mapping": _role_mapping_for_standard(agent, standard_id),
                "focus_areas": list(_STANDARD_FOCUS_AREAS.get(standard_id, [])),
            }
        )
    return records


def _evidence_sources_for_agent(agent: AgentDefinition) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for standard_id in _standards_for_agent(agent):
        source = _STANDARDS_SOURCES.get(standard_id)
        if source is None:
            continue
        entries.append(
            {
                "source_id": source["source_id"],
                "title": source["title"],
                "organization": source["organization"],
                "version": source["version"],
                "url": source["url"],
                "last_verified": source["last_verified"],
                "applicability": _role_mapping_for_standard(agent, standard_id),
            }
        )
    return entries


def _master_instruction(
    agent: AgentDefinition,
    *,
    protocols: list[str],
    llm_recommendation: dict[str, Any],
) -> str:
    provider = str(llm_recommendation.get("provider", "openai"))
    model = str(llm_recommendation.get("model", "gpt-5.2-pro"))
    protocol = _protocol_profile(agent, protocols)["primary_code"]

    if agent.category == "specialist":
        specialty = _specialty_label(agent) or "assigned language"
        return (
            f"You are {agent.agent_id}, the {specialty} specialist for {agent.pod}. "
            f"Convert source patterns into Refined-IR semantics without language leakage, "
            f"submit audit-ready artifacts with traceability, and escalate uncertainty via "
            f"protocol {protocol}. Use {provider}/{model} for deep extraction accuracy."
        )
    if agent.category == "pod_manager":
        return (
            f"You are {agent.agent_id}, the synthesis manager for {agent.pod}. "
            f"Merge specialist outputs into a coherent group standard, remove duplicate logic, "
            f"and publish only validated pod artifacts to executive orchestration via protocol "
            f"{protocol}. Maintain deterministic, standards-first decision making."
        )
    if agent.category == "pod_audit":
        return (
            f"You are {agent.agent_id}, the audit gate for {agent.pod}. "
            f"Run strict verification, reject artifacts that fail tolerance thresholds, and "
            f"return actionable remediation evidence through protocol {protocol}. "
            f"Correctness is non-negotiable."
        )
    if agent.short_code == "PM":
        return (
            "You are the user-intent guardian. Translate ambiguous human requests into precise "
            "mission contracts, preserve UX intent through delivery, and communicate progress "
            "clearly across the multi-agent pipeline."
        )
    if agent.short_code == "CEO":
        return (
            "You are the global orchestrator. Decompose mission scope, assign pod workloads, "
            "resolve cross-pod dependencies, and enforce end-to-end delivery quality with "
            "stateful governance."
        )
    if agent.short_code == "BROKER":
        return (
            "You are the traffic control authority. Keep all provider routes healthy, enforce "
            "key isolation and rate limits, and preserve throughput under load without losing "
            "mission continuity."
        )
    if agent.short_code == "ACCOUNTANT":
        return (
            "You are the budget authority. Track and enforce mission spend in real time, "
            "detect inefficient usage patterns, and protect cost ceilings while keeping "
            "delivery quality intact."
        )
    if agent.short_code == "SECURITY":
        return (
            "You are the security gate. Assume hostile conditions, surface exploitable risk "
            "early, and block unsafe artifacts until remediated with verifiable evidence."
        )
    if agent.short_code == "IS":
        return (
            "You are the knowledge authority. Keep standards fresh, index technical changes, "
            "and broadcast high-value updates that prevent stale implementation decisions."
        )
    if agent.short_code == "VC":
        return (
            "You are the provenance controller. Keep mission changes reversible, traceable, "
            "and aligned with commit quality and release hygiene standards."
        )
    if agent.short_code == "COMPLIANCE":
        return (
            "You are the policy and licensing gate. Enforce attribution, compatibility, and "
            "legal safety requirements before release progression."
        )
    if agent.short_code == "HW":
        return (
            "You are the hardware optimization lead. Tune workloads for local host constraints, "
            "resolve performance bottlenecks, and maximize stable throughput."
        )
    if agent.short_code == "TESTER":
        return (
            "You are the adversarial systems tester. Break assumptions with integration tests, "
            "quantify failure risk, and block release on unresolved critical defects."
        )
    if agent.short_code == "DEPLOY":
        return (
            "You are the release operator. Convert validated artifacts into reproducible "
            "deployments, enforce rollout safety checks, and prepare rollback paths."
        )
    if agent.short_code == "DEPABS":
        return (
            "You are the dependency absorption authority. Default is ABSORB unless KEEP is "
            "justified against the safety block list. Extract intent, prove equivalence through "
            "shadow comparison, eliminate the dependency, and emit a signed SBOM delta."
        )
    if agent.short_code == "TESTDATA":
        return (
            "You are the test environment operator. Provision isolated per-mission databases, "
            "generate schema-valid synthetic data, validate migration-framework correctness, "
            "and tear down all state cleanly after mission completion."
        )
    if agent.short_code == "RQCA":
        return (
            "You are the runtime QC authority. Launch the built application in a sandboxed "
            "environment, walk the golden path, capture all failures as structured evidence, "
            "and block mission promotion when critical runtime defects are found."
        )
    return (
        f"You are {agent.agent_id}. Execute {agent.role.lower()} responsibilities with "
        f"deterministic quality controls and protocol-aware coordination."
    )


def build_agent_persona_profile(
    agent: AgentDefinition,
    *,
    protocols: list[str],
    llm_recommendation: dict[str, Any],
    data_systems: list[dict[str, Any]],
) -> dict[str, Any]:
    protocol = _protocol_profile(agent, protocols)

    return {
        "job_role": {
            "title": _job_title_for_agent(agent),
            "primary_function": agent.role,
            "scope": _job_scope_for_agent(agent),
        },
        "education_certifications": _education_for_agent(agent),
        "traits_skills": _traits_for_agent(agent),
        "methods_procedures": _methods_for_agent(agent),
        "tools": _tools_for_agent(
            agent,
            llm_recommendation=llm_recommendation,
            data_systems=data_systems,
        ),
        "master_instruction": _master_instruction(
            agent,
            protocols=protocols,
            llm_recommendation=llm_recommendation,
        ),
        "protocol": protocol,
        "api_configuration": {
            "api_key_env_var": _api_key_env_var(agent),
            "api_slot_id": f"{agent.agent_id}-API-KEY",
            "context_window_tokens": 1_000_000,
            "cached_content": _cache_hints_for_agent(agent),
            "model_routing": _model_routing(llm_recommendation),
        },
        "standards_alignment": _standards_alignment_for_agent(agent),
        "evidence_sources": _evidence_sources_for_agent(agent),
    }
