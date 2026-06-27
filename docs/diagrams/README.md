# theFactory — Architectural Diagrams Directory

Document version: 2026.06.26
Last updated: 2026-06-26
Status: Canonical
Audience: Developers and operators

This directory contains the canonical enterprise architecture diagrams for **theFactory**, aligned with Microsoft Enterprise documentation standards, C4 Modeling, and the arc42 architecture template.

---

## Document Index

For the full detailed documentation covering stakeholder viewpoints, components, data flows, and security guidelines, see the main master document:
👉 **[ENTERPRISE_ARCHITECTURE_DIAGRAMS.md](ENTERPRISE_ARCHITECTURE_DIAGRAMS.md)**

---

## Standalone Diagram Catalog

This directory contains standalone `.mermaid` source files for each viewpoint, allowing modular integration, editing, and version tracking:

1. **[01_system_context.mermaid](01_system_context.mermaid)**: C4 Level 1 diagram illustrating the system boundary, external actors, and public integrations.
2. **[02_container_architecture.mermaid](02_container_architecture.mermaid)**: C4 Level 2 diagram detailing all platform containers, services, and the 7 datastore nodes.
3. **[03_component_orchestrator.mermaid](03_component_orchestrator.mermaid)**: C4 Level 3 diagram showcasing the modules, engines, and storage facade of the Orchestrator.
4. **[04_component_api_gateway.mermaid](04_component_api_gateway.mermaid)**: C4 Level 3 diagram detailing OAuth, OIDC, rate limiting, and SSE controllers in the API Gateway.
5. **[05_component_protocol_bus.mermaid](05_component_protocol_bus.mermaid)**: C4 Level 3 diagram detailing 6-protocol routing, validator schemas, and backpressure in the Protocol Bus.
6. **[06_mission_intake_lifecycle_sequence.mermaid](06_mission_intake_lifecycle_sequence.mermaid)**: Dynamically mapping end-to-end mission launch, review verification, and completion sequence.
7. **[07_agent_hierarchy_delegation.mermaid](07_agent_hierarchy_delegation.mermaid)**: The cognitive topology of the 41-agent hierarchical tiers.
8. **[08_data_information_flow.mermaid](08_data_information_flow.mermaid)**: Storage plane synchronization including relational checkpoints, vector knowledge indexes, graph concept mappings, and S3-offloaded storage.
9. **[09_security_trust_boundaries.mermaid](09_security_trust_boundaries.mermaid)**: Highlighting Mutual TLS links, auth zones, Windows DPAPI keystore, and LLM safety filters.
10. **[10_deployment_infrastructure.mermaid](10_deployment_infrastructure.mermaid)**: Standard docker-compose layout, service profiles (condensed vs. full-dedicated), and environment overlays.

---

## How to View and Edit Diagrams

Mermaid is a Javascript-based diagramming tool that uses text declarations. To view or edit these diagrams:

1. **VS Code**: Install the *Markdown Preview Mermaid Support* or *Mermaid Previewer* extensions.
2. **GitHub**: Standalone `.mermaid` files and embedded code blocks render automatically in markdown.
3. **Mermaid Live Editor**: Copy and paste raw file text into [mermaid.live](https://mermaid.live) to render, customize, or export to PNG/SVG/PDF.

---

## Maintenance Guidelines

As specified in `docs/DIAGRAM_STANDARDS.md`, these diagrams must be kept in sync with the codebase. Update these diagrams immediately if any of the following occur:
- Changes to microservices inventory or host port maps.
- Adjustments to mission state graphs or transitions.
- Modification to the 41-agent registration tiers.
- Alterations in authentication protocols or key protection mechanisms.
