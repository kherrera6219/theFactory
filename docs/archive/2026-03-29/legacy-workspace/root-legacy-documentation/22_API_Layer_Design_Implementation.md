# DOCUMENT 22: API LAYER DESIGN & IMPLEMENTATION
## Holy Grail Refinery - Development Specifications

**Document ID:** 22  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

The Holy Grail Refinery exposes a **unified RESTful API** for external clients to interact with the 35-agent system. The API layer provides authentication, rate limiting, request routing, and aggregation of responses from multiple agents. This document specifies the complete API design, implementation patterns, and integration guidelines.

**API Architecture:**
- **Gateway Layer:** Single entry point with authentication and routing
- **Agent API Endpoints:** Individual agent capabilities exposed via HTTP
- **Aggregation Layer:** Combine responses from multiple agents
- **WebSocket Channels:** Real-time updates and streaming responses
- **GraphQL Interface:** Flexible querying for complex data relationships

---

## TABLE OF CONTENTS

1. [API Architecture Overview](#1-api-architecture-overview)
2. [Authentication & Authorization](#2-authentication--authorization)
3. [RESTful API Endpoints](#3-restful-api-endpoints)
4. [WebSocket Streaming API](#4-websocket-streaming-api)
5. [GraphQL Schema](#5-graphql-schema)
6. [Rate Limiting & Throttling](#6-rate-limiting--throttling)
7. [Error Handling](#7-error-handling)
8. [API Documentation](#8-api-documentation)
9. [Client SDK Examples](#9-client-sdk-examples)
10. [Deployment & Scaling](#10-deployment--scaling)

---

## 1. API ARCHITECTURE OVERVIEW

### 1.1 Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL CLIENTS                          │
│              (Web UI, CLI, Third-party Apps)                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                     API GATEWAY                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Authentication│  │ Rate Limiting│  │   Routing    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   REST API   │ │  WebSocket   │ │   GraphQL    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  AGENT ORCHESTRATION LAYER                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   CEO    │  │  Manager │  │Specialist│  │  Support │   │
│  │  Agent   │  │  Agents  │  │  Agents  │  │  Agents  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    SEMANTIC BUS (Redis)                      │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Gateway** | Kong / Nginx | Request routing, load balancing |
| **REST Framework** | FastAPI (Python) | High-performance async API |
| **WebSocket** | FastAPI WebSocket | Real-time streaming |
| **GraphQL** | Strawberry GraphQL | Flexible querying |
| **Authentication** | JWT + OAuth2 | Secure access control |
| **Rate Limiting** | Redis | Token bucket algorithm |
| **Documentation** | OpenAPI 3.1 / Swagger | Auto-generated docs |
| **Monitoring** | Prometheus + Grafana | Metrics and dashboards |

### 1.3 API Design Principles

1. **RESTful:** Standard HTTP methods (GET, POST, PUT, DELETE)
2. **Versioned:** `/api/v1/` prefix for backward compatibility
3. **Paginated:** Large result sets use cursor-based pagination
4. **Filtered:** Query parameters for filtering and sorting
5. **Documented:** OpenAPI spec with examples
6. **Secure:** All endpoints require authentication
7. **Idempotent:** Safe retry behavior for mutations

---

## 2. AUTHENTICATION & AUTHORIZATION

### 2.1 JWT-Based Authentication

**File:** `api/auth/jwt_handler.py`

```python
"""
JWT authentication for API access
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


class JWTHandler:
    """Manage JWT tokens"""
    
    @staticmethod
    def create_access_token(user_id: str, scopes: list[str]) -> str:
        """
        Create JWT access token
        
        Args:
            user_id: Unique user identifier
            scopes: List of permission scopes (e.g., ['read:logicnodes', 'write:tasks'])
        """
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "scopes": scopes,
            "type": "access"
        }
        
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return token
    
    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """Create long-lived refresh token"""
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }
        
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return token
    
    @staticmethod
    def verify_token(token: str) -> dict:
        """
        Verify and decode JWT token
        
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
            
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)


# Dependency for protected endpoints
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get current authenticated user
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"user_id": user["sub"]}
    """
    token = credentials.credentials
    payload = JWTHandler.verify_token(token)
    
    # Verify token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    return payload


# Scope-based authorization
class RequireScopes:
    """Dependency to require specific scopes"""
    
    def __init__(self, required_scopes: list[str]):
        self.required_scopes = required_scopes
    
    def __call__(self, user: dict = Depends(get_current_user)) -> dict:
        user_scopes = user.get("scopes", [])
        
        for scope in self.required_scopes:
            if scope not in user_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required scope: {scope}"
                )
        
        return user
```

### 2.2 OAuth2 Login Flow

```python
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return JWT tokens
    
    Scopes assigned based on user role:
    - Admin: all scopes
    - Developer: read/write logicnodes, tasks
    - Viewer: read-only
    """
    # Verify credentials (check against database)
    user = authenticate_user(request.username, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Determine scopes based on user role
    scopes = get_user_scopes(user.role)
    
    # Generate tokens
    access_token = JWTHandler.create_access_token(user.id, scopes)
    refresh_token = JWTHandler.create_refresh_token(user.id)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """Exchange refresh token for new access token"""
    payload = JWTHandler.verify_token(refresh_token)
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    user_id = payload["sub"]
    user = get_user_by_id(user_id)
    scopes = get_user_scopes(user.role)
    
    access_token = JWTHandler.create_access_token(user_id, scopes)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token  # Reuse same refresh token
    )
```

### 2.3 Permission Scopes

| Scope | Description | Typical Role |
|-------|-------------|--------------|
| `read:logicnodes` | View LogicNodes | Viewer, Developer, Admin |
| `write:logicnodes` | Create/update LogicNodes | Developer, Admin |
| `delete:logicnodes` | Delete LogicNodes | Admin |
| `read:tasks` | View tasks | Viewer, Developer, Admin |
| `write:tasks` | Create/assign tasks | Developer, Admin |
| `read:agents` | View agent status | Viewer, Developer, Admin |
| `control:agents` | Start/stop agents | Admin |
| `read:audit` | View audit logs | Developer, Admin |
| `admin:all` | Full system access | Admin |

---

## 3. RESTFUL API ENDPOINTS

### 3.1 FastAPI Application Structure

**File:** `api/main.py`

```python
"""
Main FastAPI application
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from api.routers import (
    auth_router,
    logicnodes_router,
    tasks_router,
    agents_router,
    workflows_router,
    health_router
)
from api.middleware import rate_limit_middleware

# Initialize FastAPI app
app = FastAPI(
    title="Holy Grail Refinery API",
    version="1.0.0",
    description="Unified API for 35-agent code refinement system",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Custom middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logging.info(
        f"{request.method} {request.url.path} - "
        f"{response.status_code} - {process_time:.3f}s"
    )
    
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Include routers
app.include_router(auth_router)
app.include_router(logicnodes_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(workflows_router, prefix="/api/v1")
app.include_router(health_router)

# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if app.debug else "An unexpected error occurred"
        }
    )


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": "Holy Grail Refinery API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "status": "operational"
    }
```

### 3.2 LogicNodes API

**File:** `api/routers/logicnodes.py`

```python
"""
LogicNodes CRUD API
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Optional, List
from pydantic import BaseModel

from api.auth.jwt_handler import RequireScopes
from database.models.logicnode import LogicNode
from database.connection import get_logicnode_session

router = APIRouter(prefix="/logicnodes", tags=["LogicNodes"])


class LogicNodeCreate(BaseModel):
    source_file: str
    source_language: str
    domain: str
    concept: str
    intent: str
    inputs: list
    outputs: list
    preconditions: Optional[list] = []
    postconditions: Optional[list] = []
    side_effects: Optional[list] = []


class LogicNodeResponse(BaseModel):
    logicnode_id: str
    source_language: str
    domain: str
    concept: str
    intent: str
    inputs: list
    outputs: list
    verification_status: str
    created_at: str
    
    class Config:
        orm_mode = True


@router.get("/", response_model=List[LogicNodeResponse])
async def list_logicnodes(
    language: Optional[str] = None,
    domain: Optional[str] = None,
    verified_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user: dict = Depends(RequireScopes(["read:logicnodes"])),
    db = Depends(get_logicnode_session)
):
    """
    List LogicNodes with optional filtering
    
    Query Parameters:
    - language: Filter by source language
    - domain: Filter by semantic domain
    - verified_only: Only return verified LogicNodes
    - skip: Pagination offset
    - limit: Max results (1-1000)
    """
    query = db.query(LogicNode)
    
    if language:
        query = query.filter(LogicNode.source_language == language)
    if domain:
        query = query.filter(LogicNode.domain == domain)
    if verified_only:
        query = query.filter(LogicNode.verification_status == "verified")
    
    total = query.count()
    results = query.offset(skip).limit(limit).all()
    
    return results


@router.get("/{logicnode_id}", response_model=LogicNodeResponse)
async def get_logicnode(
    logicnode_id: str,
    user: dict = Depends(RequireScopes(["read:logicnodes"])),
    db = Depends(get_logicnode_session)
):
    """Get LogicNode by ID"""
    logicnode = db.query(LogicNode).filter(
        LogicNode.logicnode_id == logicnode_id
    ).first()
    
    if not logicnode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LogicNode {logicnode_id} not found"
        )
    
    return logicnode


@router.post("/", response_model=LogicNodeResponse, status_code=status.HTTP_201_CREATED)
async def create_logicnode(
    data: LogicNodeCreate,
    user: dict = Depends(RequireScopes(["write:logicnodes"])),
    db = Depends(get_logicnode_session)
):
    """Create new LogicNode"""
    import uuid
    
    logicnode = LogicNode(
        logicnode_id=f"ln-{uuid.uuid4().hex[:12]}",
        extracted_by=user["sub"],
        **data.dict()
    )
    
    db.add(logicnode)
    db.commit()
    db.refresh(logicnode)
    
    return logicnode


@router.delete("/{logicnode_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_logicnode(
    logicnode_id: str,
    user: dict = Depends(RequireScopes(["delete:logicnodes"])),
    db = Depends(get_logicnode_session)
):
    """Delete LogicNode"""
    logicnode = db.query(LogicNode).filter(
        LogicNode.logicnode_id == logicnode_id
    ).first()
    
    if not logicnode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LogicNode {logicnode_id} not found"
        )
    
    db.delete(logicnode)
    db.commit()
    
    return None
```

### 3.3 Tasks API

**File:** `api/routers/tasks.py`

```python
"""
Tasks management API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from api.auth.jwt_handler import RequireScopes
from database.models.state import Task, Agent
from database.connection import get_state_session

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class TaskCreate(BaseModel):
    task_type: str
    assigned_to: str  # Agent ID
    priority: int = 3
    input_data: dict
    deadline: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    task_type: str
    assigned_to: str
    assigned_by: str
    priority: int
    status: str
    created_at: str
    deadline: Optional[str]
    
    class Config:
        orm_mode = True


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    user: dict = Depends(RequireScopes(["write:tasks"])),
    db = Depends(get_state_session)
):
    """
    Create and assign a new task
    
    Task will be sent to agent via Protocol Alpha (directive)
    """
    import uuid
    from semantic_bus.mcp_server import send_message
    
    # Verify agent exists
    agent = db.query(Agent).filter(Agent.agent_id == data.assigned_to).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {data.assigned_to} not found"
        )
    
    # Create task in database
    task = Task(
        task_id=f"task-{uuid.uuid4().hex[:12]}",
        assigned_by=user["sub"],
        **data.dict()
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Send task to agent via Semantic Bus (Protocol Alpha)
    send_message({
        "message_id": f"msg-{uuid.uuid4().hex[:8]}",
        "protocol": "alpha",
        "sender": "API",
        "recipient": data.assigned_to,
        "timestamp": datetime.utcnow().isoformat(),
        "payload": {
            "message_type": "assignment",
            "task_id": task.task_id,
            "priority": data.priority,
            "instructions": data.task_type,
            "deadline": data.deadline
        }
    })
    
    return task


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    status_filter: Optional[str] = None,
    assigned_to: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    user: dict = Depends(RequireScopes(["read:tasks"])),
    db = Depends(get_state_session)
):
    """List tasks with optional filtering"""
    query = db.query(Task)
    
    if status_filter:
        query = query.filter(Task.status == status_filter)
    if assigned_to:
        query = query.filter(Task.assigned_to == assigned_to)
    
    results = query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
    return results


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    user: dict = Depends(RequireScopes(["read:tasks"])),
    db = Depends(get_state_session)
):
    """Get task by ID"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    return task
```

### 3.4 Agents API

**File:** `api/routers/agents.py`

```python
"""
Agents status and control API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from pydantic import BaseModel

from api.auth.jwt_handler import RequireScopes
from database.models.state import Agent
from database.connection import get_state_session

router = APIRouter(prefix="/agents", tags=["Agents"])


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    tier: str
    pod: Optional[str]
    status: str
    current_task_id: Optional[str]
    heartbeat_at: Optional[str]
    
    class Config:
        orm_mode = True


@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    pod: Optional[str] = None,
    tier: Optional[str] = None,
    status_filter: Optional[str] = None,
    user: dict = Depends(RequireScopes(["read:agents"])),
    db = Depends(get_state_session)
):
    """
    List all agents with optional filtering
    
    Query Parameters:
    - pod: Filter by pod (A, B, C, D)
    - tier: Filter by tier (executive, support, pod)
    - status: Filter by status (idle, busy, error, offline)
    """
    query = db.query(Agent)
    
    if pod:
        query = query.filter(Agent.pod == pod)
    if tier:
        query = query.filter(Agent.tier == tier)
    if status_filter:
        query = query.filter(Agent.status == status_filter)
    
    agents = query.all()
    return agents


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    user: dict = Depends(RequireScopes(["read:agents"])),
    db = Depends(get_state_session)
):
    """Get agent details"""
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found"
        )
    
    return agent


@router.post("/{agent_id}/restart", status_code=status.HTTP_202_ACCEPTED)
async def restart_agent(
    agent_id: str,
    user: dict = Depends(RequireScopes(["control:agents"])),
    db = Depends(get_state_session)
):
    """
    Restart an agent container
    Requires admin privileges
    """
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found"
        )
    
    # Send restart command to Docker
    import docker
    client = docker.from_env()
    
    try:
        container = client.containers.get(f"hgr-{agent_id.lower()}")
        container.restart()
        
        return {
            "message": f"Agent {agent_id} restart initiated",
            "status": "restarting"
        }
    
    except docker.errors.NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container for agent {agent_id} not found"
        )
```

---

## 4. WEBSOCKET STREAMING API

### 4.1 Real-Time Task Updates

**File:** `api/websocket/task_stream.py`

```python
"""
WebSocket endpoint for real-time task updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Set
import json
import asyncio

from api.auth.jwt_handler import verify_token
from semantic_bus.redis_client import RedisClient

router = APIRouter()

# Active WebSocket connections
active_connections: Set[WebSocket] = set()


@router.websocket("/ws/tasks")
async def task_stream(websocket: WebSocket, token: str):
    """
    Stream task updates in real-time
    
    Usage:
        ws = new WebSocket('ws://localhost:8000/ws/tasks?token=<jwt_token>')
        ws.onmessage = (event) => {
            const task = JSON.parse(event.data)
            console.log('Task update:', task)
        }
    
    Message format:
        {
            "event": "task_created" | "task_updated" | "task_completed",
            "task_id": "task-abc123",
            "data": { ... task data ... }
        }
    """
    # Verify JWT token
    try:
        payload = verify_token(token)
        user_id = payload["sub"]
    except:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    # Accept connection
    await websocket.accept()
    active_connections.add(websocket)
    
    # Subscribe to task updates via Redis
    redis = RedisClient()
    
    def task_update_callback(channel, message):
        """Handle task updates from Redis"""
        asyncio.create_task(
            websocket.send_text(json.dumps(message))
        )
    
    try:
        # Listen for task updates
        redis.subscribe(["protocol:beta:tasks"], task_update_callback)
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Echo ping/pong for keepalive
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason="Internal error")
```

### 4.2 LogicNode Extraction Stream

```python
@router.websocket("/ws/extraction/{task_id}")
async def extraction_stream(websocket: WebSocket, task_id: str, token: str):
    """
    Stream LogicNode extraction progress
    
    Real-time updates as agents extract LogicNodes from source code
    """
    # Verify token
    try:
        verify_token(token)
    except:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    await websocket.accept()
    
    redis = RedisClient()
    
    # Subscribe to extraction events for this task
    channel = f"extraction:{task_id}"
    
    def extraction_callback(channel, message):
        """Send extraction updates to client"""
        asyncio.create_task(
            websocket.send_json({
                "event": message.get("event"),
                "logicnode_id": message.get("logicnode_id"),
                "progress": message.get("progress"),
                "total": message.get("total")
            })
        )
    
    try:
        redis.subscribe([channel], extraction_callback)
        
        while True:
            await asyncio.sleep(1)  # Keep connection alive
    
    except WebSocketDisconnect:
        pass
```

---

## 5. GRAPHQL SCHEMA

### 5.1 GraphQL Setup

**File:** `api/graphql/schema.py`

```python
"""
GraphQL schema for flexible querying
"""

import strawberry
from typing import List, Optional
from datetime import datetime

from database.models.logicnode import LogicNode as LogicNodeModel
from database.connection import get_logicnode_session


@strawberry.type
class LogicNode:
    logicnode_id: str
    source_language: str
    domain: str
    concept: str
    intent: str
    verification_status: str
    created_at: datetime


@strawberry.type
class Agent:
    agent_id: str
    name: str
    tier: str
    pod: Optional[str]
    status: str


@strawberry.type
class Task:
    task_id: str
    task_type: str
    assigned_to: str
    priority: int
    status: str


@strawberry.type
class Query:
    
    @strawberry.field
    def logicnodes(
        self,
        language: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 100
    ) -> List[LogicNode]:
        """Query LogicNodes with filtering"""
        db = next(get_logicnode_session())
        
        query = db.query(LogicNodeModel)
        
        if language:
            query = query.filter(LogicNodeModel.source_language == language)
        if domain:
            query = query.filter(LogicNodeModel.domain == domain)
        
        results = query.limit(limit).all()
        
        return [
            LogicNode(
                logicnode_id=ln.logicnode_id,
                source_language=ln.source_language,
                domain=ln.domain,
                concept=ln.concept,
                intent=ln.intent,
                verification_status=ln.verification_status,
                created_at=ln.created_at
            )
            for ln in results
        ]
    
    @strawberry.field
    def logicnode_by_id(self, logicnode_id: str) -> Optional[LogicNode]:
        """Get single LogicNode by ID"""
        db = next(get_logicnode_session())
        
        ln = db.query(LogicNodeModel).filter(
            LogicNodeModel.logicnode_id == logicnode_id
        ).first()
        
        if not ln:
            return None
        
        return LogicNode(
            logicnode_id=ln.logicnode_id,
            source_language=ln.source_language,
            domain=ln.domain,
            concept=ln.concept,
            intent=ln.intent,
            verification_status=ln.verification_status,
            created_at=ln.created_at
        )


schema = strawberry.Schema(query=Query)
```

### 5.2 GraphQL Endpoint

```python
from strawberry.fastapi import GraphQLRouter

graphql_app = GraphQLRouter(schema)

# Add to main app
app.include_router(graphql_app, prefix="/api/v1/graphql")
```

**Example Query:**

```graphql
query GetPythonLogicNodes {
  logicnodes(language: "python", domain: "control_flow", limit: 10) {
    logicnodeId
    concept
    intent
    verificationStatus
    createdAt
  }
}
```

---

## 6. RATE LIMITING & THROTTLING

### 6.1 Redis-Based Rate Limiter

**File:** `api/middleware/rate_limit.py`

```python
"""
Token bucket rate limiting using Redis
"""

from fastapi import HTTPException, status, Request
from semantic_bus.redis_client import RedisClient
import time


class RateLimiter:
    """
    Token bucket rate limiter
    
    Each user gets a bucket of tokens that refills over time
    Each request consumes 1 token
    """
    
    def __init__(
        self,
        redis: RedisClient,
        max_tokens: int = 100,
        refill_rate: float = 10.0  # tokens per second
    ):
        self.redis = redis
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
    
    def is_allowed(self, user_id: str) -> bool:
        """
        Check if request is allowed
        
        Returns:
            True if request allowed, False if rate limited
        """
        key = f"rate_limit:{user_id}"
        now = time.time()
        
        # Get current bucket state
        bucket_data = self.redis.client.get(key)
        
        if bucket_data:
            tokens, last_update = map(float, bucket_data.split(":"))
        else:
            tokens = self.max_tokens
            last_update = now
        
        # Refill tokens based on time elapsed
        time_elapsed = now - last_update
        tokens = min(
            self.max_tokens,
            tokens + (time_elapsed * self.refill_rate)
        )
        
        # Check if request allowed
        if tokens >= 1:
            tokens -= 1
            allowed = True
        else:
            allowed = False
        
        # Update bucket
        self.redis.client.setex(
            key,
            3600,  # Expire after 1 hour
            f"{tokens}:{now}"
        )
        
        return allowed


# Middleware
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all requests"""
    
    # Skip rate limiting for health checks
    if request.url.path == "/health":
        return await call_next(request)
    
    # Get user ID from JWT
    auth_header = request.headers.get("Authorization")
    if auth_header:
        token = auth_header.replace("Bearer ", "")
        try:
            from api.auth.jwt_handler import JWTHandler
            payload = JWTHandler.verify_token(token)
            user_id = payload["sub"]
        except:
            user_id = request.client.host
    else:
        user_id = request.client.host
    
    # Check rate limit
    redis = RedisClient()
    limiter = RateLimiter(redis)
    
    if not limiter.is_allowed(user_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"}
        )
    
    response = await call_next(request)
    return response
```

---

## 7. ERROR HANDLING

### 7.1 Standardized Error Responses

```python
from pydantic import BaseModel
from typing import Optional

class ErrorResponse(BaseModel):
    """Standard error response format"""
    error: str
    detail: str
    code: Optional[str] = None
    timestamp: str


# Example error responses
{
    "error": "Not Found",
    "detail": "LogicNode ln-abc123 not found",
    "code": "LOGICNODE_NOT_FOUND",
    "timestamp": "2026-02-05T10:30:00Z"
}

{
    "error": "Validation Error",
    "detail": "Invalid task priority. Must be 1-5.",
    "code": "VALIDATION_ERROR",
    "timestamp": "2026-02-05T10:30:00Z"
}
```

### 7.2 HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET request |
| 201 | Created | Successful POST (resource created) |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid input data |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |
| 503 | Service Unavailable | System overloaded or maintenance |

---

## 8. API DOCUMENTATION

### 8.1 OpenAPI Specification

FastAPI auto-generates OpenAPI 3.1 spec at `/api/openapi.json`

**Interactive docs available at:**
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

### 8.2 Example OpenAPI Snippet

```yaml
openapi: 3.1.0
info:
  title: Holy Grail Refinery API
  version: 1.0.0
  description: Unified API for 35-agent code refinement system

paths:
  /api/v1/logicnodes:
    get:
      summary: List LogicNodes
      tags:
        - LogicNodes
      parameters:
        - name: language
          in: query
          schema:
            type: string
          description: Filter by programming language
        - name: domain
          in: query
          schema:
            type: string
          description: Filter by semantic domain
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/LogicNodeResponse'
      security:
        - bearerAuth: []
```

---

## 9. CLIENT SDK EXAMPLES

### 9.1 Python SDK

**File:** `sdk/python/hgr_client.py`

```python
"""
Python SDK for Holy Grail Refinery API
"""

import requests
from typing import Optional, List, Dict

class HGRClient:
    """Client for Holy Grail Refinery API"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def list_logicnodes(
        self,
        language: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """List LogicNodes with filtering"""
        params = {"limit": limit}
        if language:
            params["language"] = language
        if domain:
            params["domain"] = domain
        
        response = requests.get(
            f"{self.base_url}/api/v1/logicnodes",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def create_task(
        self,
        task_type: str,
        assigned_to: str,
        input_data: Dict,
        priority: int = 3
    ) -> Dict:
        """Create a new task"""
        payload = {
            "task_type": task_type,
            "assigned_to": assigned_to,
            "input_data": input_data,
            "priority": priority
        }
        
        response = requests.post(
            f"{self.base_url}/api/v1/tasks",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()


# Usage example
client = HGRClient(
    base_url="http://localhost:8000",
    api_key="your_jwt_token"
)

# Get Python LogicNodes
logicnodes = client.list_logicnodes(language="python", limit=50)

# Create extraction task
task = client.create_task(
    task_type="extract_logicnodes",
    assigned_to="AGENT-PY-001",
    input_data={"repo_url": "https://github.com/example/repo"},
    priority=1
)
```

### 9.2 JavaScript/TypeScript SDK

```typescript
/**
 * TypeScript SDK for Holy Grail Refinery API
 */

interface LogicNode {
  logicnode_id: string;
  source_language: string;
  domain: string;
  concept: string;
  intent: string;
  verification_status: string;
}

interface Task {
  task_id: string;
  task_type: string;
  assigned_to: string;
  priority: number;
  status: string;
}

class HGRClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }

  async listLogicNodes(params?: {
    language?: string;
    domain?: string;
    limit?: number;
  }): Promise<LogicNode[]> {
    const query = new URLSearchParams(
      params as Record<string, string>
    ).toString();
    
    return this.request<LogicNode[]>(
      `/api/v1/logicnodes?${query}`
    );
  }

  async createTask(data: {
    task_type: string;
    assigned_to: string;
    input_data: Record<string, any>;
    priority?: number;
  }): Promise<Task> {
    return this.request<Task>('/api/v1/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
}

// Usage
const client = new HGRClient(
  'http://localhost:8000',
  'your_jwt_token'
);

const logicNodes = await client.listLogicNodes({
  language: 'python',
  limit: 50
});
```

---

## 10. DEPLOYMENT & SCALING

### 10.1 Docker Deployment

**File:** `docker-compose.yml` (API service)

```yaml
services:
  api-gateway:
    build:
      context: ./api
      dockerfile: Dockerfile
    container_name: hgr-api
    restart: unless-stopped
    
    ports:
      - "8000:8000"
    
    environment:
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - POSTGRES_HOST=postgres-main
      - REDIS_HOST=redis-semantic-bus
    
    depends_on:
      - postgres-main
      - redis-semantic-bus
    
    networks:
      - hgr-network
    
    deploy:
      replicas: 2  # Load balanced
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
```

### 10.2 Production Configuration

**Gunicorn + Uvicorn workers:**

```bash
gunicorn api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

---

## DOCUMENT METADATA

**Document ID:** 22  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Owner:** Chief Architect  
**Dependencies:** Documents 20 (Semantic Bus), 21 (Database Schemas)  
**Next Document:** 23 (Testing Framework & Quality Assurance)

---

*End of API Layer Design & Implementation*
