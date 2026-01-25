# Fix for Analysis Task Failures

## Problem
Analysis tasks are failing because the Celery worker container is not running. Tasks are being dispatched to Celery but no workers are available to process them.

## Root Cause
- Tasks are created and dispatched via Celery chord (parallel execution)
- The `celery-worker` container defined in docker-compose.yml is not running
- Without workers, tasks remain in RUNNING state indefinitely

## Solution

### Step 1: Start the Celery Worker

From the project root directory, run:

```bash
docker compose up -d celery-worker redis
```

This will start:
- `redis`: Message broker for Celery
- `celery-worker`: Worker process that executes analysis tasks

### Step 2: Verify the Worker is Running

Check that the containers are up:

```bash
docker compose ps
```

You should see both `redis` and `celery-worker` with status "Up".

### Step 3: Monitor Worker Logs

Watch the worker logs to see it processing tasks:

```bash
docker compose logs -f celery-worker
```

You should see output like:
```
[tasks]
  . app.tasks.aggregate_results
  . app.tasks.execute_analysis
  . app.tasks.execute_subtask

celery@... ready.
```

### Step 4: Restart Failed Tasks

The TaskExecutionService has auto-recovery that will:
1. Detect tasks stuck in RUNNING state for > 15 minutes
2. Reset them to PENDING for retry
3. Automatically execute them when workers are available

Alternatively, manually restart failed tasks through the UI or API.

## Alternative: Use In-Process Execution (Development Only)

If you don't want to use Celery, you can disable it:

1. Edit `.env` or environment variables:
   ```
   USE_CELERY_ANALYSIS=false
   ```

2. Restart the web application

Tasks will then execute in-process using ThreadPoolExecutor instead of Celery.
**Note**: This is not recommended for production as it limits concurrency and scalability.

## Verification

After starting the worker, create a new analysis task and check:

1. Worker logs show task execution
2. Task status changes from PENDING → RUNNING → COMPLETED
3. Results appear in the UI
4. No tasks remain stuck in RUNNING state

## Additional Diagnostics

### Check Redis Connection
```bash
docker compose exec web python -c "import redis; r = redis.from_url('redis://redis:6379/0'); print('Redis OK:', r.ping())"
```

### Check Celery Worker Health
```bash
docker compose exec celery-worker celery -A app.celery_worker.celery inspect ping
```

### View Active Tasks
```bash
docker compose exec celery-worker celery -A app.celery_worker.celery inspect active
```

## Architecture Overview

```
┌─────────────────┐
│   Web App       │
│  (Flask)        │
└────────┬────────┘
         │ Dispatches tasks
         ↓
┌─────────────────┐      ┌──────────────┐
│     Redis       │◄─────┤Celery Worker │
│  (Task Queue)   │      │ (Executor)   │
└─────────────────┘      └──────┬───────┘
                                │ Calls via WebSocket
                                ↓
                    ┌───────────────────────┐
                    │  Analyzer Services    │
                    │  - static-analyzer    │
                    │  - dynamic-analyzer   │
                    │  - ai-analyzer        │
                    │  - performance-tester │
                    └───────────────────────┘
```

Without the Celery worker, tasks get queued in Redis but never execute.
