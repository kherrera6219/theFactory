# License Strategy

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Maintainers, contributors, partners, evaluators, legal review

This document was rewritten on 2026-07-03 — the previous version asserted the repository's `LICENSE` file was MIT and described a forward-looking "open-core" plan built on that premise. Neither was accurate: the repository is dual-licensed under AGPL-3.0 (non-commercial) or a separate Commercial License, has been since before this document's prior version was written, and already requires a signed CLA for all contributions.

## Current State

The repository's root `LICENSE` file is a **dual license**:

- **Option A — AGPL-3.0**: for open-source, non-commercial, personal, academic, or research use only. Requires publishing modifications and, if the software is run as a networked/hosted service, making the complete corresponding source available to users of that service (the AGPL network-use clause).
- **Option B — Commercial License**: required for commercial use, SaaS/hosted deployment to third parties, internal enterprise deployment, building proprietary products on top of theFactory, or any use where you don't want AGPL-3.0's copyleft/source-disclosure obligations. Contact `kherrera3250@gmail.com` to obtain one.

If unsure which applies, AGPL-3.0 is the default; commercial/enterprise use requires contacting the copyright holder first.

## Patent Notice

The `LICENSE` file also carries a patent notice: the architecture and methods embodied in this software (the task-activated multi-agent orchestration model, the 6-protocol typed event bus routing system, the LogicNode concept-extraction pipeline, the dependency-absorption enforcement system, the 41-agent persona-bound LLM routing model, and the mission-lifecycle chain-of-custody audit system) are the subject of a pending patent application. Neither license option grants any patent rights without a separate written patent license agreement.

## Contributor License Agreement (CLA)

Unlike a "may be added later" open-core plan, a CLA is **already mandatory today**. Every contributor must sign the CLA in [`CLA.md`](../CLA.md) before a pull request can be accepted — this is stated in the `LICENSE` file itself and in [`CONTRIBUTING.md`](../CONTRIBUTING.md).

## Third-Party Licenses

theFactory depends on a substantial set of third-party packages (FastAPI, Next.js, Redis, PostgreSQL, Qdrant, etc.). Their own licenses apply to those components independently of theFactory's own dual license. License-compliance scanning for dependencies is part of CI (see the security workflow in `.github/workflows/`).

## Trademark and Naming

The dual license grants copyright/patent-adjacent permissions as described above; it does not grant trademark rights. The names "theFactory" and any associated logos are reserved. Forks and derivatives distributed under the AGPL-3.0 option must retain the license text and copyright/patent notices, and should not represent themselves as the official theFactory project.

## If You're Evaluating This Repository

- Read the actual `LICENSE` file at the repository root — it is the authoritative source, not this document.
- If you plan any commercial, SaaS, or internal-enterprise use, contact the copyright holder before proceeding rather than assuming AGPL-3.0 terms are sufficient.
- If you plan to contribute, read and sign `CLA.md` first.
