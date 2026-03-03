# DOCUMENT 31: AGENT COMMUNICATION PATTERNS
## Holy Grail Refinery - Development Specifications

**Document ID:** 31  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document specifies the complete communication patterns, message flows, and interaction protocols for the 35-agent Holy Grail Refinery system. It provides concrete implementation patterns for all 6 named protocols (Alpha, Beta, Delta, Sigma, Omega, Rho) with real message examples, error handling strategies, and coordination mechanisms.

**Key Communication Patterns:**
- **Protocol Alpha:** PM ↔ CEO mission planning and delivery
- **Protocol Beta:** CEO ↔ Pod Specialists task distribution
- **Protocol Delta:** Pod Specialists ↔ Audit Agents verification
- **Protocol Sigma:** Audit Agents ↔ Knowledge Lake queries
- **Protocol Omega:** CEO ↔ Support Ring infrastructure coordination
- **Protocol Rho:** Mission Control UI ↔ PM Agent user interaction

**Communication Infrastructure:**
- **Redis Semantic Bus:** Pub/Sub message routing
- **Message Schemas:** Standardized JSON formats
- **Retry Logic:** Exponential backoff with circuit breakers
- **Monitoring:** Message tracing and latency tracking

---

## TABLE OF CONTENTS

1. [Communication Architecture](#1-communication-architecture)
2. [Protocol Alpha: PM ↔ CEO](#2-protocol-alpha-pm--ceo)
3. [Protocol Beta: CEO ↔ Specialists](#3-protocol-beta-ceo--specialists)
4. [Protocol Delta: Specialists ↔ Audit](#4-protocol-delta-specialists--audit)
5. [Protocol Sigma: Agents ↔ Knowledge](#5-protocol-sigma-agents--knowledge)
6. [Protocol Omega: CEO ↔ Support](#6-protocol-omega-ceo--support)
7. [Protocol Rho: UI ↔ PM](#7-protocol-rho-ui--pm)
8. [Message Schema Catalog](#8-message-schema-catalog)
9. [Error Handling & Recovery](#9-error-handling--recovery)
10. [Performance Optimization](#10-performance-optimization)

---

## 1. COMMUNICATION ARCHITECTURE

### 1.1 Redis Semantic Bus Topology

```
                        REDIS SEMANTIC BUS
                    (Central Message Backbone)
                              │
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
   ┌───▼────┐           ┌─────▼─────┐         ┌─────▼─────┐
   │ User   │           │   CEO     │         │ Support   │
   │ Tier   │           │   Tier    │         │   Ring    │
   └───┬────┘           └─────┬─────┘         └─────┬─────┘
       │                      │                      │
   Protocol Rho          Protocol Beta          Protocol Omega
       │                      │                      │
   ┌───▼────┐           ┌─────▼─────┐         ┌─────▼─────┐
   │   PM   │───Alpha──▶│    CEO    │◀─Delta──│   Audit   │
   │ Agent  │           │   Agent   │         │  Agents   │
   └────────┘           └─────┬─────┘         └─────┬─────┘
                              │                      │
                        Protocol Beta            Protocol Sigma
                              │                      │
                        ┌─────▼─────┐         ┌─────▼─────┐
                        │   Pod     │         │ Knowledge │
                        │Specialists│         │   Lake    │
                        └───────────┘         └───────────┘
```

### 1.2 Channel Structure

**Redis Channel Naming Convention:**

```
hgr:{protocol}:{source_agent}:{target_agent}:{message_type}

Examples:
- hgr:alpha:PM-001:CEO-001:mission_request
- hgr:beta:CEO-001:AGENT-PY-001:extraction_task
- hgr:delta:AGENT-PY-001:AUDIT-LEAD-001:verification_request
```

### 1.3 Message Envelope Standard

**All messages follow this envelope structure:**

```json
{
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "protocol": "alpha",
  "timestamp": "2026-02-05T14:30:00.000Z",
  "source_agent": "PM-001",
  "target_agent": "CEO-001",
  "message_type": "mission_request",
  "correlation_id": "mission-abc123",
  "priority": "high",
  "ttl_seconds": 300,
  "retry_count": 0,
  "payload": {
    /* Protocol-specific data */
  },
  "metadata": {
    "trace_id": "trace-xyz789",
    "user_id": "user-456",
    "session_id": "session-def012"
  }
}
```

---

## 2. PROTOCOL ALPHA: PM ↔ CEO

**Purpose:** Mission planning, status updates, and delivery coordination

### 2.1 Message Flow

```
USER → PM Agent → CEO Agent → Pod Managers → Specialists → Audit
                                                              │
CEO Agent ← Pod Managers ← Specialists ← Audit ← ─ ─ ─ ─ ─ ─┘
     │
     ▼
PM Agent → USER
```

### 2.2 Alpha-001: Mission Request

**Direction:** PM Agent → CEO Agent

```json
{
  "message_id": "msg-001",
  "protocol": "alpha",
  "timestamp": "2026-02-05T14:30:00.000Z",
  "source_agent": "PM-001",
  "target_agent": "CEO-001",
  "message_type": "mission_request",
  "correlation_id": "mission-m001",
  "priority": "high",
  "payload": {
    "mission_id": "mission-m001",
    "mission_type": "code_refinement",
    "user_request": "Build a REST API for user management in Python",
    "requirements": {
      "languages": ["python"],
      "frameworks": ["fastapi", "sqlalchemy"],
      "features": [
        "User CRUD operations",
        "JWT authentication",
        "PostgreSQL database",
        "Docker containerization"
      ],
      "constraints": {
        "performance": "< 100ms response time",
        "security": "OWASP Top 10 compliance",
        "scalability": "Handle 1000 concurrent users"
      }
    },
    "deliverables": [
      "LogicNode extraction for all components",
      "Unified binary compilation",
      "Documentation",
      "Test suite"
    ],
    "deadline": "2026-02-10T00:00:00.000Z",
    "budget": {
      "tokens": 5000000,
      "time_hours": 24
    }
  }
}
```

**Response:** Alpha-002: Mission Acknowledgment

```json
{
  "message_id": "msg-002",
  "protocol": "alpha",
  "timestamp": "2026-02-05T14:30:05.000Z",
  "source_agent": "CEO-001",
  "target_agent": "PM-001",
  "message_type": "mission_acknowledgment",
  "correlation_id": "mission-m001",
  "in_reply_to": "msg-001",
  "payload": {
    "mission_id": "mission-m001",
    "status": "accepted",
    "estimated_completion": "2026-02-09T18:00:00.000Z",
    "execution_plan": {
      "phases": [
        {
          "phase": "knowledge_acquisition",
          "duration_minutes": 30,
          "agents": ["IS-001"]
        },
        {
          "phase": "logicnode_extraction",
          "duration_minutes": 180,
          "agents": ["AGENT-PY-001"]
        },
        {
          "phase": "verification",
          "duration_minutes": 120,
          "agents": ["AUDIT-LEAD-001", "AUDIT-CORRECTNESS-001"]
        },
        {
          "phase": "fusion_compilation",
          "duration_minutes": 60,
          "agents": ["CEO-001"]
        },
        {
          "phase": "delivery",
          "duration_minutes": 30,
          "agents": ["PM-001"]
        }
      ],
      "total_estimated_minutes": 420,
      "risk_factors": [
        "Complex authentication requirements may extend verification phase",
        "Docker optimization may require additional testing"
      ]
    },
    "resource_allocation": {
      "tokens_allocated": 4800000,
      "agents_assigned": 8,
      "databases_required": ["knowledge_lake", "logicnode_registry"]
    }
  }
}
```

### 2.3 Alpha-003: Status Update

**Direction:** CEO Agent → PM Agent

```json
{
  "message_id": "msg-003",
  "protocol": "alpha",
  "timestamp": "2026-02-05T15:45:00.000Z",
  "source_agent": "CEO-001",
  "target_agent": "PM-001",
  "message_type": "status_update",
  "correlation_id": "mission-m001",
  "payload": {
    "mission_id": "mission-m001",
    "current_phase": "logicnode_extraction",
    "progress_percentage": 35.0,
    "completed_tasks": [
      {
        "task_id": "task-001",
        "description": "Knowledge Lake indexing of FastAPI docs",
        "completed_at": "2026-02-05T15:00:00.000Z",
        "agent": "IS-001"
      }
    ],
    "active_tasks": [
      {
        "task_id": "task-002",
        "description": "Extract LogicNodes from FastAPI route definitions",
        "agent": "AGENT-PY-001",
        "progress": 60,
        "estimated_completion": "2026-02-05T16:30:00.000Z"
      }
    ],
    "pending_tasks": [
      {
        "task_id": "task-003",
        "description": "Extract LogicNodes from authentication middleware",
        "agent": "AGENT-PY-001",
        "estimated_start": "2026-02-05T16:30:00.000Z"
      }
    ],
    "issues": [],
    "next_milestone": "Complete LogicNode extraction phase"
  }
}
```

### 2.4 Alpha-004: Delivery Notification

**Direction:** CEO Agent → PM Agent

```json
{
  "message_id": "msg-004",
  "protocol": "alpha",
  "timestamp": "2026-02-09T17:30:00.000Z",
  "source_agent": "CEO-001",
  "target_agent": "PM-001",
  "message_type": "delivery_notification",
  "correlation_id": "mission-m001",
  "payload": {
    "mission_id": "mission-m001",
    "status": "completed",
    "completed_at": "2026-02-09T17:30:00.000Z",
    "deliverables": [
      {
        "type": "logicnode_cluster",
        "cluster_id": "cluster-c001",
        "logicnode_count": 47,
        "languages_covered": ["python"],
        "verification_status": "verified",
        "download_url": "s3://hgr-outputs/mission-m001/cluster-c001.json"
      },
      {
        "type": "unified_binary",
        "binary_path": "/outputs/user_management_api",
        "size_bytes": 15728640,
        "checksum": "sha256:abc123...",
        "download_url": "s3://hgr-outputs/mission-m001/api_binary"
      },
      {
        "type": "documentation",
        "format": "markdown",
        "files": [
          "README.md",
          "API_REFERENCE.md",
          "DEPLOYMENT.md"
        ],
        "download_url": "s3://hgr-outputs/mission-m001/docs/"
      },
      {
        "type": "test_suite",
        "test_count": 156,
        "coverage_percentage": 98.5,
        "download_url": "s3://hgr-outputs/mission-m001/tests/"
      }
    ],
    "execution_summary": {
      "total_duration_minutes": 405,
      "tokens_consumed": 4650000,
      "agents_involved": 8,
      "logicnodes_extracted": 47,
      "equivalence_tests_passed": 46953,
      "equivalence_tests_total": 47000,
      "pass_rate": 0.999
    },
    "quality_metrics": {
      "code_quality_score": 9.2,
      "performance_score": 9.5,
      "security_score": 9.8,
      "documentation_score": 9.0
    }
  }
}
```

---

## 3. PROTOCOL BETA: CEO ↔ SPECIALISTS

**Purpose:** Task distribution and LogicNode collection

### 3.1 Beta-001: Extraction Task Assignment

**Direction:** CEO Agent → Language Specialist

```json
{
  "message_id": "msg-beta-001",
  "protocol": "beta",
  "timestamp": "2026-02-05T15:00:00.000Z",
  "source_agent": "CEO-001",
  "target_agent": "AGENT-PY-001",
  "message_type": "extraction_task",
  "correlation_id": "mission-m001",
  "priority": "high",
  "payload": {
    "task_id": "task-002",
    "mission_id": "mission-m001",
    "task_type": "logicnode_extraction",
    "source_files": [
      {
        "file_path": "/input/main.py",
        "language": "python",
        "size_bytes": 5120,
        "checksum": "md5:def456..."
      },
      {
        "file_path": "/input/auth.py",
        "language": "python",
        "size_bytes": 3072,
        "checksum": "md5:ghi789..."
      }
    ],
    "extraction_scope": {
      "paradigm": "dynamic",
      "domains": [
        "http_operations",
        "authentication",
        "database_operations"
      ],
      "concepts": [
        "route_handler",
        "jwt_token_generation",
        "database_query"
      ]
    },
    "requirements": {
      "confidence_threshold": 0.99,
      "include_source_mapping": true,
      "extract_dependencies": true
    },
    "context": {
      "library_versions": {
        "fastapi": "0.104.1",
        "sqlalchemy": "2.0.23",
        "pyjwt": "2.8.0"
      },
      "knowledge_lake_query": "FastAPI route patterns and JWT authentication"
    },
    "deadline": "2026-02-05T17:00:00.000Z"
  }
}
```

**Response:** Beta-002: Extraction Results

```json
{
  "message_id": "msg-beta-002",
  "protocol": "beta",
  "timestamp": "2026-02-05T16:45:00.000Z",
  "source_agent": "AGENT-PY-001",
  "target_agent": "CEO-001",
  "message_type": "extraction_results",
  "correlation_id": "mission-m001",
  "in_reply_to": "msg-beta-001",
  "payload": {
    "task_id": "task-002",
    "status": "completed",
    "logicnodes_extracted": 12,
    "logicnodes": [
      {
        "logicnode_id": "ln-001",
        "paradigm": "dynamic",
        "domain": "http_operations",
        "concept": "route_handler_post",
        "intent": "Handle HTTP POST request to create user resource",
        "inputs": [
          {
            "name": "user_data",
            "type": "dict",
            "constraints": [
              {
                "type": "schema",
                "schema": {
                  "username": "str",
                  "email": "str",
                  "password": "str"
                }
              }
            ]
          }
        ],
        "outputs": [
          {
            "name": "response",
            "type": "dict",
            "constraints": [
              {
                "type": "schema",
                "schema": {
                  "user_id": "int",
                  "status": "str"
                }
              }
            ]
          }
        ],
        "preconditions": [
          {
            "type": "predicate",
            "expression": "user_data is not None"
          },
          {
            "type": "predicate",
            "expression": "valid_email(user_data['email'])"
          }
        ],
        "postconditions": [
          {
            "type": "predicate",
            "expression": "response['user_id'] > 0"
          },
          {
            "type": "predicate",
            "expression": "response['status'] == 'created'"
          }
        ],
        "side_effects": [
          {
            "type": "database_write",
            "target": "users_table",
            "operation": "INSERT"
          }
        ],
        "source_language": "python",
        "source_code": "@app.post('/users')\nasync def create_user(user: UserCreate):\n    ...",
        "source_file_path": "/input/main.py",
        "source_line_number": 42,
        "confidence": 0.995
      }
      /* ... 11 more LogicNodes */
    ],
    "extraction_metadata": {
      "total_lines_processed": 856,
      "concepts_identified": 12,
      "knowledge_lake_queries": 8,
      "processing_time_seconds": 105
    }
  }
}
```

### 3.2 Beta-003: Fusion Request

**Direction:** CEO Agent → Pod Sub-Manager

```json
{
  "message_id": "msg-beta-003",
  "protocol": "beta",
  "timestamp": "2026-02-09T16:00:00.000Z",
  "source_agent": "CEO-001",
  "target_agent": "MANAGER-POD-A-001",
  "message_type": "fusion_request",
  "correlation_id": "mission-m001",
  "payload": {
    "fusion_id": "fusion-f001",
    "mission_id": "mission-m001",
    "logicnode_ids": [
      "ln-001", "ln-002", "ln-003", "ln-004", "ln-005",
      "ln-006", "ln-007", "ln-008", "ln-009", "ln-010",
      "ln-011", "ln-012"
    ],
    "fusion_strategy": "semantic_clustering",
    "target_paradigm": "dynamic",
    "optimization_goals": [
      "minimize_redundancy",
      "maximize_cohesion",
      "preserve_semantics"
    ]
  }
}
```

**Response:** Beta-004: Group Standard

```json
{
  "message_id": "msg-beta-004",
  "protocol": "beta",
  "timestamp": "2026-02-09T16:30:00.000Z",
  "source_agent": "MANAGER-POD-A-001",
  "target_agent": "CEO-001",
  "message_type": "group_standard",
  "correlation_id": "mission-m001",
  "in_reply_to": "msg-beta-003",
  "payload": {
    "fusion_id": "fusion-f001",
    "group_standard_id": "gs-001",
    "paradigm": "dynamic",
    "clusters": [
      {
        "cluster_id": "cluster-c001",
        "canonical_concept": "http_crud_operations",
        "logicnode_ids": ["ln-001", "ln-002", "ln-003", "ln-004"],
        "cohesion_score": 0.98,
        "consensus_logicnode_id": "ln-consensus-001"
      },
      {
        "cluster_id": "cluster-c002",
        "canonical_concept": "authentication_flow",
        "logicnode_ids": ["ln-005", "ln-006", "ln-007"],
        "cohesion_score": 0.97,
        "consensus_logicnode_id": "ln-consensus-002"
      }
      /* ... more clusters */
    ],
    "fusion_metrics": {
      "redundancy_eliminated": 0.35,
      "semantic_preservation": 0.999,
      "cluster_count": 5
    }
  }
}
```

---

## 4. PROTOCOL DELTA: SPECIALISTS ↔ AUDIT

**Purpose:** LogicNode verification and quality assurance

### 4.1 Delta-001: Verification Request

**Direction:** Language Specialist → Audit Agent

```json
{
  "message_id": "msg-delta-001",
  "protocol": "delta",
  "timestamp": "2026-02-05T17:00:00.000Z",
  "source_agent": "AGENT-PY-001",
  "target_agent": "AUDIT-LEAD-001",
  "message_type": "verification_request",
  "correlation_id": "mission-m001",
  "payload": {
    "verification_id": "verify-v001",
    "logicnode_ids": ["ln-001", "ln-002", "ln-003"],
    "verification_type": "equivalence_testing",
    "requirements": {
      "test_count": 1000,
      "tolerance": 0.000001,
      "pass_threshold": 0.999999
    },
    "priority": "high"
  }
}
```

**Response:** Delta-002: Verification Assignment

```json
{
  "message_id": "msg-delta-002",
  "protocol": "delta",
  "timestamp": "2026-02-05T17:01:00.000Z",
  "source_agent": "AUDIT-LEAD-001",
  "target_agent": "AUDIT-CORRECTNESS-001",
  "message_type": "verification_assignment",
  "correlation_id": "mission-m001",
  "in_reply_to": "msg-delta-001",
  "payload": {
    "verification_id": "verify-v001",
    "assigned_logicnode_ids": ["ln-001", "ln-002", "ln-003"],
    "test_specifications": {
      "test_count_per_logicnode": 1000,
      "tolerance": 0.000001,
      "test_types": [
        "input_output_equivalence",
        "side_effect_verification",
        "precondition_validation",
        "postcondition_validation"
      ]
    },
    "deadline": "2026-02-05T19:00:00.000Z"
  }
}
```

### 4.2 Delta-003: Verification Results

**Direction:** Audit Agent → Language Specialist / CEO

```json
{
  "message_id": "msg-delta-003",
  "protocol": "delta",
  "timestamp": "2026-02-05T18:45:00.000Z",
  "source_agent": "AUDIT-CORRECTNESS-001",
  "target_agent": "AUDIT-LEAD-001",
  "message_type": "verification_results",
  "correlation_id": "mission-m001",
  "payload": {
    "verification_id": "verify-v001",
    "results": [
      {
        "logicnode_id": "ln-001",
        "status": "verified",
        "tests_passed": 1000,
        "tests_total": 1000,
        "pass_rate": 1.0,
        "tolerance_violations": 0,
        "execution_time_seconds": 45
      },
      {
        "logicnode_id": "ln-002",
        "status": "verified",
        "tests_passed": 999,
        "tests_total": 1000,
        "pass_rate": 0.999,
        "tolerance_violations": 1,
        "execution_time_seconds": 42
      },
      {
        "logicnode_id": "ln-003",
        "status": "rejected",
        "tests_passed": 985,
        "tests_total": 1000,
        "pass_rate": 0.985,
        "tolerance_violations": 15,
        "execution_time_seconds": 38,
        "failure_reasons": [
          "Postcondition violation in 15 test cases",
          "Side effect inconsistency detected"
        ]
      }
    ],
    "overall_summary": {
      "verified_count": 2,
      "rejected_count": 1,
      "total_tests_run": 3000,
      "average_pass_rate": 0.995
    }
  }
}
```

---

## 5. PROTOCOL SIGMA: AGENTS ↔ KNOWLEDGE

**Purpose:** Knowledge Lake queries and documentation retrieval

### 5.1 Sigma-001: Knowledge Query

**Direction:** Any Agent → IS Agent (Knowledge Lake)

```json
{
  "message_id": "msg-sigma-001",
  "protocol": "sigma",
  "timestamp": "2026-02-05T15:05:00.000Z",
  "source_agent": "AGENT-PY-001",
  "target_agent": "IS-001",
  "message_type": "knowledge_query",
  "correlation_id": "mission-m001",
  "payload": {
    "query_id": "query-q001",
    "query_text": "FastAPI route handler with dependency injection",
    "query_type": "hybrid",
    "filters": {
      "language": "python",
      "library": "fastapi",
      "doc_type": "tutorial"
    },
    "top_k": 10,
    "include_code_examples": true
  }
}
```

**Response:** Sigma-002: Knowledge Results

```json
{
  "message_id": "msg-sigma-002",
  "protocol": "sigma",
  "timestamp": "2026-02-05T15:05:02.000Z",
  "source_agent": "IS-001",
  "target_agent": "AGENT-PY-001",
  "message_type": "knowledge_results",
  "correlation_id": "mission-m001",
  "in_reply_to": "msg-sigma-001",
  "payload": {
    "query_id": "query-q001",
    "total_results": 10,
    "execution_time_ms": 87,
    "results": [
      {
        "doc_id": "doc-12345",
        "title": "FastAPI Dependency Injection",
        "url": "https://fastapi.tiangolo.com/tutorial/dependencies/",
        "chunk_text": "FastAPI has a very powerful but intuitive Dependency Injection system...",
        "score": 0.95,
        "source": "vector",
        "code_examples": [
          {
            "language": "python",
            "code": "from fastapi import Depends\n\nasync def get_query(skip: int = 0):\n    return skip"
          }
        ]
      }
      /* ... 9 more results */
    ]
  }
}
```

---

## 6. PROTOCOL OMEGA: CEO ↔ SUPPORT

**Purpose:** Infrastructure coordination and resource management

### 6.1 Omega-001: Infrastructure Request

**Direction:** CEO Agent → Support Agent

```json
{
  "message_id": "msg-omega-001",
  "protocol": "omega",
  "timestamp": "2026-02-05T14:32:00.000Z",
  "source_agent": "CEO-001",
  "target_agent": "SUPPORT-DEVOPS-001",
  "message_type": "infrastructure_request",
  "correlation_id": "mission-m001",
  "payload": {
    "request_id": "infra-r001",
    "request_type": "container_scaling",
    "details": {
      "agent_containers": [
        {
          "agent_id": "AGENT-PY-001",
          "replicas": 3,
          "memory_limit": "4GB",
          "cpu_limit": "2.0"
        }
      ],
      "database_connections": {
        "knowledge_lake": 10,
        "logicnode_registry": 5
      },
      "reason": "High load for Python extraction tasks"
    }
  }
}
```

**Response:** Omega-002: Infrastructure Status

```json
{
  "message_id": "msg-omega-002",
  "protocol": "omega",
  "timestamp": "2026-02-05T14:35:00.000Z",
  "source_agent": "SUPPORT-DEVOPS-001",
  "target_agent": "CEO-001",
  "message_type": "infrastructure_status",
  "correlation_id": "mission-m001",
  "in_reply_to": "msg-omega-001",
  "payload": {
    "request_id": "infra-r001",
    "status": "completed",
    "containers_scaled": [
      {
        "agent_id": "AGENT-PY-001",
        "previous_replicas": 1,
        "current_replicas": 3,
        "status": "running"
      }
    ],
    "resource_allocation": {
      "total_memory_allocated": "12GB",
      "total_cpu_allocated": "6.0",
      "estimated_cost_per_hour": "$0.50"
    }
  }
}
```

---

## 7. PROTOCOL RHO: UI ↔ PM

**Purpose:** User interaction and mission control interface

### 7.1 Rho-001: User Command

**Direction:** Mission Control UI → PM Agent

```json
{
  "message_id": "msg-rho-001",
  "protocol": "rho",
  "timestamp": "2026-02-05T14:30:00.000Z",
  "source_agent": "UI-001",
  "target_agent": "PM-001",
  "message_type": "user_command",
  "correlation_id": "user-session-12345",
  "payload": {
    "user_id": "user-456",
    "session_id": "session-def012",
    "command_type": "create_mission",
    "parameters": {
      "description": "Build a REST API for user management in Python",
      "languages": ["python"],
      "frameworks": ["fastapi"],
      "deadline": "2026-02-10T00:00:00.000Z"
    }
  }
}
```

**Response:** Rho-002: PM Response

```json
{
  "message_id": "msg-rho-002",
  "protocol": "rho",
  "timestamp": "2026-02-05T14:30:10.000Z",
  "source_agent": "PM-001",
  "target_agent": "UI-001",
  "message_type": "pm_response",
  "correlation_id": "user-session-12345",
  "in_reply_to": "msg-rho-001",
  "payload": {
    "response_type": "mission_created",
    "mission_id": "mission-m001",
    "message": "Mission created successfully. CEO Agent has accepted the mission.",
    "estimated_completion": "2026-02-09T18:00:00.000Z",
    "next_steps": [
      "CEO Agent is planning execution strategy",
      "Language specialists will be assigned shortly",
      "You will receive status updates every 30 minutes"
    ]
  }
}
```

---

## 8. MESSAGE SCHEMA CATALOG

### 8.1 Core Message Types by Protocol

| Protocol | Message Type | Direction | Purpose |
|----------|--------------|-----------|---------|
| **Alpha** | mission_request | PM → CEO | Initiate new mission |
| | mission_acknowledgment | CEO → PM | Confirm mission acceptance |
| | status_update | CEO → PM | Periodic progress updates |
| | delivery_notification | CEO → PM | Mission completion |
| **Beta** | extraction_task | CEO → Specialist | Assign extraction work |
| | extraction_results | Specialist → CEO | Submit LogicNodes |
| | fusion_request | CEO → Sub-Manager | Request pod-level fusion |
| | group_standard | Sub-Manager → CEO | Submit fused standard |
| **Delta** | verification_request | Specialist → Audit | Request verification |
| | verification_assignment | Audit Lead → Audit Agent | Assign testing |
| | verification_results | Audit → Specialist/CEO | Report test results |
| **Sigma** | knowledge_query | Any → IS Agent | Query Knowledge Lake |
| | knowledge_results | IS Agent → Any | Return search results |
| **Omega** | infrastructure_request | CEO → Support | Request resources |
| | infrastructure_status | Support → CEO | Confirm allocation |
| **Rho** | user_command | UI → PM | User interaction |
| | pm_response | PM → UI | PM response to user |

---

## 9. ERROR HANDLING & RECOVERY

### 9.1 Error Message Format

```json
{
  "message_id": "msg-error-001",
  "protocol": "alpha",
  "timestamp": "2026-02-05T15:30:00.000Z",
  "source_agent": "AGENT-PY-001",
  "target_agent": "CEO-001",
  "message_type": "error",
  "correlation_id": "mission-m001",
  "in_reply_to": "msg-beta-001",
  "payload": {
    "error_code": "EXTRACTION_FAILED",
    "error_message": "Unable to parse source file due to syntax error",
    "error_details": {
      "file_path": "/input/main.py",
      "line_number": 42,
      "syntax_error": "unexpected indentation"
    },
    "recovery_action": "manual_intervention_required",
    "suggested_resolution": "Fix syntax error in source file and retry"
  }
}
```

### 9.2 Retry Strategy

**Exponential Backoff with Jitter:**

```python
"""
Retry logic for message delivery
"""

import random
import asyncio
from typing import Callable

async def send_message_with_retry(
    send_func: Callable,
    message: dict,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
):
    """
    Send message with exponential backoff retry
    """
    for attempt in range(max_retries):
        try:
            result = await send_func(message)
            return result
        
        except Exception as e:
            if attempt == max_retries - 1:
                # Final attempt failed
                raise
            
            # Calculate exponential backoff with jitter
            delay = min(
                base_delay * (2 ** attempt) + random.uniform(0, 1),
                max_delay
            )
            
            print(f"Retry attempt {attempt + 1}/{max_retries} after {delay:.2f}s")
            await asyncio.sleep(delay)
```

### 9.3 Circuit Breaker Pattern

```python
"""
Circuit breaker for protecting downstream agents
"""

from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: Exception = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection
        """
        if self.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout):
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            
            # Success - reset if half-open
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            
            return result
        
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            
            raise
```

---

## 10. PERFORMANCE OPTIMIZATION

### 10.1 Message Batching

```python
"""
Batch multiple messages for efficient transmission
"""

import asyncio
from typing import List

class MessageBatcher:
    def __init__(
        self,
        max_batch_size: int = 100,
        max_wait_time: float = 0.1
    ):
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.pending_messages = []
        self.batch_task = None
    
    async def send(self, message: dict):
        """
        Add message to batch queue
        """
        self.pending_messages.append(message)
        
        if len(self.pending_messages) >= self.max_batch_size:
            await self._flush_batch()
        elif self.batch_task is None:
            self.batch_task = asyncio.create_task(self._flush_after_delay())
    
    async def _flush_batch(self):
        """
        Send batched messages
        """
        if not self.pending_messages:
            return
        
        batch = self.pending_messages.copy()
        self.pending_messages.clear()
        
        # Cancel delayed flush if active
        if self.batch_task:
            self.batch_task.cancel()
            self.batch_task = None
        
        # Send batch
        await self._send_batch(batch)
    
    async def _flush_after_delay(self):
        """
        Flush batch after max wait time
        """
        await asyncio.sleep(self.max_wait_time)
        await self._flush_batch()
    
    async def _send_batch(self, messages: List[dict]):
        """
        Actual batch send implementation
        """
        # Implementation depends on Redis/messaging backend
        pass
```

### 10.2 Message Compression

```python
"""
Compress large messages for efficient transmission
"""

import json
import zlib

def compress_message(message: dict, threshold_bytes: int = 1024) -> dict:
    """
    Compress message payload if above threshold
    """
    json_str = json.dumps(message)
    size = len(json_str.encode('utf-8'))
    
    if size > threshold_bytes:
        compressed = zlib.compress(json_str.encode('utf-8'))
        
        return {
            "compressed": True,
            "original_size": size,
            "data": compressed.hex()
        }
    
    return message

def decompress_message(message: dict) -> dict:
    """
    Decompress message if compressed
    """
    if message.get("compressed"):
        compressed_data = bytes.fromhex(message["data"])
        decompressed = zlib.decompress(compressed_data)
        return json.loads(decompressed.decode('utf-8'))
    
    return message
```

---

## DOCUMENT METADATA

**Document ID:** 31  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Owner:** Chief Architect  
**Dependencies:** Documents 7 (Communication Protocols), 20 (Semantic Bus)  
**Next Document:** 32 (Production Deployment Guide)

---

*End of Agent Communication Patterns*
