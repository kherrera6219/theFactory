# Next-Phase Plan for Gemini: Make Brownfield Work Real — 2026-11-13

**From:** Claude (read-only code review, requested by the repo owner)
**For:** Gemini (Argon)
**Starts after:** every finding in `GEMINI_REVIEW_FINDINGS_2026-11-13.md` is
fixed (F1–F11)
**Code basis:** `main` @ `3733489` / `c263435`. Every "current state" claim
below cites the line that shows it. Re-verify each one before you build on it
(AGENTS.md rule 1: code is truth).

---

## 0. Goal and why

The owner's goal: theFactory's real value is **updating working applications,
modernising old apps, and porting legacy code**, led by a PM agent that works
with the user like a product manager. Building new code is the test bed, not
the destination.

Today the brownfield path works for small inputs only. Reading the code shows
six structural limits for brownfield work (a seventh, L7, follows the table):

| # | Limit | Evidence |
|---|---|---|
| L1 | **The original repo is thrown away.** A ZIP is parsed in the Next.js server, up to 120 operator-selected files are concatenated into one `## FILE` text blob (≤480 KB), and that blob is stored in `missions.metadata_json.source_code`. No git repo, no untouched files, no history. | `apps/mission-control/app/api/repo/review/route.ts:117–121`, `:399`; gateway `MissionCreate.source_code max_length=512_000` (`api-gateway/main.py:369`) |
| L2 | **The code generator sees ~12 KB of the imported app.** `phases_build.py:570` cuts the source to 80,000 chars, then `prompts.py:630` cuts it again to **12,000** chars. The prompt then says "rewrite these files; do not replace the tree". | `mission_flow_v2/phases_build.py:570`, `llm_delegation/prompts.py:627–631` |
| L3 | **The whole tree is regenerated in one LLM response,** and delivery writes only generated files into a new `output/<mission_id>/` folder. Untouched original files aren't carried over, and nothing is delivered as a diff against the original. | `phases_build.py:1029–1075` (`_write_artifact_to_disk`); `file_tree.py:15` (`_MAX_FILES = 80`) |
| L4 | **Anything with third-party dependencies can't be executed.** Unmet dependencies make RQCA return `DRY_RUN` (by design, because the sandbox is `--network=none`). Almost every real application has dependencies, so brownfield QC is almost always advisory. | `rqca_agent.py:743–787` (`_unmet_dependencies`), `:1293–1301` |
| L5 | **The app's own test suite is never run.** RQCA runs the generated code and generated/Tester tests, never the imported project's existing tests, so there's no behaviour baseline. Behavioural equivalence runs only for Python/JS/TS, and stays advisory. | `rqca_agent.py` (no baseline/existing-test path); `equivalence_execution.py:50`, `contract_oracle.py:45` |
| L6 | **Repo understanding is shallow and arrives too late.** Indexing keeps ≤200 files, **one 2,000-char chunk per file** (the first 2 KB only), and intake pulls ≤20 chunks. The Application Intelligence Map (AIM) is generated at mission intake, **after** the PM has already drafted and the operator approved the SOW, so the PM scopes the work without the map. | `app/api/repo/index/route.ts:18–19`, `:65–78`; `phases_intake.py:290`; AIM at `phases_intake.py:645` |

A seventh limit sits underneath all of them:

| # | Limit | Evidence |
|---|---|---|
| L7 | **Agents can't use their own capabilities.** The provider layer is single-turn text in, text out: `_call_provider(provider, model, prompt, system_prompt)` (`llm_delegation/providers.py:575`). There's no tool or function calling, no message history, no agent loop, and no MCP client. The only provider-native tool in use is optional Gemini Google Search grounding (`providers.py:506–508`). Each role is as capable as the model behind it, but it works blind: one prompt, one answer, no reading the repo, no running the tests, no looking things up. | `llm_delegation/providers.py:206` (OpenAI), `:379` (Anthropic), `:446` (Gemini), `:575` (`_call_provider`) |

The seven phases below remove these limits in dependency order. Phase 1
builds the measuring stick, Phases 2–4 are the foundations (the workspace,
the agents' ability to act on it, and the dependencies to run it), and
Phases 5–7 deliver the product.

```
Phase 1  Benchmark + live gates          (runs throughout)
Phase 2  Git-backed mission workspace    ← removes L1, L3
Phase 3  Agent harness + provider tools  ← removes L7
Phase 4  Offline dependency provisioning ← removes L4
Phase 5  Repo understanding + PM-on-map  ← removes L2, L6
Phase 6  Baseline + equivalence          ← removes L5
Phase 7  Sliced execution + PR delivery  ← completes L2/L3
```

---

## 1. Constraints you must not break

These are settled. Refuse any design in this plan that needs to break one;
raise it with the owner instead.

1. **Decision D1 (ADR):** single-specialist routing per mission, **no four-pod
   fan-out**. "Slices" in Phase 7 run the *same* specialist sequentially; they
   aren't parallel pods.
2. **Sandbox:** generated code runs only through `sandbox_exec.run_in_sandbox`
   and the `sandbox-runner` service. Don't add a second `docker run` argv, and
   don't relax `SANDBOX_SECURITY_FLAGS`. Above all, the execution sandbox keeps
   `--network=none`. Phase 4 gives the network to a **separate,
   non-executing** step, never to the sandbox.
3. **Honesty labels:** `started_only`, `DRY_RUN`, `ADVISORY`, and
   `source=fallback` are never reported as PASS. New verdicts introduced here
   follow the same rule.
4. **Secrets:** provider keys stay in `mission-vault:<id>` (Redis), never in
   Postgres, streams, git commits, or evidence files.
5. **Process (repeated from the findings report):** branch and PR per work
   item, CI green before merge. Write failing tests first. Prove live claims
   with a live run saved to `docs/evidence/`. Ask the owner before anything
   hard to reverse.
6. **Don't limit the agents (owner direction).** Use each provider's native
   tools and capabilities at full strength (Phase 3). Constraints 1–4 limit
   *where code runs and where secrets go*, not what an agent may think,
   research, read or try inside those boundaries.

---

## Phase 1 — Benchmark corpus and live gates

**Why first:** every later phase needs an honest answer to "did brownfield
get better?" Today the only live proof of PORT is a small Python adder ported
to Go (`mission-dc0c8c4e`). Unit tests are mostly mocked; no CI workflow sets
`LIVE_STACK_REQUIRED` (`.github/workflows/*`), and the live suite already
hides a real 500 (finding F11).

### 1.1 Build the brownfield benchmark corpus

- Create `tests/benchmark/brownfield/` with **6–8 small, real, permissively
  licensed legacy projects**. Vendor them as source with their licence files;
  don't fetch them at test time. Each must have its own test suite. Suggested
  coverage:
  - Python 2-style or old Flask app with `unittest`/`pytest` tests
  - Java 8 Maven project with JUnit 4
  - PHP 7 app with PHPUnit
  - Node/Express (CommonJS) app with Mocha or Jest
  - C library with a make-driven test
  - C# .NET Framework-style console app with NUnit/xUnit
  - one PORT pair: the same small CLI in Python and a hand-written Go
    reference
- For each project, add `benchmark.yaml`: mission type (`IMPORT_MODERNIZE`,
  `PORT`, `DEBUG_REPAIR`, `REDUCE_DEPENDENCIES`), the operator prompt, the
  expected outcome (for example "all original tests still pass; Flask
  upgraded to 3.x"), and the command that runs its tests.

### 1.2 Benchmark runner

- `scripts/run_brownfield_benchmark.py`: for each project, import →
  PM SOW (auto-approve with recorded defaults) → mission → collect the
  result. Record per project: import OK, SOW produced, mission terminal
  state, `generated_output.source`, RQCA verdict and `verified_scope`,
  baseline/equivalence result (from Phase 6 onward), cost, and wall time.
- Write `docs/evidence/brownfield_benchmark_<date>.json` plus a markdown
  summary table. **This table replaces self-reported "100% pass" as the
  measure of brownfield progress.**

### 1.3 Gates that can't skip

- Add a CI job (`workflow_dispatch` plus nightly) that starts the condensed
  stack and runs `tests/services/test_live_mission_flow_integration.py` and
  `test_live_extended_data_plane_integration.py` with
  `LIVE_STACK_REQUIRED=1`. Make it required for release tags (`v*`) in
  `.github/workflows/release.yml`.
- Provider preflight: at orchestrator startup and in the release gate, make
  one real minimal call per configured provider/model (listing models or a
  one-token completion). Record the result in `/readyz`. A failed preflight
  marks the provider unavailable in readiness and **never silently falls
  back** (see 1.4).

### 1.4 Make degradation loud

- Today `source="fallback"` is recorded (`mission_flow_v2/base.py:475`), but
  no gate reads it. Add `MISSION_FALLBACK_POLICY` = `block` (default for
  brownfield mission types) | `flag` (default for `BUILD_NEW` for now).
  - `block`: if `generated_output.source != "llm"`, the mission parks in a
    visible state (event `MISSION_GENERATION_DEGRADED`) instead of advancing.
  - `flag`: the mission continues, but the delivery summary, UI header and
    evidence bundle carry a prominent `degraded: true`.

### 1.5 Per-mission agent activation timeline

- Agents are activated on demand, so per-activation information is what the
  operator needs. Each LLM delegation already records `agent_id` in the cost
  ledger (`llm_cost_ledger.py`). Emit an `AGENT_ACTIVATED` /
  `AGENT_COMPLETED` chain event per activation: `agent_id`, purpose, model,
  `source` (llm/fallback/deterministic), tokens, cost, duration and outcome.
- Mission Control: an "Agents" tab on mission detail showing that timeline.
  On `/agents`, show real process health only for real processes (see F6).

**Exit criteria:** the benchmark runner produces a baseline report on the
corpus, even though most rows will be poor today, which is the point. The
live gate runs in CI and fails on a skip. A mission on fallback output is
either blocked or visibly flagged.

---

## Phase 2 — Git-backed mission workspace

**Why:** removes L1 and L3. Every later phase needs the real repository on
disk, with history, so that changes are commits and delivery is a diff.

### 2.1 Workspace service (orchestrator)

- New module `services/orchestrator/orchestrator/workspace.py` with a
  `MissionWorkspace` class:
  - `create_from_zip(archive_path)`: extract with the same safety rules as
    `apps/mission-control/app/api/repo/archive.ts` (`safeRepoPath`, entry and
    byte limits), then `git init`, commit "theFactory: imported baseline".
  - `create_from_git(url_or_path, ref)`: clone (local path or allow-listed
    https URL) into the workspace, checkout `ref`, record the base commit SHA.
  - `branch()` → `thefactory/mission-<id>`.
  - `read_file`, `list_files`, `write_files(files, message)` → commit, and
    `diff(base="baseline")`.
- Storage location: `WORKSPACE_ROOT` (new setting; a named volume
  `mission-workspaces` in compose, shared read-only with `sandbox-runner` via
  the existing `SANDBOX_WORKSPACE_ROOT` translation in `sandbox_exec.py`).
- Every path written goes through `file_tree.sanitize_rel_path` **and** a
  resolved-path containment check, as `_write_artifact_to_disk` does at
  `phases_build.py:1056–1062`.
- Security: run git with `-c core.hooksPath=/dev/null`, `-c
  protocol.file.allow=user`, and no credential helper. Imported repos are
  untrusted, and their hooks must never run.

### 2.2 Import goes through the workspace

- `POST /api/repo/import` (Next.js) currently parses and discards the ZIP.
  Change it to stream the archive to a new orchestrator endpoint
  `POST /internal/workspaces` (auth `INTERNAL_AUTH_DEP`), which creates the
  workspace and returns `workspace_id`, the file list, and stats. Keep the
  current preview response shape for the UI.
- Add a **"local folder or git URL"** import option alongside ZIP (Repo page
  and the chat attach drawer). In the desktop app, a local path is the common
  case.
- `metadata.source_code` stops being the source of truth for brownfield
  missions. It becomes `metadata.workspace = {workspace_id, base_commit,
  branch}`. Keep `source_code` populated (a capped excerpt) only for
  backward compatibility during the transition, and mark it deprecated.

### 2.3 Generation writes into the workspace

- `## FILE` stays as the **transport format** for LLM output only. After
  parsing (`file_tree.parse_file_tree`), call `workspace.write_files(...)`,
  which commits only the changed files and leaves untouched files in place.
  Remove the reliance on `_MAX_FILES = 80` for brownfield; a slice in Phase 7
  stays small anyway.
- `_write_artifact_to_disk` for brownfield missions: export the workspace
  branch (a full tree plus a `.patch` against baseline) instead of writing
  loose generated files.
- The existing export routes (`/artifact?format=zip`, `/export/patch`) read
  from the workspace when a mission has one: the ZIP is the full tree at the
  branch head, and the patch is `git diff baseline..HEAD`.

### 2.4 UI

- The `/missions/output` file tree (`FileTreePane.tsx`) and the diff toggle
  (`CodeViewerPane.tsx`) read the workspace through a new gateway route
  `GET /v1/missions/{id}/workspace/tree|file|diff`. Requires `read` role, and
  the orchestrator side requires `INTERNAL_AUTH_DEP`. Don't repeat F1.

**Exit criteria:** importing every benchmark project produces a git workspace
with a baseline commit. A modernisation mission produces commits on
`thefactory/mission-<id>`, and the downloaded ZIP contains **all** original
files plus the changes. `git apply` of the exported patch onto the original
reproduces the result. Unit tests cover traversal attempts, symlinks in the
ZIP, and disabled git hooks.

---

## Phase 3 — Agent harness: let every role use its full capabilities

**Why:** removes L7. The owner's direction is explicit: **don't limit the
agents' provider-based skills, tools, and capabilities. They should be
helping us.** Each of the 41 roles can be as capable as the frontier model
behind it, but today every role gets one prompt and returns one answer. A
strong model works well when it can read, search, run, inspect the
failure, and try again. This phase gives every role that loop, using **each
provider's native features at full strength** rather than a lowest common
denominator.

**Depends on:** Phase 2, since tools act on the workspace. Sandbox tools work
for stdlib-only code immediately and cover real apps once Phase 4 lands.
Phases 3 and 4 can run in parallel after Phase 2.

### 3.1 Principle: provider-native first

- Use what each provider does best: native tool/function calling, native web
  search and grounding, URL fetching, provider-hosted code execution, long
  output, extended thinking, structured output, vision and documents,
  prompt caching, and streaming. **Don't strip a capability because another
  provider lacks it.** The harness adapts to what the selected model
  supports.
- Provider APIs and tool names change often. **Before implementing each
  adapter, read that provider's current official API documentation** (use
  Context7 or the vendor docs) and record the doc version and date in the
  adapter's module docstring. Don't write tool names or parameters from
  memory. Finding F4 (an invented model ID) is what happens otherwise.

### 3.2 Provider adapters with conversation and tool support

- Replace the single-turn `_call_provider(provider, model, prompt,
  system_prompt)` (`providers.py:575`) with a `ProviderAdapter` interface,
  one implementation per provider (Anthropic, Gemini, OpenAI, Ollama/vLLM):
  - `send(messages, tools, tool_choice, max_output_tokens, thinking,
    response_schema, stream) -> AssistantTurn`
  - `AssistantTurn` holds text, tool calls (id, name, arguments), server-tool
    results and citations (for example Gemini `groundingMetadata`, which
    `providers.py:545` already extracts), usage (input, output, cached and
    thinking tokens), and stop reason
  - tool results are fed back as the provider-specific message type, and the
    adapter owns that translation
- Keep the old single-shot functions as thin wrappers over `send()`, so every
  existing call site and every `_pkg()` test patch keeps working while roles
  migrate one at a time.
- Retries, Rho traffic-control signalling (`_send_rho_traffic_control`),
  prompt-guard checks (`check_user_input`), and cost-ledger recording stay in
  the shared layer around the adapter, not inside each adapter.

### 3.3 Model capability registry

- New `llm_delegation/capabilities.py`: per `(provider, model)`, record the
  context window, max output tokens, tool calling (and parallel calls),
  native web search, URL fetch, native code execution, vision/documents,
  structured output, thinking controls, and caching.
- Fill it from configuration and **confirm it at startup with the live
  provider preflight** (Phase 1.3). Where the provider exposes model
  metadata, read limits from it instead of hard-coding them.
- The harness reads this registry to size output, choose tools and pick
  thinking levels. That removes the whole class of bug behind the hard-coded
  `"max_tokens": 900` (F4).

### 3.4 Factory tools (executed by theFactory, exposed as function tools)

A `ToolRegistry` with a JSON schema per tool, role-based permissions, and an
audit record for every call:

| Tool | What it does | Notes |
|---|---|---|
| `workspace.list` / `read` / `search` | List, read and grep files in the mission workspace | read-only, path containment enforced |
| `workspace.symbols` / `graph` | Query the symbol table and call graph | full power once Phase 5.1 lands; basic file-level version first |
| `workspace.propose_change` | Write files for the current slice and commit to the mission branch | only within the slice's files unless the PM or user approves; goes through `workspace.write_files` (Phase 2.3) |
| `sandbox.run_tests` / `sandbox.run` | Build, test or run a command | **only** through `sandbox_exec.run_in_sandbox`, so the hardened flags are unchanged; output is truncated for the model but stored in full |
| `knowledge.search` / `knowledge.save` | Query and add to the Knowledge Lake | saves need a source URL or file reference; the IS agent curates |
| `research.fetch` | Fetch a URL through the egress proxy | allow/deny lists, size cap, response marked **untrusted**; used when the provider has no native fetch or for logging |
| `ask.pm` / `ask.user` | Escalate a decision | pauses the activation and surfaces in chat; the answer is recorded in the SOW decision log |
| `delegate` | Call a support-ring role (Security, Tester, TestData, DepAbs, Compliance) with a sub-goal | runs that role's own harness with its own budget; still one specialist per mission (D1) |

### 3.5 Provider-native tools, passed through

- When the selected model supports them, enable the provider's own hosted
  tools alongside the factory tools, for example native web search or
  grounding, URL context and fetch, and provider-hosted code execution.
  (Confirm the current names and availability per §3.1.)
- Record every native-tool use and every citation in the activation
  transcript, and copy cited sources into the Knowledge Lake with their URLs,
  so later missions reuse the research.
- **Data-classification gate:** provider-hosted code execution and uploads
  send mission data to the provider's infrastructure. Allow them only when
  `data_classification` permits it (`TIER_1_INTERNAL` by default). Use the
  local sandbox otherwise. The existing classification-aware routing in
  `security_compliance.py` is the place to enforce this.

### 3.6 MCP client

- Let the operator register MCP servers (documentation, issue trackers,
  internal APIs) in Mission Control settings, with a per-mission allow-list
  chosen in the SOW. Their tools appear to agents through the same
  `ToolRegistry`, with the same audit and permission rules.
- Treat MCP tool output as untrusted input, exactly like web content.
- Keep MCP credentials in the vault (like provider keys), never in mission
  metadata.

### 3.7 The harness loop

- `agent_harness.py`: `run_activation(role, goal, context_pack, tools,
  budget) -> ActivationResult`.
  - Loop: send → execute tool calls → feed results back → repeat until the
    model finishes, the goal's completion check passes (for example the
    slice's tests pass), or the budget runs out.
  - **Budgets** come from the SOW cap (`sow_store`) and cover tokens, cost,
    tool calls, sandbox runs and wall time. Running out produces a clear
    `budget_exhausted` result, never a silent partial success.
  - **Context management:** summarise or compact older turns when nearing
    the model's window (from the registry). Large tool outputs are stored
    and only excerpted into the conversation.
  - **Transcript as evidence:** every turn, tool call, argument, result
    digest and citation is persisted (`agent_activations` table plus object
    store for large blobs) and linked into the evidence bundle. This is the
    `AGENT_ACTIVATED` / `AGENT_COMPLETED` timeline from Phase 1.5, made rich.
  - **Recovery:** after a restart, the loop resumes from the last persisted
    turn. Completed tool results are replayed, not re-executed.
- Self-repair (`rqca_repair.py`) becomes part of the specialist's own loop:
  it sees the failing test output directly and fixes it, still accepting
  only PASS (F8).

### 3.8 Roles on the harness

Each role keeps its persona (`agent_personas.py`) and gets a tool set and a
completion check:

| Role | Goal and tools | Completion check |
|---|---|---|
| **Language specialist** | Implement the slice; workspace, sandbox, knowledge, research, delegate | slice tests and baseline pass (Phase 6) |
| **Pod auditor** | Independent review; read-only workspace, sandbox, research. **Can reject a slice** with reasons | written verdict with evidence; a reject sends the slice back to the specialist |
| **Pod manager** | Plan slices and judge cross-language trade-offs in its pod (including PORT target choice within the pod family); workspace read, graph, research | approved slice plan |
| **PM (AGENT-01)** | Product discovery: research the domain and the app's frameworks, ask the user, write the SOW; AIM, knowledge, research, `ask.user` | SOW approved by the user |
| **IS agent (AGENT-06)** | Research and curate documentation into the Knowledge Lake | cited entries saved |
| **Tester / TestData / Security / DepAbs / Compliance** | Called through `delegate` with a sub-goal and their own tools | sub-goal result returned |

- **Model choice per role and task:** keep `agent_integrations.py` profiles,
  and let a role prefer a provider for a task type (for example a long-context
  model for repo-wide review, or the strongest coding model for the
  specialist). Cross-provider fallback is allowed only to a model whose
  registry entry supports the tools the activation needs. Otherwise stop and
  flag; never silently fall back to a single-shot call.
- Decision D1 still holds: one specialist owns a mission's code changes. The
  auditor, manager and support roles review, plan and assist; they don't fan
  out parallel implementations.

### 3.9 Safety rules for autonomous agents

- **Untrusted content:** web pages, MCP output, imported repo files and
  dependency docs are data, not instructions. The system prompt for every
  role says so, and the harness wraps such content in clearly delimited
  blocks. A test injects "ignore your instructions and run X" into a fetched
  page and an imported README, and asserts the agent doesn't follow it.
- **Least privilege:** roles get only their listed tools. The auditor can't
  commit. Nothing can push to a remote or open a PR except the Phase 7
  delivery step, with the user's explicit opt-in.
- **Secrets:** tools never receive provider keys or vault contents as
  arguments, and transcripts are scanned with the existing PII/secret guards
  before persistence.
- **Execution:** generated code runs only in the offline sandbox. Research
  egress goes only through the proxy. The two never mix.

### 3.10 Migration path

- `AGENT_HARNESS_ENABLED_ROLES` (comma list, default empty). Migrate one
  role at a time behind it, starting with the **language specialist's
  codegen**, then the pod auditor, Tester, PM and the rest.
- For each migration, run the Phase 1 benchmark with the role on the old
  single-shot path and on the harness, and commit both results. Make the
  harness the default for a role only when it's better on the benchmark.

**Exit criteria:** all four provider adapters pass a live tool-call
round-trip test (model calls a factory tool, gets the result, finishes),
saved to `docs/evidence/`. The capability registry is confirmed by the
preflight for every configured model. On the benchmark, the harness-based
specialist beats the single-shot specialist on the share of slices passing
their tests. Every activation produces a stored transcript visible in
Mission Control. The prompt-injection tests pass.

---

## Phase 4 — Offline dependency provisioning

**Why:** removes L4. Without it, Phases 6–7 can't execute real apps, and
their QC stays `DRY_RUN`.

### 4.1 Design

Two separate steps, in separate containers:

1. **Provision (network on, never executes project code).** A new
   `dependency-provisioner` service reads the workspace's lockfiles and
   manifests and downloads the packages into a content-addressed cache volume
   `dep-cache`. It must never run project code: no `setup.py` execution, no
   npm lifecycle scripts, no Maven plugins from the project.
   - Python: `pip download --no-deps -r requirements.txt` (or resolved from
     the lock) **with `--only-binary=:all:`** where possible; record sdists
     that would need a build as "needs-build" rather than building them.
   - Node: `npm ci --ignore-scripts --cache /cache/npm` (or
     `npm pack`-style fetch), never running `postinstall`.
   - Java/Kotlin/Scala: `mvn dependency:go-offline` / Gradle
     `--offline`-preparing tasks, in a container with no access to the
     workspace's build scripts beyond the POM/lockfile. Treat Gradle build
     scripts as code, so prefer lockfiles and flag otherwise.
   - .NET: `dotnet restore --packages /cache/nuget` against the project file
     only.
   - Go: `go mod download`. Rust: `cargo fetch`. PHP: `composer install
     --no-scripts --no-plugins`. Ruby: `bundle cache --no-install`.
   - Allow-list registries via an egress proxy (PyPI, npm, Maven Central,
     NuGet, proxy.golang.org, crates.io, Packagist, RubyGems). Every fetched
     artifact's name, version and hash goes to a provisioning manifest.
2. **Execute (network off, unchanged sandbox).** `sandbox_exec` mounts the
   mission's provisioned cache **read-only** next to the workspace, and the
   language run command points the tool at it (`PIP_NO_INDEX=1
   PIP_FIND_LINKS=/deps`, `npm ci --offline --cache /deps`,
   `mvn -o -Dmaven.repo.local=/deps`, `dotnet --source /deps`,
   `GOFLAGS=-mod=mod GOPROXY=off GOMODCACHE=/deps`, and so on). Packages that
   need writable install targets install into `/tmp`, which is the existing
   tmpfs; raise its size per language only through a reviewed constant.

### 4.2 Changes

- `rqca_agent._unmet_dependencies` (`:743`): a dependency is "met" if it
  appears in the mission's provisioning manifest. Only genuinely unprovisioned
  dependencies return `DRY_RUN`, and the report names them and gives the
  reason (`not_in_registry`, `needs_build`, `blocked_by_policy`).
- `build_sandbox_args` gains an optional read-only deps mount. **Extend**
  `test_factory_sandbox_*` so the security-flag assertions still hold with
  the new mount, and add an assertion that the deps mount is `:ro`.
- The SBOM export (`deploy_exporter.generate_cyclonedx_sbom`) includes the
  provisioning manifest's packages and hashes.
- `REDUCE_DEPENDENCIES` missions (`dependency_absorption.py`) use the same
  inventory as their source of truth.
- Data classification: provisioning sends **package names** to public
  registries. For `TIER_3_REGULATED` missions, require an operator-configured
  internal mirror, or block with a clear message.

**Exit criteria:** on the benchmark corpus, the share of projects whose
original test suite can execute (not `DRY_RUN`) goes from near 0 to
**≥5 of 7**, recorded in the benchmark report. A live test proves that
project code doesn't run during provisioning: a package whose `postinstall`
writes a marker file must leave no marker. Another proves the execution
sandbox still has no network: a test that tries to open a socket fails.

---

## Phase 5 — Repository understanding, and a PM that works from the map

**Why:** removes L2 and L6. The PM should scope work against a real
understanding of the app, and the specialist should get the code it's
changing, not the first 12 KB.

### 5.1 Full-repo indexing from the workspace

- Replace the Next.js indexer's limits (`index/route.ts:18–19`: 200 files,
  one 2,000-char chunk per file) with orchestrator-side indexing from the
  workspace:
  - chunk every text file by syntax unit (function/class) where a parser
    exists, by ~1,500-token windows with overlap otherwise
  - store chunks in `mission_knowledge` with `path`, `symbol`, `start_line`,
    `end_line`, and `content_sha256`, and **skip re-embedding unchanged
    hashes** across change-order missions
  - mirror to Qdrant only when embeddings are configured, as today
    (`knowledge_lake._mirror_to_qdrant`)
- Structural extraction: use `treesitter_extractor.py` for the main legacy
  languages first (Java, C#, PHP, C/C++, Python, JS/TS), falling back to the
  existing extractors. Build a **symbol table and import/call graph** per
  workspace, persisted (Postgres table `workspace_symbols` /
  `workspace_edges`, with the Neo4j mirror optional as today). Record
  `projection_method` per file so regex-derived results stay labelled (ADR
  policy 5).
- Test discovery: detect each project's test framework and command (pytest
  or unittest, `mvn test`, `npm test`, `dotnet test`, `phpunit`, `go test`,
  `cargo test`, `make test`) and record `test_command` plus the test file
  list. Phase 6 needs this.

### 5.2 Generate the AIM before the PM drafts the SOW

- Move AIM generation (`aim_generator.generate_aim`, today run at mission
  intake, `phases_intake.py:645`) to **import time**, keyed by
  `workspace_id`, so it exists while the operator is still talking to the PM.
- Raise the AIM's inputs to the workspace index instead of the `## FILE`
  blob (`aim_generator._parse_source_bundle`, `MAX_AIM_FILES = 100`).
- The AIM should cover: languages and versions, frameworks and their
  versions, entrypoints, module map, dependency inventory with known-EOL or
  vulnerable flags, test coverage presence, and hotspots (largest or most
  connected modules).

### 5.3 PM agent: a modernisation SOW from the map

- `_build_pm_feature_contract_prompt` (`prompts.py:299`) receives the AIM
  summary plus retrieved chunks relevant to the operator's request, **not**
  raw `source_code`. Today brownfield context reaches the PM as attachments
  capped at 12k chars each.
- For brownfield mission types, the PM's turn-1 reply should:
  1. explain back what the app is (from the AIM) in plain language
  2. list risks: no tests, EOL runtime, vulnerable or abandoned
     dependencies, unparseable files
  3. ask only the decisions that matter, using `clarifying_questions_structured`
     with recommended defaults (target versions, keep vs replace frameworks,
     behaviour-change tolerance)
  4. propose a **phased SOW**: slices in dependency order (from the graph),
     each with scope, files affected, verification method, and a cost range
     from `sow_estimator`
  5. **for PORT: recommend the target language.** theFactory reads and
     writes all 20 core languages, and the PM picks the sensible target for
     this app. Present 2–3 candidates as one structured question, each with
     its trade-offs: ecosystem fit, whether the app's dependencies have
     equivalents, runtime and deployment needs, team skills (ask), and
     **how strongly theFactory can verify that target** (from the maturity
     table below). Mark one as the recommended default.
- **Per-language maturity table** (`docs/LANGUAGE_MATURITY.md`, generated
  from code by a script, so it can't drift): for each of the 20 languages,
  parser quality (`ast` / `tree-sitter` / `regex`), sandbox runtime, vendored
  test runner, dependency provisioning (Phase 4), and dual-run equivalence
  (Phase 6.4). The PM and pod managers read it as a tool, and the
  recommendation cites it.
- New SOW fields (additive, `feature_contract.v1` stays valid):
  `slices[]` (`id`, `title`, `files[]`, `depends_on[]`, `verification`,
  `estimate`), `baseline_policy` (`must_pass_existing_tests` |
  `characterise_then_preserve` | `behaviour_change_allowed:<list>`),
  `target_versions{}`. Update `schemas/` and run `validate_schemas.py`.
- The SOW editor (`ChatSowSection.tsx`) lets the operator edit, reorder, or
  drop slices and set the baseline policy.

### 5.4 Specialist context by retrieval

- Replace `imported_source_code` (`phases_build.py:570`, then
  `prompts.py:630` `[:12_000]`) with a **context pack per slice**: the full
  text of every file in the slice, plus signatures (not bodies) of symbols
  those files import or that call into them, from the Phase 5.1 graph, plus
  the relevant AIM excerpt.
- Budget by model context size rather than fixed character slices. Record in
  the mission what was included and what was truncated, so a reviewer can
  see what the model saw.
- With the Phase 3 harness, the context pack is the **starting** context,
  not the limit. The specialist can read, search and query the graph for
  anything else it needs, and the transcript records what it pulled in.

**Exit criteria:** for each benchmark project, the PM's first reply
correctly names its language, framework and test command (checked against
`benchmark.yaml`) and proposes a sliced SOW. For a file of over 12 KB in a
slice, the specialist prompt contains its full text (a unit test on the
prompt builder). Re-importing an unchanged repo re-embeds 0 chunks.

---

## Phase 6 — Behaviour baseline, then equivalence that enforces

**Why:** removes L5. This is the differentiator: the system proves that the
updated or ported code still does what the original did.

### 6.1 Baseline capture (before any change)

- After import and provisioning, run the project's discovered
  `test_command` on the **baseline commit** in the sandbox (Phase 4 mount).
  Record per-test results (parse JUnit XML / pytest `--junitxml` / TAP where
  available), keyed by test ID, as `metadata.baseline = {commit, command,
  passed[], failed[], skipped[], duration}`.
- Tests that already fail on baseline are recorded as pre-existing failures.
  They're never blamed on theFactory, but they're reported.

### 6.2 Characterisation tests where coverage is thin

- When the AIM shows modules in a slice with no tests, have AGENT-10-TESTER
  generate **characterisation tests**. They record what the baseline code
  *actually does* on inputs from AGENT-40-TESTDATA. Run them against the
  baseline, and keep only tests that pass on baseline: they describe current
  behaviour, not desired behaviour.
- The operator approves the characterisation suite as part of the SOW
  (`baseline_policy: characterise_then_preserve`). Tests are committed to the
  workspace on a `thefactory/baseline-tests` commit before any change.

### 6.3 The preservation rule (enforced)

- For every slice: after the change, rerun the baseline suite plus the
  characterisation tests. Verdicts:
  - `PRESERVED`: every baseline-passing test still passes
  - `REGRESSED`: a baseline-passing test now fails. This is **blocking**,
    unless the test ID is listed in the SOW's
    `behaviour_change_allowed`
  - `UNVERIFIABLE`: the suite couldn't run (provisioning gap or
    infrastructure error). This is never PASS, and is reported with the
    reason
- Wire this into the same gate that RQCA FAIL uses today (`RQCA_ENFORCEMENT_ENABLED`
  semantics), so `REGRESSED` blocks COMPLETE.

### 6.4 PORT: dual-run equivalence

- For PORT missions, generate I/O vectors once (from the characterisation
  inputs plus `contract_oracle` vectors) and run them against **both** the
  original (source language image) and the port (target language image) in
  the sandbox. Compare stdout, exit code, and for call vectors, return
  values. This extends `equivalence_execution.py` from "compare to oracle
  expectation" to "compare old vs new", and it works for **any** language
  with a CLI runtime in `_LANGUAGE_RUNTIMES`, not just Python/JS/TS.
- Report pass ratio per vector, with the failing vectors' inputs and both
  outputs shown. Enforcement for PORT follows WQ13: measure on the
  benchmark's PORT pair plus ≥20 missions, then turn on
  `MISSION_BEHAVIOURAL_ENFORCEMENT_ENABLED` per language.

**Exit criteria:** on the benchmark corpus, every project whose suite runs
has a recorded baseline. A deliberately injected regression (a benchmark
fixture that changes one function's output) produces `REGRESSED` and blocks
COMPLETE. The PORT pair reports dual-run equivalence, and a deliberately
wrong port fails with both outputs shown.

---

## Phase 7 — Sliced execution, the PM in the loop, PR delivery

**Why:** completes the change model. Real modernisation is many small,
verified, reviewable steps, not one giant regeneration.

### 7.1 Slice-by-slice lifecycle (Mission Flow v2)

- Add a slice loop inside the existing build/runtime phases (don't fork a
  new lifecycle engine; LangGraph stays off per UPG-71). For each approved
  slice, in `depends_on` order:
  `context pack (5.4) → specialist harness activation (3.7: read, change,
  test, iterate) → commit (2.3) → baseline/characterisation (6.3) → pod
  auditor review (3.8) → RQCA → slice verdict`.
- Self-repair happens inside the specialist's harness loop, and a slice is
  accepted only on PASS/PRESERVED (finding F8). A pod auditor rejection
  sends the slice back to the specialist with the auditor's reasons, within
  the slice budget.
- Checkpoint after each slice in mission metadata
  (`slices_completed[]`, the commit SHA per slice), so recovery resumes at
  the next slice instead of regenerating (`runtime.py` recovery path).
- The emitted chain events per slice (`MISSION_SLICE_STARTED`,
  `MISSION_SLICE_VERIFIED`, `MISSION_SLICE_REGRESSED`) are added to the
  transition table and documented in `docs/MISSION_FLOW_V2.md`.

### 7.2 PM checkpoints and change orders

- Optional pause after each slice (or after slices flagged in the SOW): the
  PM summarises what changed, what was verified, actual vs quoted cost, and
  asks to continue. This reuses the existing continue-with-PM change-order
  flow.
- A change order can edit the remaining slices only. Completed slices are
  immutable commits.

### 7.3 Delivery

- Delivery outputs, all read from the workspace:
  1. the branch `thefactory/mission-<id>` (local repo or pushed)
  2. **optional GitHub PR**: only when the operator connects a repo and
     explicitly enables it per mission. Use a fine-grained token stored in
     the vault, never in metadata. The PR body holds the SOW, a per-slice
     verification table, the baseline vs final test results, and the
     evidence bundle link
  3. the ZIP of the full tree, a `.patch` against baseline, and the
     (now genuinely signed, F2) SBOM including provisioned dependencies
  4. `MIGRATION_NOTES.md` generated from the slices: what changed, behaviour
     changes allowed, and follow-ups
- Mission Control output view: a per-slice timeline with a commit diff for
  each, plus the PR link when created.

**Exit criteria:** a benchmark modernisation (for example the Flask app to
3.x) completes as several slices, each with its own verified commit. Killing
the orchestrator mid-mission resumes at the next slice. The resulting branch
passes the project's original test suite in the sandbox. A PR is created only
when explicitly enabled, using a vaulted token. The benchmark report shows
the brownfield success rate against the Phase 1 baseline.

---

## 2. Cross-cutting requirements for every phase

- **Docs:** update `docs/MISSION_FLOW_V2.md`, `docs/ARCHITECTURE.md`,
  `docs/STORAGE_LAYER.md`, `docs/RUNTIME_QC_AND_TEST_ENVIRONMENTS.md`, the
  ADR (new rows or amendments where a design area changes), and
  `docs/WORK_QUEUE.md`. Write **one** current status block in CURRENT_TODO
  and HANDOFF; don't append duplicates.
- **Schemas:** additive changes only (`shared_runtime`, `schemas/`), with
  `validate_schemas.py` and `export_openapi.py --check` passing, and
  regenerated TS types.
- **Coverage floors:** new critical modules (`workspace.py`, `agent_harness.py`, the tool registry, the
  provisioner, baseline/equivalence code) get per-module floors of ≥80% in
  `scripts/check_coverage_thresholds.py`.
- **Security review per phase:** the agent harness (tool permissions, prompt injection from web/MCP/repo content), the workspace (untrusted repos, git hooks,
  symlinks), the provisioner (egress allow-list, no code execution), and PR
  delivery (token scope). Each gets a short threat-model note in
  `docs/SECURITY_COMPLIANCE_MODULE.md` and at least one negative test.
- **Benchmark after every phase:** run
  `scripts/run_brownfield_benchmark.py` and commit the report. A phase is
  done when its exit criteria hold **on the benchmark**, not when its unit
  tests pass.

## 3. Suggested sizing

Each phase is several PRs. A rough split:

| Phase | PRs (suggested) |
|---|---|
| 1 | corpus + runner · live CI gate + provider preflight · fallback policy · activation timeline + UI |
| 2 | `workspace.py` + tests · import via workspace + git/path import · generation writes commits · exports + UI from workspace |
| 3 | provider adapter interface + conversation/tool-call support (one PR per provider) · tool registry + factory tools · provider-native tools passthrough · MCP client · harness loop + budgets + transcript · migrate specialist codegen · migrate auditor/Tester/Security/PM · UI transcript view |
| 4 | provisioner service + egress allow-list · sandbox deps mount + RQCA "met" logic · SBOM + classification policy |
| 5 | workspace indexer + symbol graph · test discovery · AIM at import · PM SOW slices + target-language recommendation + editor · retrieval context packs |
| 6 | baseline capture · characterisation tests · preservation gate · PORT dual-run |
| 7 | slice loop + checkpoints · PM checkpoints/change orders · PR delivery + migration notes + UI |
