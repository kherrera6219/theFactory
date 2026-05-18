# DOCKER CONTAINERIZATION GUIDE

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Container Architecture for 35-Agent System

**Version:** 1.0  
**Date:** February 2026  
**Status:** Complete Specification  
**Document Owner:** Infrastructure Lead

---

## EXECUTIVE SUMMARY

Comprehensive guide to Docker containerization strategy for the Holy Grail Refinery. Covers resource allocation, networking, security, and orchestration for 40 total containers (35 agents + 5 infrastructure).

**Key Specifications:**
- **Total Containers:** 40 (35 agents + 5 infrastructure services)
- **Resource Allocation:** 28GB RAM, 18 CPU cores
- **Network Architecture:** Internal bridge network with Semantic Bus
- **Storage Strategy:** Named volumes for persistence
- **Orchestration:** Docker Compose with health checks

---

## 1. CONTAINER ARCHITECTURE OVERVIEW

### 1.1 Container Distribution

**Agent Containers (35 total):**
```
Executive Tier (2):
├── PM Agent:        1.0 GB RAM, 0.5 CPU
└── CEO Agent:       2.0 GB RAM, 1.0 CPU

Support Ring (9):
├── IS Agent:        2.0 GB RAM, 0.5 CPU (Knowledge Lake queries)
├── API Broker:      1.0 GB RAM, 0.5 CPU
├── Accountant:      1.0 GB RAM, 0.5 CPU
├── Security:        1.5 GB RAM, 0.75 CPU
├── Compliance:      1.0 GB RAM, 0.5 CPU
├── Data Architect:  1.5 GB RAM, 0.75 CPU
├── Diplomat:        1.0 GB RAM, 0.5 CPU
├── SRE:             1.5 GB RAM, 0.75 CPU
└── AI/Data:         2.0 GB RAM, 1.0 CPU

Pod A - Dynamic (6):
├── Manager:         1.5 GB RAM, 0.75 CPU
├── Audit:           2.0 GB RAM, 1.0 CPU (compute-intensive)
├── Python:          1.5 GB RAM, 0.75 CPU
├── JavaScript:      1.5 GB RAM, 0.75 CPU
├── Ruby:            1.5 GB RAM, 0.75 CPU
└── PHP:             1.5 GB RAM, 0.75 CPU

Pod B - Systems (6):
├── Manager:         1.5 GB RAM, 0.75 CPU
├── Audit:           2.0 GB RAM, 1.0 CPU
├── C:               1.5 GB RAM, 0.75 CPU
├── C++:             1.5 GB RAM, 0.75 CPU
├── Rust:            1.5 GB RAM, 0.75 CPU
└── Zig:             1.5 GB RAM, 0.75 CPU

Pod C - Enterprise (6):
├── Manager:         1.5 GB RAM, 0.75 CPU
├── Audit:           2.0 GB RAM, 1.0 CPU
├── Java:            2.0 GB RAM, 1.0 CPU (JVM overhead)
├── C#:              2.0 GB RAM, 1.0 CPU (.NET runtime)
├── Scala:           2.0 GB RAM, 1.0 CPU
└── Kotlin:          2.0 GB RAM, 1.0 CPU

Pod D - Mathematical (6):
├── Manager:         1.5 GB RAM, 0.75 CPU
├── Audit:           2.0 GB RAM, 1.0 CPU
├── MATLAB:          2.0 GB RAM, 1.0 CPU
├── R:               1.5 GB RAM, 0.75 CPU
├── Julia:           2.0 GB RAM, 1.0 CPU
└── Mathematica:     2.0 GB RAM, 1.0 CPU

Total Agents: 60 GB RAM, 30 CPU cores (actual limit: 28GB, 18 cores)
```

**Infrastructure Containers (5 total):**
```
├── Redis:           4.0 GB RAM, 2.0 CPU
├── PostgreSQL:      4.0 GB RAM, 1.0 CPU
├── Qdrant:          8.0 GB RAM, 2.0 CPU
├── Git Server:      2.0 GB RAM, 0.5 CPU
└── Mission Control: 2.0 GB RAM, 1.0 CPU

Total Infrastructure: 20 GB RAM, 6.5 CPU cores
```

**System Totals:**
- **RAM:** 28 GB allocated (4 GB reserved for OS)
- **CPU:** 18 cores allocated (2 cores reserved for OS)
- **Storage:** ~150 GB for Docker images

---

## 2. BASE DOCKER IMAGES

### 2.1 Python Agent Base Image

**Dockerfile.python-agent-base:**
```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-base.txt .
RUN pip install --no-cache-dir -r requirements-base.txt

# Create non-root user
RUN useradd -m -u 1000 agent && \
    chown -R agent:agent /app

USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command (override in child images)
CMD ["python", "agent.py"]
```

**requirements-base.txt:**
```txt
anthropic>=0.18.0
redis>=5.0.0
psycopg2-binary>=2.9.9
pydantic>=2.5.0
langgraph>=0.0.30
langchain>=0.1.0
python-dotenv>=1.0.0
aioredis>=2.0.1
asyncpg>=0.29.0
fastapi>=0.109.0
uvicorn>=0.27.0
prometheus-client>=0.19.0
opentelemetry-api>=1.22.0
opentelemetry-sdk>=1.22.0
```

**Build base image:**
```bash
docker build -t refinery/python-agent-base:latest -f docker/Dockerfile.python-agent-base .
```

---

### 2.2 Specific Agent Image Example

**Dockerfile for Python Specialist:**
```dockerfile
FROM refinery/python-agent-base:latest

# Copy agent code
COPY agents/pods/pod_a/python_specialist/ /app/

# Install agent-specific dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose health check port
EXPOSE 8080

# Run agent
CMD ["python", "python_specialist_agent.py"]
```

---

## 3. DOCKER COMPOSE ORCHESTRATION

### 3.1 Main docker-compose.yml

**Complete orchestration file:**
```yaml
version: '3.8'

services:
  # ============================================
  # INFRASTRUCTURE SERVICES
  # ============================================
  
  redis:
    image: redis:7-alpine
    container_name: refinery-redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - refinery-net
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  postgres:
    image: postgres:15-alpine
    container_name: refinery-postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./infrastructure/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    networks:
      - refinery-net
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 4G
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:v1.7.4
    container_name: refinery-qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant-storage:/qdrant/storage
    networks:
      - refinery-net
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 8G
    restart: unless-stopped

  # ============================================
  # EXECUTIVE TIER
  # ============================================
  
  pm-agent:
    build:
      context: .
      dockerfile: docker/agents/Dockerfile.pm-agent
    container_name: refinery-pm-agent
    environment:
      - AGENT_ID=PM-AGENT-001
      - API_KEY=${PM_API_KEY}
      - REDIS_HOST=redis
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - POSTGRES_HOST=postgres
    depends_on:
      - redis
      - postgres
    networks:
      - refinery-net
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 1G
    restart: unless-stopped

  ceo-agent:
    build:
      context: .
      dockerfile: docker/agents/Dockerfile.ceo-agent
    container_name: refinery-ceo-agent
    environment:
      - AGENT_ID=CEO-AGENT-001
      - API_KEY=${CEO_API_KEY}
      - REDIS_HOST=redis
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - POSTGRES_HOST=postgres
    depends_on:
      - redis
      - postgres
    networks:
      - refinery-net
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
    restart: unless-stopped

  # ============================================
  # POD A - DYNAMIC LANGUAGES
  # ============================================
  
  pod-a-manager:
    build:
      context: .
      dockerfile: docker/agents/Dockerfile.pod-a-manager
    container_name: refinery-pod-a-manager
    environment:
      - AGENT_ID=MANAGER-POD-A-001
      - API_KEY=${MANAGER_POD_A_API_KEY}
      - REDIS_HOST=redis
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    depends_on:
      - redis
    networks:
      - refinery-net
    deploy:
      resources:
        limits:
          cpus: '0.75'
          memory: 1.5G
    restart: unless-stopped

  python-specialist:
    build:
      context: .
      dockerfile: docker/agents/Dockerfile.python-specialist
    container_name: refinery-python-specialist
    environment:
      - AGENT_ID=AGENT-PY-001
      - API_KEY=${PYTHON_SPECIALIST_API_KEY}
      - REDIS_HOST=redis
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - QDRANT_HOST=qdrant
    depends_on:
      - redis
      - qdrant
    networks:
      - refinery-net
    deploy:
      resources:
        limits:
          cpus: '0.75'
          memory: 1.5G
    restart: unless-stopped

  # (Repeat similar blocks for remaining 33 agents...)
  
# ============================================
# NETWORKS
# ============================================
networks:
  refinery-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
    driver_opts:
      com.docker.network.bridge.name: refinery-bridge

# ============================================
# VOLUMES
# ============================================
volumes:
  redis-data:
    driver: local
  postgres-data:
    driver: local
  qdrant-storage:
    driver: local
  git-data:
    driver: local
```

---

## 4. NETWORKING ARCHITECTURE

### 4.1 Internal Bridge Network

**Network Configuration:**
```
Network Name: refinery-net
Driver: bridge
Subnet: 172.20.0.0/16
Gateway: 172.20.0.1

IP Allocation:
├── Infrastructure: 172.20.0.2 - 172.20.0.10
│   ├── Redis:           172.20.0.2
│   ├── PostgreSQL:      172.20.0.3
│   ├── Qdrant:          172.20.0.4
│   ├── Git Server:      172.20.0.5
│   └── Mission Control: 172.20.0.6
│
├── Executive: 172.20.1.1 - 172.20.1.10
│   ├── PM Agent:        172.20.1.1
│   └── CEO Agent:       172.20.1.2
│
├── Support: 172.20.2.1 - 172.20.2.20
│   └── (9 support agents)
│
├── Pod A: 172.20.3.1 - 172.20.3.10
├── Pod B: 172.20.4.1 - 172.20.4.10
├── Pod C: 172.20.5.1 - 172.20.5.10
└── Pod D: 172.20.6.1 - 172.20.6.10
```

**DNS Resolution:**
- Containers resolve by service name: `ping redis` works
- No external DNS required for inter-container communication
- External access only through exposed ports

---

## 5. RESOURCE MANAGEMENT

### 5.1 CPU Allocation Strategy

**Docker Compose CPU Limits:**
```yaml
deploy:
  resources:
    limits:
      cpus: '0.75'  # Maximum CPU cores
    reservations:
      cpus: '0.25'  # Guaranteed minimum
```

**CPU Shares (alternative approach):**
```yaml
cpu_shares: 1024  # Relative weight (default is 1024)
```

**Performance vs Management Agents:**
- **Management agents** (PM, CEO, Managers): 0.5-1.0 CPU
- **Specialist agents** (language-specific): 0.75 CPU
- **Audit agents** (compute-heavy): 1.0 CPU
- **Infrastructure services**: 1.0-2.0 CPU

---

### 5.2 Memory Allocation

**Hard vs Soft Limits:**
```yaml
deploy:
  resources:
    limits:
      memory: 2G      # Hard limit (OOM kill if exceeded)
    reservations:
      memory: 1G      # Soft limit (guaranteed)
```

**Memory Swap:**
```yaml
mem_swappiness: 0  # Disable swap (prefer OOM kill)
```

---

## 6. HEALTH CHECKS

### 6.1 Health Check Configuration

**HTTP Health Check (agents):**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  start_period: 40s
  retries: 3
```

**Redis Health Check:**
```yaml
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
  interval: 10s
  timeout: 3s
  retries: 3
```

**PostgreSQL Health Check:**
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U $POSTGRES_USER"]
  interval: 10s
  timeout: 3s
  retries: 3
```

---

## 7. LOGGING STRATEGY

### 7.1 Logging Driver Configuration

**JSON File Driver (default):**
```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
    labels: "agent_id,pod"
    tag: "{{.Name}}/{{.ID}}"
```

**Centralized Logging (production):**
```yaml
logging:
  driver: fluentd
  options:
    fluentd-address: localhost:24224
    tag: refinery.{{.Name}}
```

---

## 8. SECURITY CONFIGURATION

### 8.1 Non-Root Users

**All agents run as non-root:**
```dockerfile
RUN useradd -m -u 1000 agent
USER agent
```

### 8.2 Secrets Management

**Docker Secrets (Swarm mode):**
```yaml
secrets:
  redis_password:
    external: true
  postgres_password:
    external: true

services:
  redis:
    secrets:
      - redis_password
```

**Environment Variables (Compose mode):**
```yaml
services:
  agent:
    env_file:
      - .env
    environment:
      - API_KEY=${AGENT_API_KEY}
```

### 8.3 Network Isolation

**No direct internet access for agents:**
```yaml
networks:
  refinery-net:
    internal: true  # No external connectivity
  
  public:
    internal: false  # For Mission Control UI only
```

---

## 9. VOLUME MANAGEMENT

### 9.1 Named Volumes

**Persistent Data:**
```yaml
volumes:
  redis-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/refinery/redis
  
  postgres-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/refinery/postgres
```

### 9.2 Bind Mounts (Development)

**Mount local code for hot reload:**
```yaml
volumes:
  - ./agents/pods/pod_a/python_specialist:/app:ro
```

---

## 10. BUILD OPTIMIZATION

### 10.1 Multi-Stage Builds

**Example:**
```dockerfile
# Build stage
FROM python:3.11 as builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "agent.py"]
```

### 10.2 Layer Caching

**Optimize Dockerfile order:**
```dockerfile
# 1. Install system packages (rarely changes)
RUN apt-get update && apt-get install -y curl

# 2. Install Python dependencies (changes occasionally)
COPY requirements.txt .
RUN pip install -r requirements.txt

# 3. Copy application code (changes frequently)
COPY . .
```

### 10.3 BuildKit

**Enable BuildKit:**
```bash
export DOCKER_BUILDKIT=1
docker compose build
```

---

## 11. OPERATIONS

### 11.1 Starting the System

**Start all services:**
```bash
docker compose up -d
```

**Start specific services:**
```bash
docker compose up -d redis postgres qdrant
docker compose up -d pm-agent ceo-agent
```

**Watch logs:**
```bash
docker compose logs -f
docker compose logs -f python-specialist
```

---

### 11.2 Stopping the System

**Graceful shutdown:**
```bash
docker compose down
```

**Remove volumes (DANGER - data loss):**
```bash
docker compose down -v
```

---

### 11.3 Scaling Agents

**Scale specific agent (if stateless):**
```bash
docker compose up -d --scale python-specialist=2
```

**Note:** Most agents are stateful and should NOT be scaled without additional coordination.

---

## 12. MONITORING

### 12.1 Docker Stats

**Real-time resource usage:**
```bash
docker stats
```

**Specific container:**
```bash
docker stats refinery-python-specialist
```

---

### 12.2 Prometheus Metrics

**Expose metrics endpoint:**
```python
from prometheus_client import start_http_server, Counter, Gauge

requests_total = Counter('agent_requests_total', 'Total requests')
memory_usage = Gauge('agent_memory_bytes', 'Memory usage in bytes')

start_http_server(9090)
```

**Scrape config:**
```yaml
scrape_configs:
  - job_name: 'refinery-agents'
    static_configs:
      - targets:
        - 'python-specialist:9090'
        - 'javascript-specialist:9090'
```

---

## 13. TROUBLESHOOTING

### 13.1 Container Won't Start

**Check logs:**
```bash
docker logs refinery-python-specialist
```

**Inspect container:**
```bash
docker inspect refinery-python-specialist
```

**Common issues:**
- Missing environment variables
- Port conflicts
- Network connectivity issues
- Resource limits too restrictive

---

### 13.2 Out of Memory

**Check memory usage:**
```bash
docker stats --no-stream
```

**Increase memory limit:**
```yaml
deploy:
  resources:
    limits:
      memory: 3G  # Increased from 2G
```

---

## DOCUMENT METADATA

**Document ID:** 17  
**Version:** 1.0  
**Created:** February 2026  
**Owner:** Infrastructure Lead

---

*End of Docker Containerization Guide*
