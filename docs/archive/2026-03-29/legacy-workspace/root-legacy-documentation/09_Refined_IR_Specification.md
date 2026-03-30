# REFINED-IR SPECIFICATION
## Holy Grail Refinery: Universal Logic Representation Standard

**Version:** 1.0  
**Date:** February 2026  
**Status:** Design Phase - Foundation Schema  
**Document Owner:** Refined-IR Standards Committee

---

## EXECUTIVE SUMMARY

Refined-IR (Refined Intermediate Representation) is the lingua franca of the Holy Grail Refinery. It is a strict, mathematical DSL that describes computational intent without language-specific syntax. Every agent in the system speaks Refined-IR, enabling 14 programming languages to achieve unified comprehension through semantic abstraction rather than code conversion.

**Core Principle:** A LogicNode captures *what* code does, not *how* a specific language does it.

---

## 1. DESIGN PHILOSOPHY

### 1.1 Objectives

1. **Language Agnostic:** Describe logic without reference to any specific programming language syntax
2. **Mathematically Precise:** Enable formal verification through unambiguous specifications
3. **Composable:** LogicNodes can reference other LogicNodes to build complex systems
4. **Traceable:** Complete provenance from source code to final binary
5. **Verifiable:** Support automated equivalence testing with 0.0001% tolerance

### 1.2 Non-Goals

- **NOT a programming language:** Refined-IR is not executable; it's a specification format
- **NOT code conversion:** We don't translate Python → Rust; we extract Python's intent into Refined-IR, and Rust's intent into Refined-IR, then verify they describe the same concept
- **NOT syntax preservation:** Language idioms are abstracted away; only pure logic remains

### 1.3 The Abstraction Hierarchy

```
High Level: User "Vibe" (natural language)
    ↓
PM Level: Feature Contract (structured requirements)
    ↓
CEO Level: Refined-IR Contract (required LogicNodes)
    ↓
Specialist Level: LogicNode Extraction (language → Refined-IR)
    ↓
Audit Level: Verification (Refined-IR → test harness)
    ↓
Sub-Manager Level: Group Standards (consolidated LogicNodes)
    ↓
CEO Level: Master Logic Stream (fused LogicNodes)
    ↓
Low Level: Optimized Binary (LLVM IR → machine code)
```

---

## 2. BASE LOGICNODE SCHEMA

### 2.1 Complete Schema Definition

```typescript
interface LogicNode {
  // === IDENTITY ===
  id: UUID;                    // Unique identifier
  version: SemVer;             // Schema version (currently "1.0.0")
  created_by: AgentID;         // Which agent created this
  created_at: ISO8601;         // Timestamp
  
  // === CLASSIFICATION ===
  paradigm: "dynamic" | "systems" | "enterprise" | "mathematical";
  domain: string;              // e.g., "list_operations", "memory_management"
  concept: string;             // e.g., "filter", "allocate", "multiply"
  
  // === THE LOGIC ===
  intent: string;              // Human-readable description
  inputs: InputSpec[];         // What this logic consumes
  outputs: OutputSpec[];       // What this logic produces
  preconditions: Constraint[]; // What must be true before execution
  postconditions: Constraint[]; // What must be true after execution
  side_effects: SideEffect[];  // Observable effects beyond outputs
  
  // === TRACEABILITY ===
  source_language: string;     // e.g., "python", "rust", "java"
  source_reference: string;    // Library/function/line reference
  source_license: string;      // e.g., "MIT", "Apache-2.0", "BSD-3-Clause"
  confidence: float;           // Extraction confidence (0.0 - 1.0)
  
  // === VERIFICATION ===
  audit_status: "pending" | "verified" | "rejected" | "needs_revision";
  audit_agent: AgentID | null;
  audit_timestamp: ISO8601 | null;
  equivalence_tests_passed: integer;
  equivalence_tests_total: integer;
  verification_tolerance: float; // e.g., 0.0001
  
  // === METADATA ===
  tags: string[];              // Searchable tags
  complexity: "constant" | "logarithmic" | "linear" | "quadratic" | "exponential";
  purity: "pure" | "impure";   // Does it have side effects?
  properties: Record<string, any>; // Extensible metadata
}
```

### 2.2 InputSpec Schema

```typescript
interface InputSpec {
  name: string;                // Parameter name
  type: LogicType;             // Type specification
  constraints: Constraint[];   // Restrictions on this input
  optional: boolean;           // Can be omitted?
  default: Value | null;       // Default value if omitted
  description: string;         // Human-readable explanation
}
```

### 2.3 OutputSpec Schema

```typescript
interface OutputSpec {
  name: string;                // Return value name
  type: LogicType;             // Type specification
  constraints: Constraint[];   // Guarantees about this output
  description: string;         // Human-readable explanation
}
```

---

## 3. UNIVERSAL TYPE SYSTEM

### 3.1 Base Types

All 14 languages must map to these foundational types:

```typescript
type LogicType = 
  // Primitive Types
  | { base: "void" }
  | { base: "boolean" }
  | { base: "integer", bits?: 8 | 16 | 32 | 64 | 128 }
  | { base: "float", bits?: 32 | 64 | 128 }
  | { base: "string", encoding?: "utf8" | "ascii" | "unicode" }
  | { base: "bytes" }
  
  // Collection Types
  | { base: "list", parameters: [LogicType] }
  | { base: "set", parameters: [LogicType] }
  | { base: "map", parameters: [LogicType, LogicType] }
  | { base: "tuple", parameters: LogicType[] }
  
  // Optional/Result Types
  | { base: "option", parameters: [LogicType] }
  | { base: "result", parameters: [LogicType, LogicType] }
  
  // Function Types
  | { base: "function", inputs: LogicType[], outputs: LogicType[] }
  
  // Structural Types
  | { base: "struct", fields: Record<string, LogicType> }
  | { base: "enum", variants: Record<string, LogicType | null> }
  
  // Generic/Abstract Types
  | { base: "generic", name: string, constraints: Constraint[] }
  | { base: "any" }
  | { base: "iterable", parameters: [LogicType] }
  | { base: "awaitable", parameters: [LogicType] }
  | { base: "callable", signature: FunctionType }
```

### 3.2 Type Mapping Examples

#### Example 1: List of Integers

**Python:** `List[int]`  
**JavaScript:** `number[]`  
**Rust:** `Vec<i32>`  
**Java:** `ArrayList<Integer>`

**Refined-IR:**
```json
{
  "base": "list",
  "parameters": [
    { "base": "integer", "bits": 32 }
  ]
}
```

#### Example 2: Optional String

**Python:** `Optional[str]`  
**JavaScript:** `string | null`  
**Rust:** `Option<String>`  
**Java:** `Optional<String>`

**Refined-IR:**
```json
{
  "base": "option",
  "parameters": [
    { "base": "string" }
  ]
}
```

#### Example 3: Map from String to Integer

**Python:** `Dict[str, int]`  
**JavaScript:** `Map<string, number>`  
**Rust:** `HashMap<String, i32>`  
**Java:** `HashMap<String, Integer>`

**Refined-IR:**
```json
{
  "base": "map",
  "parameters": [
    { "base": "string" },
    { "base": "integer", "bits": 32 }
  ]
}
```

---

## 4. CONSTRAINT SYSTEM

### 4.1 Base Constraint Types

```typescript
type Constraint = 
  // Value Constraints
  | { type: "range", min: number, max: number }
  | { type: "length", min: number, max: number }
  | { type: "non_null" }
  | { type: "non_empty" }
  
  // Logical Constraints
  | { type: "predicate", expression: string, message: string }
  | { type: "invariant", expression: string, message: string }
  
  // Structural Constraints
  | { type: "unique_elements" }
  | { type: "sorted", order: "asc" | "desc" }
  
  // Relationship Constraints
  | { type: "subset_of", reference: string }
  | { type: "element_of", set: string }
```

### 4.2 Constraint Examples

#### Length Constraint

```json
{
  "type": "length",
  "min": 1,
  "max": 100,
  "message": "String must be between 1 and 100 characters"
}
```

#### Predicate Constraint

```json
{
  "type": "predicate",
  "expression": "forall(x in collection): x > 0",
  "message": "All elements must be positive"
}
```

#### Invariant Constraint

```json
{
  "type": "invariant",
  "expression": "size(output) <= size(input)",
  "message": "Output cannot be larger than input"
}
```

---

## 5. SIDE EFFECT SYSTEM

### 5.1 Side Effect Types

```typescript
type SideEffect = {
  type: SideEffectType;
  description: string;
  scope: "local" | "external" | "global";
  idempotent: boolean;
}

type SideEffectType =
  // I/O Effects
  | "io_read"
  | "io_write"
  | "network_request"
  | "network_response"
  
  // State Effects
  | "mutation"
  | "allocation"
  | "deallocation"
  | "cache_update"
  
  // System Effects
  | "file_system"
  | "database"
  | "logging"
  | "metrics"
  
  // Concurrency Effects
  | "thread_spawn"
  | "lock_acquire"
  | "lock_release"
  | "channel_send"
  | "channel_receive"
  
  // Domain-Specific Effects
  | "dom_mutation"
  | "ui_render"
  | "transaction"
  | "exception"
```

### 5.2 Side Effect Examples

#### File Write

```json
{
  "type": "file_system",
  "description": "Writes data to file at specified path",
  "scope": "external",
  "idempotent": false
}
```

#### In-Memory Mutation

```json
{
  "type": "mutation",
  "description": "Modifies list in-place",
  "scope": "local",
  "idempotent": true
}
```

---

## 6. COMPLETE LOGICNODE EXAMPLE

### 6.1 Example: Filter Collection

This example shows how Python's `filter()`, JavaScript's `.filter()`, Rust's iterator `.filter()`, and Java's Stream `.filter()` all map to the same LogicNode.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "version": "1.0.0",
  "created_by": "poda_spec_python",
  "created_at": "2026-02-04T15:30:00Z",
  
  "paradigm": "dynamic",
  "domain": "list_operations",
  "concept": "filter_collection",
  
  "intent": "Return elements from a collection that satisfy a predicate function",
  
  "inputs": [
    {
      "name": "source",
      "type": {
        "base": "iterable",
        "parameters": [{ "base": "any" }]
      },
      "constraints": [
        { "type": "non_null" }
      ],
      "optional": false,
      "default": null,
      "description": "The collection to filter"
    },
    {
      "name": "predicate",
      "type": {
        "base": "function",
        "inputs": [{ "base": "any" }],
        "outputs": [{ "base": "boolean" }]
      },
      "constraints": [
        { "type": "non_null" }
      ],
      "optional": false,
      "default": null,
      "description": "Function that returns true for elements to keep"
    }
  ],
  
  "outputs": [
    {
      "name": "result",
      "type": {
        "base": "list",
        "parameters": [{ "base": "any" }]
      },
      "constraints": [
        {
          "type": "predicate",
          "expression": "forall(x in result): x in source",
          "message": "All output elements must exist in input"
        },
        {
          "type": "predicate",
          "expression": "forall(x in result): predicate(x) == true",
          "message": "All output elements must satisfy the predicate"
        },
        {
          "type": "predicate",
          "expression": "forall(x in source): predicate(x) implies x in result",
          "message": "All input elements that satisfy predicate must be in output"
        }
      ],
      "description": "Filtered collection containing only elements that passed predicate"
    }
  ],
  
  "preconditions": [],
  
  "postconditions": [
    {
      "type": "invariant",
      "expression": "size(result) <= size(source)",
      "message": "Output cannot be larger than input"
    }
  ],
  
  "side_effects": [],
  
  "source_language": "python",
  "source_reference": "builtins.filter (Python 3.13 standard library)",
  "source_license": "PSF-2.0",
  "confidence": 0.98,
  
  "audit_status": "verified",
  "audit_agent": "poda_audit",
  "audit_timestamp": "2026-02-04T15:35:00Z",
  "equivalence_tests_passed": 1000,
  "equivalence_tests_total": 1000,
  "verification_tolerance": 0.0001,
  
  "tags": ["filtering", "collection", "pure", "higher-order"],
  "complexity": "linear",
  "purity": "pure",
  "properties": {
    "preserves_order": true,
    "lazy": false,
    "parallel_safe": true
  }
}
```

### 6.2 How Different Languages Map to This LogicNode

**Python:**
```python
filtered = list(filter(lambda x: x > 0, numbers))
```

**JavaScript:**
```javascript
const filtered = numbers.filter(x => x > 0);
```

**Rust:**
```rust
let filtered: Vec<_> = numbers.iter().filter(|&&x| x > 0).collect();
```

**Java:**
```java
List<Integer> filtered = numbers.stream()
    .filter(x -> x > 0)
    .collect(Collectors.toList());
```

**Ruby:**
```ruby
filtered = numbers.select { |x| x > 0 }
```

**All produce the same LogicNode** because they describe the same intent.

---

## 7. LOGICNODE COMPOSITION

### 7.1 Referencing Other LogicNodes

LogicNodes can reference other LogicNodes to build complex operations:

```json
{
  "domain": "data_pipeline",
  "concept": "transform_and_filter",
  "intent": "Map then filter a collection",
  
  "composition": [
    {
      "step": 1,
      "logicnode_ref": "map_collection",
      "inputs": { "source": "input", "mapper": "transform_fn" },
      "outputs": { "result": "mapped" }
    },
    {
      "step": 2,
      "logicnode_ref": "filter_collection",
      "inputs": { "source": "mapped", "predicate": "filter_fn" },
      "outputs": { "result": "output" }
    }
  ]
}
```

### 7.2 Dependency Graph

LogicNodes form a directed acyclic graph (DAG) during fusion:

```
User Input
    ↓
[Validation LogicNode]
    ↓
[Parsing LogicNode]
    ↓
[Transformation LogicNode]
    ↓
[Filtering LogicNode]
    ↓
[Aggregation LogicNode]
    ↓
Output
```

---

## 8. VERIFICATION FRAMEWORK

### 8.1 Equivalence Testing

For a LogicNode to be verified, it must pass equivalence tests:

**Test Generation:**
1. Audit Agent generates 1,000 test cases
2. Test cases cover:
   - Normal cases (80%)
   - Edge cases (15%)
   - Stress tests (5%)

**Test Execution:**
1. Run original source code with test inputs
2. Run LogicNode specification with same inputs
3. Compare outputs with 0.0001% tolerance

**Pass Criteria:**
- **Pure Functions:** Outputs must match exactly
- **Floating Point:** Outputs within 0.0001% relative error
- **Side Effects:** Observable effects must match

### 8.2 Formal Verification

Audit Agents use constraint expressions to verify:

**Precondition Verification:**
```
Before execution: Verify all preconditions hold
If violated: Reject LogicNode with specific violation
```

**Postcondition Verification:**
```
After execution: Verify all postconditions hold
If violated: Reject LogicNode with specific violation
```

**Invariant Verification:**
```
Throughout execution: Verify all invariants maintained
If violated: Reject LogicNode with violation trace
```

---

## 9. POD-SPECIFIC EXTENSIONS

Each Pod extends the base schema with domain-specific types and constraints.

### 9.1 Dynamic Pod Extensions

**Additional Types:**
- `{ base: "any" }` - Dynamic typing
- `{ base: "callable" }` - First-class functions
- `{ base: "iterable" }` - Iteration protocol
- `{ base: "awaitable" }` - Async/await pattern

**Additional Constraints:**
- `{ type: "duck_typed", protocol: string }` - Structural typing

**Additional Side Effects:**
- `"dom_mutation"` - Browser DOM changes
- `"event_emit"` - Event system interaction

### 9.2 Systems Pod Extensions

**Additional Types:**
- `{ base: "pointer", mutability: "const" | "mut" }` - Memory addresses
- `{ base: "owned" }` - Rust ownership
- `{ base: "borrowed", lifetime: string }` - Rust borrowing
- `{ base: "raw_memory", size: number }` - Unstructured memory

**Additional Constraints:**
- `{ type: "memory_safe" }` - No memory leaks/errors
- `{ type: "no_allocation" }` - Stack-only
- `{ type: "thread_safe" }` - Concurrent access safe

**Additional Side Effects:**
- `"heap_allocation"` - Dynamic memory allocation
- `"unsafe_operation"` - Unsafe code block
- `"ffi_call"` - Foreign function interface

### 9.3 Enterprise Pod Extensions

**Additional Types:**
- `{ base: "interface", methods: Record<string, FunctionType> }`
- `{ base: "class", extends: string[], implements: string[] }`
- `{ base: "generic", bounds: LogicType[] }`

**Additional Constraints:**
- `{ type: "null_safe" }` - Cannot be null
- `{ type: "implements", interface: string }` - Interface compliance

**Additional Side Effects:**
- `"database"` - Database interaction
- `"transaction"` - Transactional operation
- `"dependency_injection"` - DI container access

### 9.4 Mathematical Pod Extensions

**Additional Types:**
- `{ base: "matrix", dimensions: [number, number], dtype: string }`
- `{ base: "vector", size: number, dtype: string }`
- `{ base: "tensor", shape: number[], dtype: string }`
- `{ base: "distribution", family: string, parameters: Record<string, number> }`

**Additional Constraints:**
- `{ type: "dimensions_match", reference: string }` - Matrix compatibility
- `{ type: "positive_definite" }` - Mathematical property
- `{ type: "normalized" }` - Sum to 1 or magnitude 1

**Additional Side Effects:**
- `"random_generation"` - Non-deterministic randomness
- `"numerical_approximation"` - Precision loss possible

---

## 10. SCHEMA VERSIONING

### 10.1 Version Strategy

**Format:** Semantic Versioning (SemVer)  
**Current Version:** 1.0.0

**Version Changes:**
- **Major (1.x.x → 2.x.x):** Breaking changes to schema structure
- **Minor (x.1.x → x.2.x):** Backward-compatible additions
- **Patch (x.x.1 → x.x.2):** Clarifications, bug fixes

### 10.2 Migration Strategy

When schema version updates:

1. **Audit Agents** updated to understand both old and new versions
2. **Migration Period:** 30 days where both versions accepted
3. **Automatic Conversion:** Old LogicNodes auto-converted to new schema
4. **Validation:** Re-verification required after conversion

---

## 11. CONFLICT RESOLUTION

### 11.1 When Specialists Disagree

If two Specialists produce LogicNodes for the same concept that differ:

**Resolution Process:**
1. **Sub-Manager** detects conflict (different inputs, outputs, or constraints)
2. **Flag for Review:** Mark both LogicNodes as `needs_revision`
3. **IS Agent Query:** Request authoritative documentation
4. **CEO Arbitration:** CEO decides which interpretation is correct
5. **Specialist Re-extraction:** Losing Specialist re-extracts with clarification

### 11.2 Concept Evolution

When a concept evolves (e.g., Python 3.12 → 3.13):

1. **IS Agent** detects new documentation
2. **Broadcast:** Standards Manifesto via Protocol Sigma
3. **Re-extraction:** Specialists re-extract affected concepts
4. **Versioning:** New LogicNode version created, old version deprecated
5. **Migration:** Missions using old version flagged for update

---

## 12. VALIDATION RULES

### 12.1 Schema Validation

Before a LogicNode is accepted:

**Structural Validation:**
- All required fields present
- Types conform to LogicType spec
- UUIDs valid and unique
- Timestamps in ISO-8601 format

**Semantic Validation:**
- Domain exists in pod's domain registry
- Concept defined in domain's concept catalog
- Types compatible (inputs → outputs)
- Constraints syntactically valid

**Consistency Validation:**
- Inputs referenced in outputs exist
- Postconditions reference actual outputs
- Side effects match purity declaration

### 12.2 Automated Rejection

LogicNodes automatically rejected if:
- Schema version unsupported
- Required field missing
- Type not in universal type system
- Constraint expression invalid syntax
- Confidence < 0.80 (too uncertain)

---

## 13. BEST PRACTICES

### 13.1 For Specialists

1. **Be Precise:** Use specific types, not `any` unless truly dynamic
2. **Document Constraints:** Capture all invariants and preconditions
3. **Trace Sources:** Always include `source_reference` and `source_license`
4. **High Confidence:** Only submit LogicNodes with confidence > 0.90
5. **Pure When Possible:** Prefer pure functions over side effects

### 13.2 For Audit Agents

1. **Comprehensive Testing:** Cover normal, edge, and stress cases
2. **Strict Tolerance:** 0.0001% is a hard limit, not a guideline
3. **Document Failures:** Provide specific error messages on rejection
4. **Verify Constraints:** Don't just test I/O, validate all constraints

### 13.3 For Sub-Managers

1. **Semantic Equivalence:** Verify concepts match by intent, not implementation
2. **Conservative Merging:** When in doubt, don't merge
3. **Preserve All Properties:** Merged LogicNode must satisfy all input constraints

---

## APPENDIX A: COMPLETE TYPE GRAMMAR

```typescript
// Base Type System
type LogicType =
  | PrimitiveType
  | CollectionType
  | OptionType
  | FunctionType
  | StructuralType
  | GenericType
  | PodExtensionType;

type PrimitiveType =
  | { base: "void" }
  | { base: "boolean" }
  | { base: "integer", bits?: number }
  | { base: "float", bits?: number }
  | { base: "string", encoding?: string }
  | { base: "bytes" };

type CollectionType =
  | { base: "list", parameters: [LogicType] }
  | { base: "set", parameters: [LogicType] }
  | { base: "map", parameters: [LogicType, LogicType] }
  | { base: "tuple", parameters: LogicType[] };

type OptionType =
  | { base: "option", parameters: [LogicType] }
  | { base: "result", parameters: [LogicType, LogicType] };

type FunctionType = {
  base: "function",
  inputs: LogicType[],
  outputs: LogicType[]
};

type StructuralType =
  | { base: "struct", fields: Record<string, LogicType> }
  | { base: "enum", variants: Record<string, LogicType | null> };

type GenericType = {
  base: "generic",
  name: string,
  constraints: Constraint[]
};
```

---

## APPENDIX B: EXPRESSION LANGUAGE

Constraint expressions use a simple predicate logic:

**Operators:**
- Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Logical: `and`, `or`, `not`, `implies`
- Quantifiers: `forall(x in collection): predicate`, `exists(x in collection): predicate`
- Set: `in`, `subset`, `superset`
- Arithmetic: `+`, `-`, `*`, `/`, `%`

**Functions:**
- `size(collection)` - number of elements
- `length(string)` - string length
- `min(collection)`, `max(collection)`
- `sum(collection)`, `average(collection)`
- `sorted(collection)`, `unique(collection)`

**Example Expressions:**
```
forall(x in result): x > 0
size(output) == size(input)
min(collection) >= 0 and max(collection) <= 100
exists(x in list): x == target
```

---

**Document End**
