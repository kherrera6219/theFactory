# COMMUNICATION PROTOCOL SPECIFICATION
## Holy Grail Refinery: Inter-Agent Communication Standards

**Version:** 1.0  
**Date:** February 2026  
**Status:** Design Phase  
**Document Owner:** System Integration Team

---

## EXECUTIVE SUMMARY

The Holy Grail Refinery uses 6 named communication protocols to enable coordinated action across 35 agents. All communication flows through the Redis-based Semantic Bus using standardized JSON message formats. This document specifies each protocol's purpose, message schemas, routing rules, and usage patterns.

---

## 1. PROTOCOL OVERVIEW

### 1.1 The Six Protocols

| Protocol | Type | Direction | Primary Users | Purpose |
|----------|------|-----------|---------------|---------|
| **Alpha** | Directive | Top-down | CEO → Pods/Support | Strategic commands and task assignments |
| **Beta** | Production | Bottom-up | Specialists → Sub-Managers | LogicNode submission and results |
| **Delta** | Audit | Lateral | QC/Audit → Pods/CEO | Verification results (pass/fail) |
| **Sigma** | Knowledge | Broadcast | IS Agent → All | Documentation updates and standards |
| **Omega** | User | Bidirectional | PM ↔ CEO | User requirements and status |
| **Rho** | Traffic | Broadcast | API Broker → All | Rate limits and routing directives |

### 1.2 Message Transport: The Semantic Bus

**Technology:** Redis Pub/Sub + Streams  
**Channels:** Protocol-specific + pod-specific channels  
**Persistence:** Messages stored in Redis Streams for 24 hours  
**Delivery:** At-least-once delivery guarantee

---

## 2. STANDARD MESSAGE ENVELOPE

All protocols share a common message envelope:

```json
{
  "protocol": "alpha|beta|delta|sigma|omega|rho",
  "message_id": "uuid-v4",
  "timestamp": "ISO-8601 datetime",
  "sender_id": "agent_identifier",
  "recipients": ["agent_id"] or "broadcast",
  "correlation_id": "uuid-v4 (for request/response pairs)",
  "priority": "low|normal|high|critical",
  "ttl": 3600,
  "payload": {
    // Protocol-specific content
  },
  "metadata": {
    "mission_id": "uuid-v4",
    "retry_count": 0,
    "trace_id": "uuid-v4"
  }
}
```

---

## 3. PROTOCOL ALPHA: DIRECTIVE

### 3.1 Purpose

Top-down strategic communication from CEO to Pods and Support agents. Used for:
- Mission assignments
- Task decomposition
- Resource allocation
- Phase transitions
- Strategic directives

### 3.2 Message Schema

```json
{
  "protocol": "alpha",
  "payload": {
    "directive_type": "mission_assignment|phase_transition|resource_allocation|abort",
    "directive": {
      // Type-specific fields
    }
  }
}
```

### 3.3 Directive Types

#### 3.3.1 Mission Assignment

```json
{
  "directive_type": "mission_assignment",
  "directive": {
    "mission_id": "uuid-v4",
    "refined_ir_contract": {
      "required_domains": ["list_operations", "async_io"],
      "required_concepts": ["filter", "map", "fetch"],
      "target_pods": ["dynamic", "systems"],
      "quality_threshold": 0.9999,
      "deadline": "ISO-8601"
    },
    "assigned_agents": ["poda_spec_python", "podb_spec_rust"],
    "priority": "high"
  }
}
```

#### 3.3.2 Phase Transition

```json
{
  "directive_type": "phase_transition",
  "directive": {
    "current_phase": "extraction",
    "next_phase": "verification",
    "trigger": "all_logicnodes_submitted",
    "affected_pods": ["dynamic", "systems", "enterprise", "mathematical"]
  }
}
```

### 3.4 Routing Rules

- **Channel:** `protocol:alpha`
- **Publisher:** CEO Agent only
- **Subscribers:** All Sub-Managers, Support Ring agents
- **Response Expected:** Acknowledgment within 30 seconds

---

## 4. PROTOCOL BETA: PRODUCTION

### 4.1 Purpose

Bottom-up communication of work products from Specialists to Sub-Managers and from Sub-Managers to CEO. Primarily used for:
- LogicNode submission
- Group Standard delivery
- Progress updates

### 4.2 Message Schema

```json
{
  "protocol": "beta",
  "payload": {
    "production_type": "logicnode_submission|group_standard|progress_update",
    "production": {
      // Type-specific fields
    }
  }
}
```

### 4.3 Production Types

#### 4.3.1 LogicNode Submission

```json
{
  "production_type": "logicnode_submission",
  "production": {
    "logicnode": {
      "id": "uuid-v4",
      "concept": "filter_collection",
      "domain": "list_operations",
      "paradigm": "dynamic",
      "intent": "Return elements matching predicate",
      "inputs": [
        {"name": "collection", "type": {"base": "list"}},
        {"name": "predicate", "type": {"base": "function"}}
      ],
      "outputs": [
        {"name": "filtered", "type": {"base": "list"}}
      ],
      "source_language": "python",
      "source_reference": "itertools.filter, line 42",
      "confidence": 0.95
    },
    "verification_required": true
  }
}
```

#### 4.3.2 Group Standard Delivery

```json
{
  "production_type": "group_standard",
  "production": {
    "pod": "dynamic",
    "consolidated_logicnodes": ["uuid-1", "uuid-2", "uuid-3", "uuid-4"],
    "group_standard_logicnode": {
      "id": "uuid-v4",
      "concept": "filter_collection",
      "merged_from": ["python", "javascript", "ruby", "php"],
      // ... full LogicNode spec
    },
    "verification_status": "verified",
    "audit_signature": "poda_audit:sha256:..."
  }
}
```

### 4.4 Routing Rules

- **Channel:** `protocol:beta:pod_{pod_name}`
- **Publishers:** Specialists, Sub-Managers
- **Subscribers:** Sub-Managers (from Specialists), CEO (from Sub-Managers)
- **Response Expected:** Verification request or acceptance

---

## 5. PROTOCOL DELTA: AUDIT

### 5.1 Purpose

Lateral communication of quality control results. Used for:
- Verification pass/fail notifications
- Security findings
- Compliance issues
- Test results

### 5.2 Message Schema

```json
{
  "protocol": "delta",
  "payload": {
    "audit_type": "verification_result|security_finding|compliance_issue|integration_test",
    "audit": {
      // Type-specific fields
    }
  }
}
```

### 5.3 Audit Types

#### 5.3.1 Verification Result

```json
{
  "audit_type": "verification_result",
  "audit": {
    "logicnode_id": "uuid-v4",
    "status": "pass|fail",
    "tests_run": 1000,
    "tests_passed": 1000,
    "tolerance": 0.0001,
    "actual_deviation": 0.0,
    "execution_time_ms": 2340,
    "details": {
      "test_categories": {
        "edge_cases": {"passed": 100, "total": 100},
        "normal_cases": {"passed": 800, "total": 800},
        "stress_tests": {"passed": 100, "total": 100}
      }
    },
    "failures": [] // empty if pass, detailed if fail
  }
}
```

#### 5.3.2 Security Finding

```json
{
  "audit_type": "security_finding",
  "audit": {
    "logicnode_id": "uuid-v4",
    "severity": "critical|high|medium|low",
    "vulnerability_type": "sql_injection|buffer_overflow|weak_crypto|exposed_secret",
    "description": "Detected potential SQL injection in database query construction",
    "affected_code": "string concatenation for SQL query",
    "recommendation": "Use parameterized queries",
    "cve_reference": "CWE-89",
    "auto_fix_available": false
  }
}
```

### 5.4 Routing Rules

- **Channel:** `protocol:delta`
- **Publishers:** QC/Audit Agents, Security Agent, Compliance Agent, System Integration Tester
- **Subscribers:** Sub-Managers, CEO, originating Specialists
- **Response Expected:** Remediation action or acknowledgment

---

## 6. PROTOCOL SIGMA: KNOWLEDGE

### 6.1 Purpose

Broadcast updates from IS Agent to all agents about:
- Documentation updates
- New standards and best practices
- Security advisories (CVEs)
- Performance benchmarks

### 6.2 Message Schema

```json
{
  "protocol": "sigma",
  "payload": {
    "knowledge_type": "documentation_update|standards_manifesto|security_advisory|benchmark",
    "knowledge": {
      // Type-specific fields
    }
  }
}
```

### 6.3 Knowledge Types

#### 6.3.1 Standards Manifesto (Pre-Mission Broadcast)

```json
{
  "knowledge_type": "standards_manifesto",
  "knowledge": {
    "issued_at": "ISO-8601",
    "applies_to": "mission-uuid-v4",
    "updates": [
      {
        "language": "python",
        "version": "3.13",
        "changes": [
          "New TaskGroup for async operations",
          "Improved error messages",
          "Performance improvements in dict operations"
        ],
        "deprecated": ["asyncio.coroutine decorator"],
        "recommended": "Use async/await syntax exclusively"
      },
      {
        "language": "javascript",
        "framework": "react",
        "version": "19",
        "changes": ["Actions API", "useOptimistic hook"],
        "deprecated": ["Legacy lifecycle methods"],
        "recommended": "Use functional components with hooks"
      }
    ]
  }
}
```

#### 6.3.2 Security Advisory

```json
{
  "knowledge_type": "security_advisory",
  "knowledge": {
    "cve_id": "CVE-2025-1234",
    "severity": "critical",
    "affected_languages": ["c", "cpp"],
    "affected_libraries": ["openssl < 3.1.5"],
    "vulnerability": "Remote code execution via buffer overflow",
    "action_required": "Reject any LogicNodes using openssl < 3.1.5",
    "patch_available": true,
    "safe_version": "openssl >= 3.1.5"
  }
}
```

### 6.4 Routing Rules

- **Channel:** `protocol:sigma`
- **Publisher:** IS Agent only
- **Subscribers:** All agents (mandatory subscription)
- **Response Expected:** Acknowledgment + compliance confirmation

---

## 7. PROTOCOL OMEGA: USER

### 7.1 Purpose

Bidirectional communication between PM Agent and CEO for:
- User requirement transmission
- Mission status updates
- Clarification requests
- Delivery notifications

### 7.2 Message Schema

```json
{
  "protocol": "omega",
  "payload": {
    "user_type": "feature_contract|status_update|clarification|delivery_notification",
    "user": {
      // Type-specific fields
    }
  }
}
```

### 7.3 User Types

#### 7.3.1 Feature Contract (PM → CEO)

```json
{
  "user_type": "feature_contract",
  "user": {
    "user_vibe": "Build an AI-powered stock tracker that looks like a retro terminal",
    "visual_mockup_url": "data:image/png;base64,...",
    "functional_requirements": [
      "Real-time stock price updates",
      "Historical chart visualization",
      "Alert system for price thresholds",
      "Terminal-style command interface"
    ],
    "non_functional_requirements": {
      "performance": "< 100ms update latency",
      "aesthetics": "Green text on black background, monospace font",
      "platform": "Web browser, desktop only"
    },
    "success_criteria": [
      "Visual match to mockup",
      "All functional requirements met",
      "Performance target achieved"
    ],
    "constraints": [
      "No external dependencies at runtime",
      "Must work offline after initial load"
    ]
  }
}
```

#### 7.3.2 Status Update (CEO → PM)

```json
{
  "user_type": "status_update",
  "user": {
    "mission_id": "uuid-v4",
    "phase": "extraction|verification|fusion|compilation|deployment",
    "progress_percent": 65,
    "completed_tasks": [
      "Dynamic Pod extraction complete",
      "Systems Pod extraction complete"
    ],
    "in_progress_tasks": [
      "Enterprise Pod verification"
    ],
    "blocked_tasks": [],
    "estimated_completion": "ISO-8601",
    "issues": []
  }
}
```

### 7.4 Routing Rules

- **Channel:** `protocol:omega` (private channel, only PM and CEO)
- **Publishers:** PM Agent, CEO Agent
- **Subscribers:** PM Agent, CEO Agent
- **Response Expected:** Varies by message type

---

## 8. PROTOCOL RHO: TRAFFIC

### 8.1 Purpose

Broadcast from API Broker to all agents for:
- Rate limit warnings
- Model routing directives
- Cost alerts
- Traffic shaping

### 8.2 Message Schema

```json
{
  "protocol": "rho",
  "payload": {
    "traffic_type": "rate_limit_warning|model_routing|cost_alert|throttle",
    "traffic": {
      // Type-specific fields
    }
  }
}
```

### 8.3 Traffic Types

#### 8.3.1 Model Routing Directive

```json
{
  "traffic_type": "model_routing",
  "traffic": {
    "effective_immediately": true,
    "routing_rules": [
      {
        "condition": "message_length < 500 tokens",
        "route_to": "gemini-flash",
        "reason": "cost_optimization"
      },
      {
        "condition": "verification_task = true",
        "route_to": "gemini-pro",
        "reason": "accuracy_required"
      }
    ],
    "override_allowed": false
  }
}
```

#### 8.3.2 Cost Alert

```json
{
  "traffic_type": "cost_alert",
  "traffic": {
    "severity": "warning|critical",
    "current_cost": 8.50,
    "budget": 10.00,
    "burn_rate": "0.5/min",
    "projected_overage": 2.50,
    "action_required": "Enable aggressive caching, defer non-critical tasks",
    "affected_agents": ["poda_spec_python", "podc_spec_java"]
  }
}
```

### 8.4 Routing Rules

- **Channel:** `protocol:rho`
- **Publisher:** API Broker only
- **Subscribers:** All agents (mandatory)
- **Response Expected:** Immediate compliance

---

## 9. ERROR HANDLING AND RETRIES

### 9.1 Message Delivery Failures

**Retry Policy:**
```json
{
  "max_retries": 3,
  "backoff": "exponential",
  "base_delay_ms": 1000,
  "max_delay_ms": 8000,
  "retry_on": ["timeout", "network_error", "recipient_unavailable"]
}
```

### 9.2 Undeliverable Messages

After 3 retries, messages are moved to Dead Letter Queue (DLQ):
- **Storage:** Redis Stream `dlq:{protocol}`
- **Retention:** 7 days
- **Alerting:** System Integration Tester notified
- **Recovery:** Manual review and reprocessing

---

## 10. MESSAGE VERSIONING

### 10.1 Version Header

All messages include schema version:
```json
{
  "schema_version": "1.0",
  "protocol": "alpha",
  // ...
}
```

### 10.2 Backward Compatibility

- Minor version changes (1.0 → 1.1): Backward compatible
- Major version changes (1.0 → 2.0): Breaking changes, migration required
- Agents must handle both old and new versions during transition period

---

## 11. SECURITY CONSIDERATIONS

### 11.1 Message Signing

All messages include sender signature:
```json
{
  "signature": {
    "algorithm": "HMAC-SHA256",
    "key_id": "agent_api_key_hash",
    "signature": "hex_encoded_signature"
  }
}
```

### 11.2 Authorization

- Agents can only publish to authorized channels
- API Broker enforces publish permissions
- Unauthorized publish attempts logged and alerted

---

## 12. MONITORING AND OBSERVABILITY

### 12.1 Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| **Message Latency** | < 50ms p95 | > 200ms |
| **Delivery Success Rate** | > 99.9% | < 99% |
| **DLQ Size** | 0 messages | > 10 messages |
| **Protocol Usage** | Balanced | Any protocol > 80% of traffic |

### 12.2 Tracing

Every message includes `trace_id` for end-to-end tracing:
```
User Request → PM → CEO → [Pods] → CEO → PM → User Response
    (Single trace_id throughout)
```

---

**Document End**
