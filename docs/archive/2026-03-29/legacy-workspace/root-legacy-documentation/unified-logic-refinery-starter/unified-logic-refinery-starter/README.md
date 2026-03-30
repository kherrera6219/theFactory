# Unified Logic Refinery — Starter Repo

This is a **starter scaffold** generated from `BLUEPRINT_SPEC.md` (v1.0.0).

## What’s included
- JSON Schemas for:
  - LogicNode (`schemas/logicnode.schema.json`)
  - Refined-IR module (`schemas/rir.module.schema.json`)
  - Refined-IR function (`schemas/rir.fn.schema.json`)
  - Semantic Bus event envelope (`schemas/event.envelope.schema.json`)
- Topic catalog (`protocol/topics.yaml`)
- SQLite ledger schema (`ledger/schema.sql`)
- Docker Compose topology (`deploy/docker-compose.yaml`)
- Placeholders for orchestrator + dashboard services (`services/*`)
- Minimal Makefile + scripts

## Quick start (local)
```bash
docker compose -f deploy/docker-compose.yaml up -d --build
```

## Notes
This scaffold is intentionally minimal: it gives you **contracts + topology** and leaves implementation for agents/orchestrator up to you.

Generated: 2026-01-29
