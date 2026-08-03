"""Concept catalog — maps regex patterns to LogicNode concept IDs.

Derived from the legacy Pod A/B/C/D specification documents.
Each language group has pattern entries that the ``LanguageExtractor``
uses to detect computational intent in source code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ConceptPattern:
    """A single detectable concept pattern."""

    concept_id: str
    domain: str
    concept: str
    intent: str
    regex: str  # Python ``re`` pattern (case-insensitive search)


# ---------------------------------------------------------------------------
# Pod A — Dynamic Languages (Python, JavaScript, Ruby, PHP)
# ---------------------------------------------------------------------------

_POD_A_PYTHON: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "DYN-001-001",
        "list_operations",
        "filter_collection",
        "Return elements that satisfy a predicate",
        r"\bfilter\s*\(|for\s+\w+\s+in\s+\w+\s+if\b",
    ),
    ConceptPattern(
        "DYN-001-002",
        "list_operations",
        "map_collection",
        "Transform each element",
        r"\bmap\s*\(|\[\s*\w+\(.+?\)\s+for\s+",
    ),
    ConceptPattern(
        "DYN-001-003",
        "list_operations",
        "reduce_collection",
        "Accumulate values into single result",
        r"functools\.reduce\s*\(|\.reduce\s*\(",
    ),
    ConceptPattern(
        "DYN-001-004",
        "list_operations",
        "sort_collection",
        "Order elements",
        r"\bsorted\s*\(|\.sort\s*\(",
    ),
    ConceptPattern(
        "DYN-001-005",
        "list_operations",
        "find_element",
        "Return first element matching predicate",
        r"\bnext\s*\(\s*\(",
    ),
    ConceptPattern(
        "DYN-001-007", "list_operations", "unique_elements", "Remove duplicates", r"\bset\s*\("
    ),
    ConceptPattern(
        "DYN-002-002",
        "string_manipulation",
        "split_string",
        "Break string into parts",
        r"\.split\s*\(",
    ),
    ConceptPattern(
        "DYN-002-003",
        "string_manipulation",
        "join_strings",
        "Combine list of strings",
        r"\.join\s*\(",
    ),
    ConceptPattern(
        "DYN-002-005",
        "string_manipulation",
        "trim_string",
        "Remove whitespace from ends",
        r"\.strip\s*\(",
    ),
    ConceptPattern(
        "DYN-002-006",
        "string_manipulation",
        "replace_substring",
        "Replace occurrences",
        r"\.replace\s*\(",
    ),
    ConceptPattern(
        "DYN-003-001", "dictionary_operations", "get_value", "Retrieve value by key", r"\.get\s*\("
    ),
    ConceptPattern(
        "DYN-003-008",
        "dictionary_operations",
        "merge_dicts",
        "Combine dictionaries",
        r"\{\s*\*\*\w+",
    ),
    ConceptPattern(
        "DYN-005-001",
        "function_patterns",
        "define_function",
        "Create named function",
        r"\bdef\s+\w+\s*\(",
    ),
    ConceptPattern(
        "DYN-005-002",
        "function_patterns",
        "anonymous_function",
        "Create unnamed function",
        r"\blambda\s+",
    ),
    ConceptPattern(
        "DYN-005-004",
        "function_patterns",
        "partial_application",
        "Fix some arguments",
        r"functools\.partial\s*\(",
    ),
    ConceptPattern(
        "DYN-005-006",
        "function_patterns",
        "variadic_arguments",
        "Accept variable number of arguments",
        r"\bdef\s+\w+\s*\(\s*\*\w+",
    ),
    ConceptPattern(
        "DYN-006-001",
        "async_patterns",
        "async_function",
        "Define asynchronous function",
        r"\basync\s+def\b",
    ),
    ConceptPattern(
        "DYN-006-002", "async_patterns", "await_result", "Wait for async operation", r"\bawait\s+"
    ),
    ConceptPattern(
        "DYN-006-004",
        "async_patterns",
        "parallel_all",
        "Wait for multiple async operations",
        r"asyncio\.gather\s*\(",
    ),
    ConceptPattern("DYN-007-001", "error_handling", "try_catch", "Handle exceptions", r"\btry\s*:"),
    ConceptPattern(
        "DYN-007-002", "error_handling", "throw_error", "Raise exception", r"\braise\s+"
    ),
    ConceptPattern(
        "DYN-008-001",
        "io_operations",
        "read_file",
        "Load file contents",
        r"\bopen\s*\(.+?\)\.read|Path\(.+?\)\.read_text",
    ),
    ConceptPattern(
        "DYN-008-002",
        "io_operations",
        "write_file",
        "Save file contents",
        r"\bopen\s*\(.+?['\"]w['\"]",
    ),
    ConceptPattern(
        "DYN-009-001",
        "http_operations",
        "http_get",
        "Send HTTP GET request",
        r"requests\.get\s*\(|httpx\.\w*get\s*\(",
    ),
    ConceptPattern(
        "DYN-009-002",
        "http_operations",
        "http_post",
        "Send HTTP POST request",
        r"requests\.post\s*\(|httpx\.\w*post\s*\(",
    ),
    ConceptPattern(
        "DYN-010-001", "serialization", "json_encode", "Serialize to JSON", r"json\.dumps?\s*\("
    ),
    ConceptPattern(
        "DYN-010-002", "serialization", "json_decode", "Deserialize from JSON", r"json\.loads?\s*\("
    ),
    ConceptPattern(
        "DYN-013-001",
        "module_patterns",
        "import_module",
        "Import module/package",
        r"\bimport\s+\w+|\bfrom\s+\w+\s+import\b",
    ),
    ConceptPattern(
        "DYN-014-001",
        "object_patterns",
        "define_class",
        "Create class definition",
        r"\bclass\s+\w+",
    ),
    ConceptPattern(
        "DYN-014-002",
        "object_patterns",
        "inheritance",
        "Extend a class",
        r"\bclass\s+\w+\s*\(\s*\w+",
    ),
    ConceptPattern(
        "DYN-017-001", "regex_patterns", "regex_match", "Match regex pattern", r"\bre\.\w+\s*\("
    ),
)

_POD_A_JAVASCRIPT: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "DYN-001-001",
        "list_operations",
        "filter_collection",
        "Return elements that satisfy a predicate",
        r"\.filter\s*\(",
    ),
    ConceptPattern(
        "DYN-001-002", "list_operations", "map_collection", "Transform each element", r"\.map\s*\("
    ),
    ConceptPattern(
        "DYN-001-003",
        "list_operations",
        "reduce_collection",
        "Accumulate values into single result",
        r"\.reduce\s*\(",
    ),
    ConceptPattern(
        "DYN-001-004", "list_operations", "sort_collection", "Order elements", r"\.sort\s*\("
    ),
    ConceptPattern(
        "DYN-001-005",
        "list_operations",
        "find_element",
        "Return first element matching predicate",
        r"\.find\s*\(",
    ),
    ConceptPattern(
        "DYN-005-001",
        "function_patterns",
        "define_function",
        "Create named function",
        r"\bfunction\s+\w+\s*\(|(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\(",
    ),
    ConceptPattern(
        "DYN-005-002",
        "function_patterns",
        "anonymous_function",
        "Create unnamed function",
        r"=>\s*[{(]|\bfunction\s*\(",
    ),
    ConceptPattern(
        "DYN-006-001",
        "async_patterns",
        "async_function",
        "Define asynchronous function",
        r"\basync\s+function\b|\basync\s*\(",
    ),
    ConceptPattern(
        "DYN-006-002", "async_patterns", "await_result", "Wait for async operation", r"\bawait\s+"
    ),
    ConceptPattern(
        "DYN-006-003",
        "async_patterns",
        "create_promise",
        "Create async promise",
        r"\bnew\s+Promise\s*\(",
    ),
    ConceptPattern(
        "DYN-006-004",
        "async_patterns",
        "parallel_all",
        "Wait for multiple async operations",
        r"Promise\.all\s*\(",
    ),
    ConceptPattern(
        "DYN-007-001", "error_handling", "try_catch", "Handle exceptions", r"\btry\s*\{"
    ),
    ConceptPattern(
        "DYN-007-002", "error_handling", "throw_error", "Raise exception", r"\bthrow\s+"
    ),
    ConceptPattern(
        "DYN-009-001", "http_operations", "http_get", "Send HTTP GET request", r"\bfetch\s*\("
    ),
    ConceptPattern(
        "DYN-010-001", "serialization", "json_encode", "Serialize to JSON", r"JSON\.stringify\s*\("
    ),
    ConceptPattern(
        "DYN-010-002", "serialization", "json_decode", "Deserialize from JSON", r"JSON\.parse\s*\("
    ),
    ConceptPattern(
        "DYN-013-001",
        "module_patterns",
        "import_module",
        "Import module/package",
        r"\bimport\s+.+\s+from\b|\brequire\s*\(",
    ),
    ConceptPattern(
        "DYN-014-001",
        "object_patterns",
        "define_class",
        "Create class definition",
        r"\bclass\s+\w+",
    ),
    ConceptPattern(
        "DYN-014-002",
        "object_patterns",
        "inheritance",
        "Extend a class",
        r"\bclass\s+\w+\s+extends\s+",
    ),
    ConceptPattern(
        "DYN-015-001",
        "dom_manipulation",
        "query_selector",
        "Select DOM elements",
        r"document\.querySelector|document\.getElementById",
    ),
)

_POD_A_RUBY: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "DYN-001-001",
        "list_operations",
        "filter_collection",
        "Return elements that satisfy a predicate",
        r"\.select\s*[\{(]",
    ),
    ConceptPattern(
        "DYN-001-002",
        "list_operations",
        "map_collection",
        "Transform each element",
        r"\.map\s*[\{(]",
    ),
    ConceptPattern(
        "DYN-001-003",
        "list_operations",
        "reduce_collection",
        "Accumulate values into single result",
        r"\.reduce\s*[\{(]|\.inject\s*[\{(]",
    ),
    ConceptPattern(
        "DYN-005-001",
        "function_patterns",
        "define_function",
        "Create named function",
        r"\bdef\s+\w+",
    ),
    ConceptPattern(
        "DYN-006-001",
        "async_patterns",
        "async_function",
        "Define asynchronous function",
        r"\bFiber\.new\b",
    ),
    ConceptPattern(
        "DYN-007-001", "error_handling", "try_catch", "Handle exceptions", r"\bbegin\b.*\brescue\b"
    ),
    ConceptPattern(
        "DYN-007-002", "error_handling", "throw_error", "Raise exception", r"\braise\s+"
    ),
    ConceptPattern(
        "DYN-014-001",
        "object_patterns",
        "define_class",
        "Create class definition",
        r"\bclass\s+\w+",
    ),
    ConceptPattern(
        "DYN-014-002",
        "object_patterns",
        "inheritance",
        "Extend a class",
        r"\bclass\s+\w+\s*<\s*\w+",
    ),
)

_POD_A_PHP: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "DYN-001-001",
        "list_operations",
        "filter_collection",
        "Return elements that satisfy a predicate",
        r"\barray_filter\s*\(",
    ),
    ConceptPattern(
        "DYN-001-002",
        "list_operations",
        "map_collection",
        "Transform each element",
        r"\barray_map\s*\(",
    ),
    ConceptPattern(
        "DYN-001-003",
        "list_operations",
        "reduce_collection",
        "Accumulate values into single result",
        r"\barray_reduce\s*\(",
    ),
    ConceptPattern(
        "DYN-005-001",
        "function_patterns",
        "define_function",
        "Create named function",
        r"\bfunction\s+\w+\s*\(",
    ),
    ConceptPattern(
        "DYN-007-001", "error_handling", "try_catch", "Handle exceptions", r"\btry\s*\{"
    ),
    ConceptPattern(
        "DYN-007-002", "error_handling", "throw_error", "Raise exception", r"\bthrow\s+new\s+"
    ),
    ConceptPattern(
        "DYN-014-001",
        "object_patterns",
        "define_class",
        "Create class definition",
        r"\bclass\s+\w+",
    ),
    ConceptPattern(
        "DYN-014-002",
        "object_patterns",
        "inheritance",
        "Extend a class",
        r"\bclass\s+\w+\s+extends\s+",
    ),
)

# ---------------------------------------------------------------------------
# Pod B — Systems Languages (C, C++, Rust, Zig)
# ---------------------------------------------------------------------------

_POD_B_C: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "SYS-001-001",
        "memory_management",
        "malloc_alloc",
        "Allocate heap memory",
        r"\bmalloc\s*\(|\bcalloc\s*\(",
    ),
    ConceptPattern(
        "SYS-001-002", "memory_management", "free_dealloc", "Free heap memory", r"\bfree\s*\("
    ),
    ConceptPattern(
        "SYS-002-001", "pointer_operations", "pointer_deref", "Dereference pointer", r"\*\s*\w+"
    ),
    ConceptPattern(
        "SYS-003-001",
        "function_patterns",
        "define_function",
        "Create named function",
        r"\b(?:void|int|char|float|double|long|unsigned|signed|struct\s+\w+)\s+\w+\s*\(",
    ),
    ConceptPattern(
        "SYS-004-001",
        "struct_patterns",
        "define_struct",
        "Define data structure",
        r"\bstruct\s+\w+\s*\{",
    ),
    ConceptPattern(
        "SYS-005-001",
        "preprocessor",
        "include_header",
        "Include header file",
        r"#\s*include\s+[<\"]",
    ),
    ConceptPattern(
        "SYS-005-002",
        "preprocessor",
        "define_macro",
        "Define preprocessor macro",
        r"#\s*define\s+\w+",
    ),
    ConceptPattern(
        "SYS-006-001",
        "io_operations",
        "printf_output",
        "Formatted output",
        r"\bprintf\s*\(|\bfprintf\s*\(",
    ),
    ConceptPattern(
        "SYS-006-002", "io_operations", "file_open", "Open file handle", r"\bfopen\s*\("
    ),
)

_POD_B_CPP: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "SYS-001-003",
        "memory_management",
        "smart_pointer",
        "Use smart pointer",
        r"\bstd::(?:unique_ptr|shared_ptr|weak_ptr)\b",
    ),
    ConceptPattern(
        "SYS-001-004", "memory_management", "new_alloc", "Allocate with new", r"\bnew\s+\w+"
    ),
    ConceptPattern(
        "SYS-003-001",
        "function_patterns",
        "define_function",
        "Create named function",
        r"\b(?:void|int|auto|bool|std::\w+)\s+\w+\s*\(",
    ),
    ConceptPattern(
        "SYS-007-001",
        "template_patterns",
        "template_function",
        "Define template function",
        r"\btemplate\s*<",
    ),
    ConceptPattern(
        "SYS-007-002", "template_patterns", "define_class", "Define class", r"\bclass\s+\w+"
    ),
    ConceptPattern(
        "SYS-007-003",
        "template_patterns",
        "inheritance",
        "Inherit from class",
        r"\bclass\s+\w+\s*:\s*(?:public|private|protected)\b",
    ),
    ConceptPattern(
        "SYS-008-001", "container_patterns", "vector_usage", "Use dynamic array", r"\bstd::vector\b"
    ),
    ConceptPattern(
        "SYS-008-002",
        "container_patterns",
        "map_usage",
        "Use associative container",
        r"\bstd::(?:map|unordered_map)\b",
    ),
    ConceptPattern(
        "SYS-009-001", "concurrency", "thread_create", "Create thread", r"\bstd::thread\b"
    ),
    ConceptPattern(
        "SYS-009-002",
        "concurrency",
        "mutex_lock",
        "Use mutex",
        r"\bstd::(?:mutex|lock_guard|unique_lock)\b",
    ),
)

_POD_B_RUST: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "SYS-010-001", "ownership", "borrow_ref", "Borrow reference", r"&\w+|&mut\s+\w+"
    ),
    ConceptPattern(
        "SYS-010-002", "ownership", "lifetime_annotation", "Annotate lifetime", r"<'\w+>"
    ),
    ConceptPattern(
        "SYS-011-001", "error_handling", "result_type", "Use Result type", r"\bResult\s*<"
    ),
    ConceptPattern(
        "SYS-011-002", "error_handling", "option_type", "Use Option type", r"\bOption\s*<"
    ),
    ConceptPattern(
        "SYS-011-003",
        "error_handling",
        "unwrap_or",
        "Unwrap with fallback",
        r"\.unwrap_or\s*\(|\.unwrap\s*\(",
    ),
    ConceptPattern(
        "SYS-011-004", "error_handling", "question_mark", "Propagate error with ?", r"\w+\s*\?;"
    ),
    ConceptPattern(
        "SYS-012-001",
        "function_patterns",
        "define_function",
        "Create named function",
        r"\bfn\s+\w+",
    ),
    ConceptPattern(
        "SYS-012-002", "function_patterns", "closure", "Create closure", r"\|\s*\w*\s*\|\s*[{]"
    ),
    ConceptPattern(
        "SYS-013-001", "type_patterns", "define_struct", "Define struct", r"\bstruct\s+\w+"
    ),
    ConceptPattern("SYS-013-002", "type_patterns", "define_enum", "Define enum", r"\benum\s+\w+"),
    ConceptPattern(
        "SYS-013-003", "type_patterns", "impl_block", "Implement methods", r"\bimpl\s+\w+"
    ),
    ConceptPattern(
        "SYS-013-004", "type_patterns", "define_trait", "Define trait", r"\btrait\s+\w+"
    ),
    ConceptPattern(
        "SYS-014-001",
        "pattern_matching",
        "match_expression",
        "Pattern match",
        r"\bmatch\s+\w+\s*\{",
    ),
    ConceptPattern(
        "SYS-015-001",
        "async_patterns",
        "async_function",
        "Define async function",
        r"\basync\s+fn\b",
    ),
    ConceptPattern("SYS-015-002", "async_patterns", "await_result", "Await future", r"\.await\b"),
    ConceptPattern("SYS-016-001", "module_patterns", "use_module", "Import module", r"\buse\s+\w+"),
    ConceptPattern(
        "SYS-016-002", "module_patterns", "mod_declaration", "Declare module", r"\bmod\s+\w+"
    ),
)

_POD_B_GO: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "SYS-020-001",
        "function_patterns",
        "define_function",
        "Create named function",
        r"\bfunc\s+\w+\s*\(",
    ),
    ConceptPattern(
        "SYS-020-002",
        "concurrency",
        "goroutine",
        "Launch goroutine",
        r"\bgo\s+\w+\s*\(",
    ),
    ConceptPattern(
        "SYS-020-003",
        "concurrency",
        "channel_operation",
        "Create or use channel",
        r"\bmake\s*\(\s*chan\b|<-\s*\w+|\bclose\s*\(",
    ),
    ConceptPattern(
        "SYS-020-004",
        "resource_management",
        "defer_call",
        "Defer function call to end of scope",
        r"\bdefer\s+\w+",
    ),
    ConceptPattern(
        "SYS-020-005",
        "error_handling",
        "error_check",
        "Check returned error value",
        r"\berr\s*!=\s*nil\b",
    ),
    ConceptPattern(
        "SYS-020-006",
        "type_patterns",
        "define_struct",
        "Define struct type",
        r"\btype\s+\w+\s+struct\b",
    ),
    ConceptPattern(
        "SYS-020-007",
        "type_patterns",
        "define_interface",
        "Define interface type",
        r"\btype\s+\w+\s+interface\b",
    ),
    ConceptPattern(
        "SYS-020-008",
        "error_handling",
        "wrap_error",
        "Wrap or create error value",
        r"\berrors\.New\s*\(|fmt\.Errorf\s*\(",
    ),
    ConceptPattern(
        "SYS-020-009",
        "module_patterns",
        "import_package",
        "Import package",
        r'^\s*import\s+(?:"[\w./]+"|`[\w./]+`|\()',
    ),
    ConceptPattern(
        "SYS-020-010",
        "collection_patterns",
        "slice_operation",
        "Slice or map operation",
        r"\bappend\s*\(|\bmake\s*\(\s*\[\]|\blen\s*\(",
    ),
    ConceptPattern(
        "SYS-020-011",
        "serialization",
        "json_marshal",
        "Marshal struct to JSON",
        r"\bjson\.Marshal\s*\(|\bjson\.Unmarshal\s*\(",
    ),
)

_POD_B_ZIG: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "SYS-021-001",
        "function_patterns",
        "define_function",
        "Create named function",
        r"\bfn\s+\w+\s*\(",
    ),
    ConceptPattern(
        "SYS-021-002",
        "metaprogramming",
        "comptime_eval",
        "Compile-time evaluation",
        r"\bcomptime\b",
    ),
    ConceptPattern(
        "SYS-021-003",
        "error_handling",
        "error_union",
        "Propagate error with try or error union return",
        r"\btry\s+\w+|\berror\s*\{|!\s*\w+\s*\{",
    ),
    ConceptPattern(
        "SYS-021-004",
        "type_patterns",
        "define_struct",
        "Define struct type",
        r"\bstruct\s*\{",
    ),
    ConceptPattern(
        "SYS-021-005",
        "memory_management",
        "allocator_usage",
        "Use allocator for heap memory",
        r"allocator\.alloc\s*\(|std\.heap\.\w+|\.deinit\s*\(",
    ),
    ConceptPattern(
        "SYS-021-006",
        "module_patterns",
        "import_module",
        "Import Zig module",
        r'@import\s*\(\s*"[\w./]+"',
    ),
    ConceptPattern(
        "SYS-021-007",
        "resource_management",
        "defer_call",
        "Defer resource cleanup",
        r"\bdefer\s+\w+",
    ),
    ConceptPattern(
        "SYS-021-008",
        "type_patterns",
        "optional_type",
        "Use optional type",
        r"\?\s*\w+|\borelse\b|\bif\s+\(\s*\w+\s*\)\s*\|",
    ),
    ConceptPattern(
        "SYS-021-009",
        "io_operations",
        "print_output",
        "Write to stdout",
        r"std\.debug\.print\s*\(|std\.io\.getStdOut",
    ),
)

# ---------------------------------------------------------------------------
# Pod C — Enterprise Languages (Java, C#, Scala, Kotlin)
# ---------------------------------------------------------------------------

_POD_C_JAVA: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "ENT-001-001", "class_patterns", "define_class", "Define class", r"\bclass\s+\w+"
    ),
    ConceptPattern(
        "ENT-001-002",
        "class_patterns",
        "inheritance",
        "Extend class",
        r"\bclass\s+\w+\s+extends\s+",
    ),
    ConceptPattern(
        "ENT-001-003",
        "class_patterns",
        "implement_interface",
        "Implement interface",
        r"\bimplements\s+\w+",
    ),
    ConceptPattern(
        "ENT-001-004",
        "class_patterns",
        "define_interface",
        "Define interface",
        r"\binterface\s+\w+",
    ),
    ConceptPattern(
        "ENT-002-001",
        "function_patterns",
        "define_method",
        "Define method",
        r"\b(?:public|private|protected)\s+(?:static\s+)?(?:void|int|String|boolean|long|double)\s+\w+\s*\(",
    ),
    ConceptPattern(
        "ENT-003-001", "error_handling", "try_catch", "Handle exceptions", r"\btry\s*\{"
    ),
    ConceptPattern(
        "ENT-003-002", "error_handling", "throw_exception", "Throw exception", r"\bthrow\s+new\s+"
    ),
    ConceptPattern(
        "ENT-004-001",
        "collection_patterns",
        "list_usage",
        "Use List collection",
        r"\bList\s*<|ArrayList\s*<|LinkedList\s*<",
    ),
    ConceptPattern(
        "ENT-004-002",
        "collection_patterns",
        "map_usage",
        "Use Map collection",
        r"\bMap\s*<|HashMap\s*<|TreeMap\s*<",
    ),
    ConceptPattern(
        "ENT-004-003",
        "collection_patterns",
        "stream_operations",
        "Use Stream API",
        r"\.stream\s*\(\)|\.parallelStream\s*\(",
    ),
    ConceptPattern(
        "ENT-005-001", "annotation_patterns", "annotation_usage", "Use annotation", r"@\w+"
    ),
    ConceptPattern(
        "ENT-006-001",
        "generics",
        "generic_class",
        "Define generic class",
        r"\bclass\s+\w+\s*<\s*\w+",
    ),
    ConceptPattern(
        "ENT-007-001",
        "concurrency",
        "thread_create",
        "Create thread",
        r"\bnew\s+Thread\b|\bExecutors\.\w+",
    ),
    ConceptPattern(
        "ENT-007-002",
        "concurrency",
        "synchronized_block",
        "Synchronize access",
        r"\bsynchronized\s*[\({]",
    ),
    ConceptPattern(
        "ENT-008-001", "module_patterns", "import_package", "Import package", r"\bimport\s+[\w.]+"
    ),
)

_POD_C_CSHARP: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "ENT-001-001", "class_patterns", "define_class", "Define class", r"\bclass\s+\w+"
    ),
    ConceptPattern(
        "ENT-001-002", "class_patterns", "inheritance", "Extend class", r"\bclass\s+\w+\s*:\s*\w+"
    ),
    ConceptPattern(
        "ENT-002-001",
        "function_patterns",
        "define_method",
        "Define method",
        r"\b(?:public|private|protected|internal)\s+(?:static\s+)?(?:void|int|string|bool|Task)\s+\w+\s*\(",
    ),
    ConceptPattern(
        "ENT-003-001", "error_handling", "try_catch", "Handle exceptions", r"\btry\s*\{"
    ),
    ConceptPattern(
        "ENT-006-001",
        "generics",
        "generic_class",
        "Define generic class",
        r"\bclass\s+\w+\s*<\s*\w+",
    ),
    ConceptPattern(
        "ENT-009-001", "async_patterns", "async_method", "Define async method", r"\basync\s+Task"
    ),
    ConceptPattern("ENT-009-002", "async_patterns", "await_result", "Await task", r"\bawait\s+"),
    ConceptPattern(
        "ENT-010-001",
        "linq_patterns",
        "linq_query",
        "LINQ query",
        r"\.Where\s*\(|\.Select\s*\(|\.OrderBy\s*\(",
    ),
)

_POD_C_SCALA: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "ENT-001-001", "class_patterns", "define_class", "Define class", r"\bclass\s+\w+"
    ),
    ConceptPattern(
        "ENT-011-001",
        "functional_patterns",
        "case_class",
        "Define case class",
        r"\bcase\s+class\s+\w+",
    ),
    ConceptPattern(
        "ENT-011-002", "functional_patterns", "pattern_match", "Pattern match", r"\bmatch\s*\{"
    ),
    ConceptPattern(
        "ENT-011-003", "functional_patterns", "define_trait", "Define trait", r"\btrait\s+\w+"
    ),
    ConceptPattern(
        "ENT-002-001", "function_patterns", "define_function", "Define function", r"\bdef\s+\w+"
    ),
    ConceptPattern(
        "ENT-011-004",
        "functional_patterns",
        "for_comprehension",
        "For comprehension",
        r"\bfor\s*\{.*yield\b",
    ),
)

_POD_C_KOTLIN: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "ENT-001-001", "class_patterns", "define_class", "Define class", r"\bclass\s+\w+"
    ),
    ConceptPattern(
        "ENT-012-001", "kotlin_patterns", "data_class", "Define data class", r"\bdata\s+class\s+\w+"
    ),
    ConceptPattern("ENT-012-002", "kotlin_patterns", "null_safety", "Null-safe access", r"\?\.|!!"),
    ConceptPattern(
        "ENT-012-003",
        "kotlin_patterns",
        "coroutine_launch",
        "Launch coroutine",
        r"\blaunch\s*\{|\basync\s*\{",
    ),
    ConceptPattern(
        "ENT-002-001", "function_patterns", "define_function", "Define function", r"\bfun\s+\w+"
    ),
    ConceptPattern(
        "ENT-009-001",
        "async_patterns",
        "suspend_function",
        "Define suspend function",
        r"\bsuspend\s+fun\b",
    ),
)

# ---------------------------------------------------------------------------
# Pod D — Mathematical & Functional Languages (MATLAB, R, Julia, Mathematica; Haskell/OCaml below)
# ---------------------------------------------------------------------------

_POD_D_MATLAB: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "MATH-001-001",
        "matrix_operations",
        "matrix_multiply",
        "Matrix multiplication",
        r"\*\s*\w+|mtimes\s*\(",
    ),
    ConceptPattern(
        "MATH-001-002",
        "matrix_operations",
        "transpose",
        "Transpose matrix",
        r"\w+['\"]|\btranspose\s*\(",
    ),
    ConceptPattern("MATH-001-003", "matrix_operations", "inverse", "Invert matrix", r"\binv\s*\("),
    ConceptPattern(
        "MATH-001-004", "matrix_operations", "determinant", "Compute determinant", r"\bdet\s*\("
    ),
    ConceptPattern(
        "MATH-002-001", "function_patterns", "define_function", "Define function", r"\bfunction\b"
    ),
    ConceptPattern(
        "MATH-003-001", "plotting", "plot_data", "Plot data", r"\bplot\s*\(|\bfigure\s*\("
    ),
    ConceptPattern(
        "MATH-004-001", "linear_algebra", "eigenvalues", "Compute eigenvalues", r"\beig\s*\("
    ),
    ConceptPattern(
        "MATH-004-002", "linear_algebra", "svd", "Singular value decomposition", r"\bsvd\s*\("
    ),
    ConceptPattern("MATH-005-001", "statistics", "mean_calc", "Calculate mean", r"\bmean\s*\("),
    ConceptPattern(
        "MATH-005-002", "statistics", "std_dev", "Calculate standard deviation", r"\bstd\s*\("
    ),
)

_POD_D_R: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "MATH-001-001", "matrix_operations", "matrix_multiply", "Matrix multiplication", r"%\*%"
    ),
    ConceptPattern(
        "MATH-002-001",
        "function_patterns",
        "define_function",
        "Define function",
        r"\w+\s*<-\s*function\s*\(",
    ),
    ConceptPattern(
        "MATH-003-001", "plotting", "plot_data", "Plot data", r"\bplot\s*\(|\bggplot\s*\("
    ),
    ConceptPattern(
        "MATH-006-001",
        "data_manipulation",
        "dataframe_ops",
        "DataFrame operations",
        r"\bdata\.frame\s*\(|\btibble\s*\(",
    ),
    ConceptPattern(
        "MATH-006-002", "data_manipulation", "pipe_operator", "Pipe operator", r"%>%|\|>"
    ),
    ConceptPattern(
        "MATH-006-003",
        "data_manipulation",
        "dplyr_verb",
        "dplyr verb",
        r"\bfilter\s*\(|\bmutate\s*\(|\bsummarise\s*\(|\bgroup_by\s*\(",
    ),
    ConceptPattern("MATH-005-001", "statistics", "mean_calc", "Calculate mean", r"\bmean\s*\("),
    ConceptPattern(
        "MATH-005-003", "statistics", "linear_model", "Fit linear model", r"\blm\s*\(|\bglm\s*\("
    ),
)

_POD_D_JULIA: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "MATH-002-001",
        "function_patterns",
        "define_function",
        "Define function",
        r"\bfunction\s+\w+",
    ),
    ConceptPattern(
        "MATH-007-001",
        "type_patterns",
        "define_struct",
        "Define struct",
        r"\bstruct\s+\w+|\bmutable\s+struct\b",
    ),
    ConceptPattern(
        "MATH-007-002",
        "type_patterns",
        "multiple_dispatch",
        "Multiple dispatch",
        r"\bfunction\s+\w+\s*\([^)]*::\w+",
    ),
    ConceptPattern(
        "MATH-001-001", "matrix_operations", "matrix_multiply", "Matrix multiplication", r"\*\s*\w+"
    ),
    ConceptPattern(
        "MATH-004-001",
        "linear_algebra",
        "eigenvalues",
        "Compute eigenvalues",
        r"\beigen\s*\(|\beigvals\s*\(",
    ),
    ConceptPattern(
        "MATH-003-001", "plotting", "plot_data", "Plot data", r"\bplot\s*\(|\bscatter\s*\("
    ),
)

_POD_D_MATHEMATICA: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "MATH-008-001",
        "symbolic",
        "symbolic_solve",
        "Symbolic equation solving",
        r"\bSolve\s*\[|\bDSolve\s*\[",
    ),
    ConceptPattern(
        "MATH-008-002",
        "symbolic",
        "simplify_expr",
        "Simplify expression",
        r"\bSimplify\s*\[|\bFullSimplify\s*\[",
    ),
    ConceptPattern(
        "MATH-008-003", "symbolic", "integrate", "Symbolic integration", r"\bIntegrate\s*\["
    ),
    ConceptPattern(
        "MATH-008-004", "symbolic", "differentiate", "Symbolic differentiation", r"\bD\s*\["
    ),
    ConceptPattern(
        "MATH-003-001", "plotting", "plot_data", "Plot data", r"\bPlot\s*\[|\bListPlot\s*\["
    ),
    ConceptPattern(
        "MATH-002-001",
        "function_patterns",
        "define_function",
        "Define function",
        r"\w+\s*\[.*\]\s*:=",
    ),
)


_POD_D_HASKELL: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "MATH-009-001",
        "type_patterns",
        "type_signature",
        "Declare function type signature",
        r"\w+\s*::\s*\S",
    ),
    ConceptPattern(
        "MATH-009-002",
        "pattern_matching",
        "case_expression",
        "Pattern match with case ... of",
        r"\bcase\s+\w+\s+of\b",
    ),
    ConceptPattern(
        "MATH-009-003",
        "type_patterns",
        "define_typeclass",
        "Define type class",
        r"\bclass\s+\w+.*\bwhere\b",
    ),
    ConceptPattern(
        "MATH-009-004",
        "type_patterns",
        "typeclass_instance",
        "Implement type class instance",
        r"\binstance\s+\w+.*\bwhere\b",
    ),
    ConceptPattern(
        "MATH-009-005",
        "type_patterns",
        "define_data",
        "Define algebraic data type",
        r"\bdata\s+\w+",
    ),
    ConceptPattern(
        "MATH-009-006",
        "function_patterns",
        "lambda",
        "Create anonymous lambda function",
        r"\\\s*\w+\s*->",
    ),
    ConceptPattern(
        "MATH-009-007",
        "list_operations",
        "list_comprehension",
        "List comprehension",
        r"\[\s*\w+\s*\|",
    ),
    ConceptPattern(
        "MATH-009-008",
        "async_patterns",
        "monadic_bind",
        "Monadic bind (>>=)",
        r">>=",
    ),
    ConceptPattern(
        "MATH-009-009",
        "module_patterns",
        "import_module",
        "Import module",
        r"^\s*import\s+(?:qualified\s+)?[\w.]+",
    ),
    ConceptPattern(
        "MATH-009-010",
        "async_patterns",
        "do_notation",
        "Monadic do-notation block",
        r"\bdo\s*$|\bdo\s*\n",
    ),
    ConceptPattern(
        "MATH-009-011",
        "function_patterns",
        "function_composition",
        "Compose functions with . operator",
        r"\w+\s+\.\s+\w+",
    ),
    ConceptPattern(
        "MATH-009-012",
        "function_patterns",
        "define_function",
        "Define top-level function",
        r"^\w+\s+\w+.*=\s*\S",
    ),
)

_POD_D_OCAML: Final[tuple[ConceptPattern, ...]] = (
    ConceptPattern(
        "MATH-010-001",
        "function_patterns",
        "define_function",
        "Define named function with let binding",
        r"\blet\s+\w+\s+\w+.*=",
    ),
    ConceptPattern(
        "MATH-010-002",
        "function_patterns",
        "recursive_function",
        "Define recursive function",
        r"\blet\s+rec\s+\w+",
    ),
    ConceptPattern(
        "MATH-010-003",
        "pattern_matching",
        "match_expression",
        "Pattern match expression",
        r"\bmatch\s+\w+\s+with\b",
    ),
    ConceptPattern(
        "MATH-010-004",
        "type_patterns",
        "define_type",
        "Define type alias or variant",
        r"\btype\s+\w+",
    ),
    ConceptPattern(
        "MATH-010-005",
        "module_patterns",
        "open_module",
        "Open module namespace",
        r"\bopen\s+[\w.]+",
    ),
    ConceptPattern(
        "MATH-010-006",
        "function_patterns",
        "pipe_operator",
        "Pipeline operator |>",
        r"\|>",
    ),
    ConceptPattern(
        "MATH-010-007",
        "error_handling",
        "exception_handling",
        "Handle exceptions with try ... with",
        r"\btry\b.*\bwith\b",
    ),
    ConceptPattern(
        "MATH-010-008",
        "module_patterns",
        "define_module",
        "Define module with struct ... end",
        r"\bmodule\s+\w+\s*=\s*struct\b",
    ),
    ConceptPattern(
        "MATH-010-009",
        "module_patterns",
        "functor",
        "Define or apply functor",
        r"\bfunctor\s*\(",
    ),
    ConceptPattern(
        "MATH-010-010",
        "function_patterns",
        "anonymous_function",
        "Create anonymous function with fun",
        r"\bfun\s+\w+\s*->",
    ),
    ConceptPattern(
        "MATH-010-011",
        "type_patterns",
        "option_type",
        "Use option type",
        r"\bSome\s*\(|\bNone\b|\boption\b",
    ),
)

# ---------------------------------------------------------------------------
# Public lookup — language name → pattern tuple
# ---------------------------------------------------------------------------

LANGUAGE_PATTERNS: Final[dict[str, tuple[ConceptPattern, ...]]] = {
    # Pod A — Dynamic
    "python": _POD_A_PYTHON,
    "javascript": _POD_A_JAVASCRIPT,
    "typescript": _POD_A_JAVASCRIPT,  # shares JS patterns
    "ruby": _POD_A_RUBY,
    "php": _POD_A_PHP,
    # Pod B — Systems
    "c": _POD_B_C,
    "cpp": _POD_B_CPP,
    "rust": _POD_B_RUST,
    "go": _POD_B_GO,
    "zig": _POD_B_ZIG,
    # Pod C — Enterprise
    "java": _POD_C_JAVA,
    "csharp": _POD_C_CSHARP,
    "scala": _POD_C_SCALA,
    "kotlin": _POD_C_KOTLIN,
    # Pod D — Mathematical / Functional
    "matlab": _POD_D_MATLAB,
    "r": _POD_D_R,
    "julia": _POD_D_JULIA,
    "mathematica": _POD_D_MATHEMATICA,
    "haskell": _POD_D_HASKELL,
    "ocaml": _POD_D_OCAML,
}


def get_patterns(language: str) -> tuple[ConceptPattern, ...]:
    """Return concept patterns for a given language, or empty tuple if unknown."""
    return LANGUAGE_PATTERNS.get(language.strip().lower(), ())


def all_languages() -> list[str]:
    """Return sorted list of all supported language keys."""
    return sorted(LANGUAGE_PATTERNS.keys())
