# Protocol Alpha: Directive Protocol
## The Command & Control Communication System

---

## Executive Summary

Protocol Alpha is the hierarchical command protocol used by leadership-tier agents (CEO, Sub-Managers, PM Agent) to issue directives, assignments, and strategic decisions throughout the Holy Grail Refinery system. It represents top-down communication that cascades requirements and orchestrates the 34-agent organization.

**Primary Function:** Strategic command distribution and mission assignment  
**Direction:** Top-Down (Leadership → Workers)  
**Format:** Structured JSON directives with clear authority chains  
**Latency Target:** <50ms for critical path decisions

---

## Protocol Architecture

### Communication Flow

```
Human User → PM Agent → Grand Manager (CEO) → Sub-Managers → Specialists
                    ↓
              [Semantic Bus broadcasts to Support Agents]
```

### Authority Hierarchy

1. **Tier 1 - User Interface**
   - PM Agent receives human "vibe" and translates to structured requirements

2. **Tier 2 - Executive Command**
   - Grand Manager (CEO) decomposes into logic clusters and assigns to Pods

3. **Tier 3 - Tactical Management**
   - Sub-Managers translate strategy into specific extraction tasks

4. **Tier 4 - Execution**
   - Specialists receive precise instructions for logic mining operations

---

## Message Structure

### Directive Message Schema

```json
{
  "protocol": "ALPHA",
  "version": "1.0",
  "message_id": "UUID",
  "timestamp": "ISO-8601",
  "sender": {
    "agent_id": "CEO-001",
    "agent_type": "GRAND_MANAGER",
    "tier": 2
  },
  "recipient": {
    "agent_id": "SUB-MANAGER-A",
    "agent_type": "POD_MANAGER",
    "tier": 3,
    "pod": "DYNAMIC"
  },
  "directive_type": "MISSION_ASSIGNMENT | PRIORITY_SHIFT | ABORT | VALIDATE",
  "payload": {
    "mission_id": "M-2025-001",
    "priority": "HIGH | MEDIUM | LOW | CRITICAL",
    "assignment": {
      "target_languages": ["Python", "JavaScript", "Ruby", "PHP"],
      "source_libraries": ["react@18.2.0", "numpy@1.24.0"],
      "extraction_scope": "FULL | PARTIAL | INCREMENTAL",
      "logic_domains": ["UI_RENDERING", "DATA_PROCESSING"],
      "constraints": {
        "time_budget_seconds": 300,
        "token_budget": 50000,
        "quality_threshold": 0.95
      }
    },
    "dependencies": ["MISSION-M-2025-000"],
    "success_criteria": {
      "logicnode_count_min": 100,
      "coverage_percentage": 85,
      "audit_pass_required": true
    }
  },
  "routing": {
    "broadcast": false,
    "cc": ["SECURITY-001", "ACCOUNTANT-001"],
    "reply_required": true,
    "deadline": "ISO-8601"
  }
}
```

### Directive Types

#### 1. MISSION_ASSIGNMENT
Assigns new extraction or fusion work to subordinate agents.

**Example:**
```json
{
  "directive_type": "MISSION_ASSIGNMENT",
  "payload": {
    "mission_id": "M-2025-042",
    "priority": "HIGH",
    "assignment": {
      "description": "Extract authentication logic from Django framework",
      "target_languages": ["Python"],
      "source_libraries": ["django@4.2.0"],
      "extraction_scope": "PARTIAL",
      "logic_domains": ["AUTH", "SESSION", "SECURITY"],
      "deliverable": "REFINED_IR_LOGICNODES"
    }
  }
}
```

#### 2. PRIORITY_SHIFT
Changes priority of ongoing work based on strategic needs.

```json
{
  "directive_type": "PRIORITY_SHIFT",
  "payload": {
    "mission_id": "M-2025-038",
    "old_priority": "MEDIUM",
    "new_priority": "CRITICAL",
    "reason": "User deadline accelerated",
    "resource_reallocation": {
      "model_upgrade": "FLASH_TO_PRO",
      "additional_tokens": 100000
    }
  }
}
```

#### 3. ABORT
Terminates ongoing work due to changing requirements or discovered blockers.

```json
{
  "directive_type": "ABORT",
  "payload": {
    "mission_id": "M-2025-027",
    "reason": "OBSOLETE | BLOCKED | USER_CANCELLED",
    "cleanup_required": true,
    "resource_recovery": {
      "release_tokens": true,
      "clear_cache": false
    }
  }
}
```

#### 4. VALIDATE
Requests confirmation or validation before proceeding with high-impact decision.

```json
{
  "directive_type": "VALIDATE",
  "payload": {
    "decision_point": "FUSION_STRATEGY",
    "proposed_action": "Merge Pod A and Pod C outputs using LLVM backend",
    "risk_assessment": "MEDIUM",
    "alternatives": ["WASM_TARGET", "NATIVE_BINARY"],
    "approval_required_from": ["PM-001"]
  }
}
```

---

## Communication Patterns

### Pattern 1: Mission Cascade

**Scenario:** User requests new application build

```
1. Human → PM Agent
   Message: Natural language "vibe"
   
2. PM Agent → CEO (via Protocol Alpha)
   Directive: PRD (Product Requirements Document)
   
3. CEO → Sub-Managers (via Protocol Alpha)
   Directive: Mission assignments to 4 Pods
   
4. Sub-Managers → Specialists (via Protocol Alpha)
   Directive: Specific library extraction tasks
```

### Pattern 2: Emergency Override

**Scenario:** Critical security issue detected

```
1. Security Agent → CEO (via Protocol Sigma - escalated to Alpha)
   Alert: CVE detected in extracted code
   
2. CEO → All Sub-Managers (via Protocol Alpha - broadcast)
   Directive: ABORT all missions using affected library
   
3. Sub-Managers → Specialists (via Protocol Alpha)
   Directive: Immediate halt and rollback
```

### Pattern 3: Resource Reallocation

**Scenario:** Pod requires more computational resources

```
1. Sub-Manager → CEO (via Protocol Beta - response via Alpha)
   Status: Token budget exhausted, mission 60% complete
   
2. CEO → API Broker (via Protocol Alpha)
   Directive: Reallocate 50K tokens from Pod D to Pod A
   
3. CEO → Sub-Manager (via Protocol Alpha)
   Directive: Continue with extended budget
```

---

## Integration with Semantic Bus

### Bus Subscription Model

**Alpha-Enabled Agents:**
- PM Agent (publisher + subscriber)
- Grand Manager/CEO (publisher + subscriber)
- Sub-Managers (publisher + subscriber)
- API Broker (subscriber only - for resource directives)
- Security Agent (subscriber only - for abort directives)
- Accountant (subscriber only - for budget directives)

### Redis Channel Structure

```
alpha:global           # System-wide broadcasts
alpha:pod:a            # Dynamic Pod directives
alpha:pod:b            # Systems Pod directives
alpha:pod:c            # Enterprise Pod directives
alpha:pod:d            # Mathematical Pod directives
alpha:support          # Support agent directives
alpha:priority:critical # High-priority override channel
```

### Message Routing Rules

1. **Direct Assignment:** Published to specific agent channel
2. **Pod Broadcast:** Published to pod-specific channel
3. **System Alert:** Published to `alpha:global`
4. **Priority Override:** Published to both specific + `alpha:priority:critical`

---

## Quality Assurance

### Message Validation

All Alpha messages must pass validation before bus publication:

```python
def validate_alpha_message(message):
    required_fields = [
        "protocol", "message_id", "timestamp",
        "sender", "recipient", "directive_type", "payload"
    ]
    
    # Schema validation
    if not all(field in message for field in required_fields):
        raise ValidationError("Missing required fields")
    
    # Authority validation
    if not is_authorized_sender(message['sender'], message['directive_type']):
        raise AuthorizationError("Sender lacks authority for directive type")
    
    # Routing validation
    if message['routing']['broadcast'] and message['directive_type'] != "ABORT":
        raise RoutingError("Only ABORT directives can use broadcast")
    
    return True
```

### Acknowledgment Requirements

All Alpha directives require acknowledgment:

```json
{
  "protocol": "ALPHA_ACK",
  "original_message_id": "UUID",
  "status": "RECEIVED | ACCEPTED | REJECTED | DEFERRED",
  "estimated_completion": "ISO-8601",
  "resource_requirements": {
    "tokens": 45000,
    "time_seconds": 240,
    "dependencies": []
  }
}
```

---

## Performance Characteristics

### Latency Requirements

| Route | Max Latency | P95 Target |
|-------|-------------|------------|
| PM → CEO | 50ms | 20ms |
| CEO → Sub-Manager | 50ms | 25ms |
| Sub-Manager → Specialist | 100ms | 50ms |
| Emergency Broadcast | 10ms | 5ms |

### Throughput Capacity

- **Normal Operations:** 500 directives/second
- **Peak Load:** 2,000 directives/second
- **Emergency Mode:** 5,000 directives/second (broadcast only)

### Message Size Limits

- **Standard Directive:** 64KB
- **Mission Assignment:** 256KB (includes full specification)
- **Emergency Abort:** 4KB (minimal payload)

---

## Error Handling

### Delivery Failures

```json
{
  "error_type": "DELIVERY_FAILURE",
  "original_message_id": "UUID",
  "failure_reason": "AGENT_OFFLINE | TIMEOUT | QUEUE_FULL",
  "retry_policy": {
    "max_attempts": 3,
    "backoff_strategy": "EXPONENTIAL",
    "escalate_after": 3,
    "escalation_target": "CEO"
  }
}
```

### Authority Violations

```json
{
  "error_type": "AUTHORITY_VIOLATION",
  "violating_agent": "SPECIALIST-A-1",
  "attempted_action": "MISSION_ASSIGNMENT",
  "required_tier": 3,
  "actual_tier": 4,
  "action_taken": "REJECTED_AND_LOGGED"
}
```

### Conflict Resolution

When conflicting directives arrive:

1. **Priority-based:** CRITICAL > HIGH > MEDIUM > LOW
2. **Timestamp-based:** Most recent wins for same priority
3. **Authority-based:** Higher tier agent overrides lower tier
4. **Escalation:** Conflicts between same-tier escalate to CEO

---

## Security Considerations

### Authentication

All Alpha messages must include cryptographic signature:

```json
{
  "signature": {
    "algorithm": "ED25519",
    "public_key_id": "CEO-001-PUB",
    "signature_bytes": "base64-encoded-signature",
    "signed_fields": ["message_id", "timestamp", "sender", "directive_type"]
  }
}
```

### Authorization Matrix

| Sender Tier | Can Issue To | Directive Types Allowed |
|-------------|--------------|------------------------|
| Tier 1 (PM) | Tier 2 (CEO) | MISSION_ASSIGNMENT, VALIDATE |
| Tier 2 (CEO) | Tier 3, Support | ALL |
| Tier 3 (Sub-Mgr) | Tier 4 | MISSION_ASSIGNMENT, PRIORITY_SHIFT |
| Tier 4 (Specialist) | None | N/A |

### Audit Trail

Every Alpha message generates immutable audit record:

```json
{
  "audit_record_id": "AUD-2025-001234",
  "message_id": "UUID",
  "timestamp": "ISO-8601",
  "sender": "CEO-001",
  "recipients": ["SUB-MANAGER-A", "SUB-MANAGER-B"],
  "directive_type": "MISSION_ASSIGNMENT",
  "hash": "SHA-256 of complete message",
  "stored_in": "TRACEABILITY_LEDGER"
}
```

---

## Implementation Guidelines

### Sender Best Practices

1. **Clear Scope:** Define mission boundaries explicitly
2. **Measurable Success:** Include quantifiable success criteria
3. **Resource Awareness:** Specify token and time budgets
4. **Dependency Tracking:** List all prerequisite missions
5. **Rollback Plan:** Include abort conditions

### Receiver Best Practices

1. **Immediate ACK:** Send acknowledgment within 100ms
2. **Feasibility Check:** Validate resource availability before accepting
3. **Status Updates:** Send Protocol Beta updates at 25%, 50%, 75% completion
4. **Exception Reporting:** Escalate blockers immediately via Protocol Sigma

### API Broker Integration

The API Broker monitors Alpha traffic for resource directives:

```python
# API Broker watches for resource-related Alpha messages
def handle_alpha_directive(message):
    if message['directive_type'] == 'MISSION_ASSIGNMENT':
        # Pre-allocate tokens based on mission constraints
        allocate_token_budget(
            agent=message['recipient'],
            tokens=message['payload']['constraints']['token_budget'],
            priority=message['payload']['priority']
        )
    
    if message['directive_type'] == 'ABORT':
        # Release allocated resources
        release_resources(
            mission_id=message['payload']['mission_id']
        )
```

---

## Monitoring & Observability

### Key Metrics

1. **Directive Delivery Rate:** % of directives successfully delivered
2. **Average Acknowledgment Time:** Time from send to ACK
3. **Mission Completion Rate:** % of assignments completed successfully
4. **Abort Rate:** % of missions aborted (should be <5%)
5. **Authority Violation Rate:** Attempted unauthorized directives

### Alerting Thresholds

- **Delivery failures >5%:** Page on-call engineer
- **ACK time >1 second:** Warning alert
- **Abort rate >10%:** Investigate mission planning quality
- **Authority violations >0:** Security incident

### Dashboard Visualization

Mission Control displays real-time Alpha traffic:
- Active directives by Pod
- Mission completion progress bars
- Authority hierarchy tree with active flows
- Recent abort events with reasons

---

## Protocol Evolution

### Version 1.0 (Current)

- JSON-based messaging
- Synchronous acknowledgment required
- Manual conflict resolution

### Version 2.0 (Planned)

- Binary protocol buffers for reduced bandwidth
- Asynchronous acknowledgment with timeout
- AI-assisted conflict resolution via CEO agent
- Multi-cast optimization for Pod broadcasts

---

## Appendix A: Example Scenarios

### Complete Mission Lifecycle

```
Time 0:00 - User requests "Build a real-time chat app"

Time 0:01 - PM Agent → CEO (Alpha)
{
  "directive_type": "MISSION_ASSIGNMENT",
  "payload": {
    "mission_id": "M-CHAT-APP",
    "description": "Real-time bidirectional messaging system",
    "target_languages": "ALL",
    "priority": "HIGH"
  }
}

Time 0:02 - CEO → Sub-Manager A (Alpha)
{
  "directive_type": "MISSION_ASSIGNMENT",
  "payload": {
    "mission_id": "M-CHAT-APP-FRONTEND",
    "assignment": "Extract WebSocket libraries from React/Vue",
    "deliverable": "UI LogicNodes"
  }
}

Time 0:02 - CEO → Sub-Manager B (Alpha)
{
  "directive_type": "MISSION_ASSIGNMENT",
  "payload": {
    "mission_id": "M-CHAT-APP-BACKEND",
    "assignment": "Extract high-performance event loops",
    "deliverable": "Server LogicNodes"
  }
}

[Work proceeds via Protocol Beta...]

Time 5:00 - User changes mind: "Actually make it a video chat app"

Time 5:01 - PM Agent → CEO (Alpha)
{
  "directive_type": "PRIORITY_SHIFT",
  "payload": {
    "mission_id": "M-CHAT-APP",
    "new_requirements": "Add WebRTC video streaming"
  }
}

Time 5:02 - CEO → Sub-Manager D (Alpha)
{
  "directive_type": "MISSION_ASSIGNMENT",
  "payload": {
    "mission_id": "M-CHAT-APP-VIDEO",
    "assignment": "Extract video codec logic from FFmpeg",
    "priority": "CRITICAL"
  }
}
```

---

## Summary

Protocol Alpha is the nervous system of command and control in the Holy Grail Refinery. It ensures clear authority, traceable decisions, and coordinated action across 34 autonomous agents. By maintaining strict hierarchical communication with comprehensive validation and audit trails, Alpha enables the distributed AI organization to function as a unified software manufacturing system.

**Key Principles:**
1. Clear authority chains prevent chaos
2. Structured messages enable automation
3. Acknowledgments ensure reliability
4. Audit trails provide accountability
5. Priority systems enable dynamic adaptation

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-30  
**Maintained By:** Holy Grail Refinery Architecture Team  
**Related Protocols:** Beta (Production), Delta (Audit), Sigma (Knowledge), Omega (User), Rho (Traffic)
