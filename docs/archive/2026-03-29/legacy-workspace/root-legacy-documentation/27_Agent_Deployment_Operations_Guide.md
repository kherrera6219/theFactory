# DOCUMENT 27: AGENT DEPLOYMENT & OPERATIONS GUIDE
## Holy Grail Refinery - Development Specifications

**Document ID:** 27  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive deployment and operational procedures** for all 35 agents in the Holy Grail Refinery system. It covers initial deployment, configuration, scaling, maintenance, troubleshooting, and day-to-day operations on the local AW1 hardware platform.

**Deployment Architecture:**
- **Platform:** Docker containers on Ubuntu 24.04 (AW1 hardware)
- **Orchestration:** Docker Compose with service dependencies
- **Configuration:** Environment-based with Vault integration
- **Scaling:** Vertical (resource allocation) and horizontal (replica count)
- **Monitoring:** Integrated health checks and metrics

**Operational Objectives:**
- 🚀 Zero-downtime deployments
- 📊 99.999% agent uptime
- ⚡ < 5 minute recovery time
- 🔧 Automated health recovery
- 📈 Dynamic resource allocation

---

## TABLE OF CONTENTS

1. [Prerequisites](#1-prerequisites)
2. [Initial System Deployment](#2-initial-system-deployment)
3. [Agent Configuration](#3-agent-configuration)
4. [Service Management](#4-service-management)
5. [Scaling Operations](#5-scaling-operations)
6. [Health Monitoring](#6-health-monitoring)
7. [Troubleshooting Guide](#7-troubleshooting-guide)
8. [Maintenance Procedures](#8-maintenance-procedures)
9. [Backup & Recovery](#9-backup--recovery)
10. [Operational Playbooks](#10-operational-playbooks)

---

## 1. PREREQUISITES

### 1.1 Hardware Requirements (AW1)

**Verified System Specifications:**
```
CPU: Intel Core i7-14700F (20 cores, 28 threads)
RAM: 32GB DDR5-5600
GPU: NVIDIA RTX 4060 Ti (16GB VRAM)
Storage: 1TB NVMe SSD
Network: Gigabit Ethernet
OS: Ubuntu 24.04 LTS
```

**Resource Allocation:**
```
API Gateway:           2 CPUs, 2GB RAM
35 Agents:            20 CPUs, 20GB RAM (avg 0.6 CPU, 571MB per agent)
PostgreSQL:            4 CPUs, 4GB RAM
Redis:                 2 CPUs, 2GB RAM
Monitoring Stack:      2 CPUs, 4GB RAM
Reserve:               4 CPUs, 2GB RAM
```

### 1.2 Software Prerequisites

**File:** `scripts/prereq_check.sh`

```bash
#!/bin/bash
set -e

echo "Checking prerequisites for Holy Grail Refinery..."

# Check OS
if [ ! -f /etc/os-release ]; then
    echo "❌ Cannot detect OS"
    exit 1
fi

source /etc/os-release
if [ "$ID" != "ubuntu" ] || [ "${VERSION_ID}" != "24.04" ]; then
    echo "⚠️  Warning: Recommended OS is Ubuntu 24.04"
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed"
    echo "Install: curl -fsSL https://get.docker.com | sh"
    exit 1
fi
echo "✓ Docker $(docker --version)"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not installed"
    exit 1
fi
echo "✓ Docker Compose $(docker-compose --version)"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not installed"
    exit 1
fi
echo "✓ Python $(python3 --version)"

# Check disk space
AVAILABLE=$(df -BG / | awk 'NR==2 {print $4}' | sed 's/G//')
if [ "$AVAILABLE" -lt 100 ]; then
    echo "⚠️  Warning: Low disk space (${AVAILABLE}GB available, 100GB+ recommended)"
fi
echo "✓ Disk space: ${AVAILABLE}GB available"

# Check RAM
TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
if [ "$TOTAL_RAM" -lt 28 ]; then
    echo "⚠️  Warning: Low RAM (${TOTAL_RAM}GB, 32GB recommended)"
fi
echo "✓ RAM: ${TOTAL_RAM}GB"

# Check CPU cores
CPU_CORES=$(nproc)
if [ "$CPU_CORES" -lt 16 ]; then
    echo "⚠️  Warning: Low CPU count (${CPU_CORES} cores, 20+ recommended)"
fi
echo "✓ CPU: ${CPU_CORES} cores"

echo ""
echo "✓ All prerequisites met"
```

### 1.3 Network Configuration

**File:** `config/network_setup.sh`

```bash
#!/bin/bash
# Configure networking for Holy Grail Refinery

# Create Docker networks
docker network create --driver bridge \
    --subnet=172.20.0.0/16 \
    --gateway=172.20.0.1 \
    hgr-network

# Configure DNS
echo "nameserver 8.8.8.8" >> /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf

# Configure hosts file
cat >> /etc/hosts <<EOF
127.0.0.1 api.hgr.local
127.0.0.1 grafana.hgr.local
127.0.0.1 prometheus.hgr.local
EOF

echo "✓ Network configuration complete"
```

---

## 2. INITIAL SYSTEM DEPLOYMENT

### 2.1 Complete Deployment Script

**File:** `scripts/deploy.sh`

```bash
#!/bin/bash
set -e

echo "=========================================="
echo "Holy Grail Refinery - Full Deployment"
echo "=========================================="

# Configuration
export HGR_VERSION="1.0.0"
export HGR_ENV="production"
export HGR_ROOT="/opt/holy-grail-refinery"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Prerequisites
echo -e "${BLUE}Step 1/8: Checking prerequisites...${NC}"
./scripts/prereq_check.sh

# Step 2: Environment setup
echo -e "${BLUE}Step 2/8: Setting up environment...${NC}"
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    
    # Generate secrets
    echo "Generating secrets..."
    JWT_SECRET=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -base64 32)
    REDIS_PASSWORD=$(openssl rand -base64 32)
    
    # Update .env
    sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT_SECRET/" .env
    sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$DB_PASSWORD/" .env
    sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=$REDIS_PASSWORD/" .env
fi
echo -e "${GREEN}✓ Environment configured${NC}"

# Step 3: Create directories
echo -e "${BLUE}Step 3/8: Creating directories...${NC}"
mkdir -p data/{postgres,redis,prometheus,grafana,loki}
mkdir -p logs/{agents,api,system}
mkdir -p backups
mkdir -p config/agents
echo -e "${GREEN}✓ Directories created${NC}"

# Step 4: Pull Docker images
echo -e "${BLUE}Step 4/8: Pulling Docker images...${NC}"
docker-compose pull
echo -e "${GREEN}✓ Images pulled${NC}"

# Step 5: Initialize databases
echo -e "${BLUE}Step 5/8: Initializing databases...${NC}"
docker-compose up -d postgres redis
sleep 10

# Run database migrations
docker-compose exec -T postgres psql -U hgr_admin -d knowledge_lake < database/migrations/init.sql
echo -e "${GREEN}✓ Databases initialized${NC}"

# Step 6: Start infrastructure services
echo -e "${BLUE}Step 6/8: Starting infrastructure...${NC}"
docker-compose up -d postgres redis prometheus grafana loki
sleep 20
echo -e "${GREEN}✓ Infrastructure started${NC}"

# Step 7: Start API and agents
echo -e "${BLUE}Step 7/8: Starting agents...${NC}"

# Start API
docker-compose up -d api
sleep 10

# Start managers first
echo "Starting manager agents..."
docker-compose up -d \
    agent-manager-pod-a \
    agent-manager-pod-b \
    agent-manager-pod-c \
    agent-manager-pod-d
sleep 15

# Start specialist agents
echo "Starting specialist agents..."
docker-compose up -d \
    $(docker-compose config --services | grep "agent-" | grep -v "manager")
sleep 20

# Start support agents
echo "Starting support agents..."
docker-compose up -d \
    agent-audit-sec \
    agent-audit-perf \
    agent-audit-correctness \
    agent-knowledge \
    agent-devops
sleep 10

echo -e "${GREEN}✓ All agents started${NC}"

# Step 8: Health check
echo -e "${BLUE}Step 8/8: Running health checks...${NC}"
./scripts/health_check.sh

# Deployment summary
echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Services:"
echo "  API:        http://localhost:8000"
echo "  Grafana:    http://localhost:3000"
echo "  Prometheus: http://localhost:9090"
echo ""
echo "Next steps:"
echo "  1. View logs:     docker-compose logs -f"
echo "  2. Check status:  docker-compose ps"
echo "  3. Run tests:     ./scripts/integration_test.sh"
echo ""
```

### 2.2 Docker Compose Master File

**File:** `docker-compose.yml`

```yaml
version: '3.8'

services:
  # =========================================================================
  # INFRASTRUCTURE
  # =========================================================================
  postgres:
    image: postgres:16-alpine
    container_name: hgr-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_MULTIPLE_DATABASES: knowledge_lake,state_graph,logicnode_registry,traceability_ledger,model_store
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./scripts/init-databases.sh:/docker-entrypoint-initdb.d/init-databases.sh
    ports:
      - "5432:5432"
    networks:
      - hgr-network
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 4G

  redis:
    image: redis:7.2-alpine
    container_name: hgr-redis
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis-data:/data
    ports:
      - "6379:6379"
    networks:
      - hgr-network
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G

  # =========================================================================
  # API GATEWAY
  # =========================================================================
  api:
    image: hgr-api:${HGR_VERSION:-latest}
    container_name: hgr-api
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres/knowledge_lake
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    networks:
      - hgr-network
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G

  # =========================================================================
  # POD A AGENTS (Dynamic Languages)
  # =========================================================================
  agent-manager-pod-a:
    image: hgr-agent-manager:${HGR_VERSION:-latest}
    container_name: hgr-agent-manager-pod-a
    restart: unless-stopped
    environment:
      - AGENT_ID=MANAGER-POD-A-001
      - POD=A
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
    depends_on:
      - redis
    networks:
      - hgr-network
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G

  agent-python:
    image: hgr-agent-python:${HGR_VERSION:-latest}
    container_name: hgr-agent-python
    restart: unless-stopped
    environment:
      - AGENT_ID=AGENT-PY-001
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
    depends_on:
      - redis
      - agent-manager-pod-a
    networks:
      - hgr-network
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  agent-javascript:
    image: hgr-agent-javascript:${HGR_VERSION:-latest}
    container_name: hgr-agent-javascript
    restart: unless-stopped
    environment:
      - AGENT_ID=AGENT-JS-001
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
    depends_on:
      - redis
      - agent-manager-pod-a
    networks:
      - hgr-network
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  # ... (Similar definitions for remaining 31 agents)

  # =========================================================================
  # MONITORING
  # =========================================================================
  prometheus:
    image: prom/prometheus:latest
    container_name: hgr-prometheus
    restart: unless-stopped
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - hgr-network

  grafana:
    image: grafana/grafana:latest
    container_name: hgr-grafana
    restart: unless-stopped
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"
    networks:
      - hgr-network

volumes:
  postgres-data:
  redis-data:
  prometheus-data:
  grafana-data:

networks:
  hgr-network:
    driver: bridge
```

---

## 3. AGENT CONFIGURATION

### 3.1 Agent Configuration Template

**File:** `config/agents/agent-template.yaml`

```yaml
# Agent configuration template
agent:
  id: AGENT-XX-001
  name: "Agent Name"
  tier: pod  # executive, support, pod
  pod: A     # A, B, C, D (null for non-pod agents)

# Capabilities
capabilities:
  languages:
    - python
  domains:
    - control_flow
    - data_structures

# Resource limits
resources:
  cpu_limit: "0.5"
  memory_limit: "512M"
  timeout_seconds: 300

# Communication
protocols:
  - alpha
  - beta
  - omega

# Features
features:
  requires_audit: true
  max_concurrent_tasks: 5
  enable_caching: true

# Logging
logging:
  level: INFO
  structured: true
  output: /var/log/agents/${AGENT_ID}.log
```

### 3.2 Agent Configuration Management

**File:** `scripts/configure_agent.py`

```python
#!/usr/bin/env python3
"""
Agent configuration management tool
"""

import yaml
import os
from typing import Dict, Any


class AgentConfigurator:
    """Manage agent configurations"""
    
    def __init__(self, config_dir: str = "config/agents"):
        self.config_dir = config_dir
    
    def load_config(self, agent_id: str) -> Dict[str, Any]:
        """Load agent configuration"""
        config_file = f"{self.config_dir}/{agent_id}.yaml"
        
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Config not found: {config_file}")
        
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    
    def save_config(self, agent_id: str, config: Dict[str, Any]):
        """Save agent configuration"""
        config_file = f"{self.config_dir}/{agent_id}.yaml"
        
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
    
    def generate_env_file(self, agent_id: str) -> str:
        """
        Generate .env file for agent from config
        
        Returns:
            Path to generated .env file
        """
        config = self.load_config(agent_id)
        
        env_lines = [
            f"AGENT_ID={agent_id}",
            f"AGENT_NAME={config['agent']['name']}",
            f"AGENT_TIER={config['agent']['tier']}",
            f"AGENT_POD={config['agent'].get('pod', '')}",
            f"CPU_LIMIT={config['resources']['cpu_limit']}",
            f"MEMORY_LIMIT={config['resources']['memory_limit']}",
            f"LOG_LEVEL={config['logging']['level']}"
        ]
        
        env_file = f".env.{agent_id}"
        with open(env_file, 'w') as f:
            f.write('\n'.join(env_lines))
        
        return env_file
    
    def validate_config(self, agent_id: str) -> bool:
        """Validate agent configuration"""
        try:
            config = self.load_config(agent_id)
            
            # Required fields
            required = ['agent', 'capabilities', 'resources', 'protocols']
            for field in required:
                if field not in config:
                    print(f"❌ Missing required field: {field}")
                    return False
            
            # Validate resource limits
            cpu = float(config['resources']['cpu_limit'])
            if cpu < 0.1 or cpu > 4.0:
                print(f"❌ Invalid CPU limit: {cpu}")
                return False
            
            print(f"✓ Configuration valid for {agent_id}")
            return True
            
        except Exception as e:
            print(f"❌ Validation error: {e}")
            return False


# CLI usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: configure_agent.py <command> <agent_id>")
        print("Commands: validate, generate-env")
        sys.exit(1)
    
    command = sys.argv[1]
    agent_id = sys.argv[2]
    
    configurator = AgentConfigurator()
    
    if command == "validate":
        configurator.validate_config(agent_id)
    elif command == "generate-env":
        env_file = configurator.generate_env_file(agent_id)
        print(f"Generated: {env_file}")
```

---

## 4. SERVICE MANAGEMENT

### 4.1 Service Control Script

**File:** `scripts/service_control.sh`

```bash
#!/bin/bash
# Service management for Holy Grail Refinery

case $1 in
    start)
        echo "Starting Holy Grail Refinery..."
        docker-compose up -d
        ;;
    
    stop)
        echo "Stopping Holy Grail Refinery..."
        docker-compose down
        ;;
    
    restart)
        echo "Restarting Holy Grail Refinery..."
        docker-compose restart
        ;;
    
    status)
        echo "Service Status:"
        docker-compose ps
        ;;
    
    logs)
        AGENT=${2:-all}
        if [ "$AGENT" == "all" ]; then
            docker-compose logs -f
        else
            docker-compose logs -f $AGENT
        fi
        ;;
    
    restart-agent)
        AGENT=$2
        if [ -z "$AGENT" ]; then
            echo "Usage: $0 restart-agent <agent-name>"
            exit 1
        fi
        echo "Restarting $AGENT..."
        docker-compose restart $AGENT
        ;;
    
    scale)
        SERVICE=$2
        REPLICAS=$3
        if [ -z "$SERVICE" ] || [ -z "$REPLICAS" ]; then
            echo "Usage: $0 scale <service> <replicas>"
            exit 1
        fi
        echo "Scaling $SERVICE to $REPLICAS replicas..."
        docker-compose up -d --scale $SERVICE=$REPLICAS
        ;;
    
    health)
        echo "Health Check:"
        ./scripts/health_check.sh
        ;;
    
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|restart-agent|scale|health}"
        exit 1
        ;;
esac
```

### 4.2 Health Check Script

**File:** `scripts/health_check.sh`

```bash
#!/bin/bash
# Comprehensive health check for all services

echo "Running health checks..."

FAILED=0

# Check infrastructure
check_service() {
    SERVICE=$1
    PORT=$2
    
    if curl -f http://localhost:$PORT/health > /dev/null 2>&1; then
        echo "✓ $SERVICE healthy"
    else
        echo "❌ $SERVICE unhealthy"
        FAILED=$((FAILED + 1))
    fi
}

# Check API
check_service "API" "8000"

# Check agents
for i in {1..35}; do
    AGENT_ID=$(printf "AGENT-%02d" $i)
    CONTAINER="hgr-agent-$(echo $AGENT_ID | tr '[:upper:]' '[:lower:]')"
    
    if docker ps --format "{{.Names}}" | grep -q $CONTAINER; then
        STATUS=$(docker inspect --format='{{.State.Health.Status}}' $CONTAINER 2>/dev/null)
        if [ "$STATUS" == "healthy" ]; then
            echo "✓ $AGENT_ID healthy"
        else
            echo "❌ $AGENT_ID unhealthy ($STATUS)"
            FAILED=$((FAILED + 1))
        fi
    else
        echo "❌ $AGENT_ID not running"
        FAILED=$((FAILED + 1))
    fi
done

# Summary
echo ""
if [ $FAILED -eq 0 ]; then
    echo "✓ All health checks passed"
    exit 0
else
    echo "❌ $FAILED service(s) failed health checks"
    exit 1
fi
```

---

## 5. SCALING OPERATIONS

### 5.1 Vertical Scaling (Resource Adjustment)

**File:** `scripts/scale_resources.sh`

```bash
#!/bin/bash
# Adjust resource allocation for agents

AGENT=$1
NEW_CPU=$2
NEW_MEMORY=$3

if [ -z "$AGENT" ] || [ -z "$NEW_CPU" ] || [ -z "$NEW_MEMORY" ]; then
    echo "Usage: $0 <agent-name> <cpu> <memory>"
    echo "Example: $0 agent-python 1.0 1G"
    exit 1
fi

# Update docker-compose.yml
sed -i "/$AGENT:/,/deploy:/s/cpus: '.*'/cpus: '$NEW_CPU'/" docker-compose.yml
sed -i "/$AGENT:/,/memory:/s/memory: .*/memory: $NEW_MEMORY/" docker-compose.yml

# Restart agent with new limits
docker-compose up -d --no-deps $AGENT

echo "✓ $AGENT scaled to $NEW_CPU CPU, $NEW_MEMORY memory"
```

### 5.2 Horizontal Scaling (Replica Management)

**File:** `scripts/scale_replicas.sh`

```bash
#!/bin/bash
# Scale agent replicas

AGENT=$1
REPLICAS=$2

if [ -z "$AGENT" ] || [ -z "$REPLICAS" ]; then
    echo "Usage: $0 <agent-name> <replica-count>"
    exit 1
fi

# Scale service
docker-compose up -d --scale $AGENT=$REPLICAS --no-recreate

# Wait for health checks
sleep 30

# Verify
RUNNING=$(docker ps --filter "name=$AGENT" --format "{{.Names}}" | wc -l)
if [ $RUNNING -eq $REPLICAS ]; then
    echo "✓ $AGENT scaled to $REPLICAS replicas"
else
    echo "❌ Scaling failed. Running: $RUNNING, Expected: $REPLICAS"
    exit 1
fi
```

---

## 6. HEALTH MONITORING

### 6.1 Agent Health Monitor

**File:** `scripts/monitor_health.py`

```python
#!/usr/bin/env python3
"""
Continuous health monitoring for all agents
"""

import time
import docker
import requests
from typing import Dict, List


class HealthMonitor:
    """Monitor agent health continuously"""
    
    def __init__(self):
        self.client = docker.from_env()
        self.unhealthy_count = {}
    
    def check_agent_health(self, container_name: str) -> bool:
        """Check if agent container is healthy"""
        try:
            container = self.client.containers.get(container_name)
            
            # Check running state
            if container.status != 'running':
                return False
            
            # Check health status
            health = container.attrs['State'].get('Health', {})
            if health.get('Status') == 'healthy':
                return True
            
            return False
            
        except docker.errors.NotFound:
            return False
        except Exception as e:
            print(f"Error checking {container_name}: {e}")
            return False
    
    def auto_heal(self, container_name: str):
        """Automatically restart unhealthy container"""
        print(f"Auto-healing {container_name}...")
        
        try:
            container = self.client.containers.get(container_name)
            container.restart()
            print(f"✓ Restarted {container_name}")
        except Exception as e:
            print(f"❌ Failed to restart {container_name}: {e}")
    
    def monitor_loop(self, check_interval: int = 30):
        """
        Main monitoring loop
        
        Args:
            check_interval: Seconds between health checks
        """
        print("Starting health monitor...")
        
        while True:
            # Get all HGR containers
            containers = self.client.containers.list(
                filters={"name": "hgr-"}
            )
            
            for container in containers:
                name = container.name
                healthy = self.check_agent_health(name)
                
                if not healthy:
                    # Increment unhealthy count
                    self.unhealthy_count[name] = self.unhealthy_count.get(name, 0) + 1
                    
                    print(f"⚠️  {name} unhealthy ({self.unhealthy_count[name]} consecutive checks)")
                    
                    # Auto-heal after 3 consecutive failures
                    if self.unhealthy_count[name] >= 3:
                        self.auto_heal(name)
                        self.unhealthy_count[name] = 0
                else:
                    # Reset unhealthy count
                    if name in self.unhealthy_count:
                        del self.unhealthy_count[name]
            
            time.sleep(check_interval)


if __name__ == "__main__":
    monitor = HealthMonitor()
    monitor.monitor_loop()
```

---

## 7. TROUBLESHOOTING GUIDE

### 7.1 Common Issues

**Issue:** Agent not starting

```bash
# Check logs
docker-compose logs agent-python

# Common causes:
# 1. Configuration error
docker-compose config --services | grep agent-python

# 2. Resource limits
docker stats --no-stream agent-python

# 3. Network connectivity
docker exec agent-python ping redis

# Solution: Restart with fresh config
docker-compose stop agent-python
docker-compose up -d agent-python
```

**Issue:** High memory usage

```bash
# Identify memory hog
docker stats --no-stream | sort -k 4 -h

# Inspect specific agent
docker exec agent-python ps aux --sort=-%mem | head -n 10

# Solution: Increase memory limit or optimize code
./scripts/scale_resources.sh agent-python 1.0 1G
```

**Issue:** Agent not responding to messages

```bash
# Check Redis connection
docker exec agent-python redis-cli -h redis ping

# Check message queue
docker exec redis redis-cli KEYS "protocol:*"

# Check agent logs for errors
docker logs agent-python --tail 100

# Solution: Restart agent and check configuration
docker-compose restart agent-python
```

### 7.2 Diagnostic Commands

**File:** `scripts/diagnose.sh`

```bash
#!/bin/bash
# Diagnostic tool for troubleshooting

AGENT=$1

if [ -z "$AGENT" ]; then
    echo "Usage: $0 <agent-name>"
    exit 1
fi

echo "Diagnosing $AGENT..."
echo ""

# Check if running
echo "Status:"
docker ps --filter "name=$AGENT" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Check logs
echo "Recent logs (last 50 lines):"
docker logs $AGENT --tail 50
echo ""

# Check resource usage
echo "Resource usage:"
docker stats --no-stream $AGENT
echo ""

# Check health
echo "Health status:"
docker inspect --format='{{.State.Health.Status}}' $AGENT
echo ""

# Check environment
echo "Environment variables:"
docker exec $AGENT env | grep -E "(AGENT_|REDIS_|DATABASE_)" | sort
echo ""

# Check connectivity
echo "Connectivity:"
echo -n "Redis: "
docker exec $AGENT ping -c 1 redis > /dev/null 2>&1 && echo "OK" || echo "FAIL"
echo -n "Postgres: "
docker exec $AGENT ping -c 1 postgres > /dev/null 2>&1 && echo "OK" || echo "FAIL"
```

---

## 8. MAINTENANCE PROCEDURES

### 8.1 Routine Maintenance

**File:** `scripts/maintenance.sh`

```bash
#!/bin/bash
# Routine maintenance tasks

echo "Running maintenance..."

# 1. Clean up old containers
echo "Cleaning up stopped containers..."
docker container prune -f

# 2. Clean up old images
echo "Cleaning up unused images..."
docker image prune -a -f --filter "until=168h"  # Older than 7 days

# 3. Clean up old volumes
echo "Cleaning up unused volumes..."
docker volume prune -f

# 4. Vacuum databases
echo "Vacuuming databases..."
docker exec hgr-postgres vacuumdb -U hgr_admin -a -z

# 5. Clear Redis cache
echo "Clearing expired Redis keys..."
docker exec hgr-redis redis-cli --scan --pattern "cache:*" | xargs -L 1 docker exec hgr-redis redis-cli DEL

# 6. Rotate logs
echo "Rotating logs..."
find logs/ -name "*.log" -mtime +30 -exec gzip {} \;
find logs/ -name "*.log.gz" -mtime +90 -delete

# 7. Update agent metrics
echo "Updating agent metrics..."
curl -X POST http://localhost:8000/api/v1/system/update-metrics

echo "✓ Maintenance complete"
```

### 8.2 Update Procedure

**File:** `scripts/update.sh`

```bash
#!/bin/bash
# Update Holy Grail Refinery to new version

NEW_VERSION=$1

if [ -z "$NEW_VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

echo "Updating to version $NEW_VERSION..."

# 1. Backup current state
./scripts/backup.sh

# 2. Pull new images
docker-compose pull

# 3. Update configuration
export HGR_VERSION=$NEW_VERSION

# 4. Rolling update
for SERVICE in $(docker-compose config --services | grep "agent-"); do
    echo "Updating $SERVICE..."
    docker-compose up -d --no-deps $SERVICE
    sleep 10
done

# 5. Verify health
./scripts/health_check.sh

echo "✓ Update to $NEW_VERSION complete"
```

---

## 9. BACKUP & RECOVERY

### 9.1 Backup Script

**File:** `scripts/backup.sh`

```bash
#!/bin/bash
# Comprehensive backup

BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/hgr_backup_$TIMESTAMP"

mkdir -p $BACKUP_PATH

echo "Creating backup: $BACKUP_PATH"

# 1. Backup databases
echo "Backing up databases..."
for DB in knowledge_lake state_graph logicnode_registry traceability_ledger model_store; do
    docker exec hgr-postgres pg_dump -U hgr_admin -Fc $DB > "$BACKUP_PATH/${DB}.dump"
done

# 2. Backup Redis
echo "Backing up Redis..."
docker exec hgr-redis redis-cli --rdb /data/dump.rdb BGSAVE
sleep 5
docker cp hgr-redis:/data/dump.rdb "$BACKUP_PATH/redis.rdb"

# 3. Backup configurations
echo "Backing up configurations..."
tar czf "$BACKUP_PATH/config.tar.gz" config/ .env docker-compose.yml

# 4. Create archive
echo "Creating archive..."
cd $BACKUP_DIR
tar czf "hgr_backup_$TIMESTAMP.tar.gz" "hgr_backup_$TIMESTAMP"
rm -rf "hgr_backup_$TIMESTAMP"

echo "✓ Backup complete: $BACKUP_DIR/hgr_backup_$TIMESTAMP.tar.gz"
```

### 9.2 Recovery Script

**File:** `scripts/restore.sh`

```bash
#!/bin/bash
# Restore from backup

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file>"
    exit 1
fi

echo "Restoring from: $BACKUP_FILE"

# Extract backup
TEMP_DIR=$(mktemp -d)
tar xzf $BACKUP_FILE -C $TEMP_DIR

# Stop services
docker-compose down

# Restore databases
for DB in knowledge_lake state_graph logicnode_registry traceability_ledger model_store; do
    echo "Restoring $DB..."
    docker-compose up -d postgres
    sleep 5
    docker exec -i hgr-postgres pg_restore -U hgr_admin -d $DB -c < "$TEMP_DIR/${DB}.dump"
done

# Restore Redis
docker cp "$TEMP_DIR/redis.rdb" hgr-redis:/data/dump.rdb
docker-compose restart redis

# Restore configurations
tar xzf "$TEMP_DIR/config.tar.gz" -C /

# Start services
docker-compose up -d

# Cleanup
rm -rf $TEMP_DIR

echo "✓ Restore complete"
```

---

## 10. OPERATIONAL PLAYBOOKS

### 10.1 Playbook: Adding New Agent

```bash
# 1. Create agent configuration
cp config/agents/agent-template.yaml config/agents/AGENT-NEW-001.yaml
vim config/agents/AGENT-NEW-001.yaml

# 2. Add to docker-compose.yml
cat >> docker-compose.yml <<EOF
  agent-new:
    image: hgr-agent-new:latest
    container_name: hgr-agent-new
    environment:
      - AGENT_ID=AGENT-NEW-001
    networks:
      - hgr-network
EOF

# 3. Build and deploy
docker-compose build agent-new
docker-compose up -d agent-new

# 4. Verify
docker-compose ps agent-new
docker logs agent-new
```

### 10.2 Playbook: Emergency Shutdown

```bash
# 1. Stop accepting new tasks
curl -X POST http://localhost:8000/api/v1/system/pause

# 2. Wait for active tasks to complete (max 5 minutes)
timeout 300 bash -c 'until [ $(curl -s http://localhost:8000/api/v1/tasks/active | jq length) -eq 0 ]; do sleep 5; done'

# 3. Backup current state
./scripts/backup.sh

# 4. Graceful shutdown
docker-compose down

echo "✓ System shut down gracefully"
```

---

## DOCUMENT METADATA

**Document ID:** 27  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Owner:** DevOps Lead  
**Dependencies:** Documents 19-26  
**Next Document:** 28 (Development Workflow & Best Practices)

---

*End of Agent Deployment & Operations Guide*
