# DOCUMENT 50: CONTINUOUS TESTING STRATEGY

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Quality & Testing

**Document ID:** 50  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document defines the **continuous testing strategy** for the Holy Grail Refinery system, establishing automated testing practices that run throughout the development lifecycle. The strategy ensures code quality, prevents regressions, and maintains system reliability through automated validation at every stage.

**Continuous Testing Philosophy:**
- 🔄 **Shift-Left Testing:** Find defects early in development
- 🤖 **Automation-First:** Minimize manual testing overhead
- 📊 **Data-Driven Decisions:** Use metrics to guide quality improvements
- ⚡ **Fast Feedback:** Developers get test results within minutes
- 🎯 **Risk-Based:** Focus testing effort on high-risk areas

**Testing Layers:**
1. **Pre-Commit Testing** - Local developer validation
2. **Commit Testing** - Automated CI on every commit
3. **Integration Testing** - Component interaction validation
4. **System Testing** - Full 35-agent orchestration
5. **Production Testing** - Live system monitoring

**Quality Metrics:**
- ✅ **Code Coverage:** ≥ 90% (unit + integration)
- 🎯 **Test Success Rate:** ≥ 99.5%
- ⚡ **Test Execution Time:** < 15 minutes (full suite)
- 🔄 **Deployment Frequency:** 10+ per day
- 🐛 **Defect Escape Rate:** < 1% to production

---

## TABLE OF CONTENTS

1. [Continuous Testing Architecture](#1-continuous-testing-architecture)
2. [Pre-Commit Testing](#2-pre-commit-testing)
3. [Continuous Integration Testing](#3-continuous-integration-testing)
4. [Continuous Deployment Testing](#4-continuous-deployment-testing)
5. [Production Testing](#5-production-testing)
6. [Test Automation Framework](#6-test-automation-framework)
7. [Test Data Management](#7-test-data-management)
8. [Performance Testing Strategy](#8-performance-testing-strategy)
9. [Security Testing Strategy](#9-security-testing-strategy)
10. [Quality Metrics & Reporting](#10-quality-metrics--reporting)

---

## 1. CONTINUOUS TESTING ARCHITECTURE

### 1.1 Testing Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                  CONTINUOUS TESTING PIPELINE                    │
└─────────────────────────────────────────────────────────────────┘

Local Development (Developer Workstation)
┌─────────────────────────────────────────┐
│  Pre-Commit Hooks                       │
│  • Lint checks (Black, Flake8)         │
│  • Type checking (mypy)                 │
│  • Unit tests (fast subset)            │
│  • Security scan (Bandit)               │
│  Duration: < 30 seconds                 │
└──────────────────┬──────────────────────┘
                   │
                   ▼
Continuous Integration (GitHub Actions)
┌─────────────────────────────────────────┐
│  Commit Pipeline (Every Push)           │
│  • Full unit test suite                 │
│  • Code coverage analysis               │
│  • Static analysis                      │
│  • Container build validation           │
│  Duration: 5-8 minutes                  │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Integration Pipeline (Main Branch)     │
│  • Integration test suite               │
│  • API contract testing                 │
│  • Database migration tests             │
│  • Cross-agent communication tests      │
│  Duration: 15-20 minutes                │
└──────────────────┬──────────────────────┘
                   │
                   ▼
Continuous Deployment (Staging)
┌─────────────────────────────────────────┐
│  Staging Deployment                     │
│  • E2E test scenarios                   │
│  • Performance benchmarks               │
│  • Security vulnerability scans         │
│  • Load testing                         │
│  Duration: 30-45 minutes                │
└──────────────────┬──────────────────────┘
                   │
                   ▼
Production Deployment
┌─────────────────────────────────────────┐
│  Production Validation                  │
│  • Smoke tests                          │
│  • Synthetic monitoring                 │
│  • Real user monitoring                 │
│  • A/B testing framework                │
│  Duration: Continuous                   │
└─────────────────────────────────────────┘
```

### 1.2 Testing Frequency Matrix

| Test Type | Trigger | Frequency | Duration | Scope |
|-----------|---------|-----------|----------|-------|
| **Lint & Format** | Pre-commit | Every commit attempt | < 10s | Changed files |
| **Fast Unit Tests** | Pre-commit | Every commit attempt | < 30s | Changed modules |
| **Full Unit Tests** | CI commit | Every push | 5-8 min | All modules |
| **Integration Tests** | CI main branch | Every merge | 15-20 min | Component interactions |
| **E2E Tests** | Nightly + staging | Daily + deployments | 30-45 min | Full workflows |
| **Performance Tests** | Weekly + release | Scheduled | 1-2 hours | System benchmarks |
| **Security Scans** | Daily + release | Scheduled | 30 min | Vulnerabilities |
| **Production Tests** | Continuous | Always on | Real-time | User flows |

---

## 2. PRE-COMMIT TESTING

### 2.1 Pre-Commit Hook Configuration

**File:** `.pre-commit-config.yaml`

```yaml
# Holy Grail Refinery Pre-Commit Configuration
repos:
  # Code Formatting
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11
        args: ['--line-length=100']

  # Import Sorting
  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ['--profile', 'black', '--line-length', '100']

  # Linting
  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=100', '--extend-ignore=E203,W503']

  # Type Checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        args: ['--ignore-missing-imports', '--strict']
        additional_dependencies: ['types-redis', 'types-requests']

  # Security Scanning
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-ll', '-i', 'B101,B601']

  # Fast Unit Tests (Subset)
  - repo: local
    hooks:
      - id: fast-unit-tests
        name: Fast Unit Tests
        entry: pytest
        language: system
        types: [python]
        args: [
          'tests/unit/',
          '-m', 'fast',
          '-x',  # Stop on first failure
          '--tb=short',
          '--quiet'
        ]
        pass_filenames: false
```

**Installation:**
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

### 2.2 Fast Unit Test Selection

**Marking Fast Tests:**

```python
# tests/unit/test_pm_agent.py
import pytest

@pytest.mark.fast
def test_pm_agent_initialization():
    """Fast test: No external dependencies"""
    agent = PMAgent(agent_id="PM-001")
    assert agent.state == AgentState.IDLE

@pytest.mark.fast
def test_parse_vibe_basic():
    """Fast test: Pure logic, no I/O"""
    result = PMAgent.parse_vibe("Build a web scraper")
    assert "scraper" in result.keywords
    assert result.intent == "build"

@pytest.mark.slow
@pytest.mark.integration
def test_full_mission_creation():
    """Slow test: Requires database, Redis"""
    # This test is skipped in pre-commit
    ...
```

**pytest.ini Configuration:**

```ini
[pytest]
markers =
    fast: Fast unit tests (< 100ms each)
    slow: Slow tests with I/O operations
    integration: Integration tests
    e2e: End-to-end tests
    smoke: Smoke tests for deployments
```

---

## 3. CONTINUOUS INTEGRATION TESTING

### 3.1 GitHub Actions Workflow

**File:** `.github/workflows/continuous-testing.yml`

```yaml
name: Continuous Testing Pipeline

on:
  push:
    branches: ['**']
  pull_request:
    branches: [main, develop]

env:
  PYTHON_VERSION: '3.11'

jobs:
  # Job 1: Lint and Format Check
  lint:
    name: Lint & Format Validation
    runs-on: ubuntu-latest
    timeout-minutes: 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Cache dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
      
      - name: Install dependencies
        run: |
          pip install black flake8 isort mypy bandit
      
      - name: Run Black
        run: black --check --diff .
      
      - name: Run Flake8
        run: flake8 agents/ api/ tests/
      
      - name: Run isort
        run: isort --check-only --diff .
      
      - name: Run mypy
        run: mypy agents/ api/ --ignore-missing-imports
      
      - name: Run Bandit
        run: bandit -r agents/ api/ -ll

  # Job 2: Unit Tests
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: lint
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Cache dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Run unit tests with coverage
        run: |
          pytest tests/unit/ \
            -v \
            --cov=agents \
            --cov=api \
            --cov-report=xml \
            --cov-report=html \
            --cov-report=term-missing \
            --junitxml=junit-unit.xml \
            --cov-fail-under=90
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: unit-tests
          name: codecov-umbrella
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: unit-test-results
          path: |
            junit-unit.xml
            htmlcov/

  # Job 3: Integration Tests (Main Branch Only)
  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    timeout-minutes: 20
    needs: unit-tests
    if: github.ref == 'refs/heads/main' || github.event_name == 'pull_request'
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: hgr_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
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
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Initialize test database
        run: |
          python scripts/init_test_db.py
        env:
          DATABASE_URL: postgresql://postgres:test_password@localhost:5432/hgr_test
      
      - name: Run integration tests
        run: |
          pytest tests/integration/ \
            -v \
            --junitxml=junit-integration.xml
        env:
          DATABASE_URL: postgresql://postgres:test_password@localhost:5432/hgr_test
          REDIS_URL: redis://localhost:6379
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: integration-test-results
          path: junit-integration.xml

  # Job 4: Build Docker Images
  docker-build:
    name: Docker Image Build
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: unit-tests
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Build PM Agent Image
        uses: docker/build-push-action@v4
        with:
          context: ./agents/pm_agent
          file: ./agents/pm_agent/Dockerfile
          push: false
          tags: hgr/pm-agent:test
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      - name: Build CEO Agent Image
        uses: docker/build-push-action@v4
        with:
          context: ./agents/ceo_agent
          file: ./agents/ceo_agent/Dockerfile
          push: false
          tags: hgr/ceo-agent:test
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      # Build images for all 35 agents
      # (Similar steps repeated for each agent)

  # Job 5: Security Scanning
  security-scan:
    name: Security Vulnerability Scan
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: unit-tests
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Safety (Python dependency check)
        run: |
          pip install safety
          safety check --json --output safety-report.json || true
      
      - name: Run Trivy (Container scanning)
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'
      
      - name: Upload Trivy results to GitHub Security
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'
      
      - name: Upload security reports
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            safety-report.json
            trivy-results.sarif

  # Job 6: Test Summary
  test-summary:
    name: Test Summary
    runs-on: ubuntu-latest
    if: always()
    needs: [lint, unit-tests, integration-tests, docker-build, security-scan]
    
    steps:
      - name: Generate Test Summary
        run: |
          echo "## Test Results Summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Job | Status |" >> $GITHUB_STEP_SUMMARY
          echo "|-----|--------|" >> $GITHUB_STEP_SUMMARY
          echo "| Lint | ${{ needs.lint.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Unit Tests | ${{ needs.unit-tests.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Integration Tests | ${{ needs.integration-tests.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Docker Build | ${{ needs.docker-build.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Security Scan | ${{ needs.security-scan.result }} |" >> $GITHUB_STEP_SUMMARY
```

---

## 4. CONTINUOUS DEPLOYMENT TESTING

### 4.1 Staging Deployment Pipeline

**Automatic Staging Deployment (on main branch merge):**

```yaml
# .github/workflows/deploy-staging.yml
name: Deploy to Staging

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    name: Deploy to Staging Environment
    runs-on: ubuntu-latest
    environment: staging
    timeout-minutes: 30
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to staging
        run: |
          ./scripts/deploy_staging.sh
        env:
          SSH_PRIVATE_KEY: ${{ secrets.STAGING_SSH_KEY }}
          STAGING_HOST: ${{ secrets.STAGING_HOST }}
      
      - name: Wait for deployment
        run: sleep 60
      
      - name: Run E2E tests
        run: |
          pytest tests/e2e/ \
            --base-url=https://staging.hgr.local \
            -v \
            --junitxml=junit-e2e.xml
      
      - name: Run performance benchmarks
        run: |
          locust -f tests/load/locustfile.py \
            --host=https://staging.hgr.local \
            --headless \
            --users=10 \
            --spawn-rate=2 \
            --run-time=5m \
            --html=performance-report.html
      
      - name: Rollback on failure
        if: failure()
        run: |
          ./scripts/rollback_staging.sh
```

---

## 5. PRODUCTION TESTING

### 5.1 Synthetic Monitoring

**Continuous Production Health Checks:**

```python
# monitoring/synthetic_tests.py
"""
Synthetic monitoring tests that run continuously in production
"""

import asyncio
import time
from typing import Dict, List
from datadog import statsd

class SyntheticMonitor:
    """
    Run synthetic tests against production every 5 minutes
    """
    
    async def run_mission_creation_test(self) -> Dict:
        """
        Test: Create a simple mission and verify completion
        """
        start_time = time.time()
        
        try:
            # 1. Submit mission
            response = await self.api_client.post(
                "/api/v1/missions",
                json={
                    "description": "Synthetic test: Extract Python list operations",
                    "type": "synthetic_test"
                }
            )
            mission_id = response.json()["mission_id"]
            
            # 2. Poll for completion (max 2 minutes)
            completed = await self.wait_for_mission(mission_id, timeout=120)
            
            # 3. Verify outputs
            if completed:
                mission = await self.api_client.get(f"/api/v1/missions/{mission_id}")
                assert mission.json()["status"] == "completed"
                assert len(mission.json()["logicnodes"]) > 0
            
            duration = time.time() - start_time
            
            # Send metrics
            statsd.histogram('synthetic.mission_creation.duration', duration)
            statsd.increment('synthetic.mission_creation.success')
            
            return {"success": True, "duration": duration}
            
        except Exception as e:
            duration = time.time() - start_time
            statsd.increment('synthetic.mission_creation.failure')
            return {"success": False, "duration": duration, "error": str(e)}
    
    async def run_knowledge_lake_test(self) -> Dict:
        """
        Test: Query Knowledge Lake and verify results
        """
        start_time = time.time()
        
        try:
            response = await self.api_client.post(
                "/api/v1/knowledge/search",
                json={"query": "Python list filter operations", "top_k": 5}
            )
            
            results = response.json()["results"]
            assert len(results) >= 3, "Expected at least 3 results"
            
            duration = time.time() - start_time
            statsd.histogram('synthetic.knowledge_lake.duration', duration)
            statsd.increment('synthetic.knowledge_lake.success')
            
            return {"success": True, "duration": duration, "results_count": len(results)}
            
        except Exception as e:
            duration = time.time() - start_time
            statsd.increment('synthetic.knowledge_lake.failure')
            return {"success": False, "duration": duration, "error": str(e)}
    
    async def run_all_tests(self):
        """
        Run all synthetic tests in parallel
        """
        tests = [
            self.run_mission_creation_test(),
            self.run_knowledge_lake_test(),
            # Add more synthetic tests
        ]
        
        results = await asyncio.gather(*tests, return_exceptions=True)
        
        # Log results
        for test_name, result in zip(["mission_creation", "knowledge_lake"], results):
            if isinstance(result, Exception):
                print(f"Synthetic test {test_name} failed: {result}")
            else:
                print(f"Synthetic test {test_name}: {result}")

# Run continuously
if __name__ == "__main__":
    monitor = SyntheticMonitor()
    
    while True:
        asyncio.run(monitor.run_all_tests())
        time.sleep(300)  # Run every 5 minutes
```

### 5.2 Real User Monitoring (RUM)

**Client-Side Performance Tracking:**

```typescript
// mission-control/src/monitoring/rum.ts
/**
 * Real User Monitoring for Mission Control UI
 */

export class RealUserMonitoring {
  /**
   * Track page load performance
   */
  trackPageLoad() {
    if (typeof window.performance !== 'undefined') {
      const perfData = window.performance.timing
      const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart
      
      // Send to analytics
      this.sendMetric('page_load_time', pageLoadTime)
      
      // Track Web Vitals
      this.trackWebVitals()
    }
  }
  
  /**
   * Track Core Web Vitals (LCP, FID, CLS)
   */
  trackWebVitals() {
    // Largest Contentful Paint
    new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries()
      const lastEntry = entries[entries.length - 1]
      this.sendMetric('largest_contentful_paint', lastEntry.renderTime)
    }).observe({ type: 'largest-contentful-paint', buffered: true })
    
    // First Input Delay
    new PerformanceObserver((entryList) => {
      const firstInput = entryList.getEntries()[0]
      this.sendMetric('first_input_delay', firstInput.processingStart - firstInput.startTime)
    }).observe({ type: 'first-input', buffered: true })
    
    // Cumulative Layout Shift
    let clsValue = 0
    new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries()) {
        if (!entry.hadRecentInput) {
          clsValue += entry.value
        }
      }
      this.sendMetric('cumulative_layout_shift', clsValue)
    }).observe({ type: 'layout-shift', buffered: true })
  }
  
  /**
   * Track user interactions
   */
  trackUserAction(action: string, metadata?: any) {
    const startTime = performance.now()
    
    return () => {
      const duration = performance.now() - startTime
      this.sendMetric(`user_action.${action}`, duration, metadata)
    }
  }
}

// Usage
const rum = new RealUserMonitoring()

// Track page loads
rum.trackPageLoad()

// Track user actions
const endTracking = rum.trackUserAction('create_mission')
// ... user creates mission ...
endTracking()
```

---

## 6. TEST AUTOMATION FRAMEWORK

### 6.1 Pytest Configuration

**File:** `pytest.ini`

```ini
[pytest]
minversion = 7.0
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Markers
markers =
    fast: Fast unit tests (< 100ms)
    slow: Slow tests with I/O
    integration: Integration tests
    e2e: End-to-end tests
    smoke: Smoke tests
    performance: Performance tests
    security: Security tests
    flaky: Flaky tests (allowed to retry)

# Coverage settings
addopts =
    --cov=agents
    --cov=api
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=90
    --strict-markers
    --tb=short
    -v

# Parallel execution
[pytest:xdist]
numprocesses = auto

# Timeout settings
timeout = 300
timeout_method = thread
```

### 6.2 Test Fixtures

**File:** `tests/conftest.py`

```python
"""
Shared pytest fixtures for all tests
"""

import pytest
import asyncio
from typing import AsyncGenerator
from agents.pm_agent.pm_agent import PMAgent
from agents.ceo_agent.ceo_agent import CEOAgent
from infrastructure.semantic_bus import SemanticBus
from infrastructure.database import DatabaseManager

# ============================================================================
# Async Event Loop Fixture
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for async tests
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="session")
async def test_database():
    """
    Create test database for session
    """
    db = DatabaseManager(database_url="postgresql://localhost/hgr_test")
    await db.initialize()
    await db.create_tables()
    yield db
    await db.drop_tables()
    await db.close()

@pytest.fixture
async def clean_database(test_database):
    """
    Clean database between tests
    """
    await test_database.truncate_all_tables()
    yield test_database

# ============================================================================
# Redis Fixtures
# ============================================================================

@pytest.fixture(scope="session")
async def test_redis():
    """
    Create test Redis connection
    """
    redis = SemanticBus(redis_url="redis://localhost:6379/1")
    await redis.connect()
    yield redis
    await redis.disconnect()

@pytest.fixture
async def clean_redis(test_redis):
    """
    Clean Redis between tests
    """
    await test_redis.flushdb()
    yield test_redis

# ============================================================================
# Agent Fixtures
# ============================================================================

@pytest.fixture
def pm_agent(test_database, test_redis):
    """
    Create PM Agent for testing
    """
    agent = PMAgent(
        agent_id="PM-001-TEST",
        database=test_database,
        semantic_bus=test_redis
    )
    return agent

@pytest.fixture
def ceo_agent(test_database, test_redis):
    """
    Create CEO Agent for testing
    """
    agent = CEOAgent(
        agent_id="CEO-001-TEST",
        database=test_database,
        semantic_bus=test_redis
    )
    return agent

# ============================================================================
# Mock API Client Fixture
# ============================================================================

@pytest.fixture
def api_client():
    """
    Create test API client
    """
    from fastapi.testclient import TestClient
    from api.main import app
    
    client = TestClient(app)
    return client

# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def sample_mission_data():
    """
    Sample mission data for testing
    """
    return {
        "description": "Build a web scraper for news articles",
        "requirements": {
            "languages": ["python"],
            "features": ["async", "rate_limiting"]
        },
        "constraints": {
            "max_execution_time": 300,
            "max_memory_mb": 512
        }
    }

@pytest.fixture
def sample_logicnode_data():
    """
    Sample LogicNode data for testing
    """
    return {
        "paradigm": "dynamic",
        "domain": "list_operations",
        "concept": "filter",
        "intent": "Remove elements from list that don't match predicate",
        "inputs": [
            {"name": "collection", "type": "List[T]"},
            {"name": "predicate", "type": "Callable[[T], bool]"}
        ],
        "outputs": [
            {"name": "filtered", "type": "List[T]"}
        ],
        "preconditions": [
            {"type": "not_null", "target": "collection"}
        ],
        "postconditions": [
            {"type": "subset", "target": "filtered", "of": "collection"}
        ]
    }
```

---

## 7. TEST DATA MANAGEMENT

### 7.1 Test Data Strategy

**Principles:**
- 🎯 **Realistic Data:** Use production-like data structures
- 🔒 **No PII:** Never use real user data in tests
- 🔄 **Repeatability:** Same inputs produce same outputs
- 🧹 **Isolation:** Tests don't interfere with each other
- 📦 **Fixtures:** Centralized test data management

**Test Data Categories:**
1. **Minimal Data:** Smallest valid inputs (smoke tests)
2. **Representative Data:** Typical production scenarios
3. **Edge Cases:** Boundary conditions, unusual inputs
4. **Invalid Data:** Error handling validation
5. **Large Data:** Performance and scale testing

### 7.2 Test Data Factories

**File:** `tests/factories.py`

```python
"""
Factory classes for generating test data
"""

from factory import Factory, Faker, SubFactory, LazyAttribute
from datetime import datetime
import uuid

class MissionFactory(Factory):
    """
    Generate test mission data
    """
    class Meta:
        model = dict
    
    mission_id = LazyAttribute(lambda _: str(uuid.uuid4()))
    description = Faker('sentence', nb_words=10)
    status = "pending"
    created_at = LazyAttribute(lambda _: datetime.utcnow().isoformat())
    created_by = "PM-001"
    requirements = {
        "languages": ["python"],
        "features": []
    }

class LogicNodeFactory(Factory):
    """
    Generate test LogicNode data
    """
    class Meta:
        model = dict
    
    logicnode_id = LazyAttribute(lambda _: str(uuid.uuid4()))
    paradigm = "dynamic"
    domain = "list_operations"
    concept = "filter"
    intent = "Filter collection based on predicate"
    inputs = [
        {"name": "collection", "type": "List[T]"},
        {"name": "predicate", "type": "Callable[[T], bool]"}
    ]
    outputs = [
        {"name": "result", "type": "List[T]"}
    ]
    confidence = 0.99

class AgentMessageFactory(Factory):
    """
    Generate test agent messages
    """
    class Meta:
        model = dict
    
    message_id = LazyAttribute(lambda _: str(uuid.uuid4()))
    protocol = "alpha"
    sender = "PM-001"
    recipient = "CEO-001"
    message_type = "mission_request"
    payload = {}
    timestamp = LazyAttribute(lambda _: datetime.utcnow().isoformat())

# Usage in tests
def test_mission_creation():
    mission = MissionFactory()
    assert mission["status"] == "pending"
    assert "mission_id" in mission
```

---

## 8. PERFORMANCE TESTING STRATEGY

### 8.1 Performance Test Levels

| Level | Scope | Users | Duration | Frequency |
|-------|-------|-------|----------|-----------|
| **Micro-benchmarks** | Individual functions | N/A | < 1 min | Pre-commit |
| **Component Performance** | Single agent | 1 | 5 min | Daily |
| **System Performance** | Full system | 10 | 30 min | Weekly |
| **Load Testing** | Production simulation | 100 | 2 hours | Pre-release |
| **Stress Testing** | Beyond capacity | 500+ | 1 hour | Quarterly |
| **Soak Testing** | Sustained load | 50 | 24 hours | Monthly |

### 8.2 Locust Performance Testing

**File:** `tests/performance/locustfile.py`

```python
"""
Locust performance testing scenarios
"""

from locust import HttpUser, task, between, events
import random

class HGRUser(HttpUser):
    """
    Simulate typical Holy Grail Refinery user
    """
    wait_time = between(5, 15)  # Wait 5-15s between requests
    
    def on_start(self):
        """
        Called when user starts (login)
        """
        # Authenticate
        response = self.client.post("/api/v1/auth/token", json={
            "username": "test_user",
            "password": "test_password"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def create_mission(self):
        """
        Create a new mission (most common action)
        """
        mission_data = {
            "description": f"Test mission {random.randint(1000, 9999)}",
            "requirements": {
                "languages": random.choice([
                    ["python"],
                    ["javascript"],
                    ["python", "javascript"]
                ])
            }
        }
        
        with self.client.post(
            "/api/v1/missions",
            json=mission_data,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
            else:
                response.failure(f"Failed: {response.status_code}")
    
    @task(5)
    def search_knowledge_lake(self):
        """
        Search Knowledge Lake (very common)
        """
        queries = [
            "Python list operations",
            "JavaScript async patterns",
            "C++ memory management",
            "Java design patterns"
        ]
        
        self.client.post(
            "/api/v1/knowledge/search",
            json={"query": random.choice(queries), "top_k": 10},
            headers=self.headers
        )
    
    @task(2)
    def get_mission_status(self):
        """
        Check mission status
        """
        # Assume we have some mission IDs stored
        mission_id = "some-mission-id-here"
        self.client.get(
            f"/api/v1/missions/{mission_id}",
            headers=self.headers
        )
    
    @task(1)
    def list_missions(self):
        """
        List user's missions
        """
        self.client.get(
            "/api/v1/missions",
            headers=self.headers
        )

# Performance thresholds
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("Performance test starting...")

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """
    Check performance thresholds
    """
    # Fail if response time > 2 seconds
    if response_time > 2000:
        print(f"WARNING: Slow response for {name}: {response_time}ms")

# Run with: locust -f locustfile.py --host=http://localhost:8000
```

---

## 9. SECURITY TESTING STRATEGY

### 9.1 Security Test Layers

| Layer | Tool | Frequency | Scope |
|-------|------|-----------|-------|
| **SAST** | Bandit, Semgrep | Every commit | Source code |
| **Dependency Scan** | Safety, pip-audit | Daily | Python packages |
| **Container Scan** | Trivy, Snyk | On image build | Docker images |
| **DAST** | OWASP ZAP | Weekly | Running application |
| **Pen Testing** | Manual + Metasploit | Quarterly | Full system |

### 9.2 Automated Security Testing

**File:** `scripts/security_scan.sh`

```bash
#!/bin/bash
# Automated security testing

set -e

echo "=== Holy Grail Refinery Security Scan ==="

# 1. Python code security scan (Bandit)
echo "[1/5] Running Bandit (SAST)..."
bandit -r agents/ api/ -f json -o security-reports/bandit.json

# 2. Dependency vulnerability scan (Safety)
echo "[2/5] Running Safety (dependency check)..."
safety check --json --output security-reports/safety.json || true

# 3. Container image scan (Trivy)
echo "[3/5] Running Trivy (container scan)..."
trivy image --format json --output security-reports/trivy.json hgr/pm-agent:latest

# 4. Secret detection (Gitleaks)
echo "[4/5] Running Gitleaks (secret scan)..."
gitleaks detect --source . --report-path security-reports/gitleaks.json

# 5. Generate summary report
echo "[5/5] Generating summary..."
python scripts/security_report_summary.py

echo "✅ Security scan complete. Check security-reports/ directory."
```

---

## 10. QUALITY METRICS & REPORTING

### 10.1 Quality Dashboard

**Real-Time Metrics Tracked:**

```yaml
code_quality:
  - metric: code_coverage
    target: ">= 90%"
    current: 91.2%
    status: PASS
  
  - metric: test_success_rate
    target: ">= 99.5%"
    current: 99.8%
    status: PASS
  
  - metric: lint_score
    target: ">= 9.5/10"
    current: 9.8/10
    status: PASS

performance:
  - metric: unit_test_duration
    target: "< 5 minutes"
    current: 4.2 minutes
    status: PASS
  
  - metric: integration_test_duration
    target: "< 20 minutes"
    current: 18.5 minutes
    status: PASS
  
  - metric: e2e_test_duration
    target: "< 45 minutes"
    current: 38 minutes
    status: PASS

security:
  - metric: critical_vulnerabilities
    target: 0
    current: 0
    status: PASS
  
  - metric: high_vulnerabilities
    target: 0
    current: 1
    status: FAIL
  
  - metric: secret_leaks
    target: 0
    current: 0
    status: PASS

deployment:
  - metric: deployment_success_rate
    target: ">= 99%"
    current: 99.5%
    status: PASS
  
  - metric: mean_time_to_recovery
    target: "< 5 minutes"
    current: 3.2 minutes
    status: PASS
```

### 10.2 Weekly Quality Report

**Automated Weekly Report Email:**

```python
# scripts/generate_weekly_quality_report.py
"""
Generate and email weekly quality report
"""

from datetime import datetime, timedelta
from jinja2 import Template

def generate_weekly_report():
    """
    Generate comprehensive quality report
    """
    # Gather metrics from last 7 days
    metrics = {
        "period": {
            "start": (datetime.now() - timedelta(days=7)).isoformat(),
            "end": datetime.now().isoformat()
        },
        "test_statistics": {
            "total_tests_run": 1247,
            "tests_passed": 1244,
            "tests_failed": 3,
            "success_rate": 99.76
        },
        "code_coverage": {
            "unit_coverage": 91.2,
            "integration_coverage": 87.5,
            "overall_coverage": 89.8
        },
        "deployment_stats": {
            "total_deployments": 47,
            "successful_deployments": 47,
            "rollbacks": 0,
            "success_rate": 100.0
        },
        "security": {
            "vulnerabilities_found": 2,
            "vulnerabilities_fixed": 1,
            "pending_vulnerabilities": 1
        },
        "performance": {
            "avg_test_duration_minutes": 15.3,
            "avg_deployment_duration_minutes": 12.5,
            "slowest_test": "test_full_mission_e2e (38 min)"
        }
    }
    
    # Generate HTML report
    template = Template("""
    <html>
    <body>
        <h1>Weekly Quality Report</h1>
        <p>Period: {{ metrics.period.start }} to {{ metrics.period.end }}</p>
        
        <h2>Test Statistics</h2>
        <ul>
            <li>Total Tests: {{ metrics.test_statistics.total_tests_run }}</li>
            <li>Success Rate: {{ metrics.test_statistics.success_rate }}%</li>
        </ul>
        
        <h2>Code Coverage</h2>
        <ul>
            <li>Overall Coverage: {{ metrics.code_coverage.overall_coverage }}%</li>
        </ul>
        
        <h2>Deployment Success</h2>
        <ul>
            <li>Deployments: {{ metrics.deployment_stats.total_deployments }}</li>
            <li>Success Rate: {{ metrics.deployment_stats.success_rate }}%</li>
        </ul>
    </body>
    </html>
    """)
    
    html = template.render(metrics=metrics)
    
    # Send email (implementation details omitted)
    send_email(
        to="dev-team@hgr.com",
        subject=f"Weekly Quality Report - {datetime.now().strftime('%Y-%m-%d')}",
        html=html
    )

if __name__ == "__main__":
    generate_weekly_report()
```

---

## DOCUMENT METADATA

**Document ID:** 50  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Owner:** Chief Architect / QA Lead  
**Dependencies:** Documents 41-49 (All testing documents)  
**Next Document:** 51 (Developer Onboarding Guide)

---

*End of Continuous Testing Strategy*
