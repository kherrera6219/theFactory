<div align="center">

# 🏭 theFactory

**An AI software factory — not a code-completion tool.**

*theFactory is a local-first, event-driven AI software factory for building, modernizing, debugging, securing, porting, validating, and optimizing applications through task-activated specialist agents, multi-provider model routing, dependency absorption, isolated workspaces, ephemeral runtime test environments, AI runtime QC, and audit-ready evidence.*

[![CI](https://github.com/kherrera6219/theFactory/actions/workflows/ci.yml/badge.svg)](https://github.com/kherrera6219/theFactory/actions/workflows/ci.yml)
[![Security](https://github.com/kherrera6219/theFactory/actions/workflows/security.yml/badge.svg)](https://github.com/kherrera6219/theFactory/actions/workflows/security.yml)
[![Coverage Gate](https://img.shields.io/badge/coverage%20gate-80%25%2B-blue)](docs/TESTING_QUALITY_GATES.md)
[![Audit](https://img.shields.io/badge/repo%20audit-hygiene%20script-blue)](scripts/production_review_audit.py)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](apps/mission-control/package.json)
[![License](https://img.shields.io/badge/license-AGPL--3.0%20%2F%20Commercial-blue)](LICENSE)

</div>

> **Version:** 1.3.0 · **Last updated:** 2026-08-21 · **Status:** Active development — feature-complete against the v1.3 mission-pipeline scope
>
> **Development status:** the infrastructure, security model, protocol bus, data plane, operator UI, and test surface are mature and CI-verified. Live BUILD_NEW missions have reached `COMPLETE` (Go S1-01, chat-driven PyQt6, stdlib Snake). Default LLM route is **Gemini 3.7 Flash**. Runtime QC runs generated tests when they exist; a bare launch (`started_only`) or syntax-only compile is **ADVISORY**, never a PASS.
>
> **Recent on `main` (2026-08-21/22):** Project continuity bus (`projects` / `project_handoff` / `project_work_items`, migration `V010`) so follow-on missions resume shared project state instead of starting blank — see [`docs/PROJECT_CONTINUITY_BUS.md`](docs/PROJECT_CONTINUITY_BUS.md). Repo ZIP import Phases 5–7 (launch index guard, knowledge ingestion, agent context load) are implemented and the Chat UI trigger seam is closed — see [`docs/evidence/repo_zip_phases_5_7_verification_20260821.md`](docs/evidence/repo_zip_phases_5_7_verification_20260821.md). Ordered remaining work lives in [`docs/WORK_QUEUE.md`](docs/WORK_QUEUE.md).
>
> The **semantic engine is partially realised**: LogicNodes carry AST-recovered types, Refined-IR carries real op streams and side-effect-derived purity, and behavioural equivalence executes generated code in a hardened sandbox — but type recovery is real only for **Python, Java, and Haskell**. Other languages produce honestly-labelled templated output. BUILD_NEW is a sequential specialist prompt-chain, not a four-pod fan-out.
>
> Deliberately **not** built, by recorded decision: the four-pod parallel comprehension model, the Doc 30 LogicNode Registry, binary/LLVM output, and the 0.0001% equivalence tolerance. Per-area verdicts are in [`docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md`](docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md).
>
> **Not production-ready.** PORT-through-SOW, fail-QC-blocks-COMPLETE, failure injection, provider fallback, EDCP live-bus, spend-cap pause, and Chat ZIP import are recorded ([`docs/evidence/end_state_live_proof_20260817.json`](docs/evidence/end_state_live_proof_20260817.json), [`docs/evidence/remaining_live_proof_20260817.json`](docs/evidence/remaining_live_proof_20260817.json)). Sandbox `docker.sock` lives on `sandbox-runner`. See [`docs/WORK_QUEUE.md`](docs/WORK_QUEUE.md).


---

## Table of Contents

SEE_FULL_FILE_IN_NEXT_CALL
