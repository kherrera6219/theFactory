# DOCUMENT 23: TESTING FRAMEWORK & QUALITY ASSURANCE
## Holy Grail Refinery - Development Specifications

**Document ID:** 23  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

The Holy Grail Refinery employs a **comprehensive multi-layered testing strategy** to ensure the 35-agent system operates with extreme reliability. Given the system's goal of 0.0001% tolerance (99.9999% accuracy), testing infrastructure must be robust, automated, and continuous.

**Testing Pyramid:**
- **Unit Tests** (70%): Individual agent functions, LogicNode validation
- **Integration Tests** (20%): Agent-to-agent communication, database operations
- **System Tests** (8%): End-to-end workflows, multi-agent orchestration
- **Performance Tests** (2%): Load testing, stress testing, benchmarking

**Quality Gates:**
- ✅ 90% code coverage minimum
- ✅ All tests pass before deployment
- ✅ Performance regression < 5%
- ✅ Zero critical security vulnerabilities

---

## TABLE OF CONTENTS

1. [Testing Architecture](#1-testing-architecture)
2. [Unit Testing](#2-unit-testing)
3. [Integration Testing](#3-integration-testing)
4. [System Testing](#4-system-testing)
5. [Performance Testing](#5-performance-testing)
6. [Security Testing](#6-security-testing)
7. [Test Data Management](#7-test-data-management)
8. [Continuous Integration](#8-continuous-integration)
9. [Quality Metrics](#9-quality-metrics)
10. [Testing Tools & Frameworks](#10-testing-tools--frameworks)

---

## 1. TESTING ARCHITECTURE

### 1.1 Testing Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    PRODUCTION SYSTEM                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   E2E / SYSTEM TESTS                         │
│  • Complete workflows (extract → verify → synthesize)        │
│  • Multi-agent orchestration scenarios                       │
│  • User acceptance testing                                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   INTEGRATION TESTS                          │
│  • Agent-to-agent communication via Semantic Bus             │
│  • Database read/write operations                            │
│  • API endpoint testing                                      │
│  • Protocol validation                                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      UNIT TESTS                              │
│  • Individual agent functions                                │
│  • LogicNode validation                                      │
│  • Helper utilities                                          │
│  • Data model validation                                     │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Test Environment Setup

**Test Docker Compose:**

```yaml
# docker-compose.test.yml
services:
  # Test database (ephemeral)
  postgres-test:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass
      POSTGRES_DB: test_db
    tmpfs:
      - /var/lib/postgresql/data  # In-memory for speed
  
  # Test Redis
  redis-test:
    image: redis:7.2-alpine
    tmpfs:
      - /data
  
  # Test API server
  api-test:
    build: ./api
    environment:
      DATABASE_URL: postgresql://test_user:test_pass@postgres-test/test_db
      REDIS_URL: redis://redis-test:6379
      TESTING: "true"
    depends_on:
      - postgres-test
      - redis-test
```

---

## 2. UNIT TESTING

### 2.1 Agent Function Testing (pytest)

**File:** `tests/unit/test_python_agent.py`

```python
"""
Unit tests for Python Specialist Agent
"""

import pytest
from agents.pod_a.python_agent import PythonAgent
from agents.base.message import Message

@pytest.fixture
def python_agent():
    """Create test instance of Python agent"""
    return PythonAgent(agent_id="AGENT-PY-TEST")


class TestPythonAgent:
    """Test suite for Python Specialist Agent"""
    
    def test_extract_logicnode_from_function(self, python_agent):
        """Test extracting LogicNode from simple Python function"""
        source_code = '''
def add(a, b):
    """Add two numbers"""
    return a + b
'''
        
        result = python_agent.extract_logicnode(source_code)
        
        assert result is not None
        assert result['domain'] == 'arithmetic_operations'
        assert result['concept'] == 'addition'
        assert len(result['inputs']) == 2
        assert len(result['outputs']) == 1
    
    def test_extract_logicnode_from_conditional(self, python_agent):
        """Test extracting LogicNode from if statement"""
        source_code = '''
if x > 0:
    result = "positive"
else:
    result = "non-positive"
'''
        
        result = python_agent.extract_logicnode(source_code)
        
        assert result['domain'] == 'control_flow'
        assert result['concept'] == 'conditional'
        assert len(result['inputs']) == 1
        assert result['inputs'][0]['name'] == 'condition'
    
    def test_handle_invalid_syntax(self, python_agent):
        """Test handling of invalid Python syntax"""
        source_code = "def broken("
        
        with pytest.raises(SyntaxError):
            python_agent.extract_logicnode(source_code)
    
    def test_handle_protocol_alpha_message(self, python_agent):
        """Test handling Protocol Alpha (directive) message"""
        message = Message(
            message_id="msg-001",
            protocol="alpha",
            sender="MANAGER-POD-A-001",
            recipient="AGENT-PY-TEST",
            payload={
                "message_type": "assignment",
                "task_id": "task-123",
                "instructions": "Extract LogicNodes from repo"
            }
        )
        
        result = python_agent.handle_message(message)
        
        assert result['status'] == 'accepted'
        assert result['task_id'] == 'task-123'


@pytest.mark.parametrize("source,expected_domain,expected_concept", [
    ("x = [1, 2, 3]", "data_structures", "list_literal"),
    ("x = {'a': 1}", "data_structures", "dict_literal"),
    ("for i in range(10):", "control_flow", "for_loop"),
    ("while x > 0:", "control_flow", "while_loop"),
    ("try:\n    x\nexcept:", "error_handling", "try_except"),
])
def test_extract_various_concepts(python_agent, source, expected_domain, expected_concept):
    """Parameterized test for multiple Python concepts"""
    result = python_agent.extract_logicnode(source)
    
    assert result['domain'] == expected_domain
    assert result['concept'] == expected_concept
```

### 2.2 LogicNode Validation Testing

**File:** `tests/unit/test_logicnode_validation.py`

```python
"""
Unit tests for LogicNode validation
"""

import pytest
from agents.base.logicnode import LogicNode, validate_logicnode

class TestLogicNodeValidation:
    """Test LogicNode schema validation"""
    
    def test_valid_logicnode(self):
        """Test validation of correctly formatted LogicNode"""
        logicnode = {
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
            "side_effects": []
        }
        
        # Should not raise exception
        validate_logicnode(logicnode)
    
    def test_missing_required_field(self):
        """Test validation fails when required field missing"""
        logicnode = {
            "domain": "arithmetic_operations",
            # Missing 'concept' field
            "intent": "Add two numbers",
            "inputs": [],
            "outputs": []
        }
        
        with pytest.raises(ValueError, match="Missing required field: concept"):
            validate_logicnode(logicnode)
    
    def test_invalid_type_system(self):
        """Test validation fails with invalid type"""
        logicnode = {
            "domain": "test",
            "concept": "test",
            "intent": "Test",
            "inputs": [
                {"name": "x", "type": {"base": "invalid_type"}}
            ],
            "outputs": []
        }
        
        with pytest.raises(ValueError, match="Invalid type: invalid_type"):
            validate_logicnode(logicnode)
    
    def test_constraint_validation(self):
        """Test constraint validation logic"""
        logicnode = {
            "domain": "test",
            "concept": "test",
            "intent": "Test",
            "inputs": [
                {"name": "x", "type": {"base": "number"}}
            ],
            "outputs": [
                {"name": "y", "type": {"base": "number"}}
            ],
            "preconditions": [
                {
                    "type": "range",
                    "variable": "x",
                    "min": 0,
                    "max": 100
                }
            ]
        }
        
        validate_logicnode(logicnode)
        
        # Test with inputs
        assert validate_logicnode_preconditions(logicnode, {"x": 50})
        assert not validate_logicnode_preconditions(logicnode, {"x": 150})
```

### 2.3 Database Model Testing

**File:** `tests/unit/test_models.py`

```python
"""
Unit tests for database models
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models.knowledge import Concept, LanguageMapping, Base

@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()


class TestConceptModel:
    """Test Concept ORM model"""
    
    def test_create_concept(self, db_session):
        """Test creating a new concept"""
        concept = Concept(
            concept_id="TEST-001-001",
            name="test_concept",
            domain="test_domain",
            pod="A",
            intent="Test concept for unit testing",
            is_pure=True
        )
        
        db_session.add(concept)
        db_session.commit()
        
        # Retrieve and verify
        retrieved = db_session.query(Concept).filter_by(
            concept_id="TEST-001-001"
        ).first()
        
        assert retrieved is not None
        assert retrieved.name == "test_concept"
        assert retrieved.pod == "A"
    
    def test_concept_with_mappings(self, db_session):
        """Test concept with language mappings relationship"""
        concept = Concept(
            concept_id="TEST-001-002",
            name="addition",
            domain="arithmetic",
            pod="A",
            intent="Add two numbers"
        )
        
        mapping_python = LanguageMapping(
            concept_id="TEST-001-002",
            language="python",
            syntax="a + b"
        )
        
        mapping_js = LanguageMapping(
            concept_id="TEST-001-002",
            language="javascript",
            syntax="a + b"
        )
        
        concept.mappings = [mapping_python, mapping_js]
        
        db_session.add(concept)
        db_session.commit()
        
        # Verify relationship
        retrieved = db_session.query(Concept).filter_by(
            concept_id="TEST-001-002"
        ).first()
        
        assert len(retrieved.mappings) == 2
        assert any(m.language == "python" for m in retrieved.mappings)
```

### 2.4 Running Unit Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=agents --cov=database --cov-report=html

# Run specific test file
pytest tests/unit/test_python_agent.py -v

# Run specific test
pytest tests/unit/test_python_agent.py::TestPythonAgent::test_extract_logicnode_from_function -v

# Run tests in parallel (faster)
pytest tests/unit/ -n auto
```

---

## 3. INTEGRATION TESTING

### 3.1 Semantic Bus Integration

**File:** `tests/integration/test_semantic_bus.py`

```python
"""
Integration tests for Semantic Bus communication
"""

import pytest
import asyncio
from semantic_bus.redis_client import RedisClient
from semantic_bus.mcp_server import send_message

@pytest.fixture
def redis_client():
    """Connect to test Redis instance"""
    client = RedisClient(host="redis-test", port=6379)
    yield client
    client.client.flushdb()  # Clean up after test


class TestSemanticBus:
    """Integration tests for agent communication"""
    
    @pytest.mark.asyncio
    async def test_protocol_alpha_delivery(self, redis_client):
        """Test Protocol Alpha message delivery"""
        received_messages = []
        
        def callback(channel, message):
            received_messages.append(message)
        
        # Subscribe to channel
        asyncio.create_task(
            redis_client.subscribe(
                ["protocol:alpha:agent:TEST-001"],
                callback
            )
        )
        
        # Wait for subscription to establish
        await asyncio.sleep(0.1)
        
        # Send message
        redis_client.publish(
            "protocol:alpha:agent:TEST-001",
            {
                "message_id": "msg-test",
                "protocol": "alpha",
                "sender": "ARCH-001",
                "recipient": "TEST-001",
                "payload": {
                    "message_type": "assignment",
                    "task_id": "task-test",
                    "instructions": "Test message"
                }
            }
        )
        
        # Wait for delivery
        await asyncio.sleep(0.1)
        
        assert len(received_messages) == 1
        assert received_messages[0]['message_id'] == 'msg-test'
    
    def test_dead_letter_queue(self, redis_client):
        """Test DLQ handles failed messages"""
        invalid_message = {
            "message_id": "msg-invalid",
            "protocol": "unknown_protocol",
            "payload": {}
        }
        
        redis_client.push_to_dlq(invalid_message, "Invalid protocol")
        
        # Verify DLQ contains message
        dlq_items = redis_client.client.lrange("semantic_bus:dlq", 0, -1)
        assert len(dlq_items) == 1
```

### 3.2 Database Integration Tests

**File:** `tests/integration/test_database.py`

```python
"""
Integration tests for database operations
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models.logicnode import LogicNode, Base

@pytest.fixture(scope="module")
def db_engine():
    """Create test database engine"""
    engine = create_engine(
        "postgresql://test_user:test_pass@postgres-test/test_db"
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    """Create database session for each test"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


class TestLogicNodeCRUD:
    """Test CRUD operations for LogicNodes"""
    
    def test_create_and_retrieve_logicnode(self, db_session):
        """Test creating and retrieving LogicNode"""
        logicnode = LogicNode(
            logicnode_id="ln-test-001",
            source_file="test.py",
            source_language="python",
            domain="arithmetic_operations",
            concept="addition",
            intent="Add two numbers",
            inputs=[
                {"name": "a", "type": {"base": "number"}},
                {"name": "b", "type": {"base": "number"}}
            ],
            outputs=[
                {"name": "result", "type": {"base": "number"}}
            ],
            extracted_by="AGENT-PY-TEST"
        )
        
        db_session.add(logicnode)
        db_session.commit()
        
        # Retrieve
        retrieved = db_session.query(LogicNode).filter_by(
            logicnode_id="ln-test-001"
        ).first()
        
        assert retrieved is not None
        assert retrieved.concept == "addition"
        assert len(retrieved.inputs) == 2
    
    def test_query_logicnodes_by_language(self, db_session):
        """Test querying LogicNodes by language"""
        # Create multiple LogicNodes
        for i, lang in enumerate(["python", "javascript", "python"]):
            ln = LogicNode(
                logicnode_id=f"ln-test-{i}",
                source_language=lang,
                domain="test",
                concept="test",
                intent="test",
                inputs=[],
                outputs=[],
                extracted_by="TEST"
            )
            db_session.add(ln)
        
        db_session.commit()
        
        # Query Python LogicNodes
        python_nodes = db_session.query(LogicNode).filter_by(
            source_language="python"
        ).all()
        
        assert len(python_nodes) == 2
```

### 3.3 API Integration Tests

**File:** `tests/integration/test_api.py`

```python
"""
Integration tests for API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

# Mock authentication for tests
TEST_TOKEN = "test_jwt_token"


class TestLogicNodesAPI:
    """Integration tests for /api/v1/logicnodes endpoints"""
    
    def test_list_logicnodes(self):
        """Test GET /api/v1/logicnodes"""
        response = client.get(
            "/api/v1/logicnodes",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_create_logicnode(self):
        """Test POST /api/v1/logicnodes"""
        data = {
            "source_file": "test.py",
            "source_language": "python",
            "domain": "arithmetic_operations",
            "concept": "addition",
            "intent": "Add two numbers",
            "inputs": [
                {"name": "a", "type": {"base": "number"}},
                {"name": "b", "type": {"base": "number"}}
            ],
            "outputs": [
                {"name": "result", "type": {"base": "number"}}
            ]
        }
        
        response = client.post(
            "/api/v1/logicnodes",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
            json=data
        )
        
        assert response.status_code == 201
        assert "logicnode_id" in response.json()
    
    def test_unauthorized_access(self):
        """Test API rejects requests without auth"""
        response = client.get("/api/v1/logicnodes")
        
        assert response.status_code == 401


class TestTasksAPI:
    """Integration tests for /api/v1/tasks endpoints"""
    
    def test_create_task(self):
        """Test POST /api/v1/tasks"""
        data = {
            "task_type": "extract_logicnodes",
            "assigned_to": "AGENT-PY-001",
            "priority": 1,
            "input_data": {
                "repo_url": "https://github.com/test/repo"
            }
        }
        
        response = client.post(
            "/api/v1/tasks",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
            json=data
        )
        
        assert response.status_code == 201
        assert "task_id" in response.json()
```

---

## 4. SYSTEM TESTING

### 4.1 End-to-End Workflow Tests

**File:** `tests/system/test_e2e_extraction_workflow.py`

```python
"""
End-to-end test for complete extraction workflow
"""

import pytest
import asyncio
from typing import List

@pytest.mark.system
@pytest.mark.asyncio
async def test_complete_extraction_workflow():
    """
    Test complete workflow:
    1. CEO receives extraction request
    2. CEO assigns to Pod A Manager
    3. Pod A Manager assigns to Python Specialist
    4. Python Specialist extracts LogicNodes
    5. Python Specialist sends to Audit
    6. Audit verifies LogicNodes
    7. Results returned to CEO
    """
    
    # Step 1: Submit extraction request via API
    from tests.helpers import create_api_client
    
    client = create_api_client()
    
    response = client.post("/api/v1/tasks", json={
        "task_type": "extract_logicnodes",
        "assigned_to": "ARCH-001",
        "input_data": {
            "source_code": """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
        }
    })
    
    task_id = response.json()["task_id"]
    
    # Step 2: Wait for workflow completion
    max_wait = 60  # seconds
    elapsed = 0
    
    while elapsed < max_wait:
        task_status = client.get(f"/api/v1/tasks/{task_id}").json()
        
        if task_status["status"] == "completed":
            break
        
        await asyncio.sleep(1)
        elapsed += 1
    
    assert task_status["status"] == "completed", "Workflow did not complete in time"
    
    # Step 3: Verify LogicNodes were extracted
    logicnodes = client.get(
        "/api/v1/logicnodes",
        params={"source_language": "python"}
    ).json()
    
    assert len(logicnodes) > 0, "No LogicNodes extracted"
    
    # Verify concepts detected
    concepts = [ln["concept"] for ln in logicnodes]
    assert "conditional" in concepts
    assert "recursion" in concepts or "function_call" in concepts
```

### 4.2 Multi-Agent Coordination Tests

**File:** `tests/system/test_pod_coordination.py`

```python
"""
Test coordination between Pod Manager and Specialists
"""

import pytest
import asyncio

@pytest.mark.system
@pytest.mark.asyncio
async def test_pod_a_fan_out_fan_in():
    """
    Test Pod A Manager coordinating multiple specialists:
    - Assign 4 tasks to 4 different specialists
    - Wait for all to complete
    - Aggregate results
    """
    
    from agents.managers.pod_a_manager import PodAManager
    from semantic_bus.redis_client import RedisClient
    
    manager = PodAManager()
    redis = RedisClient()
    
    # Create test tasks
    tasks = [
        {"language": "python", "file": "test1.py"},
        {"language": "javascript", "file": "test2.js"},
        {"language": "ruby", "file": "test3.rb"},
        {"language": "php", "file": "test4.php"}
    ]
    
    # Manager assigns tasks
    task_ids = []
    for task in tasks:
        task_id = await manager.assign_task(task)
        task_ids.append(task_id)
    
    # Wait for all tasks to complete
    timeout = 30
    start = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - start < timeout:
        statuses = [manager.get_task_status(tid) for tid in task_ids]
        
        if all(s == "completed" for s in statuses):
            break
        
        await asyncio.sleep(0.5)
    
    # Verify all completed
    final_statuses = [manager.get_task_status(tid) for tid in task_ids]
    assert all(s == "completed" for s in final_statuses)
```

---

## 5. PERFORMANCE TESTING

### 5.1 Load Testing with Locust

**File:** `tests/performance/locustfile.py`

```python
"""
Load testing for Holy Grail Refinery API
"""

from locust import HttpUser, task, between
import random

class HGRUser(HttpUser):
    """Simulated API user"""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Login and get token"""
        response = self.client.post("/auth/login", json={
            "username": "test_user",
            "password": "test_pass"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)  # Weight: 3x more likely than other tasks
    def list_logicnodes(self):
        """List LogicNodes"""
        self.client.get(
            "/api/v1/logicnodes",
            headers=self.headers,
            params={"limit": 50}
        )
    
    @task(2)
    def get_specific_logicnode(self):
        """Get specific LogicNode"""
        logicnode_id = f"ln-{random.randint(1, 1000):06d}"
        self.client.get(
            f"/api/v1/logicnodes/{logicnode_id}",
            headers=self.headers
        )
    
    @task(1)
    def create_task(self):
        """Create extraction task"""
        self.client.post(
            "/api/v1/tasks",
            headers=self.headers,
            json={
                "task_type": "extract_logicnodes",
                "assigned_to": "AGENT-PY-001",
                "input_data": {"source": "test"}
            }
        )
```

**Run load test:**

```bash
# 100 users, spawn 10/second
locust -f tests/performance/locustfile.py \
  --host http://localhost:8000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m
```

### 5.2 Benchmark Tests

**File:** `tests/performance/test_benchmarks.py`

```python
"""
Performance benchmarks for critical operations
"""

import pytest
import time
from agents.pod_a.python_agent import PythonAgent

@pytest.mark.benchmark
def test_logicnode_extraction_speed():
    """Benchmark LogicNode extraction speed"""
    
    agent = PythonAgent()
    
    source_code = """
def complex_function(x, y, z):
    result = []
    for i in range(x):
        if i % 2 == 0:
            result.append(i * y)
        else:
            result.append(i + z)
    return result
"""
    
    # Run 100 extractions
    start = time.time()
    
    for _ in range(100):
        agent.extract_logicnode(source_code)
    
    elapsed = time.time() - start
    avg_time = elapsed / 100
    
    # Should extract at least 10 LogicNodes per second
    assert avg_time < 0.1, f"Extraction too slow: {avg_time:.3f}s per extraction"


@pytest.mark.benchmark
def test_database_query_performance():
    """Benchmark database query performance"""
    from database.connection import get_logicnode_session
    from database.models.logicnode import LogicNode
    
    db = next(get_logicnode_session())
    
    # Query 1000 LogicNodes
    start = time.time()
    
    results = db.query(LogicNode).limit(1000).all()
    
    elapsed = time.time() - start
    
    # Should complete in under 100ms
    assert elapsed < 0.1, f"Query too slow: {elapsed:.3f}s"
```

---

## 6. SECURITY TESTING

### 6.1 Security Vulnerability Scanning

**File:** `.github/workflows/security.yml`

```yaml
name: Security Scan

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  security:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      # Python security scan
      - name: Run Bandit
        run: |
          pip install bandit
          bandit -r agents/ api/ -f json -o bandit-report.json
      
      # Dependency vulnerability scan
      - name: Run Safety
        run: |
          pip install safety
          safety check --json > safety-report.json
      
      # Container security scan
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'hgr-api:latest'
          format: 'sarif'
          output: 'trivy-results.sarif'
      
      # Upload results
      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: trivy-results.sarif
```

### 6.2 Penetration Testing

**File:** `tests/security/test_api_security.py`

```python
"""
Security tests for API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


class TestAPISecurity:
    """Security tests for API"""
    
    def test_sql_injection_prevention(self):
        """Test API prevents SQL injection"""
        malicious_input = "'; DROP TABLE logicnodes; --"
        
        response = client.get(
            "/api/v1/logicnodes",
            params={"language": malicious_input}
        )
        
        # Should return 400 or 422, not 500
        assert response.status_code in [200, 400, 422]
    
    def test_xss_prevention(self):
        """Test API sanitizes HTML/JS input"""
        malicious_input = "<script>alert('xss')</script>"
        
        response = client.post(
            "/api/v1/logicnodes",
            json={
                "concept": malicious_input,
                "domain": "test",
                "intent": "test"
            }
        )
        
        # Should reject or sanitize
        if response.status_code == 201:
            data = response.json()
            assert "<script>" not in data.get("concept", "")
    
    def test_rate_limiting(self):
        """Test rate limiting works"""
        
        # Make 150 requests rapidly (exceed limit of 100)
        responses = []
        for _ in range(150):
            response = client.get("/api/v1/logicnodes")
            responses.append(response.status_code)
        
        # Should see 429 (Too Many Requests)
        assert 429 in responses
    
    def test_unauthorized_access_blocked(self):
        """Test protected endpoints require auth"""
        response = client.delete("/api/v1/logicnodes/ln-test")
        
        assert response.status_code == 401
```

---

## 7. TEST DATA MANAGEMENT

### 7.1 Test Fixtures

**File:** `tests/fixtures/logicnodes.py`

```python
"""
Test fixtures for LogicNodes
"""

SAMPLE_LOGICNODES = [
    {
        "logicnode_id": "ln-test-001",
        "source_language": "python",
        "domain": "arithmetic_operations",
        "concept": "addition",
        "intent": "Add two numbers",
        "inputs": [
            {"name": "a", "type": {"base": "number"}},
            {"name": "b", "type": {"base": "number"}}
        ],
        "outputs": [
            {"name": "result", "type": {"base": "number"}}
        ]
    },
    {
        "logicnode_id": "ln-test-002",
        "source_language": "python",
        "domain": "control_flow",
        "concept": "conditional",
        "intent": "Branch execution based on condition",
        "inputs": [
            {"name": "condition", "type": {"base": "boolean"}}
        ],
        "outputs": [
            {"name": "branch_taken", "type": {"base": "string"}}
        ]
    }
]


def get_sample_logicnode(index=0):
    """Get a sample LogicNode for testing"""
    return SAMPLE_LOGICNODES[index].copy()
```

### 7.2 Database Seeding

**File:** `tests/helpers/seed_database.py`

```python
"""
Seed test database with sample data
"""

from database.connection import get_logicnode_session
from database.models.logicnode import LogicNode

def seed_test_database():
    """Populate test database with sample LogicNodes"""
    db = next(get_logicnode_session())
    
    sample_data = [
        # Add 100 sample LogicNodes across all languages
        LogicNode(
            logicnode_id=f"ln-test-{i:04d}",
            source_language=["python", "javascript", "rust", "java"][i % 4],
            domain="test_domain",
            concept="test_concept",
            intent="Test LogicNode",
            inputs=[],
            outputs=[],
            extracted_by="TEST"
        )
        for i in range(100)
    ]
    
    db.bulk_save_objects(sample_data)
    db.commit()
```

---

## 8. CONTINUOUS INTEGRATION

### 8.1 GitHub Actions CI Pipeline

**File:** `.github/workflows/ci.yml`

```yaml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pass
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7.2
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run linters
        run: |
          flake8 agents/ api/
          black --check agents/ api/
          mypy agents/ api/
      
      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --cov=agents --cov=api --cov-report=xml
        env:
          DATABASE_URL: postgresql://test_user:test_pass@localhost/test_db
          REDIS_URL: redis://localhost:6379
      
      - name: Run integration tests
        run: |
          pytest tests/integration/ -v
        env:
          DATABASE_URL: postgresql://test_user:test_pass@localhost/test_db
          REDIS_URL: redis://localhost:6379
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true
      
      - name: Build Docker images
        run: |
          docker build -t hgr-api:test ./api
      
      - name: Run system tests
        run: |
          docker-compose -f docker-compose.test.yml up -d
          sleep 10
          pytest tests/system/ -v
          docker-compose -f docker-compose.test.yml down
```

### 8.2 Pre-commit Hooks

**File:** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
  
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=100']
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

---

## 9. QUALITY METRICS

### 9.1 Coverage Requirements

```python
# pytest.ini
[pytest]
minversion = 7.0
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Coverage settings
addopts = 
    --cov-fail-under=90
    --cov-report=html
    --cov-report=term-missing
    --strict-markers
    -v

markers =
    unit: Unit tests
    integration: Integration tests
    system: System/E2E tests
    benchmark: Performance benchmarks
```

### 9.2 Quality Gates

| Metric | Threshold | Enforcement |
|--------|-----------|-------------|
| **Code Coverage** | ≥ 90% | CI fails if below |
| **Test Pass Rate** | 100% | CI fails if any test fails |
| **Lint Score** | 10/10 | CI fails if < 9.5 |
| **Type Coverage** | ≥ 95% | Warning if below |
| **Performance Regression** | < 5% | Warning if exceeded |
| **Security Vulnerabilities** | 0 critical/high | CI fails if found |

### 9.3 Test Metrics Dashboard

```python
# Generate test report
pytest tests/ --html=report.html --self-contained-html

# Metrics to track:
# - Total tests: 1,247
# - Pass rate: 99.8%
# - Average execution time: 12.3s
# - Code coverage: 91.2%
# - Flaky tests: 2
```

---

## 10. TESTING TOOLS & FRAMEWORKS

### 10.1 Test Stack

| Tool | Purpose | Version |
|------|---------|---------|
| **pytest** | Test runner | 7.4+ |
| **pytest-cov** | Coverage reporting | 4.1+ |
| **pytest-asyncio** | Async test support | 0.21+ |
| **pytest-xdist** | Parallel test execution | 3.3+ |
| **Locust** | Load testing | 2.15+ |
| **Bandit** | Security scanning | 1.7+ |
| **Safety** | Dependency vulnerabilities | 2.3+ |
| **Trivy** | Container scanning | Latest |
| **Black** | Code formatting | 23.3+ |
| **Flake8** | Linting | 6.0+ |
| **mypy** | Type checking | 1.3+ |

### 10.2 Test Execution Commands

```bash
# Run all tests
make test

# Run specific test category
make test-unit
make test-integration
make test-system

# Run with coverage
make test-coverage

# Run performance tests
make test-performance

# Run security tests
make test-security

# Run tests in watch mode
ptw tests/ -- -v
```

---

## DOCUMENT METADATA

**Document ID:** 23  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Owner:** Chief Architect  
**Dependencies:** Documents 19-22  
**Next Document:** 24 (CI/CD Pipeline Configuration)

---

*End of Testing Framework & Quality Assurance*
