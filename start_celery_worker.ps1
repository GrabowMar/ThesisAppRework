#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start Celery Worker with Proper Configuration
    
.DESCRIPTION
    Starts Celery worker with thread pool for Windows compatibility
    and parallel subtask execution support.
#>

param(
    [switch]$Debug,
    [switch]$Restart,
    [int]$Concurrency = 8
)

Write-Host "🚀 Starting Celery Worker for Analysis System" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

# Get script root directory
$ROOT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$SRC_DIR = Join-Path $ROOT_DIR "src"

# Check Redis
Write-Host "`n📦 Checking Redis connection..." -ForegroundColor Yellow
try {
    $redisRunning = docker ps --filter "name=redis" --filter "status=running" --format "{{.Names}}" | Select-String "redis"
    if ($redisRunning) {
        Write-Host "✅ Redis is running: $redisRunning" -ForegroundColor Green
    } else {
        Write-Host "❌ Redis is not running!" -ForegroundColor Red
        Write-Host "   Start Redis with: docker run -d --name redis -p 6379:6379 redis:alpine" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "❌ Failed to check Redis: $_" -ForegroundColor Red
    exit 1
}

# Stop existing Celery workers
if ($Restart) {
    Write-Host "`n🛑 Stopping existing Celery workers..." -ForegroundColor Yellow
    Get-Process | Where-Object { $_.ProcessName -like "*celery*" -or $_.CommandLine -like "*celery*" } | ForEach-Object {
        Write-Host "  Killing process $($_.Id): $($_.ProcessName)" -ForegroundColor Gray
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

# Navigate to src directory
if (-not (Test-Path $SRC_DIR)) {
    Write-Host "❌ Source directory not found: $SRC_DIR" -ForegroundColor Red
    exit 1
}

Push-Location $SRC_DIR

try {
    Write-Host "`n⚙️  Celery Configuration:" -ForegroundColor Cyan
    Write-Host "  Pool:        threads (Windows compatible)" -ForegroundColor White
    Write-Host "  Concurrency: $Concurrency workers" -ForegroundColor White
    Write-Host "  Queues:      celery, subtasks, aggregation, monitoring" -ForegroundColor White
    Write-Host "  Log Level:   $(if ($Debug) { 'debug' } else { 'info' })" -ForegroundColor White
    
    $logLevel = if ($Debug) { "debug" } else { "info" }
    
    # Check for Python
    $pythonCmd = $null
    $venvPython = Join-Path $ROOT_DIR ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $pythonCmd = $venvPython
        Write-Host "  Python:      .venv (virtual environment)" -ForegroundColor White
    } else {
        try {
            python --version 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $pythonCmd = "python"
                Write-Host "  Python:      system" -ForegroundColor White
            }
        } catch { }
    }
    
    if (-not $pythonCmd) {
        Write-Host "`n❌ Python not found. Please install Python or activate virtual environment" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "`n🔧 Starting Celery worker..." -ForegroundColor Yellow
    Write-Host "   Command: $pythonCmd -m celery -A app.tasks worker --pool=threads --concurrency=$Concurrency --loglevel=$logLevel" -ForegroundColor Gray
    
    # Start Celery worker in foreground for visibility
    & $pythonCmd -m celery -A app.tasks worker --pool=threads --concurrency=$Concurrency --loglevel=$logLevel
    
} catch {
    Write-Host "`n❌ Failed to start Celery worker: $_" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}
