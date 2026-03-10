# Diagram Standards

Last updated: 2026-03-09

## Purpose

This document defines the minimum diagram set required for theFactory's living documentation.
It aligns enterprise architecture documentation practice with the additional concerns introduced by
multi-agent execution, event choreography, profile-based deployment, and strict service-auth
controls.

## Standards Basis

theFactory uses a pragmatic combination of enterprise architecture and modeling standards:

- ISO/IEC/IEEE 42010 architecture-description practice: architecture documentation should use
  viewpoints that address specific stakeholder concerns.
- C4 model: a small core set of static and dynamic diagrams is usually enough for maintainable
  software architecture documentation.
- arc42: architecture docs should include building-block, runtime, and deployment views.
- OMG UML: sequence and state diagrams are standard notations for dynamic behavior and lifecycle.
- AWS Prescriptive Guidance for multi-agent systems: enterprise multi-agent docs need explicit
  views for orchestration, worker specialization, shared state/memory, and interaction boundaries.

Reference links:

- ISO/IEC/IEEE 42010 overview: https://www.iso.org/standard/74393.html
- C4 model diagrams: https://c4model.com/diagrams
- arc42 building-block view: https://docs.arc42.org/section-5/
- arc42 runtime view: https://docs.arc42.org/section-6/
- arc42 deployment view: https://docs.arc42.org/section-7/
- OMG UML specification portal: https://www.omg.org/spec/UML/
- AWS multi-agent patterns: https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/welcome.html

## Required Diagram Set

| Concern | Diagram Type | Standard Basis | Required for theFactory | Canonical Location |
|---------|--------------|----------------|-------------------------|--------------------|
| External actors, system boundary, upstream/downstream dependencies | System context view | ISO 42010, C4 | Yes | `ARCHITECTURE_DIAGRAMS.md#system-context-view` |
| Major services, responsibilities, and runtime relationships | Container / building-block view | C4, arc42 section 5 | Yes | `ARCHITECTURE_DIAGRAMS.md#container-view` |
| Mission state progression and key runtime events | Lifecycle state view | UML state, arc42 runtime | Yes | `ARCHITECTURE_DIAGRAMS.md#mission-lifecycle-state-view` |
| End-to-end mission execution path | Runtime sequence view | UML sequence, arc42 section 6 | Yes | `ARCHITECTURE_DIAGRAMS.md#mission-runtime-sequence` |
| Agent tiers, delegation, and collaboration structure | Multi-agent topology view | ISO 42010 concern-based viewpoints, AWS multi-agent guidance | Yes | `ARCHITECTURE_DIAGRAMS.md#multi-agent-topology-view` |
| Event streams, persistence, knowledge adapters, and artifact flows | Information / data-plane view | arc42 building-block + runtime | Yes | `ARCHITECTURE_DIAGRAMS.md#data-and-knowledge-plane-view` |
| Deployment modes, overlays, and isolation profiles | Deployment / environment view | C4 deployment, arc42 section 7 | Yes | `ARCHITECTURE_DIAGRAMS.md#deployment-profile-view` |
| Public boundary, auth paths, and internal trust boundaries | Security / trust-boundary view | ISO 42010 stakeholder concerns, enterprise security architecture practice | Yes | `ARCHITECTURE_DIAGRAMS.md#security-and-trust-boundary-view` |

## TheFactory Rules

- Use Mermaid in canonical docs so diagrams stay versioned with code and render in standard
  Markdown tooling.
- Treat the undated docs in `docs/` as living documentation.
- Keep date-stamped ADRs, audits, and evidence files as historical records rather than canonical
  architecture references.
- Update diagrams whenever any of the following change:
  - service inventory
  - public or operator ports
  - mission lifecycle semantics
  - agent registry shape
  - compose profiles or deployment overlays
  - authentication or key-isolation behavior
  - active versus feature-flagged data-plane adapters

## Scope Decisions

The current diagram set does not include service-internal component diagrams for every FastAPI app.
That is deliberate: the repository's primary documentation needs are cross-service architecture,
multi-agent coordination, runtime sequencing, and deployment governance. Component-level diagrams
should be added only when a service's internal structure becomes architecturally significant or too
complex to understand from code and tests alone.
