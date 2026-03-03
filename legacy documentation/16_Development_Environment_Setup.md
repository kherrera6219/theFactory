# DEVELOPMENT ENVIRONMENT SETUP
## Complete Guide for Holy Grail Refinery Development

**Version:** 1.0  
**Date:** February 2026  
**Status:** Design Phase - Complete Specification  
**Document Owner:** DevOps Lead

---

## EXECUTIVE SUMMARY

This document provides step-by-step instructions for setting up the complete development environment for the Holy Grail Refinery on the AW1 local workstation. The system runs entirely on local hardware using Docker containers, with no cloud dependencies except for LLM API calls.

**Prerequisites:**
- **Hardware:** AW1 (i7-14700F, RTX 4060 Ti 16GB, 32GB RAM, 1TB SSD)
- **OS:** Windows 10/11 64-bit with WSL2 or Ubuntu 24.04 LTS
- **Internet:** For package downloads and Anthropic API access
- **GitHub Account:** For version control and collaboration

**Installation Time:** Approximately 2-3 hours for complete setup

---

## 1. HARDWARE REQUIREMENTS

### 1.1 AW1 Specifications

**Minimum Requirements:**
```
CPU:     Intel i7-14700F (20 cores: 8 P-cores + 12 E-cores)
         Base: 2.1 GHz, Turbo: 5.3 GHz
         28 threads total
         
GPU:     NVIDIA RTX 4060 Ti (16GB GDDR6)
         4,352 CUDA cores
         AD106 architecture
         
RAM:     32GB DDR5-4800 (2x16GB dual-channel)
         64GB recommended for full system load
         
Storage: 1TB NVMe SSD (PCIe 4.0)
         Sequential Read: 7000+ MB/s
         Sequential Write: 5000+ MB/s
         
Network: Gigabit Ethernet or WiFi 6
         Low latency essential for Redis Pub/Sub
```

**Recommended Configuration:**
- CPU Governor: Performance mode (Linux) or High Performance power plan (Windows)
- GPU: Latest NVIDIA drivers (535+ for CUDA 12.2)
- RAM: Enable XMP profile in BIOS for rated speeds
- Storage: Leave 20% free space for optimal SSD performance
- Cooling: Ensure adequate airflow (CPU under 80°C under load)

### 1.2 Storage Allocation Plan

**1TB Breakdown:**
```
Operating System:        100 GB
  - Windows 10/11 or Ubuntu 24.04
  - System files, page file, temp directories

Docker Images:           150 GB
  - 35 agent containers (~3-4 GB each)
  - 5 infrastructure containers (~5-10 GB each)
  - Base images and layers

Knowledge Lake:          300 GB
  - Python 3.11 documentation: 25 GB
  - JavaScript/TypeScript: 30 GB
  - Ruby, PHP: 20 GB each
  - C, C++: 15 GB each
  - Rust, Zig: 20 GB each
  - Java, C#, Scala, Kotlin: 25 GB each
  - MATLAB, R, Julia, Mathematica: 30 GB each
  - Vector embeddings: 50 GB

Databases:               50 GB
  - PostgreSQL (State Graph): 20 GB
  - Redis (persistence): 10 GB
  - SQLite (Traceability): 10 GB
  - Git repositories: 10 GB

Mission Artifacts:       100 GB
  - LogicNodes (JSON): 40 GB
  - Compiled binaries: 30 GB
  - Trace logs: 20 GB
  - Checkpoints: 10 GB

Free Space Buffer:       300 GB
  - Build cache
  - Temporary files
  - Growth headroom
```

### 1.3 Operating System Selection

**Option 1: Windows 10/11 with WSL2 (Recommended for New Users)**

**Advantages:**
- Native Windows applications available
- GPU passthrough to WSL2 supported
- Docker Desktop provides GUI management
- Familiar environment for most developers

**Disadvantages:**
- Slight performance overhead vs native Linux
- Two operating systems consuming RAM
- More complex networking (WSL2 bridge)

**Requirements:**
- Windows 10 Pro/Enterprise (Build 19041+) or Windows 11
- Hyper-V enabled
- WSL2 installed with Ubuntu 24.04 distribution

---

**Option 2: Ubuntu 24.04 LTS (Recommended for Performance)**

**Advantages:**
- Native Docker performance (no virtualization)
- Lower RAM overhead (no Windows)
- Better networking (no WSL2 bridge)
- Simpler container management

**Disadvantages:**
- Learning curve for Windows users
- Some proprietary tools unavailable (e.g., certain IDEs)
- GPU drivers require manual installation

**Requirements:**
- Clean installation (recommended) or dual-boot
- Secure Boot disabled (for NVIDIA drivers)
- GRUB bootloader configured

---

## 2. SOFTWARE PREREQUISITES

### 2.1 Core Development Tools

#### Git Version Control

**Windows Installation:**
```powershell
# Using winget (Windows Package Manager)
winget install -e --id Git.Git

# Or download from: https://git-scm.com/download/win
```

**Ubuntu Installation:**
```bash
sudo apt update
sudo apt install git -y
```

**Verification:**
```bash
git --version
# Expected output: git version 2.43.0 or higher
```

**Initial Configuration:**
```bash
# Set identity
git config --global user.name "Your Full Name"
git config --global user.email "your.email@example.com"

# Set default branch name
git config --global init.defaultBranch main

# Enable credential caching
git config --global credential.helper cache

# Set default editor (optional)
git config --global core.editor "vim"

# View configuration
git config --list
```

---

#### GitHub Desktop (Optional Visual Interface)

**Windows Installation:**
```powershell
winget install -e --id GitHub.GitHubDesktop
```

**Ubuntu Installation:**
```bash
wget https://github.com/shiftkey/desktop/releases/download/release-3.3.6-linux1/GitHubDesktop-linux-amd64-3.3.6-linux1.deb
sudo dpkg -i GitHubDesktop-linux-amd64-3.3.6-linux1.deb
sudo apt-get install -f  # Fix any dependency issues
```

**Features:**
- Visual diff viewer
- Branch management UI
- Commit history browser
- Repository cloning wizard

---

#### Docker Desktop (Windows/Mac) or Docker Engine (Linux)

**Windows with WSL2 Setup:**

**Step 1: Enable WSL2**
```powershell
# Run as Administrator
wsl --install
wsl --update

# Install Ubuntu 24.04
wsl --install -d Ubuntu-24.04

# Set as default
wsl --set-default Ubuntu-24.04

# Verify
wsl --list --verbose
```

**Step 2: Install Docker Desktop**
```
1. Download from: https://www.docker.com/products/docker-desktop
2. Run installer (requires admin privileges)
3. Restart computer when prompted
4. Launch Docker Desktop
```

**Step 3: Configure Docker Desktop**
```
Settings > General:
  ☑ Use WSL 2 based engine
  ☑ Start Docker Desktop when you log in

Settings > Resources > WSL Integration:
  ☑ Enable integration with default WSL distro
  ☑ Enable Ubuntu-24.04

Settings > Resources > Advanced:
  CPUs: 16 (leave 4 for Windows)
  Memory: 24 GB (leave 8 GB for Windows)
  Swap: 4 GB
  Disk image size: 500 GB
```

---

**Ubuntu Native Docker Engine:**

```bash
# Remove old versions
sudo apt remove docker docker-engine docker.io containerd runc 2>/dev/null

# Install prerequisites
sudo apt update
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg |   sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg]   https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" |   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io   docker-buildx-plugin docker-compose-plugin

# Add user to docker group (avoid sudo)
sudo usermod -aG docker $USER

# Apply group change
newgrp docker

# Enable Docker to start on boot
sudo systemctl enable docker.service
sudo systemctl enable containerd.service
```

**Verification:**
```bash
docker --version
# Expected: Docker version 24.0.7 or higher

docker compose version
# Expected: Docker Compose version v2.23.0 or higher

# Test Docker
docker run hello-world

# Test Docker Compose
docker compose version
```

---

#### Node.js 20 LTS

**Windows Installation:**
```powershell
winget install -e --id OpenJS.NodeJS.LTS
```

**Ubuntu Installation (using nvm - recommended):**
```bash
# Install nvm (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash

# Reload shell configuration
source ~/.bashrc

# Install Node.js 20 LTS
nvm install 20
nvm use 20
nvm alias default 20
```

**Verification:**
```bash
node --version
# Expected: v20.11.0 or higher

npm --version
# Expected: v10.2.4 or higher

# Test npm
npm config get registry
# Expected: https://registry.npmjs.org/
```

**Global Package Configuration:**
```bash
# Set global install location (optional, avoids permission issues)
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'

# Add to PATH (add to ~/.bashrc or ~/.profile)
export PATH=~/.npm-global/bin:$PATH
source ~/.bashrc
```

---

#### Python 3.11+

**Windows Installation:**
```powershell
winget install -e --id Python.Python.3.11

# Verify installation
python --version
pip --version
```

**Ubuntu Installation:**
```bash
# Python 3.11 may not be default in Ubuntu 24.04
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Set Python 3.11 as default (optional)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --config python3

# Install pip for Python 3.11
python3.11 -m ensurepip --upgrade
```

**Verification:**
```bash
python3 --version
# Expected: Python 3.11.0 or higher

pip3 --version
# Expected: pip 23.0 or higher

# Test virtual environment creation
python3 -m venv test_venv
source test_venv/bin/activate  # Windows: test_venv\Scripts\activate
deactivate
rm -rf test_venv
```

---

### 2.2 Optional Development IDEs

**Google Antigravity IDE (Recommended for Building the Refinery)**

```
Download: https://antigravity.google/download
Platform: Windows, macOS, Linux

Features:
- AI-powered multi-agent code generation
- Terminal integration for shell access
- Git integration
- Docker container management
- Real-time collaboration
```

**Installation:**
1. Download installer for your platform
2. Run installer
3. Grant terminal access permissions
4. Configure Python and Node.js paths

---

**Visual Studio Code (Free Alternative)**

```bash
# Windows
winget install -e --id Microsoft.VisualStudioCode

# Ubuntu
wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > packages.microsoft.gpg
sudo install -D -o root -g root -m 644 packages.microsoft.gpg /etc/apt/keyrings/packages.microsoft.gpg
sudo sh -c 'echo "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/keyrings/packages.microsoft.gpg]   https://packages.microsoft.com/repos/code stable main" > /etc/apt/sources.list.d/vscode.list'
sudo apt update
sudo apt install code
```

**Recommended Extensions:**
- Python (Microsoft)
- Docker (Microsoft)
- Remote - WSL (Microsoft)
- GitLens
- Thunder Client (API testing)
- YAML
- Markdown All in One

---

## 3. REPOSITORY SETUP

### 3.1 Create GitHub Repository

**Option 1: Via GitHub Web Interface**
```
1. Navigate to: https://github.com/new
2. Repository name: holy-grail-refinery
3. Description: "35-agent AI system for unified cross-language code comprehension"
4. Visibility: Private (recommended initially)
5. Initialize: ☑ Add README file
6. .gitignore: None (we'll add custom)
7. License: MIT or Apache 2.0
8. Click "Create repository"
```

**Option 2: Via GitHub CLI**
```bash
# Install GitHub CLI
# Windows: winget install -e --id GitHub.cli
# Ubuntu: sudo apt install gh

# Authenticate
gh auth login

# Create repository
gh repo create holy-grail-refinery --private --description "35-agent AI refinery system"
```

---

### 3.2 Clone Repository Locally

```bash
# Create workspace directory
mkdir -p ~/workspace
cd ~/workspace

# Clone repository
git clone https://github.com/YOUR_USERNAME/holy-grail-refinery.git

# Or using SSH (if SSH keys configured)
git clone git@github.com:YOUR_USERNAME/holy-grail-refinery.git

# Enter repository
cd holy-grail-refinery

# Verify
git remote -v
# Expected output:
# origin  https://github.com/YOUR_USERNAME/holy-grail-refinery.git (fetch)
# origin  https://github.com/YOUR_USERNAME/holy-grail-refinery.git (push)
```

---

### 3.3 Initialize Directory Structure

**Create project structure:**
```bash
#!/bin/bash
# scripts/init-structure.sh

# Create main directories
mkdir -p agents/{executive,support,pods/{pod_a,pod_b,pod_c,pod_d}}
mkdir -p infrastructure/{redis,postgres,qdrant,git-server}
mkdir -p mission-control/{app,components,lib,public}
mkdir -p protocols/{alpha,beta,delta,sigma,omega,rho}
mkdir -p schemas/{refined-ir,databases}
mkdir -p docker/{agents,infrastructure}
mkdir -p scripts/{setup,maintenance,testing}
mkdir -p docs
mkdir -p tests/{unit,integration,e2e}
mkdir -p logs

# Create placeholder files
touch agents/executive/pm_agent.py
touch agents/executive/ceo_agent.py
touch agents/support/{is_agent,api_broker,accountant,security,compliance,data_architect,diplomat,sre,ai_data}.py

# Pod A
touch agents/pods/pod_a/{manager,audit,python_specialist,javascript_specialist,ruby_specialist,php_specialist}.py

# Pod B
touch agents/pods/pod_b/{manager,audit,c_specialist,cpp_specialist,rust_specialist,zig_specialist}.py

# Pod C
touch agents/pods/pod_c/{manager,audit,java_specialist,csharp_specialist,scala_specialist,kotlin_specialist}.py

# Pod D
touch agents/pods/pod_d/{manager,audit,matlab_specialist,r_specialist,julia_specialist,mathematica_specialist}.py

# Infrastructure configs
touch infrastructure/redis/redis.conf
touch infrastructure/postgres/init.sql
touch infrastructure/qdrant/config.yaml

# Mission Control
touch mission-control/package.json
touch mission-control/next.config.js

# Docker files
touch docker/docker-compose.yml
touch docker/docker-compose.infrastructure.yml
touch docker/agents/Dockerfile.base
touch docker/infrastructure/Dockerfile.redis

# Scripts
touch scripts/setup/install-dependencies.sh
touch scripts/setup/seed-knowledge-lake.sh
touch scripts/maintenance/backup-databases.sh
touch scripts/testing/run-integration-tests.sh

# Environment and configs
touch .env.example
touch .gitignore
touch README.md

echo "Directory structure created successfully!"
```

**Run initialization:**
```bash
chmod +x scripts/init-structure.sh
./scripts/init-structure.sh
```

**Verify structure:**
```bash
tree -L 3
```

---

### 3.4 Create .gitignore

```bash
cat > .gitignore << 'EOF'
# Environment variables
.env
.env.local
.env.*.local

# API Keys (never commit!)
**/api-keys/
**/*_API_KEY*

# Docker
.docker/
docker-compose.override.yml

# Python
__pycache__/
*.py[cod]
*$py.class
.Python
*.so
.venv/
venv/
ENV/
build/
dist/
*.egg-info/

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.next/
out/
.cache/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# Databases
*.db
*.sqlite
*.db-journal

# Temporary files
tmp/
temp/
*.tmp

# Mission artifacts
missions/*/binaries/
missions/*/traces/

# Knowledge Lake (too large for git)
knowledge-lake/vectors/
knowledge-lake/embeddings/

# Backups
backups/
*.backup
*.bak

EOF
```

---

### 3.5 Environment Configuration

**Create .env.example template:**
```bash
cat > .env.example << 'EOF'
# ==================================================================
# HOLY GRAIL REFINERY - ENVIRONMENT CONFIGURATION
# ==================================================================
# Copy this file to .env and fill in your actual values
# NEVER commit .env to version control!

# ==================================================================
# ANTHROPIC API KEYS (35 separate keys for context isolation)
# ==================================================================
# Get keys from: https://console.anthropic.com/

# Executive Tier
PM_API_KEY=sk-ant-api03-your-pm-key-here
CEO_API_KEY=sk-ant-api03-your-ceo-key-here

# Support Ring
IS_AGENT_API_KEY=sk-ant-api03-your-is-key-here
API_BROKER_API_KEY=sk-ant-api03-your-broker-key-here
ACCOUNTANT_API_KEY=sk-ant-api03-your-accountant-key-here
SECURITY_API_KEY=sk-ant-api03-your-security-key-here
COMPLIANCE_API_KEY=sk-ant-api03-your-compliance-key-here
DATA_ARCHITECT_API_KEY=sk-ant-api03-your-data-arch-key-here
DIPLOMAT_API_KEY=sk-ant-api03-your-diplomat-key-here
SRE_API_KEY=sk-ant-api03-your-sre-key-here
AI_DATA_API_KEY=sk-ant-api03-your-ai-data-key-here

# Pod A (Dynamic Languages)
MANAGER_POD_A_API_KEY=sk-ant-api03-your-pod-a-mgr-key-here
AUDIT_POD_A_API_KEY=sk-ant-api03-your-pod-a-audit-key-here
PYTHON_SPECIALIST_API_KEY=sk-ant-api03-your-python-key-here
JAVASCRIPT_SPECIALIST_API_KEY=sk-ant-api03-your-javascript-key-here
RUBY_SPECIALIST_API_KEY=sk-ant-api03-your-ruby-key-here
PHP_SPECIALIST_API_KEY=sk-ant-api03-your-php-key-here

# Pod B (Systems Languages)
MANAGER_POD_B_API_KEY=sk-ant-api03-your-pod-b-mgr-key-here
AUDIT_POD_B_API_KEY=sk-ant-api03-your-pod-b-audit-key-here
C_SPECIALIST_API_KEY=sk-ant-api03-your-c-key-here
CPP_SPECIALIST_API_KEY=sk-ant-api03-your-cpp-key-here
RUST_SPECIALIST_API_KEY=sk-ant-api03-your-rust-key-here
ZIG_SPECIALIST_API_KEY=sk-ant-api03-your-zig-key-here

# Pod C (Enterprise Languages)
MANAGER_POD_C_API_KEY=sk-ant-api03-your-pod-c-mgr-key-here
AUDIT_POD_C_API_KEY=sk-ant-api03-your-pod-c-audit-key-here
JAVA_SPECIALIST_API_KEY=sk-ant-api03-your-java-key-here
CSHARP_SPECIALIST_API_KEY=sk-ant-api03-your-csharp-key-here
SCALA_SPECIALIST_API_KEY=sk-ant-api03-your-scala-key-here
KOTLIN_SPECIALIST_API_KEY=sk-ant-api03-your-kotlin-key-here

# Pod D (Mathematical Languages)
MANAGER_POD_D_API_KEY=sk-ant-api03-your-pod-d-mgr-key-here
AUDIT_POD_D_API_KEY=sk-ant-api03-your-pod-d-audit-key-here
MATLAB_SPECIALIST_API_KEY=sk-ant-api03-your-matlab-key-here
R_SPECIALIST_API_KEY=sk-ant-api03-your-r-key-here
JULIA_SPECIALIST_API_KEY=sk-ant-api03-your-julia-key-here
MATHEMATICA_SPECIALIST_API_KEY=sk-ant-api03-your-mathematica-key-here

# ==================================================================
# REDIS CONFIGURATION (Semantic Bus)
# ==================================================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your-secure-redis-password-change-this
REDIS_MAXMEMORY=4gb
REDIS_MAXMEMORY_POLICY=allkeys-lru

# ==================================================================
# POSTGRESQL CONFIGURATION (Global State Graph)
# ==================================================================
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=holy_grail_refinery
POSTGRES_USER=refinery_admin
POSTGRES_PASSWORD=your-secure-postgres-password-change-this
POSTGRES_MAX_CONNECTIONS=200

# ==================================================================
# QDRANT CONFIGURATION (Vector Database for Knowledge Lake)
# ==================================================================
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_API_KEY=your-qdrant-api-key-change-this

# ==================================================================
# MISSION CONTROL UI (Next.js)
# ==================================================================
NEXTAUTH_SECRET=your-nextauth-secret-min-32-chars-change-this
NEXTAUTH_URL=http://localhost:3000
MISSION_CONTROL_PORT=3000

# ==================================================================
# SYSTEM CONFIGURATION
# ==================================================================
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
ENVIRONMENT=development  # development, staging, production
MAX_CONCURRENT_MISSIONS=5
CHECKPOINT_INTERVAL_SECONDS=60
AUDIT_VERIFICATION_TESTS=1000
AUDIT_TOLERANCE=0.0001

# ==================================================================
# HARDWARE CONFIGURATION (AW1)
# ==================================================================
CPU_CORES_TOTAL=20
CPU_CORES_RESERVED_OS=2
GPU_DEVICE=0  # NVIDIA device ID
GPU_MEMORY_FRACTION=0.9

# ==================================================================
# FEATURE FLAGS
# ==================================================================
ENABLE_GPU_ACCELERATION=true
ENABLE_DISTRIBUTED_TRACING=true
ENABLE_PROMETHEUS_METRICS=true
ENABLE_REAL_TIME_DASHBOARD=true

EOF
```

**Create actual .env file:**
```bash
cp .env.example .env

# Edit with your actual values
# Windows: notepad .env
# Linux: nano .env or vim .env
```

**⚠️ SECURITY WARNING:**
- **NEVER** commit .env to version control
- Each API key should be unique (35 different keys)
- Use strong passwords for Redis and PostgreSQL
- Rotate keys quarterly for security

---

## 4. INFRASTRUCTURE SERVICES SETUP

### 4.1 Redis (Semantic Bus)

**Create Redis configuration:**
```bash
cat > infrastructure/redis/redis.conf << 'EOF'
# Redis configuration for Holy Grail Refinery Semantic Bus

# Network
bind 0.0.0.0
port 6379
protected-mode yes
requirepass your-redis-password-from-env

# Persistence
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
dbfilename dump.rdb
dir /data

# Memory
maxmemory 4gb
maxmemory-policy allkeys-lru

# Pub/Sub
notify-keyspace-events KEA

# Performance
timeout 0
tcp-keepalive 300
tcp-backlog 511

# Logging
loglevel notice
logfile /var/log/redis/redis.log

# Slow log
slowlog-log-slower-than 10000
slowlog-max-len 128

# Latency monitoring
latency-monitor-threshold 100

EOF
```

**Create Redis Dockerfile:**
```dockerfile
# docker/infrastructure/Dockerfile.redis
FROM redis:7-alpine

# Install monitoring tools
RUN apk add --no-cache redis-tools

# Copy configuration
COPY infrastructure/redis/redis.conf /usr/local/etc/redis/redis.conf

# Create log directory
RUN mkdir -p /var/log/redis && chmod 755 /var/log/redis

# Expose ports
EXPOSE 6379

# Start Redis with custom config
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
```

---

### 4.2 PostgreSQL (Global State Graph)

**Create initialization SQL:**
```sql
-- infrastructure/postgres/init.sql

-- Create database (if using default postgres DB)
-- CREATE DATABASE holy_grail_refinery;

-- Connect to database
\c holy_grail_refinery;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Missions table
CREATE TABLE missions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 50,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    created_by VARCHAR(100) DEFAULT 'user',
    prd_document JSONB,
    clusters JSONB,
    final_binary_path VARCHAR(500),
    metadata JSONB
);

CREATE INDEX idx_missions_status ON missions(status);
CREATE INDEX idx_missions_created_at ON missions(created_at DESC);

-- LogicNodes table
CREATE TABLE logicnodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mission_id UUID REFERENCES missions(id) ON DELETE CASCADE,
    version VARCHAR(20) DEFAULT '1.0.0',
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    
    paradigm VARCHAR(50) NOT NULL,
    domain VARCHAR(100) NOT NULL,
    concept VARCHAR(100) NOT NULL,
    intent TEXT NOT NULL,
    
    inputs JSONB NOT NULL DEFAULT '[]',
    outputs JSONB NOT NULL DEFAULT '[]',
    preconditions JSONB DEFAULT '[]',
    postconditions JSONB DEFAULT '[]',
    side_effects JSONB DEFAULT '[]',
    
    source_language VARCHAR(50),
    source_reference TEXT,
    confidence DECIMAL(3,2) DEFAULT 0.99,
    
    audit_status VARCHAR(50) DEFAULT 'pending',
    audit_agent VARCHAR(100),
    audit_timestamp TIMESTAMP,
    equivalence_tests_passed INTEGER DEFAULT 0,
    equivalence_tests_total INTEGER DEFAULT 1000,
    
    metadata JSONB
);

CREATE INDEX idx_logicnodes_mission ON logicnodes(mission_id);
CREATE INDEX idx_logicnodes_domain ON logicnodes(domain);
CREATE INDEX idx_logicnodes_audit_status ON logicnodes(audit_status);
CREATE INDEX idx_logicnodes_created_by ON logicnodes(created_by);

-- Agent assignments table
CREATE TABLE agent_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mission_id UUID REFERENCES missions(id) ON DELETE CASCADE,
    agent_id VARCHAR(100) NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    task_description TEXT,
    status VARCHAR(50) DEFAULT 'assigned',
    assigned_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    input_logicnode_ids UUID[],
    output_logicnode_ids UUID[],
    metadata JSONB
);

CREATE INDEX idx_assignments_agent ON agent_assignments(agent_id);
CREATE INDEX idx_assignments_mission ON agent_assignments(mission_id);
CREATE INDEX idx_assignments_status ON agent_assignments(status);

-- LangGraph checkpoints table
CREATE TABLE langraph_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mission_id UUID REFERENCES missions(id) ON DELETE CASCADE,
    agent_id VARCHAR(100) NOT NULL,
    state_name VARCHAR(100) NOT NULL,
    state_data JSONB NOT NULL,
    parent_checkpoint_id UUID REFERENCES langraph_checkpoints(checkpoint_id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_checkpoints_mission ON langraph_checkpoints(mission_id);
CREATE INDEX idx_checkpoints_agent ON langraph_checkpoints(agent_id);
CREATE INDEX idx_checkpoints_created_at ON langraph_checkpoints(created_at DESC);

-- Events table (audit trail)
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID UNIQUE DEFAULT uuid_generate_v4(),
    mission_id UUID REFERENCES missions(id),
    agent_id VARCHAR(100),
    event_type VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    payload JSONB,
    trace_id VARCHAR(100)  -- For distributed tracing
);

CREATE INDEX idx_events_mission ON events(mission_id);
CREATE INDEX idx_events_agent ON events(agent_id);
CREATE INDEX idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX idx_events_trace_id ON events(trace_id);

-- Create views for common queries
CREATE VIEW active_missions AS
SELECT * FROM missions 
WHERE status IN ('pending', 'in_progress', 'verifying')
ORDER BY priority DESC, created_at ASC;

CREATE VIEW verified_logicnodes AS
SELECT * FROM logicnodes
WHERE audit_status = 'verified'
  AND equivalence_tests_passed = equivalence_tests_total;

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to missions table
CREATE TRIGGER update_missions_updated_at BEFORE UPDATE ON missions
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO refinery_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO refinery_admin;
```

**Create PostgreSQL Dockerfile:**
```dockerfile
# docker/infrastructure/Dockerfile.postgres
FROM postgres:15-alpine

# Install extensions
RUN apk add --no-cache postgresql-contrib

# Copy initialization script
COPY infrastructure/postgres/init.sql /docker-entrypoint-initdb.d/

# Expose port
EXPOSE 5432

# Use default entrypoint from base image
```

---

### 4.3 Qdrant (Vector Database for Knowledge Lake)

**Create Qdrant configuration:**
```yaml
# infrastructure/qdrant/config.yaml
service:
  host: 0.0.0.0
  port: 6333
  grpc_port: 6334

storage:
  storage_path: /qdrant/storage
  snapshots_path: /qdrant/snapshots
  on_disk_payload: true

log_level: INFO

# Performance tuning for AW1
telemetry_disabled: true
max_search_threads: 8
optimizer:
  default_segment_number: 0
  max_segment_size_kb: 20000
  memmap_threshold_kb: 50000
  indexing_threshold_kb: 20000
  flush_interval_sec: 5
  max_optimization_threads: 4
```

**Create Qdrant Dockerfile:**
```dockerfile
# docker/infrastructure/Dockerfile.qdrant
FROM qdrant/qdrant:v1.7.4

# Copy configuration
COPY infrastructure/qdrant/config.yaml /qdrant/config/production.yaml

# Create storage directories
RUN mkdir -p /qdrant/storage /qdrant/snapshots

# Expose ports
EXPOSE 6333 6334

# Start with custom config
CMD ["./qdrant", "--config-path", "/qdrant/config/production.yaml"]
```

---

### 4.4 Docker Compose for Infrastructure

**Create docker-compose.infrastructure.yml:**
```yaml
# docker-compose.infrastructure.yml
version: '3.8'

services:
  redis:
    build:
      context: .
      dockerfile: docker/infrastructure/Dockerfile.redis
    container_name: refinery-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
      - redis-logs:/var/log/redis
    environment:
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    networks:
      - refinery-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  postgres:
    build:
      context: .
      dockerfile: docker/infrastructure/Dockerfile.postgres
    container_name: refinery-postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    networks:
      - refinery-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 3s
      retries: 3

  qdrant:
    build:
      context: .
      dockerfile: docker/infrastructure/Dockerfile.qdrant
    container_name: refinery-qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant-storage:/qdrant/storage
      - qdrant-snapshots:/qdrant/snapshots
    networks:
      - refinery-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/"]
      interval: 10s
      timeout: 3s
      retries: 3

  git-server:
    image: gitea/gitea:1.21
    container_name: refinery-git-server
    ports:
      - "3001:3000"
      - "2222:22"
    volumes:
      - git-data:/data
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
    environment:
      - USER_UID=1000
      - USER_GID=1000
    networks:
      - refinery-net
    restart: unless-stopped

  mission-control:
    build:
      context: ./mission-control
      dockerfile: Dockerfile
    container_name: refinery-mission-control
    ports:
      - "3000:3000"
    environment:
      - NEXTAUTH_SECRET=${NEXTAUTH_SECRET}
      - NEXTAUTH_URL=${NEXTAUTH_URL}
      - REDIS_HOST=redis
      - POSTGRES_HOST=postgres
    depends_on:
      - redis
      - postgres
    networks:
      - refinery-net
    restart: unless-stopped

networks:
  refinery-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

volumes:
  redis-data:
  redis-logs:
  postgres-data:
  qdrant-storage:
  qdrant-snapshots:
  git-data:
```

**Start infrastructure services:**
```bash
# Build and start all infrastructure
docker compose -f docker-compose.infrastructure.yml up -d

# View logs
docker compose -f docker-compose.infrastructure.yml logs -f

# Check status
docker compose -f docker-compose.infrastructure.yml ps
```

**Expected output:**
```
NAME                      STATUS    PORTS
refinery-redis            Up        6379/tcp
refinery-postgres         Up        5432/tcp
refinery-qdrant           Up        6333/tcp, 6334/tcp
refinery-git-server       Up        3001/tcp, 2222/tcp
refinery-mission-control  Up        3000/tcp
```

---

*(Continuing with sections 5-10 covering: Infrastructure Testing, Agent Development, Build System, Verification, Troubleshooting, and Next Steps...)*

**Document 16 is 25KB and continues for full implementation details.**

---

## DOCUMENT METADATA

**Document ID:** 16  
**Version:** 1.0  
**Created:** February 2026  
**Owner:** DevOps Lead

---

*End of Development Environment Setup - Part 1 of 2*
