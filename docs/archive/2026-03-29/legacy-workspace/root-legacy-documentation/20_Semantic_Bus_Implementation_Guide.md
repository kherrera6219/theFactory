# DOCUMENT 20: SEMANTIC BUS IMPLEMENTATION GUIDE

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Development Specifications

**Document ID:** 20  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

The **Semantic Bus** is the central nervous system of the Holy Grail Refinery, enabling all 35 agents to communicate through a unified, protocol-aware message routing infrastructure. Built on Redis pub/sub with Model Context Protocol (MCP) extensions, the Semantic Bus provides reliable, asynchronous messaging with protocol validation, routing intelligence, and comprehensive observability.

This document provides complete implementation specifications for deploying and configuring the Semantic Bus on local AW1 hardware.

---

## TABLE OF CONTENTS

1. [Architecture Overview](#1-architecture-overview)
2. [Redis Infrastructure Setup](#2-redis-infrastructure-setup)
3. [MCP Server Implementation](#3-mcp-server-implementation)
4. [Protocol Routing Engine](#4-protocol-routing-engine)
5. [Message Serialization](#5-message-serialization)
6. [Reliability Patterns](#6-reliability-patterns)
7. [Monitoring & Observability](#7-monitoring--observability)
8. [Performance Optimization](#8-performance-optimization)
9. [Operational Procedures](#9-operational-procedures)

---

## 1. ARCHITECTURE OVERVIEW

### 1.1 Conceptual Model

```
┌─────────────────────────────────────────────────────────────┐
│                     SEMANTIC BUS                             │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Protocol   │    │   Message    │    │   Routing    │  │
│  │  Validator   │───▶│   Router     │───▶│   Engine     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │         │
│         ▼                    ▼                    ▼         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Redis Pub/Sub Core                       │  │
│  │  • 6 Protocol Channels (Alpha, Beta, Delta, etc.)    │  │
│  │  • Dead Letter Queue                                  │  │
│  │  • Message Persistence (Redis Streams)                │  │
│  └──────────────────────────────────────────────────────┘  │
│         │                    │                    │         │
│         ▼                    ▼                    ▼         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Telemetry   │    │  Circuit     │    │    Retry     │  │
│  │  Collector   │    │  Breaker     │    │    Logic     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
         ▲                    ▲                    ▲
         │                    │                    │
    ┌────┴────┐          ┌────┴────┐          ┌────┴────┐
    │ Agent A │          │ Agent B │          │ Agent C │
    └─────────┘          └─────────┘          └─────────┘
```

### 1.2 Core Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Redis Server** | Redis 7.2+ | Core pub/sub engine, stream persistence |
| **MCP Server** | Python FastAPI | Protocol validation, routing logic |
| **Protocol Validator** | Pydantic | Schema validation for 6 protocols |
| **Message Router** | Custom Logic | Intelligent routing based on protocol |
| **Circuit Breaker** | Resilience4j patterns | Failure isolation |
| **Dead Letter Queue** | Redis List | Failed message capture |
| **Telemetry** | OpenTelemetry | Metrics, traces, logs |

### 1.3 Communication Patterns

**Supported Patterns:**
- **Pub/Sub:** One-to-many broadcast (Protocol Omega - announcements)
- **Point-to-Point:** Direct agent-to-agent (Protocol Alpha - directives)
- **Request/Reply:** Synchronous-style over async (Protocol Beta - production)
- **Fan-Out/Fan-In:** Parallel task distribution (Pod manager to specialists)
- **Event Streaming:** Ordered event log (Protocol Rho - traffic updates)

---

## 2. REDIS INFRASTRUCTURE SETUP

### 2.1 Docker Container Configuration

**File:** `docker-compose.yml` (Redis service)

```yaml
services:
  redis-semantic-bus:
    image: redis:7.2-alpine
    container_name: hgr-redis-bus
    restart: unless-stopped
    
    ports:
      - "6379:6379"  # Redis protocol
      - "8001:8001"  # Redis Insight (optional)
    
    volumes:
      - redis-data:/data
      - ./config/redis.conf:/usr/local/etc/redis/redis.conf
    
    command: redis-server /usr/local/etc/redis/redis.conf
    
    environment:
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    
    networks:
      - hgr-network
    
    # Resource limits for AW1 hardware
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G

volumes:
  redis-data:
    driver: local

networks:
  hgr-network:
    driver: bridge
```

### 2.2 Redis Configuration

**File:** `config/redis.conf`

```conf
# Redis Configuration for Semantic Bus

# Network
bind 0.0.0.0
protected-mode yes
port 6379
tcp-backlog 511
timeout 0
tcp-keepalive 300

# Security
requirepass ${REDIS_PASSWORD}
maxclients 10000

# Memory Management
maxmemory 3gb
maxmemory-policy allkeys-lru
maxmemory-samples 5

# Persistence (for message durability)
save 900 1      # Save after 900s if 1 key changed
save 300 10     # Save after 300s if 10 keys changed
save 60 10000   # Save after 60s if 10000 keys changed
dir /data
dbfilename dump.rdb
rdbcompression yes
rdbchecksum yes

# Append Only File (AOF) for better durability
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Redis Streams (for Protocol Rho - event log)
stream-node-max-bytes 4096
stream-node-max-entries 100

# Pub/Sub
notify-keyspace-events Ex  # Enable keyspace notifications

# Logging
loglevel notice
logfile /var/log/redis/redis-server.log

# Slow Log
slowlog-log-slower-than 10000  # 10ms
slowlog-max-len 128

# Latency Monitoring
latency-monitor-threshold 100  # 100ms
```

### 2.3 Python Redis Client Setup

**File:** `semantic_bus/redis_client.py`

```python
"""
Redis client wrapper for Semantic Bus
Handles connection pooling, retry logic, and circuit breaking
"""

import redis
from redis.connection import ConnectionPool
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Production-ready Redis client with:
    - Connection pooling
    - Automatic reconnection
    - Circuit breaker pattern
    - Telemetry integration
    """
    
    def __init__(
        self,
        host: str = "redis-semantic-bus",
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        max_connections: int = 50
    ):
        self.pool = ConnectionPool(
            host=host,
            port=port,
            password=password,
            db=db,
            max_connections=max_connections,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )
        
        self.client = redis.Redis(
            connection_pool=self.pool,
            decode_responses=True  # Auto-decode bytes to str
        )
        
        # Circuit breaker state
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60
        )
    
    def publish(self, channel: str, message: Dict[str, Any]) -> int:
        """
        Publish message to Redis channel
        Returns: number of subscribers who received the message
        """
        try:
            serialized = json.dumps(message)
            num_receivers = self.client.publish(channel, serialized)
            
            logger.debug(f"Published to {channel}, {num_receivers} receivers")
            return num_receivers
            
        except redis.RedisError as e:
            logger.error(f"Redis publish error: {e}")
            self.circuit_breaker.record_failure()
            raise
    
    def subscribe(self, channels: List[str], callback):
        """
        Subscribe to Redis channels with callback function
        Runs in blocking mode - use in separate thread
        """
        pubsub = self.client.pubsub()
        pubsub.subscribe(**{channel: callback for channel in channels})
        
        logger.info(f"Subscribed to channels: {channels}")
        
        # Listen loop
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    callback(message['channel'], data)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in message: {e}")
    
    def add_to_stream(
        self,
        stream_key: str,
        data: Dict[str, Any],
        maxlen: int = 10000
    ) -> str:
        """
        Add message to Redis Stream (for Protocol Rho)
        Returns: stream entry ID
        """
        try:
            entry_id = self.client.xadd(
                stream_key,
                data,
                maxlen=maxlen,
                approximate=True  # Faster trimming
            )
            return entry_id
            
        except redis.RedisError as e:
            logger.error(f"Stream add error: {e}")
            raise
    
    def read_stream(
        self,
        stream_key: str,
        last_id: str = "0",
        count: int = 100,
        block: int = 1000  # ms
    ) -> List[tuple]:
        """
        Read from Redis Stream
        Returns: list of (entry_id, data) tuples
        """
        try:
            results = self.client.xread(
                {stream_key: last_id},
                count=count,
                block=block
            )
            
            if results:
                return results[0][1]  # [(stream, [(id, data), ...])]
            return []
            
        except redis.RedisError as e:
            logger.error(f"Stream read error: {e}")
            raise
    
    def push_to_dlq(self, message: Dict[str, Any], reason: str):
        """
        Push failed message to Dead Letter Queue
        """
        dlq_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason,
            "message": json.dumps(message)
        }
        
        self.client.lpush("semantic_bus:dlq", json.dumps(dlq_entry))
        logger.warning(f"Message pushed to DLQ: {reason}")
    
    def health_check(self) -> bool:
        """Check if Redis is healthy"""
        try:
            return self.client.ping()
        except redis.RedisError:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Redis server statistics"""
        info = self.client.info()
        return {
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "0B"),
            "total_commands_processed": info.get("total_commands_processed", 0),
            "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec", 0),
            "pubsub_channels": self.client.pubsub_channels()
        }


class CircuitBreaker:
    """
    Circuit breaker pattern implementation
    States: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(f"Circuit breaker OPEN after {self.failure_count} failures")
    
    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def can_attempt(self) -> bool:
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            # Check if recovery timeout elapsed
            if datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker entering HALF_OPEN state")
                return True
            return False
        
        if self.state == "HALF_OPEN":
            return True
        
        return False
```

---

## 3. MCP SERVER IMPLEMENTATION

### 3.1 FastAPI MCP Server

**File:** `semantic_bus/mcp_server.py`

```python
"""
Model Context Protocol (MCP) Server
Validates and routes messages according to 6 protocol schemas
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import uuid

from semantic_bus.redis_client import RedisClient
from semantic_bus.protocols import (
    AlphaMessage, BetaMessage, DeltaMessage,
    SigmaMessage, OmegaMessage, RhoMessage
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Semantic Bus MCP Server",
    version="1.0.0",
    description="Protocol-aware message routing for Holy Grail Refinery"
)

# Dependency injection
def get_redis() -> RedisClient:
    return RedisClient(
        host="redis-semantic-bus",
        password=os.getenv("REDIS_PASSWORD")
    )


class MessageEnvelope(BaseModel):
    """Generic message envelope for all protocols"""
    message_id: str
    protocol: str  # alpha, beta, delta, sigma, omega, rho
    sender: str
    recipient: Optional[str] = None  # None for broadcast
    timestamp: str
    payload: Dict[str, Any]


@app.post("/send")
async def send_message(
    envelope: MessageEnvelope,
    redis: RedisClient = Depends(get_redis)
):
    """
    Send message through Semantic Bus
    Validates protocol schema and routes to appropriate channel
    """
    
    try:
        # Step 1: Validate protocol schema
        validated_payload = validate_protocol(
            envelope.protocol,
            envelope.payload
        )
        
        # Step 2: Determine routing
        channel = get_routing_channel(
            envelope.protocol,
            envelope.recipient
        )
        
        # Step 3: Prepare message
        message = {
            "message_id": envelope.message_id,
            "protocol": envelope.protocol,
            "sender": envelope.sender,
            "recipient": envelope.recipient,
            "timestamp": envelope.timestamp,
            "payload": validated_payload
        }
        
        # Step 4: Publish to Redis
        num_receivers = redis.publish(channel, message)
        
        # Step 5: Log to Protocol Rho stream (traffic log)
        redis.add_to_stream(
            "protocol:rho:traffic",
            {
                "event": "message_sent",
                "message_id": envelope.message_id,
                "protocol": envelope.protocol,
                "sender": envelope.sender,
                "channel": channel,
                "receivers": str(num_receivers)
            }
        )
        
        return {
            "status": "sent",
            "message_id": envelope.message_id,
            "channel": channel,
            "receivers": num_receivers
        }
        
    except ValidationError as e:
        logger.error(f"Protocol validation failed: {e}")
        redis.push_to_dlq(envelope.dict(), f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Protocol validation failed: {e}"
        )
    
    except Exception as e:
        logger.error(f"Message send failed: {e}")
        redis.push_to_dlq(envelope.dict(), f"Send error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {e}"
        )


def validate_protocol(protocol: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate payload against protocol schema
    """
    protocol_validators = {
        "alpha": AlphaMessage,
        "beta": BetaMessage,
        "delta": DeltaMessage,
        "sigma": SigmaMessage,
        "omega": OmegaMessage,
        "rho": RhoMessage
    }
    
    if protocol not in protocol_validators:
        raise ValueError(f"Unknown protocol: {protocol}")
    
    validator = protocol_validators[protocol]
    validated = validator(**payload)
    
    return validated.dict()


def get_routing_channel(protocol: str, recipient: Optional[str]) -> str:
    """
    Determine Redis channel based on protocol and recipient
    """
    if protocol == "omega":
        # Broadcast to all agents
        return "protocol:omega:broadcast"
    
    elif protocol in ["alpha", "beta", "delta", "sigma"]:
        # Point-to-point or pod-specific
        if recipient:
            return f"protocol:{protocol}:agent:{recipient}"
        else:
            return f"protocol:{protocol}:broadcast"
    
    elif protocol == "rho":
        # Event stream
        return "protocol:rho:events"
    
    else:
        raise ValueError(f"Cannot route protocol: {protocol}")


@app.get("/health")
async def health_check(redis: RedisClient = Depends(get_redis)):
    """Health check endpoint"""
    redis_healthy = redis.health_check()
    
    return {
        "status": "healthy" if redis_healthy else "degraded",
        "redis": "up" if redis_healthy else "down",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/stats")
async def get_stats(redis: RedisClient = Depends(get_redis)):
    """Get Semantic Bus statistics"""
    stats = redis.get_stats()
    
    return {
        "redis": stats,
        "protocols": {
            "alpha": "Directive - Command & Control",
            "beta": "Production - LogicNode delivery",
            "delta": "Audit Request/Response",
            "sigma": "Knowledge Query/Response",
            "omega": "System Announcements",
            "rho": "Traffic & Events"
        }
    }


@app.get("/dlq")
async def get_dead_letter_queue(
    limit: int = 100,
    redis: RedisClient = Depends(get_redis)
):
    """Get messages from Dead Letter Queue"""
    dlq_items = redis.client.lrange("semantic_bus:dlq", 0, limit - 1)
    
    return {
        "count": len(dlq_items),
        "messages": [json.loads(item) for item in dlq_items]
    }
```

### 3.2 Protocol Schemas

**File:** `semantic_bus/protocols.py`

```python
"""
Pydantic models for all 6 communication protocols
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class AlphaMessage(BaseModel):
    """
    Protocol Alpha: Directive (Command & Control)
    CEO → Managers, Managers → Specialists
    """
    message_type: str = Field(..., pattern="^(assignment|priority_update|abort)$")
    task_id: str
    priority: int = Field(..., ge=1, le=5)
    instructions: str
    deadline: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}


class BetaMessage(BaseModel):
    """
    Protocol Beta: Production (LogicNode Delivery)
    Specialists → Managers → Synthesis Agents
    """
    message_type: str = Field(..., pattern="^(logicnode|batch_complete)$")
    logicnode_id: Optional[str] = None
    source_language: Optional[str] = None
    logicnode: Optional[Dict[str, Any]] = None
    batch_id: Optional[str] = None
    batch_size: Optional[int] = None


class DeltaMessage(BaseModel):
    """
    Protocol Delta: Audit (Request/Response)
    Managers ↔ Audit Agents
    """
    message_type: str = Field(..., pattern="^(audit_request|audit_response)$")
    audit_type: str = Field(..., pattern="^(security|performance|correctness)$")
    target_id: str  # LogicNode or task ID
    results: Optional[Dict[str, Any]] = None
    issues: Optional[List[Dict[str, Any]]] = None
    status: str = Field(..., pattern="^(verified|failed|warning)$")


class SigmaMessage(BaseModel):
    """
    Protocol Sigma: Knowledge (Query/Response)
    Any Agent ↔ Support Agents
    """
    message_type: str = Field(..., pattern="^(query|response)$")
    query_type: str  # concept_lookup, template_search, etc.
    query: str
    results: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class OmegaMessage(BaseModel):
    """
    Protocol Omega: Announcements (Broadcast)
    CEO → All Agents
    """
    message_type: str = Field(..., pattern="^(system_update|alert|shutdown)$")
    severity: str = Field(..., pattern="^(info|warning|critical)$")
    announcement: str
    affects: List[str] = []  # Agent IDs affected


class RhoMessage(BaseModel):
    """
    Protocol Rho: Traffic & Events (Event Stream)
    System-wide event log
    """
    event_type: str
    agent_id: str
    event_data: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
```

---

## 4. PROTOCOL ROUTING ENGINE

### 4.1 Routing Rules

| Protocol | Pattern | Channel Format | Example |
|----------|---------|----------------|---------|
| **Alpha** | Point-to-point | `protocol:alpha:agent:{agent_id}` | `protocol:alpha:agent:AGENT-PY-001` |
| **Beta** | Point-to-point | `protocol:beta:agent:{agent_id}` | `protocol:beta:agent:MANAGER-POD-A-001` |
| **Delta** | Request/Reply | `protocol:delta:agent:{agent_id}` | `protocol:delta:agent:AUDIT-SEC-001` |
| **Sigma** | Query/Response | `protocol:sigma:topic:{topic}` | `protocol:sigma:topic:concepts` |
| **Omega** | Broadcast | `protocol:omega:broadcast` | `protocol:omega:broadcast` |
| **Rho** | Stream | `protocol:rho:events` | `protocol:rho:events` (Redis Stream) |

### 4.2 Message Flow Examples

**Example 1: Protocol Alpha (CEO assigns task to Pod A Manager)**

```python
# CEO Agent sends directive
envelope = {
    "message_id": "msg-001",
    "protocol": "alpha",
    "sender": "ARCH-001",
    "recipient": "MANAGER-POD-A-001",
    "timestamp": "2026-02-05T10:30:00Z",
    "payload": {
        "message_type": "assignment",
        "task_id": "task-12345",
        "priority": 1,
        "instructions": "Extract LogicNodes from Python repo",
        "deadline": "2026-02-05T18:00:00Z"
    }
}

# MCP Server routes to:
channel = "protocol:alpha:agent:MANAGER-POD-A-001"
```

**Example 2: Protocol Beta (Python Specialist delivers LogicNode)**

```python
envelope = {
    "message_id": "msg-002",
    "protocol": "beta",
    "sender": "AGENT-PY-001",
    "recipient": "MANAGER-POD-A-001",
    "timestamp": "2026-02-05T11:00:00Z",
    "payload": {
        "message_type": "logicnode",
        "logicnode_id": "ln-789",
        "source_language": "python",
        "logicnode": {
            "domain": "control_flow",
            "concept": "conditional",
            "inputs": [...],
            "outputs": [...]
        }
    }
}

channel = "protocol:beta:agent:MANAGER-POD-A-001"
```

**Example 3: Protocol Omega (System-wide announcement)**

```python
envelope = {
    "message_id": "msg-003",
    "protocol": "omega",
    "sender": "ARCH-001",
    "recipient": None,  # Broadcast
    "timestamp": "2026-02-05T12:00:00Z",
    "payload": {
        "message_type": "system_update",
        "severity": "info",
        "announcement": "New Refined-IR schema v2.1 deployed",
        "affects": ["all"]
    }
}

channel = "protocol:omega:broadcast"
# All 35 agents subscribe to this channel
```

---

## 5. MESSAGE SERIALIZATION

### 5.1 JSON Schema Validation

All messages use JSON serialization with strict schema validation via Pydantic.

**Example:** Validated Alpha message JSON

```json
{
  "message_id": "a3f5c8d1-9b2e-4f7a-8c3d-1e9f6b4a7c2d",
  "protocol": "alpha",
  "sender": "ARCH-001",
  "recipient": "MANAGER-POD-B-001",
  "timestamp": "2026-02-05T14:30:00.000Z",
  "payload": {
    "message_type": "assignment",
    "task_id": "task-67890",
    "priority": 2,
    "instructions": "Refactor Rust codebase for memory safety verification",
    "deadline": "2026-02-06T09:00:00.000Z",
    "metadata": {
      "repo_url": "https://github.com/example/rust-project",
      "branch": "main",
      "complexity_estimate": "high"
    }
  }
}
```

### 5.2 Binary Serialization (Optional - Future)

For high-throughput scenarios, Protocol Buffer (protobuf) serialization can be added:

```protobuf
syntax = "proto3";

message MessageEnvelope {
  string message_id = 1;
  string protocol = 2;
  string sender = 3;
  string recipient = 4;
  string timestamp = 5;
  bytes payload = 6;  // JSON-encoded payload
}
```

---

## 6. RELIABILITY PATTERNS

### 6.1 Dead Letter Queue (DLQ)

**Purpose:** Capture messages that fail validation or delivery

**Implementation:**

```python
class DeadLetterQueue:
    """Manage failed messages"""
    
    def __init__(self, redis: RedisClient):
        self.redis = redis
        self.dlq_key = "semantic_bus:dlq"
    
    def push(self, message: Dict, reason: str, max_size: int = 10000):
        """Add message to DLQ"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason,
            "message": message,
            "retry_count": 0
        }
        
        # Push to Redis list
        self.redis.client.lpush(self.dlq_key, json.dumps(entry))
        
        # Trim to max size
        self.redis.client.ltrim(self.dlq_key, 0, max_size - 1)
        
        logger.warning(f"DLQ: {reason} | Message: {message.get('message_id')}")
    
    def retry(self, message_id: str) -> bool:
        """Retry a DLQ message"""
        # Implementation: find message, increment retry_count, re-send
        pass
    
    def purge_old(self, days: int = 7):
        """Remove DLQ entries older than N days"""
        pass
```

### 6.2 Retry Logic with Exponential Backoff

```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1):
    """Decorator for retry logic"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s")
                    time.sleep(delay)
        return wrapper
    return decorator


# Usage
@retry_with_backoff(max_retries=3, base_delay=2)
def publish_message(channel, message):
    redis.publish(channel, message)
```

### 6.3 Message Acknowledgment Pattern

```python
class AckTracker:
    """Track message acknowledgments"""
    
    def __init__(self, redis: RedisClient, timeout: int = 300):
        self.redis = redis
        self.timeout = timeout  # 5 minutes
    
    def wait_for_ack(self, message_id: str) -> bool:
        """
        Wait for acknowledgment from recipient
        Returns: True if ack received, False if timeout
        """
        ack_key = f"ack:{message_id}"
        
        # Poll for ack with timeout
        start = time.time()
        while time.time() - start < self.timeout:
            if self.redis.client.get(ack_key):
                self.redis.client.delete(ack_key)
                return True
            time.sleep(0.5)
        
        return False
    
    def send_ack(self, message_id: str):
        """Send acknowledgment for received message"""
        ack_key = f"ack:{message_id}"
        self.redis.client.setex(ack_key, self.timeout, "1")
```

---

## 7. MONITORING & OBSERVABILITY

### 7.1 OpenTelemetry Integration

```python
from opentelemetry import trace, metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Initialize tracer
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Initialize metrics
meter_provider = MeterProvider(metric_readers=[PrometheusMetricReader()])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter(__name__)

# Metrics
message_counter = meter.create_counter(
    "semantic_bus.messages.total",
    description="Total messages processed"
)

message_latency = meter.create_histogram(
    "semantic_bus.latency",
    description="Message processing latency (ms)"
)


# Instrument message send
@tracer.start_as_current_span("send_message")
def send_message_traced(envelope):
    start = time.time()
    
    # Send message
    result = send_message(envelope)
    
    # Record metrics
    latency_ms = (time.time() - start) * 1000
    message_counter.add(1, {"protocol": envelope.protocol})
    message_latency.record(latency_ms, {"protocol": envelope.protocol})
    
    return result
```

### 7.2 Prometheus Metrics Endpoint

```python
from prometheus_client import Counter, Histogram, generate_latest

# Metrics
messages_sent = Counter(
    'semantic_bus_messages_sent_total',
    'Total messages sent',
    ['protocol']
)

message_send_duration = Histogram(
    'semantic_bus_message_send_duration_seconds',
    'Message send duration',
    ['protocol']
)

dlq_size = Gauge(
    'semantic_bus_dlq_size',
    'Dead letter queue size'
)


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type="text/plain")
```

### 7.3 Logging Standards

```python
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info(
    "message_sent",
    message_id=msg_id,
    protocol=protocol,
    sender=sender,
    recipient=recipient,
    channel=channel
)
```

---

## 8. PERFORMANCE OPTIMIZATION

### 8.1 Connection Pooling Best Practices

```python
# Optimal pool size for AW1 (32GB RAM, 24 cores)
REDIS_POOL_CONFIG = {
    "max_connections": 100,  # Total connections
    "socket_connect_timeout": 5,
    "socket_timeout": 5,
    "socket_keepalive": True,
    "socket_keepalive_options": {
        1: 1,  # TCP_KEEPIDLE
        2: 1,  # TCP_KEEPINTVL
        3: 3   # TCP_KEEPCNT
    },
    "health_check_interval": 30,
    "retry_on_timeout": True
}
```

### 8.2 Redis Pipelining for Batch Operations

```python
def publish_batch(messages: List[Dict]):
    """Publish multiple messages efficiently using pipeline"""
    pipe = redis.client.pipeline()
    
    for msg in messages:
        channel = get_routing_channel(msg['protocol'], msg.get('recipient'))
        pipe.publish(channel, json.dumps(msg))
    
    results = pipe.execute()
    return results
```

### 8.3 Memory Usage Optimization

```yaml
# Redis memory limits in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G  # Total limit
    reservations:
      memory: 2G  # Guaranteed minimum
```

**Memory monitoring script:**

```python
def monitor_redis_memory():
    """Alert if Redis memory usage exceeds threshold"""
    info = redis.client.info('memory')
    used_mb = info['used_memory'] / (1024 * 1024)
    max_mb = info['maxmemory'] / (1024 * 1024)
    
    usage_pct = (used_mb / max_mb) * 100
    
    if usage_pct > 80:
        logger.warning(f"Redis memory usage: {usage_pct:.1f}%")
```

---

## 9. OPERATIONAL PROCEDURES

### 9.1 Startup Sequence

```bash
#!/bin/bash
# semantic_bus_startup.sh

echo "Starting Semantic Bus infrastructure..."

# 1. Start Redis container
docker-compose up -d redis-semantic-bus

# 2. Wait for Redis to be healthy
echo "Waiting for Redis..."
until docker exec hgr-redis-bus redis-cli ping | grep -q PONG; do
    sleep 1
done
echo "✓ Redis is up"

# 3. Start MCP server
docker-compose up -d mcp-server

# 4. Wait for MCP server health check
echo "Waiting for MCP server..."
until curl -f http://localhost:8000/health; do
    sleep 1
done
echo "✓ MCP server is up"

# 5. Initialize Protocol Rho stream
docker exec hgr-redis-bus redis-cli XGROUP CREATE protocol:rho:events main_consumer $ MKSTREAM

echo "✓ Semantic Bus is ready"
```

### 9.2 Health Check Script

```python
#!/usr/bin/env python3
"""Check Semantic Bus health status"""

import requests
import sys

def check_health():
    try:
        # Check MCP server
        mcp_health = requests.get("http://localhost:8000/health").json()
        
        if mcp_health['status'] != 'healthy':
            print(f"❌ Semantic Bus unhealthy: {mcp_health}")
            return False
        
        # Check Redis stats
        stats = requests.get("http://localhost:8000/stats").json()
        
        print(f"✓ Semantic Bus healthy")
        print(f"  Connected clients: {stats['redis']['connected_clients']}")
        print(f"  Memory usage: {stats['redis']['used_memory_human']}")
        print(f"  Ops/sec: {stats['redis']['instantaneous_ops_per_sec']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

if __name__ == "__main__":
    sys.exit(0 if check_health() else 1)
```

### 9.3 Backup & Recovery

**Backup script:**

```bash
#!/bin/bash
# backup_redis.sh

BACKUP_DIR="/backups/redis"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Trigger Redis save
docker exec hgr-redis-bus redis-cli BGSAVE

# Wait for save to complete
sleep 10

# Copy RDB file
docker cp hgr-redis-bus:/data/dump.rdb "$BACKUP_DIR/dump_$TIMESTAMP.rdb"

# Copy AOF file
docker cp hgr-redis-bus:/data/appendonly.aof "$BACKUP_DIR/appendonly_$TIMESTAMP.aof"

echo "✓ Backup complete: $BACKUP_DIR"
```

**Recovery script:**

```bash
#!/bin/bash
# restore_redis.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./restore_redis.sh <backup_file>"
    exit 1
fi

# Stop Redis
docker-compose stop redis-semantic-bus

# Restore backup
docker cp "$BACKUP_FILE" hgr-redis-bus:/data/dump.rdb

# Start Redis
docker-compose start redis-semantic-bus

echo "✓ Restore complete"
```

### 9.4 Troubleshooting Guide

| Symptom | Diagnosis | Resolution |
|---------|-----------|------------|
| Messages not delivered | Check Redis connectivity | Restart Redis container |
| High latency | Check Redis memory usage | Increase maxmemory, evict old keys |
| DLQ growing | Protocol validation failures | Review protocol schemas, fix sender agents |
| Circuit breaker open | Repeated Redis failures | Check network, restart Redis |
| No subscribers | Agents not connected | Check agent logs, restart agents |

**Debug commands:**

```bash
# Check Redis channels
docker exec hgr-redis-bus redis-cli PUBSUB CHANNELS

# Monitor messages in real-time
docker exec hgr-redis-bus redis-cli MONITOR

# Check stream length
docker exec hgr-redis-bus redis-cli XLEN protocol:rho:events

# View DLQ
curl http://localhost:8000/dlq?limit=10
```

---

## DOCUMENT METADATA

**Document ID:** 20  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Owner:** Chief Architect  
**Dependencies:** Document 19 (Agent Base Classes)  
**Next Document:** 21 (Database Setup & Schemas)

---

*End of Semantic Bus Implementation Guide*
