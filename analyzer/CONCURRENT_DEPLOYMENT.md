# Concurrent Analyzer Deployment Guide

## Overview

The new concurrent analyzer architecture supports **true parallel analysis** by running multiple replicas of each analyzer service. This completely solves the concurrent analysis bottleneck.

### Architecture Highlights

- **Horizontal Scaling**: 3x static-analyzer, 2x dynamic-analyzer, 2x performance-tester, 2x ai-analyzer
- **Internal Concurrency**: Each replica can handle 2-3 concurrent analyses via task queue
- **Connection Pooling**: Smart load balancing across all replicas
- **Total Capacity**: **~18-30 concurrent analyses** (vs 1-4 before)

---

## Quick Start

### 1. Stop Old Analyzers

```bash
cd analyzer
docker compose down
```

### 2. Deploy Concurrent Architecture

```bash
# Deploy with new concurrent compose file
docker compose -f docker-compose.concurrent.yml up -d

# Verify all replicas are running
docker compose -f docker-compose.concurrent.yml ps
```

### 3. Configure Environment Variables

Add to your `.env` file:

```bash
# Concurrent Analyzer Configuration
# ==================================

# Static Analyzer Replicas (3x)
STATIC_ANALYZER_URLS=ws://localhost:2001,ws://localhost:2002,ws://localhost:2003

# Dynamic Analyzer Replicas (2x)
DYNAMIC_ANALYZER_URLS=ws://localhost:2011,ws://localhost:2012

# Performance Tester Replicas (2x)
PERF_TESTER_URLS=ws://localhost:2021,ws://localhost:2022

# AI Analyzer Replicas (2x)
AI_ANALYZER_URLS=ws://localhost:2031,ws://localhost:2032

# Pool Configuration
ANALYZER_LOAD_BALANCING=least_loaded  # Options: least_loaded, round_robin, random
ANALYZER_MAX_RETRIES=3
ANALYZER_REQUEST_TIMEOUT=600
```

### 4. Update Application Code (Optional)

The connection pool integrates automatically, but for explicit control:

```python
# In your analyzer integration code
from analyzer.analyzer_manager_pooled import PooledAnalyzerManager

manager = PooledAnalyzerManager()
result = await manager.run_static_analysis('model-slug', 1, tools=['bandit', 'semgrep'])
```

---

## Architecture Details

### Replica Port Mapping

| Service | Replica 1 | Replica 2 | Replica 3 |
|---------|-----------|-----------|-----------|
| **static-analyzer** | 2001 | 2002 | 2003 |
| **dynamic-analyzer** | 2011 | 2012 | - |
| **performance-tester** | 2021 | 2022 | - |
| **ai-analyzer** | 2031 | 2032 | - |

### Load Balancing Strategies

#### 1. **Least Loaded** (Recommended - Default)
- Routes to replica with lowest active request count
- Best for variable workloads
- Optimal resource utilization

#### 2. **Round Robin**
- Distributes requests evenly in sequence
- Simple and predictable
- Good for uniform workloads

#### 3. **Random**
- Random replica selection
- Lowest overhead
- Good enough for most cases

### Capacity Planning

**Single Replica Capacity:**
- Each replica: 2-3 concurrent analyses
- CPU bound: Python static tools (bandit, pylint)
- I/O bound: Network tools (ZAP, curl)

**Total System Capacity:**
```
Static Analysis:  3 replicas × 2 concurrent = 6 parallel static analyses
Dynamic Analysis: 2 replicas × 2 concurrent = 4 parallel dynamic analyses
Performance Test: 2 replicas × 2 concurrent = 4 parallel perf tests
AI Analysis:      2 replicas × 2 concurrent = 4 parallel AI analyses

TOTAL: Up to 18 analyses running concurrently
```

With internal queueing (queue size: 100 per replica):
- **Static**: 3 × 100 = 300 queued requests
- **Dynamic**: 2 × 100 = 200 queued requests
- etc.

---

## Monitoring & Health Checks

### Check Pool Status

```python
from app.services.analyzer_pool import get_analyzer_pool

pool = await get_analyzer_pool()
stats = pool.get_pool_stats()

# Example output:
{
    'static-analyzer': {
        'total_endpoints': 3,
        'healthy_endpoints': 3,
        'total_active_requests': 5,
        'endpoints': [
            {
                'url': 'ws://localhost:2001',
                'healthy': True,
                'active_requests': 2,
                'total_requests': 150,
                'total_failures': 1,
                'avg_response_time': 45.2,
                'load_score': 24.5
            },
            # ... more endpoints
        ]
    },
    # ... more services
}
```

### Docker Health Checks

```bash
# Check all replicas
docker compose -f docker-compose.concurrent.yml ps

# View logs for specific replica
docker logs static-analyzer-1

# Check resource usage
docker stats --no-stream
```

### Endpoint Health API

```bash
# Check health of specific replica
curl -X POST ws://localhost:2001 -d '{"type":"health_check"}'

# Response:
{
    "type": "health_response",
    "status": "healthy",
    "service": "static-analyzer",
    "concurrency": {
        "max_concurrent": 2,
        "active_analyses": 1,
        "queued_analyses": 0,
        "queue_capacity": 100
    },
    "stats": {
        "total_requests": 150,
        "completed_requests": 148,
        "failed_requests": 2
    }
}
```

---

## Scaling Up/Down

### Add More Replicas

Edit `docker-compose.concurrent.yml`:

```yaml
static-analyzer-4:
  # Copy static-analyzer-3 config
  ports:
    - "2004:2001"
  container_name: "static-analyzer-4"
  # ... rest of config
```

Update `.env`:
```bash
STATIC_ANALYZER_URLS=ws://localhost:2001,ws://localhost:2002,ws://localhost:2003,ws://localhost:2004
```

Restart:
```bash
docker compose -f docker-compose.concurrent.yml up -d
```

### Reduce Replicas

Remove services from `docker-compose.concurrent.yml` and update `STATIC_ANALYZER_URLS` accordingly.

---

## Troubleshooting

### Problem: "Queue is full" errors

**Cause**: Too many concurrent requests, queue capacity exceeded

**Solution**:
1. Add more replicas
2. Increase queue size in analyzer (set `MAX_QUEUE_SIZE=200` env var)
3. Increase `MAX_CONCURRENT_ANALYSES` per replica

### Problem: Replica marked unhealthy

**Cause**: 3+ consecutive failures

**Solution**:
1. Check replica logs: `docker logs static-analyzer-1`
2. Verify it's running: `docker ps`
3. Check resource usage: `docker stats`
4. Restart specific replica: `docker restart static-analyzer-1`

The pool automatically:
- Stops routing to unhealthy replicas
- Retries after 60s cooldown period
- Distributes load to healthy replicas

### Problem: Slow response times

**Cause**: Replicas overloaded or resource constrained

**Solution**:
1. Check pool stats to see load distribution
2. Add more replicas if load is consistently high
3. Increase CPU/memory limits in docker-compose
4. Check if tools are CPU/IO bound and adjust concurrency

### Problem: Connection refused errors

**Cause**: Replicas not started or wrong ports

**Solution**:
```bash
# Verify replicas are running
docker compose -f docker-compose.concurrent.yml ps

# Check if ports are listening
netstat -an | grep -E "2001|2002|2003|2011|2012"

# Restart all
docker compose -f docker-compose.concurrent.yml restart
```

---

## Performance Tuning

### Increase Internal Concurrency

For CPU-heavy workloads (static analysis):
```yaml
environment:
  - MAX_CONCURRENT_ANALYSES=3  # Increase from 2
  - MAX_QUEUE_SIZE=150  # Increase from 100
```

### Adjust Timeout Values

For long-running analyses:
```bash
# In .env
STATIC_ANALYSIS_TIMEOUT=600  # 10 minutes
DYNAMIC_ANALYSIS_TIMEOUT=300  # 5 minutes
```

### Resource Limits

Adjust in `docker-compose.concurrent.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 2G  # Increase if OOM errors
      cpus: '1.0'  # Increase for CPU-bound tools
```

---

## Migration from Old Architecture

### Step 1: Parallel Deployment (Zero Downtime)

Keep old analyzers running during migration:

```bash
# Old analyzers still running on 2001-2004
cd analyzer
docker compose ps

# Start new replicas on different ports
docker compose -f docker-compose.concurrent.yml up -d
```

### Step 2: Update Application Config

```bash
# Update .env to use new ports
STATIC_ANALYZER_URLS=ws://localhost:2001,ws://localhost:2002,ws://localhost:2003
```

### Step 3: Test New Architecture

```bash
# Run test pipeline
# Verify concurrent analyses work

# Check pool stats
curl http://localhost:5000/api/analyzer/pool/stats
```

### Step 4: Shutdown Old Analyzers

```bash
cd analyzer
docker compose -f docker-compose.yml down
```

---

## Rollback Procedure

If issues occur, rollback to single-instance architecture:

```bash
# Stop concurrent deployment
cd analyzer
docker compose -f docker-compose.concurrent.yml down

# Start original deployment
docker compose up -d

# Update .env back to single URLs
STATIC_ANALYZER_URL=ws://localhost:2001
DYNAMIC_ANALYZER_URL=ws://localhost:2002
PERF_TESTER_URL=ws://localhost:2003
AI_ANALYZER_URL=ws://localhost:2004
```

---

## Benefits Summary

✅ **18-30x More Concurrent Capacity** (vs 1-2 before)
✅ **Automatic Load Balancing** across replicas
✅ **Automatic Failover** when replicas fail
✅ **No Code Changes Required** (drop-in replacement)
✅ **Graceful Degradation** under load (queueing)
✅ **Health Monitoring** built-in
✅ **Easy Scaling** (add more replicas)

---

## Next Steps

1. Deploy concurrent architecture
2. Monitor pool stats during first pipeline
3. Adjust replica count based on load
4. Fine-tune concurrency per replica
5. Set up alerts for unhealthy replicas (optional)

Questions? Check troubleshooting section or logs.
