"""is_agent.py — IS Agent: Knowledge Lake population for mission context.

Phase 8 bootstrap: indexes static language reference docs into the Knowledge
Lake (storage layer) so pod workers can query documentation context during
extraction. Phase 16 adds refresh detection and shared embedding metadata.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Any

LOGGER = logging.getLogger(__name__)

# Static documentation seed for Phase 8.
# Each entry: language_key → list of (topic, content) tuples.
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
                "has, delete, clear, forEach, keys, values, entries."),
        ("Set", "Set: unique value collection. Methods: add, has, delete, clear, forEach. "
                "Convert array to set to deduplicate: new Set(array)."),
        ("JSON", "JSON.parse(string): parse JSON string. JSON.stringify(value): serialize to JSON. "
                 "Handles: object, array, string, number, boolean, null."),
        ("Math", "Math functions: floor, ceil, round, abs, max, min, pow, sqrt, random, "
                 "sin, cos, tan, log, PI, E."),
        ("Date", "Date: date/time. new Date() for current time. Methods: getTime, toISOString, "
                 "getFullYear, getMonth, getDate, getHours, getMinutes, getSeconds."),
        ("RegExp", "RegExp: regular expressions. Flags: g, i, m, s. "
                   "Methods: test, exec. String: match, matchAll, replace."),
        ("Error", "Error types: Error, TypeError, RangeError, ReferenceError, SyntaxError. "
                  "Properties: message, name, stack. Custom errors: class MyError extends Error."),
    ],
    "typescript": [
        ("types", "TypeScript type annotations: string, number, boolean, null, undefined, "
                  "never, unknown, any, void. Union: A | B. Intersection: A & B."),
        ("interfaces", "interface: structural contracts. Extends for inheritance. "
                       "Optional fields: name?: Type. Readonly: readonly name: Type."),
        ("generics", "Generics: function<T>(arg: T): T. Constraints: T extends Base. "
                     "Built-in: Array<T>, Promise<T>, Record<K,V>, Partial<T>, Required<T>."),
        ("enums", "enum: named constant sets. Numeric (default) or string enums. "
                  "const enum for inline values. keyof typeof for key unions."),
        ("decorators", "@decorator syntax. Class, method, property, parameter decorators. "
                       "experimentalDecorators must be enabled in tsconfig."),
    ],
    "java": [
        ("java.util.List", "List interface: ArrayList, LinkedList. Methods: add, get, set, remove, "
                           "size, isEmpty, contains, indexOf, subList, toArray, iterator."),
        ("java.util.Map", "Map interface: HashMap, TreeMap, LinkedHashMap. Methods: put, get, "
                          "remove, containsKey, containsValue, keySet, values, entrySet, size."),
        ("java.util.stream", "Stream API: filter, map, flatMap, reduce, collect, forEach, "
                              "sorted, distinct, limit, skip, count, findFirst, anyMatch, allMatch."
                              ),
        ("java.util.Optional", "Optional: null-safe container. Methods: of, ofNullable, empty, "
                               "get, isPresent, ifPresent, orElse, orElseGet, orElseThrow, filter."
                               ),
        ("java.io", "File I/O: Files.readAllLines, Files.write, BufferedReader, FileReader, "
                    "FileWriter, Path, Paths.get. Try-with-resources for auto-closing."),
        ("java.lang.String", "String methods: length, charAt, substring, indexOf, contains, "
                              "startsWith, endsWith, toLowerCase, toUpperCase, trim, split."
                              ),
        ("java.util.Collections", "Collections utility: sort, reverse, shuffle, min, max, "
                                  "frequency, unmodifiableList, synchronizedList."),
        ("java.util.concurrent", "Concurrency: ExecutorService, Future, CompletableFuture, "
                                 "AtomicInteger, ConcurrentHashMap, CountDownLatch, Semaphore."),
        ("annotations", "Common annotations: @Override, @Deprecated, @SuppressWarnings, "
                        "@FunctionalInterface. Spring: @Component, @Service, @Repository, @Bean."),
        ("exceptions", "Checked vs unchecked exceptions. Common: IOException, SQLException, "
                       "NullPointerException, IllegalArgumentException. try-catch-finally."),
    ],
}

# Languages with bootstrap docs available
SUPPORTED_LANGUAGES: frozenset[str] = frozenset(_BOOTSTRAP_DOCS)

# Sentinel mission_id used for global knowledge lake entries (not per-mission)
_KNOWLEDGE_LAKE_ID = "__knowledge_lake__"


def detect_required_languages(
    *,
    prompt: str,
    requested_target_language: str | None,
    source_code: str | None,
    mission_type: str,
) -> list[str]:
    """Return the language keys IS Agent should index docs for."""
    languages: set[str] = set()

    if requested_target_language:
        key = requested_target_language.strip().lower()
        # typescript source gets both ts and js docs
        if key == "typescript":
            languages.update({"typescript", "javascript"})
        elif key in SUPPORTED_LANGUAGES:
            languages.add(key)

    if source_code:
        if re.search(r"^import |^from .+ import ", source_code, re.MULTILINE):
            languages.add("python")
        if re.search(r"^import .+;|require\(|const .+ = require", source_code, re.MULTILINE):
            languages.add("javascript")
        if re.search(r"^import [A-Z]|^package [a-z]", source_code, re.MULTILINE):
            # Note: this pattern is not unique to Java (Kotlin/Scala share the
            # same import/package conventions), but requiring the literal
            # word "java" to also appear in the prompt or source text was too
            # restrictive — legitimate Java source with no such mention
            # (e.g. a prompt like "port this billing module") never got
            # detected at all, silently skipping Java bootstrap docs.
            languages.add("java")

    # Always index at least the target language
    if not languages and requested_target_language:
        languages.add(requested_target_language.strip().lower())
    elif not languages:
        languages.add("python")

    # Filter to only supported languages
    return sorted(lang for lang in languages if lang in SUPPORTED_LANGUAGES)


def _build_docs_content(language_key: str) -> tuple[str, str]:
    """Return (combined_text, content_hash) for a language."""
    docs = _BOOTSTRAP_DOCS[language_key]
    parts = [f"## {topic}\n{description}" for topic, description in docs]
    combined = f"# {language_key} Language Reference\n\n" + "\n\n".join(parts)
    content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]
    return combined, content_hash


def _check_knowledge_exists(*, settings: Any, knowledge_id: str) -> bool:
    """Return True if this knowledge_id is already indexed in the lake."""
    try:
        from .storage import list_knowledge
        records = list_knowledge(settings, _KNOWLEDGE_LAKE_ID, limit=200)
        return any(
            isinstance(r, dict) and r.get("knowledge_id") == knowledge_id
            for r in records
        )
    except Exception as exc:
        LOGGER.debug("_knowledge_is_indexed: storage error for %s: %s", knowledge_id, exc)
        return False


def _knowledge_is_current(*, settings: Any, knowledge_id: str, content_hash: str) -> bool:
    """Return True if an indexed global knowledge record has this hash."""
    try:
        from .storage import list_knowledge

        records = list_knowledge(settings, _KNOWLEDGE_LAKE_ID, limit=200)
        for record in records:
            if not isinstance(record, dict) or record.get("knowledge_id") != knowledge_id:
                continue
            content = record.get("content")
            if isinstance(content, dict) and content.get("hash") == content_hash:
                return True
        return False
    except Exception as exc:
        LOGGER.debug("_knowledge_is_current: storage error for %s: %s", knowledge_id, exc)
        return False


def _bootstrap_content_for_language(language_key: str) -> dict[str, Any]:
    combined_text, content_hash = _build_docs_content(language_key)
    return {
        "combined_text": combined_text,
        "language": language_key,
        "kind": "bootstrap_documentation",
        "hash": content_hash,
        "topic_count": len(_BOOTSTRAP_DOCS[language_key]),
    }


async def run_fetch_phase(
    *,
    mission_id: str,
    required_languages: list[str],
    settings: Any,
    attachments: list[Any] | None = None,
) -> dict[str, Any]:
    """IS Agent execution: index bootstrap docs for required languages.

    Never raises — errors are captured in the result dict. The mission
    proceeds regardless of individual language indexing failures.
    """
    indexed_languages: list[str] = []
    refreshed_languages: list[str] = []
    unchanged_languages: list[str] = []
    skipped_languages: list[str] = []
    knowledge_ids: list[str] = []
    errors: list[str] = []

    if attachments:
        att_result = await _process_mission_attachments(
            mission_id=mission_id,
            attachments=attachments,
            settings=settings,
        )
        knowledge_ids.extend(att_result.get("knowledge_ids", []))
        for err in att_result.get("errors", []):
            errors.append(f"attachment: {err}")

    for language_key in required_languages:
        if language_key not in _BOOTSTRAP_DOCS:
            skipped_languages.append(language_key)
            continue

        knowledge_id = f"docs.{language_key}.bootstrap"

        try:
            content = _bootstrap_content_for_language(language_key)
            created_at = datetime.now(UTC).isoformat()
            refresh_enabled = bool(getattr(settings, "knowledge_refresh_enabled", True))
            already_indexed = await asyncio.to_thread(
                _check_knowledge_exists,
                settings=settings,
                knowledge_id=knowledge_id,
            )
            current = await asyncio.to_thread(
                _knowledge_is_current,
                settings=settings,
                knowledge_id=knowledge_id,
                content_hash=content["hash"],
            )

            if not already_indexed or (refresh_enabled and not current):
                await asyncio.to_thread(
                    _upsert_knowledge_safe,
                    settings=settings,
                    mission_id=_KNOWLEDGE_LAKE_ID,
                    knowledge_id=knowledge_id,
                    content=content,
                    created_at=created_at,
                )
                refreshed_languages.append(language_key)
            else:
                unchanged_languages.append(language_key)
            await asyncio.to_thread(
                _upsert_knowledge_safe,
                settings=settings,
                mission_id=mission_id,
                knowledge_id=knowledge_id,
                content=content,
                created_at=created_at,
            )

            indexed_languages.append(language_key)
            knowledge_ids.append(knowledge_id)
            LOGGER.info(
                "IS Agent indexed %s documentation (%d topics)",
                language_key,
                len(_BOOTSTRAP_DOCS[language_key]),
            )

        except Exception as exc:
            LOGGER.warning("IS Agent failed to index %s: %s", language_key, exc)
            errors.append(f"{language_key}: {exc}")

    return {
        "indexed_languages": indexed_languages,
        "refreshed_languages": refreshed_languages,
        "unchanged_languages": unchanged_languages,
        "skipped_languages": skipped_languages,
        "knowledge_ids": knowledge_ids,
        "errors": errors,
        "knowledge_ready": len(indexed_languages) > 0,
        "refresh_enabled": bool(getattr(settings, "knowledge_refresh_enabled", True)),
        "embedding_provider": str(
            getattr(settings, "knowledge_embedding_provider", "deterministic")
        ),
        "embedding_model": str(
            getattr(settings, "knowledge_embedding_model", "deterministic-hash-v1")
        ),
        "indexed_at": datetime.now(UTC).isoformat(),
        "mission_id": mission_id,
    }


def _upsert_knowledge_safe(
    *,
    settings: Any,
    mission_id: str,
    knowledge_id: str,
    content: dict[str, Any],
    created_at: str,
) -> None:
    """Write to the unified storage façade; log and swallow on failure."""
    try:
        from .storage import upsert_knowledge
        upsert_knowledge(
            settings,
            mission_id,
            knowledge_id,
            content,
            created_at,
        )
    except Exception as exc:
        LOGGER.warning("IS Agent storage write failed for %s: %s", knowledge_id, exc)
        raise


def _attachment_field(att: Any, field: str, default: str) -> str:
    if isinstance(att, dict):
        return str(att.get(field, default) or default)
    return str(getattr(att, field, default) or default)


def _attachment_object_key(settings: Any, mission_id: str, file_id: str) -> str:
    """Derive the object-storage key where an attachment's bytes are stored.

    An attachment may carry an explicit ``object_key`` (set by the API layer at
    upload time); otherwise we fall back to the conventional
    ``{prefix}/{mission_id}/attachments/{file_id}`` layout.
    """
    prefix = str(getattr(settings, "object_storage_prefix", "missions") or "").strip("/")
    if prefix:
        return f"{prefix}/{mission_id}/attachments/{file_id}"
    return f"{mission_id}/attachments/{file_id}"


def _load_attachment_bytes(att: Any, settings: Any, mission_id: str, file_id: str) -> bytes | None:
    """Return the raw bytes for an attachment, or ``None`` if unavailable.

    Bytes may be supplied inline on the attachment (``content_bytes``) or read
    back from object storage by key. Any storage failure is swallowed to
    ``None`` so intake degrades to metadata-only handling.
    """
    inline = att.get("content_bytes") if isinstance(att, dict) else getattr(att, "content_bytes", None)
    if isinstance(inline, (bytes, bytearray)):
        return bytes(inline)

    explicit_key = _attachment_field(att, "object_key", "")
    key = explicit_key or _attachment_object_key(settings, mission_id, file_id)
    try:
        from .object_store import get_object
        return get_object(settings, key)
    except Exception as exc:  # noqa: BLE001 - degrade to metadata-only on any error
        LOGGER.warning("Attachment byte fetch failed for key %s: %s", key, type(exc).__name__)
        return None


async def _process_mission_attachments(
    *,
    mission_id: str,
    attachments: list[Any],
    settings: Any,
) -> dict[str, Any]:
    """Index mission-specific attachments into the Knowledge Lake.

    For each attachment we attempt to load the raw bytes (inline or from object
    storage) and extract real text via :mod:`orchestrator.document_parser`.
    Extracted content is indexed into the Knowledge Lake and attached back to the
    in-memory attachment object as ``content`` so the PM prompt can embed it.
    When bytes are unavailable (metadata-only intake), we preserve the legacy
    behaviour of indexing filename/purpose metadata with a logged warning.
    """
    from .document_parser import parse_document

    processed_count = 0
    errors: list[str] = []
    knowledge_ids: list[str] = []

    for att in attachments:
        filename = _attachment_field(att, "filename", "unknown")
        file_id = _attachment_field(att, "file_id", "unknown")
        purpose = _attachment_field(att, "purpose", "reference")
        content_type = _attachment_field(att, "content_type", "")

        knowledge_id = f"mission.{mission_id}.att.{file_id}"

        extracted: str | None = None
        raw = _load_attachment_bytes(att, settings, mission_id, file_id)
        if raw is not None:
            extracted = parse_document(raw, content_type, filename)
            if extracted is None:
                LOGGER.warning(
                    "No text extracted from attachment %s (type=%s)", filename, content_type
                )
        else:
            LOGGER.warning(
                "No bytes available for attachment %s; indexing metadata only", filename
            )

        try:
            if extracted:
                content = {
                    "type": "attachment",
                    "title": f"Attachment: {filename}",
                    "filename": filename,
                    "purpose": purpose,
                    "language": "document",
                    "combined_text": extracted,
                    "content": extracted,
                    "topics": [("document_content", extracted)],
                    "hash": hashlib.sha256(extracted.encode("utf-8")).hexdigest(),
                    "source": "attachment_extraction",
                }
                # Surface the extracted text to dict-form attachments so callers
                # that reuse this list (e.g. the PM prompt) see the content.
                if isinstance(att, dict):
                    att["content"] = extracted
            else:
                content = {
                    "type": "attachment",
                    "title": f"Attachment: {filename}",
                    "filename": filename,
                    "purpose": purpose,
                    "topics": [
                        (
                            "file_metadata",
                            f"Filename: {filename}, ID: {file_id}, Purpose: {purpose}",
                        )
                    ],
                    "hash": hashlib.sha256(f"{file_id}-{filename}".encode()).hexdigest(),
                    "source": "attachment_metadata",
                }

            await asyncio.to_thread(
                _upsert_knowledge_safe,
                settings=settings,
                mission_id=mission_id,
                knowledge_id=knowledge_id,
                content=content,
                created_at=datetime.now(UTC).isoformat(),
            )
            processed_count += 1
            knowledge_ids.append(knowledge_id)
        except Exception as exc:
            errors.append(f"{filename}: {exc}")

    return {
        "processed_count": processed_count,
        "knowledge_ids": knowledge_ids,
        "errors": errors,
    }
