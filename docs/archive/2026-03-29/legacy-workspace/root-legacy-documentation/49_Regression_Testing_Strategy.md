# DOCUMENT 49: REGRESSION TESTING STRATEGY

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Quality & Testing

**Document ID:** 49  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive regression testing strategy** for the Holy Grail Refinery system. Regression testing ensures that new changes don't break existing functionality and that the system maintains its 99.9999% accuracy guarantee over time.

**Regression Testing Goals:**
- 🔒 **Prevent Breakage:** Catch regressions before deployment
- 📊 **Track Quality:** Monitor quality trends over time
- ⚡ **Fast Feedback:** Rapid detection of introduced bugs
- 🎯 **Targeted Testing:** Focus on high-risk areas
- 📈 **Continuous Improvement:** Expand coverage based on defects

**Key Principles:**
- **Automated:** All regression tests automated in CI/CD
- **Comprehensive:** Cover all critical functionality
- **Maintainable:** Easy to update as system evolves
- **Fast:** Complete suite runs in < 30 minutes
- **Reliable:** Deterministic, no flaky tests

**Regression Test Categories:**

| Category | Test Count | Run Frequency | Max Duration |
|----------|-----------|---------------|--------------|
| **Smoke Tests** | 50 | Every commit | 2 minutes |
| **Core Functionality** | 500 | Every PR | 10 minutes |
| **Full Regression** | 2000+ | Nightly | 30 minutes |
| **Performance Regression** | 100 | Weekly | 2 hours |
| **Security Regression** | 200 | Weekly | 1 hour |

---

## TABLE OF CONTENTS

1. [Regression Testing Architecture](#1-regression-testing-architecture)
2. [Test Selection Strategy](#2-test-selection-strategy)
3. [Baseline Management](#3-baseline-management)
4. [Smoke Test Suite](#4-smoke-test-suite)
5. [Functional Regression Tests](#5-functional-regression-tests)
6. [Performance Regression Detection](#6-performance-regression-detection)
7. [Visual Regression Testing](#7-visual-regression-testing)
8. [API Contract Regression](#8-api-contract-regression)
9. [Database Schema Regression](#9-database-schema-regression)
10. [Regression Triage & Resolution](#10-regression-triage--resolution)

---

## 1. REGRESSION TESTING ARCHITECTURE

### 1.1 Multi-Tiered Approach

**Pyramid Structure:**
```
                    /\
                   /  \
                  / E2E \ ────────── 100 tests (5% of suite)
                 /------\             Nightly, 30 min
                /        \
               / Integr.  \ ───────── 400 tests (20% of suite)
              /------------\          Every PR, 10 min
             /              \
            /  Unit Tests    \ ────── 1500 tests (75% of suite)
           /------------------\       Every commit, 5 min
          /____________________\
```

### 1.2 Continuous Regression Testing

**CI/CD Integration:**
```yaml
# .github/workflows/regression-tests.yml
name: Regression Tests

on:
  push:
    branches: [main, develop]
  pull_request:
  schedule:
    - cron: '0 2 * * *'  # Nightly at 2 AM

jobs:
  smoke-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Smoke Tests
        run: |
          pytest tests/smoke/ \
            --maxfail=1 \
            -v \
            --tb=short
      
      - name: Fail Fast on Smoke Failure
        if: failure()
        run: |
          echo "::error::Smoke tests failed - stopping pipeline"
          exit 1
  
  unit-regression:
    needs: smoke-tests
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Unit Regression Tests
        run: |
          pytest tests/unit/ \
            --cov=src \
            --cov-report=xml \
            --cov-fail-under=90
      
      - name: Upload Coverage
        uses: codecov/codecov-action@v3
  
  integration-regression:
    needs: smoke-tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v3
      
      - name: Start Test Environment
        run: docker-compose -f docker-compose.test.yml up -d
      
      - name: Run Integration Tests
        run: |
          pytest tests/integration/ \
            --durations=10
  
  full-regression:
    if: github.event_name == 'schedule'
    needs: [unit-regression, integration-regression]
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Full Regression Suite
        run: |
          pytest tests/ \
            --regression \
            --html=regression-report.html \
            --self-contained-html
      
      - name: Upload Report
        uses: actions/upload-artifact@v3
        with:
          name: regression-report
          path: regression-report.html
```

---

## 2. TEST SELECTION STRATEGY

### 2.1 Risk-Based Test Selection

**Prioritize High-Risk Areas:**
```python
"""
Risk-based test selection
"""

from enum import Enum
from dataclasses import dataclass
from typing import List

class RiskLevel(Enum):
    CRITICAL = 4  # Core system functions
    HIGH = 3      # Important features
    MEDIUM = 2    # Standard features
    LOW = 1       # Nice-to-have features

@dataclass
class TestCase:
    """Test case with risk metadata"""
    test_id: str
    name: str
    risk_level: RiskLevel
    last_failure: Optional[datetime]
    execution_time_ms: int
    change_frequency: float  # How often code changes

class RiskBasedSelector:
    """
    Select tests based on risk and change impact
    """
    
    def select_tests_for_change(
        self,
        changed_files: List[str],
        all_tests: List[TestCase],
        time_budget_minutes: int = 10
    ) -> List[TestCase]:
        """
        Select tests to run based on changed files
        
        Strategy:
        1. Always run tests for directly changed modules
        2. Run high-risk tests
        3. Run recently failing tests
        4. Fill time budget with other tests by priority
        """
        selected = []
        
        # Step 1: Direct impact tests
        directly_impacted = self._find_directly_impacted_tests(
            changed_files,
            all_tests
        )
        selected.extend(directly_impacted)
        
        # Step 2: Critical risk tests
        critical_tests = [
            t for t in all_tests
            if t.risk_level == RiskLevel.CRITICAL
            and t not in selected
        ]
        selected.extend(critical_tests)
        
        # Step 3: Recently failing tests
        recently_failed = [
            t for t in all_tests
            if t.last_failure is not None
            and (datetime.now() - t.last_failure).days < 7
            and t not in selected
        ]
        selected.extend(recently_failed)
        
        # Step 4: Fill time budget
        remaining_time = (time_budget_minutes * 60 * 1000) - sum(
            t.execution_time_ms for t in selected
        )
        
        remaining_tests = [t for t in all_tests if t not in selected]
        remaining_tests.sort(
            key=lambda t: (t.risk_level.value, -t.change_frequency),
            reverse=True
        )
        
        for test in remaining_tests:
            if test.execution_time_ms <= remaining_time:
                selected.append(test)
                remaining_time -= test.execution_time_ms
        
        return selected
    
    def _find_directly_impacted_tests(
        self,
        changed_files: List[str],
        all_tests: List[TestCase]
    ) -> List[TestCase]:
        """
        Find tests that directly test changed code
        """
        # Map source files to test files
        # (Implementation specific to project structure)
        impacted = []
        
        for changed_file in changed_files:
            # Find corresponding test file
            test_file = self._get_test_file_for_source(changed_file)
            
            # Find tests in that file
            tests_in_file = [
                t for t in all_tests
                if test_file in t.test_id
            ]
            impacted.extend(tests_in_file)
        
        return impacted
```

### 2.2 Change Impact Analysis

**Detect Affected Components:**
```python
"""
Change impact analysis
"""

import ast
from pathlib import Path
from typing import Set, Dict

class ChangeImpactAnalyzer:
    """
    Analyze which components are affected by code changes
    """
    
    def analyze_changes(
        self,
        changed_files: List[Path]
    ) -> Dict[str, Set[str]]:
        """
        Analyze impact of changed files
        
        Returns:
            Dictionary mapping component -> affected test suites
        """
        impact_map = {}
        
        for file_path in changed_files:
            if file_path.suffix == '.py':
                impact = self._analyze_python_file(file_path)
            else:
                impact = self._analyze_generic_file(file_path)
            
            impact_map[str(file_path)] = impact
        
        return impact_map
    
    def _analyze_python_file(self, file_path: Path) -> Set[str]:
        """
        Analyze Python file to determine impact
        """
        affected = set()
        
        # Parse file
        code = file_path.read_text()
        tree = ast.parse(code)
        
        # Check for agent classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if 'Agent' in node.name:
                    affected.add('agent_tests')
                if 'Audit' in node.name:
                    affected.add('audit_tests')
        
        # Check for database models
        if 'models' in str(file_path):
            affected.add('database_tests')
        
        # Check for API endpoints
        if 'api' in str(file_path):
            affected.add('api_tests')
        
        return affected
```

---

## 3. BASELINE MANAGEMENT

### 3.1 Golden Master Testing

**Establish Known-Good Baselines:**
```python
"""
Golden master testing for regression detection
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Dict

class GoldenMaster:
    """
    Golden master / snapshot testing
    """
    
    def __init__(self, baseline_dir: Path):
        self.baseline_dir = baseline_dir
        self.baseline_dir.mkdir(exist_ok=True)
    
    def assert_matches_baseline(
        self,
        test_name: str,
        actual_output: Any,
        update_baseline: bool = False
    ) -> None:
        """
        Compare actual output against stored baseline
        
        Args:
            test_name: Unique test identifier
            actual_output: Output from current test run
            update_baseline: If True, update baseline instead of comparing
        """
        baseline_file = self.baseline_dir / f"{test_name}.baseline.json"
        
        # Serialize actual output
        actual_json = json.dumps(actual_output, sort_keys=True, indent=2)
        
        if update_baseline or not baseline_file.exists():
            # Store new baseline
            baseline_file.write_text(actual_json)
            print(f"📝 Updated baseline: {test_name}")
            return
        
        # Load existing baseline
        expected_json = baseline_file.read_text()
        expected = json.loads(expected_json)
        
        # Compare
        if actual_output != expected:
            # Generate diff
            diff = self._generate_diff(expected, actual_output)
            
            raise AssertionError(
                f"Output does not match baseline for {test_name}\n"
                f"Diff:\n{diff}\n\n"
                f"To update baseline, run with --update-baselines"
            )
    
    def _generate_diff(self, expected: Any, actual: Any) -> str:
        """Generate human-readable diff"""
        import difflib
        
        expected_str = json.dumps(expected, sort_keys=True, indent=2)
        actual_str = json.dumps(actual, sort_keys=True, indent=2)
        
        diff = difflib.unified_diff(
            expected_str.splitlines(),
            actual_str.splitlines(),
            lineterm='',
            fromfile='baseline',
            tofile='actual'
        )
        
        return '\n'.join(diff)

# Usage in tests:
def test_logicnode_extraction():
    """
    Test LogicNode extraction produces expected output
    """
    golden = GoldenMaster(Path('tests/baselines'))
    
    code = '''
def filter_list(items, predicate):
    return [item for item in items if predicate(item)]
'''
    
    agent = PythonExtractionAgent()
    logicnode = agent.extract_logicnode(code)
    
    # Compare against baseline
    golden.assert_matches_baseline(
        'logicnode_extraction_filter',
        logicnode.to_dict()
    )
```

### 3.2 Baseline Versioning

**Track Baseline Evolution:**
```python
"""
Baseline version management
"""

from dataclasses import dataclass
from datetime import datetime

@dataclass
class BaselineVersion:
    """Baseline version metadata"""
    version: str
    created_at: datetime
    commit_hash: str
    description: str
    test_count: int

class BaselineManager:
    """
    Manage baseline versions
    """
    
    def __init__(self, baseline_dir: Path):
        self.baseline_dir = baseline_dir
        self.versions_file = baseline_dir / 'versions.json'
    
    def create_baseline_version(
        self,
        version: str,
        commit_hash: str,
        description: str
    ) -> BaselineVersion:
        """
        Create new baseline version
        """
        # Count baseline files
        test_count = len(list(self.baseline_dir.glob('*.baseline.json')))
        
        baseline_version = BaselineVersion(
            version=version,
            created_at=datetime.now(),
            commit_hash=commit_hash,
            description=description,
            test_count=test_count
        )
        
        # Store version metadata
        self._save_version(baseline_version)
        
        # Tag baselines with version
        self._tag_baselines(version)
        
        return baseline_version
    
    def compare_versions(
        self,
        version_a: str,
        version_b: str
    ) -> Dict[str, Any]:
        """
        Compare two baseline versions
        """
        baselines_a = self._load_baselines(version_a)
        baselines_b = self._load_baselines(version_b)
        
        differences = {
            'added': [],
            'removed': [],
            'modified': []
        }
        
        # Find differences
        for test_name in baselines_b:
            if test_name not in baselines_a:
                differences['added'].append(test_name)
            elif baselines_a[test_name] != baselines_b[test_name]:
                differences['modified'].append(test_name)
        
        for test_name in baselines_a:
            if test_name not in baselines_b:
                differences['removed'].append(test_name)
        
        return differences
```

---

## 4. SMOKE TEST SUITE

### 4.1 Critical Path Tests

**Essential Functionality Checks:**
```python
"""
Smoke tests - critical functionality
"""

import pytest

class TestSmokeTests:
    """
    Smoke test suite - runs on every commit
    
    These tests verify the most critical functionality.
    If any fail, the build should be rejected immediately.
    """
    
    def test_system_starts(self):
        """System can start successfully"""
        # Start core services
        result = subprocess.run(
            ['docker-compose', 'up', '-d'],
            capture_output=True
        )
        assert result.returncode == 0
    
    def test_database_accessible(self, test_database):
        """Database is accessible"""
        result = await test_database.fetchval('SELECT 1')
        assert result == 1
    
    def test_semantic_bus_operational(self):
        """Semantic Bus is operational"""
        bus = SemanticBus()
        
        # Send message
        await bus.publish('test', {'data': 'hello'})
        
        # Receive message
        messages = []
        async for msg in bus.subscribe('test'):
            messages.append(msg)
            break
        
        assert len(messages) == 1
    
    def test_agent_can_start(self):
        """Agent can be instantiated"""
        agent = PythonExtractionAgent(agent_id='AGENT-PY-001-test')
        assert agent is not None
        assert agent.agent_id == 'AGENT-PY-001-test'
    
    def test_simple_code_extraction(self):
        """Simple code can be extracted"""
        agent = PythonExtractionAgent()
        
        code = "def add(a, b): return a + b"
        
        logicnode = agent.extract_logicnode(code)
        
        assert logicnode is not None
        assert logicnode.concept_name is not None
    
    def test_api_responds(self):
        """API endpoint responds"""
        response = requests.get('http://localhost:8000/health')
        assert response.status_code == 200
    
    def test_logicnode_can_be_saved(self, test_database):
        """LogicNode can be saved to database"""
        logicnode = {
            'logicnode_id': 'SMOKE-TEST-001',
            'concept_name': 'test',
            'source_language': 'python'
        }
        
        await test_database.execute(
            "INSERT INTO logicnodes (logicnode_id, concept_name, source_language) VALUES ($1, $2, $3)",
            logicnode['logicnode_id'],
            logicnode['concept_name'],
            logicnode['source_language']
        )
        
        # Verify it was saved
        result = await test_database.fetchrow(
            "SELECT * FROM logicnodes WHERE logicnode_id = $1",
            'SMOKE-TEST-001'
        )
        
        assert result is not None
```

---

## 5. FUNCTIONAL REGRESSION TESTS

### 5.1 Feature-Based Test Organization

**Organize by Feature:**
```
tests/regression/
├── agents/
│   ├── test_python_agent_regression.py
│   ├── test_javascript_agent_regression.py
│   └── test_audit_agents_regression.py
├── extraction/
│   ├── test_semantic_extraction_regression.py
│   └── test_logicnode_generation_regression.py
├── protocols/
│   ├── test_protocol_alpha_regression.py
│   └── test_protocol_beta_regression.py
└── api/
    ├── test_api_endpoints_regression.py
    └── test_authentication_regression.py
```

### 5.2 Example Regression Tests

**Agent Functionality Regression:**
```python
"""
Agent functionality regression tests
"""

class TestPythonAgentRegression:
    """
    Regression tests for Python extraction agent
    """
    
    def test_list_comprehension_extraction(self, golden_master):
        """
        Regression: List comprehension extraction
        
        Historical issue: Lost predicate information in v0.9
        Fixed in: v1.0
        """
        agent = PythonExtractionAgent()
        
        code = '''
def filter_positive(numbers):
    return [n for n in numbers if n > 0]
'''
        
        logicnode = agent.extract_logicnode(code)
        
        # Verify postcondition includes predicate
        assert any(
            'n > 0' in str(pc) or 'positive' in str(pc).lower()
            for pc in logicnode.postconditions
        ), "Predicate information missing from postconditions"
        
        # Compare against baseline
        golden_master.assert_matches_baseline(
            'python_agent_list_comprehension',
            logicnode.to_dict()
        )
    
    def test_async_function_extraction(self, golden_master):
        """
        Regression: Async function extraction
        
        Historical issue: Side effects not captured for async in v1.1
        Fixed in: v1.2
        """
        agent = PythonExtractionAgent()
        
        code = '''
async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
'''
        
        logicnode = agent.extract_logicnode(code)
        
        # Verify side effects include network I/O
        assert any(
            'network' in str(se).lower() or 'io' in str(se).lower()
            for se in logicnode.side_effects
        ), "Network side effect not captured"
        
        golden_master.assert_matches_baseline(
            'python_agent_async_function',
            logicnode.to_dict()
        )
    
    def test_class_method_extraction(self, golden_master):
        """
        Regression: Class method extraction
        
        Historical issue: 'self' parameter caused type errors in v1.3
        Fixed in: v1.4
        """
        agent = PythonExtractionAgent()
        
        code = '''
class Calculator:
    def add(self, a, b):
        return a + b
'''
        
        logicnode = agent.extract_logicnode(code)
        
        # Verify 'self' is handled correctly
        input_names = [inp['name'] for inp in logicnode.inputs]
        assert 'self' not in input_names, "'self' should be filtered out"
        
        golden_master.assert_matches_baseline(
            'python_agent_class_method',
            logicnode.to_dict()
        )
```

---

## 6. PERFORMANCE REGRESSION DETECTION

### 6.1 Performance Benchmarking

**Track Performance Over Time:**
```python
"""
Performance regression detection
"""

import time
from dataclasses import dataclass
from typing import List

@dataclass
class PerformanceMetric:
    """Performance measurement"""
    test_name: str
    metric_name: str
    value: float
    unit: str
    timestamp: datetime
    commit_hash: str

class PerformanceRegressionDetector:
    """
    Detect performance regressions
    """
    
    def __init__(self, baseline_db: str):
        self.baseline_db = baseline_db
    
    def measure_performance(
        self,
        test_name: str,
        func: Callable,
        iterations: int = 100
    ) -> PerformanceMetric:
        """
        Measure performance of function
        """
        # Warmup
        for _ in range(10):
            func()
        
        # Measure
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append((end - start) * 1000)  # ms
        
        # Calculate statistics
        import numpy as np
        median_time = np.median(times)
        
        metric = PerformanceMetric(
            test_name=test_name,
            metric_name='execution_time_ms',
            value=median_time,
            unit='ms',
            timestamp=datetime.now(),
            commit_hash=self._get_current_commit()
        )
        
        return metric
    
    def check_for_regression(
        self,
        current_metric: PerformanceMetric,
        threshold_percent: float = 10.0
    ) -> bool:
        """
        Check if current measurement is a regression
        
        Args:
            current_metric: Current measurement
            threshold_percent: % degradation considered regression
        
        Returns:
            True if regression detected
        """
        # Get baseline
        baseline = self._load_baseline(current_metric.test_name)
        
        if baseline is None:
            # No baseline - store this as baseline
            self._store_baseline(current_metric)
            return False
        
        # Calculate degradation
        degradation_percent = (
            (current_metric.value - baseline.value) / baseline.value
        ) * 100
        
        if degradation_percent > threshold_percent:
            print(f"⚠️ Performance regression detected!")
            print(f"   Test: {current_metric.test_name}")
            print(f"   Baseline: {baseline.value:.2f} {baseline.unit}")
            print(f"   Current: {current_metric.value:.2f} {current_metric.unit}")
            print(f"   Degradation: {degradation_percent:.1f}%")
            return True
        
        return False

# Usage in tests:
@pytest.mark.performance
def test_extraction_performance_regression():
    """
    Track code extraction performance
    """
    detector = PerformanceRegressionDetector('performance_baselines.db')
    
    agent = PythonExtractionAgent()
    code = Path('tests/fixtures/medium_1k_loc.py').read_text()
    
    # Measure performance
    metric = detector.measure_performance(
        'extraction_1k_loc',
        lambda: agent.extract_logicnode(code),
        iterations=50
    )
    
    # Check for regression
    has_regression = detector.check_for_regression(metric, threshold_percent=10)
    
    assert not has_regression, "Performance regression detected"
```

### 6.2 Performance Trend Visualization

**Track Trends:**
```python
"""
Visualize performance trends
"""

import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def visualize_performance_trends(
    test_name: str,
    days: int = 30
) -> None:
    """
    Generate performance trend chart
    """
    # Load historical data
    metrics = load_performance_history(test_name, days=days)
    
    # Plot
    dates = [m.timestamp for m in metrics]
    values = [m.value for m in metrics]
    
    plt.figure(figsize=(12, 6))
    plt.plot(dates, values, marker='o')
    plt.axhline(
        y=metrics[0].value,
        color='g',
        linestyle='--',
        label='Baseline'
    )
    plt.xlabel('Date')
    plt.ylabel('Execution Time (ms)')
    plt.title(f'Performance Trend: {test_name}')
    plt.legend()
    plt.grid(True)
    plt.savefig(f'performance_trend_{test_name}.png')
```

---

## 7. VISUAL REGRESSION TESTING

### 7.1 UI Screenshot Comparison

**For Mission Control UI:**
```python
"""
Visual regression testing
"""

from selenium import webdriver
from PIL import Image, ImageChops

class VisualRegressionTester:
    """
    Visual regression testing for UI
    """
    
    def __init__(self, baseline_dir: Path):
        self.baseline_dir = baseline_dir
        self.driver = webdriver.Chrome()
    
    def capture_screenshot(
        self,
        url: str,
        test_name: str
    ) -> Path:
        """
        Capture screenshot of page
        """
        self.driver.get(url)
        self.driver.set_window_size(1920, 1080)
        
        # Wait for page to load
        time.sleep(2)
        
        screenshot_path = Path(f'screenshots/{test_name}.png')
        self.driver.save_screenshot(str(screenshot_path))
        
        return screenshot_path
    
    def compare_with_baseline(
        self,
        current_screenshot: Path,
        test_name: str,
        threshold: float = 0.01
    ) -> bool:
        """
        Compare screenshot with baseline
        
        Args:
            current_screenshot: Path to current screenshot
            test_name: Test identifier
            threshold: Max allowed difference (0-1)
        
        Returns:
            True if images match (within threshold)
        """
        baseline_path = self.baseline_dir / f"{test_name}.png"
        
        if not baseline_path.exists():
            # No baseline - save current as baseline
            shutil.copy(current_screenshot, baseline_path)
            return True
        
        # Load images
        baseline = Image.open(baseline_path)
        current = Image.open(current_screenshot)
        
        # Compare
        diff = ImageChops.difference(baseline, current)
        
        # Calculate difference percentage
        diff_pixels = sum(sum(pixel) for pixel in diff.getdata())
        total_pixels = baseline.size[0] * baseline.size[1] * 3  # RGB
        diff_percent = diff_pixels / total_pixels
        
        if diff_percent > threshold:
            # Save diff image
            diff.save(f'screenshots/{test_name}_diff.png')
            print(f"⚠️ Visual regression detected: {diff_percent:.2%} difference")
            return False
        
        return True

# Usage:
def test_dashboard_visual_regression():
    """
    Visual regression test for dashboard
    """
    tester = VisualRegressionTester(Path('tests/baselines/visual'))
    
    # Capture current screenshot
    screenshot = tester.capture_screenshot(
        'http://localhost:3000/dashboard',
        'dashboard_main'
    )
    
    # Compare with baseline
    matches = tester.compare_with_baseline(screenshot, 'dashboard_main')
    
    assert matches, "Dashboard visual regression detected"
```

---

## 8. API CONTRACT REGRESSION

### 8.1 API Contract Testing

**Ensure API Backward Compatibility:**
```python
"""
API contract regression testing
"""

from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass
class APIContract:
    """API endpoint contract"""
    endpoint: str
    method: str
    request_schema: Dict[str, Any]
    response_schema: Dict[str, Any]
    status_codes: List[int]

class APIContractTester:
    """
    Test API contract adherence
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.contracts = self._load_contracts()
    
    def test_endpoint_contract(
        self,
        contract: APIContract
    ) -> bool:
        """
        Test if endpoint adheres to contract
        """
        # Make request
        response = requests.request(
            method=contract.method,
            url=f"{self.base_url}{contract.endpoint}",
            json=contract.request_schema
        )
        
        # Check status code
        assert response.status_code in contract.status_codes, \
            f"Unexpected status code: {response.status_code}"
        
        # Validate response schema
        response_data = response.json()
        self._validate_schema(response_data, contract.response_schema)
        
        return True
    
    def _validate_schema(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> None:
        """
        Validate data against schema
        """
        for field, field_type in schema.items():
            assert field in data, f"Missing field: {field}"
            
            actual_type = type(data[field]).__name__
            expected_type = field_type
            
            # Type checking logic...

# Test all API endpoints
def test_api_contract_regression():
    """
    Ensure all API endpoints maintain their contracts
    """
    tester = APIContractTester('http://localhost:8000')
    
    # Test each contract
    for contract in tester.contracts:
        tester.test_endpoint_contract(contract)
```

---

## 9. DATABASE SCHEMA REGRESSION

### 9.1 Schema Version Testing

**Ensure Migration Compatibility:**
```python
"""
Database schema regression testing
"""

class SchemaRegressionTester:
    """
    Test database schema changes
    """
    
    async def test_migration_reversibility(self):
        """
        Test that migrations can be reversed
        """
        # Apply migration
        await self._apply_migration('0023_add_confidence_field')
        
        # Verify schema
        schema_after = await self._get_schema()
        assert 'confidence' in schema_after['logicnodes']
        
        # Reverse migration
        await self._reverse_migration('0023_add_confidence_field')
        
        # Verify schema restored
        schema_before = await self._get_schema()
        assert 'confidence' not in schema_before['logicnodes']
    
    async def test_data_preserved_after_migration(self):
        """
        Test that existing data is preserved
        """
        # Insert test data
        test_data = {'logicnode_id': 'SCHEMA-TEST-001', ...}
        await self.db.execute("INSERT INTO logicnodes (...) VALUES (...)")
        
        # Apply migration
        await self._apply_migration('0024_add_index')
        
        # Verify data still exists
        result = await self.db.fetchrow(
            "SELECT * FROM logicnodes WHERE logicnode_id = $1",
            'SCHEMA-TEST-001'
        )
        assert result is not None
```

---

## 10. REGRESSION TRIAGE & RESOLUTION

### 10.1 Regression Classification

**Triage Process:**
```python
"""
Regression triage
"""

from enum import Enum

class RegressionSeverity(Enum):
    CRITICAL = "critical"      # System broken, blocks all work
    HIGH = "high"             # Major feature broken
    MEDIUM = "medium"         # Minor feature issue
    LOW = "low"              # Edge case or cosmetic

@dataclass
class Regression:
    """Detected regression"""
    test_name: str
    failure_message: str
    introduced_in_commit: str
    severity: RegressionSeverity
    affected_components: List[str]

class RegressionTriager:
    """
    Triage and prioritize regressions
    """
    
    def classify_regression(
        self,
        test_failure: Dict[str, Any]
    ) -> Regression:
        """
        Classify a test failure as regression
        """
        # Determine severity
        if 'smoke' in test_failure['test_name']:
            severity = RegressionSeverity.CRITICAL
        elif 'api' in test_failure['test_name']:
            severity = RegressionSeverity.HIGH
        else:
            severity = RegressionSeverity.MEDIUM
        
        # Find introducing commit
        introducing_commit = self._bisect_failure(test_failure['test_name'])
        
        return Regression(
            test_name=test_failure['test_name'],
            failure_message=test_failure['message'],
            introduced_in_commit=introducing_commit,
            severity=severity,
            affected_components=test_failure['components']
        )
```

### 10.2 Automated Regression Reporting

**Generate Regression Report:**
```markdown
# Regression Test Report

**Date:** February 6, 2026  
**Commit:** abc123def  
**Branch:** feature/new-extraction  

## Summary
- **Total Tests:** 2000
- **Passed:** 1985 (99.25%)
- **Failed:** 15 (0.75%)
- **Regressions Detected:** 3

## Critical Regressions (0)
None

## High Priority Regressions (2)

### REG-001: API endpoint returns 500
- **Test:** `test_api_extract_endpoint`
- **Introduced in:** commit xyz789
- **Error:** Internal server error when processing async code
- **Action Required:** Fix before merge

### REG-002: Performance degradation
- **Test:** `test_extraction_performance`
- **Baseline:** 450ms
- **Current:** 620ms (+37%)
- **Action Required:** Investigate performance issue

## Medium Priority Regressions (1)

### REG-003: Edge case handling
- **Test:** `test_unicode_edge_cases`
- **Error:** UnicodeDecodeError on rare characters
- **Action Required:** Fix in next sprint
```

---

## DOCUMENT METADATA

**Document ID:** 49  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Owner:** QA Engineering Team  
**Dependencies:** Documents 41-48 (Testing suite)  
**Next Document:** 50 (Test Automation Infrastructure)

---

*End of Regression Testing Strategy*
