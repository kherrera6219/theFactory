# License Strategy

Document version: 2026.04.25
Last updated: 2026-04-25
Status: Canonical (Strategy)
Audience: Maintainers, contributors, partners, evaluators, legal review

This document records the licensing strategy for theFactory. It resolves the ambiguity that existed in earlier README assertions of "proprietary" while the repository's `LICENSE` file is in fact MIT.

## Table of Contents

- [Current State](#current-state)
- [Resolution](#resolution)
- [Open-Core Strategy](#open-core-strategy)
- [What Stays Open](#what-stays-open)
- [What Becomes Commercial](#what-becomes-commercial)
- [Contribution Implications](#contribution-implications)
- [Trademark and Naming](#trademark-and-naming)
- [Third-Party Licenses](#third-party-licenses)
- [Pending Actions](#pending-actions)

---

## Current State

The repository's `LICENSE` file at the repository root is MIT:

> MIT License — Copyright (c) 2026 Kevin Eloy Herrera

The README badge previously asserted "license: proprietary," which contradicts the actual license file. This document and the README update accompanying it resolve that contradiction in favor of the actual `LICENSE` file: MIT.

**Effective state:** the repository contents covered by `LICENSE` are MIT-licensed.

## Resolution

For anyone reviewing or evaluating the project:

1. Treat the repository's `LICENSE` file as authoritative
2. The MIT license applies to all code, schemas, and documentation in the repository unless a directory or file explicitly states otherwise
3. Future commercial editions (see below) will be released as separate distributions, not by re-licensing this repository

If a contributor or partner relied on the previous "proprietary" statement, they should review their use under MIT terms instead. MIT is permissive and broadly compatible with commercial use, modification, and redistribution provided the copyright notice and license text are retained.

## Open-Core Strategy

theFactory adopts an **open-core** strategy:

- **Core (open):** the runtime services, agent registry, mission lifecycle, language extraction, semantic bus, builder/repo review, and the documentation that describes them. All under MIT.
- **Commercial (separate):** advanced enterprise capabilities (multi-tenancy, approved-dependency registry, advanced compliance reporting, air-gapped deployment hardening, premium runtime QC features, support and SLA) shipped as separately-licensed distributions.

This approach is patterned on widely-adopted open-core projects in the developer-tools and infrastructure space. It permits broad community adoption while preserving the option to fund continued development through commercial editions.

## What Stays Open

The MIT-licensed core includes, at minimum:

- API gateway, orchestrator, pod workers, audit worker, semantic bus MCP, dashboard
- The 38-agent registry and persona definitions
- Mission lifecycle (Mission Flow v2 and any successor default lifecycles)
- Language extraction engine and the concept catalog
- Refined IR foundation
- Builder and repo-review approval flow
- Mission Control operator UI
- Schemas under `/schemas/`
- Canonical documentation under `/docs/`
- Test suites and CI workflows
- Local-first deployment via Docker Compose

All current code in the repository at the time of this document's publication is MIT.

## What Becomes Commercial

Capabilities planned for commercial editions (these may live in separate repositories or be shipped under different license terms):

- Multi-tenant SaaS hosting and management plane
- Enterprise SSO connectors (SAML, SCIM provisioning)
- Approved-dependency registry with policy enforcement
- Advanced compliance reporting (SOC 2, ISO 27001, FedRAMP, PCI evidence packs)
- Air-gapped deployment automation and signed update channels
- Premium runtime QC (mobile emulators, advanced computer-use validation)
- Long-term support and incident-response SLAs
- Customer success and managed onboarding

These capabilities are forward-looking. They are not present in the repository today, and their inclusion in the repository in any form will be governed by additional license notices at the time they are added.

## Contribution Implications

Under MIT:

- Contributions to the core are accepted under MIT (matching the project license)
- Contributors retain copyright in their contributions; the license grants the project broad permission
- A formal Contributor License Agreement (CLA) or Developer Certificate of Origin (DCO) may be added later if commercial editions require it; this document does not impose one today
- Contributors should not include third-party code under copyleft licenses (GPL, AGPL, LGPL) without explicit maintainer review

## Trademark and Naming

The MIT license grants copyright permissions; it does not grant trademark rights. The names "theFactory", "Holy Grail Refinery", and any associated logos are not licensed under MIT and remain reserved.

Forks and derivatives must:

- Retain the MIT copyright notice and license text
- Use distinct names and branding for derived products
- Not represent themselves as the official theFactory project

## Third-Party Licenses

theFactory depends on a substantial set of third-party packages (FastAPI, Next.js, Redis, PostgreSQL, Qdrant, etc.). Their licenses apply to those components. Aggregate license inventories are produced as part of CI (see the security workflow).

Copyleft licenses (GPL, AGPL, LGPL) are blocked from inclusion in the core by the CI license-scan gate. Permissive licenses (MIT, Apache 2.0, BSD, ISC, MPL-2.0 file-level) are permitted.

## Pending Actions

1. Update the README license badge from "proprietary" to "MIT" (companion change to this document)
2. Confirm no documentation outside this file still asserts a "proprietary" stance
3. Schedule a commercial-edition planning ADR for when the first commercial capability is ready
4. Decide on CLA or DCO requirement when commercial editions begin

These pending actions are tracked in the project roadmap. None are blockers for the open core; they are administrative follow-ups.
