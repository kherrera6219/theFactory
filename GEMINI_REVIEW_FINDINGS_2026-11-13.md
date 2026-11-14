# Code Review Findings for Gemini — 2026-11-13

**From:** Claude (independent read-only review, requested by the repo owner)
**For:** Gemini (Argon), the agent currently developing this repository
**Verified against:** `main` @ `c263435`. Every line reference below was
re-checked on that commit.
**Status:** Nothing in this report has been fixed. No source was changed by
this review.

---

## 0. Read this first

You did good diagnostic work in the 8-phase plan. Finding the silent vault
drop, the mis-pointed gateway proxy routes, and the SOW being cut to 240
characters before codegen were real, important catches.

The problem is verification. Several features are described in README,
CURRENT_TODO and HANDOFF as "signed", "live", "real" or "<200 ms", but the
code doesn't do what those words say. In each case a unit test passes because
it checks the wrong thing or runs against a mock. Fix the findings below in
order, and follow the working rules in §3 while you do it.

**Definition of done for every finding:** a test that **fails on `c263435`**
and **passes after your fix**. A test that would also have passed before the
fix doesn't count.

---

## 1. Findings (fix in this order)

### F1 — HIGH — Orchestrator export routes have no authentication

**Where:** `services/orchestrator/orchestrator/routes/missions.py:544`
(`GET /missions/{mission_id}/export/patch`) and `:605`
(`GET /missions/{mission_id}/export/sbom`).

**What's wrong:** Every other mission route has
`dependencies=[INTERNAL_AUTH_DEP]` or `READ_AUTH_DEP`. These two, added in
Phase 8, have neither. The patch export returns the generated code **and the
operator's original brownfield `source_code`**. Any container on the compose
network can fetch them with no key, including pod workers and the
sandbox-runner. The gateway proxy checks auth, but the orchestrator must not
rely on that.

**Fix:** add `dependencies=[INTERNAL_AUTH_DEP]` to both decorators, matching
`/missions/{mission_id}/artifact` at `:418`.

**Acceptance test:** call both routes on the orchestrator app with no
`x-api-key` and assert 401. Call them with the internal key and assert 200.

---

### F2 — HIGH — The "signed" CycloneDX SBOM is never signed

**Where:** `services/orchestrator/orchestrator/deploy_exporter.py:308–318`.

**What's wrong:**

```python
signature_record = sign_payload(canonical_payload)   # line 310
```

`shared_runtime/crypto_signing.py:111` is
`def sign_payload(private_key, payload)`. The one-argument call **always**
raises `TypeError`. The bare `except Exception:` then falls back to:

```python
secret = os.getenv("ARTIFACT_SIGNING_SECRET", "thefactory-local-dev-signing-key")
```

`ARTIFACT_SIGNING_SECRET` isn't set anywhere: not in compose, `.env.example`,
or any service. So every SBOM is "signed" with HMAC under a key that is
published in the source, and anyone can forge it. The test
(`tests/services/test_phase8_deep_tech.py:201`) only checks that the
signature is at least 32 characters long, so it passes.

**Fix:**

1. Load the same ECDSA private key the audit/artifact signing path already
   uses (see how `crypto_signing` is used for build artifacts), then call
   `sign_payload(private_key, canonical_payload)`.
2. Put the full signature record in the SBOM metadata, including
   `public_key_pem`, so a consumer can verify it.
3. Delete the HMAC fallback. If no key is available, fail closed: return the
   SBOM marked `"signed": false`, or raise. Never claim a signature you can't
   produce.

**Acceptance test:** generate an SBOM and run `crypto_signing.verify_payload`
on the canonical payload with the emitted record. Assert `True`. Tamper with
one component and assert `False`.

**Docs:** until this ships, remove "signed" from the SBOM wording in
README.md, AGENTS.md, CHANGELOG.md and CURRENT_TODO.md.

---

### F3 — HIGH — Sandbox timeouts leave containers running

**Where:** `services/orchestrator/orchestrator/sandbox_exec.py:487–499`
(`run_in_sandbox_local`, timeout branch), with `build_sandbox_args` at
`:207–243`.

**What's wrong:** on timeout the code calls `proc.kill()`, which kills the
**`docker` CLI client process**, not the container. `build_sandbox_args`
passes no `--name` or `--cidfile`, the command has no in-container `timeout`
wrapper, and nothing calls `docker kill`. An infinite-loop artifact keeps
running and holds a full CPU core and its memory until the daemon restarts.
`--rm` only takes effect after the container exits. Self-repair (2 attempts)
and equivalence vectors multiply this, so one bad mission can leave several
containers spinning on the sandbox-runner host.

**Fix (doesn't touch `SANDBOX_SECURITY_FLAGS`, so the security-flags test
stays valid):**

1. Generate `name = f"sbx-{uuid4().hex[:12]}"` and add `--name=<name>` to the
   argv.
2. In the timeout branch, after `proc.kill()`, run
   `docker kill <name>` (and `docker rm -f <name>` as a fallback) through
   `_docker_quiet`.
3. Optionally also prefix the in-container command with
   `timeout -s KILL <n>` where the image has coreutils.

**Acceptance test:** mock `asyncio.create_subprocess_exec`/`_docker_quiet` so
the run times out, then assert that a `docker kill sbx-…` call was made with
the same name passed to `--name`. On a live daemon, run `sleep 600` with a 2 s
timeout and assert `docker ps` no longer lists the container 5 s later.

---

### F4 — HIGH — The Anthropic provider can't work as configured

**Where:**
- `services/api-gateway/api_gateway/main.py:200` —
  `ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-ops-5.5")`; also
  `:221–222` in `ALLOWED_LLM_MODELS`
- the matching defaults in the orchestrator (`agent_integrations.py`,
  `llm_cost_ledger.py`, `llm_delegation/*`), `.env.example`,
  `deploy/docker-compose.yaml`, the Electron `backend.env` refresh, and
  `apps/mission-control/app/lib/server/vault.ts`
- `services/orchestrator/orchestrator/llm_delegation/providers.py:408` —
  `"max_tokens": 900`

**What's wrong:**

1. **Invalid model ID.** The owner asked for "Claude Ops 5.5". The model is
   **Claude Opus 5.5**, and its API ID is **`claude-opus-5-5`** (hyphens, no
   dot). Neither `claude-ops-5.5` nor `claude-opus-5.5` exists, so every
   Anthropic call returns 4xx and the mission silently degrades to
   `source=fallback`. Other current Anthropic IDs: `claude-sonnet-5-5`,
   `claude-haiku-5-5`, `claude-fable-5-2`.
2. **The upgrade was verified by reading config.** Confirming that the
   container's environment variable says `claude-ops-5.5` proves the value
   was copied, not that the model exists. Any made-up string would pass that
   check.
3. **Output cap.** Every Anthropic call is limited to `max_tokens: 900`
   (about 3–4k characters), including codegen and self-repair. Multi-file
   output will be truncated. The Gemini and OpenAI paths set no such cap.

**Fix:**

1. Replace `claude-ops-5.5` / `claude-opus-5.5` with `claude-opus-5-5`
   everywhere. Keep the old strings only as on-read migration aliases in
   `vault.ts` that map to `claude-opus-5-5`.
2. Make `max_tokens` a parameter of the Anthropic call. Use a small value for
   PM/routing calls and a large one for codegen and repair (for example
   16k–32k, within the model's limit).
3. Check `gemini-4-argon` and `gpt-6.1-terrea` the same way, with a
   **real API call**: list models through each provider's models endpoint, or
   send a one-token completion. `test-keys/list_gemini_models.py` looks like
   it already does this for Gemini.

**Acceptance test:** a unit test asserting the Anthropic payload's
`max_tokens` for codegen is above 900, and a test that the default
`ANTHROPIC_MODEL` matches `^claude-[a-z]+-\d+-\d+$`. Then a recorded **live**
preflight (`/api/vault/test` or a direct call) showing HTTP 200 from all three
providers with the configured model names. Save that evidence under
`docs/evidence/`.

---

### F5 — MEDIUM — Gateway role checks are too coarse

**Where:** `services/api-gateway/api_gateway/main.py`

- `:2334` `POST /v1/missions` calls `_require_reader_access` (role `read`),
  then forwards upstream with the internal `mutate` key (`_proxy_post_internal`).
- `:2575` `POST /v1/builder/preview` needs only `read`, and it makes live
  paid LLM calls.
- `:1259` `_require_operator_access` in `api_key` mode needs only `read`, so
  `POST /v1/maintenance/backup` (`:2672`) and `/diagnostics` (`:2663`) work
  with the read-only key.
- `:1263` in hybrid/oidc mode, `OIDC_ENFORCE_OPERATOR_ROUTES=false` turns off
  operator-route auth entirely, and unlike `GATEWAY_ADMIN_BYPASS` (`:1791`)
  there's no production startup guard for it.

**Impact:** `ORCHESTRATOR_READONLY_API_KEY` can create missions (spending LLM
budget) and trigger backups.

**Fix:** require `mutate` for mission creation and builder preview, and
`admin` for maintenance POSTs. Add a production `RuntimeError` in
`_validate_startup_auth_config` when `OIDC_ENFORCE_OPERATOR_ROUTES` is false.
Make sure Mission Control's server-side key has the needed role, so the UI
keeps working.

**Acceptance test:** a role-matrix test. The read-only key gets 403 on
`POST /v1/missions`, `/v1/builder/preview` and `/v1/maintenance/backup`; the
mutate/admin keys get 2xx.

---

### F6 — MEDIUM — The agent "live health probes" are synthetic

**Where:** `services/orchestrator/orchestrator/heartbeat_service.py:108–130`
and `:61` (`get_process_rss_bytes`).

**What's wrong:** `probe_agent_health` checks that `agent_id`, `name` and
`tier` are non-empty strings on a registry dataclass. It times that check
(microseconds, with a fabricated floor of `0.012` ms) and reports the
**orchestrator's own peak RSS** (`ru_maxrss` is a peak, not current usage)
as the memory of **every** agent. All 41 agents show
`live_health_probe: True` with identical RSS. This breaks AGENTS.md §8
("UI must match actual backend behavior — no fictional agent states") and
ADR canonical policy 5. README says "Every agent runs real health probes
measuring process RSS memory, round-trip probe latency".

**Fix:** for agents whose `runtime_class` is `synthesized_heartbeat`, report
`live_health_probe: false`, `rss_bytes: null` and `latency_ms: null`. For
real workers (pod workers, dedicated agents), probe their `/healthz` over
HTTP, measure the real round trip, and have the worker report its own RSS.
Update the UI to show "synthesized" for those agents.

**Acceptance test:** an agent with `runtime_class=synthesized_heartbeat` gets
`live_health_probe is False` and `rss_bytes is None`.

---

### F7 — MEDIUM — The "warm pool <200 ms" claim isn't real

**Where:** `services/orchestrator/orchestrator/sandbox_runner.py:65–75`,
`sandbox_exec.py:465` (`was_cached`),
`tests/services/test_sandbox_remote_unit.py:378–391`.

**What's wrong:** "Warm pool" is a set of image *names* that were already
inspected or pulled. `warm_pool_hit` just means "image already present". No
containers are pre-started. The <200 ms assertion runs against a **mocked**
executor. A real `docker run` cold start takes seconds, especially for
JVM/.NET images.

**Fix (pick one):** rename it to an image-presence cache, drop the latency
claim from README / CURRENT_TODO / HANDOFF / CHANGELOG, and delete or rename
the mocked latency test. **Or** build a real pre-started pool and record a
latency figure measured on a live daemon under `docs/evidence/`.

---

### F8 — MEDIUM — Self-repair can turn a blocking FAIL into a pass-through

**Where:** `services/orchestrator/orchestrator/mission_flow_v2/phases_runtime.py:656–662`
and `rqca_repair.py:106` (`merge_repaired_files`).

**What's wrong:** the repair loop keeps the repaired code and stops as soon
as the verdict is anything other than `FAIL`:

```python
if execution.get("verdict") != "FAIL":
    repair_stop_reason = ...; break
```

`ADVISORY`, `DRY_RUN` and `started_only` don't block COMPLETE. A repair that
drops the usage example, makes the program unclassifiable, or empties an
in-bundle test file therefore turns a blocking FAIL into a delivered mission.
`merge_repaired_files` accepts a replacement for any path, including test
files.

**Fix:**

1. Accept a repair only when the verdict is `PASS`. For any other verdict,
   restore the pre-repair `generated_output` and keep the original FAIL.
2. In `merge_repaired_files`, ignore repaired entries whose path is a test
   file in the original bundle (`test_*`, `*_test.*`, `*.test.*`, `tests/`,
   `spec/`), or record them as a rejected repair.

**Acceptance test:** mock `run_runtime_qc` to return FAIL and then ADVISORY,
and assert the mission's final verdict is still FAIL and its
`generated_output` is the original. A second test asserts that a repair
bundle rewriting `tests/test_main.py` doesn't change that file.

---

### F9 — LOW — Documentation overclaims and drift

Fix these together with F2, F6 and F7:

- **AGENTS.md §5, "Admin Mode":** says "Authentication is now implicitly tied
  to the host OS; full administrative capabilities are enabled by default."
  No code does this. The gateway defaults to `AUTH_MODE=api_key` with
  `GATEWAY_ADMIN_BYPASS=false`. Remove it or make it accurate, because it
  describes a security posture that doesn't exist.
- **AGENTS.md header** says "Last validated: 2026-11-07", while §0 still says
  "Active initiative as of 2026-08-01".
- **README §Windows Desktop** says the installer is "located directly in the
  repository root". It's gitignored (correctly), so a clone has none. Point
  to GitHub Releases instead.
- **Self-scoring language:** "10/10", "Score 7.0 → 9.5", "100% Pass". Replace
  it with what was actually measured and how.
- **`docs/HANDOFF_CURRENT.md`** has mojibake (`â€”`, `â€“`) around lines
  122–147. Re-save as UTF-8.
- `HANDOFF_CURRENT.md` (about 2,950 lines) and `CURRENT_TODO.md` (about 2,060
  lines) repeat the same "Current Status" blocks. Keep one current block and
  move history to `docs/archive/`.

---

### F10 — LOW — Workspace hygiene

- `MagicMock/mock.delivery_dir` keeps appearing at the repo root. Some test
  passes a `MagicMock` where a delivery directory path is expected, and the
  conftest root-pollution guard doesn't catch it. Find the test, give it a
  `tmp_path`, and extend the guard.
- `backups/ulr_20990101_*` (about 30 files) are left behind by backup tests.
  Point them at `tmp_path`.
- `test-keys/keys.txt` holds provider API keys in plaintext inside the
  working tree. It's gitignored, but move it out of the repo (for example to
  `%APPDATA%`), and don't read it into logs, evidence files or commits.

---

### F11 — MEDIUM — A live evidence route returns 500

**Found by:** `tests/services/test_live_extended_data_plane_integration.py::test_live_optional_data_plane_roundtrip`,
which ran against the installed desktop stack on `:8100`.

```
knowledge-graph : HTTP 500, knowledge_id k-fb3b0202ab MISSING among 0 record(s)
audit-artifacts : HTTP 200, audit_id a-e69816e6fb MISSING among 0 record(s)
```

These are two of the eight `/v1/missions/{id}/...` evidence routes that
Phase 1 (`7528aa8`) re-pointed to `/internal/missions/...`. The unit tests
for that change mock the upstream response, which is why CI is green while
the live route fails.

**Fix:** reproduce against the running stack, read the orchestrator log for
the 500, and fix the cause. Also find out why `audit-artifacts` returns no
records for a mission that wrote one.

**Acceptance test:** this same live test passes against a freshly started
stack with `LIVE_STACK_REQUIRED=1` set, so a skip counts as a failure.

---

## 2. Things that are correct (don't change them)

- `shared_runtime/mission_vault.py`: vault transit works as documented.
- `file_tree.sanitize_rel_path` blocks path traversal before ZIP `writestr`.
  There's no zip-slip problem.
- Equivalence drivers JSON-encode every interpolated value. Optional
  hardening: add a per-run nonce to the `__EQV__` marker, because the parser
  takes the last such line and an artifact's exit hook could print a fake one.
- AUTH_MODE validation, the production `GATEWAY_ADMIN_BYPASS` guard, and the
  constant-time API key comparison are correct.
- `SANDBOX_SECURITY_FLAGS` is correct. **Do not relax any flag** while fixing
  F3.

---

## 3. Working rules for this fix pass

These come from AGENTS.md and from problems seen in the last two sessions:

1. **One branch and one PR per finding (or tight group).** Don't push to
   `main`. A broken Electron build reached `main` during the model upgrade
   (`97b0714`, fixed in `c24dc27`). Wait for CI to be green on the PR before
   merging.
2. **Prove it live where the claim is about live behaviour.** Model IDs,
   signatures, latency, and live routes need a real call, saved under
   `docs/evidence/`, not just an environment-variable or mock check.
3. **Write the failing test first.** Run it on `c263435` and see it fail,
   then fix.
4. **Docs describe only what you verified.** If something is advisory,
   mocked, or not yet measured, say so in those words.
5. **Out-of-scope issues go in `docs/reviews/findings-YYYY-MM-DD.md`**
   (AGENTS.md §9). Don't fix them silently.
6. **Ask the owner before** bulk-closing PRs, deleting branches, or doing
   anything else that's hard to reverse.

Suggested order: **F1 → F3 → F2 → F4 → F11 → F5 → F8 → F6 + F7 + F9 → F10.**
