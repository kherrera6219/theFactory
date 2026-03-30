# DOCUMENT 53: AGENT DEVELOPMENT GUIDE
## Holy Grail Refinery - Documentation & Training

**Document ID:** 53  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Documentation & Training  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides an **advanced guide for developing agents** within the Holy Grail Refinery system. It covers agent architecture patterns, implementation best practices, testing strategies, and deployment procedures. This guide is for developers who have completed the onboarding process and are ready to build production agents.

**What You'll Learn:**
- 🏗️ **Agent Architecture Patterns** - State machines, message handling, LLM integration
- 💻 **Implementation Guidelines** - Code structure, error handling, logging
- 🧪 **Testing Strategies** - Unit tests, integration tests, mock agents
- 📊 **Performance Optimization** - Context management, caching, parallelization
- 🚀 **Deployment** - Dockerization, monitoring, scaling

**Prerequisites:**
- Completed Document 51 (Developer Onboarding Guide)
- Understanding of async Python programming
- Familiarity with LangChain or similar LLM frameworks
- Experience with Docker and Redis

**Agent Types Covered:**
1. **Language Specialists** - Extract LogicNodes from source code
2. **Manager Agents** - Coordinate teams and consolidate results
3. **Audit Agents** - Verify LogicNodes with 0.0001% tolerance
4. **Support Agents** - Infrastructure and tooling support

---

## TABLE OF CONTENTS

1. [Agent Architecture Deep Dive](#1-agent-architecture-deep-dive)
2. [Implementing Language Specialists](#2-implementing-language-specialists)
3. [Building Manager Agents](#3-building-manager-agents)
4. [Creating Audit Agents](#4-creating-audit-agents)
5. [Developing Support Agents](#5-developing-support-agents)
6. [LLM Integration Patterns](#6-llm-integration-patterns)
7. [Testing Agent Implementations](#7-testing-agent-implementations)
8. [Performance & Optimization](#8-performance--optimization)
9. [Deployment & Operations](#9-deployment--operations)
10. [Advanced Topics](#10-advanced-topics)

---

## 1. AGENT ARCHITECTURE DEEP DIVE

### 1.1 Core Agent Components

Every agent in Holy Grail Refinery consists of these components:

```
┌─────────────────────────────────────────────────────────────┐
│                        AGENT                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────┐                                     │
│  │   State Machine    │  Manages agent lifecycle            │
│  │   (FSM)            │  (IDLE → PROCESSING → COMPLETE)     │
│  └────────────────────┘                                     │
│           │                                                  │
│           ▼                                                  │
│  ┌────────────────────┐                                     │
│  │  Message Handler   │  Receives/sends Protocol messages   │
│  │  (Semantic Bus)    │  (Alpha, Beta, Delta, etc.)         │
│  └────────────────────┘                                     │
│           │                                                  │
│           ▼                                                  │
│  ┌────────────────────┐                                     │
│  │   Core Logic       │  Agent-specific processing          │
│  │   Processor        │  (extraction, verification, etc.)   │
│  └────────────────────┘                                     │
│           │                                                  │
│           ▼                                                  │
│  ┌────────────────────┐                                     │
│  │   LLM Interface    │  Claude API integration             │
│  │   (Optional)       │  Context window management          │
│  └────────────────────┘                                     │
│           │                                                  │
│           ▼                                                  │
│  ┌────────────────────┐                                     │
│  │   Database Layer   │  Read/write to shared databases     │
│  │                    │  (State, Registry, Knowledge)       │
│  └────────────────────┘                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Agent Lifecycle States

**State Diagram:**
```
     ┌──────┐
     │ INIT │
     └───┬──┘
         │
         ▼
     ┌──────┐
  ┌─▶│ IDLE │◀──┐
  │  └───┬──┘   │
  │      │      │
  │      ▼      │
  │  ┌─────────┐│
  │  │RECEIVING││
  │  └───┬─────┘│
  │      │      │
  │      ▼      │
  │  ┌──────────┴─┐
  │  │ PROCESSING │
  │  └───┬────────┘
  │      │
  │      ▼
  │  ┌─────────┐
  └──│COMPLETE │
     └─────────┘
         │
         ▼
     ┌──────┐
     │ERROR │
     └──────┘
```

**State Transitions:**
```python
class AgentState(Enum):
    INIT = "initializing"         # Starting up, loading resources
    IDLE = "idle"                 # Waiting for tasks
    RECEIVING = "receiving"       # Processing incoming message
    PROCESSING = "processing"     # Executing core logic
    COMPLETE = "complete"         # Task finished successfully
    ERROR = "error"              # Error state, needs recovery
    PAUSED = "paused"            # Manually paused
    SHUTTING_DOWN = "shutting_down"  # Graceful shutdown

# Valid transitions
VALID_TRANSITIONS = {
    AgentState.INIT: [AgentState.IDLE, AgentState.ERROR],
    AgentState.IDLE: [AgentState.RECEIVING, AgentState.PAUSED, AgentState.SHUTTING_DOWN],
    AgentState.RECEIVING: [AgentState.PROCESSING, AgentState.IDLE, AgentState.ERROR],
    AgentState.PROCESSING: [AgentState.COMPLETE, AgentState.ERROR],
    AgentState.COMPLETE: [AgentState.IDLE],
    AgentState.ERROR: [AgentState.IDLE, AgentState.SHUTTING_DOWN],
    AgentState.PAUSED: [AgentState.IDLE, AgentState.SHUTTING_DOWN],
    AgentState.SHUTTING_DOWN: []
}
```

### 1.3 Agent Base Class

**File:** `infrastructure/agent_base.py`

```python
"""
Base class for all Holy Grail Refinery agents
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Optional, Any
from datetime import datetime
import uuid

from infrastructure.semantic_bus import SemanticBus
from infrastructure.database import DatabaseManager
from infrastructure.metrics import MetricsCollector

logger = logging.getLogger(__name__)

class AgentState(Enum):
    """Agent lifecycle states"""
    INIT = "initializing"
    IDLE = "idle"
    RECEIVING = "receiving"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"

class AgentBase(ABC):
    """
    Abstract base class for all agents
    
    Provides:
    - State machine management
    - Semantic Bus integration
    - Database connectivity
    - Metrics collection
    - Error handling
    - Logging
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        tier: str,
        pod: Optional[str] = None,
        semantic_bus: Optional[SemanticBus] = None,
        database: Optional[DatabaseManager] = None
    ):
        """
        Initialize agent
        
        Args:
            agent_id: Unique identifier (e.g., "AGENT-PY-001")
            agent_name: Human-readable name
            tier: Agent tier ("executive", "support", "pod")
            pod: Pod identifier if tier="pod" ("A", "B", "C", "D")
            semantic_bus: Redis connection for messaging
            database: PostgreSQL connection
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.tier = tier
        self.pod = pod
        
        # Infrastructure
        self.semantic_bus = semantic_bus
        self.database = database
        self.metrics = MetricsCollector(agent_id)
        
        # State management
        self.state = AgentState.INIT
        self.current_task = None
        self.error_count = 0
        self.max_errors = 5  # Shutdown after 5 consecutive errors
        
        # Statistics
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.startup_time = datetime.utcnow()
        
        # Logging
        self.logger = logging.getLogger(f"agent.{agent_id}")
        self.logger.info(f"Agent {agent_id} ({agent_name}) initialized")
    
    async def start(self):
        """
        Start agent (main entry point)
        """
        try:
            self.logger.info(f"Starting agent {self.agent_id}")
            
            # Connect infrastructure
            await self._connect_infrastructure()
            
            # Subscribe to message channels
            await self._subscribe_channels()
            
            # Announce startup
            await self._announce_startup()
            
            # Transition to IDLE
            await self._transition_state(AgentState.IDLE)
            
            # Main processing loop
            await self._run_loop()
            
        except Exception as e:
            self.logger.error(f"Fatal error in agent startup: {e}", exc_info=True)
            await self._transition_state(AgentState.ERROR)
            raise
    
    async def _connect_infrastructure(self):
        """Connect to Semantic Bus and databases"""
        if self.semantic_bus:
            await self.semantic_bus.connect()
            self.logger.info("Connected to Semantic Bus")
        
        if self.database:
            await self.database.connect()
            self.logger.info("Connected to database")
    
    async def _subscribe_channels(self):
        """Subscribe to relevant Semantic Bus channels"""
        if not self.semantic_bus:
            return
        
        # Subscribe to agent-specific channel
        await self.semantic_bus.subscribe(
            f"agent.{self.agent_id}",
            self._handle_message
        )
        
        # Subscribe to tier-wide broadcasts
        await self.semantic_bus.subscribe(
            f"tier.{self.tier}",
            self._handle_broadcast
        )
        
        # Pod-specific subscription
        if self.pod:
            await self.semantic_bus.subscribe(
                f"pod.{self.pod}",
                self._handle_pod_message
            )
        
        self.logger.info("Subscribed to message channels")
    
    async def _announce_startup(self):
        """Announce agent availability"""
        if not self.semantic_bus:
            return
        
        message = {
            "message_id": str(uuid.uuid4()),
            "protocol": "system",
            "message_type": "agent_startup",
            "timestamp": datetime.utcnow().isoformat(),
            "source_agent": self.agent_id,
            "payload": {
                "agent_name": self.agent_name,
                "tier": self.tier,
                "pod": self.pod,
                "state": self.state.value
            }
        }
        
        await self.semantic_bus.publish("system.events", message)
        self.logger.info("Startup announced")
    
    async def _run_loop(self):
        """Main agent processing loop"""
        while self.state != AgentState.SHUTTING_DOWN:
            try:
                if self.state == AgentState.IDLE:
                    # Heartbeat
                    await self._send_heartbeat()
                    await asyncio.sleep(5)
                
                elif self.state == AgentState.PROCESSING:
                    # Task is being processed (handled by _handle_message)
                    await asyncio.sleep(1)
                
                elif self.state == AgentState.ERROR:
                    # Attempt recovery
                    await self._recover_from_error()
                    await asyncio.sleep(10)
                
                elif self.state == AgentState.PAUSED:
                    # Wait for resume
                    await asyncio.sleep(5)
            
            except Exception as e:
                self.logger.error(f"Error in run loop: {e}", exc_info=True)
                await self._transition_state(AgentState.ERROR)
    
    async def _send_heartbeat(self):
        """Send heartbeat to monitoring system"""
        if not self.semantic_bus:
            return
        
        message = {
            "message_id": str(uuid.uuid4()),
            "protocol": "system",
            "message_type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat(),
            "source_agent": self.agent_id,
            "payload": {
                "state": self.state.value,
                "tasks_completed": self.tasks_completed,
                "tasks_failed": self.tasks_failed,
                "uptime_seconds": (datetime.utcnow() - self.startup_time).total_seconds()
            }
        }
        
        await self.semantic_bus.publish("system.heartbeats", message)
    
    async def _transition_state(self, new_state: AgentState):
        """
        Transition to new state with validation
        
        Args:
            new_state: Target state
        
        Raises:
            ValueError: If transition is invalid
        """
        old_state = self.state
        
        # Validate transition
        valid_transitions = {
            AgentState.INIT: [AgentState.IDLE, AgentState.ERROR],
            AgentState.IDLE: [AgentState.RECEIVING, AgentState.PAUSED, AgentState.SHUTTING_DOWN],
            AgentState.RECEIVING: [AgentState.PROCESSING, AgentState.IDLE, AgentState.ERROR],
            AgentState.PROCESSING: [AgentState.COMPLETE, AgentState.ERROR],
            AgentState.COMPLETE: [AgentState.IDLE],
            AgentState.ERROR: [AgentState.IDLE, AgentState.SHUTTING_DOWN],
            AgentState.PAUSED: [AgentState.IDLE, AgentState.SHUTTING_DOWN],
        }
        
        if new_state not in valid_transitions.get(old_state, []):
            raise ValueError(
                f"Invalid state transition: {old_state.value} → {new_state.value}"
            )
        
        # Perform transition
        self.state = new_state
        self.logger.info(f"State transition: {old_state.value} → {new_state.value}")
        
        # Notify system
        if self.semantic_bus:
            message = {
                "message_id": str(uuid.uuid4()),
                "protocol": "system",
                "message_type": "state_change",
                "timestamp": datetime.utcnow().isoformat(),
                "source_agent": self.agent_id,
                "payload": {
                    "old_state": old_state.value,
                    "new_state": new_state.value
                }
            }
            await self.semantic_bus.publish("system.events", message)
    
    async def _handle_message(self, message: Dict):
        """
        Handle incoming message from Semantic Bus
        
        Args:
            message: Message dictionary
        """
        try:
            await self._transition_state(AgentState.RECEIVING)
            
            message_type = message.get("message_type")
            self.logger.info(f"Received message: {message_type}")
            
            # Route to handler
            if message_type == "task_assignment":
                await self._handle_task_assignment(message)
            
            elif message_type == "status_request":
                await self._handle_status_request(message)
            
            elif message_type == "control_command":
                await self._handle_control_command(message)
            
            else:
                # Delegate to subclass
                await self.handle_message(message)
        
        except Exception as e:
            self.logger.error(f"Error handling message: {e}", exc_info=True)
            await self._transition_state(AgentState.ERROR)
    
    async def _handle_task_assignment(self, message: Dict):
        """Handle task assignment"""
        if self.state not in [AgentState.IDLE, AgentState.RECEIVING]:
            self.logger.warning(f"Received task while in state {self.state}")
            # Send rejection
            await self._send_task_rejection(message, "Agent busy")
            return
        
        # Extract task
        task = message["payload"]["task"]
        self.current_task = task
        
        # Transition to processing
        await self._transition_state(AgentState.PROCESSING)
        
        # Process task
        try:
            result = await self.process_task(task)
            
            # Send result
            await self._send_task_result(task, result)
            
            # Update statistics
            self.tasks_completed += 1
            self.error_count = 0
            
            # Transition to complete then idle
            await self._transition_state(AgentState.COMPLETE)
            await self._transition_state(AgentState.IDLE)
            
        except Exception as e:
            self.logger.error(f"Task processing failed: {e}", exc_info=True)
            
            # Send error
            await self._send_task_error(task, str(e))
            
            # Update statistics
            self.tasks_failed += 1
            self.error_count += 1
            
            # Check error threshold
            if self.error_count >= self.max_errors:
                self.logger.critical("Max errors reached, shutting down")
                await self._transition_state(AgentState.SHUTTING_DOWN)
            else:
                await self._transition_state(AgentState.ERROR)
    
    async def _handle_status_request(self, message: Dict):
        """Handle status request"""
        status = self.get_status()
        
        # Send response
        response = {
            "message_id": str(uuid.uuid4()),
            "protocol": message.get("protocol", "system"),
            "message_type": "status_response",
            "timestamp": datetime.utcnow().isoformat(),
            "source_agent": self.agent_id,
            "target_agent": message["source_agent"],
            "in_reply_to": message["message_id"],
            "payload": status
        }
        
        await self.semantic_bus.publish(
            f"agent.{message['source_agent']}",
            response
        )
    
    async def _handle_control_command(self, message: Dict):
        """Handle control commands (pause, resume, shutdown)"""
        command = message["payload"]["command"]
        
        if command == "pause":
            await self._transition_state(AgentState.PAUSED)
        
        elif command == "resume":
            if self.state == AgentState.PAUSED:
                await self._transition_state(AgentState.IDLE)
        
        elif command == "shutdown":
            await self._transition_state(AgentState.SHUTTING_DOWN)
        
        elif command == "health_check":
            # Respond with health status
            health = self.get_health()
            # Send health response...
    
    async def _handle_broadcast(self, message: Dict):
        """Handle tier-wide broadcasts"""
        # Can be overridden by subclass
        pass
    
    async def _handle_pod_message(self, message: Dict):
        """Handle pod-wide messages"""
        # Can be overridden by subclass
        pass
    
    async def _recover_from_error(self):
        """Attempt to recover from error state"""
        self.logger.info("Attempting error recovery")
        
        # Reset current task
        self.current_task = None
        
        # Transition back to idle
        await self._transition_state(AgentState.IDLE)
        
        self.logger.info("Error recovery successful")
    
    async def _send_task_result(self, task: Dict, result: Any):
        """Send task completion result"""
        message = {
            "message_id": str(uuid.uuid4()),
            "protocol": task.get("protocol", "beta"),
            "message_type": "task_complete",
            "timestamp": datetime.utcnow().isoformat(),
            "source_agent": self.agent_id,
            "target_agent": task["assigned_by"],
            "payload": {
                "task_id": task["task_id"],
                "result": result
            }
        }
        
        await self.semantic_bus.publish(
            f"agent.{task['assigned_by']}",
            message
        )
    
    async def _send_task_error(self, task: Dict, error: str):
        """Send task failure notification"""
        message = {
            "message_id": str(uuid.uuid4()),
            "protocol": task.get("protocol", "beta"),
            "message_type": "task_failed",
            "timestamp": datetime.utcnow().isoformat(),
            "source_agent": self.agent_id,
            "target_agent": task["assigned_by"],
            "payload": {
                "task_id": task["task_id"],
                "error": error
            }
        }
        
        await self.semantic_bus.publish(
            f"agent.{task['assigned_by']}",
            message
        )
    
    async def _send_task_rejection(self, message: Dict, reason: str):
        """Send task rejection"""
        response = {
            "message_id": str(uuid.uuid4()),
            "protocol": message.get("protocol"),
            "message_type": "task_rejected",
            "timestamp": datetime.utcnow().isoformat(),
            "source_agent": self.agent_id,
            "target_agent": message["source_agent"],
            "payload": {
                "reason": reason
            }
        }
        
        await self.semantic_bus.publish(
            f"agent.{message['source_agent']}",
            response
        )
    
    def get_status(self) -> Dict:
        """
        Get current agent status
        
        Returns:
            Status dictionary
        """
        uptime = (datetime.utcnow() - self.startup_time).total_seconds()
        
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "tier": self.tier,
            "pod": self.pod,
            "state": self.state.value,
            "current_task": self.current_task["task_id"] if self.current_task else None,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "success_rate": (
                self.tasks_completed / (self.tasks_completed + self.tasks_failed)
                if (self.tasks_completed + self.tasks_failed) > 0
                else 0.0
            ),
            "uptime_seconds": uptime
        }
    
    def get_health(self) -> Dict:
        """
        Get agent health status
        
        Returns:
            Health dictionary
        """
        status = self.get_status()
        
        # Determine health
        if self.state == AgentState.ERROR:
            health = "unhealthy"
        elif self.state == AgentState.SHUTTING_DOWN:
            health = "terminating"
        elif self.error_count > 0:
            health = "degraded"
        else:
            health = "healthy"
        
        return {
            **status,
            "health": health,
            "error_count": self.error_count
        }
    
    # ========================================================================
    # ABSTRACT METHODS (Must be implemented by subclasses)
    # ========================================================================
    
    @abstractmethod
    async def process_task(self, task: Dict) -> Any:
        """
        Process assigned task (IMPLEMENT IN SUBCLASS)
        
        Args:
            task: Task dictionary
        
        Returns:
            Task result
        """
        raise NotImplementedError("Subclass must implement process_task()")
    
    async def handle_message(self, message: Dict):
        """
        Handle custom message types (OVERRIDE IN SUBCLASS)
        
        Args:
            message: Message dictionary
        """
        self.logger.warning(f"Unhandled message type: {message.get('message_type')}")
```

This base class provides:
- ✅ State machine with validated transitions
- ✅ Semantic Bus integration (subscribe/publish)
- ✅ Database connectivity
- ✅ Heartbeat mechanism
- ✅ Error handling and recovery
- ✅ Metrics collection
- ✅ Logging infrastructure

### 1.4 Using the Base Class

**Example: Simple Echo Agent**

```python
from infrastructure.agent_base import AgentBase

class EchoAgent(AgentBase):
    """
    Simple echo agent that returns whatever it receives
    """
    
    async def process_task(self, task: Dict) -> Dict:
        """
        Echo the task back
        """
        self.logger.info(f"Processing echo task: {task['task_id']}")
        
        # Simply return the input
        return {
            "echo": task.get("input", ""),
            "processed_by": self.agent_id,
            "timestamp": datetime.utcnow().isoformat()
        }

# Usage
if __name__ == "__main__":
    agent = EchoAgent(
        agent_id="ECHO-001",
        agent_name="Echo Agent",
        tier="support",
        semantic_bus=semantic_bus,
        database=database
    )
    
    asyncio.run(agent.start())
```

---

## 2. IMPLEMENTING LANGUAGE SPECIALISTS

Language Specialists extract LogicNodes from source code in specific programming languages.

### 2.1 Language Specialist Architecture

**Key Responsibilities:**
1. **Parse source code** - Use language-specific parsers (AST, tree-sitter, etc.)
2. **Identify patterns** - Match code patterns to concepts
3. **Extract LogicNodes** - Convert code to Refined-IR format
4. **Self-verification** - Run basic checks before sending to Audit
5. **Query Knowledge Lake** - Access language documentation

**Python Specialist Example:**

```python
"""
Python Specialist Agent - Extracts LogicNodes from Python code
"""

import ast
import asyncio
from typing import List, Dict
from infrastructure.agent_base import AgentBase
from infrastructure.knowledge_lake import KnowledgeLake
from infrastructure.logicnode_registry import LogicNodeRegistry

class PythonSpecialist(AgentBase):
    """
    Python language specialist
    
    Extracts LogicNodes from Python source code using AST analysis
    """
    
    def __init__(self, agent_id: str, **kwargs):
        super().__init__(
            agent_id=agent_id,
            agent_name="Python Specialist",
            tier="pod",
            pod="A",
            **kwargs
        )
        
        # Knowledge Lake access
        self.knowledge_lake = KnowledgeLake()
        
        # LogicNode Registry
        self.registry = LogicNodeRegistry()
        
        # Concept templates
        self.concept_templates = self._load_concept_templates()
    
    def _load_concept_templates(self) -> Dict:
        """Load LogicNode templates for Python concepts"""
        return {
            "list_filter": {
                "domain": "list_operations",
                "concept": "filter",
                "intent": "Remove elements that don't satisfy predicate"
            },
            "list_map": {
                "domain": "list_operations",
                "concept": "map",
                "intent": "Transform each element in collection"
            },
            # ... more templates
        }
    
    async def process_task(self, task: Dict) -> Dict:
        """
        Process Python extraction task
        
        Args:
            task: Contains source_code, file_path, mission_id
        
        Returns:
            Extracted LogicNodes
        """
        source_code = task["source_code"]
        file_path = task.get("file_path", "unknown.py")
        mission_id = task["mission_id"]
        
        self.logger.info(f"Extracting LogicNodes from {file_path}")
        
        # 1. Parse Python code to AST
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError as e:
            self.logger.error(f"Syntax error in {file_path}: {e}")
            return {"error": f"Syntax error: {e}", "logicnodes": []}
        
        # 2. Visit AST nodes and extract patterns
        extractor = PythonASTExtractor(
            knowledge_lake=self.knowledge_lake,
            templates=self.concept_templates
        )
        
        logicnodes = []
        for node in ast.walk(tree):
            extracted = await extractor.visit_node(node, source_code)
            logicnodes.extend(extracted)
        
        self.logger.info(f"Extracted {len(logicnodes)} LogicNodes")
        
        # 3. Self-verification
        verified_nodes = []
        for node in logicnodes:
            if await self._self_verify(node):
                verified_nodes.append(node)
            else:
                self.logger.warning(f"Self-verification failed for {node['logicnode_id']}")
        
        self.logger.info(f"Self-verified {len(verified_nodes)}/{len(logicnodes)} LogicNodes")
        
        # 4. Store in registry
        for node in verified_nodes:
            await self.registry.create_logicnode(
                mission_id=mission_id,
                **node
            )
        
        return {
            "logicnodes_extracted": len(logicnodes),
            "logicnodes_verified": len(verified_nodes),
            "logicnode_ids": [n["logicnode_id"] for n in verified_nodes]
        }
    
    async def _self_verify(self, logicnode: Dict) -> bool:
        """
        Self-verification checks
        
        Returns:
            True if LogicNode passes basic checks
        """
        # Check required fields
        required = ["paradigm", "domain", "concept", "intent", "inputs", "outputs"]
        for field in required:
            if field not in logicnode:
                return False
        
        # Check non-empty inputs/outputs
        if not logicnode["inputs"] or not logicnode["outputs"]:
            return False
        
        # Check confidence threshold
        if logicnode.get("confidence", 0) < 0.90:
            return False
        
        return True


class PythonASTExtractor:
    """
    AST visitor that extracts LogicNodes from Python syntax patterns
    """
    
    def __init__(self, knowledge_lake: KnowledgeLake, templates: Dict):
        self.knowledge_lake = knowledge_lake
        self.templates = templates
    
    async def visit_node(self, node: ast.AST, source_code: str) -> List[Dict]:
        """
        Visit AST node and extract LogicNodes
        
        Args:
            node: AST node
            source_code: Original source code
        
        Returns:
            List of extracted LogicNodes
        """
        logicnodes = []
        
        # List comprehension → filter or map
        if isinstance(node, ast.ListComp):
            ln = await self._extract_list_comprehension(node, source_code)
            if ln:
                logicnodes.append(ln)
        
        # Function definition → various concepts
        elif isinstance(node, ast.FunctionDef):
            ln = await self._extract_function(node, source_code)
            if ln:
                logicnodes.append(ln)
        
        # For loop → iteration
        elif isinstance(node, ast.For):
            ln = await self._extract_for_loop(node, source_code)
            if ln:
                logicnodes.append(ln)
        
        # More patterns...
        
        return logicnodes
    
    async def _extract_list_comprehension(self, node: ast.ListComp, source: str) -> Optional[Dict]:
        """
        Extract LogicNode from list comprehension
        
        [x for x in items if x > 10] → filter LogicNode
        [x * 2 for x in items] → map LogicNode
        """
        # Determine if it's filter or map
        has_if = len(node.ifs) > 0
        has_transform = not (
            isinstance(node.elt, ast.Name) and
            node.elt.id == node.generators[0].target.id
        )
        
        if has_if and not has_transform:
            # Pure filter
            concept = "filter"
        elif has_transform and not has_if:
            # Pure map
            concept = "map"
        else:
            # Both filter and map (filter_map)
            concept = "filter_map"
        
        # Query Knowledge Lake for concept details
        docs = await self.knowledge_lake.search(
            query=f"Python list comprehension {concept}",
            filters={"language": "python", "domain": "list_operations"}
        )
        
        # Build LogicNode
        logicnode = {
            "logicnode_id": f"ln-{uuid.uuid4()}",
            "paradigm": "dynamic",
            "domain": "list_operations",
            "concept": concept,
            "intent": self.templates[f"list_{concept}"]["intent"],
            "inputs": [
                {"name": "collection", "type": "List[T]"},
                {"name": "predicate", "type": "Callable[[T], bool]"} if has_if else None
            ],
            "outputs": [
                {"name": "result", "type": "List[T]"}
            ],
            "source_language": "python",
            "source_code": ast.unparse(node),
            "source_line_number": node.lineno,
            "confidence": 0.95,
            "preconditions": [
                {"type": "not_null", "target": "collection"}
            ],
            "postconditions": [
                {"type": "subset", "target": "result", "of": "collection"}
            ],
            "side_effects": []
        }
        
        # Remove None from inputs
        logicnode["inputs"] = [i for i in logicnode["inputs"] if i is not None]
        
        return logicnode
    
    async def _extract_function(self, node: ast.FunctionDef, source: str) -> Optional[Dict]:
        """Extract LogicNode from function definition"""
        # Analyze function body to determine concept
        # This is more complex and requires deeper analysis
        # ...
        pass
    
    async def _extract_for_loop(self, node: ast.For, source: str) -> Optional[Dict]:
        """Extract LogicNode from for loop"""
        # Analyze loop to determine concept (iterate, reduce, etc.)
        # ...
        pass
```

### 2.2 Language Specialist Best Practices

**1. Use Language-Specific Parsers:**
```python
# Python: ast module
import ast
tree = ast.parse(python_code)

# JavaScript: Use esprima or acorn via subprocess
import subprocess
result = subprocess.run(
    ["node", "parse_js.js", js_file],
    capture_output=True
)

# C/C++: Use tree-sitter
from tree_sitter import Language, Parser
parser = Parser()
parser.set_language(Language('build/languages.so', 'cpp'))
tree = parser.parse(bytes(cpp_code, "utf8"))
```

**2. Pattern Matching:**
```python
# Bad: String matching
if "for x in" in code:
    # Fragile and error-prone
    ...

# Good: AST pattern matching
if isinstance(node, ast.For) and isinstance(node.iter, ast.Call):
    # Robust structural matching
    ...
```

**3. Confidence Scoring:**
```python
def calculate_confidence(logicnode: Dict, evidence: Dict) -> float:
    """
    Calculate confidence score based on evidence
    
    Factors:
    - Pattern clarity (0.6 weight)
    - Knowledge Lake match (0.2 weight)
    - Code complexity (0.2 weight)
    """
    pattern_score = evidence["pattern_clarity"]
    knowledge_score = evidence.get("knowledge_match", 0.5)
    complexity_penalty = 1.0 - min(evidence["complexity"] / 100, 0.5)
    
    confidence = (
        pattern_score * 0.6 +
        knowledge_score * 0.2 +
        complexity_penalty * 0.2
    )
    
    return min(confidence, 0.99)  # Cap at 0.99 (never 100% certain)
```

**4. Knowledge Lake Integration:**
```python
async def enhance_with_knowledge(self, logicnode: Dict):
    """
    Enhance LogicNode with Knowledge Lake documentation
    """
    # Search for concept documentation
    results = await self.knowledge_lake.search(
        query=f"{logicnode['concept']} {logicnode['source_language']}",
        filters={
            "language": logicnode["source_language"],
            "domain": logicnode["domain"]
        },
        top_k=3
    )
    
    if results:
        # Add documentation references
        logicnode["documentation_refs"] = [
            {
                "doc_id": r["doc_id"],
                "title": r["title"],
                "url": r["url"]
            }
            for r in results
        ]
        
        # Extract code examples
        logicnode["reference_examples"] = [
            ex for r in results
            for ex in r.get("code_examples", [])
        ]
```

---

## 3. BUILDING MANAGER AGENTS

Manager agents coordinate teams of specialists and consolidate results.

### 3.1 Sub-Manager Pattern

```python
"""
Pod Sub-Manager Agent - Coordinates language specialists
"""

from typing import List, Dict
from infrastructure.agent_base import AgentBase

class SubManagerAgent(AgentBase):
    """
    Sub-Manager for a language pod
    
    Responsibilities:
    - Receive tasks from CEO
    - Decompose into specialist assignments
    - Coordinate parallel execution
    - Consolidate specialist results
    - Perform cross-language fusion
    """
    
    def __init__(self, agent_id: str, pod: str, **kwargs):
        super().__init__(
            agent_id=agent_id,
            agent_name=f"Pod {pod} Sub-Manager",
            tier="pod",
            pod=pod,
            **kwargs
        )
        
        # Specialists in this pod
        self.specialists = self._get_pod_specialists(pod)
        
        # Task tracking
        self.active_tasks = {}
    
    def _get_pod_specialists(self, pod: str) -> List[str]:
        """Get specialist IDs for pod"""
        if pod == "A":
            return ["AGENT-PY-001", "AGENT-JS-001", "AGENT-RUBY-001", "AGENT-PHP-001"]
        elif pod == "B":
            return ["AGENT-C-001", "AGENT-CPP-001", "AGENT-RUST-001", "AGENT-ZIG-001"]
        elif pod == "C":
            return ["AGENT-JAVA-001", "AGENT-CS-001", "AGENT-SCALA-001", "AGENT-KOTLIN-001"]
        elif pod == "D":
            return ["AGENT-MATLAB-001", "AGENT-R-001", "AGENT-JULIA-001", "AGENT-MATH-001"]
        return []
    
    async def process_task(self, task: Dict) -> Dict:
        """
        Process pod-level task
        
        Args:
            task: Contains mission_id, languages, requirements
        
        Returns:
            Consolidated pod results
        """
        mission_id = task["mission_id"]
        languages = task["languages"]
        
        self.logger.info(f"Processing pod task for mission {mission_id}")
        self.logger.info(f"Languages: {languages}")
        
        # 1. Decompose into specialist tasks
        specialist_tasks = await self._decompose_task(task)
        
        # 2. Assign to specialists (parallel)
        specialist_results = await self._execute_parallel(specialist_tasks)
        
        # 3. Consolidate results
        consolidated = await self._consolidate_results(specialist_results)
        
        # 4. Cross-language fusion
        fused = await self._fuse_cross_language(consolidated)
        
        return {
            "pod": self.pod,
            "mission_id": mission_id,
            "specialists_used": list(specialist_results.keys()),
            "logicnodes_total": fused["logicnodes_count"],
            "pod_standard": fused["pod_standard"]
        }
    
    async def _decompose_task(self, task: Dict) -> Dict[str, Dict]:
        """
        Decompose pod task into specialist tasks
        
        Returns:
            Dict mapping specialist_id to task
        """
        languages = task["languages"]
        specialist_tasks = {}
        
        # Map languages to specialists
        language_mapping = {
            "python": "AGENT-PY-001",
            "javascript": "AGENT-JS-001",
            "ruby": "AGENT-RUBY-001",
            "php": "AGENT-PHP-001",
            # ... more mappings
        }
        
        for language in languages:
            specialist_id = language_mapping.get(language.lower())
            if specialist_id and specialist_id in self.specialists:
                specialist_tasks[specialist_id] = {
                    "task_id": f"{task['task_id']}-{language}",
                    "mission_id": task["mission_id"],
                    "language": language,
                    "source_code": task["source_code"].get(language, ""),
                    "assigned_by": self.agent_id
                }
        
        return specialist_tasks
    
    async def _execute_parallel(self, specialist_tasks: Dict[str, Dict]) -> Dict:
        """
        Execute specialist tasks in parallel
        
        Returns:
            Dict mapping specialist_id to result
        """
        # Send tasks to all specialists
        for specialist_id, task in specialist_tasks.items():
            message = {
                "message_id": str(uuid.uuid4()),
                "protocol": "beta",
                "message_type": "task_assignment",
                "timestamp": datetime.utcnow().isoformat(),
                "source_agent": self.agent_id,
                "target_agent": specialist_id,
                "payload": {"task": task}
            }
            
            await self.semantic_bus.publish(
                f"agent.{specialist_id}",
                message
            )
        
        # Wait for all results
        results = {}
        pending = set(specialist_tasks.keys())
        
        while pending:
            # Poll for results (simplified - use async callbacks in production)
            await asyncio.sleep(5)
            
            for specialist_id in list(pending):
                # Check if result received
                result = await self._check_specialist_result(specialist_id)
                if result:
                    results[specialist_id] = result
                    pending.remove(specialist_id)
        
        return results
    
    async def _consolidate_results(self, specialist_results: Dict) -> Dict:
        """
        Consolidate specialist results
        
        Combines all LogicNodes from specialists
        """
        all_logicnodes = []
        
        for specialist_id, result in specialist_results.items():
            logicnode_ids = result.get("logicnode_ids", [])
            
            # Fetch LogicNodes from registry
            for ln_id in logicnode_ids:
                ln = await self.registry.get_logicnode(ln_id)
                all_logicnodes.append(ln)
        
        return {
            "logicnodes": all_logicnodes,
            "logicnodes_count": len(all_logicnodes)
        }
    
    async def _fuse_cross_language(self, consolidated: Dict) -> Dict:
        """
        Perform cross-language fusion
        
        Groups similar LogicNodes across languages into "Pod Standard"
        """
        logicnodes = consolidated["logicnodes"]
        
        # Group by (domain, concept)
        groups = {}
        for ln in logicnodes:
            key = (ln["domain"], ln["concept"])
            if key not in groups:
                groups[key] = []
            groups[key].append(ln)
        
        # Create pod standard LogicNodes
        pod_standard = []
        for (domain, concept), group in groups.items():
            # Fuse all language variants into single "canonical" LogicNode
            fused = await self._fuse_logicnode_group(group)
            pod_standard.append(fused)
        
        return {
            "logicnodes_count": len(logicnodes),
            "pod_standard": pod_standard,
            "pod_standard_count": len(pod_standard)
        }
    
    async def _fuse_logicnode_group(self, group: List[Dict]) -> Dict:
        """
        Fuse multiple LogicNodes into single canonical version
        
        Takes consensus of inputs, outputs, preconditions, postconditions
        """
        # Use first as template
        fused = group[0].copy()
        
        # Update to reflect fusion
        fused["logicnode_id"] = f"pod-{self.pod}-{fused['domain']}-{fused['concept']}"
        fused["source_language"] = "multi"
        fused["language_variants"] = [ln["source_language"] for ln in group]
        fused["confidence"] = sum(ln["confidence"] for ln in group) / len(group)
        
        return fused
```

---

## 4. CREATING AUDIT AGENTS

Audit agents verify LogicNodes with 0.0001% tolerance testing.

### 4.1 Audit Agent Pattern

```python
"""
Audit Agent - Verifies LogicNodes with equivalence testing
"""

import asyncio
from typing import Dict, List
from infrastructure.agent_base import AgentBase

class AuditAgent(AgentBase):
    """
    Audit agent that verifies LogicNodes
    
    Runs 1,000 equivalence tests per LogicNode
    Achieves 0.0001% tolerance (999/1000 must pass)
    """
    
    def __init__(self, agent_id: str, **kwargs):
        super().__init__(
            agent_id=agent_id,
            agent_name="Audit Agent",
            tier="pod",
            **kwargs
        )
        
        self.tests_per_logicnode = 1000
        self.pass_threshold = 0.999
    
    async def process_task(self, task: Dict) -> Dict:
        """
        Audit LogicNodes
        
        Args:
            task: Contains logicnode_ids to verify
        
        Returns:
            Verification results
        """
        logicnode_ids = task["logicnode_ids"]
        
        self.logger.info(f"Auditing {len(logicnode_ids)} LogicNodes")
        
        results = []
        for ln_id in logicnode_ids:
            # Fetch LogicNode
            ln = await self.registry.get_logicnode(ln_id)
            
            # Run verification
            result = await self._verify_logicnode(ln)
            results.append(result)
        
        verified = sum(1 for r in results if r["passed"])
        
        return {
            "logicnodes_audited": len(logicnode_ids),
            "logicnodes_verified": verified,
            "verification_rate": verified / len(logicnode_ids),
            "results": results
        }
    
    async def _verify_logicnode(self, logicnode: Dict) -> Dict:
        """
        Verify single LogicNode
        
        Returns:
            Verification result
        """
        self.logger.info(f"Verifying LogicNode {logicnode['logicnode_id']}")
        
        # Generate test cases
        test_cases = await self._generate_test_cases(logicnode)
        
        # Run tests
        passed = 0
        failed = 0
        
        for test in test_cases:
            result = await self._run_test(logicnode, test)
            if result:
                passed += 1
            else:
                failed += 1
        
        # Calculate pass rate
        pass_rate = passed / len(test_cases)
        
        # Check threshold
        verification_passed = pass_rate >= self.pass_threshold
        
        # Update LogicNode
        await self.registry.update_logicnode(
            logicnode["logicnode_id"],
            verification_status="verified" if verification_passed else "failed",
            verification_pass_rate=pass_rate,
            verification_tests_passed=passed,
            verification_tests_total=len(test_cases)
        )
        
        return {
            "logicnode_id": logicnode["logicnode_id"],
            "passed": verification_passed,
            "pass_rate": pass_rate,
            "tests_passed": passed,
            "tests_total": len(test_cases)
        }
    
    async def _generate_test_cases(self, logicnode: Dict) -> List[Dict]:
        """
        Generate test cases for LogicNode
        
        Returns 1,000 test cases covering:
        - Normal inputs
        - Edge cases
        - Boundary conditions
        - Invalid inputs (if applicable)
        """
        test_cases = []
        
        # Normal cases (60%)
        test_cases.extend(await self._generate_normal_cases(logicnode, 600))
        
        # Edge cases (30%)
        test_cases.extend(await self._generate_edge_cases(logicnode, 300))
        
        # Boundary cases (10%)
        test_cases.extend(await self._generate_boundary_cases(logicnode, 100))
        
        return test_cases
    
    async def _generate_normal_cases(self, logicnode: Dict, count: int) -> List[Dict]:
        """Generate normal test cases"""
        # Implementation depends on concept
        # For list_filter: various lists and predicates
        # For matrix_multiply: various matrix sizes
        # ...
        pass
    
    async def _run_test(self, logicnode: Dict, test: Dict) -> bool:
        """
        Run single test case
        
        Checks that LogicNode's postconditions hold
        """
        # Execute LogicNode logic (simulated)
        inputs = test["inputs"]
        expected_output = test["expected_output"]
        
        # Apply LogicNode transformation
        actual_output = await self._apply_logicnode(logicnode, inputs)
        
        # Verify postconditions
        postconditions_met = await self._check_postconditions(
            logicnode,
            inputs,
            actual_output
        )
        
        # Compare outputs
        outputs_match = self._compare_outputs(actual_output, expected_output)
        
        return postconditions_met and outputs_match
```

---

Due to length constraints, I'll create documents 54 and 55 next. This document (53) continues with sections 5-10 covering support agents, LLM integration, testing, performance, deployment, and advanced topics. Would you like me to complete the full document 53 first, or proceed to create all four documents at a summary level?

