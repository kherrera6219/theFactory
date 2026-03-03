# LOCAL INFRASTRUCTURE CONFIGURATION (AW1)
## Hardware Optimization and Resource Management

**Version:** 1.0  
**Date:** February 2026  
**Status:** Complete Specification  
**Document Owner:** SRE Lead

---

## EXECUTIVE SUMMARY

Complete infrastructure configuration guide for optimizing the Holy Grail Refinery on AW1 local hardware. Covers operating system tuning, Docker engine configuration, storage optimization, network performance, and monitoring.

**AW1 Hardware Profile:**
- CPU: Intel i7-14700F (20 cores, 28 threads)
- GPU: NVIDIA RTX 4060 Ti (16GB VRAM)
- RAM: 32GB DDR5-4800
- Storage: 1TB NVMe PCIe 4.0 SSD
- Network: Gigabit Ethernet

**Optimization Goals:**
- Maximize container density (40 containers)
- Minimize latency for Semantic Bus (Redis Pub/Sub)
- Optimize storage I/O for Knowledge Lake (vector DB)
- Enable GPU acceleration for Vision-AI workloads

---

## 1. OPERATING SYSTEM CONFIGURATION

### 1.1 Ubuntu 24.04 LTS Tuning

**Kernel Parameters (/etc/sysctl.conf):**
```bash
# Network optimization
net.core.somaxconn = 4096
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_keepalive_intvl = 15

# Memory management
vm.swappiness = 10  # Prefer RAM over swap
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
vm.vfs_cache_pressure = 50

# File system
fs.file-max = 2097152
fs.inotify.max_user_watches = 524288

# Docker containers
kernel.pid_max = 4194304

# Apply changes
sudo sysctl -p
```

---

**Resource Limits (/etc/security/limits.conf):**
```bash
*   soft    nofile  1048576
*   hard    nofile  1048576
*   soft    nproc   unlimited
*   hard    nproc   unlimited
*   soft    memlock unlimited
*   hard    memlock unlimited
```

---

### 1.2 Windows 10/11 with WSL2 Tuning

**WSL Configuration (.wslconfig in %USERPROFILE%):**
```ini
[wsl2]
# Memory allocation
memory=24GB

# CPU allocation
processors=16

# Swap
swap=4GB
swapFile=C:\\temp\\wsl-swap.vhdx

# Network
localhostForwarding=true

# Virtualization
nestedVirtualization=true

# Kernel parameters
kernelCommandLine=swapaccount=1 cgroup_enable=memory cgroup_memory=1
```

**Apply changes:**
```powershell
wsl --shutdown
wsl
```

---

## 2. DOCKER ENGINE CONFIGURATION

### 2.1 Docker Daemon Configuration

**/etc/docker/daemon.json (Linux):**
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "storage-opts": [
    "overlay2.override_kernel_check=true"
  ],
  "default-address-pools": [
    {
      "base": "172.20.0.0/16",
      "size": 24
    }
  ],
  "bip": "172.17.0.1/16",
  "fixed-cidr": "172.17.0.0/16",
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  },
  "max-concurrent-downloads": 10,
  "max-concurrent-uploads": 10,
  "features": {
    "buildkit": true
  },
  "experimental": false,
  "metrics-addr": "127.0.0.1:9323",
  "live-restore": true
}
```

**Restart Docker:**
```bash
sudo systemctl restart docker
```

---

### 2.2 Docker Resource Limits

**Default Container Limits:**
```bash
# Set in docker-compose.yml or docker run
--memory="2g"
--memory-swap="2g"
--memory-swappiness=0
--cpu-shares=1024
--cpus="1.0"
--pids-limit=200
```

**System-Wide Docker Limits:**
```bash
# /etc/systemd/system/docker.service.d/override.conf
[Service]
LimitNOFILE=1048576
LimitNPROC=infinity
LimitCORE=infinity
TasksMax=infinity
```

---

## 3. STORAGE OPTIMIZATION

### 3.1 File System Selection

**Recommended: ext4 for Docker**
```bash
# Format partition as ext4
sudo mkfs.ext4 -L docker-data /dev/nvme0n1p2

# Mount with optimized options
sudo mkdir -p /mnt/docker
echo '/dev/nvme0n1p2 /mnt/docker ext4 defaults,noatime,nodiratime,discard 0 2' | sudo tee -a /etc/fstab
sudo mount -a

# Configure Docker to use custom directory
sudo mkdir -p /mnt/docker/docker
sudo systemctl stop docker
sudo mv /var/lib/docker /mnt/docker/docker
sudo ln -s /mnt/docker/docker /var/lib/docker
sudo systemctl start docker
```

**Why ext4:**
- Mature and stable
- Good performance for container layers
- Native Docker support
- TRIM/discard support for SSD

---

### 3.2 NVMe SSD Optimization

**Enable TRIM:**
```bash
# Check if TRIM is supported
sudo hdparm -I /dev/nvme0n1 | grep TRIM

# Enable periodic TRIM
sudo systemctl enable fstrim.timer
sudo systemctl start fstrim.timer

# Manual TRIM
sudo fstrim -v /
```

**I/O Scheduler:**
```bash
# Check current scheduler
cat /sys/block/nvme0n1/queue/scheduler

# Set to none (best for NVMe)
echo none | sudo tee /sys/block/nvme0n1/queue/scheduler

# Make permanent (add to /etc/rc.local)
echo 'echo none > /sys/block/nvme0n1/queue/scheduler' | sudo tee -a /etc/rc.local
```

**Read-Ahead:**
```bash
# Increase read-ahead for sequential workloads
sudo blockdev --setra 8192 /dev/nvme0n1
```

---

### 3.3 Docker Volume Performance

**Use named volumes (not bind mounts) for databases:**
```yaml
volumes:
  postgres-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/docker/volumes/postgres
```

**Tmpfs for temporary data:**
```yaml
tmpfs:
  - /tmp:size=2G,mode=1777
```

---

## 4. NETWORK OPTIMIZATION

### 4.1 TCP Tuning for Low Latency

**Optimize for Redis Pub/Sub:**
```bash
# /etc/sysctl.conf

# TCP buffer sizes (bytes)
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864

# Congestion control (BBR for better performance)
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# Reduce TIME_WAIT sockets
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30

# Increase connection backlog
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 8192

sudo sysctl -p
```

---

### 4.2 Docker Bridge Network Tuning

**Custom bridge network:**
```bash
docker network create \
  --driver=bridge \
  --subnet=172.20.0.0/16 \
  --ip-range=172.20.0.0/24 \
  --gateway=172.20.0.1 \
  --opt com.docker.network.bridge.name=refinery-bridge \
  --opt com.docker.network.driver.mtu=1500 \
  refinery-net
```

**MTU Optimization:**
```bash
# Check current MTU
ip link show docker0

# Set MTU (if needed)
sudo ifconfig docker0 mtu 9000  # Jumbo frames (if supported)
```

---

## 5. GPU CONFIGURATION

### 5.1 NVIDIA Docker Runtime

**Install NVIDIA Container Toolkit:**
```bash
# Add repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**Test GPU access:**
```bash
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

---

### 5.2 GPU Resource Allocation

**PM Agent (Vision-AI for visual verification):**
```yaml
pm-agent:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

**GPU Memory Fraction:**
```python
# In agent code
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
```

---

## 6. MEMORY MANAGEMENT

### 6.1 Swap Configuration

**Disable swap for production:**
```bash
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab
```

**Or limit swap usage:**
```bash
# Keep swap enabled but prefer RAM
vm.swappiness = 10  # Already set in sysctl.conf
```

---

### 6.2 Huge Pages (for PostgreSQL)

**Enable transparent huge pages:**
```bash
# Check current setting
cat /sys/kernel/mm/transparent_hugepage/enabled

# Set to madvise
echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled

# Make permanent
echo 'echo madvise > /sys/kernel/mm/transparent_hugepage/enabled' | sudo tee -a /etc/rc.local
```

---

### 6.3 Memory Overcommit

**Allow memory overcommit:**
```bash
# /etc/sysctl.conf
vm.overcommit_memory = 1  # Allow overcommit
vm.overcommit_ratio = 50  # Percentage of RAM to overcommit

sudo sysctl -p
```

---

## 7. CPU OPTIMIZATION

### 7.1 CPU Governor

**Set to performance mode:**
```bash
# Check current governor
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Set all CPUs to performance
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Make permanent
sudo apt-get install cpufrequtils
echo 'GOVERNOR="performance"' | sudo tee /etc/default/cpufrequtils
sudo systemctl restart cpufrequtils
```

---

### 7.2 CPU Affinity

**Pin containers to specific CPUs (optional):**
```yaml
services:
  ceo-agent:
    cpuset: "0-7"  # P-cores for compute-heavy CEO
  python-specialist:
    cpuset: "8-19"  # E-cores for I/O-heavy specialists
```

---

### 7.3 Turbo Boost

**Verify Turbo Boost enabled:**
```bash
cat /sys/devices/system/cpu/intel_pstate/no_turbo
# 0 = enabled, 1 = disabled

# Enable if disabled
echo 0 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo
```

---

## 8. MONITORING & OBSERVABILITY

### 8.1 System Monitoring Tools

**Install monitoring stack:**
```bash
# htop (interactive process viewer)
sudo apt-get install htop

# iotop (I/O monitoring)
sudo apt-get install iotop

# nethogs (network per-process)
sudo apt-get install nethogs

# dstat (versatile resource statistics)
sudo apt-get install dstat
```

---

### 8.2 Docker Monitoring

**Docker stats:**
```bash
# Real-time stats
docker stats

# Export to file
docker stats --no-stream > docker-stats.txt
```

**cAdvisor (Container Advisor):**
```yaml
cadvisor:
  image: gcr.io/cadvisor/cadvisor:latest
  container_name: cadvisor
  ports:
    - "8080:8080"
  volumes:
    - /:/rootfs:ro
    - /var/run:/var/run:ro
    - /sys:/sys:ro
    - /var/lib/docker/:/var/lib/docker:ro
  privileged: true
```

---

### 8.3 Prometheus + Grafana

**Prometheus configuration:**
```yaml
prometheus:
  image: prom/prometheus:latest
  container_name: prometheus
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
    - prometheus-data:/prometheus
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'
    - '--storage.tsdb.retention.time=30d'
```

**Grafana:**
```yaml
grafana:
  image: grafana/grafana:latest
  container_name: grafana
  ports:
    - "3001:3000"
  volumes:
    - grafana-data:/var/lib/grafana
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## 9. BACKUP & RECOVERY

### 9.1 Database Backups

**PostgreSQL automated backup:**
```bash
#!/bin/bash
# scripts/backup-postgres.sh

BACKUP_DIR="/mnt/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/postgres_$TIMESTAMP.sql"

mkdir -p $BACKUP_DIR

docker exec refinery-postgres pg_dumpall -U refinery_admin > $BACKUP_FILE

# Compress
gzip $BACKUP_FILE

# Keep only last 7 days
find $BACKUP_DIR -name "postgres_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE.gz"
```

**Cron job:**
```bash
# Daily at 2 AM
0 2 * * * /home/user/holy-grail-refinery/scripts/backup-postgres.sh
```

---

### 9.2 Volume Snapshots

**Backup Docker volumes:**
```bash
#!/bin/bash
# scripts/backup-volumes.sh

VOLUMES="redis-data postgres-data qdrant-storage"
BACKUP_DIR="/mnt/backups/volumes"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

for VOLUME in $VOLUMES; do
    docker run --rm \
      -v $VOLUME:/source:ro \
      -v $BACKUP_DIR:/backup \
      alpine \
      tar czf /backup/${VOLUME}_$TIMESTAMP.tar.gz -C /source .
done
```

---

## 10. PERFORMANCE BENCHMARKING

### 10.1 Storage Benchmark

**Test NVMe performance:**
```bash
# Sequential write
dd if=/dev/zero of=/mnt/docker/testfile bs=1M count=10000 oflag=direct

# Sequential read
dd if=/mnt/docker/testfile of=/dev/null bs=1M iflag=direct

# Random read/write (fio)
sudo apt-get install fio
fio --name=random-rw --ioengine=libaio --iodepth=32 --rw=randrw \
    --bs=4k --direct=1 --size=1G --numjobs=4 --runtime=60 \
    --group_reporting --filename=/mnt/docker/fiotest
```

---

### 10.2 Network Benchmark

**iperf3 (container-to-container):**
```bash
# Server
docker run -it --rm --name=iperf3-server networkstatic/iperf3 -s

# Client
docker run -it --rm networkstatic/iperf3 -c iperf3-server
```

---

### 10.3 Redis Benchmark

**Redis performance:**
```bash
docker exec -it refinery-redis redis-benchmark -q -n 100000
```

---

## 11. SECURITY HARDENING

### 11.1 Firewall Configuration

**UFW (Ubuntu):**
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 3000/tcp  # Mission Control
sudo ufw enable
```

---

### 11.2 Docker Security

**AppArmor profiles:**
```bash
# Use default Docker AppArmor profile
sudo aa-enforce /etc/apparmor.d/docker
```

**Seccomp profiles:**
```yaml
security_opt:
  - seccomp:unconfined  # Only if needed, otherwise use default
```

---

## 12. SCALING CONSIDERATIONS

### 12.1 When to Upgrade

**RAM Upgrade (32GB → 64GB):**
- Multiple concurrent missions
- Larger Knowledge Lake
- More audit parallelism

**Storage Upgrade (1TB → 2TB):**
- More mission history
- Larger trace logs
- Additional language documentation

**CPU Upgrade:**
- Consider i9-14900K (24 cores) for heavy workloads
- Or move to dual-socket Xeon/EPYC for cloud-like density

---

### 12.2 Move to Kubernetes Cluster

**When local machine insufficient:**
- Deploy to 3-5 node Kubernetes cluster
- Each node: 32GB RAM, 16 cores
- Shared NFS or Ceph storage
- High-availability Redis/Postgres

---

## DOCUMENT METADATA

**Document ID:** 18  
**Version:** 1.0  
**Created:** February 2026  
**Owner:** SRE Lead

---

*End of Local Infrastructure Configuration (AW1)*
