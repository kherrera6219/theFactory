# DOCUMENT 42: INTEGRATION TESTING FRAMEWORK

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Quality & Testing

**Document ID:** 42  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive integration testing specifications** for the Holy Grail Refinery system. Integration tests validate interactions between components, including agent-to-agent communication, database operations, API endpoints, and Semantic Bus message flow.

**Integration Testing Scope:**
- 🔗 **Agent Communication:** Inter-agent message passing via Semantic Bus
- 💾 **Database Integration:** PostgreSQL, Redis, Milvus operations
- 🌐 **API Testing:** REST API endpoints and workflows
- 📨 **Protocol Validation:** Message schema and routing verification
- 🏗️ **Infrastructure:** Docker container interactions

**Test Environment:**
- **Isolation:** Docker Compose test environment (separate from production)
- **Data:** Test databases with seeded data
- **Services:** Minimal required services (no full 35-agent deployment)
- **Cleanup:** Automatic teardown after test execution

**Quality Standards:**
- ⏱️ **Execution Time:** < 30 minutes for full integration suite
- ✅ **Pass Rate:** 100% required for deployment
- 🔄 **Idempotency:** Tests can run multiple times with same results
- 🧪 **Isolation:** No cross-test contamination

---

## TABLE OF CONTENTS

1. [Integration Test Architecture](#1-integration-test-architecture)
2. [Test Environment Setup](#2-test-environment-setup)
3. [Database Integration Testing](#3-database-integration-testing)
4. [API Integration Testing](#4-api-integration-testing)
5. [Agent Communication Testing](#5-agent-communication-testing)
6. [Semantic Bus Testing](#6-semantic-bus-testing)
7. [Protocol Validation Testing](#7-protocol-validation-testing)
8. [Cross-Pod Integration Testing](#8-cross-pod-integration-testing)
9. [Test Data Management](#9-test-data-management)
10. [CI/CD Integration](#10-cicd-integration)

---

## 1. INTEGRATION TEST ARCHITECTURE

### 1.1 Test Layers

```
â"Œâ"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"
â"‚              E2E / SYSTEM TESTS                       â"‚
â"‚         (Full 35-agent orchestration)                 â"‚
â""â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"¬â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"˜
                     â"‚
                     â–¼
â"Œâ"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"
â"‚            INTEGRATION TESTS â† YOU ARE HERE          â"‚
â"‚                                                        â"‚
â"‚  â€¢ Agent â†" Agent communication                        â"‚
â"‚  â€¢ Agent â†" Database operations                        â"‚
â"‚  â€¢ API â†" Database workflows                           â"‚
â"‚  â€¢ Semantic Bus message routing                       â"‚
â"‚  â€¢ Protocol validation                                â"‚
â""â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"¬â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"˜
                     â"‚
                     â–¼
â"Œâ"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"
â"‚                 UNIT TESTS                            â"‚
â"‚         (Isolated component testing)                  â"‚
â""â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"˜
```

### 1.2 Directory Structure

```
tests/
â"œâ"€â"€ integration/
â"‚   â"œâ"€â"€ __init__.py
â"‚   â"œâ"€â"€ conftest.py                    # Shared fixtures
â"‚   â"‚
â"‚   â"œâ"€â"€ database/
â"‚   â"‚   â"œâ"€â"€ test_postgres_operations.py
â"‚   â"‚   â"œâ"€â"€ test_redis_operations.py
â"‚   â"‚   â"œâ"€â"€ test_milvus_operations.py
â"‚   â"‚   â""â"€â"€ test_database_transactions.py
â"‚   â"‚
â"‚   â"œâ"€â"€ api/
â"‚   â"‚   â"œâ"€â"€ test_logicnode_api.py
â"‚   â"‚   â"œâ"€â"€ test_task_api.py
â"‚   â"‚   â"œâ"€â"€ test_agent_api.py
â"‚   â"‚   â""â"€â"€ test_auth_workflows.py
â"‚   â"‚
â"‚   â"œâ"€â"€ agents/
â"‚   â"‚   â"œâ"€â"€ test_agent_communication.py
â"‚   â"‚   â"œâ"€â"€ test_manager_specialist_flow.py
â"‚   â"‚   â"œâ"€â"€ test_audit_workflow.py
â"‚   â"‚   â""â"€â"€ test_cross_pod_communication.py
â"‚   â"‚
â"‚   â"œâ"€â"€ semantic_bus/
â"‚   â"‚   â"œâ"€â"€ test_message_routing.py
â"‚   â"‚   â"œâ"€â"€ test_pub_sub.py
â"‚   â"‚   â""â"€â"€ test_message_persistence.py
â"‚   â"‚
â"‚   â"œâ"€â"€ protocols/
â"‚   â"‚   â"œâ"€â"€ test_protocol_alpha.py
â"‚   â"‚   â"œâ"€â"€ test_protocol_beta.py
â"‚   â"‚   â""â"€â"€ test_protocol_validation.py
â"‚   â"‚
â"‚   â""â"€â"€ workflows/
â"‚       â"œâ"€â"€ test_extraction_workflow.py
â"‚       â"œâ"€â"€ test_audit_workflow.py
â"‚       â""â"€â"€ test_synthesis_workflow.py
â"‚
â"œâ"€â"€ fixtures/
â"‚   â"œâ"€â"€ sample_code.py
â"‚   â"œâ"€â"€ sample_logicnodes.json
â"‚   â""â"€â"€ sample_messages.json
â"‚
â""â"€â"€ docker/
    â"œâ"€â"€ docker-compose.test.yml
    â""â"€â"€ init-test-db.sql
```

---

## 2. TEST ENVIRONMENT SETUP

### 2.1 Docker Compose Test Configuration

**File:** `tests/docker/docker-compose.test.yml`

```yaml
version: '3.8'

services:
  # PostgreSQL test database
  postgres-test:
    image: postgres:16-alpine
    container_name: hgr-postgres-test
    environment:
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
      POSTGRES_DB: hgr_test
    ports:
      - "5433:5432"  # Different port to avoid conflicts
    volumes:
      - ./init-test-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user"]
      interval: 5s
      timeout: 5s
      retries: 5
  
  # Redis test instance
  redis-test:
    image: redis:7.2-alpine
    container_name: hgr-redis-test
    ports:
      - "6380:6379"  # Different port
    command: redis-server --save "" --appendonly no  # No persistence
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
  
  # Milvus test instance (lightweight)
  milvus-test:
    image: milvusdb/milvus:v2.3.3
    container_name: hgr-milvus-test
    environment:
      ETCD_ENDPOINTS: etcd-test:2379
      MINIO_ADDRESS: minio-test:9000
    ports:
      - "19531:19530"
    depends_on:
      - etcd-test
      - minio-test
  
  # Supporting services for Milvus
  etcd-test:
    image: quay.io/coreos/etcd:v3.5.5
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379
  
  minio-test:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: minio server /minio_data
  
  # Test API server
  api-test:
    build:
      context: ../..
      dockerfile: Dockerfile
    container_name: hgr-api-test
    environment:
      DATABASE_URL: postgresql://test_user:test_password@postgres-test:5432/hgr_test
      REDIS_URL: redis://redis-test:6379
      TESTING: "true"
    ports:
      - "8001:8000"
    depends_on:
      postgres-test:
        condition: service_healthy
      redis-test:
        condition: service_healthy
  
  # Test agent (Python specialist)
  agent-python-test:
    build:
      context: ../..
      dockerfile: agents/Dockerfile
    container_name: hgr-agent-python-test
    environment:
      AGENT_ID: AGENT-PY-TEST-001
      DATABASE_URL: postgresql://test_user:test_password@postgres-test:5432/hgr_test
      REDIS_URL: redis://redis-test:6379
      TESTING: "true"
    depends_on:
      - redis-test
      - postgres-test

networks:
  default:
    name: hgr-test-network
```

### 2.2 Database Initialization

**File:** `tests/docker/init-test-db.sql`

```sql
-- Initialize test database schema

CREATE TABLE IF NOT EXISTS logicnodes (
    logicnode_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent TEXT NOT NULL,
    domain VARCHAR(255) NOT NULL,
    concept VARCHAR(255) NOT NULL,
    inputs JSONB NOT NULL DEFAULT '[]',
    outputs JSONB NOT NULL DEFAULT '[]',
    preconditions JSONB NOT NULL DEFAULT '[]',
    postconditions JSONB NOT NULL DEFAULT '[]',
    side_effects JSONB NOT NULL DEFAULT '[]',
    source_language VARCHAR(50),
    source_file TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS missions (
    mission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(50) NOT NULL,
    assigned_to VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mission_id UUID REFERENCES missions(mission_id),
    task_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    assigned_to VARCHAR(255),
    priority INTEGER DEFAULT 5,
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_logicnodes_domain ON logicnodes(domain);
CREATE INDEX idx_logicnodes_concept ON logicnodes(concept);
CREATE INDEX idx_missions_status ON missions(status);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_mission_id ON tasks(mission_id);

-- Insert test data
INSERT INTO missions (mission_id, status, assigned_to, metadata) VALUES
    ('00000000-0000-0000-0000-000000000001', 'completed', 'AGENT-PY-001', '{"test": true}'),
    ('00000000-0000-0000-0000-000000000002', 'in_progress', 'AGENT-JS-001', '{"test": true}'),
    ('00000000-0000-0000-0000-000000000003', 'pending', NULL, '{"test": true}');

INSERT INTO logicnodes (logicnode_id, intent, domain, concept, inputs, outputs) VALUES
    (
        '10000000-0000-0000-0000-000000000001',
        'Add two numbers',
        'arithmetic_operations',
        'addition',
        '[{"name": "a", "type": {"base": "number"}}, {"name": "b", "type": {"base": "number"}}]',
        '[{"name": "result", "type": {"base": "number"}}]'
    ),
    (
        '10000000-0000-0000-0000-000000000002',
        'Multiply two numbers',
        'arithmetic_operations',
        'multiplication',
        '[{"name": "a", "type": {"base": "number"}}, {"name": "b", "type": {"base": "number"}}]',
        '[{"name": "result", "type": {"base": "number"}}]'
    );
```

### 2.3 Test Environment Management

**File:** `tests/integration/conftest.py`

```python
"""
Shared fixtures for integration tests
"""

import pytest
import asyncio
import subprocess
import time
from typing import Generator
import psycopg2
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Database URLs
POSTGRES_TEST_URL = "postgresql://test_user:test_password@localhost:5433/hgr_test"
REDIS_TEST_URL = "redis://localhost:6380"
API_TEST_URL = "http://localhost:8001"

@pytest.fixture(scope="session")
def docker_compose_up():
    """
    Start Docker Compose test environment
    """
    print("\nStarting test environment...")
    subprocess.run(
        ["docker-compose", "-f", "tests/docker/docker-compose.test.yml", "up", "-d"],
        check=True
    )
    
    # Wait for services to be healthy
    time.sleep(10)
    
    yield
    
    # Teardown
    print("\nStopping test environment...")
    subprocess.run(
        ["docker-compose", "-f", "tests/docker/docker-compose.test.yml", "down", "-v"],
        check=True
    )

@pytest.fixture(scope="function")
def db_session(docker_compose_up) -> Generator[Session, None, None]:
    """
    Provide a transactional database session
    """
    engine = create_engine(POSTGRES_TEST_URL)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    yield session
    
    # Rollback transaction (keeps test data isolated)
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def redis_client(docker_compose_up) -> Generator[redis.Redis, None, None]:
    """
    Provide a Redis client
    """
    client = redis.from_url(REDIS_TEST_URL)
    
    yield client
    
    # Cleanup: flush test data
    client.flushdb()
    client.close()

@pytest.fixture
def api_client(docker_compose_up):
    """
    Provide an API client (requests wrapper)
    """
    import requests
    
    class APIClient:
        def __init__(self, base_url: str):
            self.base_url = base_url
            self.session = requests.Session()
        
        def get(self, path: str, **kwargs):
            return self.session.get(f"{self.base_url}{path}", **kwargs)
        
        def post(self, path: str, **kwargs):
            return self.session.post(f"{self.base_url}{path}", **kwargs)
        
        def put(self, path: str, **kwargs):
            return self.session.put(f"{self.base_url}{path}", **kwargs)
        
        def delete(self, path: str, **kwargs):
            return self.session.delete(f"{self.base_url}{path}", **kwargs)
    
    return APIClient(API_TEST_URL)

@pytest.fixture
def sample_logicnode_data():
    """Sample LogicNode data for testing"""
    return {
        "intent": "Add two numbers and return sum",
        "domain": "arithmetic_operations",
        "concept": "addition",
        "inputs": [
            {"name": "a", "type": {"base": "number"}},
            {"name": "b", "type": {"base": "number"}}
        ],
        "outputs": [
            {"name": "result", "type": {"base": "number"}}
        ],
        "source_language": "python",
        "source_file": "test.py"
    }
```

---

## 3. DATABASE INTEGRATION TESTING

### 3.1 PostgreSQL Integration Tests

**File:** `tests/integration/database/test_postgres_operations.py`

```python
"""
Integration tests for PostgreSQL operations
"""

import pytest
from sqlalchemy.orm import Session
from uuid import UUID

@pytest.mark.integration
def test_insert_logicnode_into_database(db_session: Session, sample_logicnode_data):
    """Test inserting LogicNode into PostgreSQL"""
    # ARRANGE
    from models import LogicNode
    
    logicnode = LogicNode(**sample_logicnode_data)
    
    # ACT
    db_session.add(logicnode)
    db_session.commit()
    
    # ASSERT
    retrieved = db_session.query(LogicNode).filter_by(
        intent=sample_logicnode_data["intent"]
    ).first()
    
    assert retrieved is not None
    assert retrieved.domain == "arithmetic_operations"
    assert retrieved.concept == "addition"
    assert len(retrieved.inputs) == 2

@pytest.mark.integration
def test_query_logicnodes_by_domain(db_session: Session):
    """Test querying LogicNodes by domain"""
    from models import LogicNode
    
    # ACT
    results = db_session.query(LogicNode).filter_by(
        domain="arithmetic_operations"
    ).all()
    
    # ASSERT
    assert len(results) >= 2  # From seed data
    assert all(ln.domain == "arithmetic_operations" for ln in results)

@pytest.mark.integration
def test_update_logicnode_in_database(db_session: Session):
    """Test updating LogicNode"""
    from models import LogicNode
    
    # Get existing LogicNode
    logicnode = db_session.query(LogicNode).first()
    original_intent = logicnode.intent
    
    # ACT
    logicnode.intent = "Updated intent"
    db_session.commit()
    
    # ASSERT
    retrieved = db_session.query(LogicNode).filter_by(
        logicnode_id=logicnode.logicnode_id
    ).first()
    
    assert retrieved.intent == "Updated intent"
    assert retrieved.intent != original_intent

@pytest.mark.integration
def test_delete_logicnode_from_database(db_session: Session):
    """Test deleting LogicNode"""
    from models import LogicNode
    
    # Create new LogicNode
    logicnode = LogicNode(
        intent="To be deleted",
        domain="test",
        concept="test",
        inputs=[],
        outputs=[]
    )
    db_session.add(logicnode)
    db_session.commit()
    
    logicnode_id = logicnode.logicnode_id
    
    # ACT
    db_session.delete(logicnode)
    db_session.commit()
    
    # ASSERT
    retrieved = db_session.query(LogicNode).filter_by(
        logicnode_id=logicnode_id
    ).first()
    
    assert retrieved is None

@pytest.mark.integration
def test_transaction_rollback_on_error(db_session: Session):
    """Test that transactions rollback on error"""
    from models import LogicNode
    
    # Count LogicNodes before
    count_before = db_session.query(LogicNode).count()
    
    try:
        # Create valid LogicNode
        ln1 = LogicNode(
            intent="Valid",
            domain="test",
            concept="test",
            inputs=[],
            outputs=[]
        )
        db_session.add(ln1)
        
        # Create invalid LogicNode (will fail constraint)
        ln2 = LogicNode(
            intent="",  # Empty intent (invalid)
            domain="test",
            concept="test",
            inputs=[],
            outputs=[]
        )
        db_session.add(ln2)
        db_session.commit()
    except Exception:
        db_session.rollback()
    
    # ASSERT
    count_after = db_session.query(LogicNode).count()
    assert count_after == count_before  # No changes persisted
```

### 3.2 Redis Integration Tests

**File:** `tests/integration/database/test_redis_operations.py`

```python
"""
Integration tests for Redis operations
"""

import pytest
import redis
import json

@pytest.mark.integration
def test_set_and_get_value_from_redis(redis_client: redis.Redis):
    """Test basic Redis set/get"""
    # ACT
    redis_client.set("test_key", "test_value")
    value = redis_client.get("test_key")
    
    # ASSERT
    assert value.decode() == "test_value"

@pytest.mark.integration
def test_store_json_in_redis(redis_client: redis.Redis):
    """Test storing JSON data in Redis"""
    data = {
        "agent_id": "AGENT-PY-001",
        "state": "working",
        "current_task": "extract_logicnodes"
    }
    
    # ACT
    redis_client.set("agent:AGENT-PY-001:state", json.dumps(data))
    retrieved = json.loads(redis_client.get("agent:AGENT-PY-001:state"))
    
    # ASSERT
    assert retrieved["agent_id"] == "AGENT-PY-001"
    assert retrieved["state"] == "working"

@pytest.mark.integration
def test_redis_pub_sub_messaging(redis_client: redis.Redis):
    """Test Redis pub/sub functionality"""
    # Subscribe to channel
    pubsub = redis_client.pubsub()
    pubsub.subscribe("test_channel")
    
    # Publish message
    redis_client.publish("test_channel", "test_message")
    
    # Receive message
    message = pubsub.get_message(timeout=1.0)
    if message and message['type'] == 'subscribe':
        message = pubsub.get_message(timeout=1.0)
    
    # ASSERT
    assert message is not None
    assert message['data'].decode() == "test_message"

@pytest.mark.integration
def test_redis_list_operations(redis_client: redis.Redis):
    """Test Redis list operations (message queue simulation)"""
    queue_name = "message_queue"
    
    # Push messages
    redis_client.rpush(queue_name, "message1")
    redis_client.rpush(queue_name, "message2")
    redis_client.rpush(queue_name, "message3")
    
    # ACT
    length = redis_client.llen(queue_name)
    first_msg = redis_client.lpop(queue_name)
    
    # ASSERT
    assert length == 3
    assert first_msg.decode() == "message1"
    assert redis_client.llen(queue_name) == 2

@pytest.mark.integration
def test_redis_hash_operations(redis_client: redis.Redis):
    """Test Redis hash operations (agent state storage)"""
    agent_id = "AGENT-PY-001"
    
    # Set hash fields
    redis_client.hset(f"agent:{agent_id}", "state", "idle")
    redis_client.hset(f"agent:{agent_id}", "current_task", "none")
    redis_client.hset(f"agent:{agent_id}", "tasks_completed", "0")
    
    # ACT
    state = redis_client.hget(f"agent:{agent_id}", "state")
    all_fields = redis_client.hgetall(f"agent:{agent_id}")
    
    # ASSERT
    assert state.decode() == "idle"
    assert len(all_fields) == 3
    assert all_fields[b"tasks_completed"].decode() == "0"
```

---

## 4. API INTEGRATION TESTING

### 4.1 LogicNode API Tests

**File:** `tests/integration/api/test_logicnode_api.py`

```python
"""
Integration tests for LogicNode API endpoints
"""

import pytest

@pytest.mark.integration
def test_get_all_logicnodes(api_client):
    """Test GET /api/v1/logicnodes"""
    response = api_client.get("/api/v1/logicnodes")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2  # From seed data

@pytest.mark.integration
def test_create_logicnode_via_api(api_client, sample_logicnode_data):
    """Test POST /api/v1/logicnodes"""
    response = api_client.post(
        "/api/v1/logicnodes",
        json=sample_logicnode_data
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "logicnode_id" in data
    assert data["intent"] == sample_logicnode_data["intent"]

@pytest.mark.integration
def test_get_logicnode_by_id(api_client):
    """Test GET /api/v1/logicnodes/{id}"""
    # Use known ID from seed data
    logicnode_id = "10000000-0000-0000-0000-000000000001"
    
    response = api_client.get(f"/api/v1/logicnodes/{logicnode_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["logicnode_id"] == logicnode_id
    assert data["concept"] == "addition"

@pytest.mark.integration
def test_update_logicnode_via_api(api_client):
    """Test PUT /api/v1/logicnodes/{id}"""
    logicnode_id = "10000000-0000-0000-0000-000000000001"
    
    updated_data = {
        "intent": "Updated: Add two numbers"
    }
    
    response = api_client.put(
        f"/api/v1/logicnodes/{logicnode_id}",
        json=updated_data
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "Updated" in data["intent"]

@pytest.mark.integration
def test_delete_logicnode_via_api(api_client, sample_logicnode_data):
    """Test DELETE /api/v1/logicnodes/{id}"""
    # Create LogicNode first
    create_response = api_client.post(
        "/api/v1/logicnodes",
        json=sample_logicnode_data
    )
    logicnode_id = create_response.json()["logicnode_id"]
    
    # Delete it
    delete_response = api_client.delete(f"/api/v1/logicnodes/{logicnode_id}")
    
    assert delete_response.status_code == 204
    
    # Verify deletion
    get_response = api_client.get(f"/api/v1/logicnodes/{logicnode_id}")
    assert get_response.status_code == 404

@pytest.mark.integration
def test_search_logicnodes_by_domain(api_client):
    """Test GET /api/v1/logicnodes?domain=..."""
    response = api_client.get(
        "/api/v1/logicnodes",
        params={"domain": "arithmetic_operations"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert all(ln["domain"] == "arithmetic_operations" for ln in data)

@pytest.mark.integration
def test_create_logicnode_with_invalid_data_returns_400(api_client):
    """Test validation errors return 400"""
    invalid_data = {
        "intent": "",  # Empty intent
        "domain": "test"
        # Missing required fields
    }
    
    response = api_client.post(
        "/api/v1/logicnodes",
        json=invalid_data
    )
    
    assert response.status_code == 400
    assert "error" in response.json()
```

### 4.2 Authentication Workflow Tests

**File:** `tests/integration/api/test_auth_workflows.py`

```python
"""
Integration tests for authentication workflows
"""

import pytest

@pytest.mark.integration
def test_get_auth_token(api_client):
    """Test POST /api/v1/auth/token"""
    credentials = {
        "username": "test_user",
        "password": "test_password"
    }
    
    response = api_client.post("/api/v1/auth/token", json=credentials)
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "token_type" in data
    assert data["token_type"] == "bearer"

@pytest.mark.integration
def test_access_protected_endpoint_with_token(api_client):
    """Test accessing protected endpoint with valid token"""
    # Get token
    token_response = api_client.post("/api/v1/auth/token", json={
        "username": "test_user",
        "password": "test_password"
    })
    token = token_response.json()["access_token"]
    
    # Access protected endpoint
    response = api_client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200

@pytest.mark.integration
def test_access_protected_endpoint_without_token_returns_401(api_client):
    """Test that protected endpoints require authentication"""
    response = api_client.get("/api/v1/agents")
    
    assert response.status_code == 401

@pytest.mark.integration
def test_invalid_token_returns_401(api_client):
    """Test that invalid tokens are rejected"""
    response = api_client.get(
        "/api/v1/agents",
        headers={"Authorization": "Bearer invalid_token"}
    )
    
    assert response.status_code == 401
```

---

## 5. AGENT COMMUNICATION TESTING

### 5.1 Agent-to-Agent Message Flow

**File:** `tests/integration/agents/test_agent_communication.py`

```python
"""
Integration tests for agent-to-agent communication
"""

import pytest
import asyncio
import json

@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_sends_message_via_semantic_bus(redis_client):
    """Test agent publishing message to Semantic Bus"""
    from agents.specialists.python_agent import PythonAgent
    
    # ARRANGE
    agent = PythonAgent(
        agent_id="AGENT-PY-TEST-001",
        redis_url="redis://localhost:6380"
    )
    
    message = {
        "from": "AGENT-PY-TEST-001",
        "to": "AUDIT-LEAD-001",
        "protocol": "Alpha",
        "payload": {
            "logicnode_id": "test_001",
            "status": "ready_for_audit"
        }
    }
    
    # ACT
    await agent.send_message(message)
    
    # ASSERT
    # Check message was published to Redis
    messages = redis_client.lrange("semantic_bus:messages", 0, -1)
    assert len(messages) > 0
    
    latest_message = json.loads(messages[-1])
    assert latest_message["from"] == "AGENT-PY-TEST-001"
    assert latest_message["to"] == "AUDIT-LEAD-001"

@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_receives_message_from_semantic_bus(redis_client):
    """Test agent subscribing and receiving messages"""
    from agents.specialists.python_agent import PythonAgent
    
    # ARRANGE
    agent = PythonAgent(
        agent_id="AGENT-PY-TEST-001",
        redis_url="redis://localhost:6380"
    )
    
    # Subscribe to channel
    await agent.subscribe("agent:AGENT-PY-TEST-001")
    
    # Publish message
    message = {
        "from": "MANAGER-POD-A-001",
        "to": "AGENT-PY-TEST-001",
        "payload": {"task_id": "T001"}
    }
    redis_client.publish("agent:AGENT-PY-TEST-001", json.dumps(message))
    
    # ACT
    received_message = await agent.receive_message(timeout=5.0)
    
    # ASSERT
    assert received_message is not None
    assert received_message["from"] == "MANAGER-POD-A-001"
    assert received_message["payload"]["task_id"] == "T001"
```

### 5.2 Manager-to-Specialist Workflow

**File:** `tests/integration/agents/test_manager_specialist_flow.py`

```python
"""
Integration tests for Manager → Specialist workflow
"""

import pytest
import asyncio

@pytest.mark.integration
@pytest.mark.asyncio
async def test_manager_assigns_task_to_specialist(redis_client):
    """Test complete task assignment workflow"""
    from agents.managers.pod_a_manager import PodAManager
    from agents.specialists.python_agent import PythonAgent
    
    # ARRANGE
    manager = PodAManager(
        agent_id="MANAGER-POD-A-TEST-001",
        redis_url="redis://localhost:6380"
    )
    
    specialist = PythonAgent(
        agent_id="AGENT-PY-TEST-001",
        redis_url="redis://localhost:6380"
    )
    
    # Subscribe specialist to messages
    await specialist.subscribe("agent:AGENT-PY-TEST-001")
    
    task = {
        "task_id": "T001",
        "type": "extract_logicnodes",
        "language": "python",
        "payload": {
            "code": "def add(a, b): return a + b"
        }
    }
    
    # ACT
    await manager.assign_task("AGENT-PY-TEST-001", task)
    
    # Specialist receives and processes task
    received_task = await specialist.receive_message(timeout=5.0)
    result = await specialist.process_task(received_task)
    
    # ASSERT
    assert received_task["payload"]["task_id"] == "T001"
    assert result["status"] == "completed"
    assert "logicnodes" in result
```

---

## 6. SEMANTIC BUS TESTING

### 6.1 Message Routing Tests

**File:** `tests/integration/semantic_bus/test_message_routing.py`

```python
"""
Integration tests for Semantic Bus message routing
"""

import pytest
from semantic_bus.router import MessageRouter

@pytest.mark.integration
def test_route_message_to_correct_agent(redis_client):
    """Test message routing based on target agent"""
    router = MessageRouter(redis_url="redis://localhost:6380")
    
    message = {
        "from": "AGENT-PY-001",
        "to": "AUDIT-LEAD-001",
        "payload": {"test": "data"}
    }
    
    # ACT
    router.route_message(message)
    
    # ASSERT
    # Message should be in AUDIT-LEAD-001's queue
    messages = redis_client.lrange("agent:AUDIT-LEAD-001:inbox", 0, -1)
    assert len(messages) > 0

@pytest.mark.integration
def test_broadcast_message_to_all_agents(redis_client):
    """Test broadcasting message to multiple agents"""
    router = MessageRouter(redis_url="redis://localhost:6380")
    
    message = {
        "from": "CEO-001",
        "to": "ALL_AGENTS",
        "payload": {"announcement": "System maintenance in 1 hour"}
    }
    
    # ACT
    router.broadcast(message)
    
    # ASSERT
    # Message should be in broadcast channel
    assert redis_client.get("broadcast:latest") is not None
```

---

## 7. PROTOCOL VALIDATION TESTING

### 7.1 Protocol Schema Validation

**File:** `tests/integration/protocols/test_protocol_validation.py`

```python
"""
Integration tests for protocol message validation
"""

import pytest
from protocols.validator import validate_message

@pytest.mark.integration
def test_validate_alpha_protocol_message():
    """Test validation of Protocol Alpha messages"""
    message = {
        "protocol": "Alpha",
        "from": "AGENT-PY-001",
        "to": "ARCH-001",
        "mission_id": "MSN-001",
        "payload": {
            "status": "analysis_complete",
            "logicnodes_extracted": 15
        }
    }
    
    result = validate_message(message)
    
    assert result.is_valid
    assert len(result.errors) == 0

@pytest.mark.integration
def test_invalid_protocol_message_fails_validation():
    """Test that invalid messages fail validation"""
    message = {
        "protocol": "Alpha",
        # Missing required fields
        "payload": {}
    }
    
    result = validate_message(message)
    
    assert not result.is_valid
    assert len(result.errors) > 0
```

---

## 8. CROSS-POD INTEGRATION TESTING

### 8.1 Multi-Pod Workflow

**File:** `tests/integration/workflows/test_cross_pod_workflow.py`

```python
"""
Integration tests for cross-pod workflows
"""

import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_python_to_audit_to_synthesis_workflow(redis_client, db_session):
    """Test complete workflow across multiple pods"""
    from agents.specialists.python_agent import PythonAgent
    from agents.audit.audit_lead import AuditLead
    
    # 1. Python agent extracts LogicNodes
    python_agent = PythonAgent(agent_id="AGENT-PY-TEST-001")
    code = "def add(a, b): return a + b"
    logicnodes = await python_agent.extract_logicnodes(code)
    
    assert len(logicnodes) > 0
    
    # 2. Send to Audit
    await python_agent.send_to_audit(logicnodes[0])
    
    # 3. Audit receives and validates
    audit_agent = AuditLead(agent_id="AUDIT-LEAD-TEST-001")
    audit_message = await audit_agent.receive_message(timeout=5.0)
    audit_result = await audit_agent.validate_logicnode(
        audit_message["payload"]["logicnode"]
    )
    
    assert audit_result["is_valid"]
    
    # 4. Verify LogicNode saved to database
    from models import LogicNode
    saved_ln = db_session.query(LogicNode).filter_by(
        intent=logicnodes[0].intent
    ).first()
    
    assert saved_ln is not None
```

---

## 9. TEST DATA MANAGEMENT

### 9.1 Test Fixtures

**File:** `tests/fixtures/sample_code.py`

```python
"""
Sample code snippets for testing
"""

SAMPLE_PYTHON_FUNCTIONS = {
    "addition": """
def add(a: int, b: int) -> int:
    '''Add two numbers and return the sum'''
    return a + b
""",
    
    "multiplication": """
def multiply(x: float, y: float) -> float:
    '''Multiply two numbers'''
    return x * y
""",
    
    "complex_function": """
def process_data(data: List[int], threshold: int = 10) -> Dict[str, Any]:
    '''Process list of integers and return statistics'''
    filtered = [x for x in data if x > threshold]
    return {
        'count': len(filtered),
        'sum': sum(filtered),
        'average': sum(filtered) / len(filtered) if filtered else 0
    }
"""
}

SAMPLE_JAVASCRIPT_FUNCTIONS = {
    "addition": """
function add(a, b) {
    return a + b;
}
""",
    
    "arrow_function": """
const multiply = (x, y) => x * y;
"""
}
```

### 9.2 Data Seeding

**File:** `tests/integration/conftest.py` (continued)

```python
@pytest.fixture
def seed_test_data(db_session):
    """Seed database with test data"""
    from models import LogicNode, Mission, Task
    
    # Create sample missions
    missions = [
        Mission(mission_id=f"MSN-TEST-{i:03d}", status="pending")
        for i in range(5)
    ]
    db_session.add_all(missions)
    
    # Create sample LogicNodes
    logicnodes = [
        LogicNode(
            intent=f"Test LogicNode {i}",
            domain="test_domain",
            concept=f"test_concept_{i}",
            inputs=[],
            outputs=[]
        )
        for i in range(10)
    ]
    db_session.add_all(logicnodes)
    
    db_session.commit()
    
    return {
        "missions": missions,
        "logicnodes": logicnodes
    }
```

---

## 10. CI/CD INTEGRATION

### 10.1 GitHub Actions Workflow

**File:** `.github/workflows/integration-tests.yml`

```yaml
name: Integration Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  integration-test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Start test environment
        run: |
          docker-compose -f tests/docker/docker-compose.test.yml up -d
          sleep 30  # Wait for services
      
      - name: Run integration tests
        run: |
          pytest tests/integration/ \
            -v \
            --junitxml=junit-integration.xml \
            --cov=agents \
            --cov=api \
            --cov-report=xml:coverage-integration.xml
      
      - name: Stop test environment
        if: always()
        run: |
          docker-compose -f tests/docker/docker-compose.test.yml down -v
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: integration-test-results
          path: |
            junit-integration.xml
            coverage-integration.xml
```

### 10.2 Test Execution Script

**File:** `scripts/run_integration_tests.sh`

```bash
#!/bin/bash
# Run integration tests locally

set -e

echo "=== Integration Tests ==="

# 1. Start test environment
echo "Starting test environment..."
docker-compose -f tests/docker/docker-compose.test.yml up -d

# 2. Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 30

# 3. Run tests
echo "Running integration tests..."
pytest tests/integration/ \
    -v \
    --tb=short \
    --junitxml=junit-integration.xml

# 4. Cleanup
echo "Cleaning up..."
docker-compose -f tests/docker/docker-compose.test.yml down -v

echo "✓ Integration tests complete"
```

---

## DOCUMENT METADATA

**Document ID:** 42  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Owner:** QA Lead  
**Dependencies:** Document 41 (Unit Testing)  
**Next Document:** 43 (End-to-End Testing Scenarios)

---

*End of Integration Testing Framework*
