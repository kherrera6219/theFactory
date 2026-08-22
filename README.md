<div align="center">

# 🏭 theFactory

**An AI software factory — not a code-completion tool.**

*theFactory is a local-first, event-driven AI software factory for building, modernizing, debugging, securing, porting, validating, and optimizing applications through task-activated specialist agents, multi-provider model routing, dependency absorption, isolated workspaces, ephemeral runtime test environments, AI runtime QC, and audit-ready evidence.*

[![CI](https://github.com/kherrera6219/theFactory/actions/workflows/ci.yml/badge.svg)](https://github.com/kherrera6219/theFactory/actions/workflows/ci.yml)
[![Security](https://github.com/kherrera6219/theFactory/actions/workflows/security.yml/badge.svg)](https://github.com/kherrera6219/theFactory/actions/workflows/security.yml)
[![Coverage Gate](https://img.shields.io/badge/coverage%20gate-80%25%2B-blue)](docs/TESTING_QUALITY_GATES.md)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](apps/mission-control/package.json)
[![License](https://img.shields.io/badge/license-AGPL--3.0%20%2F%20Commercial-blue)](LICENSE)

</div>

> **Version:** 1.3.0 · **Last updated:** 2026-08-21 · **Status:** Active development — feature-complete against the v1.3 mission-pipeline scope
>
> **Development status:** Infrastructure, security, protocol bus, data plane, operator UI, and test surface are mature and CI-verified. Live BUILD_NEW missions have reached `COMPLETE` (Go S1-01, chat-driven PyQt6, stdlib Snake). Default LLM route is **Gemini 3.7 Flash**. Runtime QC runs generated tests when they exist; `started_only` / syntax-only are **ADVISORY**, never a PASS.
>
> **Recent on `main` (2026-08-21/22):**
> - **Project continuity bus** — `projects` / `project_handoff` / `project_work_items` (migration `V010`) so follow-on missions resume shared project state. See [`docs/PROJECT_CONTINUITY_BUS.md`](docs/PROJECT_CONTINUITY_BUS.md).
> - **Repo ZIP Phases 5–7** — launch index guard, knowledge ingestion, agent context load; Chat UI trigger seam closed. See [`docs/evidence/repo_zip_phases_5_7_verification_20260821.md`](docs/evidence/repo_zip_phases_5_7_verification_20260821.md).
>
> Ordered remaining work: [`docs/WORK_QUEUE.md`](docs/WORK_QUEUE.md). **Not production-ready.**

---

## What theFactory Is

theFactory accepts natural-language missions and delivers working software through a governed orchestration pipeline of task-activated specialist agents — requirements, architecture, code, tests, runtime QC, and audit evidence.

It is **not** a single-prompt code-completion tool. Details: [`docs/00_PRODUCT_OVERVIEW.md`](docs/00_PRODUCT_OVERVIEW.md), [`docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md`](docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md).

### Core Doctrines

1. Full software production lifecycles, not single-prompt drops.
2. Agents are task-activated, not a permanent always-on workforce.
3. Dependencies are liabilities until proven necessary.
4. Workspaces are isolated; the factory does not modify source in place.
5. Nothing ships without evidence.
6. Sensitive code stays local.

---

## Mission Lifecycle (At a Glance)

```
PM intake → requirements → architecture → mission plan → agent activation
  → code, docs, tests, build → dependency absorption → isolated workspace
  → disposable test environment → runtime QC → audit evidence → release handoff
```

Default engine: **Mission Flow v2** (11 internal phases). See [`docs/MISSION_FLOW_V2.md`](docs/MISSION_FLOW_V2.md).

---

## Highlights on `main`

| Area | Status |
|------|--------|
| Mission Flow v2 + 41-agent registry + 6 Redis protocols | Shipped |
| Runtime QC (RQCA); FAIL blocks COMPLETE; advisory scopes do not | Shipped |
| Sandbox execution on `sandbox-runner` (not orchestrator `docker.sock`) | Shipped |
| Chat ZIP / Repo Import + Phases 5–7 index path | Shipped (2026-08-21) |
| Project continuity bus (V010) | Foundation on `main` (2026-08-22) |
| Semantic engine (LogicNodes / Refined-IR) | Partial — real types for Python, Java, Haskell |
| BUILD_NEW behavioural equivalence decision | Open — see WORK_QUEUE #7 |
| Electron installer / uninstall | Open — needs operator sign-off |

---

## Quick Start

```bash
cp .env.example .env
# Add provider keys and service secrets
make tls-certs
make up          # full-dedicated topology (default)
# Mission Control: http://localhost:3100
```

Condensed stack: `make up-condensed`. Health: `curl http://localhost:8100/health`.

---

## Services

| Service | Port | Role |
|---------|------|------|
| api-gateway | 8100 | Public API, auth, SSE |
| orchestrator | 8101 | Mission state machine, agents |
| protocol-bus-mcp | 8102 | Six-protocol typed bus |
| mission-control | 3100 | Operator console (Next.js 16) |
| sandbox-runner | — | Isolated code execution |

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [`docs/WORK_QUEUE.md`](docs/WORK_QUEUE.md) | What is actually next |
| [`docs/PROJECT_CONTINUITY_BUS.md`](docs/PROJECT_CONTINUITY_BUS.md) | Cross-mission project handoff + work ledger |
| [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) | Shipped defaults and gaps |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture |
| [`docs/evidence/repo_zip_phases_5_7_verification_20260821.md`](docs/evidence/repo_zip_phases_5_7_verification_20260821.md) | Repo ZIP index path verification |
| [`AGENTS.md`](AGENTS.md) | Guidelines for coding agents |
| [`CHANGELOG.md`](CHANGELOG.md) | Change history |

Full API tables, compose profiles, env reference, and maturity matrix are maintained under `docs/` (especially IMPLEMENTATION_STATUS, ARCHITECTURE, and WORK_QUEUE).

---

## License

AGPL-3.0 with commercial terms — see [`LICENSE`](LICENSE) and [`docs/LICENSE_STRATEGY.md`](docs/LICENSE_STRATEGY.md).

> **Local-first:** designed to run offline. Secrets stay in `.env` and local vault endpoints. Do not commit credentials.
