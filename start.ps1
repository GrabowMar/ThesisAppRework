#!/usr/bin/env pwsh
# ThesisApp Startup Script
# ========================
# Comprehensive startup script for ThesisApp with Flask + Celery + Analyzer microservices

param(
    [Parameter(Position = 0, HelpMessage = "Startup mode: start, flask-only, celery-only, analyzer-only, dev, stop, restart, status, logs")]
    [ValidateSet("start", "flask-only", "celery-only", "analyzer-only", "dev", "stop", "restart", "status", "help", "logs")]
    [string]$Mode = "start",
    
    [Parameter(HelpMessage = "Flask host (default: 127.0.0.1)")]
    [string]$FlaskHost = "127.0.0.1",
    
    [Parameter(HelpMessage = "Flask port (default: 5000)")]
    [int]$Port = 5000,
    
    [Parameter(HelpMessage = "Environment: development, production, testing")]
    [ValidateSet("development", "production", "testing")]
    [string]$Environment = "development",
    
    [Parameter(HelpMessage = "Enable debug mode")]
    [switch]$DebugMode,
    
    [Parameter(HelpMessage = "Start in background")]
    [switch]$Background,
    
    [Parameter(HelpMessage = "Skip analyzer services")]
    [switch]$NoAnalyzer,
    
    [Parameter(HelpMessage = "Verbose output")]
    [switch]$VerboseOutput,
    
    [Parameter(HelpMessage = "Which logs to show when Mode=logs: all, flask, celery, analyzer")]
    [ValidateSet("all", "flask", "celery", "analyzer")]
    [string]$Logs = "all",
    
    [Parameter(HelpMessage = "Skip automatic container restart (containers will be restarted by default)")]
    [switch]$NoRestart
)

# Script configuration
$ROOT_DIR = $PSScriptRoot
$SRC_DIR = Join-Path $ROOT_DIR "src"
$ANALYZER_DIR = Join-Path $ROOT_DIR "analyzer"
$LOGS_DIR = Join-Path $ROOT_DIR "logs"
$RUN_DIR = Join-Path $ROOT_DIR "run"

# Ensure directories exist
@($LOGS_DIR, $RUN_DIR) | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Path $_ -Force | Out-Null
    }
}

# PID file paths
$FLASK_PID = Join-Path $RUN_DIR "flask.pid"
$CELERY_PID = Join-Path $RUN_DIR "celery.pid"
$ANALYZER_PID = Join-Path $RUN_DIR "analyzer.pid"

# Log file paths
$FLASK_LOG = Join-Path $LOGS_DIR "app.log"
$CELERY_LOG = Join-Path $LOGS_DIR "celery_worker.log"
$ANALYZER_LOG = Join-Path $LOGS_DIR "analyzer.log"

function Write-Header {
    param([string]$Title)
    
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ $($Title.PadRight(76)) ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Status {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    
    if ($VerboseOutput) {
        Write-Host "$(Get-Date -Format 'HH:mm:ss') | $Message" -ForegroundColor $Color
    }
}

function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Get-ProcessByPidFile {
    param([string]$PidFile)
    
    if (Test-Path $PidFile) {
        try {
            $processId = Get-Content $PidFile -ErrorAction Stop
            $process = Get-Process -Id $processId -ErrorAction Stop
            return $process
        } catch {
            # PID file exists but process is gone
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
            return $null
        }
    }
    return $null
}

function Stop-ServiceByPid {
    param(
        [string]$ServiceName,
        [string]$PidFile
    )
    
    $process = Get-ProcessByPidFile $PidFile
    if ($process) {
        Write-Status "Stopping $ServiceName (PID: $($process.Id))..." "Yellow"
        try {
            $process.Kill()
            $process.WaitForExit(5000)
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
            Write-Success "$ServiceName stopped"
        } catch {
            Write-Error "Failed to stop ${ServiceName}: $($_.Exception.Message)"
        }
    } else {
        Write-Status "$ServiceName is not running" "Gray"
    }
}

function Test-DockerRunning {
    try {
        docker info 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Test-PythonEnvironment {
    # Check if we're in a virtual environment or have Python available
    
    # Check for virtual environment
    $venvPython = Join-Path $ROOT_DIR ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        Write-Status "Found virtual environment at .venv" "Green"
        return $venvPython
    }
    
    # Check for system Python
    try {
        python --version 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Using system Python" "Yellow"
            return "python"
        }
    } catch { }
    
    Write-Error "Python not found. Please install Python or activate virtual environment"
    return $null
}

function Start-FlaskApp {
    Write-Status "Starting Flask application..." "Cyan"
    
    $pythonCmd = Test-PythonEnvironment
    if (-not $pythonCmd) {
        return $false
    }
    
    # Check if Flask is already running
    $existing = Get-ProcessByPidFile $FLASK_PID
    if ($existing) {
        Write-Warning "Flask app already running (PID: $($existing.Id))"
        return $true
    }
    
    # Set environment variables
    $env:FLASK_ENV = $Environment
    $env:HOST = $FlaskHost
    $env:PORT = $Port
    $env:DEBUG = if ($DebugMode) { "true" } else { "false" }
    
    # Ensure UTF-8 output for Python to avoid UnicodeEncodeError on Windows consoles
    # PYTHONUTF8 forces UTF-8 mode; PYTHONIOENCODING overrides stdio encoding explicitly.
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    try {
        # Also set the current PowerShell host encodings to UTF-8 where supported
        [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
        $OutputEncoding = [Console]::OutputEncoding
    } catch { }
    
    # Start Flask app
    $arguments = @(
        (Join-Path $SRC_DIR "main.py")
    )
    
    if ($Background) {
        Write-Status "Starting Flask in background mode..." "Cyan"
        $process = Start-Process -FilePath $pythonCmd -ArgumentList $arguments -WorkingDirectory $SRC_DIR -WindowStyle Hidden -PassThru -RedirectStandardOutput $FLASK_LOG -RedirectStandardError $FLASK_LOG
        $process.Id | Out-File -FilePath $FLASK_PID -Encoding ASCII
        Write-Success "Flask started in background (PID: $($process.Id))"
        Write-Host "   📝 Logs: $FLASK_LOG" -ForegroundColor Gray
        Write-Host "   🌐 URL: http://${FlaskHost}:${Port}" -ForegroundColor Gray
    } else {
        Write-Success "Starting Flask in foreground mode..."
        Write-Host "   🌐 URL: http://${FlaskHost}:${Port}" -ForegroundColor Gray
        Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
        Write-Host ""
        & $pythonCmd @arguments
    }
    
    return $true
}

function Start-CeleryWorker {
    Write-Status "Starting Celery worker..." "Cyan"
    
    $pythonCmd = Test-PythonEnvironment
    if (-not $pythonCmd) {
        return $false
    }
    
    # Check if Celery is already running
    $existing = Get-ProcessByPidFile $CELERY_PID
    if ($existing) {
        Write-Warning "Celery worker already running (PID: $($existing.Id))"
        return $true
    }
    
    # Start Celery worker
    $arguments = @(
        "-m", "celery",
        "-A", "worker.celery",
        "worker",
        "--loglevel=info",
        "--logfile=$CELERY_LOG"
    )
    
    Write-Status "Starting Celery worker in background..." "Cyan"
    $process = Start-Process -FilePath $pythonCmd -ArgumentList $arguments -WorkingDirectory $SRC_DIR -WindowStyle Hidden -PassThru
    $process.Id | Out-File -FilePath $CELERY_PID -Encoding ASCII
    Write-Success "Celery worker started (PID: $($process.Id))"
    Write-Host "   📝 Logs: $CELERY_LOG" -ForegroundColor Gray
    
    return $true
}

function Restart-AnalyzerContainers {
    Write-Status "Restarting analyzer containers for reliability..." "Cyan"
    
    if (-not (Test-DockerRunning)) {
        Write-Error "Docker is not running. Cannot restart containers"
        return $false
    }
    
    Push-Location $ANALYZER_DIR
    
    try {
        # Restart all services to clear any stale state
        Write-Status "Restarting Docker Compose services..." "Yellow"
        docker-compose restart 2>&1 | Out-File -FilePath $ANALYZER_LOG -Append
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Analyzer containers restarted successfully"
            
            # Wait a moment for services to stabilize
            Write-Status "Waiting for services to stabilize..." "Gray"
            Start-Sleep -Seconds 3
            
            return $true
        } else {
            Write-Warning "Container restart failed, will try normal startup"
            return $false
        }
    } catch {
        Write-Warning "Error during container restart: $_"
        return $false
    } finally {
        Pop-Location
    }
}

function Start-AnalyzerServices {
    if ($NoAnalyzer) {
        Write-Status "Skipping analyzer services (--NoAnalyzer flag)" "Yellow"
        return $true
    }
    
    Write-Status "Starting analyzer services..." "Cyan"
    
    # Check Docker
    if (-not (Test-DockerRunning)) {
        Write-Error "Docker is not running. Please start Docker Desktop"
        Write-Host "   Analyzer services require Docker containers" -ForegroundColor Gray
        return $false
    }
    
    # Navigate to analyzer directory
    Push-Location $ANALYZER_DIR
    
    try {
        # Check if analyzer services are already running
        $existingServices = docker-compose ps --services --filter status=running 2>$null
        $shouldRestart = $false
        
        if ($existingServices) {
            Write-Warning "Some analyzer services already running:"
            $existingServices | ForEach-Object {
                Write-Host "   • $_" -ForegroundColor Yellow
            }
            $shouldRestart = $true
        }
        
        # Restart containers by default for reliability (unless --NoRestart flag is used)
        if ((-not $NoRestart) -and ($shouldRestart -or $existingServices)) {
            Write-Status "Restarting containers for better reliability..." "Cyan"
            Pop-Location
            $restartSuccess = Restart-AnalyzerContainers
            Push-Location $ANALYZER_DIR
            
            if ($restartSuccess) {
                # Services already restarted, just verify status
                Write-Success "Analyzer services restarted and ready"
                
                # Save analyzer PID (use Docker Compose project)
                "analyzer-compose" | Out-File -FilePath $ANALYZER_PID -Encoding ASCII
                
                # Show service status
                Write-Host "   📊 Services status:" -ForegroundColor Gray
                docker-compose ps --format "table {{.Service}}\t{{.State}}\t{{.Ports}}" | ForEach-Object {
                    if ($_ -notmatch "SERVICE|---") {
                        Write-Host "     $_" -ForegroundColor Gray
                    }
                }
                
                Write-Host "   📝 Logs: $ANALYZER_LOG" -ForegroundColor Gray
                Write-Host "   🔗 Gateway: ws://localhost:8765" -ForegroundColor Gray
                return $true
            } else {
                Write-Warning "Container restart failed, continuing with normal startup..."
            }
        } else {
            if ($NoRestart) {
                Write-Status "Skipping automatic restart (--NoRestart flag)" "Yellow"
            }
        }
        
        # Start analyzer services
        Write-Status "Starting Docker Compose services..." "Cyan"
        docker-compose up -d 2>&1 | Out-File -FilePath $ANALYZER_LOG -Append
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Analyzer services started"
            
            # Save analyzer PID (use Docker Compose project)
            "analyzer-compose" | Out-File -FilePath $ANALYZER_PID -Encoding ASCII
            
            # Show service status
            Write-Host "   📊 Services status:" -ForegroundColor Gray
            docker-compose ps --format "table {{.Service}}\t{{.State}}\t{{.Ports}}" | ForEach-Object {
                if ($_ -notmatch "SERVICE|---") {
                    Write-Host "     $_" -ForegroundColor Gray
                }
            }
            
            Write-Host "   📝 Logs: $ANALYZER_LOG" -ForegroundColor Gray
            Write-Host "   🔗 Gateway: ws://localhost:8765" -ForegroundColor Gray
            return $true
        } else {
            Write-Error "Failed to start analyzer services"
            Write-Host "   Check logs: docker-compose logs" -ForegroundColor Gray
            return $false
        }
    } finally {
        Pop-Location
    }
}

function Stop-AnalyzerServices {
    Write-Status "Stopping analyzer services..." "Yellow"
    
    if (-not (Test-DockerRunning)) {
        Write-Warning "Docker is not running"
        Remove-Item $ANALYZER_PID -Force -ErrorAction SilentlyContinue
        return
    }
    
    Push-Location $ANALYZER_DIR
    
    try {
        docker-compose down 2>&1 | Out-File -FilePath $ANALYZER_LOG -Append
        Remove-Item $ANALYZER_PID -Force -ErrorAction SilentlyContinue
        Write-Success "Analyzer services stopped"
    } catch {
        Write-Error "Error stopping analyzer services: $_"
    } finally {
        Pop-Location
    }
}

function Show-Status {
    Write-Header "ThesisApp Services Status"
    
    # Flask status
    $flaskProcess = Get-ProcessByPidFile $FLASK_PID
    if ($flaskProcess) {
        Write-Host "🌐 Flask App: " -NoNewline -ForegroundColor White
        Write-Host "Running (PID: $($flaskProcess.Id))" -ForegroundColor Green
        Write-Host "   📍 URL: http://${FlaskHost}:${Port}" -ForegroundColor Gray
    } else {
        Write-Host "🌐 Flask App: " -NoNewline -ForegroundColor White
        Write-Host "Stopped" -ForegroundColor Red
    }
    
    # Celery status
    $celeryProcess = Get-ProcessByPidFile $CELERY_PID
    if ($celeryProcess) {
        Write-Host "⚙️  Celery Worker: " -NoNewline -ForegroundColor White
        Write-Host "Running (PID: $($celeryProcess.Id))" -ForegroundColor Green
    } else {
        Write-Host "⚙️  Celery Worker: " -NoNewline -ForegroundColor White
        Write-Host "Stopped" -ForegroundColor Red
    }
    
    # Analyzer services status
    Write-Host "🔍 Analyzer Services: " -NoNewline -ForegroundColor White
    
    if (Test-DockerRunning) {
        Push-Location $ANALYZER_DIR -ErrorAction SilentlyContinue
        
        try {
            $services = docker-compose ps --services --filter status=running 2>$null
            if ($services) {
                Write-Host "Running" -ForegroundColor Green
                $services | ForEach-Object {
                    Write-Host "   • $_" -ForegroundColor Gray
                }
            } else {
                Write-Host "Stopped" -ForegroundColor Red
            }
        } catch {
            Write-Host "Error" -ForegroundColor Red
        } finally {
            Pop-Location -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "Docker not running" -ForegroundColor Red
    }
    
    # System info
    Write-Host ""
    Write-Host "🔧 System Information:" -ForegroundColor Cyan
    Write-Host "   Environment: $Environment" -ForegroundColor Gray
    Write-Host "   Python: $(Test-PythonEnvironment)" -ForegroundColor Gray
    Write-Host "   Docker: $(if (Test-DockerRunning) { 'Available' } else { 'Not available' })" -ForegroundColor Gray
    Write-Host "   Logs Directory: $LOGS_DIR" -ForegroundColor Gray
}

function Show-Logs {
    param(
        [string]$Target = "all"
    )

    Write-Header "ThesisApp Logs"

    $follow = [bool]$Background
    $shown = $false

    function Show-OneLog {
        param(
            [string]$Name,
            [string]$Path
        )
        if (Test-Path $Path) {
            Write-Host "🔎 $Name log: $Path" -ForegroundColor Cyan
            if ($follow -and ($Target -ne 'all')) {
                try { Get-Content -Path $Path -Tail 100 -Wait } catch { }
            } else {
                try { Get-Content -Path $Path -Tail 200 | Write-Host -ForegroundColor Gray } catch { }
            }
        } else {
            Write-Warning "$Name log not found at $Path"
        }
    }

    if ($Target -eq 'all' -or $Target -eq 'flask') { Show-OneLog -Name 'Flask' -Path $FLASK_LOG; $shown = $true }
    if ($Target -eq 'all' -or $Target -eq 'celery') { Show-OneLog -Name 'Celery' -Path $CELERY_LOG; $shown = $true }
    if ($Target -eq 'all' -or $Target -eq 'analyzer') { Show-OneLog -Name 'Analyzer' -Path $ANALYZER_LOG; $shown = $true }

    if (-not $shown) {
        Write-Warning "No logs selected. Use -Logs all|flask|celery|analyzer"
    }

    if ($follow -and $Target -eq 'all') {
        Write-Host ""
        Write-Warning "Follow (-Background) works best with a single target (e.g., -Logs flask)."
    }
}

function Stop-AllServices {
    Write-Header "Stopping ThesisApp Services"
    
    Stop-ServiceByPid "Flask App" $FLASK_PID
    Stop-ServiceByPid "Celery Worker" $CELERY_PID
    Stop-AnalyzerServices
    
    Write-Success "All services stopped"
}

function Show-Help {
    Write-Header "ThesisApp Startup Script Help"
    
    Write-Host "USAGE:" -ForegroundColor Cyan
    Write-Host "  .\start.ps1 [MODE] [OPTIONS]" -ForegroundColor White
    Write-Host ""
    
    Write-Host "MODES:" -ForegroundColor Cyan
    Write-Host "  start        Start full stack (Flask + Celery + Analyzers)" -ForegroundColor White
    Write-Host "  flask-only   Start only Flask application" -ForegroundColor White
    Write-Host "  celery-only  Start only Celery worker" -ForegroundColor White
    Write-Host "  analyzer-only Start only analyzer services" -ForegroundColor White
    Write-Host "  dev          Development mode (Flask only, debug enabled)" -ForegroundColor White
    Write-Host "  stop         Stop all services" -ForegroundColor White
    Write-Host "  restart      Restart all services" -ForegroundColor White
    Write-Host "  status       Show services status" -ForegroundColor White
    Write-Host "  logs         Show recent logs (use -Logs to select)" -ForegroundColor White
    Write-Host "  help         Show this help" -ForegroundColor White
    Write-Host ""
    
    Write-Host "OPTIONS:" -ForegroundColor Cyan
    Write-Host "  -FlaskHost   Flask host (default: 127.0.0.1)" -ForegroundColor White
    Write-Host "  -Port        Flask port (default: 5000)" -ForegroundColor White
    Write-Host "  -Environment Environment: development, production, testing" -ForegroundColor White
    Write-Host "  -DebugMode   Enable debug mode" -ForegroundColor White
    Write-Host "  -Background  Start in background" -ForegroundColor White
    Write-Host "  -NoAnalyzer  Skip analyzer services" -ForegroundColor White
    Write-Host "  -NoRestart   Skip automatic container restart (containers restart by default)" -ForegroundColor White
    Write-Host "  -VerboseOutput Verbose output" -ForegroundColor White
    Write-Host "  -Logs        Which logs to show with Mode=logs: all, flask, celery, analyzer" -ForegroundColor White
    Write-Host ""
    
    Write-Host "EXAMPLES:" -ForegroundColor Cyan
    Write-Host "  .\start.ps1 start                    # Start full stack (containers auto-restart)" -ForegroundColor Gray
    Write-Host "  .\start.ps1 start -NoRestart         # Start without restarting containers" -ForegroundColor Gray
    Write-Host "  .\start.ps1 flask-only -Debug       # Start Flask in debug mode" -ForegroundColor Gray
    Write-Host "  .\start.ps1 start -Background       # Start all in background" -ForegroundColor Gray
    Write-Host "  .\start.ps1 dev                     # Development mode" -ForegroundColor Gray
    Write-Host "  .\start.ps1 logs                    # Show last 200 lines of all logs" -ForegroundColor Gray
    Write-Host "  .\start.ps1 logs -Logs flask        # Show Flask log (tail with -Background)" -ForegroundColor Gray
    Write-Host "  .\start.ps1 status                  # Check status" -ForegroundColor Gray
    Write-Host "  .\start.ps1 stop                    # Stop everything" -ForegroundColor Gray
    Write-Host ""
    
    Write-Host "LOGS:" -ForegroundColor Cyan
    Write-Host "  Flask:    $FLASK_LOG" -ForegroundColor Gray
    Write-Host "  Celery:   $CELERY_LOG" -ForegroundColor Gray
    Write-Host "  Analyzer: $ANALYZER_LOG" -ForegroundColor Gray
}

# Main execution logic
switch ($Mode) {
    "help" {
        Show-Help
        exit 0
    }
    
    "status" {
        Show-Status
        exit 0
    }
    
    "logs" {
        Show-Logs -Target $Logs
        exit 0
    }
    
    "stop" {
        Stop-AllServices
        exit 0
    }
    
    "restart" {
        Write-Header "Restarting ThesisApp Services"
        Stop-AllServices
        Start-Sleep -Seconds 2
        $Mode = "start"  # Continue to start logic
    }
}

# Start services based on mode
Write-Header "Starting ThesisApp - $Mode Mode"

switch ($Mode) {
    "start" {
        $success = $true
        
        # Start Celery worker first
        if (-not (Start-CeleryWorker)) {
            $success = $false
        }
        
        # Start analyzer services
        if (-not (Start-AnalyzerServices)) {
            $success = $false
            Write-Warning "Continuing without analyzer services..."
        }
        
        # Start Flask app (may be foreground or background)
        if (-not (Start-FlaskApp)) {
            $success = $false
        }
        
        if ($success -and $Background) {
            Write-Host ""
            Write-Success "ThesisApp started successfully in background!"
            Write-Host "Use '.\start.ps1 status' to check services" -ForegroundColor Gray
            Write-Host "Use '.\start.ps1 stop' to stop all services" -ForegroundColor Gray
        }
    }
    
    "flask-only" {
        Start-FlaskApp | Out-Null
    }
    
    "celery-only" {
        Start-CeleryWorker | Out-Null
        if (-not $Background) {
            Write-Host "Celery worker started. Press Ctrl+C to stop" -ForegroundColor Gray
            try {
                while ($true) {
                    Start-Sleep -Seconds 1
                }
            } catch {
                Stop-ServiceByPid "Celery Worker" $CELERY_PID
            }
        }
    }
    
    "analyzer-only" {
        Start-AnalyzerServices | Out-Null
        if (-not $Background) {
            Write-Host "Analyzer services started. Press Ctrl+C to stop" -ForegroundColor Gray
            try {
                while ($true) {
                    Start-Sleep -Seconds 1
                }
            } catch {
                Stop-AnalyzerServices
            }
        }
    }
    
    "dev" {
        # Development mode: Flask only with debug
        $DebugMode = $true
        $Environment = "development"
        Write-Host "🚀 Development Mode: Flask with debug enabled" -ForegroundColor Cyan
        Start-FlaskApp | Out-Null
    }
    
    default {
        Write-Error "Unknown mode: $Mode"
        Write-Host "Use '.\start.ps1 help' for usage information" -ForegroundColor Gray
        exit 1
    }
}
