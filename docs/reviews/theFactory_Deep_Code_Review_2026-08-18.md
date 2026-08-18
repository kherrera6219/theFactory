# theFactory — Deep Code Review (Pass 2, Corrected)

**Date:** 2026-08-18
**Target:** `C:\software\Holygrail\theFactory` @ `main`, commit `c1b044f`
**Supersedes:** my 2026-08-18 status review, which was structural and got several things wrong.

### Disposition (2026-08-18, `af88a79`)

Validated against code, then actioned. Electron is **later production work**, not a defect.

| ID | Disposition |
|---|---|
| N1 fallback tests → PASS | **Fixed.** `source=fallback` is ADVISORY. |
| N2 Knowledge Lake overclaim | **Docs restated.** Seed, 4 languages. Ingestion is a product decision. |
| N3 extractor AST docstrings | **Fixed.** |
| N4 PORT / RQCA flag drift | **Fixed.** Python PORT default `true`. `check_env` warns on RQCA `false`. |
| C4 ADR row 17 graph | **Fixed.** Implemented. |
| C1–C3, C5–C6 | Confirmed strengths. No work. |
| Electron | Deferred until the app is production-ready. |

Still open after this review: brownfield import in a non-seeded language; Knowledge Lake content vs rename; BUILD_NEW equivalence (#7); Repo ZIP depth 5–7.

---

## 0. What changed between pass 1 and pass 2

**Pass 1 was not a code review.** I verified that files existed, measured their sizes, grepped for stub markers, read the status documents, and inspected mission outputs. I inferred implementation depth from file names and doc claims. That was the wrong method, and you were right to call it.

**Pass 2 read implementations line by line** — all 9 migrations, the storage layer, the migration runner, `mission_flow_v2` phases (intake/build/runtime/delivery), the LLM generator and fallback layer, `sandbox_exec.py`, `rqca_agent` runtime tables, `refined_ir` projection logic, the pod-worker extractors, `is_agent` / `knowledge_lake`, `equivalence_execution`, the protocol bus server, gateway auth and rate limiting, and the Mission Control routes and graph component. I also **ran the full backend test suite live**.

**Test suite result:** ran to 100%, **exit code 0**, ~2,030 tests, 2 skipped, no failures. Only warnings are a `jsonschema.RefResolver` deprecation in two RIR test files.

Six corrections follow. Five of them are me having understated or misread the system; one is a new defect I found that nobody's status doc mentions.

---

## 1. Corrections to my first report

### C1 — The database layer. You were right; I undersold it badly.

I listed the data plane as "implemented" and moved on. What's actually there:

| Element | What the code does |
|---|---|
| `migrations.py` | Session-level `pg_advisory_lock` so concurrent orchestrator boots serialize instead of racing the `schema_migrations` PK. SHA-256 checksum per migration; a changed applied migration **raises** rather than silently drifting. Connects via `migration_postgres_url`, deliberately bypassing PgBouncer — with a comment explaining that transaction-pool mode reassigns the backend and runs `DISCARD ALL`, silently releasing the advisory lock mid-migration. |
| `storage_core.py` | `psycopg_pool` with `prepare_threshold=None` so named prepared statements can't break under PgBouncer transaction pooling. Documented. |
| V001–V009 | 15 tables, every one with purposeful composite indexes (`(mission_id, created_at DESC)` etc.), FK cascades throughout. |
| V005 | Adds `project_id` with a real backfill (`regexp_replace` slugging from metadata source or mission id), plus `agent_action_events` carrying `prev_event_digest_sha256` → `event_digest_sha256`. |
| V008 | `prune_audit_tables(retention_days)` as `SECURITY DEFINER` plpgsql returning per-table delete counts. The comment explains why `CREATE INDEX CONCURRENTLY` is *not* used (the runner executes each file as one implicit transaction). |
| V009 | Revokes `DELETE` on the compliance tables from the app role, wrapped in a `DO` block that swallows `insufficient_privilege` so a least-privileged migration role doesn't fail boot — with the out-of-band DBA procedure pointed at `OPERATIONS_RUNBOOK.md`. |

And the part I'd single out — `storage_agents.insert_agent_action_event`:

> *"Two concurrent events for the same project_id could both read the same prev_digest and both chain to it, **forking the tamper-evident hash chain with no error**."*

The fix is `pg_advisory_xact_lock(hashtextextended(project_id, 0))` around the read-then-chain critical section. Somebody thought carefully about how a hash chain fails silently under concurrency. That is not typical work.

**Verdict: the database and audit layer is the most mature subsystem in the repo.** My first report treated it as table stakes. It isn't.

### C2 — "SQLite ledger vs Postgres audit chain: still undecided." Wrong.

`ledger/schema.sql` line 1–2:

> *"Legacy SQLite traceability starter schema. Active runtime ledger tables are managed by Postgres migrations in services/orchestrator/orchestrator/migrations."*

The decision is recorded in the file itself. I carried that item forward from the May gap report without opening the file. Nothing is undecided; the file is a labelled historical artifact. It could be deleted, but that's tidying, not a decision.

### C3 — "Route duplication suggests drift." Wrong.

I flagged `logic-nodes/` vs `logicnodes/`, `history/` vs `missions/history/`, `repo/` vs `repo-import/`. Every one is a deliberate five-line alias:

```tsx
import { redirect } from "next/navigation";
export default function HistoryAliasPage() { redirect("/missions/history"); }
```

That's URL-stability hygiene, the opposite of drift. Withdraw the finding.

### C4 — The LogicNode dependency graph is built; the ADR is stale.

`ADR_DESIGN_RECONCILIATION` row 17 lists Doc 15 §3.1's graph as the one genuine deferred UI gap ("no graph library present"). `app/components/logicnode-graph.tsx` exists — 201 lines of hand-rolled SVG with layered left-to-right layout, purity-toned nodes, and this rationale:

> *"Rendered as plain SVG with no graph library. Two reasons: the page runs under a CSP that forbids `unsafe-eval`, which several layout libraries rely on; and the layout this data needs is simple enough that a dependency would cost more than it saves. … when no node carries recovered types there are no edges to draw, and the component explains why instead of rendering a disconnected cloud that reads as a bug."*

The doc is behind the code, in the good direction. Worth updating the ADR so the next reader doesn't re-scope work that's done.

### C5 — `projection_method` is better than documented.

I repeated the docs' framing that `ast_v1` covers "Python, Java, and Haskell" — a language allow-list — and separately noted the README calls Haskell "regex under an AST filename," which looked contradictory.

The code resolves it, and does it better than either doc says. In `refined_ir.py`:

```python
has_signature = bool(types_in or types_out)
```

`projection_method` is derived **per function from whether types were actually recovered**, then rolled up per module to `ast_v1` / `templated_v1` / `mixed_v1`. It is not a language allow-list at all. A Haskell file whose `::` signatures parsed cleanly earns `ast_v1` honestly; one that didn't gets `templated_v1`. And `mixed_v1` exists specifically because *"a file legitimately mixes AST-backed and regex-only extraction, and collapsing that to either extreme would misreport the module."*

That's the correct design. The documentation describes it less accurately than the implementation deserves.

### C6 — "Hardened sandbox" undersold `sandbox_exec.py`.

Every flag in `SANDBOX_SECURITY_FLAGS` carries a written justification, including the one that looks like a relaxation:

> *"`exec` is required, not a relaxation. Docker mounts tmpfs `noexec` by default, and a compiled language has to put its binary somewhere writable and then run it… Every C/C++/Rust run failed — first at link time … and then at exec time (`/tmp/a.out: Permission denied`). Both were verified by hand against `gcc:13-bookworm` and `rust:1.78-slim-bookworm`. … The sample already executes arbitrary code by construction — that is the entire purpose of the sandbox — so denying execution from tmpfs does not remove a capability an attacker lacks, it only removes the ability to compile."*

Plus: sibling-container path translation (`daemon_workspace_path`) because the daemon resolves `--volume` on the *host*, and passing an orchestrator-local temp dir silently mounts an empty directory the daemon helpfully creates; `--entrypoint=sh` normalization because `ocaml/opam` prefixes `opam exec --` and `sbtscala` launches sbt; and `_make_workspace_readable` because `--cap-drop=ALL` removes `CAP_DAC_OVERRIDE` so root becomes subject to the 0700 bits and the compiler reports `Permission denied`, *"which reads like a bug in the generated code rather than a mount-permission problem."*

This is the best-reasoned file in the repository.

---

## 2. The defect I found — and it is the important one

### N1 — The integration-test fallback emits a test that cannot fail, and nothing downstream knows.

Three facts, each individually fine:

1. **Tests are the QC command.** `_select_sandbox_command` prefers the generated test runner over a bare run command. (`CURRENT_TODO`, PR #460.)
2. **`RQCA_ENFORCEMENT_ENABLED=true` blocks only on `qc_verdict == FAIL`,** and `generate_rqca_assessment` sets `PASS` when the sandbox executed with `verified_scope = tests` and exit 0. That function is fully deterministic — it discards its LLM inputs (`_ = mission_id, mission_contract, language`) — which is good, and means it cannot tell *what* the tests asserted.
3. **`_fallback_integration_tests` in `llm_delegation/fallbacks.py`** produces, when the LLM is unreachable:

```python
def test_module_importable():
    """Verify the generated module imports without error."""
    # Adjust import path as needed for your project layout
    assert True, 'Module import check placeholder'
```

and for JS/TS: `expect(true).toBe(true);`

Compose them and you get: **LLM outage → fallback tests → `assert True` → sandbox exit 0 → `verified_scope = tests` → `qc_verdict = PASS` → mission COMPLETE with an evidence bundle.** A check that can never fail, gating delivery. That is precisely the bug class this team has spent months hunting everywhere else — the live suite that exited 0 having verified nothing, Object Lock returning 200 while dropping the report, `started_only` reported as PASS.

**The provenance exists but is not enforced.** `integration_tests.source == "fallback"` is written into the `MISSION_INTEGRATION_TESTS_GENERATED` chain event (`phases_runtime.py:451`, `phases_delivery.py:187`), so an auditor reading the chain afterwards can see it. But I searched every consumer: nothing reads that field to gate a verdict. Compare `route_provenance["fallback_used"]` in `routes/internal.py`, which *does* aggregate fallback usage for delegation — the pattern exists in the codebase, just not on this path.

**You already know the right answer, and it's twelve lines away.** `_fallback_pod_audit_verdict`, in the same file, gets it exactly right:

> *"The LLM could not run the audit, so report `degraded` with `passed=False` rather than granting a fake `PASS`. `advisory=True` keeps the pipeline moving (offline development) while making the bypass visible to operators."*

**Fix:** apply that pattern to the test fallback. Either force `qc_verdict = ADVISORY` when `integration_tests.source == "fallback"` (mirroring how `started_only` and `syntax_only` are already handled in `generate_rqca_assessment`), or make the fallback test skip loudly rather than assert true. The first is cleaner — the ADVISORY branch already exists and already carries `deployment_safe: False`.

This is the single highest-value change available in the repo right now, and it's maybe a twenty-line diff plus a test.

### N2 — The "Knowledge Lake" is a static seed, not a knowledge lake.

I marked gap 3.1 (FETCH / IS Agent / Knowledge Lake) **Closed** in pass 1 on the strength of `is_agent.py` (23 KB), `knowledge_lake.py` (20 KB) and `knowledge_embeddings.py` existing. Reading them:

`is_agent.py` is built around `_BOOTSTRAP_DOCS`, a hardcoded dict of one-line summaries:

```python
("builtins.list", "list: ordered mutable sequence. Methods: append, extend, pop, ...")
("itertools", "itertools: efficient looping. Functions: chain, cycle, repeat, ...")
```

- **Coverage: 4 language keys** — `python` (15 entries), `javascript` (12), `typescript` (5), `java` (10). About 42 one-liners total.
- **`SUPPORTED_LANGUAGES = frozenset(_BOOTSTRAP_DOCS)`** — so Go, Rust, C, C++, C#, Haskell, OCaml, Julia, Scala, Kotlin, Zig, PHP, Ruby, R, MATLAB and Mathematica get **nothing**. `detect_required_languages` filters them out entirely.
- **Zero network code.** I searched `is_agent.py` for `httpx|requests.get|urllib|aiohttp|crawl|llama_index`: **0 matches.** There is no crawler and no LlamaIndex.
- **`get_language_context` caps at `_MAX_CONTEXT_CHARS = 8_000`** against a spec that called for 700K-token cached documentation windows per specialist.
- **`knowledge_lake_refresh_loop`** in `main.py` re-runs `run_fetch_phase` hourly over `SUPPORTED_LANGUAGES` — i.e. a background task whose only effect is to re-hash the same constants and confirm they're unchanged.

To be fair to the code: the *plumbing* is genuinely good. `knowledge_lake.py` documents and fixes a real historical bug (IS-Agent wrote to PostgreSQL while the query layer read from Qdrant — "a separate, never-synced store"). Retrieval is wired into codegen for real: `phases_build.py` calls `knowledge_lake.get_language_context` and injects the result into `_codegen_context["knowledge_context"]`. Attachment ingestion is real. Refresh/hash detection is real.

But the pipe is well-built and nearly empty, and it's empty for 15 of your 19 routed languages. **This is the largest gap between claimed and actual capability in the system**, and unlike everything else in this repo it is *not* flagged in `IMPLEMENTATION_STATUS.md` — that document lists the Knowledge Lake without qualification. The docstring says "Static documentation seed for Phase 8," which is honest, but the honesty didn't propagate up to the status page the way it did for the AST extractors and the RQCA verdicts.

### N3 — Extractor docstrings claim AST; implementations are regex.

`go_ast_extractor.py`:

```python
"""go_ast_extractor.py — Structural AST-based extraction for Go / Systems languages.
- AST-first structural analysis for Go package, import, struct, interface, and method definitions.
- ...zero false-positive function/class structures.
"""
...
pkg_match = re.search(r"^\s*package\s+([A-Za-z0-9_]+)", source, re.MULTILINE)
```

Same shape in `haskell_ast_extractor.py`. The README and `IMPLEMENTATION_STATUS.md` correct this explicitly and prominently ("regex parsers shipped under an AST filename — they are not language ASTs"), which is why I don't rank this high. But a developer who opens the file and reads its docstring is told the opposite of the truth, and the claim "zero false-positive" is not something a regex can support. Fifteen minutes of docstring edits closes it.

### N4 — Python defaults and compose defaults disagree.

`settings.py` has `port_two_phase_enabled: bool = False`. `deploy/docker-compose.yaml:394` has `PORT_TWO_PHASE_ENABLED: ${PORT_TWO_PHASE_ENABLED:-true}`. Your live PORT proof (`mission-dc0c8c4e`) exercised the two-phase path, so the recorded evidence describes the compose default, not the code default.

That's defensible — compose is the shipped product — but it means "what the product does" is spread across two files that can drift, and anyone running the orchestrator outside compose (a test harness, a future embedded mode, a contributor's laptop) silently gets a different product. Worth either aligning the Python defaults to the compose values or adding a startup assertion that logs where each flag's value came from.

*(Related and still open from pass 1: your local `.env` pins `RQCA_ENFORCEMENT_ENABLED=false` against a compose default of `true`.)*

---

## 3. What the code review confirmed as genuinely strong

Beyond the sandbox and the audit chain already covered:

- **CEO routing correction** (`phases_build.py`). The CEO's delegation prompt can route a Python mission to the Pod C manager; nothing downstream reconciles that, so *"a cross-pod choice makes the mission invisible to every worker — Pod A rejects the agent, Pod C rejects the language, and neither logs an error."* The fix prefers the registry when it has an opinion and **records the correction** in `pod_manager_routing_correction` rather than silently discarding the CEO's answer. `_language_pod_manager_agent_id` returns `None` for unknown languages precisely so the check can't "correct" everything back to Pod A.
- **PORT two-phase re-entrancy guard.** The extraction branch had no guard because mission state stays at `specialist_assigned` across both phases — *"it would re-run two LLM calls, mint a fresh non-deterministic port_source_aim, and append a duplicate event."* Now guarded on `MISSION_PORT_EXTRACTION_COMPLETE`.
- **QC cache staleness.** `_cached_runtime_qc_is_stale` re-assesses stored reports whose `verified_scope_detail == "started_only"`, so PASS verdicts minted by older, less honest builds don't survive into new runs.
- **Spend cap actually blocks.** `_prepare_runtime_qc` computes real usage from `llm_cost_ledger`, compares to the SOW cap, and returns `ready=False` on `pause`. Not a dashboard number.
- **Equivalence honesty is structural.** In `equivalence_execution._classify`, a vector with `expected is None` can only ever reach `executed_without_error` — `passed` is unreachable for it. *"Counting 'it ran without crashing' as equivalence would recreate exactly the 'check that can never fail' problem this phase exists to remove."* (Which makes N1 all the more worth fixing — the principle is stated verbatim, ten files away.)
- **Fusion dedup key.** `generate_master_logic_stream`'s deterministic fallback dedups on `(domain, concept)`, with a comment that keying on bare `concept` "lost real cross-domain nodes." `MAX_FUSION_NODES` replaced hardcoded `[:20]`/`[:10]` slices that "silently dropped real nodes."
- **DEPABS execution is real.** Not just a classifier: `execute_absorption` returns `modified_source`, `build_sbom_delta` computes `reduction_percent`, and on `absorption_count > 0` the absorbed source **becomes** `generated_output` and gets repackaged as a build artifact.
- **Protocol bus.** Strict Pydantic (`extra="forbid"`, `strict=True`) per lane; production **raises** on missing `MCP_API_KEY` with the reasoning spelled out (auto-generation "changes on every container restart, silently breaking all clients"); per-agent HMAC with a documented env-var derivation; dedup, replay rejection, backpressure at 10k, DLQ, Prometheus counters for each.
- **Gateway.** `PROMPT_GUARD_MODE` defaults to `block`, not `log`, with the reasoning recorded. Split read/write rate buckets (600 read / 120 write) fixing the one-open-tab-429s-everyone bug. HMAC'd rate-limit keys. Auth-failure metrics labelled by reason.
- **`PM_AUTO_ACCEPT_DEFAULTS_ENABLED` comment**, which I'd frame and hang on a wall: *"Defaults true: the alternative is not a safe default but a broken one — it parked 100% of missions."*

Route surface: 39 gateway + 56 orchestrator + 6 bus = **101 routes**. Mission Control: 22 pages, 39 lib modules, 31 test files.

---

## 4. Revised scorecard

| Subsystem | Pass 1 | Pass 2 (after reading code) |
|---|---|---|
| Database / migrations / audit chain | "implemented" | **Materially exceeds spec.** Best-in-repo. |
| Sandbox isolation | "hardened" | **Exceptional.** Every flag justified and field-verified. |
| Mission lifecycle (v2) | "real" | **Real and defensively written**, with recorded corrections for its own failure modes. |
| Cognition / prompt layer | "closed" | **Closed.** 12 versioned assets, deterministic fallbacks throughout. |
| DEPABS | "closed (opt-in)" | **Closed, deeper than stated** — real source rewriting + SBOM delta. |
| Refined-IR projection labelling | "closed" | **Better than documented** — per-function derivation, not a language list. |
| Equivalence verification | "Python only, advisory" | **Confirmed, and structurally honest.** |
| RQCA verdict logic | "closed and hardened" | **Confirmed** — but see N1. |
| Knowledge Lake / FETCH | **"Closed"** | **Overclaimed.** Static 42-entry seed, 4 languages, no crawler. |
| Protocol bus | "closed" | **Confirmed, exceeds spec.** |
| Mission Control | "22 routes, some drift" | **No drift.** Aliases are deliberate. Graph is built. |
| Test suite | "1,769 test fns claimed" | **Verified live: ~2,030 tests, exit 0.** |

---

## 5. Revised recommendations, in order

1. **Fix N1.** Make `qc_verdict` ADVISORY when `integration_tests.source == "fallback"`, or stop the fallback emitting `assert True`. Twenty lines. This is a delivery gate that can currently pass on a test that cannot fail.
2. **Restate the Knowledge Lake honestly in `IMPLEMENTATION_STATUS.md`**, the same way the AST extractors and RQCA verdicts are restated. Then decide: either build real ingestion (the retrieval plumbing is done and waiting) or rename it to what it is — a bootstrap prompt-context seed. Either is fine; the current framing is the problem.
3. **Run one real brownfield mission** (unchanged from pass 1, and N2 makes it more urgent — a real repo in a non-seeded language gets zero knowledge context, and you won't see that until you try it).
4. Align Python and compose flag defaults, or log flag provenance at startup. Fix the local `.env` RQCA override.
5. Fix the four extractor docstrings.
6. Update ADR row 17 — the LogicNode graph shipped.
7. Then the doc consolidation and positioning work from pass 1, which still stands.

---

## 6. Bottom line, revised

Reading the implementation moved my assessment **up**, not down. The concurrency reasoning in the audit chain, the security reasoning in the sandbox, and the failure-mode comments throughout the lifecycle are the work of someone who has repeatedly been burned by silent failure and built accordingly. The full test suite passes clean. Nothing I read was decorative.

Two things changed materially. The database layer is far stronger than I credited — you were right to push back. And the Knowledge Lake is far weaker than the status docs claim, which is the one place where this project's otherwise excellent self-honesty didn't hold.

And there is one real defect: a fallback test suite that asserts `True`, running as the command that decides whether a mission ships. You have the correct pattern already written twelve lines above it in the same file. Go apply it.
