# DOCUMENT 51: DEVELOPER ONBOARDING GUIDE
## Holy Grail Refinery - Documentation & Training

**Document ID:** 51  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Documentation & Training  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides a **comprehensive onboarding guide** for developers joining the Holy Grail Refinery project. It covers everything needed to become productive, from initial setup through advanced development workflows, with a focus on understanding the system's unique architecture and philosophy.

**Onboarding Phases:**
1. **Day 1: Environment Setup** (4 hours) - Get development environment running
2. **Days 2-3: System Understanding** (2 days) - Learn architecture and concepts
3. **Week 1: First Contribution** (3 days) - Submit first pull request
4. **Week 2-4: Domain Mastery** (3 weeks) - Deep dive into assigned pod/agent
5. **Month 2+: Autonomous Development** - Full productivity

**Learning Paths:**
- 🐍 **Agent Developer:** Build and maintain agent implementations
- 🏗️ **Infrastructure Engineer:** Work on Semantic Bus, databases, orchestration
- 🎨 **Frontend Developer:** Mission Control UI development
- 🧪 **QA Engineer:** Testing frameworks and quality assurance
- 📊 **Data Engineer:** Knowledge Lake, LogicNode Registry

**Expected Timeline:**
- ✅ **Day 1:** Development environment functional
- ✅ **Week 1:** First code contribution merged
- ✅ **Month 1:** Independently working on assigned components
- ✅ **Month 3:** Mentoring new team members

---

## TABLE OF CONTENTS

1. [Welcome & Project Overview](#1-welcome--project-overview)
2. [Development Environment Setup](#2-development-environment-setup)
3. [Core Concepts Tutorial](#3-core-concepts-tutorial)
4. [Codebase Navigation Guide](#4-codebase-navigation-guide)
5. [Development Workflow](#5-development-workflow)
6. [First Contribution Walkthrough](#6-first-contribution-walkthrough)
7. [Agent Development Guide](#7-agent-development-guide)
8. [Testing & Quality Standards](#8-testing--quality-standards)
9. [Debugging & Troubleshooting](#9-debugging--troubleshooting)
10. [Resources & Further Learning](#10-resources--further-learning)

---

## 1. WELCOME & PROJECT OVERVIEW

### 1.1 What is Holy Grail Refinery?

**The Vision:**
Holy Grail Refinery is a 35-agent AI system that extracts **unified computational intent** from 14 programming languages. Instead of converting code between languages, we extract the **pure semantic meaning** into universal LogicNodes.

**Key Innovation:**
```
Traditional Approach:
Python → JavaScript (lossy conversion)

Holy Grail Approach:
Python → LogicNode ← JavaScript
         (universal understanding)
```

**The "14 → 4 → 1" Model:**
- **14 Languages:** Python, JS, Ruby, PHP, C, C++, Rust, Zig, Java, C#, Scala, Kotlin, MATLAB, R, Julia, Mathematica
- **4 Pods:** Dynamic, Systems, Enterprise, Mathematical
- **1 Understanding:** Unified semantic representation (Refined-IR)

### 1.2 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE TIER                       │
│  • Mission Control UI (Next.js dashboard)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    EXECUTIVE TIER                            │
│  • PM Agent: Captures user "vibes", generates PRDs          │
│  • CEO Agent: Decomposes work, fuses results                │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    SUPPORT RING                              │
│  9 Support Agents: IS, Broker, Accountant, Security,       │
│  Diplomat, Data Architect, SRE, Compliance, DevOps          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    REFINERY PODS (4 Pods)                    │
│                                                              │
│  Pod A (Dynamic):     Pod B (Systems):                      │
│  Python, JS,          C, C++,                                │
│  Ruby, PHP            Rust, Zig                              │
│                                                              │
│  Pod C (Enterprise):  Pod D (Mathematical):                 │
│  Java, C#,            MATLAB, R,                             │
│  Scala, Kotlin        Julia, Mathematica                    │
│                                                              │
│  Each Pod: 1 Manager + 1 Audit + 4 Specialists = 6 agents  │
└─────────────────────────────────────────────────────────────┘

Total: 2 Executive + 9 Support + 24 Pod Agents = 35 Agents
```

### 1.3 Your Role in the System

**As a Developer, You Will:**
1. **Implement Agent Logic** - Build intelligent agents with specific expertise
2. **Maintain Quality Standards** - Write tests, ensure 90%+ coverage
3. **Collaborate via Semantic Bus** - Agents communicate through Redis message bus
4. **Extract Semantic Meaning** - Transform code into universal LogicNodes
5. **Uphold 0.0001% Tolerance** - Audit agents verify extreme precision

**Team Structure:**
```
Chief Architect (1)
  ├── Agent Team Lead (1)
  │   ├── Pod A Developers (3)
  │   ├── Pod B Developers (3)
  │   ├── Pod C Developers (3)
  │   └── Pod D Developers (3)
  ├── Infrastructure Lead (1)
  │   ├── Backend Engineers (2)
  │   └── DevOps Engineers (2)
  ├── Frontend Lead (1)
  │   └── UI Developers (2)
  └── QA Lead (1)
      └── QA Engineers (2)
```

---

## 2. DEVELOPMENT ENVIRONMENT SETUP

### 2.1 Prerequisites Checklist

Before starting, ensure you have:

```bash
# Required Software
□ Git (2.30+)
□ Python 3.11+
□ Node.js 18+
□ Docker 24+
□ Docker Compose 2.0+
□ PostgreSQL client (psql)
□ Redis client (redis-cli)

# Recommended Tools
□ VS Code or PyCharm
□ Git GUI (GitKraken, SourceTree, or GitHub Desktop)
□ Postman or Insomnia (API testing)
□ Redis Insight (Redis GUI)
□ pgAdmin or DBeaver (Database GUI)
```

**System Requirements:**
- **OS:** Linux (Ubuntu 22.04+), macOS 12+, or Windows 11 with WSL2
- **CPU:** 4+ cores recommended
- **RAM:** 16GB minimum, 32GB recommended
- **Storage:** 50GB free space (for Docker images, databases)

### 2.2 Step-by-Step Setup (Day 1)

#### Step 1: Clone Repository

```bash
# Clone main repository
git clone https://github.com/your-org/holy-grail-refinery.git
cd holy-grail-refinery

# Set up Git configuration
git config user.name "Your Name"
git config user.email "your.email@company.com"

# Create your feature branch
git checkout -b onboarding/yourname
```

#### Step 2: Install Python Dependencies

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Verify installation
python --version  # Should show 3.11+
pip list
```

#### Step 3: Install Node.js Dependencies

```bash
# Navigate to frontend
cd mission-control

# Install dependencies
npm install

# Verify installation
node --version  # Should show 18+
npm --version
```

#### Step 4: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Example `.env` file:**
```bash
# Database
DATABASE_URL=postgresql://hgr_admin:dev_password@localhost:5432/hgr_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# API Keys (Development)
ANTHROPIC_API_KEY=your_dev_key_here

# Environment
ENVIRONMENT=development
DEBUG=true

# Logging
LOG_LEVEL=DEBUG
```

#### Step 5: Start Infrastructure Services

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Wait for services to be ready
sleep 10

# Verify services
docker ps  # Should show 2 containers running
```

#### Step 6: Initialize Database

```bash
# Run database migrations
python scripts/init_database.py

# Verify tables created
psql $DATABASE_URL -c "\dt"

# Seed development data
python scripts/seed_dev_data.py
```

#### Step 7: Run Tests

```bash
# Run unit tests (should pass!)
pytest tests/unit/ -v

# Expected output:
# ============== 247 passed in 8.32s ==============
```

#### Step 8: Start Development Servers

```bash
# Terminal 1: Start API server
cd api/
uvicorn main:app --reload --port 8000

# Terminal 2: Start Mission Control UI
cd mission-control/
npm run dev

# Terminal 3: Start one test agent (PM Agent)
cd agents/pm_agent/
python main.py
```

#### Step 9: Verify Setup

```bash
# Open browser to http://localhost:3000
# You should see Mission Control dashboard

# Test API
curl http://localhost:8000/health
# Expected: {"status": "healthy"}

# Test PM Agent
curl -X POST http://localhost:8000/api/v1/agents/PM-001/status
# Expected: {"agent_id": "PM-001", "status": "active"}
```

**✅ Success Criteria:**
- All tests pass
- API responds on port 8000
- UI loads on port 3000
- PM Agent shows "active" status

---

## 3. CORE CONCEPTS TUTORIAL

### 3.1 What is a LogicNode?

A **LogicNode** is the universal representation of computational intent in Holy Grail Refinery.

**Analogy:** Think of LogicNodes like musical notation:
- Musical notes are language-independent
- Any musician can read them, regardless of their instrument
- Same melody, different instruments (languages)

**Example: List Filter Operation**

```json
{
  "logicnode_id": "ln-12345",
  "paradigm": "dynamic",
  "domain": "list_operations",
  "concept": "filter",
  "intent": "Remove elements from a collection that don't satisfy a predicate",
  
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
    {"type": "subset", "target": "filtered", "of": "collection"},
    {"type": "size_constraint", "target": "filtered", "operator": "<=", "reference": "collection"}
  ],
  
  "side_effects": [],
  
  "source_language": "python",
  "confidence": 0.99
}
```

**Same Concept, Different Languages:**

```python
# Python
filtered = [x for x in items if x > 10]

# JavaScript
const filtered = items.filter(x => x > 10);

# Ruby
filtered = items.select { |x| x > 10 }

# All extract to the SAME LogicNode!
```

### 3.2 The Refined-IR Specification

**Refined-IR** (Refined Intermediate Representation) is our universal language.

**Key Components:**
1. **Paradigm:** Dynamic, Systems, Enterprise, Mathematical
2. **Domain:** list_operations, async_programming, memory_management, etc.
3. **Concept:** filter, map, reduce, malloc, async_await, etc.
4. **Intent:** Plain English description of what the code does

**Type System:**
```
Primitives: Int, Float, String, Bool
Collections: List[T], Set[T], Map[K,V], Array[T,N]
Functions: Callable[[In], Out]
Generics: T, K, V (type parameters)
```

### 3.3 Agent Communication via Semantic Bus

Agents communicate through **Redis Pub/Sub** using structured protocols.

**6 Named Protocols:**
1. **Protocol Alpha:** PM ↔ CEO (mission management)
2. **Protocol Beta:** CEO ↔ Sub-Managers (work distribution)
3. **Protocol Delta:** Specialists → Audit (verification)
4. **Protocol Sigma:** Audit → Knowledge Lake (learning)
5. **Protocol Omega:** PM → User (human communication)
6. **Protocol Rho:** Support Ring ↔ Executive (infrastructure)

**Example Message (Protocol Alpha):**

```json
{
  "message_id": "msg-67890",
  "protocol": "alpha",
  "message_type": "mission_request",
  "sender": "PM-001",
  "recipient": "CEO-001",
  "timestamp": "2026-02-06T14:30:00Z",
  
  "payload": {
    "mission_id": "mission-12345",
    "description": "Extract Python list operations from Flask project",
    "requirements": {
      "languages": ["python"],
      "target_domains": ["list_operations", "dict_operations"]
    }
  }
}
```

**Publishing a Message:**

```python
import asyncio
import json
from infrastructure.semantic_bus import SemanticBus

async def send_message():
    bus = SemanticBus(redis_url="redis://localhost:6379")
    await bus.connect()
    
    message = {
        "message_id": "msg-001",
        "protocol": "alpha",
        "sender": "PM-001",
        "recipient": "CEO-001",
        "payload": {"mission_id": "m-123"}
    }
    
    await bus.publish("protocol.alpha", json.dumps(message))
    await bus.disconnect()

asyncio.run(send_message())
```

### 3.4 The 14 → 4 → 1 Reduction Process

**How a Mission Flows Through the System:**

```
Step 1: User Input
User: "Analyze this Python web scraper for list operations"

Step 2: PM Agent (Protocol Omega → Alpha)
PM extracts intent → Generates PRD → Sends to CEO

Step 3: CEO Agent (Protocol Alpha → Beta)
CEO decomposes PRD → Identifies Pod A (Dynamic) needed → Assigns task

Step 4: Pod A Sub-Manager (Protocol Beta → Internal)
Sub-Manager assigns Python Specialist

Step 5: Python Specialist (Extraction)
Reads code → Extracts 47 LogicNodes → Self-verification

Step 6: Audit Agent (Protocol Delta)
Runs 1,000 tests per LogicNode → Verifies 0.0001% tolerance

Step 7: Sub-Manager Fusion
Consolidates all Pod A LogicNodes → Creates "Pod Standard"

Step 8: CEO Grand Fusion (Protocol Beta → Alpha)
Fuses all 4 Pod Standards → Creates "Master Stream"

Step 9: PM Agent Delivery (Protocol Alpha → Omega)
Formats results for user → Presents insights

Step 10: User Receives
"Your scraper uses 12 list_filter operations, 8 map operations..."
```

---

## 4. CODEBASE NAVIGATION GUIDE

### 4.1 Repository Structure

```
holy-grail-refinery/
├── agents/                      # All 35 agent implementations
│   ├── pm_agent/               # Agent 01: PM Agent
│   │   ├── pm_agent.py         # Main agent logic
│   │   ├── prompts.py          # LLM prompt templates
│   │   ├── tests/              # Agent-specific tests
│   │   └── Dockerfile          # Container definition
│   ├── ceo_agent/              # Agent 02: CEO Agent
│   ├── pod_a/                  # Pod A agents (6 agents)
│   │   ├── sub_manager/
│   │   ├── audit_agent/
│   │   ├── python_specialist/
│   │   ├── javascript_specialist/
│   │   ├── ruby_specialist/
│   │   └── php_specialist/
│   └── ... (similar for Pods B, C, D)
│
├── api/                        # REST API layer
│   ├── main.py                 # FastAPI application
│   ├── routers/                # API endpoints
│   │   ├── missions.py
│   │   ├── agents.py
│   │   └── knowledge.py
│   ├── models/                 # Pydantic models
│   └── dependencies.py         # Dependency injection
│
├── infrastructure/             # Shared infrastructure
│   ├── semantic_bus.py        # Redis Pub/Sub wrapper
│   ├── database.py            # PostgreSQL manager
│   ├── knowledge_lake.py      # Vector search
│   └── logicnode_registry.py  # LogicNode CRUD
│
├── mission-control/           # Next.js UI
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/             # Next.js pages
│   │   └── lib/               # Utilities
│   └── public/                # Static assets
│
├── tests/                     # Test suites
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── e2e/                   # End-to-end tests
│
├── scripts/                   # Utility scripts
│   ├── init_database.py
│   ├── seed_dev_data.py
│   └── deploy.sh
│
├── docs/                      # Documentation
│   ├── 01_PRD.md
│   ├── 05_Architecture.md
│   └── ... (60 total documents)
│
├── docker-compose.yml         # Local development stack
├── requirements.txt           # Python dependencies
├── pytest.ini                 # Test configuration
└── README.md                  # Project overview
```

### 4.2 Key Files to Understand

**High Priority (Read These First):**

1. `docs/01_Product_Requirements_Document.md` - Understand the vision
2. `docs/05_System_Architecture_Document.md` - Learn system structure
3. `docs/09_Refined_IR_Specification.md` - Master LogicNode format
4. `agents/pm_agent/pm_agent.py` - See a complete agent implementation
5. `infrastructure/semantic_bus.py` - Learn message passing

**Medium Priority (Week 1):**

6. `api/main.py` - Understand API structure
7. `agents/pod_a/python_specialist/python_specialist.py` - See language extraction
8. `tests/integration/test_agent_communication.py` - Learn testing patterns
9. `docker-compose.yml` - Understand local infrastructure

**Low Priority (Month 1):**

10. Mission Control UI code (if you're frontend)
11. Deployment scripts (if you're DevOps)
12. Other pod implementations

### 4.3 Code Reading Exercise

**Exercise: Trace a Mission from Start to Finish**

Open these files side-by-side and follow the data flow:

```
1. api/routers/missions.py
   → User submits mission via POST /api/v1/missions

2. agents/pm_agent/pm_agent.py
   → PM Agent receives mission, generates PRD

3. infrastructure/semantic_bus.py
   → PM publishes Protocol Alpha message to CEO

4. agents/ceo_agent/ceo_agent.py
   → CEO receives message, decomposes work

5. agents/pod_a/sub_manager/sub_manager.py
   → Sub-Manager assigns to Python Specialist

6. agents/pod_a/python_specialist/python_specialist.py
   → Specialist extracts LogicNodes

7. infrastructure/logicnode_registry.py
   → LogicNodes stored in database

8. api/routers/missions.py
   → User retrieves mission results
```

**Task:** Add print statements to trace this flow, then run a test mission.

---

## 5. DEVELOPMENT WORKFLOW

### 5.1 Daily Development Cycle

```
Morning:
09:00 - Pull latest changes from main
09:15 - Review assigned issues in GitHub
09:30 - Stand-up meeting (15 min)
10:00 - Start development work

Development Loop:
1. Create feature branch
2. Write tests (TDD approach)
3. Implement feature
4. Run tests locally
5. Commit with meaningful message
6. Push and create PR
7. Address code review feedback
8. Merge to main

Afternoon:
14:00 - Code review for teammates
15:00 - Continue feature work
16:30 - Document changes
17:00 - End of day commit
```

### 5.2 Git Workflow

**Branch Naming Convention:**

```
feature/SHORT-DESCRIPTION      # New features
bugfix/ISSUE-NUMBER           # Bug fixes
refactor/COMPONENT-NAME       # Code improvements
docs/DOCUMENT-ID              # Documentation updates
test/COMPONENT-NAME           # Test additions

Examples:
feature/python-specialist-async-support
bugfix/1234-semantic-bus-timeout
refactor/logicnode-validation
docs/51-developer-onboarding
test/pm-agent-error-handling
```

**Commit Message Format:**

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Examples:**

```
feat(python-specialist): Add async/await extraction support

- Implemented AST visitor for async functions
- Added LogicNode templates for async patterns
- Updated tests with 15 new async scenarios

Closes #234
```

```
fix(semantic-bus): Prevent message timeout during high load

- Increased Redis connection pool size to 50
- Added exponential backoff for retries
- Implemented circuit breaker pattern

Fixes #456
```

**Types:** feat, fix, docs, style, refactor, test, chore

### 5.3 Pull Request Process

**Creating a PR:**

```bash
# 1. Ensure tests pass
pytest tests/ -v

# 2. Ensure linting passes
black .
flake8 .
mypy .

# 3. Push branch
git push origin feature/your-feature

# 4. Create PR on GitHub
# - Use PR template
# - Link related issues
# - Add screenshots if UI changes
# - Request reviewers
```

**PR Template:**

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally

## Related Issues
Closes #123
```

**Code Review Checklist (for Reviewers):**

```
□ Code Quality
  □ Follows Python/TypeScript style guide
  □ No code smells or anti-patterns
  □ Appropriate use of abstractions
  □ No unnecessary complexity

□ Testing
  □ Tests cover new functionality
  □ Edge cases considered
  □ Tests are readable and maintainable

□ Documentation
  □ Docstrings present for public methods
  □ README updated if needed
  □ Comments explain "why", not "what"

□ Architecture
  □ Fits within existing architecture
  □ No tight coupling introduced
  □ Proper error handling

□ Performance
  □ No obvious performance issues
  □ Database queries optimized
  □ No N+1 query problems
```

---

## 6. FIRST CONTRIBUTION WALKTHROUGH

### 6.1 Beginner Task: Add a New Concept to Knowledge Lake

**Goal:** Add "list_reverse" concept to the Python Specialist's knowledge base.

**Estimated Time:** 2-4 hours

**Step 1: Understand the Concept**

```python
# List reverse in Python
original = [1, 2, 3, 4, 5]
reversed_list = original[::-1]
# Result: [5, 4, 3, 2, 1]
```

**Step 2: Create Feature Branch**

```bash
git checkout main
git pull origin main
git checkout -b feature/list-reverse-concept
```

**Step 3: Add Concept to Catalog**

Edit: `agents/pod_a/python_specialist/concept_catalog.py`

```python
# Add to CONCEPTS dictionary
CONCEPTS = {
    # ... existing concepts ...
    
    "list_reverse": {
        "domain": "list_operations",
        "description": "Reverse the order of elements in a list",
        "python_implementations": [
            "slicing: list[::-1]",
            "method: list.reverse()",
            "function: reversed(list)"
        ],
        "logicnode_template": "ln_templates/list_reverse.json"
    }
}
```

**Step 4: Create LogicNode Template**

Create: `agents/pod_a/python_specialist/ln_templates/list_reverse.json`

```json
{
  "paradigm": "dynamic",
  "domain": "list_operations",
  "concept": "reverse",
  "intent": "Reverse the order of elements in a collection",
  
  "inputs": [
    {
      "name": "collection",
      "type": "List[T]",
      "description": "The list to reverse"
    }
  ],
  
  "outputs": [
    {
      "name": "reversed",
      "type": "List[T]",
      "description": "New list with elements in reverse order"
    }
  ],
  
  "preconditions": [
    {
      "type": "not_null",
      "target": "collection"
    }
  ],
  
  "postconditions": [
    {
      "type": "equal_size",
      "target": "reversed",
      "reference": "collection"
    },
    {
      "type": "order_constraint",
      "description": "reversed[i] == collection[n-1-i]"
    }
  ],
  
  "side_effects": [],
  "time_complexity": "O(n)",
  "space_complexity": "O(n)"
}
```

**Step 5: Write Tests**

Create: `tests/unit/test_list_reverse_concept.py`

```python
import pytest
from agents.pod_a.python_specialist.python_specialist import PythonSpecialist

def test_list_reverse_extraction():
    """
    Test that Python Specialist correctly extracts list_reverse concept
    """
    specialist = PythonSpecialist()
    
    # Test code
    python_code = """
def reverse_list(items):
    return items[::-1]
"""
    
    # Extract LogicNodes
    logicnodes = specialist.extract_logicnodes(python_code)
    
    # Verify extraction
    assert len(logicnodes) == 1
    assert logicnodes[0]["concept"] == "reverse"
    assert logicnodes[0]["domain"] == "list_operations"
    assert len(logicnodes[0]["inputs"]) == 1
    assert len(logicnodes[0]["outputs"]) == 1

def test_list_reverse_multiple_implementations():
    """
    Test that all Python reverse implementations extract to same LogicNode
    """
    specialist = PythonSpecialist()
    
    implementations = [
        "result = items[::-1]",
        "items.reverse()",
        "result = list(reversed(items))"
    ]
    
    logicnodes_list = [
        specialist.extract_logicnodes(impl) for impl in implementations
    ]
    
    # All should produce same concept
    for nodes in logicnodes_list:
        assert nodes[0]["concept"] == "reverse"

def test_list_reverse_postconditions():
    """
    Test that postconditions are correctly defined
    """
    specialist = PythonSpecialist()
    
    logicnode = specialist.get_concept_template("list_reverse")
    
    # Check postconditions
    postconditions = logicnode["postconditions"]
    assert any(pc["type"] == "equal_size" for pc in postconditions)
    assert any("order_constraint" in str(pc) for pc in postconditions)
```

**Step 6: Run Tests**

```bash
# Run your new tests
pytest tests/unit/test_list_reverse_concept.py -v

# Run all tests to ensure nothing broke
pytest tests/unit/ -v
```

**Step 7: Update Documentation**

Edit: `docs/10_Pod_A_Dynamic_Languages_Specification.md`

Add to the concept catalog section:

```markdown
### List Operations Domain

#### reverse
**Intent:** Reverse the order of elements in a collection

**Python Syntax:**
```python
reversed_list = original[::-1]
original.reverse()  # In-place
reversed_list = list(reversed(original))
```

**LogicNode Template:** `list_reverse.json`
```

**Step 8: Commit and Push**

```bash
git add .
git commit -m "feat(python-specialist): Add list_reverse concept

- Added list_reverse to concept catalog
- Created LogicNode template with postconditions
- Added comprehensive test coverage (3 test cases)
- Updated Pod A documentation

Closes #789"

git push origin feature/list-reverse-concept
```

**Step 9: Create Pull Request**

1. Go to GitHub
2. Click "New Pull Request"
3. Fill in PR template
4. Request review from Python Specialist maintainer
5. Address feedback
6. Merge when approved!

**✅ Success!** You've made your first contribution!

---

## 7. AGENT DEVELOPMENT GUIDE

### 7.1 Agent Development Lifecycle

**Phase 1: Planning (1 day)**
- Read agent's 8-part profile
- Understand agent's role in system
- Review communication protocols
- Identify required integrations

**Phase 2: Implementation (1 week)**
- Create agent class structure
- Implement state machine
- Add Semantic Bus integration
- Write extraction/processing logic

**Phase 3: Testing (3 days)**
- Write unit tests (90%+ coverage)
- Write integration tests
- Test agent communication
- Performance testing

**Phase 4: Deployment (1 day)**
- Create Dockerfile
- Add to docker-compose.yml
- Deploy to development
- Smoke testing

### 7.2 Agent Class Template

**File:** `agents/template/agent_template.py`

```python
"""
Template for creating new agents in Holy Grail Refinery
"""

import asyncio
import logging
from typing import Dict, Optional
from enum import Enum
from datetime import datetime
import uuid

from infrastructure.semantic_bus import SemanticBus
from infrastructure.database import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)

class AgentState(Enum):
    """
    Standard agent states (FSM)
    """
    IDLE = "idle"
    PROCESSING = "processing"
    WAITING = "waiting"
    ERROR = "error"

class AgentTemplate:
    """
    Template class for Holy Grail Refinery agents
    
    Replace 'AgentTemplate' with your agent name (e.g., PythonSpecialist)
    """
    
    def __init__(
        self,
        agent_id: str,
        semantic_bus: SemanticBus,
        database: DatabaseManager
    ):
        """
        Initialize agent
        
        Args:
            agent_id: Unique agent identifier (e.g., "AGENT-PY-001")
            semantic_bus: Redis Pub/Sub connection
            database: PostgreSQL connection
        """
        self.agent_id = agent_id
        self.semantic_bus = semantic_bus
        self.database = database
        
        # Agent state
        self.state = AgentState.IDLE
        self.current_task = None
        
        # Metrics
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.startup_time = datetime.utcnow()
        
        logger.info(f"Agent {self.agent_id} initialized")
    
    async def start(self):
        """
        Start agent (subscribe to channels, begin processing)
        """
        logger.info(f"Agent {self.agent_id} starting...")
        
        # Subscribe to relevant channels
        await self.semantic_bus.subscribe(
            f"agent.{self.agent_id}",
            self._handle_message
        )
        
        # Announce availability
        await self._announce_startup()
        
        # Main processing loop
        await self._process_loop()
    
    async def _process_loop(self):
        """
        Main processing loop (agent stays alive)
        """
        while True:
            try:
                if self.state == AgentState.IDLE:
                    # Wait for tasks
                    await asyncio.sleep(1)
                
                elif self.state == AgentState.PROCESSING:
                    # Process current task
                    await self._process_task(self.current_task)
                
                elif self.state == AgentState.ERROR:
                    # Handle error state
                    await self._recover_from_error()
                
            except Exception as e:
                logger.error(f"Error in process loop: {e}")
                self.state = AgentState.ERROR
    
    async def _handle_message(self, message: Dict):
        """
        Handle incoming message from Semantic Bus
        
        Args:
            message: Message dictionary with protocol, payload, etc.
        """
        logger.info(f"Received message: {message['message_type']}")
        
        message_type = message.get("message_type")
        
        if message_type == "task_assignment":
            await self._handle_task_assignment(message)
        
        elif message_type == "status_request":
            await self._handle_status_request(message)
        
        elif message_type == "shutdown":
            await self._handle_shutdown(message)
        
        else:
            logger.warning(f"Unknown message type: {message_type}")
    
    async def _handle_task_assignment(self, message: Dict):
        """
        Handle task assignment from manager
        """
        if self.state != AgentState.IDLE:
            logger.warning(f"Received task while in state {self.state}")
            return
        
        self.current_task = message["payload"]["task"]
        self.state = AgentState.PROCESSING
        
        logger.info(f"Task assigned: {self.current_task['task_id']}")
    
    async def _process_task(self, task: Dict):
        """
        Process assigned task (IMPLEMENT YOUR LOGIC HERE)
        
        Args:
            task: Task dictionary with task_id, requirements, etc.
        """
        task_id = task["task_id"]
        
        try:
            logger.info(f"Processing task {task_id}")
            
            # === YOUR AGENT LOGIC GOES HERE ===
            # Example: Extract LogicNodes, verify code, etc.
            result = await self._execute_task_logic(task)
            
            # Send result
            await self._send_result(task_id, result)
            
            # Update state
            self.state = AgentState.IDLE
            self.tasks_completed += 1
            self.current_task = None
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            self.state = AgentState.ERROR
            self.tasks_failed += 1
            await self._send_error(task_id, str(e))
    
    async def _execute_task_logic(self, task: Dict) -> Dict:
        """
        Execute core agent logic (IMPLEMENT THIS)
        
        Args:
            task: Task dictionary
        
        Returns:
            Result dictionary
        """
        # IMPLEMENT YOUR AGENT'S CORE FUNCTIONALITY HERE
        # Example for Python Specialist:
        # - Parse Python code
        # - Extract AST
        # - Identify patterns
        # - Generate LogicNodes
        # - Run self-verification
        
        raise NotImplementedError("Implement agent logic")
    
    async def _send_result(self, task_id: str, result: Dict):
        """
        Send task result via Semantic Bus
        """
        message = {
            "message_id": str(uuid.uuid4()),
            "protocol": "beta",  # or appropriate protocol
            "sender": self.agent_id,
            "recipient": "MANAGER-POD-A-001",  # or appropriate recipient
            "message_type": "task_complete",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "task_id": task_id,
                "result": result
            }
        }
        
        await self.semantic_bus.publish(
            f"agent.{message['recipient']}",
            message
        )
    
    async def _send_error(self, task_id: str, error: str):
        """
        Send task error via Semantic Bus
        """
        message = {
            "message_id": str(uuid.uuid4()),
            "protocol": "beta",
            "sender": self.agent_id,
            "recipient": "MANAGER-POD-A-001",
            "message_type": "task_failed",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "task_id": task_id,
                "error": error
            }
        }
        
        await self.semantic_bus.publish(
            f"agent.{message['recipient']}",
            message
        )
    
    async def _announce_startup(self):
        """
        Announce agent availability on startup
        """
        message = {
            "message_id": str(uuid.uuid4()),
            "sender": self.agent_id,
            "message_type": "agent_startup",
            "timestamp": datetime.utcnow().isoformat(),
            "payload": {
                "state": self.state.value
            }
        }
        
        await self.semantic_bus.publish("system.events", message)
    
    def get_health_status(self) -> Dict:
        """
        Get agent health status
        
        Returns:
            Health status dictionary
        """
        uptime = (datetime.utcnow() - self.startup_time).total_seconds()
        
        return {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "uptime_seconds": uptime,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "success_rate": (
                self.tasks_completed / (self.tasks_completed + self.tasks_failed)
                if (self.tasks_completed + self.tasks_failed) > 0
                else 0.0
            )
        }

# Entry point
if __name__ == "__main__":
    import sys
    
    async def main():
        # Initialize infrastructure
        semantic_bus = SemanticBus(redis_url="redis://localhost:6379")
        await semantic_bus.connect()
        
        database = DatabaseManager(
            database_url="postgresql://localhost/hgr_dev"
        )
        await database.connect()
        
        # Create agent
        agent = AgentTemplate(
            agent_id="AGENT-TEMPLATE-001",
            semantic_bus=semantic_bus,
            database=database
        )
        
        # Start agent
        await agent.start()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAgent shutting down...")
        sys.exit(0)
```

### 7.3 Testing Your Agent

**File:** `tests/unit/test_agent_template.py`

```python
import pytest
import asyncio
from agents.template.agent_template import AgentTemplate, AgentState

@pytest.fixture
async def agent(test_semantic_bus, test_database):
    """
    Create agent for testing
    """
    agent = AgentTemplate(
        agent_id="AGENT-TEST-001",
        semantic_bus=test_semantic_bus,
        database=test_database
    )
    return agent

@pytest.mark.asyncio
async def test_agent_initialization(agent):
    """
    Test that agent initializes correctly
    """
    assert agent.agent_id == "AGENT-TEST-001"
    assert agent.state == AgentState.IDLE
    assert agent.tasks_completed == 0

@pytest.mark.asyncio
async def test_agent_handles_task_assignment(agent):
    """
    Test that agent correctly handles task assignment
    """
    task = {
        "task_id": "task-001",
        "type": "test_task",
        "data": {}
    }
    
    message = {
        "message_type": "task_assignment",
        "payload": {"task": task}
    }
    
    await agent._handle_task_assignment(message)
    
    assert agent.state == AgentState.PROCESSING
    assert agent.current_task == task

@pytest.mark.asyncio
async def test_agent_health_status(agent):
    """
    Test health status reporting
    """
    agent.tasks_completed = 10
    agent.tasks_failed = 1
    
    health = agent.get_health_status()
    
    assert health["agent_id"] == "AGENT-TEST-001"
    assert health["tasks_completed"] == 10
    assert health["tasks_failed"] == 1
    assert health["success_rate"] == pytest.approx(0.909, 0.01)
```

---

## 8. TESTING & QUALITY STANDARDS

### 8.1 Testing Requirements

**Coverage Requirements:**
- **Unit Tests:** ≥ 90% code coverage
- **Integration Tests:** All agent interactions
- **E2E Tests:** Critical user flows

**Test Pyramid:**
```
        /\
       /E2\      10% E2E (slow, expensive)
      /____\
     /Integ\     20% Integration (medium)
    /______\
   /  Unit  \    70% Unit (fast, cheap)
  /__________\
```

### 8.2 Writing Good Tests

**Good Test Characteristics:**
1. **Fast:** Unit tests < 100ms each
2. **Isolated:** No dependencies on other tests
3. **Repeatable:** Same result every time
4. **Self-Validating:** Clear pass/fail
5. **Timely:** Written before/during implementation

**Test Naming Convention:**

```python
def test_<component>_<scenario>_<expected_result>():
    """
    Test that <component> <expected_result> when <scenario>
    """
```

**Examples:**

```python
def test_pm_agent_generates_prd_when_given_valid_vibe():
    """
    Test that PM Agent generates valid PRD when given valid user vibe
    """

def test_python_specialist_extracts_filter_logicnode_from_list_comprehension():
    """
    Test that Python Specialist extracts filter LogicNode from list comprehension
    """

def test_semantic_bus_retries_on_connection_failure():
    """
    Test that Semantic Bus retries message publishing on connection failure
    """
```

### 8.3 Testing Best Practices

**Use Fixtures for Setup:**

```python
@pytest.fixture
def sample_python_code():
    """
    Sample Python code for testing
    """
    return """
def filter_evens(numbers):
    return [x for x in numbers if x % 2 == 0]
"""

def test_extraction(sample_python_code):
    specialist = PythonSpecialist()
    nodes = specialist.extract(sample_python_code)
    assert len(nodes) == 1
```

**Test One Thing Per Test:**

```python
# BAD: Tests multiple things
def test_agent():
    agent = PythonSpecialist()
    assert agent.state == AgentState.IDLE  # State
    assert agent.extract("code")  # Extraction
    assert agent.health  # Health

# GOOD: One assertion per test
def test_agent_initializes_in_idle_state():
    agent = PythonSpecialist()
    assert agent.state == AgentState.IDLE

def test_agent_extracts_logicnodes():
    agent = PythonSpecialist()
    nodes = agent.extract("code")
    assert len(nodes) > 0
```

---

## 9. DEBUGGING & TROUBLESHOOTING

### 9.1 Common Issues & Solutions

**Issue 1: Agent Not Receiving Messages**

**Symptoms:**
- Agent starts successfully
- No messages processed
- No errors in logs

**Solution:**
```bash
# 1. Check Redis connection
redis-cli ping
# Should return: PONG

# 2. Check subscriptions
redis-cli
> PUBSUB CHANNELS
# Should show agent.AGENT-ID

# 3. Verify message publishing
redis-cli
> PUBLISH agent.PM-001 '{"test": "message"}'
# Agent should log receipt

# 4. Check channel names match
# Sender publishes to: agent.PM-001
# Agent subscribes to: agent.PM-001
```

**Issue 2: Database Connection Errors**

**Symptoms:**
```
psycopg2.OperationalError: could not connect to server
```

**Solution:**
```bash
# 1. Check PostgreSQL is running
docker ps | grep postgres

# 2. Test connection
psql $DATABASE_URL -c "SELECT 1"

# 3. Check credentials
echo $DATABASE_URL
# Should match .env file

# 4. Restart database
docker-compose restart postgres
```

**Issue 3: Tests Failing in CI but Passing Locally**

**Common Causes:**
1. **Different Python versions** - Pin version in CI
2. **Missing environment variables** - Add to GitHub secrets
3. **Database state** - Ensure clean database between tests
4. **Timing issues** - Add sleeps or awaits

**Solution:**
```bash
# Run tests exactly as CI does
docker-compose -f .github/docker-compose.test.yml up -d
pytest tests/ -v
```

### 9.2 Debugging Tools

**Logging:**

```python
import logging

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# In your code
logger.debug("About to extract LogicNodes")
logger.info(f"Extracted {len(nodes)} nodes")
logger.warning("No nodes found, retrying...")
logger.error("Extraction failed", exc_info=True)
```

**Interactive Debugging (pdb):**

```python
import pdb

def extract_logicnodes(code):
    # ... some code ...
    pdb.set_trace()  # Debugger will pause here
    # ... more code ...
```

**Redis Monitoring:**

```bash
# Monitor all Redis activity
redis-cli monitor

# Check key patterns
redis-cli
> KEYS agent:*

# Inspect a message
> GET agent:PM-001:last_message
```

**Database Queries:**

```bash
# Connect to database
psql $DATABASE_URL

# Check agent status
SELECT agent_id, state, tasks_completed 
FROM agents 
ORDER BY tasks_completed DESC;

# Check recent LogicNodes
SELECT logicnode_id, concept, confidence 
FROM logicnodes 
ORDER BY created_at DESC 
LIMIT 10;
```

---

## 10. RESOURCES & FURTHER LEARNING

### 10.1 Internal Documentation

**Must-Read Documents (Priority Order):**

1. [Product Requirements Document](../01_Product_Requirements_Document.md)
2. [System Architecture Document](../05_System_Architecture_Document.md)
3. [Refined-IR Specification](../09_Refined_IR_Specification.md)
4. [Agent Architecture Specification](../06_Agent_Architecture_Specification.md)
5. [Communication Protocol Specification](../07_Communication_Protocol_Specification.md)

**Pod-Specific Learning:**

- **Pod A Developers:** Read [Doc 10: Pod A Specification](../10_Pod_A_Dynamic_Languages_Specification.md)
- **Pod B Developers:** Read [Doc 11: Pod B Specification](../11_Pod_B_Systems_Specification.md)
- **Pod C Developers:** Read [Doc 12: Pod C Specification](../12_Pod_C_Enterprise_Specification.md)
- **Pod D Developers:** Read [Doc 13: Pod D Specification](../13_Pod_D_Mathematical_Languages_Specification.md)

### 10.2 External Resources

**Python & Async Programming:**
- [Real Python - Async IO Tutorial](https://realpython.com/async-io-python/)
- [Python AST Documentation](https://docs.python.org/3/library/ast.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

**Docker & Infrastructure:**
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Redis Pub/Sub Guide](https://redis.io/topics/pubsub)
- [PostgreSQL Tutorial](https://www.postgresql.org/docs/current/tutorial.html)

**Testing:**
- [Pytest Documentation](https://docs.pytest.org/)
- [Testing Best Practices](https://testdriven.io/blog/testing-best-practices/)

**LLM Development:**
- [Anthropic Claude Documentation](https://docs.anthropic.com/)
- [LangChain Documentation](https://python.langchain.com/)

### 10.3 Team Communication

**Channels:**
- **#dev-general** - General development discussion
- **#pod-a** - Pod A development
- **#pod-b** - Pod B development
- **#pod-c** - Pod C development
- **#pod-d** - Pod D development
- **#infrastructure** - Infrastructure and DevOps
- **#frontend** - Mission Control UI
- **#help** - Get help with issues

**Meetings:**
- **Daily Standup:** 9:30 AM (15 min)
- **Weekly Planning:** Monday 10:00 AM (1 hour)
- **Code Review Sessions:** Wednesday 2:00 PM (1 hour)
- **Architecture Review:** Friday 3:00 PM (1 hour)

**Office Hours:**
- **Chief Architect:** Tuesday 1-2 PM
- **Infrastructure Lead:** Thursday 2-3 PM
- **QA Lead:** Wednesday 3-4 PM

### 10.4 Mentorship Program

**Your Onboarding Buddy:**
You'll be assigned an onboarding buddy who will:
- Answer questions
- Review your first PRs
- Introduce you to the team
- Help with debugging

**Buddy Responsibilities:**
- Schedule 30-min check-ins (Days 1, 3, 7, 14, 30)
- Pair programming sessions (at least 3 in first month)
- Code review all first-week PRs
- Be available for questions

---

## APPENDIX A: QUICK REFERENCE CHEAT SHEET

### Development Commands

```bash
# Start infrastructure
docker-compose up -d postgres redis

# Run tests
pytest tests/unit/ -v                    # Unit tests
pytest tests/integration/ -v             # Integration tests
pytest tests/ --cov                      # With coverage

# Linting
black .                                  # Format code
flake8 .                                 # Lint
mypy .                                   # Type check

# Database
python scripts/init_database.py         # Initialize
python scripts/seed_dev_data.py         # Seed data
psql $DATABASE_URL                       # Connect

# Agent operations
python agents/pm_agent/main.py          # Run PM Agent
curl http://localhost:8000/api/v1/agents/PM-001/status
```

### Key URLs

```
Mission Control UI:     http://localhost:3000
API Documentation:      http://localhost:8000/docs
API Health Check:       http://localhost:8000/health
PostgreSQL:             postgresql://localhost:5432/hgr_dev
Redis:                  redis://localhost:6379/0
```

### File Paths

```
Agent implementations:  agents/<agent_name>/
API endpoints:          api/routers/
Tests:                  tests/unit/, tests/integration/
Documentation:          docs/
Infrastructure:         infrastructure/
Mission Control:        mission-control/src/
```

---

## DOCUMENT METADATA

**Document ID:** 51  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Documentation & Training  
**Owner:** Chief Architect  
**Target Audience:** New developers joining the project  
**Estimated Reading Time:** 4-6 hours  
**Next Document:** 52 (API Documentation & Reference)

---

**Welcome to the team! We're excited to have you on this journey to build the future of semantic code understanding. If you have any questions, don't hesitate to ask in #help or reach out to your onboarding buddy.**

**Happy coding! 🚀**

---

*End of Developer Onboarding Guide*
