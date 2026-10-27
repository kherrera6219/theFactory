# License Strategy

Document version: 2026.10.26
Last updated: 2026-10-26
Status: Canonical
Audience: Maintainers, contributors, partners, evaluators, legal review

theFactory is fully open source under the permissive [MIT License](../LICENSE).

---

## Current State

The repository's root `LICENSE` file contains the standard, unmodified MIT License text.

Under the MIT License, anyone is granted permission, free of charge, to:
- **Use**: Run theFactory for personal, academic, research, internal organizational, or commercial purposes without licensing fees.
- **Modify**: Freely adapt, refactor, extend, or build derivative works on top of the codebase.
- **Distribute & Sublicense**: Share, publish, redistribute, or embed the software in proprietary or commercial offerings.
- **No Network Copyleft**: Unlike copyleft licenses (e.g. GPL, AGPL), the MIT License does not require source code disclosure when running the software as a networked service or SaaS.

The only condition is that the copyright notice and permission notice are included in all copies or substantial portions of the Software.

---

## Third-Party Licenses

theFactory depends on a set of third-party open-source components (FastAPI, Next.js, Redis, PostgreSQL, Qdrant, SeaweedFS, etc.). Their respective open-source licenses apply independently. Automated SBOM generation (SPDX and CycloneDX) and license-compliance scanning in CI ensure that transitive dependencies remain compliant with permissive open-source guidelines.

---

## Trademark and Naming

The MIT License grants copyright permissions to the code and documentation; it does not grant trademark rights. The name "theFactory", "Holy Grail Refinery", and any associated logos are reserved project identifiers. Forks and independent distributions should not represent themselves as the official upstream theFactory release.
