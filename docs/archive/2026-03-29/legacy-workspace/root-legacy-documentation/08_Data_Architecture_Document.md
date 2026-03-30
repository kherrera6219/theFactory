# DATA ARCHITECTURE DOCUMENT
## Holy Grail Refinery: Shared Database Specifications

**Version:** 1.0  
**Date:** February 2026  
**Status:** Design Phase  
**Document Owner:** Data Architecture Team

---

## EXECUTIVE SUMMARY

The Holy Grail Refinery uses 5 shared databases to enable coordination across 35 agents while maintaining agent context isolation. This document specifies the purpose, schema, access patterns, and data lifecycle for each database.

**The 5 Databases:**
1. **Semantic Knowledge Lake** (Vector DB) - Indexed documentation for 14 languages
2. **Global State Graph** (PostgreSQL) - Mission state and coordination
3. **LogicNode Registry** (Redis + Git) - Refined-IR artifacts
4. **Traceability Ledger** (SQLite) - Chain of custody audit trail
5. **Model & Data Store** (PostgreSQL) - ML models and shared datasets

---

## 1. SEMANTIC KNOWLEDGE LAKE

### 1.1 Purpose

Centralized semantic search engine containing indexed documentation for all 14 programming languages, enabling Specialists to query for information rather than relying solely on cached context.

### 1.2 Technology Stack

- **Vector Database:** Milvus (or Weaviate as alternative)
- **Indexing Framework:** LlamaIndex
- **Storage:** Local NVMe SSD (1TB)
- **Embedding Model:** Google text-embedding-004

### 1.3 Content Structure

```
Knowledge Lake
├── Languages (14)
│   ├── Python
│   │   ├── Official Documentation (python.org)
│   │   ├── PEP Standards
│   │   ├── Popular Libraries (NumPy, Pandas, Django, FastAPI)
│   │   └── Community Knowledge (StackOverflow, GitHub Issues)
│   ├── JavaScript
│   │   ├── MDN Documentation
│   │   ├── ECMAScript Specifications
│   │   ├── Framework Docs (React, Vue, Node.js)
│   │   └── npm Package Documentation
│   └── [... 12 other languages]
├── Frameworks & Libraries
├── Best Practices & Patterns
├── Security Knowledge (CVEs, OWASP)
└── Benchmarks & Performance Data
```

### 1.4 Schema

**Document Chunk:**
```json
{
  "chunk_id": "uuid-v4",
  "source": "python.org/docs/library/itertools.html",
  "language": "python",
  "category": "standard_library",
  "subcategory": "itertools",
  "title": "itertools.filter",
  "content": "filter(predicate, iterable) → iterator...",
  "embedding": [0.123, -0.456, ...], // 768-dim vector
  "metadata": {
    "version": "3.13",
    "indexed_at": "ISO-8601",
    "chunk_size": 512,
    "overlapping": true
  }
}
```

### 1.5 Access Patterns

**Query Flow:**
```
Specialist → "How does Rust handle async I/O?"
    ↓
LlamaIndex → Semantic search in Vector DB
    ↓
Vector DB → Returns top 10 most relevant chunks
    ↓
LlamaIndex → Assembles context from chunks
    ↓
Specialist ← "Here's Rust async I/O documentation..."
```

**Access Control:**
- **Readers:** All Specialists, Sub-Managers, CEO, IS Agent
- **Writers:** IS Agent only
- **Update Frequency:** Continuous (IS Agent indexes new docs as released)

### 1.6 Query Examples

**Semantic Search:**
```python
query = "memory-safe pattern for iterating collections"
results = knowledge_lake.search(
    query=query,
    languages=["rust", "cpp"],
    top_k=5,
    filter={"category": "memory_management"}
)
```

**Returns:**
- Rust ownership patterns
- C++ RAII patterns
- Smart pointer usage
- Iterator invalidation rules

### 1.7 Indexing Pipeline

```
New Documentation Release
    ↓
IS Agent detects update
    ↓
Download documentation
    ↓
LlamaIndex: Chunk into 512-token segments with 50-token overlap
    ↓
Generate embeddings (Google text-embedding-004)
    ↓
Store in Vector DB with metadata
    ↓
Broadcast "documentation_update" via Protocol Sigma
```

### 1.8 Storage Requirements

| Component | Size |
|-----------|------|
| **Python Docs** | ~50GB (all packages) |
| **JavaScript/Node** | ~40GB |
| **Java Ecosystem** | ~60GB |
| **Other 11 Languages** | ~150GB |
| **Embeddings** | ~100GB (768-dim vectors) |
| **Metadata** | ~10GB |
| **Total** | ~410GB (with room for growth to 1TB) |

---

## 2. GLOBAL STATE GRAPH

### 2.1 Purpose

Central coordination database tracking mission state, agent assignments, LogicNode status, and workflow progress. Enables LangGraph orchestration and provides visibility into system operations.

### 2.2 Technology Stack

- **Database:** PostgreSQL 16
- **Orchestration:** LangGraph (uses Postgres as state backend)
- **Storage:** Local SSD
- **Access:** SQL + LangGraph API

### 2.3 Schema

#### 2.3.1 Missions Table

```sql
CREATE TABLE missions (
    mission_id UUID PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    created_by VARCHAR(50) NOT NULL, -- 'pm_agent'
    status VARCHAR(20) NOT NULL, -- 'planning|extraction|verification|fusion|compilation|deployment|complete|failed'
    
    feature_contract JSONB NOT NULL, -- Full Feature Contract from PM
    refined_ir_contract JSONB, -- Refined-IR Contract from CEO
    
    assigned_pods TEXT[], -- ['dynamic', 'systems']
    priority VARCHAR(10), -- 'low|normal|high|critical'
    
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    estimated_completion TIMESTAMP,
    
    current_phase VARCHAR(20),
    progress_percent INTEGER DEFAULT 0,
    
    budget_allocated DECIMAL(10,2),
    cost_incurred DECIMAL(10,2) DEFAULT 0,
    
    metadata JSONB
);

CREATE INDEX idx_missions_status ON missions(status);
CREATE INDEX idx_missions_created_at ON missions(created_at DESC);
```

#### 2.3.2 LogicNodes Table

```sql
CREATE TABLE logicnodes (
    logicnode_id UUID PRIMARY KEY,
    mission_id UUID REFERENCES missions(mission_id),
    
    concept VARCHAR(100) NOT NULL,
    domain VARCHAR(100) NOT NULL,
    paradigm VARCHAR(20) NOT NULL, -- 'dynamic|systems|enterprise|mathematical'
    
    source_language VARCHAR(20) NOT NULL,
    source_reference TEXT,
    created_by VARCHAR(50) NOT NULL, -- agent_id
    created_at TIMESTAMP NOT NULL,
    
    logicnode_json JSONB NOT NULL, -- Full LogicNode spec
    
    status VARCHAR(20) NOT NULL, -- 'extracted|pending_verification|verified|rejected|fused'
    verified_by VARCHAR(50), -- audit_agent_id
    verified_at TIMESTAMP,
    
    verification_details JSONB, -- test results
    
    rejection_reason TEXT,
    retry_count INTEGER DEFAULT 0,
    
    included_in_fusion BOOLEAN DEFAULT FALSE,
    fusion_timestamp TIMESTAMP
);

CREATE INDEX idx_logicnodes_mission ON logicnodes(mission_id);
CREATE INDEX idx_logicnodes_status ON logicnodes(status);
CREATE INDEX idx_logicnodes_concept ON logicnodes(concept);
```

#### 2.3.3 Agent Assignments Table

```sql
CREATE TABLE agent_assignments (
    assignment_id UUID PRIMARY KEY,
    mission_id UUID REFERENCES missions(mission_id),
    agent_id VARCHAR(50) NOT NULL,
    
    task_type VARCHAR(50) NOT NULL, -- 'extraction|verification|consolidation|fusion'
    task_description TEXT,
    assigned_at TIMESTAMP NOT NULL,
    
    status VARCHAR(20) NOT NULL, -- 'assigned|in_progress|completed|failed'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    output_logicnode_ids UUID[],
    
    metadata JSONB
);

CREATE INDEX idx_assignments_agent ON agent_assignments(agent_id);
CREATE INDEX idx_assignments_mission ON agent_assignments(mission_id);
```

### 2.4 Access Patterns

**Read Operations:**
- **CEO:** Full read access to all tables
- **PM Agent:** Read missions table for status updates
- **Sub-Managers:** Read logicnodes for their pod
- **Specialists:** Read own assignments
- **Accountant:** Read mission costs
- **System Integration Tester:** Read all for validation

**Write Operations:**
- **CEO:** Insert/update missions, create assignments
- **Specialists:** Insert logicnodes
- **QC/Audit Agents:** Update logicnode status (verification)
- **Sub-Managers:** Update logicnode status (consolidation)
- **Accountant:** Update mission costs

### 2.5 LangGraph Integration

LangGraph uses Global State Graph to persist workflow state:

```python
# LangGraph checkpoint stored in Postgres
checkpoint = {
    "mission_id": "uuid",
    "current_node": "extraction_phase",
    "completed_nodes": ["planning", "assignment"],
    "pending_nodes": ["verification", "fusion"],
    "state_data": {
        "logicnodes_extracted": 47,
        "logicnodes_verified": 12,
        "logicnodes_pending": 35
    }
}
```

**Recovery:** If system crashes, LangGraph reads last checkpoint and resumes.

---

## 3. LOGICNODE REGISTRY

### 3.1 Purpose

Fast-access storage for LogicNodes with Git version control for complete history and rollback capabilities.

### 3.2 Technology Stack

- **Primary Storage:** Redis (in-memory, fast access)
- **Persistent Storage:** Git repository (local, version-controlled)
- **Hybrid Architecture:** Redis for active missions, Git for history

### 3.3 Data Flow

```
Specialist creates LogicNode
    ↓
Stored in Redis key-value (fast access)
    ↓
Simultaneously committed to Git (persistent history)
    ↓
QC/Audit reads from Redis (fast verification)
    ↓
After mission complete: Redis evicted, Git remains
```

### 3.4 Redis Schema

**Key Structure:**
```
logicnode:{mission_id}:{logicnode_id} → JSON
mission:{mission_id}:logicnodes → Set of logicnode_ids
pod:{pod_name}:logicnodes → Set of logicnode_ids (for pod queries)
```

**Example:**
```redis
SET logicnode:mission-123:ln-456 '{
  "id": "ln-456",
  "concept": "filter_collection",
  "domain": "list_operations",
  ...
}'

SADD mission:mission-123:logicnodes ln-456
SADD pod:dynamic:logicnodes ln-456
```

**TTL:** 48 hours (auto-expire after mission complete)

### 3.5 Git Schema

**Repository Structure:**
```
logicnode-registry/
├── missions/
│   ├── mission-123/
│   │   ├── metadata.json
│   │   ├── logicnodes/
│   │   │   ├── ln-456.json
│   │   │   ├── ln-457.json
│   │   │   └── ...
│   │   └── fusion/
│   │       └── master-logic-stream.json
│   └── mission-124/
└── index.json (mission registry)
```

**Commit Strategy:**
- Every LogicNode creation → Git commit
- Verification pass/fail → Git commit with tag
- Fusion complete → Git commit with final output
- Mission complete → Git tag `mission-123-complete`

**Commit Message Format:**
```
[mission-123] LogicNode ln-456 created by poda_spec_python

concept: filter_collection
status: pending_verification
```

### 3.6 Access Patterns

**Fast Path (Active Missions):**
```
Specialist → Redis → LogicNode (< 1ms)
```

**Historical Path (Past Missions):**
```
User/Audit → Git → LogicNode history (< 100ms)
```

---

## 4. TRACEABILITY LEDGER

### 4.1 Purpose

Immutable audit trail providing complete chain of custody for every LogicNode from source code to final binary. Critical for compliance, security audits, and debugging.

### 4.2 Technology Stack

- **Database:** SQLite (single file, ACID guarantees)
- **Storage:** Local SSD
- **Backup:** Daily snapshots to external storage

### 4.3 Schema

```sql
CREATE TABLE traceability_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL, -- ISO-8601
    mission_id TEXT NOT NULL,
    logicnode_id TEXT NOT NULL,
    
    event_type TEXT NOT NULL, -- 'extraction|verification|rejection|consolidation|fusion|compilation'
    agent_id TEXT NOT NULL,
    
    source_info TEXT, -- Original library/function reference
    source_language TEXT,
    source_version TEXT,
    source_license TEXT,
    
    action_details TEXT, -- JSON string of what happened
    
    verification_signature TEXT, -- Audit agent signature
    verification_tests_passed INTEGER,
    verification_tests_total INTEGER,
    
    output_artifact_hash TEXT, -- SHA-256 of output
    
    metadata TEXT -- JSON string for extensibility
);

CREATE INDEX idx_trace_mission ON traceability_log(mission_id);
CREATE INDEX idx_trace_logicnode ON traceability_log(logicnode_id);
CREATE INDEX idx_trace_timestamp ON traceability_log(timestamp);
CREATE INDEX idx_trace_agent ON traceability_log(agent_id);
```

### 4.4 Example Entries

**Extraction Event:**
```sql
INSERT INTO traceability_log VALUES (
    NULL,
    '2026-02-04T10:23:45Z',
    'mission-123',
    'ln-456',
    'extraction',
    'poda_spec_python',
    'numpy==1.26.0 - numpy.filter function, line 42',
    'python',
    '1.26.0',
    'BSD-3-Clause',
    '{"extracted_from": "numpy.filter", "extraction_method": "AST_analysis"}',
    NULL,
    NULL,
    NULL,
    'sha256:abc123...',
    '{}'
);
```

**Verification Event:**
```sql
INSERT INTO traceability_log VALUES (
    NULL,
    '2026-02-04T10:25:12Z',
    'mission-123',
    'ln-456',
    'verification',
    'poda_audit',
    NULL, NULL, NULL, NULL,
    '{"verification_method": "equivalence_testing"}',
    'audit_signature:sha256:xyz789',
    1000,
    1000,
    'sha256:def456...',
    '{"tolerance": 0.0001, "pass": true}'
);
```

### 4.5 Query Patterns

**Trace LogicNode Lineage:**
```sql
SELECT * FROM traceability_log 
WHERE logicnode_id = 'ln-456' 
ORDER BY timestamp ASC;
```

**Returns:**
1. Extraction from NumPy by Python Specialist
2. Verification (pass) by Audit Agent
3. Consolidation into Group Standard by Sub-Manager
4. Fusion into Master Logic Stream by CEO
5. Compilation into final binary

**Compliance Report:**
```sql
SELECT source_license, COUNT(*) as count
FROM traceability_log
WHERE mission_id = 'mission-123' AND event_type = 'extraction'
GROUP BY source_license;
```

**Returns:**
- BSD-3-Clause: 23 LogicNodes
- MIT: 18 LogicNodes
- Apache-2.0: 6 LogicNodes

### 4.6 Immutability

- **Append-only:** No UPDATE or DELETE operations allowed
- **Integrity:** SQLite Write-Ahead Logging (WAL) mode ensures ACID
- **Backup:** Daily snapshots ensure recovery

---

## 5. MODEL & DATA STORE

### 5.1 Purpose

Store ML models, training data, and shared datasets used by agents. Supports:
- Embedding models for Knowledge Lake
- Fine-tuned specialist models (future)
- Benchmark datasets for verification
- Shared test case libraries

### 5.2 Technology Stack

- **Database:** PostgreSQL 16 (structured metadata)
- **Blob Storage:** Local filesystem (large binary files)
- **Storage:** Local SSD

### 5.3 Schema

```sql
CREATE TABLE models (
    model_id UUID PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) NOT NULL, -- 'embedding|specialist|classifier'
    version VARCHAR(20) NOT NULL,
    
    framework VARCHAR(20), -- 'pytorch|tensorflow|transformers'
    created_at TIMESTAMP NOT NULL,
    created_by VARCHAR(50),
    
    file_path TEXT NOT NULL, -- Local filesystem path
    file_size_bytes BIGINT,
    checksum_sha256 TEXT NOT NULL,
    
    metadata JSONB,
    performance_metrics JSONB
);

CREATE TABLE datasets (
    dataset_id UUID PRIMARY KEY,
    dataset_name VARCHAR(100) NOT NULL,
    dataset_type VARCHAR(50) NOT NULL, -- 'test_cases|benchmarks|training'
    language VARCHAR(20), -- Associated language or 'all'
    
    created_at TIMESTAMP NOT NULL,
    created_by VARCHAR(50),
    
    file_path TEXT NOT NULL,
    file_size_bytes BIGINT,
    checksum_sha256 TEXT NOT NULL,
    row_count INTEGER,
    
    metadata JSONB
);
```

### 5.4 Example Data

**Embedding Model:**
```sql
INSERT INTO models VALUES (
    gen_random_uuid(),
    'google-text-embedding-004',
    'embedding',
    '1.0',
    'transformers',
    NOW(),
    'is_agent',
    '/data/models/text-embedding-004.bin',
    1073741824, -- 1GB
    'sha256:...',
    '{"dimensions": 768, "max_tokens": 8192}',
    '{"avg_latency_ms": 50, "throughput": 1000}'
);
```

**Test Dataset:**
```sql
INSERT INTO datasets VALUES (
    gen_random_uuid(),
    'python-equivalence-tests',
    'test_cases',
    'python',
    NOW(),
    'poda_audit',
    '/data/datasets/python-tests.jsonl',
    52428800, -- 50MB
    'sha256:...',
    10000,
    '{"test_categories": ["edge_cases", "normal", "stress"]}'
);
```

### 5.5 Access Patterns

- **IS Agent:** Read/write models (updates embeddings)
- **QC/Audit Agents:** Read datasets (verification test cases)
- **All Specialists:** Read models (embedding generation)

---

## 6. DATA LIFECYCLE MANAGEMENT

### 6.1 Mission Data Lifecycle

```
Mission Created
    ↓
[Active: Data in Redis + Postgres + Traceability]
    ↓
Mission Completed
    ↓
[Retention: Redis TTL expires (48h), Postgres retained, Git tagged]
    ↓
After 30 Days
    ↓
[Archive: Postgres compressed, Git remains, Traceability remains]
    ↓
After 1 Year
    ↓
[Long-term: Postgres optionally purged, Git/Traceability retained indefinitely]
```

### 6.2 Knowledge Lake Updates

- **Continuous:** IS Agent indexes new docs as released
- **Stale Content:** Docs older than 2 years flagged for review
- **Deprecated:** Old versions marked as deprecated but retained

### 6.3 Backup Strategy

| Database | Backup Frequency | Retention |
|----------|-----------------|-----------|
| **Knowledge Lake** | Weekly full | 30 days |
| **Global State Graph** | Daily incremental | 90 days |
| **LogicNode Registry (Git)** | Continuous (Git) | Indefinite |
| **Traceability Ledger** | Daily | Indefinite |
| **Model & Data Store** | Weekly | 1 year |

---

## 7. PERFORMANCE OPTIMIZATION

### 7.1 Read-Heavy Workloads

**Knowledge Lake:**
- Vector DB query caching
- Precomputed embeddings for common queries
- Read replicas for scaling

**Global State Graph:**
- PostgreSQL connection pooling (max 100 connections)
- Read replicas for status queries
- Materialized views for common aggregations

### 7.2 Write-Heavy Workloads

**LogicNode Registry (Redis):**
- Pipelined writes for batch operations
- Asynchronous Git commits (don't block Redis)

**Traceability Ledger:**
- Batch inserts (buffer up to 100 entries)
- WAL mode for concurrent writes

---

## 8. MONITORING AND HEALTH

### 8.1 Key Metrics

| Database | Metric | Target | Alert |
|----------|--------|--------|-------|
| **Knowledge Lake** | Query latency | < 500ms p95 | > 1s |
| **Global State Graph** | Connection pool usage | < 80% | > 90% |
| **LogicNode Registry** | Redis memory usage | < 4GB | > 4.5GB |
| **Traceability Ledger** | Write latency | < 10ms | > 50ms |
| **Model & Data Store** | Disk usage | < 800GB | > 900GB |

### 8.2 Health Checks

Each database has health check endpoint:
```
GET /health/knowledge-lake → {status: "healthy", latency_ms: 234}
GET /health/state-graph → {status: "healthy", connections: 23/100}
GET /health/logicnode-registry → {status: "healthy", memory_mb: 2048}
GET /health/traceability → {status: "healthy", size_mb: 5120}
GET /health/model-store → {status: "healthy", disk_usage_gb: 456}
```

---

## APPENDIX: SCHEMA MIGRATION STRATEGY

### Versioning

- Schema version tracked in each database
- Migration scripts versioned with Git
- Zero-downtime migrations when possible

### Example Migration

```sql
-- Migration: Add "confidence" field to LogicNodes
-- Version: 1.1
-- Date: 2026-03-01

BEGIN;

ALTER TABLE logicnodes 
ADD COLUMN confidence DECIMAL(3,2) DEFAULT 0.95;

UPDATE schema_version SET version = '1.1', updated_at = NOW();

COMMIT;
```

---

**Document End**
