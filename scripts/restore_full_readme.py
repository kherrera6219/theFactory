#!/usr/bin/env python3
"""Restore long-form README from commit ce9e042 and apply 2026-08-21 status patches."""
from __future__ import annotations

import subprocess
from pathlib import Path

COMMIT = "ce9e04234b3dd7aaaaceb94fda84767da2c42df5"


def main() -> None:
    orig = subprocess.check_output(["git", "show", f"{COMMIT}:README.md"], text=True)
    text = orig

    text = text.replace(
        "> **Version:** 1.3.0 · **Last updated:** 2026-08-18 · **Status:** Active development — feature-complete against the v1.3 mission-pipeline scope\n",
        "> **Version:** 1.3.0 · **Last updated:** 2026-08-21 · **Status:** Active development — feature-complete against the v1.3 mission-pipeline scope\n",
        1,
    )

    insert_recent = (
        "> **Development status:** the infrastructure, security model, protocol bus, data plane, operator UI, and test surface are mature and CI-verified. Live BUILD_NEW missions have reached `COMPLETE` (Go S1-01, chat-driven PyQt6, stdlib Snake). Default LLM route is **Gemini 3.7 Flash**. Runtime QC runs generated tests when they exist; a bare launch (`started_only`) or syntax-only compile is **ADVISORY**, never a PASS.\n"
        ">\n"
        "> **Recent on `main` (2026-08-21/22):** Project continuity bus (`projects` / `project_handoff` / `project_work_items`, migration `V010`) so follow-on missions resume shared project state instead of starting blank — see [`docs/PROJECT_CONTINUITY_BUS.md`](docs/PROJECT_CONTINUITY_BUS.md). Repo ZIP import Phases 5–7 (launch index guard, knowledge ingestion, agent context load) are implemented and the Chat UI trigger seam is closed — see [`docs/evidence/repo_zip_phases_5_7_verification_20260821.md`](docs/evidence/repo_zip_phases_5_7_verification_20260821.md). Ordered remaining work lives in [`docs/WORK_QUEUE.md`](docs/WORK_QUEUE.md).\n"
        ">\n"
    )
    old_dev = (
        "> **Development status:** the infrastructure, security model, protocol bus, data plane, operator UI, and test surface are mature and CI-verified. Live BUILD_NEW missions have reached `COMPLETE` (Go S1-01, chat-driven PyQt6, stdlib Snake). Default LLM route is **Gemini 3.7 Flash**. Runtime QC runs generated tests when they exist; a bare launch (`started_only`) or syntax-only compile is **ADVISORY**, never a PASS.\n"
        ">\n"
    )
    if old_dev not in text:
        raise SystemExit("dev-status block not found")
    text = text.replace(old_dev, insert_recent, 1)

    marker = "- **Observability & Data Plane** — Complete integration across PostgreSQL, Redis, Qdrant, Milvus, Neo4j, MinIO, Jaeger OTLP, Prometheus, Grafana, Loki, and Alertmanager.\n"
    extra = marker + (
        "- **Project Continuity Bus** — Durable `projects`, `project_handoff`, and `project_work_items` (migration `V010`) so a follow-on mission can resume the same project's handoff, work ledger, and plan authority instead of a blank slate. Intake ensures the bus; delivery finalizes claimed work items only with evidence. Foundation on `main`; Mission Control project detail UI and public work-item APIs remain follow-ups ([`docs/PROJECT_CONTINUITY_BUS.md`](docs/PROJECT_CONTINUITY_BUS.md)).\n"
        "- **Repo ZIP Import Knowledge Path (Phases 5–7)** — Chat/Repo launch arms `metadata.repo_import` (`index_required`, `index_status: pending`). Phase 5 blocks PM intake until indexing completes. Phase 6 ingests bounded manifest/summary/chunk knowledge via `POST /api/repo/index` → orchestrator `/internal/missions/{id}/repo-import-index`. Phase 7 loads repository context into PM and pod-worker prompts. UI trigger seam closed 2026-08-21.\n"
    )
    if marker not in text:
        raise SystemExit("overview marker not found")
    text = text.replace(marker, extra, 1)

    old_repo = "| Repo Import | Local ZIP import, archive-hash review gate, launch-time approval verification, and mission scoping with bundled source context |"
    new_repo = "| Repo Import | Local ZIP import, archive-hash review gate, launch-time approval verification, mission scoping, and Phase 5–7 index path (launch guard → knowledge ingestion → agent context) |"
    if old_repo not in text:
        raise SystemExit("repo import row not found")
    text = text.replace(old_repo, new_repo, 1)

    old_trace = "**Traceability Ledger:** Active runtime ledger tables are Postgres migrations under `services/orchestrator/orchestrator/migrations/` including `V005_project_audit_event_schema.sql`, `V007_llm_usage_ledger_schema.sql`, and `V009_immutable_audit.sql`."
    new_trace = "**Traceability Ledger:** Active runtime ledger tables are Postgres migrations under `services/orchestrator/orchestrator/migrations/` including `V005_project_audit_event_schema.sql`, `V007_llm_usage_ledger_schema.sql`, `V009_immutable_audit.sql`, and `V010_project_continuity_bus.sql` (projects, handoff, work ledger)."
    if old_trace not in text:
        raise SystemExit("traceability line not found")
    text = text.replace(old_trace, new_trace, 1)

    old_val = "**Validation snapshot (2026-08-17):**"
    new_val = "**Validation snapshot (2026-08-21):**"
    if old_val not in text:
        raise SystemExit("validation snapshot date not found")
    text = text.replace(old_val, new_val, 1)

    needle = "Every critical file is floored at **at least 80%** (`rqca_agent` included; `sow_estimator` and `file_tree` gated). Full-dedicated stack rebuilt 2026-08-17; `sandbox-runner` is healthy. Older Phase 13 / non-ASCII smokes remain on disk."
    repl = (
        "Every critical file is floored at **at least 80%**. Full-dedicated stack rebuilt 2026-08-17; `sandbox-runner` is healthy. "
        "**Project continuity bus** landed on `main` (`ce9e042`, 2026-08-22) with migration `V010` and unit tests. "
        "**Repo ZIP Phases 5–7** backend + Chat UI trigger seam verified closed 2026-08-21 "
        "([`docs/evidence/repo_zip_phases_5_7_verification_20260821.md`](docs/evidence/repo_zip_phases_5_7_verification_20260821.md)); WORK_QUEUE item #8 closed."
    )
    if needle not in text:
        raise SystemExit("validation snapshot body not found")
    text = text.replace(needle, repl, 1)

    old_docs = "| [`docs/WORK_QUEUE.md`](docs/WORK_QUEUE.md) | Ordered next work — start here for “what is actually next” |"
    new_docs = (
        "| [`docs/WORK_QUEUE.md`](docs/WORK_QUEUE.md) | Ordered next work — start here for “what is actually next” |\n"
        "| [`docs/PROJECT_CONTINUITY_BUS.md`](docs/PROJECT_CONTINUITY_BUS.md) | Project continuity bus — handoff, work ledger, plan authority across missions |\n"
        "| [`docs/evidence/repo_zip_phases_5_7_verification_20260821.md`](docs/evidence/repo_zip_phases_5_7_verification_20260821.md) | Repo ZIP Phases 5–7 source verification (index guard, ingestion, context, UI seam) |"
    )
    if old_docs not in text:
        raise SystemExit("docs index row not found")
    text = text.replace(old_docs, new_docs, 1)

    old_state = "Current state (2026-08-17): **active development, feature-complete against the\nv1.3 mission-pipeline scope.** Infrastructure, security, the protocol bus, the\ndata plane, the operator UI, and the test surface are mature and CI-verified.\nThe semantic engine is partially realised and honestly labelled. Live BUILD_NEW\nmissions have reached `COMPLETE`. The system is **not production-ready**."
    new_state = "Current state (2026-08-21): **active development, feature-complete against the\nv1.3 mission-pipeline scope.** Infrastructure, security, the protocol bus, the\ndata plane, the operator UI, and the test surface are mature and CI-verified.\nThe semantic engine is partially realised and honestly labelled. Live BUILD_NEW\nmissions have reached `COMPLETE`. Project continuity and the Repo ZIP knowledge\npath are on `main`. The system is **not production-ready**."
    if old_state not in text:
        raise SystemExit("current status intro not found")
    text = text.replace(old_state, new_state, 1)

    old_row = "| **Core Software Engine** | **Complete for v1.3 scope** | Mission Flow v2 default, 41-agent registry, 6 Redis protocols, real AST for Python/JS/TS/Java, regex parsers for Go/Haskell/OCaml/Julia, Helm & GitHub Actions exporters, Gemini 3.7 Flash default route. |\n| **Semantic depth** |"
    new_row = (
        "| **Core Software Engine** | **Complete for v1.3 scope** | Mission Flow v2 default, 41-agent registry, 6 Redis protocols, real AST for Python/JS/TS/Java, regex parsers for Go/Haskell/OCaml/Julia, Helm & GitHub Actions exporters, Gemini 3.7 Flash default route. |\n"
        "| **Project continuity** | **Foundation on `main`** | Migration `V010`, `project_bus` ensure/finalize hooks, unit tests (`ce9e042`). Follow-on missions can resume handoff + work ledger. Project detail UI and public work-item APIs are follow-ups. |\n"
        "| **Repo ZIP knowledge path** | **Phases 5–7 closed** | Launch index guard, knowledge ingestion, agent context load, and Chat UI trigger seam verified 2026-08-21. Optional polish: index-status visibility in UI and live closed-loop proof under `LIVE_STACK_REQUIRED=1`. |\n"
        "| **Semantic depth** |"
    )
    if old_row not in text:
        raise SystemExit("maturity table rows not found")
    text = text.replace(old_row, new_row, 1)

    Path("README.md").write_text(text, encoding="utf-8")
    print(f"wrote README.md chars={len(text)} lines={text.count(chr(10))+1}")


if __name__ == "__main__":
    main()
