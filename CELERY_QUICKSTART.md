# Celery Pipeline Quick Start Guide

## 🎯 What Was Fixed

### Previous Issues
- ❌ **Sequential Execution**: 4 subtasks ran one-by-one (15-20 min total)
- ❌ **No Results**: Hard-coded suppression + persist=False
- ❌ **Solo Pool**: Celery could only process 1 task at a time
- ❌ **Concurrency=1**: Blocked parallel execution

### Current Configuration
- ✅ **Parallel Execution**: All 4 subtasks run simultaneously via Celery chord()
- ✅ **Results Enabled**: persist=True, no suppression, SINGLE_FILE_RESULTS=0
- ✅ **Thread Pool**: Windows-compatible parallel processing
- ✅ **Concurrency=8**: Up to 8 simultaneous subtasks

## 🚀 Quick Start

### 1. Test the Pipeline (RECOMMENDED FIRST STEP)
```powershell
.\test_celery_pipeline.ps1
```
This runs 8 comprehensive tests:
- ✅ Redis connectivity
- ✅ Analyzer container health
- ✅ Celery worker status
- ✅ Task imports and engines
- ✅ Database connectivity

### 2. Start Celery Worker
```powershell
# Simple start
.\start_celery_worker.ps1

# Restart existing workers
.\start_celery_worker.ps1 -Restart

# Debug mode
.\start_celery_worker.ps1 -Debug

# Custom concurrency
.\start_celery_worker.ps1 -Concurrency 12
```

### 3. Start Full Application
```powershell
# Option A: Use integrated start script (starts Celery + Flask + Analyzers)
.\start.ps1 start

# Option B: Manual start (separate terminals)
# Terminal 1: Start Celery worker
.\start_celery_worker.ps1 -Restart

# Terminal 2: Start Flask app
cd src
python main.py
```

### 4. Verify Parallel Execution
Navigate to: http://localhost:5000/analysis

Create a unified analysis for any model/app combination. You should see:
- ✅ All 4 subtasks go to "Running" simultaneously
- ✅ Progress: 0% → 25% → 50% → 75% → 100%
- ✅ Results appear in `results/<model>/app<N>/`

## 📋 Configuration Details

### Celery Worker Settings
**File**: `src/config/celery_config.py`
```python
CELERY_WORKER_POOL = 'threads'  # Windows-compatible
CELERY_WORKER_CONCURRENCY = 8   # 8 simultaneous tasks
```

### Task Routing
- **Queues**: celery, subtasks, aggregation, monitoring
- **Subtasks**: 
  - `run_static_analyzer_subtask` → subtasks queue
  - `run_dynamic_analyzer_subtask` → subtasks queue
  - `run_performance_tester_subtask` → subtasks queue
  - `run_ai_analyzer_subtask` → subtasks queue
  - `aggregate_subtask_results` → aggregation queue

### Parallel Execution Flow
```
Main Task (execute_unified_analysis_task)
    ↓
Celery Chord:
    ├─→ run_static_analyzer_subtask (5 min)     ─┐
    ├─→ run_dynamic_analyzer_subtask (5 min)    ├─ Run in parallel
    ├─→ run_performance_tester_subtask (5 min)  │  (~5 min total)
    └─→ run_ai_analyzer_subtask (5 min)        ─┘
           ↓
    aggregate_subtask_results (merge all findings)
           ↓
    Main Task Complete (100%)
```

## 🔧 Updated Scripts

### start.ps1
- **Changed**: Celery worker uses `app.tasks` module, thread pool, concurrency=8
- **Usage**: `.\start.ps1 start` (auto-starts with new config)

### start_celery_worker.ps1 (NEW)
- **Purpose**: Standalone Celery worker launcher
- **Features**: 
  - Verifies Redis connection
  - Kills existing workers (with -Restart)
  - Shows configuration details
  - Runs in foreground for visibility

### test_celery_pipeline.ps1 (NEW)
- **Purpose**: Comprehensive pipeline validation
- **Tests**: 8 checks covering Redis, Docker, Celery, DB, Engines, Tasks

### docker-deploy.sh
- **Changed**: Added `test-celery` command for container-based testing
- **Usage**: `./docker-deploy.sh test-celery`

### rebuild_analyzers.ps1
- **Changed**: Shows Celery configuration info after rebuild
- **Usage**: `.\rebuild_analyzers.ps1` (unchanged)

## 🐛 Troubleshooting

### Problem: Only 1 subtask running
**Cause**: Old Celery worker with solo pool
**Fix**: 
```powershell
# Kill old workers
Get-Process | Where-Object { $_.ProcessName -like "*celery*" } | Stop-Process -Force

# Start new worker
.\start_celery_worker.ps1 -Restart
```

### Problem: No results generated
**Check**:
1. `.env` has `SINGLE_FILE_RESULTS=0`
2. `analyzer_manager.py` line 1027: "RESULT PERSISTENCE ENABLED"
3. `orchestrator.py` line 304: `single_file_mode = False`

### Problem: Tasks stuck in "Pending"
**Check**:
1. Redis running: `docker ps | Select-String "redis"`
2. Celery worker active: `cd src; python -c "from app.tasks import celery; print(celery.control.inspect().active())"`
3. All analyzers healthy: `docker ps | Select-String "analyzer"`

### Problem: Unicode errors in console
**Fix**: Windows console encoding issue (cosmetic, doesn't affect execution)
```powershell
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
```

## 📊 Expected Results

### Timeline
- **Before**: 15-20 minutes (4 × 5 min sequential)
- **After**: ~5 minutes (parallel execution)

### Progress Updates
```
Main Task: "Unified Analysis"
├─ Status: Running 0%
├─ Subtasks:
│  ├─ Static Analyzer: Running 35% ✅
│  ├─ Dynamic Analyzer: Running 42% ✅
│  ├─ Performance Tester: Running 28% ✅
│  └─ AI Analyzer: Running 15% ✅
└─ Status: Running 45% (overall progress)
```

### Result Files
```
results/
└── google_gemini-2.5-flash/
    └── app3/
        ├── static-analyzer/
        │   ├── bandit_results.json
        │   ├── safety_results.json
        │   └── ... (other tool results)
        ├── dynamic-analyzer/
        ├── performance-tester/
        ├── ai-analyzer/
        └── unified_analysis_results.json
```

## 🎓 Next Steps

1. **Run Test**: `.\test_celery_pipeline.ps1`
2. **Start Worker**: `.\start_celery_worker.ps1 -Restart`
3. **Start Flask**: `cd src; python main.py`
4. **Test Analysis**: http://localhost:5000/analysis
5. **Monitor Progress**: Watch all 4 subtasks run in parallel!

## 📚 Related Documentation

- **Celery Config**: `src/config/celery_config.py`
- **Task Definitions**: `src/app/tasks.py`
- **Task Service**: `src/app/services/task_execution_service.py`
- **Orchestrator**: `src/app/engines/orchestrator.py`
- **Analyzer Manager**: `analyzer/analyzer_manager.py`

---

**Last Updated**: October 26, 2025  
**Status**: ✅ Ready for parallel execution testing
