# Phases 8–11 — Full Smelt-Cycle
**Tier:** 3 — Complete 7-phase pipeline end-to-end

Document version: 2026.05.18  
Last updated: 2026-05-18  
Status: Implemented - Phases 8-11 complete

---

## Current Validation - May 18, 2026

Phases 8-11 are implemented as of the May 18 pass. The system now has FETCH
knowledge context, FUSION master logic stream support, DELIVERY/PM verification,
and source-safe Application Intelligence Maps for source-bearing analysis
missions.

Treat this document as the active forward plan with these adjustments:

- Phase 8 FETCH is implemented: IS Agent execution indexes deterministic
  bootstrap docs, mirrors them into mission-scoped knowledge, exposes
  `fetch_result`, and passes documentation context into pod extraction.
- Phase 9 FUSION is implemented: FUSION creates `master_logic_stream`, exposes
  it in chain trace/Mission Control, and can replace missing or fallback
  generated output when the stream is ready for codegen.
- Phase 10 DELIVERY is implemented: completed missions receive PM delivery
  summaries, chain trace exposes `delivery_summary`, and Mission Detail shows an
  artifact-aware delivery banner.
- Phase 11 AIM is implemented: source-bearing analysis/import/modernize/debug
  missions receive bounded source-bundle inventory, chain trace exposes
  `application_intelligence_map`, and Mission Detail shows the AIM panel.

Current chain trace exposes PM/CEO artifacts at top-level fields such as
`feature_contract`, `mission_charter`, `mission_contract`, `logic_clusters`,
`pod_group_standards`, and `generated_output`; new UI examples should read those
top-level fields directly.

---

## Phase 8 Code Validation — 2026-05-17

Validated against actual source code. All five Phase 8 components are unbuilt:

| Component | File | Status |
|---|---|---|
| IS Agent module | `orchestrator/is_agent.py` | ✗ File does not exist |
| `MissionState.fetch` enum value | `orchestrator/models.py` | ✗ Not in enum; `VALID_TRANSITIONS` has no FETCH entry |
| `_prepare_fetch_phase()` | `orchestrator/mission_flow_v2.py` | ✗ Function does not exist; `V2_TRANSITIONS` goes `pm_intake → ceo_delegated` directly |
| Pod worker knowledge context injection | `pod_worker/main.py` | ✗ No `_fetch_language_docs`, `doc_context`, or `knowledge_context` |
| FETCH in `MISSION_FLOW_V2_PHASES` | `app/lib/smelt-cycle.ts` | ✗ Not in v2 phase list (the old v1 `SMELT_PHASES` array has FETCH; the v2 list does not) |

**Foundation already in place — Phase 8 builds on:**
- `storage.upsert_knowledge` and `storage.list_knowledge` re-exported from `storage.py` via `storage_logicnodes.py` ✓
- `AGENT-06-IS` ("IS Agent") registered in `agent_registry.py` with `gemini_knowledge` routing ✓
- Internal knowledge API (`GET /internal/knowledge/{mission_id}`) already wired in `routes/internal.py` ✓
- Qdrant, Milvus, and Neo4j `upsert_knowledge` / `list_knowledge` all implemented ✓

**⚠ API mismatch in Change 1 design code:** The `is_agent.py` example calls
`qdrant_store.upsert_knowledge(collection=..., content=combined_string, metadata=...)`.
The actual `qdrant_store.upsert_knowledge` signature is:
`(settings: Settings, mission_id: str, knowledge_id: str, content: dict[str, Any], created_at: str)`.
Differences: no `collection` param (uses `settings.qdrant_collection` internally), `content`
must be a `dict` not a string, `metadata` is not a separate param (embed in `content`), and
`settings` + `created_at` are required. Use `storage.upsert_knowledge(settings, ...)` from
the storage facade rather than calling the qdrant module directly.

---

# Phase 8 — FETCH Phase: IS Agent and Knowledge Lake
**Duration:** 7–10 days

---

## Problem

Specialists extract structural patterns from source code (function names, class names,
regex concept matches) but have no documentation context. A specialist extracting
`numpy.linalg.solve()` cannot tell the CEO that this is a linear system solver
unless it knows what NumPy does. The IS Agent's job is to stock the Knowledge Lake
with documentation before extraction begins.

---

## Architecture

```
PM_INTAKE → [IS Agent fetches docs] → FETCH_COMPLETE → CEO_DELEGATED → ...
                        ↓
              Qdrant Knowledge Lake
                  (already running)
                        ↓
              Pod workers query docs
              before extraction
```

The IS Agent runs concurrently with PM_INTAKE, not sequentially. CEO delegation
waits for `knowledge_ready` before proceeding.

---

## Change 1 — Create `services/orchestrator/orchestrator/is_agent.py`

```python
"""is_agent.py — IS Agent: Knowledge Lake population for mission context."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

LOGGER = logging.getLogger(__name__)

# Static documentation seed for Phase 8 bootstrap.
# Each entry: language → list of (topic, content) tuples.
# In Phase 16 these are replaced with real crawled documentation.
_BOOTSTRAP_DOCS: dict[str, list[tuple[str, str]]] = {
    "python": [
        ("builtins.list", "list: ordered mutable sequence. Methods: append, extend, pop, "
                          "insert, remove, sort, reverse, count, index, copy, clear."),
        ("builtins.dict", "dict: key-value mapping. Methods: get, set, items, keys, values, "
                          "update, pop, setdefault, copy, clear."),
        ("builtins.str", "str: immutable text sequence. Methods: split, join, strip, replace, "
                         "find, format, encode, upper, lower, startswith, endswith."),
        ("io.file", "open(): open files for reading/writing. Modes: r, w, a, rb, wb. "
                    "Context manager with 'with' statement recommended."),
        ("itertools", "itertools: efficient looping. Functions: chain, cycle, repeat, "
                      "combinations, permutations, groupby, islice, product."),
        ("collections", "collections: specialized data structures. Classes: defaultdict, "
                        "OrderedDict, Counter, deque, namedtuple, ChainMap."),
        ("functools", "functools: higher-order functions. Functions: reduce, partial, "
                      "lru_cache, wraps, cached_property, total_ordering."),
        ("pathlib", "pathlib.Path: object-oriented filesystem paths. Methods: exists, "
                    "open, read_text, write_text, mkdir, glob, iterdir, stat."),
        ("json", "json: JSON encoding/decoding. Functions: loads, dumps, load, dump. "
                 "Handles: dict, list, str, int, float, bool, None."),
        ("re", "re: regular expressions. Functions: match, search, findall, sub, split, "
               "compile, fullmatch. Flags: IGNORECASE, MULTILINE, DOTALL."),
        ("typing", "typing: type hints. Types: Optional, Union, List, Dict, Tuple, "
                   "Set, Any, Callable, Iterator, Generator, TypeVar, Generic."),
        ("dataclasses", "dataclasses: data containers. Decorator: @dataclass. "
                        "Fields: field(), dataclass(frozen=True) for immutable."),
        ("asyncio", "asyncio: async I/O. Keywords: async def, await, async for, async with. "
                    "Functions: gather, sleep, create_task, run, Queue, Lock, Event."),
        ("requests", "requests: HTTP client. Methods: get, post, put, delete, patch, head. "
                     "Session for connection pooling. Response: .json(), .text, .status_code."),
        ("csv", "csv: CSV file reading/writing. Reader/DictReader for reading, "
                "Writer/DictWriter for writing. delimiter, quotechar parameters."),
        ("os", "os: operating system interface. Functions: getcwd, chdir, listdir, "
               "makedirs, remove, rename, environ, path.join, path.exists, path.dirname."),
    ],
    "javascript": [
        ("Array", "Array methods: map, filter, reduce, forEach, find, findIndex, some, every, "
                  "includes, indexOf, slice, splice, sort, reverse, flat, flatMap, fill."),
        ("Object", "Object methods: keys, values, entries, assign, create, freeze, "
                   "fromEntries, hasOwn. Spread operator for shallow copy."),
        ("String", "String methods: split, join, slice, substring, indexOf, includes, "
                   "startsWith, endsWith, replace, replaceAll, trim, padStart, padEnd, "
                   "toUpperCase, toLowerCase, match, search."),
        ("Promise", "Promise: async operations. Methods: then, catch, finally, "
                    "Promise.all, Promise.allSettled, Promise.race, Promise.any. "
                    "async/await syntax for cleaner code."),
        ("fetch", "fetch API: HTTP requests. Returns Promise<Response>. "
                  ".json() for JSON, .text() for text. Headers, body, method options."),
        ("Map", "Map: key-value collection preserving insertion order. Methods: set, get, "
                "has, delete, clear, forEach, keys, values, entries. Better than Object for data maps."),
        ("Set", "Set: unique value collection. Methods: add, has, delete, clear, forEach. "
                "Convert array to set to deduplicate: new Set(array)."),
        ("JSON", "JSON.parse(string): parse JSON string. JSON.stringify(value, null, 2): "
                 "serialize to JSON with formatting. Handles: object, array, string, number, boolean, null."),
        ("console", "console methods: log, error, warn, info, debug, table, time, timeEnd, "
                    "group, groupEnd, assert, trace, dir."),
        ("Math", "Math functions: floor, ceil, round, abs, max, min, pow, sqrt, random, "
                 "sin, cos, tan, log, PI, E. For big integers use BigInt."),
        ("Date", "Date: date/time. new Date() for current time. Methods: getTime, toISOString, "
                 "getFullYear, getMonth, getDate, getHours, getMinutes, getSeconds."),
        ("RegExp", "RegExp: regular expressions. Flags: g (global), i (case insensitive), "
                   "m (multiline), s (dotAll). Methods: test, exec. String: match, matchAll, replace."),
        ("Error", "Error types: Error, TypeError, RangeError, ReferenceError, SyntaxError. "
                  "Properties: message, name, stack. Custom errors: class MyError extends Error."),
        ("EventTarget", "addEventListener, removeEventListener, dispatchEvent. Common events: "
                        "click, input, change, submit, load, DOMContentLoaded, keydown, keyup, resize."),
    ],
    "java": [
        ("java.util.List", "List interface: ArrayList, LinkedList. Methods: add, get, set, remove, "
                           "size, isEmpty, contains, indexOf, subList, toArray, iterator."),
        ("java.util.Map", "Map interface: HashMap, TreeMap, LinkedHashMap. Methods: put, get, "
                          "remove, containsKey, containsValue, keySet, values, entrySet, size."),
        ("java.util.stream", "Stream API: filter, map, flatMap, reduce, collect, forEach, "
                              "sorted, distinct, limit, skip, count, findFirst, anyMatch, allMatch."),
        ("java.util.Optional", "Optional: null-safe container. Methods: of, ofNullable, empty, "
                               "get, isPresent, ifPresent, orElse, orElseGet, orElseThrow, map, flatMap, filter."),
        ("java.io", "File I/O: Files.readAllLines, Files.write, BufferedReader, FileReader, "
                    "FileWriter, Path, Paths.get. Try-with-resources for auto-closing."),
        ("java.lang.String", "String methods: length, charAt, substring, indexOf, contains, "
                              "startsWith, endsWith, toLowerCase, toUpperCase, trim, split, replace, format."),
        ("java.util.Collections", "Collections utility: sort, reverse, shuffle, min, max, "
                                  "frequency, unmodifiableList, synchronizedList, singletonList, emptyList."),
        ("java.util.concurrent", "Concurrency: ExecutorService, Future, CompletableFuture, "
                                 "AtomicInteger, ConcurrentHashMap, CountDownLatch, Semaphore."),
        ("annotations", "Common annotations: @Override, @Deprecated, @SuppressWarnings, "
                        "@FunctionalInterface, @NotNull. Spring: @Component, @Service, @Repository, @Bean."),
        ("exceptions", "Checked vs unchecked exceptions. Common: IOException, SQLException, "
                       "NullPointerException, IllegalArgumentException, IllegalStateException. "
                       "try-catch-finally, multi-catch, try-with-resources."),
    ],
}


async def run_fetch_phase(
    *,
    mission_id: str,
    required_languages: list[str],
    qdrant_store: Any,
    settings: Any,
) -> dict[str, Any]:
    """
    IS Agent execution: index documentation for required languages
    into the Knowledge Lake (Qdrant), then broadcast knowledge_ready.
    
    Phase 8 uses static bootstrap docs. Phase 16 replaces with live crawling.
    """
    indexed_languages: list[str] = []
    skipped_languages: list[str] = []
    errors: list[str] = []

    for language in required_languages:
        language_key = language.strip().lower()
        if language_key not in _BOOTSTRAP_DOCS:
            skipped_languages.append(language_key)
            continue

        try:
            docs = _BOOTSTRAP_DOCS[language_key]
            knowledge_id = f"docs.{language_key}.bootstrap"

            # Check if already indexed for this collection
            existing = await asyncio.to_thread(
                _check_knowledge_exists,
                settings=settings,
                mission_id="__knowledge_lake__",
                knowledge_id=knowledge_id,
            )
            if existing:
                indexed_languages.append(language_key)
                continue

            # Build documentation content
            content_parts = []
            for topic, description in docs:
                content_parts.append(f"## {topic}\n{description}")
            combined = f"# {language_key} Language Reference\n\n" + "\n\n".join(content_parts)
            content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]

            # Store in Qdrant (using existing qdrant_store infrastructure)
            if qdrant_store is not None:
                try:
                    await asyncio.to_thread(
                        qdrant_store.upsert_knowledge,
                        collection=f"lang_docs_{language_key}",
                        knowledge_id=knowledge_id,
                        content=combined,
                        metadata={
                            "language": language_key,
                            "kind": "bootstrap_documentation",
                            "hash": content_hash,
                            "indexed_at": datetime.now(UTC).isoformat(),
                        },
                    )
                except Exception as exc:
                    LOGGER.warning("qdrant store failed for %s: %s", language_key, exc)
                    # Store in PostgreSQL knowledge as fallback
                    pass

            indexed_languages.append(language_key)
            LOGGER.info("IS Agent indexed %s documentation (%d topics)", language_key, len(docs))

        except Exception as exc:
            LOGGER.warning("IS Agent failed to index %s: %s", language_key, exc)
            errors.append(f"{language_key}: {exc}")

    return {
        "indexed_languages": indexed_languages,
        "skipped_languages": skipped_languages,
        "errors": errors,
        "knowledge_ready": len(indexed_languages) > 0,
        "indexed_at": datetime.now(UTC).isoformat(),
    }


def _check_knowledge_exists(*, settings: Any, mission_id: str, knowledge_id: str) -> bool:
    """Check if knowledge already indexed. Returns False if check fails."""
    try:
        from .storage import list_knowledge
        records = list_knowledge(settings, mission_id, limit=1)
        return any(r.get("knowledge_id") == knowledge_id for r in records)
    except Exception:
        return False


def detect_required_languages(
    *,
    prompt: str,
    requested_target_language: str | None,
    source_code: str | None,
    mission_type: str,
) -> list[str]:
    """Determine which languages the IS Agent should index docs for."""
    languages = set()

    if requested_target_language:
        languages.add(requested_target_language.strip().lower())

    # Detect from source code content
    if source_code:
        import re
        # Look for import statements as language signals
        if re.search(r"^import |^from .+ import ", source_code, re.MULTILINE):
            languages.add("python")
        if re.search(r"^import .+;|^require\(", source_code, re.MULTILINE):
            languages.add("javascript")
        if re.search(r"^import [a-zA-Z]", source_code, re.MULTILINE):
            if "java" in source_code.lower() or ".java" in prompt.lower():
                languages.add("java")

    # Always include the target language
    if not languages and requested_target_language:
        languages.add(requested_target_language.strip().lower())
    elif not languages:
        languages.add("python")  # default

    return sorted(languages)
```

---

## Change 2 — Add FETCH state to mission lifecycle

In `services/orchestrator/orchestrator/models.py`:

```python
class MissionState(str, Enum):
    intake = "INTAKE"
    queued = "QUEUED"
    pm_intake = "PM_INTAKE"
    fetch = "FETCH"             # ← ADD THIS
    ceo_delegated = "CEO_DELEGATED"
    # ... rest unchanged
```

Update `VALID_TRANSITIONS` to include the new state:
```python
(MissionState.pm_intake, MissionState.fetch),
(MissionState.fetch, MissionState.ceo_delegated),
# Keep the old direct path as well for backward compat:
(MissionState.pm_intake, MissionState.ceo_delegated),  # skip FETCH if no source
```

Update `V2_TRANSITIONS` in `mission_flow_v2.py` similarly.

---

## Change 3 — Add `_prepare_fetch_phase()` to `mission_flow_v2.py`

```python
async def _prepare_fetch_phase(
    *,
    app: Any,
    settings: Any,
    validator: Any,
    emit_state_event_fn: Any,
    mission_id: str,
) -> bool:
    from .is_agent import run_fetch_phase, detect_required_languages

    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)

    # Detect languages to index
    languages = detect_required_languages(
        prompt=mission.prompt or "",
        requested_target_language=mission.requested_target_language,
        source_code=metadata.get("source_code"),
        mission_type=metadata.get("mission_type", "BUILD_NEW"),
    )

    # Run IS Agent
    qdrant = getattr(app.state, "qdrant", None)
    fetch_result = await run_fetch_phase(
        mission_id=mission_id,
        required_languages=languages,
        qdrant_store=qdrant,
        settings=settings,
    )

    metadata["fetch_result"] = fetch_result
    metadata["knowledge_lake_ready"] = fetch_result["knowledge_ready"]

    if not _chain_event_exists(metadata, "MISSION_FETCH_COMPLETE"):
        append_chain_event(
            metadata,
            event_type="MISSION_FETCH_COMPLETE",
            agent_id="AGENT-06-IS",
            details={
                "indexed_languages": fetch_result["indexed_languages"],
                "skipped": fetch_result["skipped_languages"],
                "errors": fetch_result["errors"],
            },
        )

    return (
        await _persist_metadata(
            app=app,
            settings=settings,
            validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission_id,
            metadata=metadata,
        )
        is not None
    )
```

---

## Change 4 — Skip FETCH for missions with no source code

For `BUILD_NEW` missions with no `source_code`, FETCH is minimal (just index target language docs).
For `ANALYZE_ONLY`, `IMPORT_MODERNIZE`, `PORT` missions FETCH is critical.

In the lifecycle transition logic, add:
```python
# If mission has no source code and is BUILD_NEW, skip FETCH (use inline docs)
if (
    not metadata.get("source_code")
    and metadata.get("mission_type", "BUILD_NEW") == "BUILD_NEW"
):
    # Go directly from PM_INTAKE to CEO_DELEGATED (existing path)
    return await _advance_to_ceo_delegated(...)
else:
    # Run FETCH phase first
    return await _advance_to_fetch(...)
```

---

## Change 5 — Inject knowledge context into pod-worker extraction

In `services/pod-worker/pod_worker/main.py`, in `_handle_running_mission()`,
after fetching `mission_metadata`, query the language documentation:

```python
# Query Knowledge Lake for relevant documentation context
knowledge_context = await _fetch_language_docs(
    language=extraction_language,
    concepts=list({c.concept for c in extractor.get_concept_list() if hasattr(c, "concept")}),
)

# Pass to extractor as documentation hints
if knowledge_context:
    result = extractor.extract(source_code, doc_context=knowledge_context)
else:
    result = extractor.extract(source_code)
```

Add `_fetch_language_docs()` helper that queries the orchestrator's internal
knowledge API for bootstrap docs matching the language:

```python
async def _fetch_language_docs(language: str, concepts: list[str]) -> str | None:
    try:
        response = await _request(
            "GET",
            f"/internal/knowledge/__knowledge_lake__",
            params={"prefix": f"docs.{language}"},
        )
        if response.status_code == 200:
            records = response.json()
            if records:
                return records[0].get("content", {}).get("combined_text")
    except Exception:
        pass
    return None
```

Update `LanguageExtractor.extract()` to accept optional `doc_context: str | None`
and embed it in the concept-catalog matching logic as additional pattern hints.
This is a quality enhancement — the regex patterns still run first, doc context
improves domain classification of matched concepts.

---

## Validation

- [x] FETCH state appears in mission timeline on Mission Detail page
- [x] `metadata.fetch_result.indexed_languages` contains the target language
- [x] Chain trace shows `MISSION_FETCH_COMPLETE` event
- [x] BUILD_NEW missions receive lightweight target-language FETCH context
- [x] IMPORT_MODERNIZE/source missions pass through FETCH
- [x] Targeted Phase 8/9 pytest, ruff, and Mission Control typecheck pass
- [x] `smelt-cycle.ts` includes FETCH and `MISSION_FETCH_COMPLETE` in the v2 phase map

---

# Phase 9 — FUSION Phase: CEO Logic Folding
**Duration:** 5–7 days

---

## Problem

The FUSION state fires in the mission lifecycle but nothing executes during it.
The CEO has all pod group standards available (from Phase 6) but does not synthesize
them. Without real FUSION, the specialist that generates code (Phase 2) works from
its own pod's logicnodes only — it cannot benefit from patterns found in other pods.

---

## Change 1 — Add `generate_master_logic_stream()` to `llm_delegation.py`

```python
async def generate_master_logic_stream(
    *,
    pod_group_standards: dict[str, dict[str, Any]],
    mission_contract: dict[str, Any],
    mission_context: dict[str, Any],
) -> dict[str, Any]:
    """CEO fuses pod Group Standards into unified Master Logic Stream."""
    if not pod_group_standards:
        return {
            "master_logic_stream": [],
            "total_unified_nodes": 0,
            "eliminated_across_pods": 0,
            "ready_for_codegen": False,
            "source": "empty",
        }

    recommendation = _ceo_recommendation()
    provider = recommendation["provider"]
    model = recommendation["model"]

    # Build input summary for the prompt
    pods_summary = []
    total_input_nodes = 0
    for pod_name, standard in pod_group_standards.items():
        nodes = standard.get("canonical_logicnodes") or []
        total_input_nodes += len(nodes)
        node_summaries = [
            {"domain": n.get("domain"), "concept": n.get("concept"),
             "intent": n.get("intent")}
            for n in nodes[:15]
        ]
        pods_summary.append({
            "pod": pod_name,
            "node_count": len(nodes),
            "nodes": node_summaries,
        })

    contract_summary = mission_contract.get("contract_summary", "")
    required_domains = mission_contract.get("required_domains") or []
    acceptance_criteria = mission_contract.get("acceptance_criteria") or []

    prompt = (
        "You are AGENT-02-CEO performing Logic Folding — the Grand Fusion.\n"
        "Merge LogicNodes from all pods into a single ordered Master Logic Stream.\n"
        "Remove cross-pod duplicates. Order nodes by dependency (inputs before outputs).\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission: {_clean_text(contract_summary, max_length=300)}\n"
        f"Required domains: {json.dumps(required_domains[:10])}\n"
        f"Acceptance criteria: {json.dumps(acceptance_criteria[:4])}\n"
        f"Total input nodes across all pods: {total_input_nodes}\n"
        f"Pod inputs:\n{json.dumps(pods_summary, indent=2)}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "master_logic_stream": [\n'
        '    {"node_id": "unified-001", "domain": "domain", "concept": "concept",\n'
        '     "canonical_intent": "intent", "source_pods": ["podA"], '
        '"dependency_order": 1}\n'
        "  ],\n"
        '  "total_unified_nodes": 18,\n'
        '  "eliminated_across_pods": 4,\n'
        '  "ready_for_codegen": true\n'
        "}\n\n"
        "Keep master_logic_stream to 5–25 nodes for a clean codegen prompt.\n"
        "Order by dependency_order (lowest first = most fundamental).\n"
    )

    parsed, resolved_provider, resolved_model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context="ceo logic fusion",
    )

    if not isinstance(parsed, dict):
        # Fallback: flatten all pod nodes and deduplicate by concept name
        all_nodes = []
        seen_concepts = set()
        order = 1
        for standard in pod_group_standards.values():
            for node in (standard.get("canonical_logicnodes") or [])[:10]:
                concept = str(node.get("concept") or "")
                if concept not in seen_concepts:
                    seen_concepts.add(concept)
                    all_nodes.append({
                        "node_id": f"unified-{order:03d}",
                        "domain": node.get("domain", "generic"),
                        "concept": concept,
                        "canonical_intent": node.get("intent", ""),
                        "source_pods": [list(pod_group_standards.keys())[0]],
                        "dependency_order": order,
                    })
                    order += 1
        return {
            "master_logic_stream": all_nodes[:20],
            "total_unified_nodes": len(all_nodes),
            "eliminated_across_pods": max(0, total_input_nodes - len(all_nodes)),
            "ready_for_codegen": len(all_nodes) > 0,
            "source": "fallback",
        }

    stream = parsed.get("master_logic_stream") or []
    if not isinstance(stream, list):
        stream = []

    return {
        "master_logic_stream": stream[:25],
        "total_unified_nodes": int(parsed.get("total_unified_nodes") or len(stream)),
        "eliminated_across_pods": int(parsed.get("eliminated_across_pods") or 0),
        "ready_for_codegen": bool(parsed.get("ready_for_codegen", True)),
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
    }
```

---

## Change 2 — Wire FUSION execution into mission_flow_v2.py

In `_prepare_fusion()` (or create it if it doesn't execute):

```python
async def _prepare_fusion(
    *,
    app, settings, validator, emit_state_event_fn, mission_id,
) -> bool:
    from .llm_delegation import generate_master_logic_stream

    mission = await asyncio.to_thread(storage.fetch_mission, settings, mission_id)
    if mission is None:
        return False

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)

    pod_group_standards = metadata.get("pod_group_standards") or {}
    mission_contract = metadata.get("mission_contract") or {}

    if not pod_group_standards:
        # No group standards yet — proceed without fusion
        return True

    master_stream = await generate_master_logic_stream(
        pod_group_standards=pod_group_standards,
        mission_contract=mission_contract,
        mission_context=_mission_context(mission, metadata),
    )
    metadata["master_logic_stream"] = master_stream

    # Update generated_output to use master stream if codegen has not yet run
    # (or re-run codegen with the richer master stream input)
    if not mission_has_generated_output(metadata) and master_stream.get("ready_for_codegen"):
        specialist_agent_id = metadata.get("assigned_specialist_agent_id") or \
            resolve_specialist_agent_id(mission.requested_target_language)
        generated_output = await generate_code_from_contract(
            mission_context=_mission_context(mission, metadata),
            specialist_agent_id=specialist_agent_id,
            mission_contract=mission_contract,
            logicnodes=master_stream.get("master_logic_stream") or [],
            target_language=mission.requested_target_language or "python",
        )
        metadata["generated_output"] = generated_output

    if not _chain_event_exists(metadata, "MISSION_LOGIC_FOLDED"):
        append_chain_event(
            metadata,
            event_type="MISSION_LOGIC_FOLDED",
            agent_id=CEO_AGENT_ID,
            details={
                "unified_nodes": master_stream["total_unified_nodes"],
                "eliminated": master_stream["eliminated_across_pods"],
                "ready_for_codegen": master_stream["ready_for_codegen"],
                "source": master_stream.get("source"),
            },
        )

    return (
        await _persist_metadata(
            app=app, settings=settings, validator=validator,
            emit_state_event_fn=emit_state_event_fn,
            mission_id=mission_id, metadata=metadata,
        ) is not None
    )
```

---

## Change 3 — Display Master Logic Stream on Mission Detail page

Add a "Master Logic Stream" collapsible panel in the Mission Detail page
when `chainTrace?.master_logic_stream?.master_logic_stream?.length > 0`:

```tsx
{masterStream?.master_logic_stream?.length > 0 && (
  <Panel title="Master Logic Stream" collapsible defaultCollapsed>
    <div className="stream-summary">
      <span>{masterStream.total_unified_nodes} unified nodes</span>
      <span>{masterStream.eliminated_across_pods} duplicates eliminated</span>
    </div>
    <table className="logicnode-table">
      <thead><tr><th>#</th><th>Domain</th><th>Concept</th><th>Intent</th><th>Pods</th></tr></thead>
      <tbody>
        {masterStream.master_logic_stream.map((node: any) => (
          <tr key={node.node_id}>
            <td>{node.dependency_order}</td>
            <td>{node.domain}</td>
            <td>{node.concept}</td>
            <td>{node.canonical_intent}</td>
            <td>{(node.source_pods || []).join(", ")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </Panel>
)}
```

## Validation

- [x] Chain trace shows `MISSION_LOGIC_FOLDED` event after FUSION state
- [x] `master_logic_stream.total_unified_nodes` is exposed in chain trace
- [x] Multiple pod outputs can report `eliminated_across_pods`
- [x] Missing or fallback generated output can be replaced from a ready master stream
- [x] Mission Detail shows Master Logic Stream panel
- [x] Targeted Phase 8/9 pytest, ruff, and Mission Control typecheck pass

---

# Phase 10 — DELIVERY Phase: PM Output Presentation
**Duration:** 3–4 days

---

## Problem

When a mission reaches COMPLETE, there is no closing action. The operator can find
the generated code by digging into the chain trace metadata, but there is no
prominent "your code is ready" moment. This breaks the product experience — the
user submitted a request and received no clear response.

---

## Change 1 — Add `generate_pm_delivery_summary()` to `llm_delegation.py`

```python
async def generate_pm_delivery_summary(
    *,
    mission_context: dict[str, Any],
    generated_output: dict[str, Any],
    build_artifacts: list[dict[str, Any]],
    feature_contract: dict[str, Any],
    mission_contract: dict[str, Any],
) -> dict[str, Any]:
    """PM Agent produces delivery summary validating output against intent."""
    recommendation = _agent_recommendation("AGENT-01-PM")
    provider = recommendation["provider"]
    model = recommendation["model"]

    primary_artifact = next(
        (artifact for artifact in build_artifacts if artifact.get("artifact_type") == "generated_code"),
        build_artifacts[0] if build_artifacts else {},
    )
    manifest = primary_artifact.get("manifest") if isinstance(primary_artifact, dict) else {}
    artifact_text = primary_artifact.get("artifact_text") if isinstance(primary_artifact, dict) else ""
    code_preview = str(generated_output.get("generated_code") or artifact_text or "")[:600]
    filename = generated_output.get("filename") or manifest.get("filename") or "mission artifact"
    language = generated_output.get("language") or manifest.get("language") or "unknown"
    criteria = feature_contract.get("acceptance_criteria") or \
                mission_contract.get("acceptance_criteria") or []
    contract_summary = mission_contract.get("contract_summary") or ""

    prompt = (
        "You are AGENT-01-PM. The mission is complete. Produce a delivery summary.\n"
        f"Recommended model: {provider}/{model}\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission: {_clean_text(contract_summary, max_length=300)}\n"
        f"Delivered file: {filename} ({language})\n"
        f"Code preview:\n{_clean_text(code_preview, max_length=600)}\n"
        f"Acceptance criteria: {json.dumps(criteria[:4])}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "delivery_title": "short title for what was delivered",\n'
        '  "delivery_summary": "1-2 sentence summary for the operator",\n'
        '  "criteria_met": ["criteria that appear to be satisfied"],\n'
        '  "criteria_unmet": ["criteria that may need verification"],\n'
        '  "usage_notes": "how to run or use the delivered code",\n'
        '  "recommendations": ["optional follow-up suggestions"]\n'
        "}\n"
    )

    parsed, resolved_provider, resolved_model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context="pm delivery summary",
    )

    if not isinstance(parsed, dict):
        return {
            "delivery_title": f"Delivered: {filename}",
            "delivery_summary": f"Mission complete. {filename} generated successfully.",
            "criteria_met": [],
            "criteria_unmet": criteria,
            "usage_notes": "Open the delivered artifact and verify it against the acceptance criteria.",
            "recommendations": [],
            "primary_artifact_type": primary_artifact.get("artifact_type"),
            "source": "fallback",
        }

    return {
        "delivery_title": _clean_text(
            parsed.get("delivery_title", f"Delivered: {filename}"), max_length=120
        ),
        "delivery_summary": _clean_text(
            parsed.get("delivery_summary", "Mission complete."), max_length=500
        ),
        "criteria_met": _string_list(parsed.get("criteria_met"), limit=6),
        "criteria_unmet": _string_list(parsed.get("criteria_unmet"), limit=6),
        "usage_notes": _clean_text(parsed.get("usage_notes", ""), max_length=300),
        "recommendations": _string_list(parsed.get("recommendations"), limit=4),
        "primary_artifact_type": primary_artifact.get("artifact_type"),
        "source": "llm",
        "model_provider": resolved_provider,
        "model": resolved_model,
    }
```

## Change 2 — Call delivery summary after the completion gate

In `mission_flow_v2.py`, generate delivery only after `completion_check_fn()`
returns ready and after `_ensure_verified_build_artifact()` has packaged the
current artifact. If the mission is blocked at VERIFIED, keep the existing
`MISSION_COMPLETION_BLOCKED` behavior and do not write `delivery_summary`.

```python
build_artifacts = await asyncio.to_thread(
    storage.list_build_artifacts, settings, mission_id, 50
)
delivery_summary = await generate_pm_delivery_summary(
    mission_context=_mission_context(mission, metadata),
    generated_output=metadata.get("generated_output") or {},
    build_artifacts=build_artifacts,
    feature_contract=metadata.get("feature_contract") or {},
    mission_contract=metadata.get("mission_contract") or {},
)
metadata["delivery_summary"] = delivery_summary
append_chain_event(
    metadata,
    event_type="MISSION_DELIVERED",
    agent_id="AGENT-01-PM",
    details={
        "delivery_title": delivery_summary["delivery_title"],
        "artifact_type": delivery_summary.get("primary_artifact_type"),
        "criteria_met_count": len(delivery_summary["criteria_met"]),
        "source": delivery_summary.get("source"),
    },
)
```

## Change 3 — Mission Detail delivery banner

In `apps/mission-control/app/(shell)/missions/[id]/page.tsx`,
when `mission.state === "COMPLETE"`, render a prominent delivery banner at the top:

```tsx
{mission?.state === "COMPLETE" && chainTrace?.delivery_summary && (
  <div className="delivery-banner">
    <div className="delivery-banner-icon">✓</div>
    <div className="delivery-banner-content">
      <h2>{chainTrace.delivery_summary.delivery_title}</h2>
      <p>{chainTrace.delivery_summary.delivery_summary}</p>
      {chainTrace.delivery_summary.usage_notes && (
        <p className="usage-notes muted">
          {chainTrace.delivery_summary.usage_notes}
        </p>
      )}
    </div>
    <div className="delivery-banner-actions">
      {generatedCodeArtifact && (
        <a
          href={missionApiUrl(
            `/v1/missions/${encodeURIComponent(missionId)}/artifact?artifact_type=generated_code`,
          )}
          className="primary-button"
        >
          Download Generated Code
        </a>
      )}
    </div>
  </div>
)}
```

Add CSS for `.delivery-banner`:
```css
.delivery-banner {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-4);
  background: color-mix(in srgb, var(--success) 12%, var(--surface));
  border: 1px solid var(--success);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}
```

## Validation

- [x] Chain trace shows `MISSION_DELIVERED` event at COMPLETE
- [x] `metadata.delivery_summary.delivery_title` is specific to the mission output
- [x] Chain trace exposes `delivery_summary` at top level
- [x] Mission Detail shows delivery banner when state=COMPLETE and delivery summary exists
- [x] Generated-code download uses `/v1/missions/{mission_id}/artifact?artifact_type=generated_code`
- [x] Source-bundle-only and ANALYZE_ONLY missions get delivery text without generated-code-only wording
- [x] Missions blocked at VERIFIED do not show delivery summary or delivery banner
- [x] Targeted pytest, ruff, and Mission Control typecheck pass

---

# Phase 11 — Application Intelligence Map (AIM)
**Duration:** 5–7 days

---

## Problem

IMPORT_MODERNIZE, PORT, DEBUG_REPAIR, SECURITY_HARDEN, and ANALYZE_ONLY missions
have no pre-analysis step. The factory starts working on a repo before understanding
what is in it. The AIM must be produced before any changes happen.

---

## Validated plan update - 2026-05-18

Repo review confirmed the source-bundle path is already real: Mission Control and
the API gateway can pass `metadata.source_code`, build artifacts can parse
`## FILE ...` bundles, and Phase 7 extractors cover Python, JavaScript,
TypeScript, and Java. Phase 11 should reuse those surfaces instead of creating a
raw-source LLM prompt.

Implementation constraints:

- Generate AIM only for source-bearing `ANALYZE_ONLY`, `IMPORT_MODERNIZE`,
  `PORT`, `DEBUG_REPAIR`, `SECURITY_HARDEN`, and `REDUCE_DEPENDENCIES`
  missions. `BUILD_NEW` with no `source_code` must skip AIM.
- Run AIM after PM feature-contract generation and before CEO delegation,
  specialist codegen, or modification work. At this point the durable
  `mission_contract` has not been created yet, so use `feature_contract`,
  mission metadata, and source inventory as AIM inputs.
- Never include raw `source_code` in the LLM prompt. Build a bounded extraction
  summary containing file manifest, detected languages, counts, imports,
  domains, and truncation flags.
- Parse multi-file bundles and infer language per file. Do not run one
  extractor across the entire bundle based only on `requested_target_language`.
- Store `metadata["application_intelligence_map"]`, expose it through chain
  trace/internal API responses, render it in Mission Control, and append
  `MISSION_AIM_GENERATED`.
- Store high-risk findings and approval recommendations as AIM metadata in
  Phase 11. A blocking human approval gate is a follow-on quality/trust item
  unless it is explicitly implemented in this phase.

---

## Change 1 — Create `services/orchestrator/orchestrator/aim_generator.py`

```python
"""aim_generator.py — Application Intelligence Map generator."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

LOGGER = logging.getLogger(__name__)

AIM_REQUIRING_MISSION_TYPES = {
    "IMPORT_MODERNIZE", "PORT", "DEBUG_REPAIR",
    "SECURITY_HARDEN", "REDUCE_DEPENDENCIES", "ANALYZE_ONLY",
}


def mission_requires_aim(mission_type: str) -> bool:
    return mission_type.strip().upper() in AIM_REQUIRING_MISSION_TYPES


async def generate_aim(
    *,
    mission_id: str,
    source_code: str,
    prompt: str,
    mission_type: str,
    requested_target_language: str | None,
    feature_contract: dict[str, Any],
    settings: Any,
) -> dict[str, Any]:
    """Generate Application Intelligence Map from source code."""
    from .llm_delegation import _ceo_recommendation, _call_with_recommendation, _clean_text

    # Run all language extractors on the source bundle
    extraction_summary = await _extract_all_languages(source_code, requested_target_language)

    # CEO LLM call to synthesize findings into structured AIM
    recommendation = _ceo_recommendation()
    provider = recommendation["provider"]
    model = recommendation["model"]

    prompt_text = (
        "You are AGENT-02-CEO performing Application Intelligence Map generation.\n"
        "Analyze this source code extraction and produce a comprehensive read-only map.\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission type: {mission_type}\n"
        f"Operator request: {_clean_text(prompt, max_length=300)}\n"
        f"Target language: {requested_target_language or 'auto'}\n"
        f"Feature contract: {json.dumps(feature_contract, default=str)[:2000]}\n"
        f"Extraction summary:\n{json.dumps(extraction_summary, indent=2)}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "repository_summary": "1-2 sentences describing the codebase",\n'
        '  "detected_languages": ["list of languages found"],\n'
        '  "primary_language": "most common language",\n'
        '  "total_functions": 0,\n'
        '  "total_classes": 0,\n'
        '  "domain_distribution": {"domain": count},\n'
        '  "complexity_assessment": "low | medium | high | very_high",\n'
        '  "key_patterns": ["important patterns found"],\n'
        '  "detected_dependencies": ["library names found in imports"],\n'
        '  "risks": ["potential issues or concerns"],\n'
        '  "risk_flags": ["security | migration | dependency | data | approval"],\n'
        '  "human_approval_recommended": false,\n'
        '  "recommended_approach": "suggested strategy for this mission type",\n'
        '  "recommended_mission_type": "most appropriate mission type"\n'
        "}\n"
    )

    parsed, resolved_provider, resolved_model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt_text,
        call_context="aim generation",
    )

    aim_base = {
        "schema": "aim.v1",
        "aim_id": f"aim-{mission_id}",
        "mission_id": mission_id,
        "mission_type": mission_type,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "llm" if isinstance(parsed, dict) else "fallback",
        "model_provider": resolved_provider,
        "model": resolved_model,
        "extraction_summary": extraction_summary,
    }

    if isinstance(parsed, dict):
        aim_base.update({
            "repository_summary": parsed.get("repository_summary", ""),
            "detected_languages": parsed.get("detected_languages") or [],
            "primary_language": parsed.get("primary_language") or requested_target_language,
            "total_functions": int(parsed.get("total_functions") or
                                   extraction_summary.get("total_functions", 0)),
            "total_classes": int(parsed.get("total_classes") or
                                 extraction_summary.get("total_classes", 0)),
            "domain_distribution": parsed.get("domain_distribution") or {},
            "complexity_assessment": parsed.get("complexity_assessment", "medium"),
            "key_patterns": parsed.get("key_patterns") or [],
            "detected_dependencies": parsed.get("detected_dependencies") or
                                      extraction_summary.get("detected_imports", []),
            "risks": parsed.get("risks") or [],
            "risk_flags": parsed.get("risk_flags") or [],
            "human_approval_recommended": bool(parsed.get("human_approval_recommended", False)),
            "recommended_approach": parsed.get("recommended_approach", ""),
            "recommended_mission_type": parsed.get("recommended_mission_type", mission_type),
        })
    else:
        aim_base.update({
            "repository_summary": f"Source code analysis for {mission_type} mission.",
            "detected_languages": [requested_target_language] if requested_target_language else [],
            "primary_language": requested_target_language,
            "total_functions": extraction_summary.get("total_functions", 0),
            "total_classes": extraction_summary.get("total_classes", 0),
            "domain_distribution": extraction_summary.get("domain_counts", {}),
            "complexity_assessment": "medium",
            "key_patterns": [],
            "detected_dependencies": extraction_summary.get("detected_imports", []),
            "risks": [],
            "risk_flags": [],
            "human_approval_recommended": False,
            "recommended_approach": "Proceed with standard extraction and analysis.",
            "recommended_mission_type": mission_type,
        })

    return aim_base


async def _extract_all_languages(
    source_code: str, primary_language: str | None
) -> dict[str, Any]:
    """Run per-file extractors on a bounded source bundle for AIM."""
    try:
        import sys
        from pathlib import Path
        pod_worker_root = Path(__file__).resolve().parents[3] / "services" / "pod-worker"
        if str(pod_worker_root) not in sys.path:
            sys.path.insert(0, str(pod_worker_root))
        from pod_worker.language_extractor import get_extractor

        # Implement these as local helpers or reuse the existing source-bundle
        # parser shape from build_artifacts.py. They must return bounded file
        # entries and map extensions such as .py, .js, .ts, .tsx, and .java.
        files = _parse_source_bundle(source_code)
        domain_counts: dict[str, int] = {}
        detected_imports: list[str] = []
        detected_languages: set[str] = set()
        total_functions = 0
        total_classes = 0
        total_concepts = 0

        for file_item in files[:100]:
            language = _infer_language(file_item["path"], primary_language)
            if language not in {"python", "javascript", "typescript", "java"}:
                continue
            detected_languages.add(language)
            extractor = get_extractor(language)
            result = extractor.extract(file_item["content"][:200_000])
            total_functions += len(getattr(result, "functions", []) or [])
            total_classes += len(getattr(result, "classes", []) or [])
            concepts = getattr(result, "concepts", []) or []
            total_concepts += len(concepts)
            for concept in concepts:
                domain = getattr(concept, "domain", "generic")
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                if domain == "import":
                    detected_imports.append(getattr(concept, "concept", ""))

        return {
            "files_seen": len(files),
            "files_analyzed": min(len(files), 100),
            "truncated": len(files) > 100 or len(source_code) > 2_000_000,
            "detected_languages": sorted(detected_languages),
            "primary_language": primary_language,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "total_concepts": total_concepts,
            "domain_counts": domain_counts,
            "detected_imports": sorted({item for item in detected_imports if item})[:50],
        }
    except Exception as exc:
        LOGGER.warning("AIM extraction failed: %s", exc)
        return {
            "language": primary_language or "unknown",
            "total_functions": 0, "total_classes": 0,
            "total_concepts": 0, "domain_counts": {},
            "detected_imports": [],
        }
```

## Change 2 — Wire AIM generation into PM_INTAKE for analysis missions

In `_prepare_pm_intake()` in `mission_flow_v2.py`, after PM feature contract:

```python
from .aim_generator import mission_requires_aim, generate_aim

if mission_requires_aim(metadata.get("mission_type", "BUILD_NEW")) \
        and metadata.get("source_code"):
    aim = await generate_aim(
        mission_id=mission_id,
        source_code=metadata["source_code"],
        prompt=mission.prompt or "",
        mission_type=metadata.get("mission_type", "ANALYZE_ONLY"),
        requested_target_language=mission.requested_target_language,
        feature_contract=metadata.get("feature_contract") or {},
        settings=settings,
    )
    metadata["application_intelligence_map"] = aim
    append_chain_event(
        metadata,
        event_type="MISSION_AIM_GENERATED",
        agent_id="AGENT-02-CEO",
        details={
            "aim_id": aim["aim_id"],
            "primary_language": aim["primary_language"],
            "total_functions": aim["total_functions"],
            "complexity": aim["complexity_assessment"],
            "source": aim["source"],
        },
    )
```

## Change 3 — Add AIM viewer to Mission Detail page

When `chainTrace?.application_intelligence_map` is present:

```tsx
{aim && (
  <Panel title="Application Intelligence Map" collapsible>
    <div className="aim-summary">
      <p>{aim.repository_summary}</p>
      <div className="aim-stats">
        <MetricCard title="Functions" value={aim.total_functions} />
        <MetricCard title="Classes" value={aim.total_classes} />
        <MetricCard title="Complexity" value={aim.complexity_assessment} />
        <MetricCard title="Primary Language" value={aim.primary_language} />
      </div>
    </div>
    {aim.detected_dependencies?.length > 0 && (
      <div>
        <strong>Detected Dependencies:</strong>
        <div className="chip-list">
          {aim.detected_dependencies.map((dep: string) =>
            <span key={dep} className="chip">{dep}</span>
          )}
        </div>
      </div>
    )}
    {aim.risks?.length > 0 && (
      <div>
        <strong>Risks:</strong>
        <ul>{aim.risks.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
      </div>
    )}
    {aim.recommended_approach && (
      <div><strong>Recommended Approach:</strong> {aim.recommended_approach}</div>
    )}
  </Panel>
)}
```

## Validation

- [x] ANALYZE_ONLY mission with attached source file produces AIM in chain trace
- [x] `metadata.application_intelligence_map.repository_summary` is meaningful
- [x] AIM prompt uses bounded extraction summary and excludes raw `source_code`
- [x] Multi-file source bundles are parsed per file and per detected language
- [x] BUILD_NEW missions without source do NOT produce an AIM
- [x] Mission Detail shows AIM panel for analysis missions
- [x] Chain trace includes `MISSION_AIM_GENERATED` event
- [x] Targeted backend tests pass:
  `python -m pytest tests\services\test_mission_flow_v2.py tests\services\test_orchestrator_endpoints_extra.py tests\services\test_language_extractor.py tests\services\test_llm_delegation_unit.py -q`
- [x] Targeted ruff passes for orchestrator, pod-worker extractor, and touched tests
- [x] Mission Control lint/typecheck passes:
  `npm --prefix apps\mission-control run lint`
