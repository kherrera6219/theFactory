# DOCUMENT 60: SYSTEM ADMINISTRATOR GUIDE
## Holy Grail Refinery - Documentation & Training

**Document ID:** 60  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Documentation & Training  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This guide covers **system administration and operations** for the Holy Grail Refinery. Intended for DevOps engineers, SREs, and system administrators responsible for deploying, monitoring, and maintaining the system.

---

## TABLE OF CONTENTS

1. [Installation & Deployment](#installation--deployment)
2. [Configuration Management](#configuration-management)
3. [Monitoring & Observability](#monitoring--observability)
4. [Backup & Recovery](#backup--recovery)
5. [Troubleshooting](#troubleshooting)
6. [Performance Tuning](#performance-tuning)
7. [Security Hardening](#security-hardening)
8. [Upgrades & Maintenance](#upgrades--maintenance)

---

## INSTALLATION & DEPLOYMENT

### Prerequisites

**Hardware:**
- Intel i7-14700F or equivalent (20+ cores recommended)
- 32GB RAM minimum
- 1TB NVMe SSD
- Docker installed

**Software:**
- Ubuntu 22.04+ / macOS 12+ / Windows 11 with WSL2
- Docker 24.0+
- Docker Compose 2.0+

### Quick Installation

```bash
# Clone repository
git clone https://github.com/your-org/holy-grail-refinery
cd holy-grail-refinery

# Configure environment
cp .env.example .env
nano .env  # Add API keys

# Start services
docker-compose up -d

# Verify installation
curl http://localhost:8000/health
```

### Production Deployment

**Docker Compose Production:**

```yaml
# docker-compose.prod.yml
version: '3.9'

services:
  postgres:
    image: postgres:16
    restart: always
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    
  redis:
    image: redis:7.2
    restart: always
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
  
  # 35 agent containers...
  
volumes:
  postgres_data:
  redis_data:
```

**Start Production:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## CONFIGURATION MANAGEMENT

### Environment Variables

**File:** `.env`

```bash
# Database
DATABASE_URL=postgresql://hgr:password@postgres:5432/hgr_db

# Redis
REDIS_URL=redis://redis:6379/0

# LLM APIs
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# System
LOG_LEVEL=INFO
ENABLE_MONITORING=true
```

### Agent Configuration

**File:** `config/agents.yaml`

```yaml
agents:
  PM-001:
    model: claude-sonnet-4
    context_window: 1000000
    temperature: 0.3
  
  AGENT-PY-001:
    model: claude-sonnet-4
    context_window: 1000000
    specialization: python
```

---

## MONITORING & OBSERVABILITY

### Health Checks

**System Health:**
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "agents": {
    "total": 35,
    "active": 35,
    "error": 0
  },
  "databases": {
    "postgres": "connected",
    "redis": "connected"
  }
}
```

### Agent Status

**Check All Agents:**
```bash
curl http://localhost:8000/v1/agents
```

**Check Specific Agent:**
```bash
docker logs hgr-pm-agent
docker logs hgr-python-specialist
```

### Metrics Collection

**Prometheus Integration:**

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'hgr-api'
    static_configs:
      - targets: ['localhost:8000']
```

**Key Metrics:**
- `hgr_missions_total` - Total missions
- `hgr_missions_completed` - Completed missions
- `hgr_agent_uptime_seconds` - Agent uptime
- `hgr_logicnodes_extracted` - LogicNodes extracted

### Grafana Dashboard

Import dashboard: `dashboards/hgr-overview.json`

**Panels:**
- Mission throughput
- Agent health status
- Database performance
- Resource utilization

---

## BACKUP & RECOVERY

### Automated Backups

**Backup Script:** `scripts/backup.sh`

```bash
#!/bin/bash
BACKUP_DIR="/backups/hgr"
DATE=$(date +%Y%m%d_%H%M%S)

# PostgreSQL backup
docker exec hgr-postgres pg_dump -U hgr hgr_db > $BACKUP_DIR/db_$DATE.sql

# Redis backup
docker exec hgr-redis redis-cli SAVE
docker cp hgr-redis:/data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# Compress
tar -czf $BACKUP_DIR/hgr_backup_$DATE.tar.gz $BACKUP_DIR/*_$DATE.*
```

**Cron Schedule:**
```bash
# Daily backups at 2 AM
0 2 * * * /opt/hgr/scripts/backup.sh
```

### Disaster Recovery

**Restore from Backup:**

```bash
# Stop system
docker-compose down

# Restore PostgreSQL
cat backup/db_20260206.sql | docker exec -i hgr-postgres psql -U hgr hgr_db

# Restore Redis
docker cp backup/redis_20260206.rdb hgr-redis:/data/dump.rdb

# Restart
docker-compose up -d
```

**Recovery Time Objective (RTO):** <1 hour  
**Recovery Point Objective (RPO):** <24 hours

---

## TROUBLESHOOTING

### Common Issues

**Issue: Agent in ERROR state**

Diagnosis:
```bash
docker logs hgr-[agent-name]
```

Solutions:
- Check LLM API key validity
- Verify Semantic Bus connectivity
- Restart agent: `docker-compose restart [agent-name]`

**Issue: Mission stuck in "processing"**

Diagnosis:
```bash
# Check Mission Control
curl http://localhost:8000/v1/missions/[mission-id]

# Check agent logs
docker-compose logs -f
```

Solutions:
- Verify all agents are active
- Check for agent errors
- Restart stuck agents

**Issue: Database connection errors**

Diagnosis:
```bash
docker logs hgr-postgres
docker exec hgr-postgres psql -U hgr -c "SELECT 1"
```

Solutions:
- Verify DATABASE_URL is correct
- Check PostgreSQL is running
- Review connection pool settings

### Log Analysis

**View all logs:**
```bash
docker-compose logs -f
```

**Filter by service:**
```bash
docker-compose logs -f pm-agent
docker-compose logs -f postgres
```

**Export logs:**
```bash
docker-compose logs > hgr_logs_$(date +%Y%m%d).txt
```

---

## PERFORMANCE TUNING

### Database Optimization

**PostgreSQL Tuning:**

```sql
-- Increase shared buffers
ALTER SYSTEM SET shared_buffers = '8GB';

-- Increase work memory
ALTER SYSTEM SET work_mem = '256MB';

-- Enable parallel queries
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;

-- Reload configuration
SELECT pg_reload_conf();
```

**Create Indexes:**
```sql
CREATE INDEX idx_logicnodes_concept ON logicnodes(concept);
CREATE INDEX idx_logicnodes_domain ON logicnodes(domain);
CREATE INDEX idx_missions_status ON missions(status);
```

### Redis Optimization

```bash
# Increase max memory
redis-cli CONFIG SET maxmemory 4gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### Agent Resource Limits

**docker-compose.yml:**
```yaml
services:
  python-specialist:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

---

## SECURITY HARDENING

### Network Security

**Firewall Rules:**
```bash
# Allow only localhost
ufw default deny incoming
ufw allow from 127.0.0.1

# Or allow from specific network
ufw allow from 192.168.1.0/24
```

### API Key Management

**Use Secrets:**
```bash
# Docker secrets
echo "sk-ant-..." | docker secret create anthropic_api_key -

# Reference in compose
secrets:
  anthropic_api_key:
    external: true
```

### SSL/TLS

**Enable HTTPS:**
```yaml
# nginx reverse proxy
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
    }
}
```

---

## UPGRADES & MAINTENANCE

### Upgrading System

**Minor Version Upgrade:**
```bash
# Pull latest images
docker-compose pull

# Restart services
docker-compose down
docker-compose up -d

# Verify
curl http://localhost:8000/health
```

**Major Version Upgrade:**
```bash
# Backup first!
./scripts/backup.sh

# Review changelog
cat CHANGELOG.md

# Run migration scripts
./scripts/migrate_v1_to_v2.sh

# Upgrade
docker-compose down
docker-compose -f docker-compose.v2.yml up -d
```

### Scheduled Maintenance

**Weekly Tasks:**
- Review agent logs for errors
- Check disk space usage
- Verify backups completed
- Monitor resource utilization

**Monthly Tasks:**
- Update Docker images
- Vacuum PostgreSQL database
- Review security updates
- Test disaster recovery

---

## MONITORING CHECKLIST

### Daily
- [ ] Check system health endpoint
- [ ] Verify all 35 agents are active
- [ ] Review error logs

### Weekly
- [ ] Analyze performance metrics
- [ ] Check backup completion
- [ ] Review disk space (>20% free)

### Monthly
- [ ] Test disaster recovery
- [ ] Apply security updates
- [ ] Review resource trends
- [ ] Optimize database

---

## SUPPORT CONTACTS

**Community:**
- Forum: https://community.hgr.local
- Discord: https://discord.gg/hgr

**Enterprise Support:**
- Email: support@hgr.local
- SLA: 4-hour response for P1 issues

**Emergency:**
- On-call: +1-XXX-XXX-XXXX
- 24/7 for production issues

---

## DOCUMENT METADATA

**Document ID:** 60  
**Version:** 1.0  
**Created:** February 6, 2026  
**Category:** Documentation & Training  
**Owner:** DevOps Team Lead  
**Target Audience:** System administrators, SREs, DevOps engineers

---

*End of System Administrator Guide - Final Document in 60-Document Suite*
