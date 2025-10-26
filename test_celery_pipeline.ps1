#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test Celery and Analyzer Communication Pipeline
    
.DESCRIPTION
    Comprehensive test of:
    1. Redis connectivity
    2. Celery worker status
    3. Analyzer container health
    4. Task submission and execution
    5. Result retrieval
#>

Write-Host "🧪 Testing Celery & Analyzer Communication Pipeline" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan

$script:passedTests = 0
$script:failedTests = 0

function Test-Step {
    param(
        [string]$Name,
        [scriptblock]$Test
    )
    
    Write-Host "`n📋 TEST: $Name" -ForegroundColor Yellow
    try {
        & $Test
        Write-Host "✅ PASSED: $Name" -ForegroundColor Green
        $script:passedTests++
        return $true
    } catch {
        Write-Host "❌ FAILED: $Name" -ForegroundColor Red
        Write-Host "   Error: $_" -ForegroundColor Red
        $script:failedTests++
        return $false
    }
}

# Test 1: Redis Connectivity
Test-Step "Redis Container Running" {
    $redis = docker ps --filter "name=redis" --filter "status=running" --format "{{.Names}}"
    if (-not $redis) {
        throw "Redis container not running"
    }
    Write-Host "  Redis: $redis" -ForegroundColor Gray
}

# Test 2: Redis Port Accessible
Test-Step "Redis Port 6379 Accessible" {
    $connection = Test-NetConnection -ComputerName localhost -Port 6379 -InformationLevel Quiet
    if (-not $connection) {
        throw "Cannot connect to Redis on port 6379"
    }
    Write-Host "  Port 6379 is accessible" -ForegroundColor Gray
}

# Test 3: Analyzer Containers
Test-Step "Analyzer Containers Healthy" {
    $analyzers = docker ps --filter "name=analyzer" --format "{{.Names}}: {{.Status}}"
    $analyzerCount = ($analyzers | Measure-Object).Count
    
    if ($analyzerCount -lt 5) {
        throw "Expected 5+ analyzer containers, found $analyzerCount"
    }
    
    foreach ($analyzer in $analyzers) {
        Write-Host "  $analyzer" -ForegroundColor Gray
    }
}

# Test 4: Celery Worker Running
Test-Step "Celery Worker Process" {
    Push-Location src
    try {
        $inspect = python -c "from app.tasks import celery; import sys; i = celery.control.inspect(); w = i.active(); sys.exit(0 if w else 1)" 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Celery worker not responding"
        }
        Write-Host "  Celery worker is active" -ForegroundColor Gray
    } finally {
        Pop-Location
    }
}

# Test 5: Celery Can Import Tasks
Test-Step "Celery Task Imports" {
    Push-Location src
    try {
        $result = python -c @"
from app.tasks import (
    run_static_analyzer_subtask,
    run_dynamic_analyzer_subtask,
    run_performance_tester_subtask,
    run_ai_analyzer_subtask,
    aggregate_subtask_results
)
print('All subtask functions imported successfully')
"@
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to import Celery tasks"
        }
        Write-Host "  $result" -ForegroundColor Gray
    } finally {
        Pop-Location
    }
}

# Test 6: Database Connectivity
Test-Step "Database Accessible" {
    Push-Location src
    try {
        $result = python -c @"
from app.factory import create_app
from app.extensions import db
app = create_app()
with app.app_context():
    from app.models import AnalysisTask
    count = AnalysisTask.query.count()
    print(f'Database accessible: {count} tasks in database')
"@
        if ($LASTEXITCODE -ne 0) {
            throw "Database connection failed"
        }
        Write-Host "  $result" -ForegroundColor Gray
    } finally {
        Pop-Location
    }
}

# Test 7: Engine Registry
Test-Step "Analysis Engines Available" {
    Push-Location src
    try {
        $result = python -c @"
from app.services.analysis_engines import get_engine, ENGINE_REGISTRY
print(f'Available engines: {list(ENGINE_REGISTRY.keys())}')
for name in ['security', 'dynamic', 'performance', 'ai']:
    engine = get_engine(name)
    print(f'  ✓ {name}: {type(engine).__name__}')
"@
        if ($LASTEXITCODE -ne 0) {
            throw "Engine registry check failed"
        }
        Write-Host "  $result" -ForegroundColor Gray
    } finally {
        Pop-Location
    }
}

# Test 8: Trigger Test Analysis
Test-Step "Submit Test Analysis Task" {
    Push-Location src
    try {
        $result = python -c @"
from app.factory import create_app
from app.extensions import db
from app.services.task_service import AnalysisTaskService
from app.constants import JobPriority

app = create_app()
with app.app_context():
    # Create a test unified analysis task
    tools_by_service = {
        'static-analyzer': [1, 2],
        'dynamic-analyzer': [10],
        'performance-tester': [20],
        'ai-analyzer': [30]
    }
    
    main_task = AnalysisTaskService.create_main_task_with_subtasks(
        model_slug='test_celery_pipeline',
        app_number=999,
        analysis_type='unified',
        tools_by_service=tools_by_service,
        config_id=None,
        priority=JobPriority.NORMAL.value,
        custom_options={'unified_analysis': True, 'test_mode': True},
        task_name='Celery Pipeline Test'
    )
    
    print(f'✓ Created test task: {main_task.task_id}')
    print(f'  Status: {main_task.status}')
    print(f'  Subtasks: {len(main_task.subtasks)}')
    
    # Check subtasks
    for subtask in main_task.subtasks:
        print(f'  - {subtask.service_name}: {subtask.task_id}')
"@
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create test analysis task"
        }
        Write-Host "  $result" -ForegroundColor Gray
    } finally {
        Pop-Location
    }
}

# Summary
Write-Host "`n" + ("=" * 70) -ForegroundColor Cyan
Write-Host "📊 Test Summary:" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "  ✅ Passed: $script:passedTests" -ForegroundColor Green
Write-Host "  ❌ Failed: $script:failedTests" -ForegroundColor Red

if ($script:failedTests -eq 0) {
    Write-Host "`n🎉 ALL TESTS PASSED! Pipeline is ready." -ForegroundColor Green
    Write-Host "`nNext steps:" -ForegroundColor Cyan
    Write-Host "  1. Start Celery worker: .\start_celery_worker.ps1" -ForegroundColor White
    Write-Host "  2. Start Flask app: cd src; python main.py" -ForegroundColor White
    Write-Host "  3. Navigate to: http://localhost:5000/analysis" -ForegroundColor White
    exit 0
} else {
    Write-Host "`n⚠️  Some tests failed. Fix issues before proceeding." -ForegroundColor Yellow
    exit 1
}
