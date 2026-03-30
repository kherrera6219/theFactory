# DOCUMENT 41: UNIT TESTING STANDARDS & IMPLEMENTATION
## Holy Grail Refinery - Quality & Testing

**Document ID:** 41  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive unit testing standards and implementation guidelines** for the Holy Grail Refinery system. Given the system's 99.9999% accuracy target (0.0001% tolerance), rigorous unit testing is the foundation of quality assurance.

**Unit Testing Philosophy:**
- 🎯 **Fast:** Tests execute in milliseconds, entire suite < 5 minutes
- 🔄 **Isolated:** No dependencies on external services, databases, or network
- ✅ **Deterministic:** Same input always produces same output
- 📊 **Comprehensive:** 90%+ code coverage for all agents
- 🔍 **Focused:** One logical assertion per test

**Key Standards:**
- **Framework:** pytest 7.4+ with pytest-asyncio for async code
- **Coverage Target:** ≥ 90% line coverage, ≥ 85% branch coverage
- **Test Structure:** Arrange-Act-Assert (AAA) pattern
- **Naming Convention:** `test_<function>_<scenario>_<expected_result>`
- **Mock Strategy:** Dependency injection with pytest fixtures

**Quality Gates:**
- ✅ All unit tests must pass (100% pass rate)
- ✅ Coverage threshold enforced in CI
- ✅ No skipped tests without documented justification
- ✅ Test execution time < 5 minutes for full suite

---

## TABLE OF CONTENTS

1. [Unit Testing Architecture](#1-unit-testing-architecture)
2. [Test Structure & Organization](#2-test-structure--organization)
3. [Writing Effective Unit Tests](#3-writing-effective-unit-tests)
4. [Mocking & Test Doubles](#4-mocking--test-doubles)
5. [Async Testing Patterns](#5-async-testing-patterns)
6. [LogicNode Testing](#6-logicnode-testing)
7. [Agent Testing Patterns](#7-agent-testing-patterns)
8. [Test Fixtures & Utilities](#8-test-fixtures--utilities)
9. [Coverage Requirements & Enforcement](#9-coverage-requirements--enforcement)
10. [Continuous Testing Integration](#10-continuous-testing-integration)

---

## 1. UNIT TESTING ARCHITECTURE

### 1.1 Test Directory Structure

```
tests/
├── unit/
│   ├── __init__.py
│   ├── conftest.py                 # Shared fixtures
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── test_base_agent.py
│   │   ├── test_python_agent.py
│   │   ├── test_javascript_agent.py
│   │   ├── test_manager_agent.py
│   │   └── test_audit_agent.py
│   │
│   ├── logicnodes/
│   │   ├── __init__.py
│   │   ├── test_logicnode_validation.py
│   │   ├── test_logicnode_types.py
│   │   ├── test_logicnode_constraints.py
│   │   └── test_logicnode_transformations.py
│   │
│   ├── protocols/
│   │   ├── __init__.py
│   │   ├── test_protocol_alpha.py
│   │   ├── test_protocol_beta.py
│   │   └── test_message_schemas.py
│   │
│   ├── semantic_bus/
│   │   ├── __init__.py
│   │   ├── test_message_routing.py
│   │   ├── test_message_serialization.py
│   │   └── test_bus_operations.py
│   │
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── test_python_parser.py
│   │   ├── test_javascript_parser.py
│   │   └── test_ast_analysis.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── test_type_inference.py
│       ├── test_code_normalization.py
│       └── test_hash_functions.py
│
├── integration/
├── system/
└── performance/
```

### 1.2 Pytest Configuration

**File:** `pytest.ini`

```ini
[pytest]
# Minimum pytest version
minversion = 7.4

# Test discovery
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Output options
addopts = 
    # Verbose output
    -v
    # Show extra test summary info
    -ra
    # Strict mode (warnings as errors)
    --strict-markers
    --strict-config
    # Coverage
    --cov=agents
    --cov=logicnodes
    --cov=semantic_bus
    --cov=parsers
    --cov=utils
    --cov-report=html:htmlcov
    --cov-report=term-missing
    --cov-report=xml:coverage.xml
    # Fail if coverage below threshold
    --cov-fail-under=90
    # Parallel execution
    -n auto
    # Show slowest tests
    --durations=10
    # Disable warnings
    -W ignore::DeprecationWarning

# Test markers
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, uses external services)
    system: End-to-end system tests
    slow: Tests that take > 1 second
    asyncio: Async tests
    benchmark: Performance benchmarks

# Timeout for tests
timeout = 300

# Asyncio mode
asyncio_mode = auto
```

### 1.3 Dependencies

**File:** `requirements-test.txt`

```txt
# Testing framework
pytest==7.4.3
pytest-cov==4.1.0
pytest-asyncio==0.21.1
pytest-xdist==3.5.0
pytest-timeout==2.2.0
pytest-mock==3.12.0

# Code quality
black==23.12.1
flake8==7.0.0
mypy==1.8.0
pylint==3.0.3

# Type stubs
types-redis==4.6.0.11
types-requests==2.31.0.10

# Test utilities
faker==21.0.0
factory-boy==3.3.0
freezegun==1.4.0
responses==0.24.1
```

---

## 2. TEST STRUCTURE & ORGANIZATION

### 2.1 AAA Pattern (Arrange-Act-Assert)

**Example:**

```python
"""
Unit tests for LogicNode validation
"""

import pytest
from logicnodes.models import LogicNode
from logicnodes.validation import validate_logicnode

def test_validate_logicnode_with_valid_data_succeeds():
    """
    Test that validate_logicnode returns True for valid LogicNode
    """
    # ARRANGE: Create a valid LogicNode
    logicnode = LogicNode(
        intent="Add two numbers",
        domain="arithmetic_operations",
        concept="addition",
        inputs=[
            {"name": "a", "type": {"base": "number"}},
            {"name": "b", "type": {"base": "number"}}
        ],
        outputs=[
            {"name": "result", "type": {"base": "number"}}
        ],
        side_effects=[],
        preconditions=[],
        postconditions=[]
    )
    
    # ACT: Validate the LogicNode
    result = validate_logicnode(logicnode)
    
    # ASSERT: Validation should succeed
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_validate_logicnode_with_missing_intent_fails():
    """
    Test that validate_logicnode fails when intent is missing
    """
    # ARRANGE
    logicnode = LogicNode(
        intent="",  # Empty intent (invalid)
        domain="arithmetic_operations",
        concept="addition",
        inputs=[{"name": "a", "type": {"base": "number"}}],
        outputs=[{"name": "result", "type": {"base": "number"}}]
    )
    
    # ACT
    result = validate_logicnode(logicnode)
    
    # ASSERT
    assert result.is_valid is False
    assert "intent" in result.errors[0].field
    assert "required" in result.errors[0].message.lower()
```

### 2.2 Test Naming Convention

**Pattern:** `test_<function>_<scenario>_<expected_result>`

**Examples:**

```python
# Good names (descriptive and clear)
def test_add_numbers_with_positive_integers_returns_sum()
def test_parse_python_function_with_invalid_syntax_raises_syntax_error()
def test_send_message_to_offline_agent_retries_three_times()
def test_validate_type_constraint_with_incompatible_types_returns_false()

# Bad names (vague or unclear)
def test_add()  # Too vague
def test_parse_function_1()  # Numbered tests are unclear
def test_error()  # Doesn't describe scenario
def test_agent()  # Too broad
```

### 2.3 Test Organization

**One concept per test:**

```python
# ✅ GOOD: Separate tests for each scenario
def test_divide_with_positive_numbers_returns_quotient():
    assert divide(10, 2) == 5

def test_divide_with_zero_denominator_raises_value_error():
    with pytest.raises(ValueError):
        divide(10, 0)

def test_divide_with_negative_numbers_returns_negative_quotient():
    assert divide(-10, 2) == -5

# ❌ BAD: Multiple concepts in one test
def test_divide():
    assert divide(10, 2) == 5  # Multiple assertions
    with pytest.raises(ValueError):
        divide(10, 0)
    assert divide(-10, 2) == -5
```

---

## 3. WRITING EFFECTIVE UNIT TESTS

### 3.1 Test Independence

**Each test should be fully independent:**

```python
# ✅ GOOD: Tests don't share state
def test_agent_state_initialization():
    agent = PythonAgent(agent_id="TEST-001")
    assert agent.state == AgentState.IDLE

def test_agent_state_after_task_assignment():
    agent = PythonAgent(agent_id="TEST-002")
    agent.assign_task(Task(task_id="T001"))
    assert agent.state == AgentState.WORKING

# ❌ BAD: Tests depend on shared state
agent = PythonAgent(agent_id="SHARED-001")  # Module-level variable

def test_initial_state():
    assert agent.state == AgentState.IDLE

def test_state_after_assignment():
    # This test depends on test_initial_state running first!
    agent.assign_task(Task(task_id="T001"))
    assert agent.state == AgentState.WORKING
```

### 3.2 Testing Edge Cases

**Always test boundary conditions:**

```python
def test_parse_code_with_empty_string_returns_empty_ast():
    """Test edge case: empty input"""
    result = parse_code("")
    assert result.ast is None or result.ast == []

def test_parse_code_with_single_line_returns_valid_ast():
    """Test edge case: minimal valid input"""
    result = parse_code("x = 1")
    assert result.ast is not None

def test_parse_code_with_max_size_succeeds():
    """Test edge case: maximum allowed input size"""
    code = "x = 1\n" * 10000  # 10k lines
    result = parse_code(code)
    assert result.ast is not None

def test_parse_code_exceeding_max_size_raises_error():
    """Test edge case: input exceeds limit"""
    code = "x = 1\n" * 100000  # Too large
    with pytest.raises(CodeTooLargeError):
        parse_code(code)
```

### 3.3 Testing Error Conditions

**Test both success and failure paths:**

```python
def test_create_logicnode_with_valid_data_succeeds():
    """Happy path test"""
    logicnode = create_logicnode(
        intent="Test intent",
        domain="test_domain"
    )
    assert logicnode is not None
    assert logicnode.intent == "Test intent"

def test_create_logicnode_with_invalid_domain_raises_value_error():
    """Error path test"""
    with pytest.raises(ValueError, match="Invalid domain"):
        create_logicnode(
            intent="Test intent",
            domain="invalid_domain"
        )

def test_create_logicnode_with_missing_intent_raises_value_error():
    """Error path test"""
    with pytest.raises(ValueError, match="intent.*required"):
        create_logicnode(
            intent="",
            domain="test_domain"
        )
```

### 3.4 Parametrized Tests

**Use pytest.mark.parametrize for multiple test cases:**

```python
import pytest

@pytest.mark.parametrize(
    "input_type,expected_base_type",
    [
        ({"base": "number"}, "number"),
        ({"base": "string"}, "string"),
        ({"base": "boolean"}, "boolean"),
        ({"base": "array", "element_type": {"base": "number"}}, "array"),
    ]
)
def test_parse_type_annotation_returns_correct_base_type(
    input_type, expected_base_type
):
    """Test type parsing with various type annotations"""
    result = parse_type_annotation(input_type)
    assert result.base == expected_base_type


@pytest.mark.parametrize(
    "code,expected_domain,expected_concept",
    [
        ("x = a + b", "arithmetic_operations", "addition"),
        ("x = a - b", "arithmetic_operations", "subtraction"),
        ("x = a * b", "arithmetic_operations", "multiplication"),
        ("x = a / b", "arithmetic_operations", "division"),
    ]
)
def test_classify_operation_identifies_correct_concept(
    code, expected_domain, expected_concept
):
    """Test operation classification"""
    result = classify_operation(code)
    assert result.domain == expected_domain
    assert result.concept == expected_concept
```

---

## 4. MOCKING & TEST DOUBLES

### 4.1 Using pytest-mock

**File:** `tests/unit/agents/test_python_agent.py`

```python
"""
Unit tests for PythonAgent with mocking
"""

import pytest
from agents.specialists.python_agent import PythonAgent
from logicnodes.models import LogicNode

@pytest.fixture
def mock_semantic_bus(mocker):
    """Mock the Semantic Bus for isolated testing"""
    return mocker.patch('agents.specialists.python_agent.SemanticBus')

@pytest.fixture
def mock_knowledge_lake(mocker):
    """Mock the Knowledge Lake"""
    return mocker.patch('agents.specialists.python_agent.KnowledgeLake')

def test_extract_logicnodes_queries_knowledge_lake(
    mock_semantic_bus,
    mock_knowledge_lake
):
    """
    Test that extract_logicnodes queries Knowledge Lake
    """
    # ARRANGE
    agent = PythonAgent(agent_id="AGENT-PY-001")
    code = "def add(a, b): return a + b"
    
    # Configure mock to return empty results
    mock_knowledge_lake.query.return_value = []
    
    # ACT
    agent.extract_logicnodes(code)
    
    # ASSERT
    mock_knowledge_lake.query.assert_called_once()
    call_args = mock_knowledge_lake.query.call_args
    assert "addition" in str(call_args)


def test_send_to_audit_publishes_to_semantic_bus(
    mock_semantic_bus,
    mock_knowledge_lake
):
    """
    Test that send_to_audit publishes message to Semantic Bus
    """
    # ARRANGE
    agent = PythonAgent(agent_id="AGENT-PY-001")
    logicnode = LogicNode(
        intent="Test intent",
        domain="test_domain",
        concept="test_concept"
    )
    
    # ACT
    agent.send_to_audit(logicnode)
    
    # ASSERT
    mock_semantic_bus.publish.assert_called_once()
    message = mock_semantic_bus.publish.call_args[0][0]
    assert message.target == "AUDIT-LEAD-001"
    assert "logicnode" in message.payload
```

### 4.2 Dependency Injection Pattern

**File:** `agents/base_agent.py`

```python
"""
Base agent with dependency injection for testability
"""

from typing import Protocol
from dataclasses import dataclass

class SemanticBusProtocol(Protocol):
    """Interface for Semantic Bus (for testing)"""
    def publish(self, message: dict) -> None: ...
    def subscribe(self, channel: str) -> None: ...

class KnowledgeLakeProtocol(Protocol):
    """Interface for Knowledge Lake (for testing)"""
    def query(self, query: str) -> list: ...

@dataclass
class BaseAgent:
    """
    Base agent with injected dependencies
    """
    agent_id: str
    semantic_bus: SemanticBusProtocol
    knowledge_lake: KnowledgeLakeProtocol
    
    def send_message(self, target: str, payload: dict):
        """Send message via Semantic Bus"""
        self.semantic_bus.publish({
            "from": self.agent_id,
            "to": target,
            "payload": payload
        })
```

**Test with injected mocks:**

```python
def test_send_message_with_injected_mock():
    """Test BaseAgent.send_message with mock Semantic Bus"""
    # ARRANGE
    mock_bus = Mock(spec=SemanticBusProtocol)
    mock_lake = Mock(spec=KnowledgeLakeProtocol)
    
    agent = BaseAgent(
        agent_id="TEST-001",
        semantic_bus=mock_bus,
        knowledge_lake=mock_lake
    )
    
    # ACT
    agent.send_message("TARGET-001", {"key": "value"})
    
    # ASSERT
    mock_bus.publish.assert_called_once_with({
        "from": "TEST-001",
        "to": "TARGET-001",
        "payload": {"key": "value"}
    })
```

### 4.3 Fixture-based Mocking

**File:** `tests/unit/conftest.py`

```python
"""
Shared fixtures for unit tests
"""

import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis_mock = Mock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.publish.return_value = 1
    return redis_mock

@pytest.fixture
def mock_postgres():
    """Mock PostgreSQL connection"""
    conn_mock = Mock()
    cursor_mock = Mock()
    cursor_mock.fetchall.return_value = []
    cursor_mock.fetchone.return_value = None
    conn_mock.cursor.return_value = cursor_mock
    return conn_mock

@pytest.fixture
def sample_logicnode():
    """Sample LogicNode for testing"""
    return LogicNode(
        intent="Add two numbers",
        domain="arithmetic_operations",
        concept="addition",
        inputs=[
            {"name": "a", "type": {"base": "number"}},
            {"name": "b", "type": {"base": "number"}}
        ],
        outputs=[
            {"name": "result", "type": {"base": "number"}}
        ]
    )
```

---

## 5. ASYNC TESTING PATTERNS

### 5.1 Basic Async Tests

**File:** `tests/unit/agents/test_async_agent.py`

```python
"""
Unit tests for async agent operations
"""

import pytest
import asyncio

@pytest.mark.asyncio
async def test_process_task_async_completes_successfully():
    """Test async task processing"""
    # ARRANGE
    agent = AsyncPythonAgent(agent_id="ASYNC-001")
    task = Task(task_id="T001", payload={"code": "x = 1"})
    
    # ACT
    result = await agent.process_task(task)
    
    # ASSERT
    assert result.status == "completed"
    assert result.task_id == "T001"

@pytest.mark.asyncio
async def test_concurrent_task_processing():
    """Test processing multiple tasks concurrently"""
    # ARRANGE
    agent = AsyncPythonAgent(agent_id="ASYNC-001")
    tasks = [
        Task(task_id=f"T{i:03d}", payload={"code": f"x = {i}"})
        for i in range(10)
    ]
    
    # ACT
    results = await asyncio.gather(*[
        agent.process_task(task) for task in tasks
    ])
    
    # ASSERT
    assert len(results) == 10
    assert all(r.status == "completed" for r in results)
```

### 5.2 Async Mocking

```python
@pytest.mark.asyncio
async def test_async_api_call_with_mock(mocker):
    """Test async API call with mocked HTTP client"""
    # ARRANGE
    mock_client = mocker.AsyncMock()
    mock_client.post.return_value = {
        "logicnode_id": "LN001",
        "status": "created"
    }
    
    agent = AsyncPythonAgent(
        agent_id="ASYNC-001",
        api_client=mock_client
    )
    
    logicnode = LogicNode(intent="Test", domain="test")
    
    # ACT
    result = await agent.save_logicnode(logicnode)
    
    # ASSERT
    assert result["logicnode_id"] == "LN001"
    mock_client.post.assert_awaited_once()
```

### 5.3 Testing Timeouts

```python
@pytest.mark.asyncio
async def test_task_processing_with_timeout():
    """Test that long-running task times out"""
    # ARRANGE
    agent = AsyncPythonAgent(agent_id="ASYNC-001")
    
    async def slow_task():
        await asyncio.sleep(10)  # 10 seconds
    
    # ACT & ASSERT
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_task(), timeout=1.0)
```

---

## 6. LOGICNODE TESTING

### 6.1 LogicNode Validation Tests

**File:** `tests/unit/logicnodes/test_logicnode_validation.py`

```python
"""
Comprehensive tests for LogicNode validation
"""

import pytest
from logicnodes.models import LogicNode
from logicnodes.validation import (
    validate_logicnode,
    validate_type_constraints,
    validate_preconditions
)

class TestLogicNodeValidation:
    """Test suite for LogicNode validation"""
    
    def test_valid_logicnode_passes_all_checks(self):
        """Test that a fully valid LogicNode passes validation"""
        logicnode = LogicNode(
            intent="Add two numbers and return the sum",
            domain="arithmetic_operations",
            concept="addition",
            inputs=[
                {"name": "a", "type": {"base": "number"}},
                {"name": "b", "type": {"base": "number"}}
            ],
            outputs=[
                {"name": "result", "type": {"base": "number"}}
            ],
            preconditions=[
                {"type": "type_check", "constraint": "all_numeric"}
            ],
            postconditions=[
                {"type": "type_check", "constraint": "numeric_result"}
            ],
            side_effects=[]
        )
        
        result = validate_logicnode(logicnode)
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
    
    def test_logicnode_missing_intent_fails_validation(self):
        """Test that LogicNode without intent fails"""
        logicnode = LogicNode(
            intent="",  # Empty intent
            domain="arithmetic_operations",
            concept="addition",
            inputs=[{"name": "a", "type": {"base": "number"}}],
            outputs=[{"name": "result", "type": {"base": "number"}}]
        )
        
        result = validate_logicnode(logicnode)
        
        assert not result.is_valid
        assert any("intent" in e.field for e in result.errors)
    
    @pytest.mark.parametrize("invalid_domain", [
        "",
        "invalid_domain",
        "UPPERCASE_DOMAIN",
        "domain-with-dashes",
        "domain with spaces"
    ])
    def test_logicnode_with_invalid_domain_fails(self, invalid_domain):
        """Test that invalid domain names fail validation"""
        logicnode = LogicNode(
            intent="Test",
            domain=invalid_domain,
            concept="test",
            inputs=[],
            outputs=[]
        )
        
        result = validate_logicnode(logicnode)
        
        assert not result.is_valid
        assert any("domain" in e.field for e in result.errors)


class TestTypeConstraintValidation:
    """Test suite for type constraint validation"""
    
    def test_compatible_types_pass_validation(self):
        """Test that compatible type constraints pass"""
        input_type = {"base": "number"}
        constraint = {"allowed_types": ["number", "integer"]}
        
        result = validate_type_constraints(input_type, constraint)
        
        assert result.is_valid
    
    def test_incompatible_types_fail_validation(self):
        """Test that incompatible types fail"""
        input_type = {"base": "string"}
        constraint = {"allowed_types": ["number", "integer"]}
        
        result = validate_type_constraints(input_type, constraint)
        
        assert not result.is_valid
        assert "type mismatch" in result.error.lower()
```

### 6.2 LogicNode Transformation Tests

**File:** `tests/unit/logicnodes/test_logicnode_transformations.py`

```python
"""
Tests for LogicNode transformations and optimizations
"""

def test_merge_logicnodes_combines_equivalent_nodes():
    """Test merging of semantically equivalent LogicNodes"""
    # ARRANGE
    node1 = LogicNode(
        intent="Add a and b",
        domain="arithmetic_operations",
        concept="addition",
        inputs=[
            {"name": "a", "type": {"base": "number"}},
            {"name": "b", "type": {"base": "number"}}
        ],
        outputs=[{"name": "result", "type": {"base": "number"}}]
    )
    
    node2 = LogicNode(
        intent="Sum two numbers",  # Different intent, same semantics
        domain="arithmetic_operations",
        concept="addition",
        inputs=[
            {"name": "x", "type": {"base": "number"}},
            {"name": "y", "type": {"base": "number"}}
        ],
        outputs=[{"name": "sum", "type": {"base": "number"}}]
    )
    
    # ACT
    merged = merge_logicnodes([node1, node2])
    
    # ASSERT
    assert len(merged) == 1
    assert merged[0].concept == "addition"


def test_normalize_logicnode_standardizes_structure():
    """Test LogicNode normalization"""
    # ARRANGE
    node = LogicNode(
        intent="Add a and b",
        domain="arithmetic_operations",
        concept="addition",
        inputs=[
            {"name": "num1", "type": {"base": "number"}},
            {"name": "num2", "type": {"base": "number"}}
        ],
        outputs=[{"name": "result", "type": {"base": "number"}}]
    )
    
    # ACT
    normalized = normalize_logicnode(node)
    
    # ASSERT
    # Inputs should be renamed to standard names
    assert normalized.inputs[0]["name"] == "a"
    assert normalized.inputs[1]["name"] == "b"
    assert normalized.outputs[0]["name"] == "result"
```

---

## 7. AGENT TESTING PATTERNS

### 7.1 Testing Language Specialist Agents

**File:** `tests/unit/agents/test_python_specialist.py`

```python
"""
Unit tests for Python Language Specialist Agent
"""

import pytest
from agents.specialists.python_agent import PythonAgent
from parsers.python_parser import PythonParser

class TestPythonAgentCodeParsing:
    """Test Python code parsing functionality"""
    
    def test_parse_simple_function_extracts_correct_structure(self):
        """Test parsing of simple Python function"""
        # ARRANGE
        agent = PythonAgent(agent_id="AGENT-PY-001")
        code = """
def add(a, b):
    return a + b
"""
        
        # ACT
        ast = agent.parse_code(code)
        
        # ASSERT
        assert ast is not None
        assert len(ast.body) == 1
        assert ast.body[0].name == "add"
        assert len(ast.body[0].args.args) == 2
    
    def test_parse_code_with_imports_preserves_dependencies(self):
        """Test that imports are correctly parsed"""
        agent = PythonAgent(agent_id="AGENT-PY-001")
        code = """
import numpy as np
from typing import List

def process_array(data: List[int]) -> np.ndarray:
    return np.array(data)
"""
        
        ast = agent.parse_code(code)
        
        imports = [node for node in ast.body if node.__class__.__name__ == 'Import']
        from_imports = [node for node in ast.body if node.__class__.__name__ == 'ImportFrom']
        
        assert len(imports) == 1
        assert len(from_imports) == 1
        assert imports[0].names[0].name == "numpy"


class TestPythonAgentLogicNodeExtraction:
    """Test LogicNode extraction from Python code"""
    
    def test_extract_logicnode_from_addition_function(self):
        """Test extraction of addition LogicNode"""
        agent = PythonAgent(agent_id="AGENT-PY-001")
        code = """
def add(a: int, b: int) -> int:
    '''Add two numbers and return the sum'''
    return a + b
"""
        
        logicnodes = agent.extract_logicnodes(code)
        
        assert len(logicnodes) == 1
        ln = logicnodes[0]
        assert ln.domain == "arithmetic_operations"
        assert ln.concept == "addition"
        assert len(ln.inputs) == 2
        assert ln.inputs[0]["name"] == "a"
        assert ln.inputs[1]["name"] == "b"
        assert len(ln.outputs) == 1
        assert ln.outputs[0]["name"] == "result"
```

### 7.2 Testing Manager Agents

**File:** `tests/unit/agents/test_manager_agent.py`

```python
"""
Unit tests for Manager agents
"""

def test_manager_assigns_task_to_appropriate_specialist():
    """Test that manager routes tasks correctly"""
    # ARRANGE
    manager = PodAManager(agent_id="MANAGER-POD-A-001")
    
    task = Task(
        task_id="T001",
        type="extract_logicnodes",
        language="python",
        payload={"code": "def add(a, b): return a + b"}
    )
    
    # Mock the specialists
    python_specialist = Mock(spec=PythonAgent)
    javascript_specialist = Mock(spec=JavaScriptAgent)
    
    manager.register_specialist("python", python_specialist)
    manager.register_specialist("javascript", javascript_specialist)
    
    # ACT
    manager.assign_task(task)
    
    # ASSERT
    python_specialist.process_task.assert_called_once_with(task)
    javascript_specialist.process_task.assert_not_called()


def test_manager_load_balances_across_specialists():
    """Test load balancing when multiple specialists available"""
    manager = PodAManager(agent_id="MANAGER-POD-A-001")
    
    # Register two Python specialists
    py_specialist_1 = Mock(spec=PythonAgent, current_load=5)
    py_specialist_2 = Mock(spec=PythonAgent, current_load=2)
    
    manager.register_specialist("python", py_specialist_1)
    manager.register_specialist("python", py_specialist_2)
    
    task = Task(task_id="T001", type="extract", language="python")
    
    # ACT
    manager.assign_task(task)
    
    # ASSERT
    # Should assign to specialist with lower load
    py_specialist_2.process_task.assert_called_once()
    py_specialist_1.process_task.assert_not_called()
```

---

## 8. TEST FIXTURES & UTILITIES

### 8.1 Common Fixtures

**File:** `tests/unit/conftest.py`

```python
"""
Shared fixtures for all unit tests
"""

import pytest
from pathlib import Path

@pytest.fixture
def sample_python_code():
    """Sample Python code for testing"""
    return """
def add(a: int, b: int) -> int:
    '''Add two numbers'''
    return a + b

def subtract(a: int, b: int) -> int:
    '''Subtract b from a'''
    return a - b
"""

@pytest.fixture
def sample_javascript_code():
    """Sample JavaScript code for testing"""
    return """
function add(a, b) {
    return a + b;
}

const multiply = (a, b) => a * b;
"""

@pytest.fixture
def test_data_dir():
    """Path to test data directory"""
    return Path(__file__).parent / "test_data"

@pytest.fixture
def sample_logicnode_dict():
    """Sample LogicNode as dictionary"""
    return {
        "intent": "Add two numbers",
        "domain": "arithmetic_operations",
        "concept": "addition",
        "inputs": [
            {"name": "a", "type": {"base": "number"}},
            {"name": "b", "type": {"base": "number"}}
        ],
        "outputs": [
            {"name": "result", "type": {"base": "number"}}
        ],
        "preconditions": [],
        "postconditions": [],
        "side_effects": []
    }
```

### 8.2 Test Utilities

**File:** `tests/unit/utils/test_helpers.py`

```python
"""
Test helper utilities
"""

from typing import Any, Dict
import json

def assert_logicnode_valid(logicnode: Dict[str, Any]):
    """Assert that a LogicNode dictionary is valid"""
    required_fields = [
        "intent", "domain", "concept",
        "inputs", "outputs"
    ]
    
    for field in required_fields:
        assert field in logicnode, f"Missing required field: {field}"
    
    assert isinstance(logicnode["inputs"], list)
    assert isinstance(logicnode["outputs"], list)


def load_test_data(filename: str) -> Dict[str, Any]:
    """Load test data from JSON file"""
    path = Path(__file__).parent.parent / "test_data" / filename
    with open(path, 'r') as f:
        return json.load(f)


def create_mock_agent(agent_id: str, agent_type: str):
    """Factory for creating mock agents"""
    mock = Mock()
    mock.agent_id = agent_id
    mock.agent_type = agent_type
    mock.state = "idle"
    return mock
```

---

## 9. COVERAGE REQUIREMENTS & ENFORCEMENT

### 9.1 Coverage Configuration

**File:** `.coveragerc`

```ini
[run]
source = 
    agents
    logicnodes
    semantic_bus
    parsers
    utils

omit =
    */tests/*
    */migrations/*
    */__pycache__/*
    */venv/*
    setup.py

branch = True
parallel = True

[report]
precision = 2
show_missing = True
skip_covered = False

exclude_lines =
    # Have to re-enable the standard pragma
    pragma: no cover
    
    # Don't complain about missing debug-only code
    def __repr__
    if self\.debug
    
    # Don't complain if tests don't hit defensive assertion code
    raise AssertionError
    raise NotImplementedError
    
    # Don't complain if non-runnable code isn't run
    if __name__ == .__main__.:
    
    # Don't complain about abstract methods
    @(abc\.)?abstractmethod

[html]
directory = htmlcov
```

### 9.2 Coverage Enforcement Script

**File:** `scripts/check_coverage.sh`

```bash
#!/bin/bash
# Check code coverage and enforce thresholds

set -e

echo "Running tests with coverage..."
pytest tests/unit/ --cov --cov-report=term-missing --cov-report=html

echo ""
echo "Checking coverage thresholds..."

# Extract coverage percentage
COVERAGE=$(coverage report | grep TOTAL | awk '{print $4}' | sed 's/%//')

echo "Current coverage: ${COVERAGE}%"
echo "Required coverage: 90%"

if (( $(echo "$COVERAGE < 90" | bc -l) )); then
    echo "❌ Coverage is below 90% threshold"
    exit 1
else
    echo "✅ Coverage meets requirements"
fi

# Check for untested files
echo ""
echo "Checking for files with < 80% coverage..."
coverage report | awk '$4 ~ /^[0-7][0-9]%$/ { print $1, $4 }'

echo ""
echo "Coverage report: htmlcov/index.html"
```

### 9.3 Per-Module Coverage Requirements

```python
# tests/unit/test_coverage_requirements.py
"""
Test that critical modules meet higher coverage thresholds
"""

import pytest
from coverage import Coverage

def test_logicnode_validation_has_95_percent_coverage():
    """LogicNode validation must have 95%+ coverage"""
    cov = Coverage()
    cov.load()
    
    module_coverage = cov.analysis('logicnodes/validation.py')
    coverage_pct = (len(module_coverage[1]) / len(module_coverage[2])) * 100
    
    assert coverage_pct >= 95, \
        f"logicnodes/validation.py only has {coverage_pct:.1f}% coverage"

def test_agent_base_class_has_90_percent_coverage():
    """Base agent class must have 90%+ coverage"""
    cov = Coverage()
    cov.load()
    
    module_coverage = cov.analysis('agents/base_agent.py')
    coverage_pct = (len(module_coverage[1]) / len(module_coverage[2])) * 100
    
    assert coverage_pct >= 90
```

---

## 10. CONTINUOUS TESTING INTEGRATION

### 10.1 Pre-commit Hooks

**File:** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: local
    hooks:
      # Run unit tests before commit
      - id: pytest-unit
        name: Run unit tests
        entry: pytest tests/unit/ -x -v
        language: system
        pass_filenames: false
        always_run: true
      
      # Check code coverage
      - id: coverage-check
        name: Check code coverage
        entry: ./scripts/check_coverage.sh
        language: system
        pass_filenames: false
        always_run: true
      
      # Run linters
      - id: black
        name: black
        entry: black
        language: system
        types: [python]
      
      - id: flake8
        name: flake8
        entry: flake8
        language: system
        types: [python]
```

### 10.2 CI Pipeline Integration

**File:** `.github/workflows/test.yml`

```yaml
name: Unit Tests

on: [push, pull_request]

jobs:
  test:
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
      
      - name: Run unit tests
        run: |
          pytest tests/unit/ \
            --cov \
            --cov-report=xml \
            --cov-report=html \
            --junitxml=junit.xml
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
      
      - name: Publish test results
        uses: EnricoMi/publish-unit-test-result-action@v2
        if: always()
        with:
          files: junit.xml
```

---

## DOCUMENT METADATA

**Document ID:** 41  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Owner:** QA Lead  
**Dependencies:** Document 23 (Testing Framework)  
**Next Document:** 42 (Integration Testing Framework)

---

*End of Unit Testing Standards & Implementation*
