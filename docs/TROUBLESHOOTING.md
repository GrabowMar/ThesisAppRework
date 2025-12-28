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

### Circuit Breaker Triggered

**Symptoms:** Requests to a service fail immediately with "Service in cooldown"

**Cause:** After 3 consecutive connection failures, the circuit breaker opens for 5 minutes.

**Solutions:**
1. Wait for cooldown to expire (5 minutes)
2. Fix the underlying service issue and restart:
```bash
# Check service health
python analyzer/analyzer_manager.py health

# Restart problematic service
docker restart static-analyzer

# Force rebuild if needed
./start.ps1 -Mode Rebuild
```

**Recovery:** After cooldown, the circuit breaker enters "half-open" state and tests the connection. If successful, normal operation resumes.

### Pre-flight Check Failed

**Symptoms:** Analysis fails before starting with "Services unavailable"

**Cause:** System performs TCP port checks and WebSocket handshake before analysis.

**Automatic Recovery (December 2025):** Tasks that fail pre-flight checks are now automatically retried up to 3 times with exponential backoff (30s, 60s, 120s). If services become available within this window, the task will succeed without manual intervention.

**Diagnosis:**
```bash
# Check which services are down
python analyzer/analyzer_manager.py health

# Check individual ports
# Windows
Test-NetConnection -ComputerName localhost -Port 2001
Test-NetConnection -ComputerName localhost -Port 2002
Test-NetConnection -ComputerName localhost -Port 2003
Test-NetConnection -ComputerName localhost -Port 2004
```

**Manual Solution (if auto-retry exhausted):**
```bash
# Start all services
python analyzer/analyzer_manager.py start

# Wait a few seconds for startup
Start-Sleep 5

# Verify
python analyzer/analyzer_manager.py health

# Re-run the failed analysis from the UI
```

**Configuration:**
```env
# Maximum pre-flight retry attempts (default: 3)
PREFLIGHT_MAX_RETRIES=3

# Maximum transient failure recovery attempts (default: 3)  
TRANSIENT_FAILURE_MAX_RETRIES=3
```

### Analysis Timeout

**Symptoms:** `Task exceeded timeout`

**Solution:** Increase timeouts in `.env`:
```
STATIC_ANALYSIS_TIMEOUT=1800
SECURITY_ANALYSIS_TIMEOUT=1800
PERFORMANCE_TIMEOUT=1800
AI_ANALYSIS_TIMEOUT=2400
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

**Automatic Recovery:** Tasks stuck >2 hours are automatically marked as FAILED by maintenance. Tasks stuck >15 minutes get up to 3 retry attempts.

**Manual Solution:**
```bash
# Fix stuck tasks
python scripts/fix_task_statuses.py

# Or run maintenance cleanup
./start.ps1 -Mode Maintenance
```

### PENDING Tasks Not Executing

**Symptoms:** Tasks stay in `PENDING` state

**Diagnosis:**
1. Check TaskExecutionService is running
2. Verify analyzer services are healthy

```bash
# Check service status
python -c "
from app.factory import create_app
from app.services.service_locator import ServiceLocator
app = create_app()
with app.app_context():
    service = ServiceLocator.get_task_execution_service()
    print(f'TaskExecutionService running: {service._running}')
    print(f'Current task: {service._current_task_id}')
"
```

**Solutions:**
1. Restart Flask application
2. Check for database lock issues
3. Verify poll interval: default is 5s (production) or 2s (test)

### PARTIAL_SUCCESS Status

**Symptoms:** Task shows PARTIAL_SUCCESS instead of COMPLETED

**Meaning:** Some subtasks succeeded, some failed. Common with multi-service analyses.

**Diagnosis:**
```bash
# Check subtask results in database
# Look for error_message on failed subtasks
```

**Action:** Review the failed subtasks and re-run specific tools if needed.

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

# Check service health
./start.ps1 -Mode Health

# Manual maintenance cleanup (7-day grace period for orphan apps)
./start.ps1 -Mode Maintenance

# Full wipeout (WARNING: removes all data)
./start.ps1 -Mode Wipeout

# Reset admin password
./start.ps1 -Mode Password

# Reset database (WARNING: data loss)
rm src/data/thesis_app.db
python src/init_db.py

# Fix task statuses
python scripts/fix_task_statuses.py

# Sync generated apps to database
python scripts/sync_generated_apps.py

# Add missing_since column (one-time migration)
python scripts/add_missing_since_column.py
```

## Maintenance Service

### Understanding the 7-Day Grace Period

As of Nov 2025, orphan apps (database records without filesystem directories) are not immediately deleted:

1. **First detection**: App marked with `missing_since` timestamp
2. **Grace period**: 7 days to restore the directory
3. **Auto-restore**: If directory reappears, `missing_since` is cleared
4. **Deletion**: Only after 7 days of being missing

### Running Maintenance Manually

```bash
# Recommended: Use orchestrator
./start.ps1 -Mode Maintenance

# This performs:
# - Marks newly missing apps
# - Restores apps whose directories reappeared
# - Deletes apps missing >7 days
# - Cancels orphan tasks
# - Marks stuck tasks as FAILED
# - Deletes old completed tasks (>30 days)
```

### Maintenance Logs

Check `logs/app.log` for maintenance output:
```
[MaintenanceService] Marked 2 apps as missing (grace period: 7 days)
[MaintenanceService] Restored 1 apps (filesystem directories reappeared)
[MaintenanceService] Found 1 orphan apps ready for deletion (missing for >7 days)
```

## Getting Help

1. Check logs first: `./start.ps1 -Mode Logs`
2. Run health check: `python analyzer/analyzer_manager.py health`
3. Review [Architecture](ARCHITECTURE.md) for component relationships
4. Check [Background Services](BACKGROUND_SERVICES.md) for service-specific debugging
5. Search existing issues on GitHub
6. Create new issue with:
   - Error message
   - Steps to reproduce
   - Environment details (OS, Python version, Docker version)
