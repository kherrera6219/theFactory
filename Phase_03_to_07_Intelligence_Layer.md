# Phase 3 — PM Agent Cognition Hardening
**Tier:** 2 — Intelligence Layer | **Duration:** 2–3 days

---

## Current Validation - May 18, 2026

This grouped document is no longer the authoritative status source for Phases
3-7. Those phases have now been implemented in the codebase:

- PM feature contracts and mission charters are persisted by Mission Flow v2.
- CEO mission contracts are persisted and shown in chain trace.
- Generated output is persisted, packaged as `generated_code`, exposed through
  the gateway artifact route, and displayed in Mission Detail.
- CEO logic clusters are persisted as a `logic_clusters.v1` object with a
  `clusters` array and are exposed in Mission Detail.
- Pod group standards are produced during GATING, stored as
  `pod_group_standards`, exposed in chain trace, and displayed in Mission Detail.
- JavaScript/TypeScript and Java AST extraction are active behind
  `JS_AST_EXTRACTOR_ENABLED` and `JAVA_AST_EXTRACTOR_ENABLED`, preserving regex
  concept detection and fallback behavior.

Use this file as a follow-on hardening plan for the still-open intelligence
work:

- Chat preview now uses the backend PM endpoint with local `createBuilderPreview()`
  fallback;
- decide whether PM provider calls need a longer timeout;
- pod-worker extraction now consumes CEO logic-cluster domain focus;
- complete a live provider-key demo for the PM/CEO/generated-output path;
- use Phase 8 FETCH context to improve specialist extraction and generation
  quality.

Current chain-trace fields are exposed at the top level of the chain trace
response: `feature_contract`, `mission_charter`, `mission_contract`,
`logic_clusters`, `pod_group_standards`, and `generated_output`. Current
logic-cluster event naming is `LOGIC_CLUSTERS_DECOMPOSED`, not
`MISSION_LOGIC_CLUSTERS_ASSIGNED`.

---

## Problem

`generate_pm_feature_contract()` is already wired and makes a real LLM call.
However, the Chat page in Mission Control does NOT call it — it uses
`createBuilderPreview()` which is a local keyword-extraction stub. Operators
using the UI get a hardcoded feature contract preview, not a real PM analysis.
Also, the PM call has a 15-second default timeout which causes it to silently
fall back under load.

---

## Change 1 — Wire real PM call into Chat page

### File: `apps/mission-control/app/(shell)/chat/page.tsx`

The `sendMessage()` function currently calls `createBuilderPreview()` when the user
clicks Submit. This produces a local JS preview using pattern matching on the prompt.

Replace with a call to a new API route that invokes the orchestrator PM endpoint:

**New API route:** `apps/mission-control/app/api/pm/feature-contract/route.ts`

```typescript
import { NextResponse } from "next/server";
import { requireOperatorRequestSession } from "../../../lib/server/operator-session";
import { getVaultSecret } from "../../../lib/server/vault";

export const runtime = "nodejs";

const API_BASE_URL =
  process.env.MISSION_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8100";

export async function POST(request: Request) {
  const unauthorized = requireOperatorRequestSession(request);
  if (unauthorized) return unauthorized;

  const body = await request.json();
  const apiKey = await getVaultSecret("OPERATOR-API-KEY");

  const upstream = await fetch(`${API_BASE_URL}/v1/pm/feature-contract`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey ?? "",
    },
    body: JSON.stringify(body),
    cache: "no-store",
    signal: AbortSignal.timeout(30_000),
  });

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
```

**New gateway endpoint:** `POST /v1/pm/feature-contract`

Add to `services/api-gateway/api_gateway/main.py`:

```python
@app.post("/v1/pm/feature-contract")
async def create_pm_feature_contract(
    body: dict[str, Any],
    auth: AuthContext = Depends(require_roles(settings, {"operator", "admin"})),
):
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    result = await proxy_post(
        f"{ORCHESTRATOR_URL}/internal/pm/feature-contract",
        json_body=body,
    )
    return result
```

**New orchestrator internal endpoint:**

Add to `services/orchestrator/orchestrator/routes/internal.py`:

```python
@router.post("/pm/feature-contract")
async def create_pm_feature_contract(body: dict[str, Any], request: Request):
    from ..llm_delegation import generate_pm_feature_contract
    prompt = str(body.get("prompt", "")).strip()
    mission_type = str(body.get("mission_type", "BUILD_NEW"))
    depth_mode = str(body.get("depth_mode", "STANDARD"))
    output_mode = str(body.get("output_mode", "FULL_BUILD"))
    language = body.get("requested_target_language")
    contract = await generate_pm_feature_contract(
        prompt=prompt,
        mission_type=mission_type,
        depth_mode=depth_mode,
        output_mode=output_mode,
        requested_target_language=language,
    )
    return contract
```

**Update Chat page to call real PM:**

In `sendMessage()`, after the user submits:
```typescript
async function sendMessage() {
  // ... existing validation ...
  setThinking(true);
  try {
    const pmResponse = await fetch("/api/pm/feature-contract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: normalized,
        mission_type: selectedMissionType,
        depth_mode: selectedDepthMode,
        output_mode: selectedOutputMode,
        requested_target_language: inferRequestedTargetLanguage(normalized, files),
      }),
    });
    const contract = await pmResponse.json();
    setContract(mapApiContractToFeatureContract(contract));
    // Add PM response as chat message
    addMessage("pm", buildPMResponseText(contract));
  } catch (err) {
    // Fall back to local preview on error
    const preview = createBuilderPreview(normalized, files);
    setContract(preview);
    addMessage("pm", buildFallbackResponseText(normalized));
  } finally {
    setThinking(false);
  }
}
```

Add `mapApiContractToFeatureContract()` to map the API response to the existing
`FeatureContract` type used in the UI state.

---

## Change 2 — Increase LLM timeout for PM calls

The default LLM timeout is 20 seconds (`OPENAI_TIMEOUT_SECONDS`, `ANTHROPIC_TIMEOUT_SECONDS`).
PM and CEO calls under load may need more time.

In `.env.example`, add:
```
ANTHROPIC_TIMEOUT_SECONDS=45
OPENAI_TIMEOUT_SECONDS=45
GEMINI_TIMEOUT_SECONDS=45
```

In `deploy/docker-compose.yaml`, add to the orchestrator environment block:
```yaml
ANTHROPIC_TIMEOUT_SECONDS: ${ANTHROPIC_TIMEOUT_SECONDS:-45}
OPENAI_TIMEOUT_SECONDS: ${OPENAI_TIMEOUT_SECONDS:-45}
GEMINI_TIMEOUT_SECONDS: ${GEMINI_TIMEOUT_SECONDS:-45}
```

---

## Validation

- [ ] Submit a prompt in the Chat page — PM thinking indicator shows, real structured
      contract appears (not hardcoded template text)
- [ ] `title`, `summary`, `functional_requirements`, `acceptance_criteria` in contract
      are specific to the submitted prompt, not generic placeholder text
- [x] If provider/API access is unavailable, Chat page falls back gracefully without crashing
- [x] Full Python test suite and Mission Control typecheck pass

---

# Phase 4 — Mission Charter Generation at PM_INTAKE
**Tier:** 2 — Intelligence Layer | **Duration:** 1–2 days

---

## Problem

`build_mission_charter()` in `mission_flow_v2.py` generates a mission charter
during PM_INTAKE from the PM feature contract. The function exists and is called.
But the charter is currently built from the **fallback** feature contract (when PM
LLM call fails) most of the time. Once Phase 1+3 unlock real PM output, the charter
will be populated with real content.

This phase verifies the charter is correct, adds it to the chain trace display,
and adds a test. Current implementation already persists and displays the
charter; remaining work is credentialed provider validation and any stricter
runtime schema validation the project wants before release claims.

---

## Change 1 — Verify charter stored correctly in PM_INTAKE

In `mission_flow_v2.py`, find `_prepare_pm_intake()`. Confirm:
1. `generate_pm_feature_contract()` is awaited before `build_mission_charter()` is called
2. The charter is stored in `metadata["mission_charter"]`
3. PM intake events expose the generated feature-contract and charter context.
   Current event naming uses `FEATURE_CONTRACT_CREATED`; add a dedicated
   `MISSION_CHARTER_GENERATED` event only if the team wants more granular trace
   semantics.

If the ordering is wrong or the charter call is missing, add it:
```python
async def _prepare_pm_intake(...):
    # ...
    feature_contract = await generate_pm_feature_contract(
        prompt=mission.prompt or "",
        mission_type=metadata.get("mission_type", "BUILD_NEW"),
        depth_mode=metadata.get("depth_mode", "STANDARD"),
        output_mode=metadata.get("output_mode", "FULL_BUILD"),
        requested_target_language=mission.requested_target_language,
    )
    metadata["feature_contract"] = feature_contract

    charter = build_mission_charter(
        mission_id=mission_id,
        prompt=mission.prompt or "",
        requested_target_language=mission.requested_target_language,
        feature_contract=feature_contract,
        mission_type=metadata.get("mission_type", "BUILD_NEW"),
        depth_mode=metadata.get("depth_mode", "STANDARD"),
        output_mode=metadata.get("output_mode", "FULL_BUILD"),
    )
    metadata["mission_charter"] = charter
    # ...
```

## Change 2 — Display Mission Charter on Mission Detail page

In `apps/mission-control/app/(shell)/missions/[id]/page.tsx`,
add a collapsible "Mission Charter" panel after the Mission Signals panel:

```tsx
{chainTrace?.mission_charter && (
  <Panel title="Mission Charter" collapsible defaultCollapsed>
    <div className="charter-grid">
      <div><strong>Objective:</strong> {chainTrace.mission_charter.objective}</div>
      <div><strong>Depth:</strong> {chainTrace.mission_charter.depth_mode}</div>
      <div><strong>Output:</strong> {chainTrace.mission_charter.output_mode}</div>
    </div>
    {chainTrace.mission_charter.scope?.in_scope?.length > 0 && (
      <div>
        <strong>In scope:</strong>
        <ul>{chainTrace.mission_charter.scope.in_scope.map(
          (item: string, i: number) => <li key={i}>{item}</li>
        )}</ul>
      </div>
    )}
    {chainTrace.mission_charter.success_criteria?.length > 0 && (
      <div>
        <strong>Success criteria:</strong>
        <ul>{chainTrace.mission_charter.success_criteria.map(
          (item: string, i: number) => <li key={i}>{item}</li>
        )}</ul>
      </div>
    )}
  </Panel>
)}
```

## Change 3 — Add charter unit test

Add to `tests/services/test_mission_flow_v2_unit.py`:

```python
def test_build_mission_charter_with_real_feature_contract():
    from orchestrator.mission_flow_v2 import build_mission_charter
    contract = {
        "title": "CSV Reader",
        "summary": "Read CSV and return dicts",
        "functional_requirements": ["read CSV", "return list of dicts"],
        "acceptance_criteria": ["function returns list", "keys match headers"],
        "risk_notes": ["large files may be slow"],
        "human_approval_required": False,
    }
    charter = build_mission_charter(
        mission_id="test-001",
        prompt="Read a CSV",
        requested_target_language="python",
        feature_contract=contract,
        mission_type="BUILD_NEW",
        depth_mode="STANDARD",
        output_mode="FULL_BUILD",
    )
    assert charter["charter_id"].startswith("charter-")
    assert charter["objective"] == "Read CSV and return dicts"
    assert "read CSV" in charter["scope"]["in_scope"]
    assert "function returns list" in charter["success_criteria"]
```

---

## Validation

- [ ] Charter present in chain trace for every mission that reaches COMPLETE
- [ ] `metadata.mission_charter.objective` is the PM's summary, not the raw prompt
- [ ] Mission Detail page shows Charter panel
- [ ] New unit test passes

---

# Phase 5 — CEO Logic Cluster Decomposition
**Tier:** 2 — Intelligence Layer | **Duration:** 3–4 days

---

## Problem

The CEO currently makes two LLM calls: routing (which agent) and contract (what to build).
The contract includes `required_domains` and `logicnode_requirements` — but these are
not used to focus what each pod does. All pods extract everything from the source regardless
of which domains they were assigned. The CEO does not communicate "Pod B, focus on systems
and I/O; Pod A, focus on string manipulation and list operations."

---

## Change 1 — Add `generate_logic_clusters()` to `llm_delegation.py`

```python
async def generate_logic_clusters(
    *,
    mission_context: dict[str, Any],
    mission_contract: dict[str, Any],
    requested_target_language: str | None,
) -> list[dict[str, Any]]:
    """CEO decomposes the mission contract into pod-specific Logic Clusters."""
    recommendation = _ceo_recommendation()
    provider = recommendation["provider"]
    model = recommendation["model"]

    required_domains = mission_contract.get("required_domains") or []
    logicnode_reqs = mission_contract.get("logicnode_requirements") or []
    contract_summary = mission_contract.get("contract_summary", "")

    prompt = (
        "You are AGENT-02-CEO. Decompose this mission contract into Logic Clusters "
        "— one cluster per pod that will work on this mission.\n"
        f"Recommended model: {provider}/{model}\n"
        "Return only a JSON array. No markdown.\n\n"
        f"Mission: {_clean_text(contract_summary, max_length=300)}\n"
        f"Required domains: {json.dumps(required_domains[:12])}\n"
        f"LogicNode requirements: {json.dumps(logicnode_reqs[:8], indent=2)}\n"
        f"Target language: {_clean_text(requested_target_language or 'auto', max_length=32)}\n\n"
        "Return an array where each element has:\n"
        "{\n"
        '  "cluster_id": "short-id",\n'
        '  "assigned_pod": "podA | podB | podC | podD",\n'
        '  "domains": ["domain names assigned to this pod"],\n'
        '  "description": "one sentence",\n'
        '  "priority": "HIGH | MEDIUM | LOW"\n'
        "}\n"
        "Only include pods that have meaningful work. Omit pods with no relevant domains.\n"
        "Pod assignments: podA=dynamic/scripting, podB=systems/compiled, "
        "podC=enterprise/JVM, podD=math/scientific\n"
    )

    parsed, resolved_provider, resolved_model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context="ceo logic clusters",
    )

    if not isinstance(parsed, list):
        # Fallback: assign all work to the pod matching the target language
        pod = _pod_for_language(requested_target_language)
        return [
            {
                "cluster_id": "cluster-primary",
                "assigned_pod": pod,
                "domains": required_domains[:6],
                "description": f"Primary work cluster for {requested_target_language or 'auto'}",
                "priority": "HIGH",
                "source": "fallback",
            }
        ]

    clusters = []
    valid_pods = {"podA", "podB", "podC", "podD"}
    for item in parsed[:8]:
        if not isinstance(item, dict):
            continue
        pod = str(item.get("assigned_pod", "")).strip()
        if pod not in valid_pods:
            continue
        clusters.append({
            "cluster_id": _clean_text(item.get("cluster_id", ""), max_length=48) or f"cluster-{pod}",
            "assigned_pod": pod,
            "domains": _string_list(item.get("domains"), limit=8, max_length=64),
            "description": _clean_text(item.get("description", ""), max_length=200),
            "priority": _clean_text(item.get("priority", "MEDIUM"), max_length=12).upper(),
            "source": "llm",
            "model_provider": resolved_provider,
            "model": resolved_model,
        })

    return clusters or [{"cluster_id": "cluster-primary", "assigned_pod": "podA",
                         "domains": [], "description": "Fallback cluster", "priority": "HIGH",
                         "source": "fallback"}]
```

Add `_pod_for_language()` helper:
```python
def _pod_for_language(language: str | None) -> str:
    normalized = (language or "").strip().lower()
    if normalized in {"python", "javascript", "typescript", "ruby", "php"}:
        return "podA"
    if normalized in {"c", "cpp", "rust", "zig", "go"}:
        return "podB"
    if normalized in {"java", "csharp", "kotlin", "scala"}:
        return "podC"
    if normalized in {"matlab", "r", "julia", "mathematica", "haskell", "ocaml"}:
        return "podD"
    return "podA"
```

## Change 2 — Wire into `_prepare_ceo_delegation()` in `mission_flow_v2.py`

After `generate_mission_contract()` succeeds:

```python
logic_clusters = await generate_logic_clusters(
    mission_context=mission_context,
    mission_contract=mission_contract,
    requested_target_language=mission.requested_target_language,
)
metadata["logic_clusters"] = logic_clusters

if not _chain_event_exists(metadata, "LOGIC_CLUSTERS_DECOMPOSED"):
    append_chain_event(
        metadata,
        event_type="LOGIC_CLUSTERS_DECOMPOSED",
        agent_id=CEO_AGENT_ID,
        details={
            "cluster_count": len(logic_clusters.get("clusters", [])),
            "pods_assigned": list({
                c["assigned_pod"] for c in logic_clusters.get("clusters", [])
            }),
        },
    )
```

## Change 3 — Use clusters to focus pod-worker extraction

In `services/pod-worker/pod_worker/main.py`, in `_handle_running_mission()`,
after fetching `mission_metadata`:

```python
# Determine which domains this pod should focus on
logic_cluster_doc = mission_metadata.get("logic_clusters") or {}
logic_clusters = logic_cluster_doc.get("clusters") or []
pod_cluster = next(
    (c for c in logic_clusters if c.get("assigned_pod") == POD_NAME.lower()),
    None,
)
focus_domains = pod_cluster.get("domains") or [] if pod_cluster else []

# Pass focus_domains to extractor — extractor uses them to weight concept matching
extractor = _get_extractor(extraction_language)
result = extractor.extract(source_code, focus_domains=focus_domains)
```

Update `LanguageExtractor.extract()` in `language_extractor.py` to accept
an optional `focus_domains` parameter. When provided, boost confidence scores
for concepts that match the focus domains. This does not change which concepts
are extracted — it changes which are ranked highest in the logicnode output.

## Change 4 — Display Logic Clusters on Mission Detail page

Add a "Logic Clusters" panel after the Mission Contract panel:

```tsx
{chainTrace?.logic_clusters?.clusters?.length > 0 && (
  <Panel title="Logic Clusters">
    <div className="cluster-grid">
      {chainTrace.logic_clusters.clusters.map((cluster: any) => (
        <div key={cluster.cluster_id} className="cluster-card">
          <strong>{cluster.assigned_pod}</strong>
          <span className={`priority-badge ${cluster.priority.toLowerCase()}`}>
            {cluster.priority}
          </span>
          <p>{cluster.description}</p>
          {cluster.domains.length > 0 && (
            <div className="domain-chips">
              {cluster.domains.map((d: string) => (
                <span key={d} className="domain-chip">{d}</span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  </Panel>
)}
```

## Validation

- [x] CEO delegation chain event includes `LOGIC_CLUSTERS_DECOMPOSED`
- [x] `logic_clusters.clusters` present in chain trace with at least 1 cluster
- [x] Pod workers consume cluster focus from `logic_clusters.clusters[n].assigned_pod`
- [x] Mission Detail shows Logic Clusters panel
- [x] Full Python test suite passes

---

# Phase 6 — Sub-Manager Consolidation (Pod Group Standards)
**Tier:** 2 — Intelligence Layer | **Duration:** 4–5 days

---

## Problem

Pod managers currently produce a routing stub with `plan_summary` and `deliverables`.
They do not consolidate LogicNodes from multiple specialists. In the full-dedicated
topology, a pod can have multiple specialists running. Even in condensed mode, the
Sub-Manager should consolidate the logicnodes written by the specialist(s) under its
pod and produce a Pod Group Standard before signaling CEO for FUSION.

---

## Change 1 — Add `generate_pod_group_standard()` to `llm_delegation.py`

```python
async def generate_pod_group_standard(
    *,
    pod_name: str,
    pod_manager_agent_id: str,
    mission_id: str,
    logicnodes: list[dict[str, Any]],
    mission_contract: dict[str, Any],
) -> dict[str, Any]:
    """Sub-Manager consolidates pod logicnodes into a Pod Group Standard."""
    if not logicnodes:
        return {
            "pod": pod_name,
            "pod_manager_agent_id": pod_manager_agent_id,
            "canonical_logicnodes": [],
            "eliminated_duplicates": 0,
            "summary": "No logicnodes to consolidate.",
            "source": "empty",
        }

    recommendation = _agent_recommendation(pod_manager_agent_id)
    node_summaries = [
        {"node_id": n.get("node_id"), "domain": n.get("domain"),
         "concept": n.get("concept"), "intent": n.get("intent")}
        for n in logicnodes[:30]
    ]
    prompt = (
        f"You are {pod_manager_agent_id} (Pod {pod_name} Sub-Manager).\n"
        "Consolidate these LogicNodes into a Pod Group Standard.\n"
        "Remove duplicates, merge equivalent concepts, rank by importance.\n"
        "Return only JSON with keys: canonical_logicnodes (array, max 20), "
        "eliminated_duplicates (int), summary (string).\n\n"
        f"Mission: {_clean_text(mission_contract.get('contract_summary', ''), max_length=200)}\n"
        f"LogicNodes to consolidate:\n{json.dumps(node_summaries, indent=2)}\n"
    )
    parsed, provider, model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"pod group standard {pod_name}",
    )
    if not isinstance(parsed, dict):
        return {
            "pod": pod_name,
            "pod_manager_agent_id": pod_manager_agent_id,
            "canonical_logicnodes": logicnodes[:20],
            "eliminated_duplicates": max(0, len(logicnodes) - 20),
            "summary": f"{pod_name} group standard (fallback — {len(logicnodes)} nodes passed through)",
            "source": "fallback",
        }
    return {
        "pod": pod_name,
        "pod_manager_agent_id": pod_manager_agent_id,
        "canonical_logicnodes": parsed.get("canonical_logicnodes") or logicnodes[:20],
        "eliminated_duplicates": int(parsed.get("eliminated_duplicates") or 0),
        "summary": _clean_text(parsed.get("summary") or "", max_length=400),
        "source": "llm",
        "model_provider": provider,
        "model": model,
    }
```

## Change 2 — Call consolidation after RUNNING state in `mission_flow_v2.py`

In the GATING phase handler, after the pod-worker has finished writing logicnodes:

```python
async def _prepare_gating(...):
    # Fetch all logicnodes for this mission
    logicnodes = await asyncio.to_thread(
        storage.list_logicnodes, settings, mission_id, limit=200
    )
    mission_contract = metadata.get("mission_contract") or {}
    pod_manager_agent_id = metadata.get("assigned_pod_manager_agent_id") or DEFAULT_POD_MANAGER

    # Run Sub-Manager consolidation
    pod_group_standard = await generate_pod_group_standard(
        pod_name=pod_name_from_agent(pod_manager_agent_id),
        pod_manager_agent_id=pod_manager_agent_id,
        mission_id=mission_id,
        logicnodes=[n["node"] for n in logicnodes if isinstance(n.get("node"), dict)],
        mission_contract=mission_contract,
    )
    metadata["pod_group_standards"] = {
        pod_group_standard["pod"]: pod_group_standard
    }
    append_chain_event(
        metadata,
        event_type="MISSION_POD_GROUP_STANDARD_PRODUCED",
        agent_id=pod_manager_agent_id,
        details={
            "pod": pod_group_standard["pod"],
            "canonical_count": len(pod_group_standard["canonical_logicnodes"]),
            "eliminated": pod_group_standard["eliminated_duplicates"],
            "source": pod_group_standard["source"],
        },
    )
```

## Validation

- [x] Chain trace includes `MISSION_POD_GROUP_STANDARD_PRODUCED` event after GATING
- [x] `metadata.pod_group_standards.podA.canonical_logicnodes` non-empty
- [x] `eliminated_duplicates` is >= 0 (0 is fine for simple missions)
- [x] Focused Python tests, ruff, and Mission Control lint pass

## Current status - implemented May 18, 2026

- `generate_pod_group_standard()` is implemented with provider routing,
  normalization, and deterministic fallback deduplication.
- Mission Flow v2 produces standards after the mission reaches `GATING`, stores
  them under `metadata["pod_group_standards"]`, emits
  `MISSION_POD_GROUP_STANDARD_PRODUCED`, and records audit evidence.
- Chain trace and Mission Detail expose the standards.

---

# Phase 7 — Java and JS/TS AST Extractors
**Tier:** 2 — Intelligence Layer | **Duration:** 2–3 days

---

## Problem

`java_ast_extractor.py` and `js_ast_extractor.py` both return `success=False`
immediately. Both files document exactly what is needed to activate them.
Java and JavaScript are the two most common languages after Python in enterprise
repos. Activating real AST extraction for these two languages significantly
improves logicnode quality for IMPORT_MODERNIZE and PORT missions.

---

## Change 1 — Java AST extractor

### Add dependency
In `services/pod-worker/requirements.txt`:
```
javalang==0.13.0
```

### Implement `java_ast_extractor.py`

Replace the stub body of `extract_java_ast(source: str)`:

```python
def extract_java_ast(source: str) -> "JavaAstExtractionResult":
    result = JavaAstExtractionResult()
    try:
        import javalang
        tree = javalang.parse.parse(source)
    except Exception as exc:
        LOGGER.debug("java AST parse failed: %s", exc)
        result.success = False
        result.error = str(exc)
        return result

    for path, node in tree:
        if isinstance(node, javalang.tree.MethodDeclaration):
            params = tuple(p.type.name for p in (node.parameters or []))
            modifiers = tuple(sorted(node.modifiers or []))
            annotations = tuple(
                a.name for a in (node.annotations or [])
            )
            result.methods.append(JavaMethodInfo(
                name=node.name,
                line=node.position.line if node.position else 0,
                return_type=node.return_type.name if node.return_type else "void",
                parameters=params,
                modifiers=modifiers,
                annotations=annotations,
                signature=f"{node.return_type.name if node.return_type else 'void'} "
                           f"{node.name}({', '.join(params)})",
            ))
        elif isinstance(node, (javalang.tree.ClassDeclaration,
                                javalang.tree.InterfaceDeclaration,
                                javalang.tree.EnumDeclaration)):
            kind = (
                "interface" if isinstance(node, javalang.tree.InterfaceDeclaration)
                else "enum" if isinstance(node, javalang.tree.EnumDeclaration)
                else "class"
            )
            extends_name = (
                node.extends.name
                if hasattr(node, "extends") and node.extends else None
            )
            implements = tuple(
                i.name for i in (getattr(node, "implements", None) or [])
            )
            method_names = tuple(
                m.name for m in (node.body or [])
                if isinstance(m, javalang.tree.MethodDeclaration)
            )
            result.classes.append(JavaClassInfo(
                name=node.name,
                line=node.position.line if node.position else 0,
                kind=kind,
                extends=extends_name,
                implements=implements,
                annotations=tuple(a.name for a in (node.annotations or [])),
                methods=method_names,
            ))
        elif isinstance(node, javalang.tree.Import):
            result.imports.append(JavaImportInfo(
                qualified_name=node.path,
                is_static=bool(node.static),
                is_wildcard=bool(node.wildcard),
                line=0,
            ))

    result.success = True
    return result
```

### Wire into pod-worker

In `services/pod-worker/pod_worker/main.py`, add env var:
```python
JAVA_AST_EXTRACTOR_ENABLED = (
    os.getenv("JAVA_AST_EXTRACTOR_ENABLED", "false").strip().lower() == "true"
)
```

Update `_get_extractor()`:
```python
def _get_extractor(language: str):
    if language == "python" and PYTHON_AST_EXTRACTOR_ENABLED:
        return PythonAstExtractor()
    if language == "java" and JAVA_AST_EXTRACTOR_ENABLED:
        from .java_ast_extractor import JavaAstExtractor
        return JavaAstExtractor()
    return get_extractor(language)
```

In `.env.example` and `deploy/docker-compose.yaml` orchestrator/pod-worker env:
```
JAVA_AST_EXTRACTOR_ENABLED=true
```

---

## Change 2 — JS/TS AST extractor

### Add dependency
In `services/pod-worker/requirements.txt`:
```
esprima==4.0.1
```

### Implement `js_ast_extractor.py`

Replace the stub body of `extract_js_ast(source: str)`:

```python
def extract_js_ast(source: str) -> "JsAstExtractionResult":
    result = JsAstExtractionResult()
    try:
        import esprima
        # Strip TypeScript-specific syntax before parsing with esprima
        clean_source = _strip_ts_syntax(source)
        tree = esprima.parseScript(clean_source, tolerant=True)
    except Exception as exc:
        try:
            # Retry as module (for import/export syntax)
            tree = esprima.parseModule(clean_source, tolerant=True)
        except Exception:
            LOGGER.debug("js AST parse failed: %s", exc)
            result.success = False
            result.error = str(exc)
            return result

    _walk_js_tree(tree, result)
    result.success = True
    return result


def _strip_ts_syntax(source: str) -> str:
    """Remove TypeScript-specific annotations esprima cannot parse."""
    import re
    # Remove type annotations like ': string', ': number[]', ': MyType'
    source = re.sub(r":\s*[A-Za-z_$][A-Za-z0-9_$.<>\[\]|&?]*(?=\s*[,)=;{])", "", source)
    # Remove 'as Type' casts
    source = re.sub(r"\s+as\s+[A-Za-z_$][A-Za-z0-9_$.<>\[\]|&?]*", "", source)
    # Remove interface/type declarations
    source = re.sub(r"^\s*(interface|type)\s+\w[^{]*\{[^}]*\}", "", source, flags=re.MULTILINE)
    # Remove access modifiers
    source = re.sub(r"\b(public|private|protected|readonly)\s+", "", source)
    return source


def _walk_js_tree(node: Any, result: "JsAstExtractionResult") -> None:
    if node is None:
        return
    node_type = getattr(node, "type", None)
    if node_type == "FunctionDeclaration":
        name = getattr(getattr(node, "id", None), "name", "<anonymous>")
        result.functions.append(JsFunctionInfo(
            name=name,
            line=getattr(getattr(node, "loc", None), "start", {}).get("line", 0)
                 if hasattr(node, "loc") else 0,
            is_async=getattr(node, "async", False),
            is_arrow=False,
            is_method=False,
            signature=f"function {name}()",
        ))
    elif node_type == "ClassDeclaration":
        name = getattr(getattr(node, "id", None), "name", "<anonymous>")
        extends = getattr(getattr(node, "superClass", None), "name", None)
        body = getattr(getattr(node, "body", None), "body", []) or []
        methods = tuple(
            getattr(getattr(m, "key", None), "name", "")
            for m in body
            if getattr(m, "type", None) == "MethodDefinition"
        )
        result.classes.append(JsClassInfo(
            name=name, line=0, extends=extends, methods=methods
        ))
    elif node_type == "ImportDeclaration":
        module = getattr(getattr(node, "source", None), "value", "")
        specifiers = getattr(node, "specifiers", []) or []
        names = tuple(
            getattr(getattr(s, "local", None), "name", "")
            for s in specifiers
        )
        is_default = any(
            getattr(s, "type", "") == "ImportDefaultSpecifier"
            for s in specifiers
        )
        result.imports.append(JsImportInfo(
            module=module, names=names, is_default=is_default, line=0
        ))
    # Recurse into child nodes
    for attr in vars(node).values() if hasattr(node, "__dict__") else []:
        if hasattr(attr, "type"):
            _walk_js_tree(attr, result)
        elif isinstance(attr, list):
            for item in attr:
                if hasattr(item, "type"):
                    _walk_js_tree(item, result)
```

### Wire into pod-worker

Add env var and update `_get_extractor()` similar to Java above:
```python
JS_AST_EXTRACTOR_ENABLED = (
    os.getenv("JS_AST_EXTRACTOR_ENABLED", "false").strip().lower() == "true"
)
```

```python
if language in {"javascript", "typescript"} and JS_AST_EXTRACTOR_ENABLED:
    from .js_ast_extractor import JsAstExtractor
    return JsAstExtractor()
```

---

## Change 3 — Add golden tests

Add fixture files:
- `tests/fixtures/extractors/java_spring_sample.java` — a simple Spring controller with 3 methods
- `tests/fixtures/extractors/typescript_sample.ts` — async functions and interfaces

Add tests in `tests/services/test_language_extractor_golden.py`:

```python
@pytest.mark.skipif(
    not importlib.util.find_spec("javalang"),
    reason="javalang not installed",
)
def test_java_ast_extracts_methods():
    from pod_worker.java_ast_extractor import extract_java_ast
    source = open("tests/fixtures/extractors/java_spring_sample.java").read()
    result = extract_java_ast(source)
    assert result.success is True
    method_names = [m.name for m in result.methods]
    assert "getUser" in method_names
    assert "createUser" in method_names

@pytest.mark.skipif(
    not importlib.util.find_spec("esprima"),
    reason="esprima not installed",
)
def test_js_ast_extracts_functions():
    from pod_worker.js_ast_extractor import extract_js_ast
    source = open("tests/fixtures/extractors/typescript_sample.ts").read()
    result = extract_js_ast(source)
    assert result.success is True
    assert len(result.functions) >= 1
```

## Validation

- [x] `pip install javalang esprima` succeeds
- [x] Java golden test passes with real extraction
- [x] JS golden test passes with real extraction
- [x] TypeScript golden test passes with real extraction
- [x] Fallback to regex still works when env var is false

## Current status - implemented May 18, 2026

- `extract_java_ast()` uses `javalang` to parse packages, imports, classes,
  interfaces, enums, constructors, methods, parameters, modifiers, annotations,
  and signatures.
- `extract_js_ast()` uses `esprima` to parse JavaScript and a conservative
  TypeScript-stripped form for `.ts` source.
- `JavaAstExtractor` and `JavaScriptAstExtractor` enrich structural fields while
  preserving regex concept detection.
- `JS_AST_EXTRACTOR_ENABLED` and `JAVA_AST_EXTRACTOR_ENABLED` are wired through
  pod-worker selection and compose defaults.
