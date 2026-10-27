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

# Static documentation seed for all 20 specialist language keys (4 pods).
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
    "ruby": [
        ("Enumerable", "Enumerable mixins: map, select, reject, reduce, each_with_object, "
                       "flat_map, group_by, tally, any?, all?, none?, find."),
        ("ObjectModel", "Classes, modules, prepend/include/extend, attr_reader, attr_accessor, "
                        "Data.define and Struct for value objects."),
        ("Concurrency", "Ractor for actor-style isolation, Fiber.schedule for non-blocking I/O, "
                        "Thread and Queue for concurrent work."),
        ("Testing", "RSpec (describe, it, expect) and Minitest (Minitest::Test, assert_equal) "
                    "conventions with frozen_string_literal: true."),
        ("Security", "Avoid Kernel#eval and Marshal.load on untrusted input; use JSON.parse "
                     "and parameterized ActiveRecord queries."),
    ],
    "php": [
        ("TypeSystem", "PHP 8.2+ strict_types=1, union/intersection types, readonly classes, "
                       "backed enums, constructor property promotion, and mixed/never returns."),
        ("Arrays", "Array functions: array_map, array_filter, array_reduce, array_column, "
                   "array_merge, in_array, array_key_exists, and spread operator."),
        ("PDO", "PDO prepared statements with bound parameters (:id) to prevent SQL injection; "
                "PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION."),
        ("PSR", "PSR-1/PSR-4 autoloading, PSR-7 HTTP messages, PSR-12 coding style, "
                "and PHPUnit TestCase assertions."),
    ],
    "c": [
        ("MemorySafety", "MISRA C:2012 discipline: explicit bounds lengths on every buffer, "
                         "snprintf over sprintf, calloc/free pairing, and NULL checks after allocation."),
        ("FixedWidthInts", "stdint.h & stddef.h: int32_t, uint64_t, size_t, uintptr_t, bool "
                           "(stdbool.h) to prevent architecture-dependent overflow."),
        ("ErrorHandling", "Return explicit status codes or errno; use goto cleanup labels for "
                          "deterministic resource release of file descriptors and heap buffers."),
        ("Toolchain", "Compile cleanly under -Wall -Wextra -Werror -pedantic -std=c11; "
                      "verify assertions with assert.h or Unity test runners."),
    ],
    "cpp": [
        ("RAII", "C++20/23 Rule of Zero: std::unique_ptr, std::shared_ptr, std::lock_guard, "
                 "and std::scoped_lock; never use raw owning new/delete."),
        ("Containers", "STL containers & views: std::vector, std::unordered_map, std::optional, "
                       "std::variant, std::string_view, and std::span for bounds-safe slices."),
        ("Algorithms", "std::ranges algorithms (views::filter, views::transform), constexpr "
                       "evaluation, and concepts/requires constraints."),
        ("Testing", "GoogleTest (TEST, EXPECT_EQ, ASSERT_TRUE) and Catch2 (TEST_CASE, REQUIRE) "
                    "with AddressSanitizer/UBSan-clean semantics."),
    ],
    "rust": [
        ("Ownership", "Ownership, borrowing (&T, &mut T), lifetimes ('a), and zero-unsafe "
                      "discipline; prefer slices (&[T], &str) in function parameters."),
        ("ErrorHandling", "Result<T, E> and Option<T> with ? propagation, map_err, ok_or_else, "
                          "and custom error enums implementing std::error::Error + Display."),
        ("Collections", "Vec<T>, HashMap<K, V>, BTreeMap<K, V>, HashSet<T>, and Iterator "
                        "adapters (map, filter, filter_map, fold, collect)."),
        ("Concurrency", "Send/Sync traits, Arc<Mutex<T>>, std::sync::mpsc, and tokio async/await "
                        "tasks with #[cfg(test)] mod tests and #[test] assertions."),
    ],
    "go": [
        ("Concurrency", "Goroutines, typed channels, select statements, sync.WaitGroup, "
                        "sync.Mutex, and context.Context cancellation propagation."),
        ("ErrorHandling", "Explicit error return values, errors.Is, errors.As, errors.Join, "
                          "and fmt.Errorf(\"...: %w\", err) wrapping."),
        ("Interfaces", "Small consumer-defined interfaces, io.Reader/io.Writer composition, "
                       "defer for deterministic resource cleanup, and slices/maps."),
        ("Testing", "Table-driven tests in *_test.go using testing.T, t.Run subtests, "
                    "t.Helper(), and go vet / race-detector safe patterns."),
    ],
    "zig": [
        ("Allocators", "Explicit std.mem.Allocator passing, defer and errdefer for leak-free "
                       "cleanup, and std.testing.allocator for leak detection in tests."),
        ("ErrorUnions", "Error union types (!T), try and catch |err| switch handling, "
                        "and optional types (?T) with orelse."),
        ("Comptime", "comptime generics, @TypeOf, @import(\"std\"), ArrayList, AutoHashMap, "
                     "and built-in test \"...\" { try std.testing.expectEqual(...); } blocks."),
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
    "csharp": [
        ("ModernDotNet", "C# 12 / .NET 8+: nullable reference types (#nullable enable), "
                         "records, pattern matching switch expressions, and primary constructors."),
        ("AsyncAwait", "Task<T>, ValueTask<T>, async/await with CancellationToken propagation, "
                       "and IAsyncEnumerable<T> streaming."),
        ("LINQ", "System.Linq: Where, Select, SelectMany, GroupBy, OrderBy, ToList, "
                 "ToDictionary, Any, All, and Span<T>/Memory<T> for zero-allocation slicing."),
        ("Testing", "xUnit ([Fact], [Theory], [InlineData], Assert.Equal) and NUnit "
                    "conventions with IDisposable / await using resource management."),
    ],
    "scala": [
        ("FunctionalCore", "Scala 3 immutability: case classes, enum ADTs, Option[T], "
                           "Either[E, A], Try[T], and exhaustive match expressions."),
        ("Collections", "Immutable Seq, Vector, List, Map, Set with map, flatMap, filter, "
                        "foldLeft, collect, and for-comprehensions."),
        ("TypeSystem", "given/using contextual abstractions, extension methods, opaque types, "
                       "and ScalaTest / MUnit test suites."),
    ],
    "kotlin": [
        ("NullSafety", "Nullable types (T?), safe calls (?.), Elvis operator (?:), "
                       "requireNotNull/checkNotNull, and smart casts."),
        ("DataAndSealed", "data class, sealed interface / sealed class hierarchies with "
                          "exhaustive when expressions, and value classes."),
        ("Coroutines", "suspend functions, CoroutineScope, Dispatchers, Flow, StateFlow, "
                       "and structured concurrency with kotlin.test / JUnit 5 assertions."),
    ],
    "r": [
        ("Vectorization", "Vectorized arithmetic, lapply/sapply/vapply, data.frame and "
                          "tibble manipulation, and explicit NA handling (na.rm = TRUE)."),
        ("Functions", "Pure function closures, stopifnot() precondition checks, tryCatch() "
                      "condition handling, and S3/S4/R6 dispatch."),
        ("Testing", "testthat conventions: test_that(\"desc\", { expect_equal(...); "
                    "expect_true(...); expect_error(...) })."),
    ],
    "matlab": [
        ("MatrixOps", "Vectorized array and matrix operations (.*, ./, .^), logical indexing, "
                      "and preallocation with zeros/ones/nan before loops."),
        ("Functions", "arguments ... end validation blocks (mustBeNumeric, mustBePositive), "
                      "function handles (@), and struct/table containers."),
        ("Testing", "matlab.unittest.TestCase classdef with methods (Test) and "
                    "verifyEqual / verifyTrue assertions."),
    ],
    "julia": [
        ("MultipleDispatch", "Multiple dispatch with parametric types, abstract types, "
                             "immutable struct / mutable struct, and type-stable return values."),
        ("ArraysAndBroadcasting", "1-based indexing, dot-broadcasting (f.(x)), views (@view), "
                                  "comprehension generators, and LinearAlgebra operations."),
        ("Testing", "Standard library Test module: using Test; @testset \"...\" begin "
                    "@test ...; @test_throws ... end."),
    ],
    "mathematica": [
        ("SymbolicRules", "Wolfram Language pattern matching (x_Integer, x_List), delayed "
                          "definitions (:=), Module[{vars}, body] lexical scoping, and pure functions (# &)."),
        ("ListProcessing", "Map (/@), Apply (@@, @@@), Select, Cases, Fold, FoldList, "
                           "Association (<|...|>) key-value lookups, and Total."),
        ("Testing", "VerificationTest[input, expected] and TestReport[...] for deterministic "
                    "symbolic and numerical verification."),
    ],
    "haskell": [
        ("PurityAndTypes", "Explicit top-level type signatures (::), algebraic data types "
                           "(data, newtype), Maybe and Either for total error handling without partial head/fromJust."),
        ("Typeclasses", "Functor, Applicative, Monad, Foldable, Traversable, deriving "
                        "(Eq, Show, Ord, Generic), and Data.Map.Strict / Data.Text."),
        ("Testing", "HUnit (TestCase, assertEqual) and QuickCheck property tests "
                    "(prop_*) with cabal/ghc standard modules."),
    ],
    "ocaml": [
        ("ModulesAndTypes", "Algebraic variants, records, option and ('a, 'e) result types, "
                            "exhaustive match ... with, and module / sig ... end signatures."),
        ("Recursion", "Tail-recursive helper functions withlet rec, List.map, List.fold_left, "
                      "Seq, Hashtbl, and Map.Make functors."),
        ("Testing", "Alcotest / OUnit2 test suites and inline assert (...) checks compiled "
                    "via dune or ocamlfind."),
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
        if re.search(r"^\s*#include\s+<stdio\.h>|^\s*#include\s+<stdlib\.h>", source_code, re.MULTILINE):
            languages.add("c")
        if re.search(r"^\s*#include\s+<iostream>|std::", source_code, re.MULTILINE):
            languages.add("cpp")
        if re.search(r"\bfn\s+\w+\s*\(|^\s*use\s+std::", source_code, re.MULTILINE):
            languages.add("rust")
        if re.search(r"^\s*package\s+main\b|^\s*func\s+\w+\s*\(", source_code, re.MULTILINE):
            languages.add("go")
        if re.search(r'@import\(\s*"std"\s*\)', source_code):
            languages.add("zig")
        if re.search(r"^\s*using\s+System(?:\.[\w.]+)?;", source_code, re.MULTILINE):
            languages.add("csharp")
        if re.search(r"^\s*case\s+class\s+\w+|^\s*object\s+\w+\s+extends", source_code, re.MULTILINE):
            languages.add("scala")
        if re.search(r"^\s*(?:suspend\s+)?fun\s+\w+\s*\(|^\s*data\s+class\s+\w+", source_code, re.MULTILINE):
            languages.add("kotlin")
        if re.search(r"<\?php\b", source_code):
            languages.add("php")
        if re.search(r"^\s*require_relative\b|^\s*class\s+\w+\s*<\s*\w+\n\s*def\s+", source_code, re.MULTILINE):
            languages.add("ruby")
        if re.search(r"\w+\s*<-\s*function\s*\(|^\s*library\s*\(", source_code, re.MULTILINE):
            languages.add("r")
        if re.search(r"^\s*classdef\s+\w+", source_code, re.MULTILINE):
            languages.add("matlab")
        if re.search(r"^\s*function\s+\w+\([^)]*::\w+\)|^\s*using\s+Test\b", source_code, re.MULTILINE):
            languages.add("julia")
        if re.search(r"\w+\[\w+_\w*\]\s*:=", source_code):
            languages.add("mathematica")
        if re.search(r"^\s*module\s+[A-Z][\w.]*\s+where\b", source_code, re.MULTILINE):
            languages.add("haskell")
        if re.search(r"^\s*let\s+rec\s+\w+", source_code, re.MULTILINE):
            languages.add("ocaml")

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
            if mission_id != _KNOWLEDGE_LAKE_ID:
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
