#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start Parallel Analysis System with Celery Workers
    
.DESCRIPTION
    This script starts all required services for parallel subtask execution:
    - Redis (Celery broker)
    - Celery workers (4 concurrent tasks)
    - Flask application
    - Analyzer services (Docker containers)
    
.EXAMPLE
    .\start_parallel_analysis.ps1
#>

param(
    [switch]$SkipRedis,
    [switch]$SkipWorkers,
    [switch]$SkipAnalyzers,
    [int]$WorkerConcurrency = 4
)

Write-Host "🚀 Starting Parallel Analysis System" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Set environment variables
$env:SINGLE_FILE_RESULTS = "0"
Write-Host "✅ Set SINGLE_FILE_RESULTS=0 (enable result files)" -ForegroundColor Green

# Check if Redis is running
if (-not $SkipRedis) {
    Write-Host "`n📦 Checking Redis..." -ForegroundColor Yellow
    try {
        $redisRunning = docker ps --filter "name=redis" --filter "status=running" --format "{{.Names}}" | Select-String "redis"
        if (-not $redisRunning) {
            Write-Host "Starting Redis container..." -ForegroundColor Yellow
            docker run -d --name redis -p 6379:6379 redis:alpine
            Start-Sleep -Seconds 2
        }
        Write-Host "✅ Redis is running" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Failed to start Redis: $_" -ForegroundColor Red
        exit 1
    }
}

# Start analyzer services
if (-not $SkipAnalyzers) {
    Write-Host "`n🔧 Starting Analyzer Services..." -ForegroundColor Yellow
    Push-Location analyzer
    try {
        docker-compose up -d
        Write-Host "✅ Analyzer services started" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Failed to start analyzers: $_" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    finally {
        Pop-Location
    }
    Start-Sleep -Seconds 5
}

# Start Celery workers
if (-not $SkipWorkers) {
    Write-Host "`n👷 Starting Celery Workers (concurrency=$WorkerConcurrency)..." -ForegroundColor Yellow
    Push-Location src
    try {
        # Kill existing Celery workers
        Get-Process | Where-Object { $_.ProcessName -like "*celery*" } | Stop-Process -Force -ErrorAction SilentlyContinue
        
        # Start new workers in background
        Start-Process -FilePath "celery" -ArgumentList "-A app.tasks worker --loglevel=info --concurrency=$WorkerConcurrency" -WindowStyle Minimized
        Start-Sleep -Seconds 3
        Write-Host "✅ Celery workers started" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Failed to start Celery workers: $_" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    finally {
        Pop-Location
    }
}

# Display status
Write-Host "`n📊 System Status:" -ForegroundColor Cyan
Write-Host "─────────────────" -ForegroundColor Cyan

# Check Redis
try {
    $redisStatus = docker ps --filter "name=redis" --filter "status=running" --format "{{.Status}}"
    if ($redisStatus) {
        Write-Host "✅ Redis: $redisStatus" -ForegroundColor Green
    } else {
        Write-Host "❌ Redis: Not running" -ForegroundColor Red
    }
}
catch {
    Write-Host "❌ Redis: Error checking status" -ForegroundColor Red
}

# Check Analyzer services
try {
    $analyzerServices = docker-compose -f analyzer/docker-compose.yml ps --services
    $runningServices = docker-compose -f analyzer/docker-compose.yml ps --filter "status=running" --services
    Write-Host "✅ Analyzers: $(@($runningServices).Count)/$(@($analyzerServices).Count) running" -ForegroundColor $(if ($runningServices.Count -eq $analyzerServices.Count) { "Green" } else { "Yellow" })
}
catch {
    Write-Host "❌ Analyzers: Error checking status" -ForegroundColor Red
}

# Check Celery workers
try {
    $celeryProcesses = @(Get-Process | Where-Object { $_.ProcessName -like "*celery*" })
    if ($celeryProcesses.Count -gt 0) {
        Write-Host "✅ Celery: $($celeryProcesses.Count) worker process(es)" -ForegroundColor Green
    } else {
        Write-Host "❌ Celery: No workers running" -ForegroundColor Red
    }
}
catch {
    Write-Host "❌ Celery: Error checking status" -ForegroundColor Red
}

Write-Host "`n📝 Next Steps:" -ForegroundColor Cyan
Write-Host "──────────────" -ForegroundColor Cyan
Write-Host "1. Start Flask app:" -ForegroundColor White
Write-Host "   cd src && python main.py" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Trigger analysis:" -ForegroundColor White
Write-Host "   Navigate to http://localhost:5000/analysis" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Monitor logs:" -ForegroundColor White
Write-Host "   celery -A app.tasks events" -ForegroundColor Gray
Write-Host ""
Write-Host "4. View results:" -ForegroundColor White
Write-Host "   ls results/<model>/app<N>/" -ForegroundColor Gray

Write-Host "`n✅ System ready for parallel analysis!" -ForegroundColor Green
