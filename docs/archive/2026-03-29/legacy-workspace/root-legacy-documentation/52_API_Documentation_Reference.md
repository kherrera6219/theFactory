# DOCUMENT 52: API DOCUMENTATION & REFERENCE

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Documentation & Training

**Document ID:** 52  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Documentation & Training  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive API documentation** for the Holy Grail Refinery system. It covers all REST API endpoints, WebSocket channels, authentication methods, request/response formats, and client integration patterns. This serves as the definitive reference for developers integrating with the Holy Grail Refinery platform.

**API Overview:**
- **Base URL:** `https://api.hgr.local/v1` (Production) or `http://localhost:8000/v1` (Development)
- **Protocol:** REST over HTTPS
- **Authentication:** JWT Bearer tokens with OAuth 2.0
- **Rate Limits:** 1000 requests/hour for standard users, 10,000 for enterprise
- **Versioning:** URI versioning (`/v1/`, `/v2/`)
- **Response Format:** JSON

**API Capabilities:**
- 🚀 **Mission Management** - Create, track, and retrieve mission results
- 🤖 **Agent Control** - Monitor and interact with 35 agents
- 📊 **LogicNode Registry** - Query and analyze extracted LogicNodes
- 🔍 **Knowledge Lake** - Search programming documentation
- 📈 **Analytics** - System metrics and performance data
- 🔔 **WebSocket Streaming** - Real-time updates and events

---

## TABLE OF CONTENTS

1. [Getting Started](#1-getting-started)
2. [Authentication](#2-authentication)
3. [Missions API](#3-missions-api)
4. [Agents API](#4-agents-api)
5. [LogicNodes API](#5-logicnodes-api)
6. [Knowledge Lake API](#6-knowledge-lake-api)
7. [Analytics API](#7-analytics-api)
8. [WebSocket API](#8-websocket-api)
9. [Error Handling](#9-error-handling)
10. [Client Libraries & SDKs](#10-client-libraries--sdks)

---

## 1. GETTING STARTED

### 1.1 API Access

**Prerequisites:**
1. Holy Grail Refinery account
2. API credentials (Client ID & Secret)
3. HTTPS client library

**Quick Start:**

```bash
# 1. Obtain access token
curl -X POST https://api.hgr.local/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "grant_type": "client_credentials"
  }'

# Response:
# {
#   "access_token": "eyJhbGciOiJSUzI1NiIs...",
#   "token_type": "Bearer",
#   "expires_in": 3600
# }

# 2. Make authenticated request
curl -X GET https://api.hgr.local/v1/missions \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

### 1.2 API Conventions

**HTTP Methods:**
- `GET` - Retrieve resources
- `POST` - Create new resources
- `PATCH` - Update existing resources (partial)
- `PUT` - Replace existing resources (full)
- `DELETE` - Remove resources

**Status Codes:**
- `200 OK` - Request succeeded
- `201 Created` - Resource created
- `204 No Content` - Success with no response body
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Missing or invalid authentication
- `403 Forbidden` - Authenticated but not authorized
- `404 Not Found` - Resource doesn't exist
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - System overloaded

**Pagination:**
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total_pages": 10,
    "total_items": 500
  },
  "links": {
    "first": "/v1/missions?page=1",
    "prev": null,
    "next": "/v1/missions?page=2",
    "last": "/v1/missions?page=10"
  }
}
```

---

## 2. AUTHENTICATION

### 2.1 OAuth 2.0 Client Credentials

**Endpoint:** `POST /v1/auth/token`

**Request:**
```json
{
  "client_id": "hgr_client_abc123",
  "client_secret": "secret_xyz789",
  "grant_type": "client_credentials",
  "scope": "missions:read missions:write agents:read"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "missions:read missions:write agents:read",
  "refresh_token": "refresh_abc123xyz789"
}
```

**Usage:**
```bash
curl -X GET https://api.hgr.local/v1/missions \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

### 2.2 Token Refresh

**Endpoint:** `POST /v1/auth/token/refresh`

**Request:**
```json
{
  "refresh_token": "refresh_abc123xyz789"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### 2.3 Scopes

| Scope | Description |
|-------|-------------|
| `missions:read` | Read mission data |
| `missions:write` | Create and update missions |
| `missions:delete` | Delete missions |
| `agents:read` | View agent status and logs |
| `agents:control` | Send commands to agents |
| `logicnodes:read` | Query LogicNode registry |
| `knowledge:read` | Search Knowledge Lake |
| `analytics:read` | Access system metrics |
| `admin:full` | Full administrative access |

---

## 3. MISSIONS API

Missions represent end-to-end workflows from user requirements to deliverables.

### 3.1 Create Mission

**Endpoint:** `POST /v1/missions`

**Scopes:** `missions:write`

**Request:**
```json
{
  "description": "Analyze Python web scraper for list operations and optimization opportunities",
  "requirements": {
    "languages": ["python"],
    "target_domains": ["list_operations", "io_operations"],
    "analysis_depth": "comprehensive",
    "include_optimization": true
  },
  "source": {
    "type": "github_repo",
    "url": "https://github.com/user/web-scraper",
    "branch": "main"
  },
  "options": {
    "priority": "normal",
    "notification_webhook": "https://your-app.com/webhooks/hgr",
    "deadline": "2026-02-10T00:00:00Z"
  }
}
```

**Response:** `201 Created`
```json
{
  "mission_id": "mission-m4a8f9b2",
  "status": "pending",
  "created_at": "2026-02-06T14:30:00Z",
  "estimated_completion": "2026-02-06T15:30:00Z",
  "assigned_agents": [
    {
      "agent_id": "PM-001",
      "role": "Project Manager"
    },
    {
      "agent_id": "CEO-001",
      "role": "Mission Coordinator"
    }
  ],
  "links": {
    "self": "/v1/missions/mission-m4a8f9b2",
    "status": "/v1/missions/mission-m4a8f9b2/status",
    "logs": "/v1/missions/mission-m4a8f9b2/logs",
    "websocket": "wss://api.hgr.local/v1/missions/mission-m4a8f9b2/stream"
  }
}
```

### 3.2 Get Mission Status

**Endpoint:** `GET /v1/missions/{mission_id}`

**Scopes:** `missions:read`

**Response:** `200 OK`
```json
{
  "mission_id": "mission-m4a8f9b2",
  "status": "processing",
  "progress": {
    "current_phase": "extraction",
    "percentage": 65,
    "phases_completed": ["planning", "decomposition"],
    "phases_remaining": ["extraction", "verification", "fusion", "optimization"]
  },
  "created_at": "2026-02-06T14:30:00Z",
  "updated_at": "2026-02-06T14:50:00Z",
  "estimated_completion": "2026-02-06T15:30:00Z",
  "agents_active": [
    {
      "agent_id": "AGENT-PY-001",
      "status": "extracting",
      "logicnodes_extracted": 47
    },
    {
      "agent_id": "AUDIT-LEAD-001",
      "status": "verifying",
      "logicnodes_verified": 32
    }
  ],
  "metrics": {
    "logicnodes_extracted": 47,
    "logicnodes_verified": 32,
    "verification_pass_rate": 0.9787,
    "tokens_consumed": 125000,
    "execution_time_seconds": 1200
  }
}
```

### 3.3 List Missions

**Endpoint:** `GET /v1/missions`

**Scopes:** `missions:read`

**Query Parameters:**
- `status` - Filter by status (`pending`, `processing`, `completed`, `failed`)
- `page` - Page number (default: 1)
- `per_page` - Items per page (default: 50, max: 100)
- `sort` - Sort field (`created_at`, `updated_at`)
- `order` - Sort order (`asc`, `desc`)

**Request:**
```bash
GET /v1/missions?status=completed&page=1&per_page=20&sort=created_at&order=desc
```

**Response:** `200 OK`
```json
{
  "data": [
    {
      "mission_id": "mission-m4a8f9b2",
      "description": "Analyze Python web scraper...",
      "status": "completed",
      "created_at": "2026-02-06T14:30:00Z",
      "completed_at": "2026-02-06T15:25:00Z",
      "logicnodes_count": 47,
      "links": {
        "self": "/v1/missions/mission-m4a8f9b2",
        "results": "/v1/missions/mission-m4a8f9b2/results"
      }
    }
    // ... more missions
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_pages": 5,
    "total_items": 94
  }
}
```

### 3.4 Get Mission Results

**Endpoint:** `GET /v1/missions/{mission_id}/results`

**Scopes:** `missions:read`

**Response:** `200 OK`
```json
{
  "mission_id": "mission-m4a8f9b2",
  "status": "completed",
  "completed_at": "2026-02-06T15:25:00Z",
  "results": {
    "logicnodes": {
      "total_extracted": 47,
      "by_domain": {
        "list_operations": 23,
        "io_operations": 12,
        "string_operations": 8,
        "error_handling": 4
      },
      "download_url": "/v1/missions/mission-m4a8f9b2/logicnodes/export"
    },
    "analysis": {
      "code_quality_score": 8.5,
      "complexity_score": 6.2,
      "optimization_opportunities": [
        {
          "type": "inefficient_iteration",
          "location": "scraper.py:45-52",
          "description": "Nested loops can be optimized using list comprehension",
          "impact": "high",
          "estimated_speedup": "3x"
        },
        {
          "type": "redundant_filtering",
          "location": "scraper.py:78-85",
          "description": "Multiple filter operations can be combined",
          "impact": "medium",
          "estimated_speedup": "1.5x"
        }
      ]
    },
    "recommendations": [
      "Use generator expressions for large datasets",
      "Consider async I/O for network requests",
      "Add error handling for network timeouts"
    ],
    "documentation": {
      "summary_report": "/v1/missions/mission-m4a8f9b2/docs/summary.pdf",
      "detailed_analysis": "/v1/missions/mission-m4a8f9b2/docs/analysis.md",
      "code_samples": "/v1/missions/mission-m4a8f9b2/docs/samples/"
    }
  },
  "execution_summary": {
    "total_duration_seconds": 3300,
    "agents_involved": 8,
    "tokens_consumed": 2450000,
    "cost_usd": 24.50
  }
}
```

### 3.5 Cancel Mission

**Endpoint:** `DELETE /v1/missions/{mission_id}`

**Scopes:** `missions:delete`

**Response:** `204 No Content`

### 3.6 Get Mission Logs

**Endpoint:** `GET /v1/missions/{mission_id}/logs`

**Scopes:** `missions:read`

**Query Parameters:**
- `level` - Filter by log level (`debug`, `info`, `warning`, `error`)
- `agent_id` - Filter by specific agent
- `since` - Timestamp (ISO 8601)

**Response:** `200 OK`
```json
{
  "mission_id": "mission-m4a8f9b2",
  "logs": [
    {
      "timestamp": "2026-02-06T14:30:05Z",
      "level": "info",
      "agent_id": "PM-001",
      "message": "Mission accepted, generating PRD"
    },
    {
      "timestamp": "2026-02-06T14:32:15Z",
      "level": "info",
      "agent_id": "CEO-001",
      "message": "PRD received, decomposing into tasks"
    },
    {
      "timestamp": "2026-02-06T14:35:00Z",
      "level": "info",
      "agent_id": "AGENT-PY-001",
      "message": "Starting extraction from repository"
    },
    {
      "timestamp": "2026-02-06T14:50:22Z",
      "level": "warning",
      "agent_id": "AGENT-PY-001",
      "message": "Complex nested loop detected, may require manual review"
    }
  ]
}
```

---

## 4. AGENTS API

Monitor and interact with the 35-agent system.

### 4.1 List Agents

**Endpoint:** `GET /v1/agents`

**Scopes:** `agents:read`

**Query Parameters:**
- `tier` - Filter by tier (`executive`, `support`, `pod`)
- `pod` - Filter by pod (`A`, `B`, `C`, `D`)
- `status` - Filter by status (`active`, `idle`, `error`)

**Response:** `200 OK`
```json
{
  "agents": [
    {
      "agent_id": "PM-001",
      "name": "PM Agent",
      "tier": "executive",
      "pod": null,
      "status": "active",
      "current_task": "mission-m4a8f9b2",
      "tasks_completed": 234,
      "tasks_failed": 2,
      "uptime_seconds": 8640000,
      "last_heartbeat": "2026-02-06T14:59:55Z",
      "links": {
        "self": "/v1/agents/PM-001",
        "logs": "/v1/agents/PM-001/logs",
        "metrics": "/v1/agents/PM-001/metrics"
      }
    },
    {
      "agent_id": "AGENT-PY-001",
      "name": "Python Specialist",
      "tier": "pod",
      "pod": "A",
      "status": "active",
      "current_task": "extracting LogicNodes from mission-m4a8f9b2",
      "specialization": "Python language extraction",
      "tasks_completed": 1847,
      "tasks_failed": 12,
      "uptime_seconds": 8640000,
      "last_heartbeat": "2026-02-06T14:59:58Z"
    }
    // ... 33 more agents
  ]
}
```

### 4.2 Get Agent Details

**Endpoint:** `GET /v1/agents/{agent_id}`

**Scopes:** `agents:read`

**Response:** `200 OK`
```json
{
  "agent_id": "AGENT-PY-001",
  "name": "Python Specialist",
  "tier": "pod",
  "pod": "A",
  "status": "active",
  "profile": {
    "role": "Python language extraction specialist",
    "education": "Deep knowledge of Python AST, syntax patterns, standard library",
    "specialization": ["list operations", "async patterns", "decorators", "generators"],
    "tools": ["ast module", "Knowledge Lake (Python docs)", "LogicNode templates"]
  },
  "current_task": {
    "task_id": "task-t123abc",
    "mission_id": "mission-m4a8f9b2",
    "description": "Extract LogicNodes from web scraper",
    "started_at": "2026-02-06T14:35:00Z",
    "progress": 0.65
  },
  "statistics": {
    "tasks_completed": 1847,
    "tasks_failed": 12,
    "success_rate": 0.9935,
    "avg_task_duration_seconds": 240,
    "logicnodes_extracted_total": 87234,
    "uptime_seconds": 8640000
  },
  "health": {
    "status": "healthy",
    "cpu_usage_percent": 45,
    "memory_usage_mb": 2048,
    "last_heartbeat": "2026-02-06T14:59:58Z"
  },
  "links": {
    "logs": "/v1/agents/AGENT-PY-001/logs",
    "metrics": "/v1/agents/AGENT-PY-001/metrics",
    "tasks": "/v1/agents/AGENT-PY-001/tasks"
  }
}
```

### 4.3 Get Agent Logs

**Endpoint:** `GET /v1/agents/{agent_id}/logs`

**Scopes:** `agents:read`

**Query Parameters:**
- `level` - Filter by log level
- `since` - Timestamp (ISO 8601)
- `limit` - Max number of logs (default: 100)

**Response:** `200 OK`
```json
{
  "agent_id": "AGENT-PY-001",
  "logs": [
    {
      "timestamp": "2026-02-06T14:35:05Z",
      "level": "info",
      "message": "Received extraction task for mission-m4a8f9b2"
    },
    {
      "timestamp": "2026-02-06T14:35:12Z",
      "level": "debug",
      "message": "Parsed AST with 234 nodes"
    },
    {
      "timestamp": "2026-02-06T14:36:45Z",
      "level": "info",
      "message": "Extracted 12 list_filter LogicNodes"
    }
  ]
}
```

### 4.4 Send Agent Command

**Endpoint:** `POST /v1/agents/{agent_id}/commands`

**Scopes:** `agents:control`

**Request:**
```json
{
  "command": "pause",
  "reason": "Scheduled maintenance",
  "duration_seconds": 300
}
```

**Response:** `200 OK`
```json
{
  "agent_id": "AGENT-PY-001",
  "command": "pause",
  "status": "acknowledged",
  "message": "Agent will pause after completing current task"
}
```

**Available Commands:**
- `pause` - Temporarily pause agent
- `resume` - Resume paused agent
- `restart` - Restart agent
- `health_check` - Trigger health check

---

## 5. LOGICNODES API

Query and analyze extracted LogicNodes.

### 5.1 Search LogicNodes

**Endpoint:** `GET /v1/logicnodes/search`

**Scopes:** `logicnodes:read`

**Query Parameters:**
- `q` - Search query
- `domain` - Filter by domain
- `concept` - Filter by concept
- `language` - Filter by source language
- `mission_id` - Filter by mission
- `confidence_min` - Minimum confidence (0-1)

**Request:**
```bash
GET /v1/logicnodes/search?q=list filter&domain=list_operations&confidence_min=0.95
```

**Response:** `200 OK`
```json
{
  "query": "list filter",
  "total_results": 47,
  "results": [
    {
      "logicnode_id": "ln-abc123xyz",
      "paradigm": "dynamic",
      "domain": "list_operations",
      "concept": "filter",
      "intent": "Remove elements from collection that don't satisfy predicate",
      "source_language": "python",
      "confidence": 0.99,
      "created_at": "2026-02-06T14:45:00Z",
      "inputs": [
        {"name": "collection", "type": "List[T]"},
        {"name": "predicate", "type": "Callable[[T], bool]"}
      ],
      "outputs": [
        {"name": "filtered", "type": "List[T]"}
      ],
      "verification_status": "verified",
      "links": {
        "self": "/v1/logicnodes/ln-abc123xyz",
        "mission": "/v1/missions/mission-m4a8f9b2"
      }
    }
    // ... more results
  ]
}
```

### 5.2 Get LogicNode Details

**Endpoint:** `GET /v1/logicnodes/{logicnode_id}`

**Scopes:** `logicnodes:read`

**Response:** `200 OK`
```json
{
  "logicnode_id": "ln-abc123xyz",
  "version": "1.0.0",
  "paradigm": "dynamic",
  "domain": "list_operations",
  "concept": "filter",
  "intent": "Remove elements from collection that don't satisfy predicate",
  "inputs": [
    {
      "name": "collection",
      "type": "List[T]",
      "description": "The collection to filter"
    },
    {
      "name": "predicate",
      "type": "Callable[[T], bool]",
      "description": "Function that returns true for elements to keep"
    }
  ],
  "outputs": [
    {
      "name": "filtered",
      "type": "List[T]",
      "description": "New collection containing only elements where predicate returned true"
    }
  ],
  "preconditions": [
    {
      "type": "not_null",
      "target": "collection"
    }
  ],
  "postconditions": [
    {
      "type": "subset",
      "target": "filtered",
      "of": "collection"
    },
    {
      "type": "predicate_satisfied",
      "description": "All elements in filtered satisfy predicate"
    }
  ],
  "side_effects": [],
  "source": {
    "language": "python",
    "code": "[x for x in items if x > 10]",
    "file_path": "scraper.py",
    "line_number": 45
  },
  "verification": {
    "status": "verified",
    "verified_at": "2026-02-06T14:46:00Z",
    "verified_by": "AUDIT-LEAD-001",
    "tests_passed": 999,
    "tests_total": 1000,
    "pass_rate": 0.999
  },
  "metadata": {
    "mission_id": "mission-m4a8f9b2",
    "created_by": "AGENT-PY-001",
    "created_at": "2026-02-06T14:45:00Z",
    "confidence": 0.99
  }
}
```

### 5.3 Get LogicNode Relationships

**Endpoint:** `GET /v1/logicnodes/{logicnode_id}/relationships`

**Scopes:** `logicnodes:read`

**Response:** `200 OK`
```json
{
  "logicnode_id": "ln-abc123xyz",
  "relationships": {
    "composed_of": [
      {
        "logicnode_id": "ln-def456",
        "concept": "iterate",
        "relationship": "uses_for_implementation"
      }
    ],
    "similar_to": [
      {
        "logicnode_id": "ln-ghi789",
        "concept": "filter",
        "source_language": "javascript",
        "similarity_score": 0.95
      },
      {
        "logicnode_id": "ln-jkl012",
        "concept": "filter",
        "source_language": "ruby",
        "similarity_score": 0.93
      }
    ],
    "used_in": [
      {
        "mission_id": "mission-m4a8f9b2",
        "usage_count": 3
      }
    ]
  }
}
```

### 5.4 Export LogicNodes

**Endpoint:** `GET /v1/logicnodes/export`

**Scopes:** `logicnodes:read`

**Query Parameters:**
- `mission_id` - Export LogicNodes from specific mission
- `domain` - Filter by domain
- `format` - Export format (`json`, `csv`, `yaml`)

**Response:** `200 OK`
```
Content-Type: application/json
Content-Disposition: attachment; filename="logicnodes-mission-m4a8f9b2.json"

[
  { /* LogicNode 1 */ },
  { /* LogicNode 2 */ },
  ...
]
```

---

## 6. KNOWLEDGE LAKE API

Search programming documentation and examples.

### 6.1 Search Knowledge

**Endpoint:** `POST /v1/knowledge/search`

**Scopes:** `knowledge:read`

**Request:**
```json
{
  "query": "Python asyncio event loop best practices",
  "filters": {
    "language": "python",
    "library": "asyncio",
    "doc_type": "tutorial"
  },
  "search_type": "hybrid",
  "top_k": 10,
  "include_code_examples": true
}
```

**Response:** `200 OK`
```json
{
  "query": "Python asyncio event loop best practices",
  "total_results": 10,
  "execution_time_ms": 87,
  "results": [
    {
      "doc_id": "doc-py-asyncio-123",
      "title": "Asyncio Event Loop - Best Practices",
      "url": "https://docs.python.org/3/library/asyncio-eventloop.html",
      "library": "asyncio",
      "score": 0.95,
      "chunk_text": "The event loop is the core of every asyncio application. Event loops run asynchronous tasks and callbacks, perform network IO operations, and run subprocesses...",
      "code_examples": [
        {
          "language": "python",
          "code": "import asyncio\n\nasync def main():\n    print('Hello')\n    await asyncio.sleep(1)\n    print('World')\n\nasyncio.run(main())"
        }
      ],
      "metadata": {
        "python_version": "3.11",
        "last_updated": "2024-08-15"
      }
    }
    // ... 9 more results
  ]
}
```

### 6.2 Get Documentation

**Endpoint:** `GET /v1/knowledge/docs/{doc_id}`

**Scopes:** `knowledge:read`

**Response:** `200 OK`
```json
{
  "doc_id": "doc-py-asyncio-123",
  "title": "Asyncio Event Loop - Best Practices",
  "url": "https://docs.python.org/3/library/asyncio-eventloop.html",
  "language": "python",
  "library": "asyncio",
  "content": "Full documentation text...",
  "code_examples": [...],
  "related_docs": [
    {
      "doc_id": "doc-py-asyncio-124",
      "title": "Asyncio Coroutines and Tasks"
    }
  ]
}
```

---

## 7. ANALYTICS API

System metrics and performance data.

### 7.1 Get System Metrics

**Endpoint:** `GET /v1/analytics/metrics`

**Scopes:** `analytics:read`

**Query Parameters:**
- `since` - Start timestamp
- `until` - End timestamp
- `interval` - Aggregation interval (`1m`, `5m`, `1h`, `1d`)

**Response:** `200 OK`
```json
{
  "period": {
    "start": "2026-02-06T00:00:00Z",
    "end": "2026-02-06T23:59:59Z"
  },
  "metrics": {
    "missions": {
      "total_created": 47,
      "completed": 42,
      "failed": 2,
      "in_progress": 3,
      "success_rate": 0.9545
    },
    "logicnodes": {
      "total_extracted": 2234,
      "verified": 2198,
      "verification_rate": 0.9839
    },
    "agents": {
      "total_agents": 35,
      "active": 28,
      "idle": 6,
      "error": 1,
      "uptime_percentage": 99.7
    },
    "performance": {
      "avg_mission_duration_seconds": 3600,
      "tokens_consumed_total": 15000000,
      "api_requests_total": 12450,
      "avg_response_time_ms": 187
    },
    "costs": {
      "total_usd": 150.00,
      "by_model": {
        "claude-sonnet-4": 120.00,
        "claude-haiku-4": 30.00
      }
    }
  }
}
```

### 7.2 Get Agent Performance

**Endpoint:** `GET /v1/analytics/agents/{agent_id}/performance`

**Scopes:** `analytics:read`

**Response:** `200 OK`
```json
{
  "agent_id": "AGENT-PY-001",
  "period": {
    "start": "2026-02-01T00:00:00Z",
    "end": "2026-02-06T23:59:59Z"
  },
  "statistics": {
    "tasks_completed": 234,
    "tasks_failed": 3,
    "success_rate": 0.9873,
    "avg_task_duration_seconds": 240,
    "logicnodes_extracted": 10234,
    "total_uptime_seconds": 518400,
    "uptime_percentage": 99.8
  },
  "performance_trends": {
    "daily_tasks": [
      {"date": "2026-02-01", "completed": 42, "failed": 0},
      {"date": "2026-02-02", "completed": 38, "failed": 1},
      {"date": "2026-02-03", "completed": 45, "failed": 0},
      {"date": "2026-02-04", "completed": 39, "failed": 1},
      {"date": "2026-02-05", "completed": 43, "failed": 0},
      {"date": "2026-02-06", "completed": 27, "failed": 1}
    ]
  }
}
```

---

## 8. WEBSOCKET API

Real-time updates and event streaming.

### 8.1 Connect to WebSocket

**Endpoint:** `wss://api.hgr.local/v1/ws`

**Authentication:** Include access token in connection URL:
```
wss://api.hgr.local/v1/ws?token=eyJhbGciOiJSUzI1NiIs...
```

**Client Example (JavaScript):**
```javascript
const ws = new WebSocket('wss://api.hgr.local/v1/ws?token=' + accessToken);

ws.onopen = () => {
  console.log('WebSocket connected');
  
  // Subscribe to mission updates
  ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'missions',
    mission_id: 'mission-m4a8f9b2'
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
};
```

### 8.2 Subscribe to Channels

**Available Channels:**
- `missions` - All mission events
- `missions:{mission_id}` - Specific mission updates
- `agents` - All agent status changes
- `agents:{agent_id}` - Specific agent updates
- `logicnodes` - LogicNode creation events
- `system` - System-wide notifications

**Subscribe Message:**
```json
{
  "type": "subscribe",
  "channel": "missions:mission-m4a8f9b2"
}
```

**Unsubscribe Message:**
```json
{
  "type": "unsubscribe",
  "channel": "missions:mission-m4a8f9b2"
}
```

### 8.3 Event Types

**Mission Status Change:**
```json
{
  "type": "mission_status_change",
  "channel": "missions:mission-m4a8f9b2",
  "timestamp": "2026-02-06T14:50:00Z",
  "data": {
    "mission_id": "mission-m4a8f9b2",
    "old_status": "processing",
    "new_status": "completed",
    "progress": 1.0
  }
}
```

**LogicNode Extracted:**
```json
{
  "type": "logicnode_extracted",
  "channel": "logicnodes",
  "timestamp": "2026-02-06T14:45:30Z",
  "data": {
    "logicnode_id": "ln-abc123xyz",
    "mission_id": "mission-m4a8f9b2",
    "agent_id": "AGENT-PY-001",
    "concept": "filter",
    "domain": "list_operations"
  }
}
```

**Agent State Change:**
```json
{
  "type": "agent_state_change",
  "channel": "agents:AGENT-PY-001",
  "timestamp": "2026-02-06T14:35:00Z",
  "data": {
    "agent_id": "AGENT-PY-001",
    "old_state": "idle",
    "new_state": "active",
    "task_id": "task-t123abc"
  }
}
```

---

## 9. ERROR HANDLING

### 9.1 Error Response Format

All API errors return consistent JSON format:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Missing required field: description",
    "details": {
      "field": "description",
      "constraint": "required"
    },
    "request_id": "req-abc123",
    "documentation_url": "https://docs.hgr.local/errors/INVALID_REQUEST"
  }
}
```

### 9.2 Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `AUTHENTICATION_REQUIRED` | 401 | Missing or invalid authentication |
| `INSUFFICIENT_PERMISSIONS` | 403 | Authenticated but lacks required scope |
| `INVALID_REQUEST` | 400 | Malformed request or missing required fields |
| `RESOURCE_NOT_FOUND` | 404 | Requested resource doesn't exist |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | System overloaded or maintenance |

### 9.3 Rate Limiting

**Headers:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 847
X-RateLimit-Reset: 1675701600
```

**Rate Limit Exceeded Response:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "API rate limit exceeded",
    "details": {
      "limit": 1000,
      "window_seconds": 3600,
      "retry_after_seconds": 1200
    }
  }
}
```

---

## 10. CLIENT LIBRARIES & SDKS

### 10.1 Official SDKs

**Python SDK:**
```python
pip install hgr-client

from hgr_client import HGRClient

client = HGRClient(
    client_id="your_client_id",
    client_secret="your_client_secret",
    base_url="https://api.hgr.local/v1"
)

# Create mission
mission = client.missions.create(
    description="Analyze Python web scraper",
    requirements={
        "languages": ["python"],
        "target_domains": ["list_operations"]
    },
    source={
        "type": "github_repo",
        "url": "https://github.com/user/web-scraper"
    }
)

print(f"Mission ID: {mission.mission_id}")

# Wait for completion
mission.wait_for_completion(timeout=3600)

# Get results
results = mission.get_results()
print(f"Extracted {results.logicnodes_count} LogicNodes")
```

**JavaScript/TypeScript SDK:**
```bash
npm install @hgr/client

import { HGRClient } from '@hgr/client';

const client = new HGRClient({
  clientId: 'your_client_id',
  clientSecret: 'your_client_secret',
  baseUrl: 'https://api.hgr.local/v1'
});

// Create mission
const mission = await client.missions.create({
  description: 'Analyze Python web scraper',
  requirements: {
    languages: ['python'],
    targetDomains: ['list_operations']
  },
  source: {
    type: 'github_repo',
    url: 'https://github.com/user/web-scraper'
  }
});

console.log(`Mission ID: ${mission.missionId}`);

// Stream updates
mission.on('progress', (update) => {
  console.log(`Progress: ${update.percentage}%`);
});

mission.on('completed', (results) => {
  console.log(`Extracted ${results.logicnodesCount} LogicNodes`);
});
```

### 10.2 Code Examples

**Complete Mission Workflow (Python):**

```python
from hgr_client import HGRClient
import time

# Initialize client
client = HGRClient(
    client_id="your_client_id",
    client_secret="your_client_secret"
)

# Create mission
mission = client.missions.create(
    description="Analyze Django REST API project",
    requirements={
        "languages": ["python"],
        "frameworks": ["django", "django-rest-framework"],
        "analysis_depth": "comprehensive"
    },
    source={
        "type": "github_repo",
        "url": "https://github.com/user/django-api",
        "branch": "main"
    }
)

print(f"✅ Mission created: {mission.mission_id}")

# Monitor progress
while mission.status != "completed":
    status = mission.refresh()
    print(f"📊 Status: {status.current_phase} ({status.progress}%)")
    time.sleep(10)

# Get results
results = mission.get_results()
print(f"\n🎉 Mission completed!")
print(f"📦 LogicNodes extracted: {results.logicnodes_count}")
print(f"⚡ Optimization opportunities: {len(results.optimizations)}")

# Download LogicNodes
logicnodes = results.download_logicnodes()
with open("logicnodes.json", "w") as f:
    f.write(logicnodes)

print(f"💾 LogicNodes saved to logicnodes.json")
```

---

## APPENDIX: POSTMAN COLLECTION

**Import URL:**
```
https://api.hgr.local/v1/postman/collection.json
```

**Variables:**
- `{{base_url}}` - API base URL
- `{{access_token}}` - JWT access token
- `{{mission_id}}` - Mission ID for testing
- `{{agent_id}}` - Agent ID for testing

---

## DOCUMENT METADATA

**Document ID:** 52  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Documentation & Training  
**Owner:** API Team Lead  
**Target Audience:** External developers integrating with HGR  
**Related Documents:** 22 (API Layer Design), 51 (Developer Onboarding)  
**Next Document:** 53 (Agent Development Guide)

---

**For support, visit:** https://support.hgr.local  
**Community forum:** https://community.hgr.local  
**Status page:** https://status.hgr.local

---

*End of API Documentation & Reference*
