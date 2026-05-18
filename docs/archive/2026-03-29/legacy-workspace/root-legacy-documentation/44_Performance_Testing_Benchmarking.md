# DOCUMENT 44: PERFORMANCE TESTING & BENCHMARKING

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Quality & Testing

**Document ID:** 44  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive performance testing and benchmarking specifications** for the Holy Grail Refinery system. Performance testing validates that the 35-agent system meets latency, throughput, and resource utilization targets under various workloads.

**Performance Testing Goals:**
- 📊 **Baseline Metrics:** Establish performance baselines for all components
- ⚡ **Response Time:** Validate sub-second response for interactive operations
- 🔄 **Throughput:** Measure code processing capacity (LOC/hour)
- 💾 **Resource Usage:** Track CPU, memory, disk, network utilization
- 🎯 **Bottleneck Identification:** Pinpoint performance constraints

**Testing Philosophy:**
- **Repeatable:** Tests produce consistent results across runs
- **Representative:** Test scenarios mirror real-world usage patterns
- **Measurable:** All metrics quantified with statistical confidence
- **Actionable:** Results guide optimization efforts

**Key Performance Targets:**

| Component | Metric | Target | Max Acceptable |
|-----------|--------|--------|----------------|
| **Code Extraction** | Latency | < 500ms per 1K LOC | < 1s |
| **LogicNode Generation** | Throughput | 50K LOC/hour | 30K LOC/hour |
| **Semantic Bus** | Message Latency | < 50ms p99 | < 100ms |
| **Database Queries** | Response Time | < 100ms p95 | < 200ms |
| **API Endpoints** | Response Time | < 200ms p95 | < 500ms |
| **Memory per Agent** | Peak Usage | < 2GB | < 4GB |
| **Full System** | Startup Time | < 60s | < 120s |

---

## TABLE OF CONTENTS

1. [Performance Testing Architecture](#1-performance-testing-architecture)
2. [Benchmark Suite Overview](#2-benchmark-suite-overview)
3. [Latency Testing](#3-latency-testing)
4. [Throughput Testing](#4-throughput-testing)
5. [Resource Utilization Testing](#5-resource-utilization-testing)
6. [Scalability Testing](#6-scalability-testing)
7. [Baseline Establishment](#7-baseline-establishment)
8. [Performance Regression Detection](#8-performance-regression-detection)
9. [Profiling & Optimization](#9-profiling--optimization)
10. [Reporting & Analysis](#10-reporting--analysis)

---

## 1. PERFORMANCE TESTING ARCHITECTURE

### 1.1 Testing Infrastructure

**Hardware Configuration (Baseline):**
```yaml
test_environment:
  hardware:
    model: "AW1 Workstation"
    cpu: "Intel i7-14700F (20 cores)"
    gpu: "NVIDIA RTX 4060 Ti (16GB)"
    ram: "32GB DDR5"
    storage: "1TB NVMe SSD"
  
  docker:
    version: "24.0+"
    network: "bridge mode"
    isolation: "full container isolation"
  
  monitoring:
    metrics: "Prometheus + Grafana"
    profiling: "py-spy, cProfile, perf"
    tracing: "Jaeger"
```

### 1.2 Test Environment Isolation

**Dedicated Test System:**
```python
"""
Performance test environment configuration
"""

import docker
import psutil
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class TestEnvironment:
    """
    Isolated performance testing environment
    """
    name: str = "perf-test"
    cpu_quota: int = 1600000  # 16 cores (80% of 20)
    memory_limit: str = "24g"  # 24GB (75% of 32)
    network: str = "perf-test-net"
    
    def setup(self) -> None:
        """
        Create isolated test environment
        """
        client = docker.from_env()
        
        # Create dedicated network
        try:
            client.networks.create(
                self.network,
                driver="bridge",
                check_duplicate=True
            )
        except docker.errors.APIError:
            pass  # Network already exists
        
        # Clear system caches
        self._clear_caches()
    
    def _clear_caches(self) -> None:
        """
        Clear OS caches for consistent testing
        """
        # Linux: echo 3 > /proc/sys/vm/drop_caches
        # Note: Requires sudo privileges
        pass
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get baseline system metrics
        """
        return {
            'cpu_count': psutil.cpu_count(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'disk_io': psutil.disk_io_counters()
        }
```

---

## 2. BENCHMARK SUITE OVERVIEW

### 2.1 Benchmark Categories

```python
"""
Performance benchmark suite
"""

from enum import Enum
from typing import List, Callable

class BenchmarkCategory(Enum):
    """Benchmark categories"""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    RESOURCE = "resource_utilization"
    SCALABILITY = "scalability"
    ENDURANCE = "endurance"

class PerformanceBenchmark:
    """
    Base class for performance benchmarks
    """
    
    def __init__(
        self,
        name: str,
        category: BenchmarkCategory,
        iterations: int = 100
    ):
        self.name = name
        self.category = category
        self.iterations = iterations
        self.results = []
    
    def setup(self) -> None:
        """Pre-benchmark setup"""
        pass
    
    def run(self) -> None:
        """Execute benchmark"""
        raise NotImplementedError
    
    def teardown(self) -> None:
        """Post-benchmark cleanup"""
        pass
    
    def analyze(self) -> Dict[str, float]:
        """
        Analyze results and return statistics
        """
        import numpy as np
        
        data = np.array(self.results)
        return {
            'mean': np.mean(data),
            'median': np.median(data),
            'p95': np.percentile(data, 95),
            'p99': np.percentile(data, 99),
            'std': np.std(data),
            'min': np.min(data),
            'max': np.max(data)
        }
```

### 2.2 Standard Benchmark Suite

| Benchmark ID | Name | Category | Target Metric |
|--------------|------|----------|---------------|
| **B001** | Code Extraction Latency | Latency | < 500ms/1K LOC |
| **B002** | LogicNode Generation Throughput | Throughput | 50K LOC/hour |
| **B003** | Semantic Bus Message Latency | Latency | < 50ms p99 |
| **B004** | Database Query Performance | Latency | < 100ms p95 |
| **B005** | API Endpoint Response Time | Latency | < 200ms p95 |
| **B006** | Memory Usage per Agent | Resource | < 2GB peak |
| **B007** | CPU Utilization | Resource | < 80% avg |
| **B008** | Disk I/O Throughput | Resource | > 500 MB/s |
| **B009** | Concurrent Agent Scaling | Scalability | Linear to 35 |
| **B010** | 24-Hour Endurance Test | Endurance | Stable metrics |

---

## 3. LATENCY TESTING

### 3.1 Code Extraction Latency (B001)

**Objective:** Measure time to extract semantic information from source code

**Test Implementation:**
```python
"""
Code extraction latency benchmark
"""

import time
from pathlib import Path
from typing import Dict, Any

class CodeExtractionLatencyBenchmark(PerformanceBenchmark):
    """
    Benchmark code extraction performance
    """
    
    def __init__(self):
        super().__init__(
            name="Code Extraction Latency",
            category=BenchmarkCategory.LATENCY,
            iterations=50
        )
        self.test_files = self._prepare_test_files()
    
    def _prepare_test_files(self) -> List[Path]:
        """
        Prepare test files of varying sizes
        """
        return [
            Path("test_data/small_100loc.py"),
            Path("test_data/medium_1k_loc.py"),
            Path("test_data/large_10k_loc.py"),
            Path("test_data/complex_5k_loc.py")
        ]
    
    def run(self) -> None:
        """
        Execute extraction benchmark
        """
        from agents.language.python_agent import PythonExtractionAgent
        
        agent = PythonExtractionAgent(agent_id="AGENT-PY-001-test")
        
        for test_file in self.test_files:
            code = test_file.read_text()
            loc = len(code.splitlines())
            
            start_time = time.perf_counter()
            result = agent.extract_semantics(code)
            end_time = time.perf_counter()
            
            latency_ms = (end_time - start_time) * 1000
            latency_per_1k_loc = (latency_ms / loc) * 1000
            
            self.results.append({
                'file': test_file.name,
                'loc': loc,
                'latency_ms': latency_ms,
                'latency_per_1k_loc': latency_per_1k_loc
            })
    
    def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate against targets
        """
        avg_latency_per_1k = sum(
            r['latency_per_1k_loc'] for r in self.results
        ) / len(self.results)
        
        target = 500  # ms per 1K LOC
        max_acceptable = 1000
        
        return {
            'average_latency_per_1k_loc': avg_latency_per_1k,
            'target': target,
            'max_acceptable': max_acceptable,
            'passed': avg_latency_per_1k <= max_acceptable,
            'meets_target': avg_latency_per_1k <= target
        }
```

**Test Scenarios:**
1. **Small Files** (100-500 LOC): Simple functions, basic control flow
2. **Medium Files** (1K-5K LOC): Classes with methods, moderate complexity
3. **Large Files** (10K+ LOC): Complete modules, high complexity
4. **Complex Files** (5K LOC): High cyclomatic complexity, nested structures

### 3.2 Semantic Bus Message Latency (B003)

**Objective:** Measure end-to-end message latency through Redis Semantic Bus

**Test Implementation:**
```python
"""
Semantic Bus latency benchmark
"""

import asyncio
import time
import uuid
from typing import List

class SemanticBusLatencyBenchmark(PerformanceBenchmark):
    """
    Benchmark Semantic Bus message latency
    """
    
    def __init__(self):
        super().__init__(
            name="Semantic Bus Latency",
            category=BenchmarkCategory.LATENCY,
            iterations=1000
        )
    
    async def run_async(self) -> None:
        """
        Execute async latency test
        """
        from infrastructure.semantic_bus import SemanticBus
        
        bus = SemanticBus()
        channel = f"test-{uuid.uuid4()}"
        
        # Setup receiver
        received_times = []
        
        async def receiver():
            async for message in bus.subscribe(channel):
                receive_time = time.perf_counter()
                send_time = message['timestamp']
                latency_ms = (receive_time - send_time) * 1000
                received_times.append(latency_ms)
                
                if len(received_times) >= self.iterations:
                    break
        
        # Start receiver task
        receiver_task = asyncio.create_task(receiver())
        
        # Wait for receiver to be ready
        await asyncio.sleep(0.1)
        
        # Send messages
        for i in range(self.iterations):
            message = {
                'id': i,
                'timestamp': time.perf_counter(),
                'data': 'x' * 1024  # 1KB payload
            }
            await bus.publish(channel, message)
            await asyncio.sleep(0.001)  # 1ms between sends
        
        # Wait for receiver to finish
        await receiver_task
        
        self.results = received_times
    
    def run(self) -> None:
        """Sync wrapper"""
        asyncio.run(self.run_async())
    
    def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate against targets
        """
        import numpy as np
        
        results = np.array(self.results)
        p99 = np.percentile(results, 99)
        
        target = 50  # ms
        max_acceptable = 100
        
        return {
            'p50_latency_ms': np.percentile(results, 50),
            'p95_latency_ms': np.percentile(results, 95),
            'p99_latency_ms': p99,
            'target': target,
            'max_acceptable': max_acceptable,
            'passed': p99 <= max_acceptable,
            'meets_target': p99 <= target
        }
```

### 3.3 Database Query Performance (B004)

**Objective:** Measure database query response times

**Test Queries:**
```sql
-- Query 1: LogicNode retrieval by ID (most common)
SELECT * FROM logicnodes WHERE logicnode_id = $1;

-- Query 2: Search by concept
SELECT * FROM logicnodes 
WHERE concept_name = $1 
ORDER BY confidence DESC 
LIMIT 10;

-- Query 3: Complex join (pod + language + agent)
SELECT ln.*, p.pod_name, l.language_name, a.agent_name
FROM logicnodes ln
JOIN pods p ON ln.pod_id = p.pod_id
JOIN languages l ON ln.language_id = l.language_id
JOIN agents a ON ln.agent_id = a.agent_id
WHERE ln.created_at > $1;

-- Query 4: Aggregation
SELECT pod_id, COUNT(*) as node_count, AVG(confidence) as avg_confidence
FROM logicnodes
GROUP BY pod_id;
```

**Benchmark Implementation:**
```python
"""
Database query performance benchmark
"""

import asyncpg
import time
from typing import List, Tuple

class DatabaseQueryBenchmark(PerformanceBenchmark):
    """
    Benchmark database query performance
    """
    
    def __init__(self):
        super().__init__(
            name="Database Query Performance",
            category=BenchmarkCategory.LATENCY,
            iterations=100
        )
        self.queries = self._load_test_queries()
    
    async def run_async(self) -> None:
        """
        Execute database benchmarks
        """
        conn = await asyncpg.connect(
            'postgresql://localhost:5432/logicnode_registry'
        )
        
        for query_name, query_sql, params in self.queries:
            for _ in range(self.iterations):
                start_time = time.perf_counter()
                result = await conn.fetch(query_sql, *params)
                end_time = time.perf_counter()
                
                latency_ms = (end_time - start_time) * 1000
                
                self.results.append({
                    'query': query_name,
                    'latency_ms': latency_ms,
                    'row_count': len(result)
                })
        
        await conn.close()
    
    def run(self) -> None:
        asyncio.run(self.run_async())
```

---

## 4. THROUGHPUT TESTING

### 4.1 LogicNode Generation Throughput (B002)

**Objective:** Measure code processing capacity in LOC per hour

**Test Implementation:**
```python
"""
LogicNode generation throughput benchmark
"""

import time
from pathlib import Path
from typing import Dict, List

class LogicNodeThroughputBenchmark(PerformanceBenchmark):
    """
    Benchmark LogicNode generation throughput
    """
    
    def __init__(self):
        super().__init__(
            name="LogicNode Generation Throughput",
            category=BenchmarkCategory.THROUGHPUT,
            iterations=1
        )
        self.test_corpus = self._prepare_corpus()
    
    def _prepare_corpus(self) -> List[Path]:
        """
        Prepare large code corpus for testing
        
        Target: 10K LOC across multiple files
        """
        return [
            Path(f"test_data/corpus/file_{i:03d}.py")
            for i in range(100)  # 100 files × 100 LOC = 10K LOC
        ]
    
    def run(self) -> None:
        """
        Execute throughput test
        """
        from agents.language.python_agent import PythonExtractionAgent
        
        agent = PythonExtractionAgent(agent_id="AGENT-PY-001-test")
        
        total_loc = 0
        start_time = time.perf_counter()
        
        for file_path in self.test_corpus:
            code = file_path.read_text()
            loc = len(code.splitlines())
            total_loc += loc
            
            # Process file
            result = agent.extract_and_generate_logicnodes(code)
        
        end_time = time.perf_counter()
        duration_hours = (end_time - start_time) / 3600
        
        throughput = total_loc / duration_hours
        
        self.results.append({
            'total_loc': total_loc,
            'duration_seconds': end_time - start_time,
            'duration_hours': duration_hours,
            'throughput_loc_per_hour': throughput
        })
    
    def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate against targets
        """
        result = self.results[0]
        throughput = result['throughput_loc_per_hour']
        
        target = 50000  # LOC/hour
        min_acceptable = 30000
        
        return {
            'throughput_loc_per_hour': throughput,
            'target': target,
            'min_acceptable': min_acceptable,
            'passed': throughput >= min_acceptable,
            'meets_target': throughput >= target
        }
```

### 4.2 Parallel Processing Throughput

**Test Concurrent Agent Processing:**
```python
"""
Parallel processing throughput test
"""

import asyncio
import time
from typing import List

class ParallelProcessingBenchmark(PerformanceBenchmark):
    """
    Test throughput with concurrent agents
    """
    
    async def run_parallel(self, num_agents: int = 4) -> None:
        """
        Run multiple agents in parallel
        """
        from agents.language.python_agent import PythonExtractionAgent
        
        # Create agent instances
        agents = [
            PythonExtractionAgent(agent_id=f"AGENT-PY-{i:03d}-test")
            for i in range(num_agents)
        ]
        
        # Distribute work
        workload = self._prepare_workload(num_agents)
        
        start_time = time.perf_counter()
        
        # Process in parallel
        tasks = [
            agent.process_files(files)
            for agent, files in zip(agents, workload)
        ]
        
        results = await asyncio.gather(*tasks)
        
        end_time = time.perf_counter()
        
        total_loc = sum(r['loc'] for r in results)
        duration_hours = (end_time - start_time) / 3600
        throughput = total_loc / duration_hours
        
        self.results.append({
            'num_agents': num_agents,
            'total_loc': total_loc,
            'duration_seconds': end_time - start_time,
            'throughput_loc_per_hour': throughput
        })
```

---

## 5. RESOURCE UTILIZATION TESTING

### 5.1 Memory Usage per Agent (B006)

**Objective:** Track memory consumption for each agent type

**Implementation:**
```python
"""
Memory usage benchmark
"""

import psutil
import os
import time
from typing import Dict

class MemoryUsageBenchmark(PerformanceBenchmark):
    """
    Monitor agent memory consumption
    """
    
    def __init__(self):
        super().__init__(
            name="Memory Usage per Agent",
            category=BenchmarkCategory.RESOURCE,
            iterations=1
        )
    
    def run(self) -> None:
        """
        Monitor memory during agent lifecycle
        """
        from agents.language.python_agent import PythonExtractionAgent
        
        # Get process for memory tracking
        process = psutil.Process(os.getpid())
        
        # Baseline memory
        baseline_mb = process.memory_info().rss / 1024 / 1024
        
        # Create agent
        agent = PythonExtractionAgent(agent_id="AGENT-PY-001-test")
        
        # Memory after initialization
        init_mb = process.memory_info().rss / 1024 / 1024
        
        # Load large file
        code = Path("test_data/large_10k_loc.py").read_text()
        
        # Memory during processing
        peak_samples = []
        for i in range(10):
            result = agent.extract_semantics(code)
            current_mb = process.memory_info().rss / 1024 / 1024
            peak_samples.append(current_mb)
            time.sleep(0.1)
        
        peak_mb = max(peak_samples)
        
        self.results.append({
            'baseline_mb': baseline_mb,
            'after_init_mb': init_mb,
            'peak_mb': peak_mb,
            'delta_init_mb': init_mb - baseline_mb,
            'delta_peak_mb': peak_mb - baseline_mb
        })
    
    def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate against memory targets
        """
        result = self.results[0]
        peak_mb = result['peak_mb']
        
        target = 2048  # 2GB
        max_acceptable = 4096  # 4GB
        
        return {
            'peak_memory_mb': peak_mb,
            'peak_memory_gb': peak_mb / 1024,
            'target_mb': target,
            'max_acceptable_mb': max_acceptable,
            'passed': peak_mb <= max_acceptable,
            'meets_target': peak_mb <= target
        }
```

### 5.2 CPU Utilization (B007)

**Monitor CPU usage across agents:**
```python
"""
CPU utilization benchmark
"""

import psutil
import time
import multiprocessing
from typing import List

class CPUUtilizationBenchmark(PerformanceBenchmark):
    """
    Monitor CPU utilization patterns
    """
    
    def run(self) -> None:
        """
        Monitor CPU during full system operation
        """
        cpu_count = multiprocessing.cpu_count()
        
        # Start monitoring
        samples = []
        
        def monitor():
            for _ in range(100):
                cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
                samples.append({
                    'timestamp': time.time(),
                    'overall': sum(cpu_percent) / len(cpu_percent),
                    'per_core': cpu_percent
                })
        
        # Run workload while monitoring
        monitor_thread = threading.Thread(target=monitor)
        monitor_thread.start()
        
        # Execute workload
        self._run_workload()
        
        monitor_thread.join()
        self.results = samples
    
    def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate CPU utilization
        """
        avg_utilization = sum(s['overall'] for s in self.results) / len(self.results)
        peak_utilization = max(s['overall'] for s in self.results)
        
        target = 80  # percent
        
        return {
            'average_cpu_percent': avg_utilization,
            'peak_cpu_percent': peak_utilization,
            'target': target,
            'efficient': avg_utilization < target
        }
```

---

## 6. SCALABILITY TESTING

### 6.1 Concurrent Agent Scaling (B009)

**Test Performance with Increasing Agent Count:**
```python
"""
Scalability benchmark
"""

class ScalabilityBenchmark(PerformanceBenchmark):
    """
    Test system scalability with increasing load
    """
    
    def run(self) -> None:
        """
        Test with 1, 5, 10, 20, 35 agents
        """
        agent_counts = [1, 5, 10, 20, 35]
        
        for num_agents in agent_counts:
            start_time = time.perf_counter()
            
            # Deploy N agents
            agents = self._deploy_agents(num_agents)
            
            # Execute standard workload
            throughput = self._execute_workload(agents)
            
            end_time = time.perf_counter()
            
            self.results.append({
                'num_agents': num_agents,
                'throughput': throughput,
                'duration': end_time - start_time,
                'throughput_per_agent': throughput / num_agents
            })
    
    def evaluate(self) -> Dict[str, Any]:
        """
        Check for linear scaling
        """
        # Ideal: throughput increases linearly with agent count
        # Reality: expect 85%+ efficiency
        
        baseline = self.results[0]['throughput']
        
        efficiency_scores = []
        for result in self.results[1:]:
            expected = baseline * result['num_agents']
            actual = result['throughput']
            efficiency = (actual / expected) * 100
            efficiency_scores.append(efficiency)
        
        avg_efficiency = sum(efficiency_scores) / len(efficiency_scores)
        
        return {
            'average_scaling_efficiency': avg_efficiency,
            'target': 85,
            'meets_target': avg_efficiency >= 85
        }
```

---

## 7. BASELINE ESTABLISHMENT

### 7.1 Creating Performance Baselines

**Process:**
1. Run full benchmark suite on clean system
2. Execute 10 iterations for statistical confidence
3. Record median values as baseline
4. Store baselines in version control

**Baseline Storage:**
```yaml
# baselines/v1.0.0.yaml
version: "1.0.0"
date: "2026-02-06"
hardware:
  model: "AW1"
  cpu: "i7-14700F"
  ram: "32GB"

benchmarks:
  code_extraction_latency:
    median_ms_per_1k_loc: 450
    p95_ms_per_1k_loc: 520
    p99_ms_per_1k_loc: 580
  
  logicnode_throughput:
    median_loc_per_hour: 52000
    p95_loc_per_hour: 48000
  
  semantic_bus_latency:
    median_ms: 35
    p95_ms: 45
    p99_ms: 48
  
  database_query:
    simple_query_p95_ms: 85
    complex_join_p95_ms: 180
  
  memory_per_agent:
    median_peak_mb: 1800
    p95_peak_mb: 2100
  
  cpu_utilization:
    average_percent: 72
    peak_percent: 85
```

---

## 8. PERFORMANCE REGRESSION DETECTION

### 8.1 Automated Regression Testing

**CI/CD Integration:**
```python
"""
Performance regression detection in CI
"""

import yaml
from pathlib import Path
from typing import Dict, Any

class PerformanceRegressionDetector:
    """
    Detect performance regressions
    """
    
    def __init__(self, baseline_path: Path):
        with open(baseline_path) as f:
            self.baseline = yaml.safe_load(f)
    
    def check_regression(
        self,
        current_results: Dict[str, Any],
        threshold: float = 0.1  # 10% regression threshold
    ) -> Dict[str, Any]:
        """
        Compare current results against baseline
        
        Returns:
            Dictionary with regression status
        """
        regressions = []
        
        for benchmark_name, metrics in current_results.items():
            baseline_metrics = self.baseline['benchmarks'].get(benchmark_name)
            if not baseline_metrics:
                continue
            
            for metric_name, current_value in metrics.items():
                baseline_value = baseline_metrics.get(metric_name)
                if baseline_value is None:
                    continue
                
                # Calculate regression (higher values are worse for latency)
                delta = current_value - baseline_value
                delta_percent = (delta / baseline_value) * 100
                
                if delta_percent > (threshold * 100):
                    regressions.append({
                        'benchmark': benchmark_name,
                        'metric': metric_name,
                        'baseline': baseline_value,
                        'current': current_value,
                        'delta_percent': delta_percent
                    })
        
        return {
            'passed': len(regressions) == 0,
            'regressions': regressions
        }
```

**GitHub Actions Integration:**
```yaml
# .github/workflows/performance-tests.yml
name: Performance Tests

on:
  pull_request:
    branches: [main, develop]

jobs:
  performance-benchmarks:
    runs-on: [self-hosted, performance]
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Dependencies
        run: |
          pip install -r requirements-test.txt
      
      - name: Run Performance Benchmarks
        run: |
          python -m pytest tests/performance/ \
            --benchmark-only \
            --benchmark-json=benchmark-results.json
      
      - name: Check for Regressions
        run: |
          python scripts/check_regression.py \
            --baseline baselines/v1.0.0.yaml \
            --results benchmark-results.json \
            --threshold 0.10
      
      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: benchmark-results.json
```

---

## 9. PROFILING & OPTIMIZATION

### 9.1 Profiling Tools

**Python Profiling:**
```python
"""
Profiling utilities
"""

import cProfile
import pstats
from functools import wraps
from typing import Callable

def profile_function(func: Callable) -> Callable:
    """
    Decorator to profile function execution
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        
        result = func(*args, **kwargs)
        
        profiler.disable()
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # Top 20 functions
        
        return result
    
    return wrapper

# Usage:
@profile_function
def extract_semantics(code: str):
    # ... function implementation
    pass
```

**py-spy for Production Profiling:**
```bash
# Profile running agent process
py-spy record -o profile.svg --pid <agent_pid>

# Top function report
py-spy top --pid <agent_pid>

# Flame graph
py-spy record -o flamegraph.svg --format speedscope --pid <agent_pid>
```

### 9.2 Bottleneck Identification

**Common Bottlenecks:**
1. **I/O Bound**: File operations, database queries, network calls
2. **CPU Bound**: AST parsing, semantic analysis, LogicNode generation
3. **Memory Bound**: Large data structures, excessive object creation
4. **Synchronization**: Lock contention, message queue delays

**Optimization Strategies:**
```python
"""
Performance optimization patterns
"""

# 1. Caching expensive operations
from functools import lru_cache

@lru_cache(maxsize=1024)
def parse_ast(code: str):
    # Expensive AST parsing
    return ast.parse(code)

# 2. Batch database operations
async def save_logicnodes_batch(nodes: List[LogicNode]):
    # Bulk insert instead of individual inserts
    await db.executemany(
        "INSERT INTO logicnodes (...) VALUES ($1, $2, ...)",
        [(n.id, n.concept, ...) for n in nodes]
    )

# 3. Parallel processing
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor(max_workers=4) as executor:
    results = executor.map(process_file, file_list)

# 4. Async I/O
async def process_files_async(files: List[Path]):
    tasks = [process_file(f) for f in files]
    return await asyncio.gather(*tasks)
```

---

## 10. REPORTING & ANALYSIS

### 10.1 Performance Report Format

**Executive Summary Report:**
```markdown
# Performance Test Report

**Test Date:** 2026-02-06  
**Version:** v1.0.0  
**Environment:** AW1 Workstation

## Summary

- **Overall Status:** ✅ PASS (42/44 benchmarks passed)
- **Regressions:** 2 minor regressions detected
- **Performance vs Baseline:** +5% improvement in throughput

## Key Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Code Extraction Latency | < 500ms/1K LOC | 445ms | ✅ |
| LogicNode Throughput | 50K LOC/hr | 53K LOC/hr | ✅ |
| Semantic Bus Latency p99 | < 50ms | 48ms | ✅ |
| Memory per Agent | < 2GB | 1.85GB | ✅ |
| CPU Utilization | < 80% | 74% | ✅ |

## Detailed Results

### Code Extraction Latency (B001)
- **Mean:** 445ms per 1K LOC
- **P95:** 510ms
- **P99:** 580ms
- **Status:** ✅ Meets target

### Regressions Detected

1. **Database Complex Join Query**
   - Baseline: 180ms (p95)
   - Current: 205ms (p95)
   - Delta: +13.9%
   - Recommendation: Investigate query plan, add index

2. **Parallel Processing Efficiency**
   - Baseline: 88%
   - Current: 83%
   - Delta: -5.7%
   - Recommendation: Check for resource contention
```

### 10.2 Continuous Monitoring Dashboard

**Grafana Dashboard Configuration:**
```yaml
# Performance monitoring dashboard
dashboard:
  title: "Holy Grail Performance Metrics"
  
  panels:
    - title: "Code Extraction Latency"
      type: "graph"
      targets:
        - expr: 'histogram_quantile(0.95, extraction_latency_ms_bucket)'
          legendFormat: "p95"
        - expr: 'histogram_quantile(0.99, extraction_latency_ms_bucket)'
          legendFormat: "p99"
    
    - title: "Throughput (LOC/hour)"
      type: "stat"
      targets:
        - expr: 'rate(logicnodes_generated_total[1h]) * 3600'
    
    - title: "Memory Usage per Agent"
      type: "graph"
      targets:
        - expr: 'container_memory_usage_bytes{container=~"agent-.*"}'
    
    - title: "CPU Utilization"
      type: "gauge"
      targets:
        - expr: 'rate(container_cpu_usage_seconds_total[5m]) * 100'
```

---

## DOCUMENT METADATA

**Document ID:** 44  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Quality & Testing  
**Owner:** Performance Engineering Team  
**Dependencies:** Documents 23 (Testing Framework), 25 (Monitoring)  
**Next Document:** 45 (Load Testing & Stress Testing)

---

*End of Performance Testing & Benchmarking*
