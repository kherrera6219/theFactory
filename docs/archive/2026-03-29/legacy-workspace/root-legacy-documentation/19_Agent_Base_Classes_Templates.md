# DOCUMENT 19: AGENT BASE CLASSES & TEMPLATES
## Holy Grail Refinery - Development Specifications

**Document ID:** 19  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides the **foundational base classes, templates, and abstractions** used by all 35 agents in the Holy Grail Refinery system. These components ensure consistency, code reuse, and standardization across the entire agent ecosystem while allowing for specialized behavior in each agent type.

**Core Components:**
- **BaseAgent**: Abstract class defining common agent behavior
- **Protocol Handlers**: Mixins for handling 6 communication protocols
- **Message Models**: Pydantic models for type-safe messaging
- **LogicNode Validator**: Schema validation and verification
- **Shared Utilities**: Common helper functions and tools

**Design Principles:**
- 🔧 Composition over inheritance
- 📦 Protocol-oriented design
- 🎯 Single responsibility principle
- 🔄 Dependency injection ready
- ✅ Type-safe with Pydantic

---

## TABLE OF CONTENTS

1. [Architecture Overview](#1-architecture-overview)
2. [BaseAgent Abstract Class](#2-baseagent-abstract-class)
3. [Message Models](#3-message-models)
4. [Protocol Handler Mixins](#4-protocol-handler-mixins)
5. [LogicNode Models & Validation](#5-logicnode-models--validation)
6. [Agent Profile Model](#6-agent-profile-model)
7. [Shared Utilities](#7-shared-utilities)
8. [Testing Base Classes](#8-testing-base-classes)
9. [Agent Implementation Examples](#9-agent-implementation-examples)
10. [Best Practices](#10-best-practices)

---

## 1. ARCHITECTURE OVERVIEW

### 1.1 Class Hierarchy

```
                    ┌─────────────────┐
                    │   BaseAgent     │
                    │   (Abstract)    │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐         ┌────▼────┐        ┌────▼────┐
    │ Manager │         │Language │        │ Support │
    │  Agent  │         │Specialist│        │  Agent  │
    └────┬────┘         └────┬────┘        └────┬────┘
         │                   │                   │
    ┌────▼────────┐     ┌────▼─────────┐   ┌────▼────────┐
    │PodAManager  │     │PythonAgent   │   │AuditAgent   │
    │PodBManager  │     │JavaScriptAgent│  │KnowledgeAgent│
    │PodCManager  │     │RustAgent     │   │DevOpsAgent  │
    │PodDManager  │     │...           │   │...          │
    └─────────────┘     └──────────────┘   └─────────────┘

             Protocol Handler Mixins (Composition)
    ┌──────────────┬──────────────┬──────────────┐
    │AlphaHandler  │BetaHandler   │DeltaHandler  │
    │SigmaHandler  │OmegaHandler  │RhoHandler    │
    └──────────────┴──────────────┴──────────────┘
```

### 1.2 Module Structure

```
agents/
├── base/
│   ├── __init__.py
│   ├── base_agent.py          # BaseAgent abstract class
│   ├── message.py             # Message models
│   ├── logicnode.py           # LogicNode models
│   ├── agent_profile.py       # AgentProfile model
│   └── utils.py               # Shared utilities
├── protocols/
│   ├── __init__.py
│   ├── alpha_handler.py       # Protocol Alpha mixin
│   ├── beta_handler.py        # Protocol Beta mixin
│   ├── delta_handler.py       # Protocol Delta mixin
│   ├── sigma_handler.py       # Protocol Sigma mixin
│   ├── omega_handler.py       # Protocol Omega mixin
│   └── rho_handler.py         # Protocol Rho mixin
├── managers/
│   ├── pod_a_manager.py
│   ├── pod_b_manager.py
│   ├── pod_c_manager.py
│   └── pod_d_manager.py
├── specialists/
│   ├── python_agent.py
│   ├── javascript_agent.py
│   └── ...
└── support/
    ├── audit_agent.py
    ├── knowledge_agent.py
    └── ...
```

---

## 2. BASEAGENT ABSTRACT CLASS

### 2.1 Core Implementation

**File:** `agents/base/base_agent.py`

```python
"""
BaseAgent - Abstract base class for all agents in Holy Grail Refinery
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import logging
from pydantic import BaseModel

from agents.base.message import Message, MessageResponse
from agents.base.agent_profile import AgentProfile
from semantic_bus.redis_client import RedisClient


class BaseAgent(ABC):
    """
    Abstract base class for all agents
    
    Provides common functionality:
    - Message handling and routing
    - State management
    - Health monitoring
    - Metrics collection
    - Lifecycle management
    """
    
    def __init__(
        self,
        agent_id: str,
        profile: AgentProfile,
        redis_client: Optional[RedisClient] = None
    ):
        """
        Initialize base agent
        
        Args:
            agent_id: Unique agent identifier (e.g., 'AGENT-PY-001')
            profile: Agent profile with capabilities and configuration
            redis_client: Redis client for Semantic Bus communication
        """
        self.agent_id = agent_id
        self.profile = profile
        self.redis = redis_client or RedisClient()
        
        # State management
        self.state = "initializing"
        self.current_task_id: Optional[str] = None
        self.message_queue: asyncio.Queue = asyncio.Queue()
        
        # Logging
        self.logger = logging.getLogger(self.agent_id)
        self.logger.setLevel(logging.INFO)
        
        # Metrics
        self._setup_metrics()
        
        # Register with system
        self._register_agent()
    
    # ========================================================================
    # LIFECYCLE MANAGEMENT
    # ========================================================================
    
    async def start(self):
        """Start agent and begin processing messages"""
        self.logger.info(f"Starting agent {self.agent_id}")
        self.state = "idle"
        
        # Subscribe to relevant channels
        await self._subscribe_to_channels()
        
        # Start message processing loop
        asyncio.create_task(self._message_processing_loop())
        
        # Start heartbeat
        asyncio.create_task(self._heartbeat_loop())
        
        self.logger.info(f"Agent {self.agent_id} started successfully")
    
    async def stop(self):
        """Gracefully stop agent"""
        self.logger.info(f"Stopping agent {self.agent_id}")
        self.state = "stopping"
        
        # Wait for current task to complete
        if self.current_task_id:
            self.logger.info(f"Waiting for task {self.current_task_id} to complete")
            # Wait with timeout
            await asyncio.wait_for(self._wait_for_task_completion(), timeout=60)
        
        self.state = "stopped"
        self.logger.info(f"Agent {self.agent_id} stopped")
    
    async def restart(self):
        """Restart agent"""
        await self.stop()
        await self.start()
    
    # ========================================================================
    # MESSAGE HANDLING
    # ========================================================================
    
    async def _message_processing_loop(self):
        """Main message processing loop"""
        while self.state != "stopped":
            try:
                # Get message from queue with timeout
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                
                # Process message
                await self._handle_message(message)
                
            except asyncio.TimeoutError:
                # No messages, continue
                continue
            except Exception as e:
                self.logger.error(f"Error in message processing loop: {e}")
    
    async def _handle_message(self, message: Message):
        """
        Route message to appropriate protocol handler
        
        Args:
            message: Incoming message
        """
        self.logger.info(
            f"Received message {message.message_id} "
            f"(protocol: {message.protocol})"
        )
        
        # Update metrics
        from agents.base.metrics import messages_received
        messages_received.labels(
            protocol=message.protocol,
            recipient=self.agent_id
        ).inc()
        
        # Route to protocol handler
        handler_name = f"handle_{message.protocol}_message"
        
        if hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            try:
                response = await handler(message)
                
                # Send response if needed
                if response:
                    await self._send_response(message, response)
                    
            except Exception as e:
                self.logger.error(f"Error handling message: {e}")
                await self._send_error_response(message, str(e))
        else:
            self.logger.warning(
                f"No handler for protocol {message.protocol}"
            )
    
    async def _send_response(
        self,
        original_message: Message,
        response_data: Dict[str, Any]
    ):
        """Send response message"""
        response = MessageResponse(
            message_id=f"resp-{original_message.message_id}",
            in_reply_to=original_message.message_id,
            protocol=original_message.protocol,
            sender=self.agent_id,
            recipient=original_message.sender,
            timestamp=datetime.utcnow().isoformat(),
            payload=response_data
        )
        
        await self.send_message(response)
    
    async def send_message(self, message: Message):
        """
        Send message via Semantic Bus
        
        Args:
            message: Message to send
        """
        self.logger.info(
            f"Sending message {message.message_id} "
            f"to {message.recipient} (protocol: {message.protocol})"
        )
        
        # Publish to Redis
        channel = self._get_channel_for_protocol(
            message.protocol,
            message.recipient
        )
        
        self.redis.publish(channel, message.dict())
        
        # Update metrics
        from agents.base.metrics import messages_sent
        messages_sent.labels(
            protocol=message.protocol,
            sender=self.agent_id,
            recipient=message.recipient
        ).inc()
    
    def _get_channel_for_protocol(
        self,
        protocol: str,
        recipient: Optional[str]
    ) -> str:
        """Get Redis channel name for protocol and recipient"""
        if protocol == "omega":
            return "protocol:omega:broadcast"
        elif recipient:
            return f"protocol:{protocol}:agent:{recipient}"
        else:
            return f"protocol:{protocol}:broadcast"
    
    # ========================================================================
    # ABSTRACT METHODS (Must be implemented by subclasses)
    # ========================================================================
    
    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process assigned task
        
        Args:
            task: Task data
            
        Returns:
            Task result
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Return list of agent capabilities
        
        Returns:
            List of capability strings
        """
        pass
    
    # ========================================================================
    # STATE MANAGEMENT
    # ========================================================================
    
    def set_state(self, new_state: str):
        """Update agent state"""
        old_state = self.state
        self.state = new_state
        
        self.logger.info(f"State transition: {old_state} → {new_state}")
        
        # Update metrics
        from agents.base.metrics import agent_health
        health_value = 1 if new_state in ["idle", "busy"] else 0
        agent_health.labels(agent_id=self.agent_id).set(health_value)
    
    def get_state(self) -> Dict[str, Any]:
        """Get current agent state"""
        return {
            "agent_id": self.agent_id,
            "state": self.state,
            "current_task_id": self.current_task_id,
            "uptime": self._get_uptime(),
            "messages_processed": self._get_message_count()
        }
    
    # ========================================================================
    # HEALTH & MONITORING
    # ========================================================================
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat"""
        while self.state != "stopped":
            try:
                await self._send_heartbeat()
                await asyncio.sleep(30)  # Every 30 seconds
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
    
    async def _send_heartbeat(self):
        """Send heartbeat to monitoring system"""
        heartbeat = {
            "agent_id": self.agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "state": self.state,
            "current_task_id": self.current_task_id
        }
        
        # Store in Redis with TTL
        self.redis.client.setex(
            f"heartbeat:{self.agent_id}",
            60,  # 60 second TTL
            str(heartbeat)
        )
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check
        
        Returns:
            Health check result
        """
        return {
            "agent_id": self.agent_id,
            "healthy": self.state in ["idle", "busy"],
            "state": self.state,
            "redis_connected": self.redis.health_check(),
            "last_heartbeat": self._get_last_heartbeat_time()
        }
    
    # ========================================================================
    # METRICS
    # ========================================================================
    
    def _setup_metrics(self):
        """Initialize metrics for this agent"""
        from agents.base.metrics import agent_health, agent_memory_usage
        
        # Set initial health
        agent_health.labels(agent_id=self.agent_id).set(0)
        
        # Start metrics server if not already running
        try:
            from agents.base.metrics import start_metrics_server
            start_metrics_server(port=9100)
        except OSError:
            # Server already running
            pass
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _register_agent(self):
        """Register agent in system database"""
        # Store agent info in Redis
        agent_info = {
            "agent_id": self.agent_id,
            "name": self.profile.name,
            "tier": self.profile.tier,
            "pod": self.profile.pod,
            "capabilities": self.get_capabilities(),
            "registered_at": datetime.utcnow().isoformat()
        }
        
        self.redis.client.hset(
            "agents:registry",
            self.agent_id,
            str(agent_info)
        )
    
    async def _subscribe_to_channels(self):
        """Subscribe to relevant Redis channels"""
        channels = [
            f"protocol:alpha:agent:{self.agent_id}",
            f"protocol:beta:agent:{self.agent_id}",
            f"protocol:delta:agent:{self.agent_id}",
            f"protocol:sigma:agent:{self.agent_id}",
            "protocol:omega:broadcast"
        ]
        
        def callback(channel, message):
            """Handle incoming message"""
            try:
                msg = Message(**message)
                asyncio.create_task(self.message_queue.put(msg))
            except Exception as e:
                self.logger.error(f"Error parsing message: {e}")
        
        # Subscribe in background
        asyncio.create_task(
            asyncio.to_thread(
                self.redis.subscribe,
                channels,
                callback
            )
        )
    
    def _get_uptime(self) -> int:
        """Get agent uptime in seconds"""
        # Implementation depends on startup time tracking
        return 0
    
    def _get_message_count(self) -> int:
        """Get total messages processed"""
        # Implementation depends on counter tracking
        return 0
    
    def _get_last_heartbeat_time(self) -> Optional[str]:
        """Get timestamp of last heartbeat"""
        heartbeat_data = self.redis.client.get(f"heartbeat:{self.agent_id}")
        if heartbeat_data:
            import ast
            data = ast.literal_eval(heartbeat_data)
            return data.get("timestamp")
        return None
    
    async def _wait_for_task_completion(self):
        """Wait for current task to complete"""
        while self.current_task_id:
            await asyncio.sleep(0.5)
```

---

## 3. MESSAGE MODELS

### 3.1 Core Message Types

**File:** `agents/base/message.py`

```python
"""
Message models for inter-agent communication
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime


class Message(BaseModel):
    """Base message structure for all protocols"""
    
    message_id: str = Field(..., description="Unique message identifier")
    protocol: str = Field(..., description="Protocol name (alpha, beta, etc.)")
    sender: str = Field(..., description="Sending agent ID")
    recipient: Optional[str] = Field(None, description="Recipient agent ID (None for broadcast)")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    payload: Dict[str, Any] = Field(..., description="Protocol-specific payload")
    
    class Config:
        schema_extra = {
            "example": {
                "message_id": "msg-abc123",
                "protocol": "alpha",
                "sender": "ARCH-001",
                "recipient": "AGENT-PY-001",
                "timestamp": "2026-02-05T10:30:00Z",
                "payload": {
                    "message_type": "assignment",
                    "task_id": "task-456",
                    "instructions": "Extract LogicNodes from repo"
                }
            }
        }


class MessageResponse(Message):
    """Response message"""
    
    in_reply_to: str = Field(..., description="Original message ID")
    status: str = Field(default="success", description="Response status")


class ProtocolAlphaPayload(BaseModel):
    """Protocol Alpha (Directive) payload"""
    
    message_type: str = Field(..., pattern="^(assignment|priority_update|abort)$")
    task_id: str
    priority: int = Field(..., ge=1, le=5)
    instructions: str
    deadline: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ProtocolBetaPayload(BaseModel):
    """Protocol Beta (Production) payload"""
    
    message_type: str = Field(..., pattern="^(logicnode|batch_complete)$")
    logicnode_id: Optional[str] = None
    source_language: Optional[str] = None
    logicnode: Optional[Dict[str, Any]] = None
    batch_id: Optional[str] = None
    batch_size: Optional[int] = None


class ProtocolDeltaPayload(BaseModel):
    """Protocol Delta (Audit) payload"""
    
    message_type: str = Field(..., pattern="^(audit_request|audit_response)$")
    audit_type: str = Field(..., pattern="^(security|performance|correctness)$")
    target_id: str
    results: Optional[Dict[str, Any]] = None
    issues: Optional[list] = None
    status: str = Field(..., pattern="^(verified|failed|warning)$")


class ProtocolSigmaPayload(BaseModel):
    """Protocol Sigma (Knowledge Query) payload"""
    
    message_type: str = Field(..., pattern="^(query|response)$")
    query_type: str
    query: str
    results: Optional[list] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class ProtocolOmegaPayload(BaseModel):
    """Protocol Omega (Announcement) payload"""
    
    message_type: str = Field(..., pattern="^(system_update|alert|shutdown)$")
    severity: str = Field(..., pattern="^(info|warning|critical)$")
    announcement: str
    affects: list = []


class ProtocolRhoPayload(BaseModel):
    """Protocol Rho (Traffic/Events) payload"""
    
    event_type: str
    agent_id: str
    event_data: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
```

---

## 4. PROTOCOL HANDLER MIXINS

### 4.1 Alpha Protocol Handler

**File:** `agents/protocols/alpha_handler.py`

```python
"""
Protocol Alpha (Directive) Handler Mixin
For command and control messages
"""

from typing import Dict, Any
from agents.base.message import Message, ProtocolAlphaPayload


class AlphaProtocolHandler:
    """
    Mixin for agents that handle Protocol Alpha messages
    
    Protocol Alpha is used for:
    - Task assignments from CEO/Managers
    - Priority updates
    - Task abort commands
    """
    
    async def handle_alpha_message(self, message: Message) -> Dict[str, Any]:
        """
        Handle Protocol Alpha (Directive) message
        
        Args:
            message: Incoming Alpha message
            
        Returns:
            Response data
        """
        # Validate payload
        try:
            payload = ProtocolAlphaPayload(**message.payload)
        except Exception as e:
            return {"status": "error", "error": f"Invalid payload: {e}"}
        
        # Route to specific handler
        if payload.message_type == "assignment":
            return await self._handle_assignment(payload)
        elif payload.message_type == "priority_update":
            return await self._handle_priority_update(payload)
        elif payload.message_type == "abort":
            return await self._handle_abort(payload)
        else:
            return {"status": "error", "error": "Unknown message type"}
    
    async def _handle_assignment(
        self,
        payload: ProtocolAlphaPayload
    ) -> Dict[str, Any]:
        """
        Handle task assignment
        
        Override this method in subclass to implement specific behavior
        """
        self.logger.info(
            f"Received task assignment: {payload.task_id} "
            f"(priority: {payload.priority})"
        )
        
        # Store task
        self.current_task_id = payload.task_id
        self.set_state("busy")
        
        # Process task asynchronously
        task_data = {
            "task_id": payload.task_id,
            "instructions": payload.instructions,
            "priority": payload.priority,
            "deadline": payload.deadline
        }
        
        # Start task processing
        result = await self.process_task(task_data)
        
        # Clear current task
        self.current_task_id = None
        self.set_state("idle")
        
        return {
            "status": "completed",
            "task_id": payload.task_id,
            "result": result
        }
    
    async def _handle_priority_update(
        self,
        payload: ProtocolAlphaPayload
    ) -> Dict[str, Any]:
        """Handle priority update for current task"""
        self.logger.info(
            f"Priority update for task {payload.task_id}: {payload.priority}"
        )
        
        # Update task priority
        # Implementation depends on task queue structure
        
        return {
            "status": "acknowledged",
            "task_id": payload.task_id,
            "new_priority": payload.priority
        }
    
    async def _handle_abort(
        self,
        payload: ProtocolAlphaPayload
    ) -> Dict[str, Any]:
        """Handle task abort command"""
        self.logger.warning(f"Aborting task {payload.task_id}")
        
        if self.current_task_id == payload.task_id:
            # Cancel current task
            self.current_task_id = None
            self.set_state("idle")
            
            return {
                "status": "aborted",
                "task_id": payload.task_id
            }
        else:
            return {
                "status": "error",
                "error": f"Task {payload.task_id} not currently running"
            }
```

### 4.2 Beta Protocol Handler

**File:** `agents/protocols/beta_handler.py`

```python
"""
Protocol Beta (Production) Handler Mixin
For LogicNode delivery
"""

from typing import Dict, Any
from agents.base.message import Message, ProtocolBetaPayload
from agents.base.logicnode import LogicNode, validate_logicnode


class BetaProtocolHandler:
    """
    Mixin for agents that handle Protocol Beta messages
    
    Protocol Beta is used for:
    - LogicNode delivery from specialists to managers
    - Batch completion notifications
    """
    
    async def handle_beta_message(self, message: Message) -> Dict[str, Any]:
        """
        Handle Protocol Beta (Production) message
        
        Args:
            message: Incoming Beta message
            
        Returns:
            Response data
        """
        # Validate payload
        try:
            payload = ProtocolBetaPayload(**message.payload)
        except Exception as e:
            return {"status": "error", "error": f"Invalid payload: {e}"}
        
        # Route to specific handler
        if payload.message_type == "logicnode":
            return await self._handle_logicnode_delivery(payload)
        elif payload.message_type == "batch_complete":
            return await self._handle_batch_complete(payload)
        else:
            return {"status": "error", "error": "Unknown message type"}
    
    async def _handle_logicnode_delivery(
        self,
        payload: ProtocolBetaPayload
    ) -> Dict[str, Any]:
        """Handle LogicNode delivery"""
        self.logger.info(
            f"Received LogicNode {payload.logicnode_id} "
            f"from language: {payload.source_language}"
        )
        
        # Validate LogicNode
        try:
            validate_logicnode(payload.logicnode)
        except ValueError as e:
            return {
                "status": "rejected",
                "error": f"Invalid LogicNode: {e}"
            }
        
        # Store LogicNode
        await self._store_logicnode(payload.logicnode)
        
        # Send for audit if configured
        if self.profile.requires_audit:
            await self._send_to_audit(payload.logicnode_id)
        
        return {
            "status": "accepted",
            "logicnode_id": payload.logicnode_id
        }
    
    async def _handle_batch_complete(
        self,
        payload: ProtocolBetaPayload
    ) -> Dict[str, Any]:
        """Handle batch completion notification"""
        self.logger.info(
            f"Batch {payload.batch_id} complete "
            f"({payload.batch_size} LogicNodes)"
        )
        
        return {
            "status": "acknowledged",
            "batch_id": payload.batch_id
        }
    
    async def _store_logicnode(self, logicnode: Dict[str, Any]):
        """Store LogicNode in database"""
        # Implementation depends on database setup
        pass
    
    async def _send_to_audit(self, logicnode_id: str):
        """Send LogicNode to audit agent"""
        # Implementation depends on audit workflow
        pass
```

---

## 5. LOGICNODE MODELS & VALIDATION

### 5.1 LogicNode Data Model

**File:** `agents/base/logicnode.py`

```python
"""
LogicNode models and validation
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional


class TypeSpec(BaseModel):
    """Type specification"""
    base: str
    parameters: Optional[List[Dict[str, Any]]] = []


class IOSpec(BaseModel):
    """Input/Output specification"""
    name: str
    type: TypeSpec
    default: Optional[Any] = None


class Constraint(BaseModel):
    """Constraint specification"""
    type: str  # predicate, range, dependency
    expression: Optional[str] = None
    variable: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None


class SideEffect(BaseModel):
    """Side effect specification"""
    type: str  # file_io, network, state_mutation, external_call
    description: str
    scope: str  # local, global, external


class LogicNode(BaseModel):
    """
    Universal LogicNode representation
    
    Captures pure computational intent across all programming languages
    """
    
    domain: str = Field(..., description="Semantic domain (e.g., 'control_flow')")
    concept: str = Field(..., description="Specific concept (e.g., 'conditional')")
    intent: str = Field(..., description="What this code intends to do")
    
    inputs: List[IOSpec] = Field(..., description="Input parameters")
    outputs: List[IOSpec] = Field(..., description="Output values")
    
    preconditions: List[Constraint] = Field(default=[], description="Preconditions")
    postconditions: List[Constraint] = Field(default=[], description="Postconditions")
    side_effects: List[SideEffect] = Field(default=[], description="Side effects")
    
    is_pure: bool = Field(default=True, description="Whether function is pure")
    complexity_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    @validator('domain')
    def validate_domain(cls, v):
        """Validate domain is registered"""
        valid_domains = [
            "control_flow", "data_structures", "arithmetic_operations",
            "string_operations", "file_io", "network_io", "error_handling",
            "concurrency", "memory_management", "type_operations"
        ]
        if v not in valid_domains:
            raise ValueError(f"Unknown domain: {v}")
        return v
    
    @validator('is_pure')
    def validate_purity(cls, v, values):
        """Validate purity matches side effects"""
        side_effects = values.get('side_effects', [])
        if v and len(side_effects) > 0:
            raise ValueError("Pure functions cannot have side effects")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "domain": "arithmetic_operations",
                "concept": "addition",
                "intent": "Add two numbers",
                "inputs": [
                    {"name": "a", "type": {"base": "number"}},
                    {"name": "b", "type": {"base": "number"}}
                ],
                "outputs": [
                    {"name": "result", "type": {"base": "number"}}
                ],
                "preconditions": [],
                "postconditions": [
                    {
                        "type": "predicate",
                        "expression": "result == a + b"
                    }
                ],
                "side_effects": [],
                "is_pure": True
            }
        }


def validate_logicnode(logicnode_dict: Dict[str, Any]) -> LogicNode:
    """
    Validate LogicNode dictionary against schema
    
    Args:
        logicnode_dict: LogicNode as dictionary
        
    Returns:
        Validated LogicNode instance
        
    Raises:
        ValueError: If validation fails
    """
    try:
        return LogicNode(**logicnode_dict)
    except Exception as e:
        raise ValueError(f"LogicNode validation failed: {e}")
```

---

## 6. AGENT PROFILE MODEL

**File:** `agents/base/agent_profile.py`

```python
"""
Agent profile data model
"""

from pydantic import BaseModel
from typing import List, Optional


class AgentProfile(BaseModel):
    """
    Agent profile configuration
    
    Defines agent identity, capabilities, and configuration
    """
    
    agent_id: str
    name: str
    tier: str  # executive, support, pod
    pod: Optional[str] = None  # A, B, C, D
    
    # Capabilities
    languages: List[str] = []
    domains: List[str] = []
    
    # Configuration
    requires_audit: bool = True
    max_concurrent_tasks: int = 5
    timeout_seconds: int = 300
    
    # Communication
    protocols: List[str] = ["alpha", "beta", "omega"]
    
    class Config:
        schema_extra = {
            "example": {
                "agent_id": "AGENT-PY-001",
                "name": "Python Specialist",
                "tier": "pod",
                "pod": "A",
                "languages": ["python"],
                "domains": [
                    "control_flow",
                    "data_structures",
                    "file_io"
                ],
                "requires_audit": True,
                "max_concurrent_tasks": 5,
                "timeout_seconds": 300,
                "protocols": ["alpha", "beta", "delta", "omega"]
            }
        }
```

---

## 7. SHARED UTILITIES

### 7.1 Common Helper Functions

**File:** `agents/base/utils.py`

```python
"""
Shared utility functions for all agents
"""

import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, Optional


def generate_message_id() -> str:
    """Generate unique message ID"""
    return f"msg-{uuid.uuid4().hex[:12]}"


def generate_task_id() -> str:
    """Generate unique task ID"""
    return f"task-{uuid.uuid4().hex[:12]}"


def generate_logicnode_id(source_file: str, line_number: int) -> str:
    """
    Generate deterministic LogicNode ID
    
    Args:
        source_file: Source file path
        line_number: Line number in source
        
    Returns:
        LogicNode ID
    """
    content = f"{source_file}:{line_number}"
    hash_hex = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"ln-{hash_hex}"


def calculate_complexity(logicnode: Dict[str, Any]) -> float:
    """
    Calculate complexity score for LogicNode
    
    Factors:
    - Number of inputs/outputs
    - Number of preconditions/postconditions
    - Presence of side effects
    - Nesting depth (if available)
    
    Returns:
        Complexity score (0.0 to 1.0)
    """
    score = 0.0
    
    # Inputs/outputs complexity
    io_count = len(logicnode.get('inputs', [])) + len(logicnode.get('outputs', []))
    score += min(io_count * 0.05, 0.3)
    
    # Constraints complexity
    constraint_count = (
        len(logicnode.get('preconditions', [])) +
        len(logicnode.get('postconditions', []))
    )
    score += min(constraint_count * 0.05, 0.3)
    
    # Side effects complexity
    if logicnode.get('side_effects'):
        score += 0.2
    
    # Normalize to 0-1
    return min(score, 1.0)


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """Format datetime as ISO string"""
    if dt is None:
        dt = datetime.utcnow()
    return dt.isoformat() + 'Z'


def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse ISO timestamp string"""
    return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
```

---

## 8. TESTING BASE CLASSES

### 8.1 Agent Test Harness

**File:** `tests/base/agent_test_harness.py`

```python
"""
Test harness for agent testing
"""

import pytest
from unittest.mock import Mock, AsyncMock
from agents.base.base_agent import BaseAgent
from agents.base.agent_profile import AgentProfile


class AgentTestHarness:
    """
    Test harness for agent unit tests
    
    Provides mock Redis client and utilities
    """
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        mock = Mock()
        mock.publish = Mock()
        mock.subscribe = Mock()
        mock.health_check = Mock(return_value=True)
        mock.client = Mock()
        return mock
    
    @pytest.fixture
    def sample_profile(self):
        """Sample agent profile"""
        return AgentProfile(
            agent_id="TEST-001",
            name="Test Agent",
            tier="pod",
            pod="A",
            languages=["python"],
            domains=["control_flow"],
            protocols=["alpha", "beta", "omega"]
        )
    
    def create_test_message(
        self,
        protocol: str,
        sender: str = "TEST-SENDER",
        recipient: str = "TEST-001",
        payload: dict = None
    ):
        """Create test message"""
        from agents.base.message import Message
        from agents.base.utils import generate_message_id, format_timestamp
        
        return Message(
            message_id=generate_message_id(),
            protocol=protocol,
            sender=sender,
            recipient=recipient,
            timestamp=format_timestamp(),
            payload=payload or {}
        )
```

---

## 9. AGENT IMPLEMENTATION EXAMPLES

### 9.1 Concrete Agent Example

**File:** `agents/specialists/python_agent.py`

```python
"""
Python Specialist Agent - Concrete implementation
"""

from typing import Dict, Any, List
import ast

from agents.base.base_agent import BaseAgent
from agents.base.agent_profile import AgentProfile
from agents.protocols.alpha_handler import AlphaProtocolHandler
from agents.protocols.beta_handler import BetaProtocolHandler
from agents.protocols.omega_handler import OmegaProtocolHandler
from agents.base.logicnode import LogicNode


class PythonAgent(BaseAgent, AlphaProtocolHandler, BetaProtocolHandler, OmegaProtocolHandler):
    """
    Python language specialist agent
    
    Extracts LogicNodes from Python source code
    """
    
    def __init__(self, agent_id: str = "AGENT-PY-001"):
        profile = AgentProfile(
            agent_id=agent_id,
            name="Python Specialist",
            tier="pod",
            pod="A",
            languages=["python"],
            domains=[
                "control_flow",
                "data_structures",
                "functions",
                "classes",
                "error_handling"
            ]
        )
        
        super().__init__(agent_id, profile)
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Python code extraction task
        
        Args:
            task: Task with source code to analyze
            
        Returns:
            Extracted LogicNodes
        """
        source_code = task.get('source_code')
        
        if not source_code:
            return {"status": "error", "error": "No source code provided"}
        
        # Parse Python AST
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return {"status": "error", "error": f"Syntax error: {e}"}
        
        # Extract LogicNodes
        logicnodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                ln = self._extract_function_logicnode(node)
                logicnodes.append(ln)
            elif isinstance(node, ast.If):
                ln = self._extract_conditional_logicnode(node)
                logicnodes.append(ln)
        
        return {
            "status": "success",
            "logicnodes": logicnodes,
            "count": len(logicnodes)
        }
    
    def get_capabilities(self) -> List[str]:
        """Return Python agent capabilities"""
        return [
            "extract_functions",
            "extract_classes",
            "extract_control_flow",
            "analyze_imports",
            "detect_patterns"
        ]
    
    def _extract_function_logicnode(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Extract LogicNode from function definition"""
        return {
            "domain": "functions",
            "concept": "function_definition",
            "intent": f"Define function {node.name}",
            "inputs": [
                {"name": arg.arg, "type": {"base": "any"}}
                for arg in node.args.args
            ],
            "outputs": [
                {"name": "return_value", "type": {"base": "any"}}
            ],
            "preconditions": [],
            "postconditions": [],
            "side_effects": []
        }
    
    def _extract_conditional_logicnode(self, node: ast.If) -> Dict[str, Any]:
        """Extract LogicNode from if statement"""
        return {
            "domain": "control_flow",
            "concept": "conditional",
            "intent": "Branch execution based on condition",
            "inputs": [
                {"name": "condition", "type": {"base": "boolean"}}
            ],
            "outputs": [
                {"name": "branch_taken", "type": {"base": "string"}}
            ],
            "preconditions": [],
            "postconditions": [],
            "side_effects": []
        }
```

---

## 10. BEST PRACTICES

### 10.1 Agent Development Guidelines

**1. Always extend BaseAgent**
```python
class MyAgent(BaseAgent, ProtocolHandlerA, ProtocolHandlerB):
    def __init__(self, agent_id):
        profile = AgentProfile(...)
        super().__init__(agent_id, profile)
```

**2. Use type hints and Pydantic models**
```python
async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
    # Type-safe, validated
    pass
```

**3. Handle exceptions gracefully**
```python
try:
    result = await self.process_task(task)
except Exception as e:
    self.logger.error(f"Task failed: {e}")
    return {"status": "error", "error": str(e)}
```

**4. Use decorators for metrics**
```python
from agents.base.metrics import track_task_duration

@track_task_duration('extract_logicnodes')
async def process_task(self, task):
    # Automatically tracked
    pass
```

**5. Implement idempotency**
```python
def generate_logicnode_id(self, source_file, line):
    # Deterministic IDs enable idempotency
    return f"ln-{hash(source_file + str(line))}"
```

---

## DOCUMENT METADATA

**Document ID:** 19  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Owner:** Chief Architect  
**Dependencies:** Documents 5-12 (Architecture & Specifications)  
**Next Document:** 20 (Semantic Bus Implementation)

---

*End of Agent Base Classes & Templates*
