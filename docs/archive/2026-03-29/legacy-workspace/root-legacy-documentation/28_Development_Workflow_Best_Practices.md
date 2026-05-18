# DOCUMENT 28: DEVELOPMENT WORKFLOW & BEST PRACTICES

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Development Specifications

**Document ID:** 28  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document establishes **standardized development workflows, coding standards, and best practices** for the Holy Grail Refinery project. It ensures consistency, quality, and efficiency across all development activities for the 35-agent system.

**Workflow Principles:**
- 🔄 Git-based version control with feature branches
- 👥 Mandatory code reviews for all changes
- ✅ Automated testing before merge
- 📝 Comprehensive documentation requirements
- 🚀 Continuous integration and deployment
- 🎯 Test-driven development (TDD) approach

**Quality Standards:**
- 90%+ code coverage
- Zero critical/high severity issues
- PEP 8 compliance for Python
- Type hints required
- Docstrings for all public APIs

---

## TABLE OF CONTENTS

1. [Git Workflow](#1-git-workflow)
2. [Branch Strategy](#2-branch-strategy)
3. [Coding Standards](#3-coding-standards)
4. [Code Review Process](#4-code-review-process)
5. [Testing Requirements](#5-testing-requirements)
6. [Documentation Standards](#6-documentation-standards)
7. [Commit Message Guidelines](#7-commit-message-guidelines)
8. [Pull Request Template](#8-pull-request-template)
9. [Local Development Setup](#9-local-development-setup)
10. [Troubleshooting Development Issues](#10-troubleshooting-development-issues)

---

## 1. GIT WORKFLOW

### 1.1 Repository Structure

```
holy-grail-refinery/
├── .github/
│   ├── workflows/          # CI/CD pipelines
│   ├── ISSUE_TEMPLATE/     # Issue templates
│   └── PULL_REQUEST_TEMPLATE.md
├── agents/                 # Agent implementations
│   ├── base/
│   ├── managers/
│   ├── specialists/
│   └── support/
├── api/                    # API implementation
├── database/              # Database schemas and migrations
├── semantic_bus/          # Communication layer
├── tests/                 # Test suites
│   ├── unit/
│   ├── integration/
│   └── system/
├── docs/                  # Documentation
├── scripts/               # Utility scripts
├── docker/                # Dockerfiles
├── config/                # Configuration files
├── monitoring/            # Monitoring configs
└── security/              # Security configurations
```

### 1.2 Git Configuration

**File:** `.gitconfig.local`

```ini
[user]
    name = Your Name
    email = your.email@example.com

[core]
    editor = vim
    autocrlf = input

[pull]
    rebase = true

[fetch]
    prune = true

[diff]
    colorMoved = default

[alias]
    # Useful aliases
    st = status -sb
    co = checkout
    br = branch
    ci = commit
    lg = log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit
    unstage = reset HEAD --
    last = log -1 HEAD
    amend = commit --amend --no-edit
```

### 1.3 .gitignore Configuration

**File:** `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/
*.cover

# Docker
*.log

# Environment
.env
.env.local
secrets.env

# Databases
*.db
*.sqlite
data/

# Backups
backups/
*.dump
*.rdb

# OS
.DS_Store
Thumbs.db

# Build artifacts
dist/
build/
*.egg-info/

# Monitoring data
prometheus-data/
grafana-data/
```

---

## 2. BRANCH STRATEGY

### 2.1 Branch Types

**Main Branches:**
- `main` - Production-ready code, protected
- `develop` - Integration branch for features

**Supporting Branches:**
- `feature/*` - New features or enhancements
- `bugfix/*` - Bug fixes for develop branch
- `hotfix/*` - Urgent fixes for production
- `release/*` - Release preparation

### 2.2 Branch Naming Convention

```bash
# Features
feature/agent-python-optimization
feature/add-protocol-handler
feature/improve-logicnode-extraction

# Bug fixes
bugfix/fix-redis-connection-leak
bugfix/correct-protocol-validation

# Hotfixes
hotfix/security-patch-jwt
hotfix/critical-memory-leak

# Releases
release/v1.1.0
release/v2.0.0
```

### 2.3 Workflow Steps

**Creating a feature:**

```bash
# 1. Update develop branch
git checkout develop
git pull origin develop

# 2. Create feature branch
git checkout -b feature/my-new-feature

# 3. Make changes and commit
git add .
git commit -m "feat(agents): add new capability to Python agent"

# 4. Keep branch up to date
git fetch origin develop
git rebase origin/develop

# 5. Push and create PR
git push origin feature/my-new-feature
```

**Merging workflow:**

```bash
# After PR approval
git checkout develop
git merge --no-ff feature/my-new-feature
git push origin develop

# Delete feature branch
git branch -d feature/my-new-feature
git push origin --delete feature/my-new-feature
```

---

## 3. CODING STANDARDS

### 3.1 Python Style Guide

**File:** `.flake8`

```ini
[flake8]
max-line-length = 100
extend-ignore = E203, W503
exclude = 
    .git,
    __pycache__,
    venv,
    .venv,
    build,
    dist
per-file-ignores =
    __init__.py:F401
```

**File:** `pyproject.toml`

```toml
[tool.black]
line-length = 100
target-version = ['py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''

[tool.isort]
profile = "black"
line_length = 100
skip_gitignore = true

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
ignore_missing_imports = true
```

### 3.2 Code Style Examples

**Good:**

```python
"""
Module for handling Python code extraction.

This module provides utilities for parsing Python source code
and extracting LogicNodes.
"""

from typing import Dict, Any, List, Optional
import ast
import logging

logger = logging.getLogger(__name__)


class PythonExtractor:
    """
    Extract LogicNodes from Python source code.
    
    This class uses AST parsing to identify programming concepts
    and convert them to universal LogicNode representations.
    
    Attributes:
        agent_id: Unique identifier for this agent
        config: Configuration dictionary
    """
    
    def __init__(self, agent_id: str, config: Dict[str, Any]) -> None:
        """
        Initialize Python extractor.
        
        Args:
            agent_id: Unique agent identifier
            config: Configuration dictionary
            
        Raises:
            ValueError: If agent_id is empty
        """
        if not agent_id:
            raise ValueError("agent_id cannot be empty")
        
        self.agent_id = agent_id
        self.config = config
        self._cache: Dict[str, Any] = {}
    
    def extract_function(
        self,
        node: ast.FunctionDef,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract LogicNode from function definition.
        
        Args:
            node: AST function definition node
            context: Optional context information
            
        Returns:
            LogicNode dictionary
            
        Example:
            >>> extractor = PythonExtractor("AGENT-PY-001", {})
            >>> tree = ast.parse("def add(a, b): return a + b")
            >>> func_node = tree.body[0]
            >>> logicnode = extractor.extract_function(func_node)
            >>> logicnode['concept']
            'function_definition'
        """
        logger.info(f"Extracting function: {node.name}")
        
        # Implementation
        logicnode = {
            "domain": "functions",
            "concept": "function_definition",
            "intent": f"Define function {node.name}",
            "inputs": self._extract_parameters(node.args),
            "outputs": self._infer_return_type(node),
        }
        
        return logicnode
    
    def _extract_parameters(self, args: ast.arguments) -> List[Dict[str, Any]]:
        """Extract function parameters (private helper method)."""
        # Implementation
        return []
    
    def _infer_return_type(self, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """Infer function return type (private helper method)."""
        # Implementation
        return []
```

**Bad:**

```python
# No module docstring
# No type hints
# Inconsistent naming
# No error handling

import ast

class pythonExtractor:  # Bad: should be PythonExtractor
    def __init__(self, id, cfg):  # Bad: unclear names, no types
        self.id = id
        self.cfg = cfg
    
    def extract(self, n):  # Bad: no docstring, unclear name, no types
        # No logging
        # No error handling
        x = {
            'domain': 'functions',
            'concept': 'function_definition',
            'intent': 'blah',  # Bad: unclear
        }
        return x
```

### 3.3 Pre-commit Hooks

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
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: check-merge-conflict
  
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=100']
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-pyyaml]
```

**Install pre-commit:**

```bash
pip install pre-commit
pre-commit install
```

---

## 4. CODE REVIEW PROCESS

### 4.1 Review Checklist

**File:** `docs/CODE_REVIEW_CHECKLIST.md`

```markdown
# Code Review Checklist

## Functionality
- [ ] Code accomplishes stated goal
- [ ] Edge cases handled
- [ ] Error handling implemented
- [ ] No obvious bugs

## Code Quality
- [ ] Follows coding standards
- [ ] No code duplication
- [ ] Functions are focused and small
- [ ] Variable names are clear
- [ ] No magic numbers or strings

## Testing
- [ ] Unit tests included
- [ ] Tests cover edge cases
- [ ] All tests pass
- [ ] Code coverage maintained/improved

## Documentation
- [ ] Docstrings present
- [ ] Complex logic commented
- [ ] README updated if needed
- [ ] API documentation updated

## Performance
- [ ] No obvious performance issues
- [ ] Database queries optimized
- [ ] No N+1 queries
- [ ] Appropriate caching

## Security
- [ ] Input validation present
- [ ] No SQL injection vulnerabilities
- [ ] Secrets not hardcoded
- [ ] Authentication/authorization correct

## Architecture
- [ ] Follows existing patterns
- [ ] Dependencies justified
- [ ] No circular dependencies
- [ ] Appropriate abstraction level
```

### 4.2 Review Guidelines

**Reviewer responsibilities:**
1. Review within 24 hours
2. Provide constructive feedback
3. Approve only if all criteria met
4. Test locally for complex changes

**Author responsibilities:**
1. Self-review before requesting
2. Address all comments
3. Update tests and documentation
4. Keep PR scope focused

**Example review comments:**

```python
# Good comments
# ✓ "Consider using a context manager here for automatic cleanup"
# ✓ "This could cause a race condition if X happens. Consider adding a lock."
# ✓ "Nice approach! Could we extract this to a helper function for reusability?"

# Bad comments
# ✗ "This is wrong" (not helpful)
# ✗ "I would have done it differently" (not specific)
# ✗ "Why didn't you use X?" (accusatory)
```

---

## 5. TESTING REQUIREMENTS

### 5.1 Test Structure

```
tests/
├── unit/
│   ├── agents/
│   │   ├── test_base_agent.py
│   │   ├── test_python_agent.py
│   │   └── test_manager.py
│   ├── api/
│   │   ├── test_auth.py
│   │   └── test_endpoints.py
│   └── semantic_bus/
│       └── test_protocols.py
├── integration/
│   ├── test_agent_communication.py
│   ├── test_database.py
│   └── test_semantic_bus.py
├── system/
│   ├── test_e2e_extraction.py
│   └── test_workflow.py
└── conftest.py  # Shared fixtures
```

### 5.2 Test Writing Standards

**File:** `tests/unit/agents/test_python_agent.py`

```python
"""
Unit tests for Python Specialist Agent.

Tests cover:
- LogicNode extraction from various Python constructs
- Error handling for invalid syntax
- Protocol message handling
"""

import pytest
from agents.specialists.python_agent import PythonAgent
from agents.base.message import Message


class TestPythonAgent:
    """Test suite for PythonAgent"""
    
    @pytest.fixture
    def agent(self):
        """Create test agent instance"""
        return PythonAgent(agent_id="TEST-PY-001")
    
    @pytest.fixture
    def sample_code(self):
        """Sample Python code for testing"""
        return """
def add(a, b):
    '''Add two numbers'''
    return a + b
"""
    
    def test_extract_function_basic(self, agent, sample_code):
        """Test extracting simple function"""
        # Arrange
        # (fixtures already arranged)
        
        # Act
        result = agent.extract_logicnode(sample_code)
        
        # Assert
        assert result is not None
        assert result['domain'] == 'functions'
        assert result['concept'] == 'function_definition'
        assert len(result['inputs']) == 2
        assert len(result['outputs']) == 1
    
    def test_extract_function_with_invalid_syntax(self, agent):
        """Test error handling for syntax errors"""
        # Arrange
        invalid_code = "def broken("
        
        # Act & Assert
        with pytest.raises(SyntaxError):
            agent.extract_logicnode(invalid_code)
    
    @pytest.mark.parametrize("code,expected_concept", [
        ("if x > 0: pass", "conditional"),
        ("for i in range(10): pass", "for_loop"),
        ("while True: pass", "while_loop"),
        ("try: pass\nexcept: pass", "try_except"),
    ])
    def test_extract_control_flow(self, agent, code, expected_concept):
        """Test extraction of various control flow constructs"""
        # Act
        result = agent.extract_logicnode(code)
        
        # Assert
        assert result['concept'] == expected_concept
    
    @pytest.mark.asyncio
    async def test_handle_alpha_message(self, agent):
        """Test Protocol Alpha message handling"""
        # Arrange
        message = Message(
            message_id="test-msg-001",
            protocol="alpha",
            sender="MANAGER-POD-A-001",
            recipient="TEST-PY-001",
            timestamp="2026-02-05T10:00:00Z",
            payload={
                "message_type": "assignment",
                "task_id": "task-123",
                "instructions": "Extract LogicNodes",
                "priority": 1
            }
        )
        
        # Act
        response = await agent.handle_alpha_message(message)
        
        # Assert
        assert response['status'] in ['accepted', 'completed']
        assert 'task_id' in response
```

### 5.3 Coverage Requirements

**File:** `pytest.ini`

```ini
[pytest]
minversion = 7.0
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Coverage requirements
addopts = 
    --cov=agents
    --cov=api
    --cov=semantic_bus
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=90
    -v
    --strict-markers

# Test markers
markers =
    unit: Unit tests
    integration: Integration tests
    system: System/E2E tests
    slow: Slow-running tests
    smoke: Quick smoke tests
```

---

## 6. DOCUMENTATION STANDARDS

### 6.1 Module Documentation

**Required sections:**
1. Module-level docstring
2. Class docstrings
3. Method/function docstrings
4. Complex algorithm explanations
5. Usage examples

**Template:**

```python
"""
Module name and brief description.

Longer description explaining the module's purpose,
key concepts, and how it fits into the system.

Example:
    Basic usage example showing how to use this module:
    
    >>> from agents.specialists import PythonAgent
    >>> agent = PythonAgent("AGENT-PY-001")
    >>> result = agent.extract_logicnode(code)

Attributes:
    module_level_variable1: Description
    module_level_variable2: Description
"""


class ClassName:
    """
    Brief description of the class.
    
    Longer description explaining what the class does,
    when to use it, and key concepts.
    
    Attributes:
        attr1: Description of attribute
        attr2: Description of attribute
    
    Example:
        >>> instance = ClassName(param1, param2)
        >>> result = instance.method()
    """
    
    def method_name(self, param1: str, param2: int) -> Dict[str, Any]:
        """
        Brief description of what method does.
        
        Longer description if needed, explaining algorithm,
        edge cases, or important details.
        
        Args:
            param1: Description of param1
            param2: Description of param2
        
        Returns:
            Description of return value
        
        Raises:
            ValueError: When and why
            TypeError: When and why
        
        Example:
            >>> obj.method_name("test", 42)
            {'result': 'success'}
        """
        pass
```

### 6.2 README Standards

**Required sections:**
1. Overview
2. Installation
3. Quick Start
4. Configuration
5. Usage Examples
6. API Reference
7. Contributing
8. License

**Example README structure:**

```markdown
# Holy Grail Refinery

## Overview
Brief description of the system and its purpose.

## Installation

### Prerequisites
- Python 3.11+
- Docker 20.10+
- 32GB RAM

### Setup
```bash
git clone https://github.com/org/holy-grail-refinery.git
cd holy-grail-refinery
./scripts/setup.sh
```

## Quick Start

```python
from agents.specialists import PythonAgent

agent = PythonAgent("AGENT-PY-001")
result = agent.extract_logicnode(code)
```

## Configuration
Details on configuration files and environment variables.

## API Reference
Link to detailed API documentation.

## Contributing
See CONTRIBUTING.md

## License
MIT License
```

---

## 7. COMMIT MESSAGE GUIDELINES

### 7.1 Conventional Commits

**Format:**

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Build process or tooling changes
- `ci`: CI/CD changes

**Examples:**

```bash
# Good commits
feat(agents): add LogicNode caching to Python agent

Add in-memory cache for frequently extracted LogicNodes
to reduce parsing overhead. Cache expires after 5 minutes.

Closes #123

---

fix(api): correct JWT token expiration validation

Token expiration was not being checked correctly, allowing
expired tokens to pass validation. Fixed by adding explicit
expiration check before signature verification.

Fixes #456

---

docs(readme): update installation instructions

Added Docker prerequisites and clarified setup steps.

---

refactor(semantic-bus): extract message validation to helper

Moved validation logic to separate function for better
testability and reusability.
```

**Bad commits:**

```bash
# Too vague
fix: bug fix

# Not descriptive
feat: stuff

# Missing scope
added new feature

# No explanation
WIP
```

### 7.2 Commit Best Practices

1. **Atomic commits**: One logical change per commit
2. **Working state**: Each commit should leave codebase in working state
3. **Descriptive**: Clear what and why
4. **Reference issues**: Link to issue tracker
5. **Test before commit**: Ensure tests pass

---

## 8. PULL REQUEST TEMPLATE

**File:** `.github/PULL_REQUEST_TEMPLATE.md`

```markdown
## Description
Brief description of changes and motivation.

Fixes #(issue)

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## How Has This Been Tested?
Describe the tests that you ran to verify your changes.

- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## Screenshots (if applicable)
Add screenshots to help explain your changes.

## Additional Context
Add any other context about the pull request here.
```

---

## 9. LOCAL DEVELOPMENT SETUP

### 9.1 Development Environment

**File:** `scripts/dev_setup.sh`

```bash
#!/bin/bash
# Setup local development environment

set -e

echo "Setting up development environment..."

# 1. Install Python dependencies
echo "Installing Python dependencies..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 2. Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

# 3. Setup environment variables
echo "Setting up environment variables..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Please update .env with your configuration"
fi

# 4. Start development services
echo "Starting development services..."
docker-compose -f docker-compose.dev.yml up -d postgres redis

# 5. Run database migrations
echo "Running database migrations..."
sleep 5
alembic upgrade head

# 6. Run tests to verify setup
echo "Running tests..."
pytest tests/unit -v

echo "✓ Development environment ready!"
echo ""
echo "Next steps:"
echo "  1. Activate virtualenv: source venv/bin/activate"
echo "  2. Start development: python -m agents.specialists.python_agent"
echo "  3. Run tests: pytest"
```

### 9.2 Development Docker Compose

**File:** `docker-compose.dev.yml`

```yaml
version: '3.8'

services:
  # Minimal services for development
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_PASSWORD: dev_password
    volumes:
      - postgres-dev:/var/lib/postgresql/data
  
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
  
  # Hot-reload API for development
  api-dev:
    build:
      context: .
      dockerfile: docker/api/Dockerfile.dev
    volumes:
      - ./api:/app/api
      - ./agents:/app/agents
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      - DEBUG=true
    command: uvicorn api.main:app --reload --host 0.0.0.0

volumes:
  postgres-dev:
```

---

## 10. TROUBLESHOOTING DEVELOPMENT ISSUES

### 10.1 Common Issues

**Issue: Import errors**

```bash
# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use editable install
pip install -e .
```

**Issue: Tests failing**

```bash
# Run with verbose output
pytest -vv tests/unit/test_file.py::test_function

# Run with print statements
pytest -s tests/

# Run specific test with debugging
pytest --pdb tests/unit/test_file.py::test_function
```

**Issue: Pre-commit failing**

```bash
# Run manually
pre-commit run --all-files

# Skip hooks (emergency only)
git commit --no-verify

# Update hooks
pre-commit autoupdate
```

**Issue: Docker build failing**

```bash
# Clean build
docker-compose build --no-cache

# Check logs
docker-compose logs api

# Rebuild specific service
docker-compose build api
```

### 10.2 Debugging Tips

**Python debugging:**

```python
# Use breakpoint() (Python 3.7+)
def problematic_function():
    x = compute_something()
    breakpoint()  # Execution pauses here
    y = compute_more(x)
    return y

# Use logging
import logging
logger = logging.getLogger(__name__)

logger.debug(f"Variable value: {x}")
logger.info("Function called")
logger.warning("Unexpected condition")
logger.error("Operation failed", exc_info=True)
```

**Docker debugging:**

```bash
# Enter running container
docker exec -it hgr-agent-python bash

# Check container logs
docker logs -f hgr-agent-python

# Inspect container
docker inspect hgr-agent-python

# Check resource usage
docker stats hgr-agent-python
```

---

## DOCUMENT METADATA

**Document ID:** 28  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Owner:** Development Lead  
**Dependencies:** Documents 19-27  
**Next Document:** 29 (Agent Testing Strategies)

---

*End of Development Workflow & Best Practices*
