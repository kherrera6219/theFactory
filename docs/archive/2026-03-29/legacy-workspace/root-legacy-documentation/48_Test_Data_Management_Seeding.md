# DOCUMENT 48: TEST DATA MANAGEMENT & SEEDING
## Holy Grail Refinery - Quality & Testing

**Document ID:** 48  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive test data management and database seeding specifications** for the Holy Grail Refinery system. Proper test data management ensures consistent, reliable, and repeatable testing across unit, integration, and system levels.

**Test Data Management Goals:**
- 🗄️ **Comprehensive Coverage:** Test data covering all domains and edge cases
- 🔄 **Repeatability:** Deterministic test data generation
- 🎯 **Realistic Scenarios:** Data reflecting production patterns
- 🧹 **Clean State:** Isolated test environments with proper cleanup
- 📊 **Version Control:** Test data versioned alongside code

**Key Principles:**
- **Isolation:** Each test suite has dedicated test data
- **Determinism:** Seeded random generation for reproducibility
- **Privacy:** No production data in test environments
- **Efficiency:** Fast data seeding for rapid test execution
- **Maintenance:** Easy updates as system evolves

**Test Data Categories:**

| Category | Size | Purpose | Refresh Rate |
|----------|------|---------|--------------|
| **Unit Test Fixtures** | Small (KB) | Individual function tests | Per test |
| **Integration Test Data** | Medium (MB) | Component interaction tests | Per suite |
| **System Test Corpus** | Large (GB) | End-to-end scenarios | Daily |
| **Performance Benchmarks** | Extra Large (10GB+) | Load/stress testing | Weekly |
| **Audit Test Cases** | Curated (MB) | Known good/bad LogicNodes | Per release |

---

## TABLE OF CONTENTS

1. [Test Data Architecture](#1-test-data-architecture)
2. [Database Seeding Strategy](#2-database-seeding-strategy)
3. [Test Fixtures & Factories](#3-test-fixtures--factories)
4. [Code Corpus Generation](#4-code-corpus-generation)
5. [LogicNode Test Data](#5-logicnode-test-data)
6. [Multi-Language Test Data](#6-multi-language-test-data)
7. [Test Data Versioning](#7-test-data-versioning)
8. [Test Environment Management](#8-test-environment-management)
9. [Data Cleanup & Isolation](#9-data-cleanup--isolation)
10. [Production Data Sanitization](#10-production-data-sanitization)

---

## 1. TEST DATA ARCHITECTURE

### 1.1 Test Data Hierarchy

**Three-Tier Data Structure:**
```
┌─────────────────────────────────────────────┐
│   Tier 1: Static Test Data                 │
│   - Committed to version control            │
│   - Small, carefully curated datasets       │
│   - Known edge cases and examples           │
├─────────────────────────────────────────────┤
│   Tier 2: Generated Test Data              │
│   - Procedurally generated on demand        │
│   - Large datasets for stress testing       │
│   - Seeded for reproducibility              │
├─────────────────────────────────────────────┤
│   Tier 3: Ephemeral Test Data              │
│   - Created during test execution           │
│   - Cleaned up automatically                │
│   - Per-test isolation                      │
└─────────────────────────────────────────────┘
```

### 1.2 Test Data Storage

**Directory Structure:**
```
tests/
├── fixtures/                          # Static test data (Tier 1)
│   ├── code_samples/
│   │   ├── python/
│   │   │   ├── simple_functions.py
│   │   │   ├── classes.py
│   │   │   ├── async_code.py
│   │   │   └── edge_cases.py
│   │   ├── javascript/
│   │   ├── rust/
│   │   └── ...
│   ├── logicnodes/
│   │   ├── perfect_examples.json
│   │   ├── known_errors.json
│   │   └── edge_cases.json
│   └── databases/
│       ├── minimal_seed.sql
│       ├── standard_seed.sql
│       └── full_seed.sql
│
├── generators/                        # Data generators (Tier 2)
│   ├── code_generator.py
│   ├── logicnode_generator.py
│   └── corpus_builder.py
│
└── data/                              # Generated data (gitignored)
    ├── corpus/
    ├── performance/
    └── temp/
```

---

## 2. DATABASE SEEDING STRATEGY

### 2.1 Multi-Level Seeding

**Seeding Levels:**
```python
"""
Database seeding framework
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Callable
import asyncpg

class SeedLevel(Enum):
    """Seeding levels"""
    MINIMAL = "minimal"      # Essential data only (fast)
    STANDARD = "standard"    # Typical test scenarios
    FULL = "full"           # Comprehensive test data
    PERFORMANCE = "performance"  # Large datasets for load testing

@dataclass
class SeedScript:
    """Database seed script"""
    name: str
    level: SeedLevel
    dependencies: List[str]
    script_path: str
    execution_time_est: float  # seconds
    
class DatabaseSeeder:
    """
    Manage database seeding for tests
    """
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.scripts = self._load_seed_scripts()
    
    def _load_seed_scripts(self) -> List[SeedScript]:
        """
        Define seed scripts in dependency order
        """
        return [
            # Minimal seed - essential reference data
            SeedScript(
                name="languages",
                level=SeedLevel.MINIMAL,
                dependencies=[],
                script_path="fixtures/databases/seed_languages.sql",
                execution_time_est=0.1
            ),
            SeedScript(
                name="pods",
                level=SeedLevel.MINIMAL,
                dependencies=["languages"],
                script_path="fixtures/databases/seed_pods.sql",
                execution_time_est=0.1
            ),
            SeedScript(
                name="agents",
                level=SeedLevel.MINIMAL,
                dependencies=["pods"],
                script_path="fixtures/databases/seed_agents.sql",
                execution_time_est=0.2
            ),
            
            # Standard seed - typical test scenarios
            SeedScript(
                name="logicnodes_standard",
                level=SeedLevel.STANDARD,
                dependencies=["agents", "languages"],
                script_path="fixtures/databases/seed_logicnodes_standard.sql",
                execution_time_est=2.0
            ),
            SeedScript(
                name="concept_mappings",
                level=SeedLevel.STANDARD,
                dependencies=["logicnodes_standard"],
                script_path="fixtures/databases/seed_concept_mappings.sql",
                execution_time_est=1.0
            ),
            
            # Full seed - comprehensive coverage
            SeedScript(
                name="logicnodes_full",
                level=SeedLevel.FULL,
                dependencies=["agents", "languages"],
                script_path="fixtures/databases/seed_logicnodes_full.sql",
                execution_time_est=10.0
            ),
            
            # Performance seed - large datasets
            SeedScript(
                name="logicnodes_performance",
                level=SeedLevel.PERFORMANCE,
                dependencies=["agents", "languages"],
                script_path="generators/seed_logicnodes_bulk.py",
                execution_time_est=60.0
            ),
        ]
    
    async def seed_database(
        self,
        level: SeedLevel = SeedLevel.STANDARD,
        clean: bool = True
    ) -> None:
        """
        Seed database to specified level
        
        Args:
            level: How much data to seed
            clean: Clean database before seeding
        """
        conn = await asyncpg.connect(self.db_url)
        
        try:
            if clean:
                await self._clean_database(conn)
            
            # Filter scripts by level
            scripts_to_run = [
                s for s in self.scripts
                if s.level.value <= level.value
            ]
            
            # Execute in dependency order
            for script in scripts_to_run:
                await self._execute_seed_script(conn, script)
        
        finally:
            await conn.close()
    
    async def _clean_database(self, conn: asyncpg.Connection) -> None:
        """
        Clean all test data from database
        """
        # Drop all tables in test schema
        await conn.execute("""
            DROP SCHEMA IF EXISTS test CASCADE;
            CREATE SCHEMA test;
        """)
    
    async def _execute_seed_script(
        self,
        conn: asyncpg.Connection,
        script: SeedScript
    ) -> None:
        """
        Execute a single seed script
        """
        print(f"Seeding: {script.name} (est. {script.execution_time_est}s)")
        
        if script.script_path.endswith('.sql'):
            # SQL script
            with open(script.script_path) as f:
                sql = f.read()
            await conn.execute(sql)
        else:
            # Python generator script
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                script.name,
                script.script_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Call generator function
            await module.generate_data(conn)
```

### 2.2 Seed Data SQL Scripts

**Minimal Seed - Languages:**
```sql
-- fixtures/databases/seed_languages.sql
-- Seed programming languages

INSERT INTO languages (language_id, name, pod, paradigm, version) VALUES
    ('python', 'Python', 'pod_a', 'dynamic', '3.11'),
    ('javascript', 'JavaScript', 'pod_a', 'dynamic', 'ES2023'),
    ('ruby', 'Ruby', 'pod_a', 'dynamic', '3.2'),
    ('php', 'PHP', 'pod_a', 'dynamic', '8.2'),
    ('c', 'C', 'pod_b', 'systems', 'C17'),
    ('cpp', 'C++', 'pod_b', 'systems', 'C++20'),
    ('rust', 'Rust', 'pod_b', 'systems', '1.75'),
    ('zig', 'Zig', 'pod_b', 'systems', '0.11'),
    ('java', 'Java', 'pod_c', 'enterprise', '21'),
    ('csharp', 'C#', 'pod_c', 'enterprise', '12'),
    ('scala', 'Scala', 'pod_c', 'enterprise', '3.3'),
    ('kotlin', 'Kotlin', 'pod_c', 'enterprise', '1.9'),
    ('matlab', 'MATLAB', 'pod_d', 'mathematical', 'R2024a'),
    ('r', 'R', 'pod_d', 'mathematical', '4.3');

-- Create indexes
CREATE INDEX idx_languages_pod ON languages(pod);
```

**Standard Seed - LogicNodes:**
```sql
-- fixtures/databases/seed_logicnodes_standard.sql
-- Seed standard test LogicNodes

-- List filter operation (Python)
INSERT INTO logicnodes (
    logicnode_id, concept_name, source_language,
    inputs, outputs, preconditions, postconditions,
    side_effects, complexity, confidence, agent_id
) VALUES (
    'TEST-LN-001',
    'list_filter',
    'python',
    '[{"name": "items", "type": "List[T]"}, {"name": "predicate", "type": "Callable[[T], bool]"}]'::jsonb,
    '[{"name": "result", "type": "List[T]"}]'::jsonb,
    '["items is not None", "predicate is not None"]'::jsonb,
    '["all(predicate(item) for item in result)", "all(item in items for item in result)"]'::jsonb,
    '[]'::jsonb,
    'O(n)',
    0.98,
    'AGENT-PY-001'
);

-- Array map operation (JavaScript)
INSERT INTO logicnodes (
    logicnode_id, concept_name, source_language,
    inputs, outputs, preconditions, postconditions,
    side_effects, complexity, confidence, agent_id
) VALUES (
    'TEST-LN-002',
    'array_map',
    'javascript',
    '[{"name": "array", "type": "Array<T>"}, {"name": "transform", "type": "(T) => U"}]'::jsonb,
    '[{"name": "result", "type": "Array<U>"}]'::jsonb,
    '["array != null", "transform != null"]'::jsonb,
    '["result.length === array.length"]'::jsonb,
    '[]'::jsonb,
    'O(n)',
    0.95,
    'AGENT-JS-001'
);

-- Add 50+ more standard test cases...
```

---

## 3. TEST FIXTURES & FACTORIES

### 3.1 Pytest Fixtures

**Reusable Test Fixtures:**
```python
"""
Pytest fixtures for test data
"""

import pytest
import asyncpg
from pathlib import Path
from typing import Dict, Any, List

@pytest.fixture(scope="session")
async def test_database():
    """
    Create test database for session
    """
    # Create test database
    conn = await asyncpg.connect('postgresql://localhost/postgres')
    await conn.execute('DROP DATABASE IF EXISTS holy_grail_test')
    await conn.execute('CREATE DATABASE holy_grail_test')
    await conn.close()
    
    # Connect to test database
    test_conn = await asyncpg.connect('postgresql://localhost/holy_grail_test')
    
    # Run migrations
    await run_migrations(test_conn)
    
    yield test_conn
    
    # Cleanup
    await test_conn.close()

@pytest.fixture(scope="function")
async def seeded_database(test_database):
    """
    Fresh seeded database for each test
    """
    # Seed with minimal data
    seeder = DatabaseSeeder(test_database)
    await seeder.seed_database(SeedLevel.MINIMAL, clean=True)
    
    yield test_database
    
    # Cleanup after test
    await seeder._clean_database(test_database)

@pytest.fixture
def sample_code_python() -> Dict[str, str]:
    """
    Sample Python code for testing
    """
    return {
        'simple_function': '''
def add(a, b):
    return a + b
''',
        'list_comprehension': '''
def filter_positive(numbers):
    return [n for n in numbers if n > 0]
''',
        'class_definition': '''
class Calculator:
    def __init__(self):
        self.result = 0
    
    def add(self, value):
        self.result += value
        return self.result
''',
        'async_function': '''
async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
'''
    }

@pytest.fixture
def sample_logicnodes() -> List[Dict[str, Any]]:
    """
    Sample LogicNodes for testing
    """
    return [
        {
            'logicnode_id': 'FIXTURE-LN-001',
            'concept_name': 'list_filter',
            'source_language': 'python',
            'inputs': [
                {'name': 'items', 'type': 'List[T]'},
                {'name': 'predicate', 'type': 'Callable[[T], bool]'}
            ],
            'outputs': [{'name': 'result', 'type': 'List[T]'}],
            'preconditions': ['items is not None'],
            'postconditions': ['all(predicate(item) for item in result)'],
            'side_effects': [],
            'complexity': 'O(n)',
            'confidence': 0.98
        },
        # More fixtures...
    ]

@pytest.fixture
def code_corpus(tmp_path: Path) -> Path:
    """
    Generate code corpus in temporary directory
    """
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    
    # Generate test files
    generator = CodeCorpusGenerator(corpus_dir)
    generator.generate_corpus(num_files=100)
    
    return corpus_dir
```

### 3.2 Factory Pattern for Test Data

**Test Data Factories:**
```python
"""
Factory classes for generating test data
"""

from dataclasses import dataclass
import random
from typing import Optional, List

class LogicNodeFactory:
    """
    Factory for creating test LogicNodes
    """
    
    def __init__(self, seed: int = 42):
        """Initialize with seed for reproducibility"""
        random.seed(seed)
        self.counter = 0
    
    def create_logicnode(
        self,
        concept_name: Optional[str] = None,
        language: str = "python",
        complexity: str = "O(n)",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a test LogicNode
        """
        self.counter += 1
        
        return {
            'logicnode_id': f'FACTORY-LN-{self.counter:04d}',
            'concept_name': concept_name or f'test_concept_{self.counter}',
            'source_language': language,
            'inputs': kwargs.get('inputs', [
                {'name': 'input', 'type': 'Any'}
            ]),
            'outputs': kwargs.get('outputs', [
                {'name': 'output', 'type': 'Any'}
            ]),
            'preconditions': kwargs.get('preconditions', []),
            'postconditions': kwargs.get('postconditions', []),
            'side_effects': kwargs.get('side_effects', []),
            'complexity': complexity,
            'confidence': kwargs.get('confidence', 0.95),
            'agent_id': kwargs.get('agent_id', f'AGENT-{language.upper()}-001')
        }
    
    def create_batch(
        self,
        count: int,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Create batch of LogicNodes
        """
        return [self.create_logicnode(**kwargs) for _ in range(count)]
    
    def create_perfect_logicnode(self) -> Dict[str, Any]:
        """
        Create a perfect LogicNode (should pass all audits)
        """
        return self.create_logicnode(
            concept_name='perfect_example',
            inputs=[
                {'name': 'items', 'type': 'List[int]'},
                {'name': 'threshold', 'type': 'int'}
            ],
            outputs=[{'name': 'result', 'type': 'List[int]'}],
            preconditions=[
                'items is not None',
                'threshold is not None'
            ],
            postconditions=[
                'all(item > threshold for item in result)',
                'all(item in items for item in result)'
            ],
            side_effects=[],
            complexity='O(n)',
            confidence=0.99
        )
    
    def create_incorrect_logicnode(self) -> Dict[str, Any]:
        """
        Create an incorrect LogicNode (should fail correctness audit)
        """
        return self.create_logicnode(
            concept_name='incorrect_example',
            inputs=[{'name': 'x', 'type': 'int'}],
            outputs=[{'name': 'result', 'type': 'int'}],
            preconditions=['x > 0'],
            postconditions=[
                'result > x',   # Claims result is greater
                'result < x'    # But also claims it's less (CONTRADICTION)
            ],
            confidence=0.50
        )

class CodeSampleFactory:
    """
    Factory for generating code samples
    """
    
    def __init__(self, seed: int = 42):
        random.seed(seed)
    
    def create_python_function(
        self,
        name: str = "test_function",
        num_params: int = 2,
        complexity: str = "simple"
    ) -> str:
        """
        Generate Python function code
        """
        params = [f"param{i}" for i in range(num_params)]
        
        if complexity == "simple":
            body = f"    return {' + '.join(params)}"
        elif complexity == "medium":
            body = f"""    result = 0
    for p in [{', '.join(params)}]:
        result += p
    return result"""
        else:  # complex
            body = f"""    def helper(x):
        return x * 2
    
    result = sum(helper(p) for p in [{', '.join(params)}])
    return result"""
        
        return f"""def {name}({', '.join(params)}):
{body}
"""
    
    def create_class(
        self,
        name: str = "TestClass",
        num_methods: int = 3
    ) -> str:
        """
        Generate Python class code
        """
        methods = []
        for i in range(num_methods):
            methods.append(f"""    def method_{i}(self, x):
        return x * {i + 1}""")
        
        return f"""class {name}:
    def __init__(self):
        self.value = 0

{chr(10).join(methods)}
"""

# Usage in tests:
def test_with_factory():
    factory = LogicNodeFactory(seed=42)
    
    # Create test data
    perfect = factory.create_perfect_logicnode()
    incorrect = factory.create_incorrect_logicnode()
    batch = factory.create_batch(10, language='javascript')
    
    # Use in tests...
```

---

## 4. CODE CORPUS GENERATION

### 4.1 Multi-Language Code Generator

**Generate Realistic Code Samples:**
```python
"""
Code corpus generation for testing
"""

from pathlib import Path
from typing import Dict, List
import random

class CodeCorpusGenerator:
    """
    Generate realistic code corpus for testing
    """
    
    def __init__(self, output_dir: Path, seed: int = 42):
        self.output_dir = output_dir
        random.seed(seed)
        self.templates = self._load_templates()
    
    def generate_corpus(
        self,
        num_files: int = 1000,
        languages: Optional[List[str]] = None
    ) -> List[Path]:
        """
        Generate complete test corpus
        
        Args:
            num_files: Number of files to generate
            languages: Languages to include (default: all)
        
        Returns:
            List of generated file paths
        """
        if languages is None:
            languages = ['python', 'javascript', 'rust', 'java']
        
        files = []
        
        for i in range(num_files):
            language = random.choice(languages)
            complexity = random.choice(['simple', 'medium', 'complex'])
            
            file_path = self._generate_file(
                file_id=i,
                language=language,
                complexity=complexity
            )
            
            files.append(file_path)
        
        return files
    
    def _generate_file(
        self,
        file_id: int,
        language: str,
        complexity: str
    ) -> Path:
        """
        Generate single code file
        """
        if language == 'python':
            code = self._generate_python_file(complexity)
            ext = 'py'
        elif language == 'javascript':
            code = self._generate_javascript_file(complexity)
            ext = 'js'
        elif language == 'rust':
            code = self._generate_rust_file(complexity)
            ext = 'rs'
        elif language == 'java':
            code = self._generate_java_file(complexity)
            ext = 'java'
        else:
            raise ValueError(f"Unsupported language: {language}")
        
        # Write file
        file_path = self.output_dir / f"{language}_{complexity}_{file_id:04d}.{ext}"
        file_path.write_text(code)
        
        return file_path
    
    def _generate_python_file(self, complexity: str) -> str:
        """Generate Python code"""
        if complexity == 'simple':
            return '''
def calculate_sum(numbers):
    """Calculate sum of numbers"""
    return sum(numbers)

def filter_positive(numbers):
    """Filter positive numbers"""
    return [n for n in numbers if n > 0]

def main():
    data = [1, -2, 3, -4, 5]
    positive = filter_positive(data)
    total = calculate_sum(positive)
    print(f"Sum of positive numbers: {total}")

if __name__ == "__main__":
    main()
'''
        
        elif complexity == 'medium':
            return '''
class DataProcessor:
    """Process and analyze data"""
    
    def __init__(self, data):
        self.data = data
        self.results = []
    
    def filter_data(self, predicate):
        """Filter data by predicate"""
        filtered = [item for item in self.data if predicate(item)]
        return filtered
    
    def transform_data(self, func):
        """Transform data using function"""
        transformed = [func(item) for item in self.data]
        return transformed
    
    def aggregate(self):
        """Calculate aggregates"""
        return {
            'count': len(self.data),
            'sum': sum(self.data),
            'mean': sum(self.data) / len(self.data) if self.data else 0
        }

def main():
    processor = DataProcessor([1, 2, 3, 4, 5])
    positive = processor.filter_data(lambda x: x > 0)
    doubled = processor.transform_data(lambda x: x * 2)
    stats = processor.aggregate()
    print(f"Stats: {stats}")

if __name__ == "__main__":
    main()
'''
        
        else:  # complex
            return '''
from typing import List, Callable, Optional, TypeVar
from dataclasses import dataclass
import asyncio

T = TypeVar('T')
U = TypeVar('U')

@dataclass
class ProcessingResult:
    """Result of data processing"""
    data: List[T]
    errors: List[str]
    metadata: dict

class AsyncDataPipeline:
    """Async data processing pipeline"""
    
    def __init__(self):
        self.stages = []
        self.error_handlers = []
    
    def add_stage(self, func: Callable[[T], U]) -> 'AsyncDataPipeline':
        """Add processing stage"""
        self.stages.append(func)
        return self
    
    def add_error_handler(self, handler: Callable[[Exception], None]) -> 'AsyncDataPipeline':
        """Add error handler"""
        self.error_handlers.append(handler)
        return self
    
    async def process(self, data: List[T]) -> ProcessingResult:
        """Process data through pipeline"""
        results = []
        errors = []
        
        for item in data:
            try:
                result = item
                for stage in self.stages:
                    if asyncio.iscoroutinefunction(stage):
                        result = await stage(result)
                    else:
                        result = stage(result)
                results.append(result)
            except Exception as e:
                errors.append(str(e))
                for handler in self.error_handlers:
                    handler(e)
        
        return ProcessingResult(
            data=results,
            errors=errors,
            metadata={'processed': len(results), 'failed': len(errors)}
        )

async def main():
    pipeline = AsyncDataPipeline()
    pipeline.add_stage(lambda x: x * 2)
    pipeline.add_stage(lambda x: x + 10)
    pipeline.add_error_handler(lambda e: print(f"Error: {e}"))
    
    data = [1, 2, 3, 4, 5]
    result = await pipeline.process(data)
    print(f"Results: {result.data}")
    print(f"Metadata: {result.metadata}")

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    def _generate_javascript_file(self, complexity: str) -> str:
        """Generate JavaScript code"""
        # Similar structure for JavaScript
        pass
    
    def _generate_rust_file(self, complexity: str) -> str:
        """Generate Rust code"""
        # Similar structure for Rust
        pass
```

---

## 5. LOGICNODE TEST DATA

### 5.1 Curated LogicNode Test Sets

**Known Good/Bad LogicNodes:**
```json
// fixtures/logicnodes/perfect_examples.json
[
  {
    "logicnode_id": "PERFECT-001",
    "concept_name": "list_filter",
    "description": "Perfect example of list filtering",
    "source_language": "python",
    "inputs": [
      {"name": "items", "type": "List[T]"},
      {"name": "predicate", "type": "Callable[[T], bool]"}
    ],
    "outputs": [
      {"name": "result", "type": "List[T]"}
    ],
    "preconditions": [
      "items is not None",
      "predicate is not None"
    ],
    "postconditions": [
      "all(predicate(item) for item in result)",
      "all(item in items for item in result)",
      "len(result) <= len(items)"
    ],
    "side_effects": [],
    "complexity": "O(n)",
    "confidence": 0.99,
    "test_metadata": {
      "category": "list_operations",
      "difficulty": "easy",
      "expected_audit_result": "pass_all"
    }
  }
]
```

```json
// fixtures/logicnodes/known_errors.json
[
  {
    "logicnode_id": "ERROR-001",
    "concept_name": "division_unsafe",
    "description": "Missing division-by-zero check",
    "source_language": "python",
    "inputs": [
      {"name": "numerator", "type": "float"},
      {"name": "denominator", "type": "float"}
    ],
    "outputs": [
      {"name": "result", "type": "float"}
    ],
    "preconditions": [],
    "postconditions": [
      "result == numerator / denominator"
    ],
    "side_effects": [],
    "complexity": "O(1)",
    "confidence": 0.60,
    "test_metadata": {
      "category": "arithmetic_operations",
      "difficulty": "easy",
      "expected_audit_result": "fail_correctness",
      "expected_issues": ["missing_precondition_division_by_zero"]
    }
  }
]
```

---

## 6. MULTI-LANGUAGE TEST DATA

### 6.1 Cross-Language Concept Mappings

**Test Semantic Equivalence:**
```python
"""
Cross-language test data for semantic equivalence testing
"""

class CrossLanguageTestData:
    """
    Test data for cross-language semantic mappings
    """
    
    @staticmethod
    def get_list_filter_examples() -> Dict[str, str]:
        """
        List filter implementation in multiple languages
        All should produce equivalent LogicNodes
        """
        return {
            'python': '''
def filter_list(items, predicate):
    return [item for item in items if predicate(item)]
''',
            'javascript': '''
function filterList(items, predicate) {
    return items.filter(predicate);
}
''',
            'rust': '''
fn filter_list<T, F>(items: Vec<T>, predicate: F) -> Vec<T>
where
    F: Fn(&T) -> bool,
{
    items.into_iter().filter(predicate).collect()
}
''',
            'java': '''
public static <T> List<T> filterList(List<T> items, Predicate<T> predicate) {
    return items.stream()
        .filter(predicate)
        .collect(Collectors.toList());
}
'''
        }
    
    @staticmethod
    def get_map_examples() -> Dict[str, str]:
        """
        Map/transform implementation in multiple languages
        """
        return {
            'python': '''
def map_list(items, transform):
    return [transform(item) for item in items]
''',
            'javascript': '''
function mapList(items, transform) {
    return items.map(transform);
}
''',
            'rust': '''
fn map_list<T, U, F>(items: Vec<T>, transform: F) -> Vec<U>
where
    F: Fn(T) -> U,
{
    items.into_iter().map(transform).collect()
}
''',
            'java': '''
public static <T, U> List<U> mapList(List<T> items, Function<T, U> transform) {
    return items.stream()
        .map(transform)
        .collect(Collectors.toList());
}
'''
        }
```

---

## 7. TEST DATA VERSIONING

### 7.1 Version Control Strategy

**Git LFS for Large Files:**
```bash
# .gitattributes
# Track large test data with Git LFS

tests/fixtures/corpus/*.bin filter=lfs diff=lfs merge=lfs -text
tests/fixtures/performance/*.dat filter=lfs diff=lfs merge=lfs -text
tests/data/benchmarks/*.db filter=lfs diff=lfs merge=lfs -text

# Keep small fixtures in git
tests/fixtures/**/*.json text
tests/fixtures/**/*.sql text
tests/fixtures/**/*.py text
tests/fixtures/**/*.js text
```

### 7.2 Test Data Changelog

**Track Changes to Test Data:**
```markdown
# Test Data Changelog

## Version 1.2.0 (2026-02-06)
### Added
- 50 new LogicNode test cases for async patterns
- Rust test corpus (1000 files)
- Performance benchmark dataset (10GB)

### Changed
- Updated Python test fixtures to Python 3.11 syntax
- Improved edge case coverage for list operations

### Removed
- Deprecated Python 2.7 test cases

## Version 1.1.0 (2026-01-15)
### Added
- Security vulnerability test cases (CVE database)
- Cross-language semantic equivalence tests
```

---

## 8. TEST ENVIRONMENT MANAGEMENT

### 8.1 Docker Test Environment

**Isolated Test Containers:**
```yaml
# docker-compose.test.yml
version: '3.8'

services:
  test-database:
    image: postgres:15
    environment:
      POSTGRES_DB: holy_grail_test
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
    volumes:
      - test-db-data:/var/lib/postgresql/data
      - ./tests/fixtures/databases:/docker-entrypoint-initdb.d
    ports:
      - "5433:5432"  # Different port to avoid conflicts
  
  test-redis:
    image: redis:7
    ports:
      - "6380:6379"
  
  test-milvus:
    image: milvusdb/milvus:latest
    environment:
      ETCD_ENDPOINTS: test-etcd:2379
    ports:
      - "19531:19530"

volumes:
  test-db-data:
```

### 8.2 Test Environment Configuration

**Environment-Specific Settings:**
```python
# tests/conftest.py
"""
Pytest configuration and shared fixtures
"""

import os
import pytest

def pytest_configure(config):
    """
    Configure test environment
    """
    # Set test environment variables
    os.environ['ENVIRONMENT'] = 'test'
    os.environ['DATABASE_URL'] = 'postgresql://test_user:test_password@localhost:5433/holy_grail_test'
    os.environ['REDIS_URL'] = 'redis://localhost:6380'
    os.environ['LOG_LEVEL'] = 'DEBUG'
    
    # Disable external API calls
    os.environ['MOCK_EXTERNAL_APIS'] = 'true'

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Setup test environment before all tests
    """
    # Start Docker test services
    os.system('docker-compose -f docker-compose.test.yml up -d')
    
    # Wait for services to be ready
    import time
    time.sleep(5)
    
    yield
    
    # Cleanup
    os.system('docker-compose -f docker-compose.test.yml down -v')
```

---

## 9. DATA CLEANUP & ISOLATION

### 9.1 Test Isolation Strategies

**Ensure Test Independence:**
```python
"""
Test isolation and cleanup
"""

import pytest
import asyncpg

class TestIsolation:
    """
    Patterns for test isolation
    """
    
    @pytest.fixture(autouse=True)
    async def isolate_test(self, test_database):
        """
        Wrap each test in a transaction that's rolled back
        
        Strategy 1: Transaction Rollback
        """
        # Start transaction
        async with test_database.transaction():
            yield
            # Automatic rollback at end of test
    
    @pytest.fixture
    async def clean_tables(self, test_database):
        """
        Strategy 2: Truncate Tables
        """
        # Before test
        await test_database.execute('TRUNCATE TABLE logicnodes CASCADE')
        
        yield
        
        # After test
        await test_database.execute('TRUNCATE TABLE logicnodes CASCADE')
    
    @pytest.fixture
    async def dedicated_schema(self, test_database):
        """
        Strategy 3: Per-Test Schema
        """
        # Create unique schema for this test
        schema_name = f"test_{id(self)}"
        await test_database.execute(f'CREATE SCHEMA {schema_name}')
        await test_database.execute(f'SET search_path TO {schema_name}')
        
        # Copy tables to schema
        # ... (copy table definitions)
        
        yield
        
        # Cleanup
        await test_database.execute(f'DROP SCHEMA {schema_name} CASCADE')
```

### 9.2 Cleanup Verification

**Verify Clean State:**
```python
"""
Verify test cleanup
"""

@pytest.fixture(autouse=True)
async def verify_cleanup(test_database):
    """
    Verify database is clean after each test
    """
    yield
    
    # After test, check for leftover data
    row_counts = await test_database.fetch("""
        SELECT table_name, 
               (SELECT COUNT(*) FROM information_schema.tables t2 
                WHERE t2.table_name = t.table_name) as count
        FROM information_schema.tables t
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
    """)
    
    for row in row_counts:
        count = await test_database.fetchval(
            f"SELECT COUNT(*) FROM {row['table_name']}"
        )
        
        if count > 0:
            pytest.fail(
                f"Table {row['table_name']} has {count} rows after test. "
                "Test did not clean up properly."
            )
```

---

## 10. PRODUCTION DATA SANITIZATION

### 10.1 Sanitization Rules

**Never Use Production Data:**
```python
"""
Production data sanitization (if absolutely necessary)
"""

class DataSanitizer:
    """
    Sanitize production data for test use
    
    NOTE: Prefer synthetic data generation over sanitization
    """
    
    @staticmethod
    def sanitize_logicnode(logicnode: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize a LogicNode from production
        """
        sanitized = logicnode.copy()
        
        # Remove identifying information
        sanitized['logicnode_id'] = f"SANITIZED-{hash(logicnode['logicnode_id']) % 10000:04d}"
        
        # Remove agent identifiers
        sanitized['agent_id'] = 'SANITIZED-AGENT'
        
        # Remove timestamps
        sanitized.pop('created_at', None)
        sanitized.pop('updated_at', None)
        
        # Remove user data
        sanitized.pop('user_id', None)
        sanitized.pop('project_id', None)
        
        return sanitized
    
    @staticmethod
    def anonymize_code(code: str) -> str:
        """
        Anonymize code samples
        """
        # Replace variable names
        # Replace string literals
        # Remove comments with personal info
        # ... (anonymization logic)
        
        return anonymized_code
```

### 10.2 Compliance Considerations

**Data Privacy Requirements:**
```markdown
# Test Data Privacy Policy

## Rules
1. **Never use real user data** in test environments
2. **Generate synthetic data** that mimics production patterns
3. **Sanitize thoroughly** if production data must be used
4. **Audit test data** regularly for sensitive information
5. **Encrypt test data** at rest and in transit

## Prohibited Data
- Real user names, emails, phone numbers
- Production API keys or credentials
- Actual source code from private repositories
- Customer data of any kind
- Personal identifiable information (PII)

## Compliance
- GDPR Article 5 (data minimization)
- CCPA requirements
- Internal security policies
```

---

## DOCUMENT METADATA

**Document ID:** 48  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Owner:** QA Engineering Team  
**Dependencies:** Documents 23 (Testing Framework), 41-43 (Testing Standards)  
**Next Document:** 49 (Regression Testing Strategy)

---

*End of Test Data Management & Seeding*
