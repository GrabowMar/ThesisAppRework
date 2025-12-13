# Troubleshooting Guide

Solutions for common issues in ThesisAppRework.

## Quick Diagnostics

```bash
# Check all services
./start.ps1 -Mode Status

# Health check
python analyzer/analyzer_manager.py health

# View recent logs
./start.ps1 -Mode Logs
```

## Startup Issues

### Flask Won't Start

**Symptoms:** `Address already in use` error

**Solution:**
```bash
# Stop all services
./start.ps1 -Mode Stop

# Or find and kill the process
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Linux
lsof -i :5000
kill -9 <PID>
```

### Database Locked

**Symptoms:** `sqlite3.OperationalError: database is locked`

**Solution:**
1. Stop Flask application
2. Check for zombie processes
3. Restart the application

```bash
# Find Python processes
# Windows
tasklist | findstr python

# Linux
ps aux | grep python
```

### Import Errors

**Symptoms:** `ModuleNotFoundError`

**Solution:**
```bash
# Ensure virtual environment is active
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate   # Linux

# Reinstall dependencies
pip install -r requirements.txt
```

## Analyzer Issues

### Containers Won't Start

**Symptoms:** `Cannot connect to Docker daemon`

**Solutions:**
1. Start Docker Desktop
2. Wait for Docker to fully initialize
3. Retry:
```bash
python analyzer/analyzer_manager.py start
```

### WebSocket Connection Failed

**Symptoms:** `Connection refused` on ports 2001-2004

**Diagnosis:**
```bash
# Check container status
docker ps

# Check port binding
docker port static-analyzer

# View container logs
docker logs static-analyzer
```

**Solutions:**
1. Rebuild containers:
```bash
./start.ps1 -Mode Rebuild
```

2. Check firewall settings
3. Verify Docker network:
```bash
docker network ls
docker network inspect thesisapprework_default
```

### Analysis Timeout

**Symptoms:** `Task exceeded timeout`

**Solution:** Increase timeouts in `.env`:
```
STATIC_ANALYSIS_TIMEOUT=600
SECURITY_ANALYSIS_TIMEOUT=900
PERFORMANCE_TIMEOUT=600
```

### SARIF Files Missing

**Symptoms:** Results don't include SARIF data

**Solution:** Check tool execution:
```bash
# Run with verbose output
python analyzer/analyzer_manager.py analyze model 1 static --verbose
```

## Task Issues

### Stuck Tasks

**Symptoms:** Tasks remain in `RUNNING` state indefinitely

**Solution:**
```bash
# Fix stuck tasks
python scripts/fix_task_statuses.py

# Or run maintenance
./start.ps1 -Mode Maintenance
```

### PENDING Tasks Not Executing

**Symptoms:** Tasks stay in `PENDING` state

**Diagnosis:**
1. Check TaskExecutionService is running
2. Verify analyzer services are healthy

```bash
# In Flask shell
from app.services.service_locator import ServiceLocator
service = ServiceLocator.get_task_execution_service()
print(f"Running: {service._running}")
```

### Lost Results

**Symptoms:** Analysis completed but results not visible

**Check locations:**
1. Database: `AnalysisTask.result_summary`
2. Filesystem: `results/{model}/app{N}/task_{id}/`

## API Issues

### 401 Unauthorized

**Symptoms:** All API calls return 401

**Solutions:**
1. Verify token is valid:
```bash
curl http://localhost:5000/api/tokens/verify \
  -H "Authorization: Bearer <token>"
```

2. Generate new token via UI: **User → API Access**

### 404 Not Found

**Symptoms:** Endpoint returns 404

**Check:**
1. Correct URL path (API routes start with `/api/`)
2. HTTP method (GET vs POST)
3. Blueprint registration in `factory.py`

### 503 Service Unavailable

**Symptoms:** Analyzer endpoints return 503

**Solution:** Start analyzer services:
```bash
python analyzer/analyzer_manager.py start
```

## Performance Issues

### Slow Analysis

**Possible causes:**
1. Large codebase - consider tool filtering
2. Container resource limits - increase in `docker-compose.yml`
3. Network latency - check Docker networking

**Solutions:**
```bash
# Run fewer tools
python analyzer/analyzer_manager.py analyze model 1 static --tools bandit

# Increase resources (docker-compose.yml)
services:
  static-analyzer:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2.0'
```

### High Memory Usage

**Solutions:**
1. Limit concurrent analyses
2. Reduce container memory limits
3. Enable swap (not recommended for production)

## Log Locations

| Component | Location |
|-----------|----------|
| Flask | `logs/app.log` |
| Analyzers | `docker logs <container>` |
| Tasks | Database + `logs/app.log` |

## Recovery Commands

```bash
# Reset everything
./start.ps1 -Mode Stop
docker system prune -f
./start.ps1 -Mode CleanRebuild
./start.ps1 -Mode Start

# Reset database (WARNING: data loss)
rm src/data/thesis_app.db
python src/init_db.py

# Fix task statuses
python scripts/fix_task_statuses.py

# Sync generated apps
python scripts/sync_generated_apps.py
```

## Getting Help

1. Check logs first: `./start.ps1 -Mode Logs`
2. Review [Architecture](ARCHITECTURE.md) for component relationships
3. Search existing issues on GitHub
4. Create new issue with:
   - Error message
   - Steps to reproduce
   - Environment details (OS, Python version, Docker version)
