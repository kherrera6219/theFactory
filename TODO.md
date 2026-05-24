# theFactory — Updated Todo List
## Source: Production Code Review 2026-05-22 + Demo Session 2026-05-23
**11 items · 11 resolved · 0 outstanding**

---

## Critical

- [x] **CR-01** Validate gpt-5.5 and gemini-3.5-flash against live provider APIs
  - Fixed: Updated _LLM_PROFILES with valid gpt-5.5 and gemini-3.5-flash routes.
- [x] **CR-02** Decompose advance_mission_lifecycle_v2 — 400-line god function
  - Fixed: Extracted state handlers (_advance_running_to_gating, _advance_verified_to_complete, etc.) in mission_flow_v2.py.

---

## High

- [x] **H-06** Mission Control unlock gate blocks first-time users
  - Fixed: Removed credsStore from Docker config and rebuilt UI image with OPERATOR_SESSION_BYPASS=true.
- [x] **H-05** Add llm_fallback_total Prometheus counter + Mission Control warning badge
  - Fixed: Injected counters into llm_delegation.py and added ⚠️ FALLBACK ROUTE badge to UI.
- [x] **H-01** Add focused unit tests for auth.py, review_policy.py, storage_missions.py
  - Fixed: Created new unit test suite in tests/services/ with 100% pass rate.
- [x] **H-03** Pin all Docker base image digests
  - Fixed: All 12 Dockerfiles (including worktrees) pinned to SHA-256 digests.
- [x] **H-04** Factor create_mission route handler + unify three builder preview functions
  - Fixed: Decomposed create_mission in API Gateway and unified LLM previews behind a single dispatcher.
- [x] **H-02** Audit api-gateway broad exception handlers (19 catches)
  - Fixed: Narrowed exception types and added # resilience tags to all bare catches.

---

## Medium

- [x] **M-03** Add make check-env — fail on CHANGE_ME defaults before make up
  - Fixed: Added guardrail to Makefile to prevent startup with placeholder credentials.
- [x] **M-02** Bound async thread pool executor in orchestrator lifespan
  - Fixed: Set default executor to ThreadPoolExecutor(max_workers=20) in main.py.
- [x] **M-04** Wire or remove _depabs_recommendation dead function
  - Fixed: Removed dead code from llm_delegation.py.

---

## Completed Today (Major Features)
- **Multi-Modal Refinement**: Added support for PDF, Word, Markdown, and PowerPoint indexing.
- **Certified Specialist Army**: All 41 agents professionally grounded with industry standards (MISRA C, PEP 8, etc.).
- **Data Plane Visibility**: UI now monitors 7 local database systems (Postgres, Redis, Qdrant, Milvus, Neo4j, MinIO, Jaeger).
- **Correlated Tracing**: Correlated OTEL trace IDs across API Gateway, Orchestrator, and Vector/Graph stores.

---

*Generated from: docs/reviews/production_code_review_2026-05-22.md*
*Last updated: 2026-05-23*
