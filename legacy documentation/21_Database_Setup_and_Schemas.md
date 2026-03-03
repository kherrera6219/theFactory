# DOCUMENT 21: DATABASE SETUP & SCHEMAS
## Holy Grail Refinery - Development Specifications

**Document ID:** 21  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

The Holy Grail Refinery uses **5 specialized PostgreSQL databases** to provide persistent storage, knowledge management, and operational state tracking for all 35 agents. This document provides complete setup instructions, schema definitions, migration strategies, and operational procedures for deploying the database infrastructure on local AW1 hardware.

**Database Architecture:**
1. **Knowledge Lake** - Concepts, templates, documentation
2. **State Graph** - Agent states, task tracking, workflows
3. **LogicNode Registry** - Extracted computational abstractions
4. **Traceability Ledger** - Audit trails, provenance
5. **Model Store** - ML models, embeddings, training data

---

## TABLE OF CONTENTS

1. [Infrastructure Setup](#1-infrastructure-setup)
2. [Database 1: Knowledge Lake](#2-database-1-knowledge-lake)
3. [Database 2: State Graph](#3-database-2-state-graph)
4. [Database 3: LogicNode Registry](#4-database-3-logicnode-registry)
5. [Database 4: Traceability Ledger](#5-database-4-traceability-ledger)
6. [Database 5: Model Store](#6-database-5-model-store)
7. [Connection Pooling](#7-connection-pooling)
8. [Migration Management](#8-migration-management)
9. [Backup & Recovery](#9-backup--recovery)
10. [Performance Optimization](#10-performance-optimization)

---

## 1. INFRASTRUCTURE SETUP

### 1.1 Docker Container Configuration

**File:** `docker-compose.yml` (PostgreSQL service)

```yaml
services:
  postgres-main:
    image: postgres:16-alpine
    container_name: hgr-postgres
    restart: unless-stopped
    
    ports:
      - "5432:5432"
    
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_MULTIPLE_DATABASES: knowledge_lake,state_graph,logicnode_registry,traceability_ledger,model_store
      PGDATA: /var/lib/postgresql/data/pgdata
    
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./scripts/init-databases.sh:/docker-entrypoint-initdb.d/init-databases.sh
      - ./backups:/backups
    
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    
    networks:
      - hgr-network
    
    # Resource allocation for AW1
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
    
    command: >
      postgres
      -c max_connections=200
      -c shared_buffers=2GB
      -c effective_cache_size=6GB
      -c maintenance_work_mem=512MB
      -c checkpoint_completion_target=0.9
      -c wal_buffers=16MB
      -c default_statistics_target=100
      -c random_page_cost=1.1
      -c effective_io_concurrency=200
      -c work_mem=10MB
      -c min_wal_size=1GB
      -c max_wal_size=4GB
      -c max_worker_processes=4
      -c max_parallel_workers_per_gather=2
      -c max_parallel_workers=4
      -c max_parallel_maintenance_workers=2

volumes:
  postgres-data:
    driver: local

networks:
  hgr-network:
    driver: bridge
```

### 1.2 Multi-Database Initialization Script

**File:** `scripts/init-databases.sh`

```bash
#!/bin/bash
set -e

# Parse database names from environment variable
IFS=',' read -ra DATABASES <<< "$POSTGRES_MULTIPLE_DATABASES"

echo "Creating databases..."

for db in "${DATABASES[@]}"; do
    echo "  Creating database: $db"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        CREATE DATABASE $db;
        GRANT ALL PRIVILEGES ON DATABASE $db TO $POSTGRES_USER;
EOSQL
done

echo "✓ All databases created successfully"
```

### 1.3 Environment Variables

**File:** `.env`

```bash
# PostgreSQL Configuration
POSTGRES_USER=hgr_admin
POSTGRES_PASSWORD=<secure_password>
POSTGRES_HOST=postgres-main
POSTGRES_PORT=5432

# Database names
DB_KNOWLEDGE=knowledge_lake
DB_STATE=state_graph
DB_LOGICNODE=logicnode_registry
DB_TRACEABILITY=traceability_ledger
DB_MODEL=model_store

# Connection pooling
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
```

---

## 2. DATABASE 1: KNOWLEDGE LAKE

**Purpose:** Store concepts, templates, documentation, and cross-language mappings

### 2.1 Schema Definition

```sql
-- Database: knowledge_lake
-- Schema version: 1.0

-- ============================================================================
-- TABLE: concepts
-- Stores all programming concepts across 14 languages
-- ============================================================================
CREATE TABLE concepts (
    concept_id VARCHAR(20) PRIMARY KEY,  -- e.g., 'DYN-001-001'
    name VARCHAR(100) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    pod VARCHAR(10) NOT NULL,  -- A, B, C, D
    intent TEXT NOT NULL,
    is_pure BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT unique_concept UNIQUE (pod, domain, name)
);

CREATE INDEX idx_concepts_domain ON concepts(domain);
CREATE INDEX idx_concepts_pod ON concepts(pod);
CREATE INDEX idx_concepts_name ON concepts(name);

-- ============================================================================
-- TABLE: language_mappings
-- Cross-language syntax mappings for each concept
-- ============================================================================
CREATE TABLE language_mappings (
    mapping_id SERIAL PRIMARY KEY,
    concept_id VARCHAR(20) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    language VARCHAR(20) NOT NULL,  -- python, javascript, rust, etc.
    syntax TEXT NOT NULL,
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_mapping UNIQUE (concept_id, language)
);

CREATE INDEX idx_mappings_language ON language_mappings(language);
CREATE INDEX idx_mappings_concept ON language_mappings(concept_id);

-- ============================================================================
-- TABLE: logicnode_templates
-- Templates for generating LogicNodes from concepts
-- ============================================================================
CREATE TABLE logicnode_templates (
    template_id SERIAL PRIMARY KEY,
    concept_id VARCHAR(20) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    
    -- LogicNode structure (JSON)
    inputs JSONB NOT NULL,
    outputs JSONB NOT NULL,
    preconditions JSONB DEFAULT '[]'::jsonb,
    postconditions JSONB DEFAULT '[]'::jsonb,
    side_effects JSONB DEFAULT '[]'::jsonb,
    
    -- Type system
    type_constraints JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_templates_concept ON logicnode_templates(concept_id);

-- ============================================================================
-- TABLE: documentation
-- Human-readable documentation for concepts
-- ============================================================================
CREATE TABLE documentation (
    doc_id SERIAL PRIMARY KEY,
    concept_id VARCHAR(20) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    
    description TEXT NOT NULL,
    examples JSONB DEFAULT '[]'::jsonb,  -- Array of code examples
    best_practices TEXT,
    common_pitfalls TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_docs_concept ON documentation(concept_id);

-- ============================================================================
-- TABLE: type_extensions
-- Pod-specific type system extensions
-- ============================================================================
CREATE TABLE type_extensions (
    extension_id SERIAL PRIMARY KEY,
    pod VARCHAR(10) NOT NULL,
    type_name VARCHAR(50) NOT NULL,
    base_type VARCHAR(50) NOT NULL,
    parameters JSONB DEFAULT '[]'::jsonb,
    
    description TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_type_extension UNIQUE (pod, type_name)
);

CREATE INDEX idx_type_extensions_pod ON type_extensions(pod);

-- ============================================================================
-- TABLE: constraint_catalog
-- Reusable constraint templates
-- ============================================================================
CREATE TABLE constraint_catalog (
    constraint_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    type VARCHAR(20) NOT NULL,  -- predicate, range, dependency
    template TEXT NOT NULL,
    
    description TEXT,
    examples JSONB DEFAULT '[]'::jsonb,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_constraints_type ON constraint_catalog(type);

-- ============================================================================
-- VIEWS: Convenience queries
-- ============================================================================

-- View: All concepts with their language mappings
CREATE VIEW v_concept_mappings AS
SELECT 
    c.concept_id,
    c.name,
    c.domain,
    c.pod,
    c.intent,
    json_agg(
        json_build_object(
            'language', lm.language,
            'syntax', lm.syntax,
            'notes', lm.notes
        )
    ) AS language_mappings
FROM concepts c
LEFT JOIN language_mappings lm ON c.concept_id = lm.concept_id
GROUP BY c.concept_id, c.name, c.domain, c.pod, c.intent;

-- View: Concepts with templates
CREATE VIEW v_concept_templates AS
SELECT 
    c.concept_id,
    c.name,
    c.domain,
    c.pod,
    lt.inputs,
    lt.outputs,
    lt.preconditions,
    lt.postconditions,
    lt.side_effects
FROM concepts c
JOIN logicnode_templates lt ON c.concept_id = lt.concept_id;

-- ============================================================================
-- SEED DATA: Example concept
-- ============================================================================

-- Insert example concept: Python dictionary lookup
INSERT INTO concepts (concept_id, name, domain, pod, intent, is_pure) VALUES
('DYN-003-001', 'get', 'dictionary_operations', 'A', 'Retrieve value by key from dictionary', true);

INSERT INTO language_mappings (concept_id, language, syntax, notes) VALUES
('DYN-003-001', 'python', 'dict.get(key, default)', 'Returns None if key not found'),
('DYN-003-001', 'javascript', 'obj[key] ?? default', 'Uses nullish coalescing'),
('DYN-003-001', 'ruby', 'hash.fetch(key, default)', 'Raises error without default'),
('DYN-003-001', 'php', '$array[$key] ?? $default', 'Null coalescing operator');

INSERT INTO logicnode_templates (concept_id, inputs, outputs, preconditions, postconditions) VALUES
('DYN-003-001',
 '[{"name": "source", "type": {"base": "map"}}, {"name": "key", "type": {"base": "any"}}, {"name": "default", "type": {"base": "any"}}]'::jsonb,
 '[{"name": "result", "type": {"base": "any"}}]'::jsonb,
 '[]'::jsonb,
 '[{"type": "predicate", "expression": "result != null OR default != null"}]'::jsonb
);
```

### 2.2 Python ORM Models

**File:** `database/models/knowledge.py`

```python
"""
SQLAlchemy ORM models for Knowledge Lake database
"""

from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Concept(Base):
    __tablename__ = 'concepts'
    
    concept_id = Column(String(20), primary_key=True)
    name = Column(String(100), nullable=False)
    domain = Column(String(50), nullable=False)
    pod = Column(String(10), nullable=False)
    intent = Column(Text, nullable=False)
    is_pure = Column(Boolean, default=True)
    
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    mappings = relationship("LanguageMapping", back_populates="concept", cascade="all, delete-orphan")
    templates = relationship("LogicNodeTemplate", back_populates="concept", cascade="all, delete-orphan")
    documentation = relationship("Documentation", back_populates="concept", cascade="all, delete-orphan")


class LanguageMapping(Base):
    __tablename__ = 'language_mappings'
    
    mapping_id = Column(Integer, primary_key=True, autoincrement=True)
    concept_id = Column(String(20), ForeignKey('concepts.concept_id', ondelete='CASCADE'))
    language = Column(String(20), nullable=False)
    syntax = Column(Text, nullable=False)
    notes = Column(Text)
    
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    # Relationships
    concept = relationship("Concept", back_populates="mappings")


class LogicNodeTemplate(Base):
    __tablename__ = 'logicnode_templates'
    
    template_id = Column(Integer, primary_key=True, autoincrement=True)
    concept_id = Column(String(20), ForeignKey('concepts.concept_id', ondelete='CASCADE'))
    
    inputs = Column(JSONB, nullable=False)
    outputs = Column(JSONB, nullable=False)
    preconditions = Column(JSONB, default=[])
    postconditions = Column(JSONB, default=[])
    side_effects = Column(JSONB, default=[])
    
    type_constraints = Column(JSONB, default={})
    
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    concept = relationship("Concept", back_populates="templates")


class Documentation(Base):
    __tablename__ = 'documentation'
    
    doc_id = Column(Integer, primary_key=True, autoincrement=True)
    concept_id = Column(String(20), ForeignKey('concepts.concept_id', ondelete='CASCADE'))
    
    description = Column(Text, nullable=False)
    examples = Column(JSONB, default=[])
    best_practices = Column(Text)
    common_pitfalls = Column(Text)
    
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    concept = relationship("Concept", back_populates="documentation")
```

---

## 3. DATABASE 2: STATE GRAPH

**Purpose:** Track agent states, tasks, workflows, and execution context

### 3.1 Schema Definition

```sql
-- Database: state_graph
-- Schema version: 1.0

-- ============================================================================
-- TABLE: agents
-- Current state of all 35 agents
-- ============================================================================
CREATE TABLE agents (
    agent_id VARCHAR(30) PRIMARY KEY,  -- e.g., 'AGENT-PY-001'
    name VARCHAR(100) NOT NULL,
    tier VARCHAR(20) NOT NULL,  -- executive, support, pod
    pod VARCHAR(10),  -- A, B, C, D (null for non-pod agents)
    
    status VARCHAR(20) DEFAULT 'idle',  -- idle, busy, error, offline
    current_task_id VARCHAR(50),
    
    heartbeat_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_pod ON agents(pod);

-- ============================================================================
-- TABLE: tasks
-- All tasks assigned to agents
-- ============================================================================
CREATE TABLE tasks (
    task_id VARCHAR(50) PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,  -- extract, audit, synthesize, etc.
    
    assigned_to VARCHAR(30) REFERENCES agents(agent_id),
    assigned_by VARCHAR(30) REFERENCES agents(agent_id),
    
    priority INTEGER DEFAULT 3,  -- 1 (highest) to 5 (lowest)
    status VARCHAR(20) DEFAULT 'pending',  -- pending, in_progress, completed, failed
    
    -- Task details
    input_data JSONB NOT NULL,
    output_data JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    deadline TIMESTAMP,
    
    -- Error tracking
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3
);

CREATE INDEX idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);

-- ============================================================================
-- TABLE: workflows
-- Multi-agent workflow orchestration
-- ============================================================================
CREATE TABLE workflows (
    workflow_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    
    status VARCHAR(20) DEFAULT 'running',  -- running, completed, failed, paused
    
    -- Workflow structure (LangGraph state machine)
    graph_definition JSONB NOT NULL,
    current_state JSONB NOT NULL,
    
    -- Metadata
    initiated_by VARCHAR(30) REFERENCES agents(agent_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_workflows_status ON workflows(status);

-- ============================================================================
-- TABLE: workflow_steps
-- Individual steps within workflows
-- ============================================================================
CREATE TABLE workflow_steps (
    step_id SERIAL PRIMARY KEY,
    workflow_id VARCHAR(50) REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    
    step_name VARCHAR(100) NOT NULL,
    step_order INTEGER NOT NULL,
    
    assigned_to VARCHAR(30) REFERENCES agents(agent_id),
    status VARCHAR(20) DEFAULT 'pending',
    
    input_data JSONB,
    output_data JSONB,
    
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_workflow_steps_workflow ON workflow_steps(workflow_id);
CREATE INDEX idx_workflow_steps_status ON workflow_steps(status);

-- ============================================================================
-- TABLE: agent_context
-- Agent working memory and context
-- ============================================================================
CREATE TABLE agent_context (
    context_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(30) REFERENCES agents(agent_id) ON DELETE CASCADE,
    
    context_type VARCHAR(50) NOT NULL,  -- task_context, session_state, etc.
    context_data JSONB NOT NULL,
    
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE INDEX idx_context_agent ON agent_context(agent_id);
CREATE INDEX idx_context_expires ON agent_context(expires_at);

-- ============================================================================
-- TABLE: message_log
-- Log of all inter-agent messages (Protocol traffic)
-- ============================================================================
CREATE TABLE message_log (
    log_id SERIAL PRIMARY KEY,
    message_id VARCHAR(50) NOT NULL,
    
    protocol VARCHAR(10) NOT NULL,  -- alpha, beta, delta, sigma, omega, rho
    sender VARCHAR(30) NOT NULL,
    recipient VARCHAR(30),
    
    payload JSONB NOT NULL,
    
    sent_at TIMESTAMP DEFAULT NOW(),
    delivered_at TIMESTAMP,
    acknowledged_at TIMESTAMP
);

CREATE INDEX idx_message_log_sender ON message_log(sender);
CREATE INDEX idx_message_log_recipient ON message_log(recipient);
CREATE INDEX idx_message_log_protocol ON message_log(protocol);
CREATE INDEX idx_message_log_sent ON message_log(sent_at DESC);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: Active tasks by agent
CREATE VIEW v_active_tasks AS
SELECT 
    a.agent_id,
    a.name AS agent_name,
    a.status AS agent_status,
    t.task_id,
    t.task_type,
    t.priority,
    t.status AS task_status,
    t.created_at,
    t.deadline
FROM agents a
LEFT JOIN tasks t ON a.agent_id = t.assigned_to
WHERE t.status IN ('pending', 'in_progress')
ORDER BY t.priority, t.created_at;

-- View: Workflow progress
CREATE VIEW v_workflow_progress AS
SELECT 
    w.workflow_id,
    w.name,
    w.status,
    COUNT(ws.step_id) AS total_steps,
    COUNT(CASE WHEN ws.status = 'completed' THEN 1 END) AS completed_steps,
    COUNT(CASE WHEN ws.status = 'failed' THEN 1 END) AS failed_steps
FROM workflows w
LEFT JOIN workflow_steps ws ON w.workflow_id = ws.workflow_id
GROUP BY w.workflow_id, w.name, w.status;

-- ============================================================================
-- SEED DATA: Initialize 35 agents
-- ============================================================================

-- Executive Tier
INSERT INTO agents (agent_id, name, tier, pod) VALUES
('ARCH-001', 'Chief Architect & Program Manager', 'executive', NULL),
('MANAGER-POD-A-001', 'Pod A Manager', 'executive', 'A'),
('MANAGER-POD-B-001', 'Pod B Manager', 'executive', 'B'),
('MANAGER-POD-C-001', 'Pod C Manager', 'executive', 'C'),
('MANAGER-POD-D-001', 'Pod D Manager', 'executive', 'D');

-- Pod A Specialists
INSERT INTO agents (agent_id, name, tier, pod) VALUES
('AGENT-PY-001', 'Python Specialist', 'pod', 'A'),
('AGENT-JS-001', 'JavaScript Specialist', 'pod', 'A'),
('AGENT-RUBY-001', 'Ruby Specialist', 'pod', 'A'),
('AGENT-PHP-001', 'PHP Specialist', 'pod', 'A');

-- Pod B Specialists
INSERT INTO agents (agent_id, name, tier, pod) VALUES
('AGENT-C-001', 'C Specialist', 'pod', 'B'),
('AGENT-CPP-001', 'C++ Specialist', 'pod', 'B'),
('AGENT-RUST-001', 'Rust Specialist', 'pod', 'B'),
('AGENT-ZIG-001', 'Zig Specialist', 'pod', 'B');

-- (Continue for Pod C, Pod D, Support Ring, Audit agents...)
```

---

## 4. DATABASE 3: LOGICNODE REGISTRY

**Purpose:** Store all extracted LogicNodes with semantic metadata

### 4.1 Schema Definition

```sql
-- Database: logicnode_registry
-- Schema version: 1.0

-- ============================================================================
-- TABLE: logicnodes
-- All extracted computational abstractions
-- ============================================================================
CREATE TABLE logicnodes (
    logicnode_id VARCHAR(50) PRIMARY KEY,
    
    -- Source information
    source_file VARCHAR(500),
    source_language VARCHAR(20) NOT NULL,
    source_line_start INTEGER,
    source_line_end INTEGER,
    
    -- Semantic classification
    domain VARCHAR(50) NOT NULL,
    concept VARCHAR(100) NOT NULL,
    intent TEXT NOT NULL,
    
    -- LogicNode structure (Refined-IR)
    inputs JSONB NOT NULL,
    outputs JSONB NOT NULL,
    preconditions JSONB DEFAULT '[]'::jsonb,
    postconditions JSONB DEFAULT '[]'::jsonb,
    side_effects JSONB DEFAULT '[]'::jsonb,
    
    -- Metadata
    is_pure BOOLEAN DEFAULT true,
    complexity_score FLOAT,
    
    -- Provenance
    extracted_by VARCHAR(30) NOT NULL,  -- Agent ID
    verified_by VARCHAR(30),  -- Audit Agent ID
    verification_status VARCHAR(20) DEFAULT 'unverified',  -- unverified, verified, failed
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_logicnodes_language ON logicnodes(source_language);
CREATE INDEX idx_logicnodes_domain ON logicnodes(domain);
CREATE INDEX idx_logicnodes_concept ON logicnodes(concept);
CREATE INDEX idx_logicnodes_extracted_by ON logicnodes(extracted_by);
CREATE INDEX idx_logicnodes_verified ON logicnodes(verification_status);

-- ============================================================================
-- TABLE: logicnode_dependencies
-- Graph of dependencies between LogicNodes
-- ============================================================================
CREATE TABLE logicnode_dependencies (
    dependency_id SERIAL PRIMARY KEY,
    
    from_logicnode VARCHAR(50) REFERENCES logicnodes(logicnode_id) ON DELETE CASCADE,
    to_logicnode VARCHAR(50) REFERENCES logicnodes(logicnode_id) ON DELETE CASCADE,
    
    dependency_type VARCHAR(20) NOT NULL,  -- data_flow, control_flow, composition
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_dependency UNIQUE (from_logicnode, to_logicnode, dependency_type)
);

CREATE INDEX idx_dependencies_from ON logicnode_dependencies(from_logicnode);
CREATE INDEX idx_dependencies_to ON logicnode_dependencies(to_logicnode);

-- ============================================================================
-- TABLE: logicnode_batches
-- Group LogicNodes from same extraction job
-- ============================================================================
CREATE TABLE logicnode_batches (
    batch_id VARCHAR(50) PRIMARY KEY,
    
    source_repo VARCHAR(500),
    source_branch VARCHAR(100),
    
    total_logicnodes INTEGER DEFAULT 0,
    verified_logicnodes INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE logicnode_batch_members (
    batch_id VARCHAR(50) REFERENCES logicnode_batches(batch_id) ON DELETE CASCADE,
    logicnode_id VARCHAR(50) REFERENCES logicnodes(logicnode_id) ON DELETE CASCADE,
    
    PRIMARY KEY (batch_id, logicnode_id)
);

-- ============================================================================
-- TABLE: synthesis_outputs
-- Final synthesized outputs from multiple LogicNodes
-- ============================================================================
CREATE TABLE synthesis_outputs (
    synthesis_id VARCHAR(50) PRIMARY KEY,
    
    target_language VARCHAR(20) NOT NULL,
    output_type VARCHAR(50) NOT NULL,  -- function, class, module, binary
    
    synthesized_code TEXT NOT NULL,
    
    source_logicnodes JSONB NOT NULL,  -- Array of LogicNode IDs
    
    synthesized_by VARCHAR(30) NOT NULL,  -- Agent ID
    optimization_level INTEGER DEFAULT 2,  -- 0-3
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_synthesis_language ON synthesis_outputs(target_language);
CREATE INDEX idx_synthesis_by ON synthesis_outputs(synthesized_by);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: LogicNode statistics by language
CREATE VIEW v_logicnode_stats AS
SELECT 
    source_language,
    COUNT(*) AS total_nodes,
    COUNT(CASE WHEN verification_status = 'verified' THEN 1 END) AS verified_nodes,
    AVG(complexity_score) AS avg_complexity
FROM logicnodes
GROUP BY source_language;

-- View: Dependency graph
CREATE VIEW v_dependency_graph AS
SELECT 
    d.from_logicnode,
    ln1.concept AS from_concept,
    d.to_logicnode,
    ln2.concept AS to_concept,
    d.dependency_type
FROM logicnode_dependencies d
JOIN logicnodes ln1 ON d.from_logicnode = ln1.logicnode_id
JOIN logicnodes ln2 ON d.to_logicnode = ln2.logicnode_id;
```

---

## 5. DATABASE 4: TRACEABILITY LEDGER

**Purpose:** Immutable audit trail for all system operations

### 5.1 Schema Definition

```sql
-- Database: traceability_ledger
-- Schema version: 1.0

-- ============================================================================
-- TABLE: audit_log
-- Immutable audit trail (append-only)
-- ============================================================================
CREATE TABLE audit_log (
    log_id BIGSERIAL PRIMARY KEY,
    
    event_type VARCHAR(50) NOT NULL,  -- extraction, verification, synthesis, etc.
    actor_id VARCHAR(30) NOT NULL,  -- Agent ID
    
    target_type VARCHAR(50),  -- logicnode, task, workflow, etc.
    target_id VARCHAR(50),
    
    action VARCHAR(50) NOT NULL,  -- created, updated, deleted, verified, etc.
    
    details JSONB,
    
    -- Immutability
    created_at TIMESTAMP DEFAULT NOW(),
    hash VARCHAR(64) NOT NULL  -- SHA-256 hash of (log_id, event_type, actor_id, created_at)
);

CREATE INDEX idx_audit_event_type ON audit_log(event_type);
CREATE INDEX idx_audit_actor ON audit_log(actor_id);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);

-- Prevent updates/deletes (append-only)
CREATE RULE no_update_audit_log AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE RULE no_delete_audit_log AS ON DELETE TO audit_log DO INSTEAD NOTHING;

-- ============================================================================
-- TABLE: provenance
-- Track provenance of LogicNodes and artifacts
-- ============================================================================
CREATE TABLE provenance (
    provenance_id SERIAL PRIMARY KEY,
    
    entity_type VARCHAR(50) NOT NULL,  -- logicnode, synthesis, artifact
    entity_id VARCHAR(50) NOT NULL,
    
    source_files JSONB,  -- Array of source file paths
    transformations JSONB,  -- Array of transformation steps
    
    created_by VARCHAR(30) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_provenance UNIQUE (entity_type, entity_id)
);

CREATE INDEX idx_provenance_entity ON provenance(entity_type, entity_id);

-- ============================================================================
-- TABLE: verification_results
-- Results from audit agents
-- ============================================================================
CREATE TABLE verification_results (
    verification_id SERIAL PRIMARY KEY,
    
    logicnode_id VARCHAR(50) NOT NULL,
    auditor_id VARCHAR(30) NOT NULL,
    
    audit_type VARCHAR(20) NOT NULL,  -- security, performance, correctness
    
    status VARCHAR(20) NOT NULL,  -- verified, failed, warning
    score FLOAT,  -- 0.0 to 1.0
    
    issues JSONB DEFAULT '[]'::jsonb,
    recommendations JSONB DEFAULT '[]'::jsonb,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_verification_logicnode ON verification_results(logicnode_id);
CREATE INDEX idx_verification_auditor ON verification_results(auditor_id);
CREATE INDEX idx_verification_status ON verification_results(status);
```

---

## 6. DATABASE 5: MODEL STORE

**Purpose:** Store ML models, embeddings, and training data

### 6.1 Schema Definition

```sql
-- Database: model_store
-- Schema version: 1.0

-- ============================================================================
-- TABLE: embeddings
-- Vector embeddings for semantic search
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE embeddings (
    embedding_id SERIAL PRIMARY KEY,
    
    entity_type VARCHAR(50) NOT NULL,  -- concept, logicnode, documentation
    entity_id VARCHAR(50) NOT NULL,
    
    embedding vector(1536),  -- OpenAI ada-002 dimension
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_embedding UNIQUE (entity_type, entity_id)
);

CREATE INDEX idx_embeddings_entity ON embeddings(entity_type, entity_id);
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops);

-- ============================================================================
-- TABLE: ml_models
-- Metadata for stored ML models
-- ============================================================================
CREATE TABLE ml_models (
    model_id VARCHAR(50) PRIMARY KEY,
    
    model_type VARCHAR(50) NOT NULL,  -- classifier, ranker, generator
    purpose VARCHAR(100) NOT NULL,
    
    architecture VARCHAR(50),
    hyperparameters JSONB,
    
    -- Performance metrics
    accuracy FLOAT,
    precision_score FLOAT,
    recall FLOAT,
    f1_score FLOAT,
    
    -- Storage
    file_path VARCHAR(500),  -- Path to serialized model file
    file_size_mb FLOAT,
    
    trained_by VARCHAR(30),
    trained_at TIMESTAMP,
    version VARCHAR(20)
);

CREATE INDEX idx_models_type ON ml_models(model_type);

-- ============================================================================
-- TABLE: training_data
-- Training datasets for models
-- ============================================================================
CREATE TABLE training_data (
    dataset_id VARCHAR(50) PRIMARY KEY,
    
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    data_format VARCHAR(20),  -- json, csv, parquet
    file_path VARCHAR(500),
    file_size_mb FLOAT,
    
    num_samples INTEGER,
    num_features INTEGER,
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 7. CONNECTION POOLING

### 7.1 SQLAlchemy Connection Pool Configuration

**File:** `database/connection.py`

```python
"""
Database connection management with pooling
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
import os

# Database URLs
DATABASE_URLS = {
    'knowledge': f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('DB_KNOWLEDGE')}",
    'state': f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('DB_STATE')}",
    'logicnode': f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('DB_LOGICNODE')}",
    'traceability': f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('DB_TRACEABILITY')}",
    'model': f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('DB_MODEL')}"
}

# Engine configuration
ENGINE_CONFIG = {
    'poolclass': QueuePool,
    'pool_size': int(os.getenv('DB_POOL_SIZE', 20)),
    'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', 10)),
    'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', 30)),
    'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', 3600)),
    'pool_pre_ping': True,  # Verify connections before use
    'echo': False  # Set to True for SQL logging
}

# Create engines for each database
engines = {
    name: create_engine(url, **ENGINE_CONFIG)
    for name, url in DATABASE_URLS.items()
}

# Session factories
SessionMakers = {
    name: scoped_session(sessionmaker(bind=engine))
    for name, engine in engines.items()
}


# Dependency injection helpers
def get_knowledge_session():
    """Get Knowledge Lake database session"""
    session = SessionMakers['knowledge']()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_state_session():
    """Get State Graph database session"""
    session = SessionMakers['state']()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# (Similar for logicnode, traceability, model sessions...)
```

---

## 8. MIGRATION MANAGEMENT

### 8.1 Alembic Setup

**File:** `alembic.ini`

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
version_path_separator = os

sqlalchemy.url = postgresql://%(POSTGRES_USER)s:%(POSTGRES_PASSWORD)s@%(POSTGRES_HOST)s:%(POSTGRES_PORT)s/%(DB_KNOWLEDGE)s

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### 8.2 Migration Scripts

**Generate migration:**

```bash
# Create new migration
alembic revision -m "Add logicnode complexity score"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

**Example migration:**

```python
"""Add complexity score to logicnodes

Revision ID: abc123
Revises: xyz789
Create Date: 2026-02-05

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('logicnodes', 
        sa.Column('complexity_score', sa.Float(), nullable=True))

def downgrade():
    op.drop_column('logicnodes', 'complexity_score')
```

---

## 9. BACKUP & RECOVERY

### 9.1 Automated Backup Script

**File:** `scripts/backup_databases.sh`

```bash
#!/bin/bash

BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup all 5 databases
for db in knowledge_lake state_graph logicnode_registry traceability_ledger model_store; do
    echo "Backing up $db..."
    
    docker exec hgr-postgres pg_dump -U hgr_admin -Fc $db > \
        "$BACKUP_DIR/${db}_$TIMESTAMP.dump"
    
    # Compress
    gzip "$BACKUP_DIR/${db}_$TIMESTAMP.dump"
    
    echo "✓ $db backed up"
done

# Clean up old backups (keep last 7 days)
find "$BACKUP_DIR" -name "*.dump.gz" -mtime +7 -delete

echo "✓ All databases backed up successfully"
```

### 9.2 Restore Script

```bash
#!/bin/bash

BACKUP_FILE=$1
DATABASE=$2

if [ -z "$BACKUP_FILE" ] || [ -z "$DATABASE" ]; then
    echo "Usage: ./restore_database.sh <backup_file> <database_name>"
    exit 1
fi

# Uncompress if needed
if [[ $BACKUP_FILE == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" > /tmp/restore.dump
    BACKUP_FILE=/tmp/restore.dump
fi

# Restore
docker exec -i hgr-postgres pg_restore -U hgr_admin -d $DATABASE -c < "$BACKUP_FILE"

echo "✓ Database $DATABASE restored from $BACKUP_FILE"
```

---

## 10. PERFORMANCE OPTIMIZATION

### 10.1 Query Performance

**Index Usage Monitoring:**

```sql
-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan AS index_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan ASC;

-- Find unused indexes
SELECT 
    schemaname,
    tablename,
    indexname
FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND schemaname = 'public';
```

### 10.2 VACUUM and ANALYZE

```bash
# Cron job for regular maintenance
0 2 * * * docker exec hgr-postgres vacuumdb -U hgr_admin -a -z --analyze-in-stages
```

---

## DOCUMENT METADATA

**Document ID:** 21  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Owner:** Chief Architect  
**Dependencies:** Document 20 (Semantic Bus Implementation)  
**Next Document:** 22 (API Layer Design)

---

*End of Database Setup & Schemas*
