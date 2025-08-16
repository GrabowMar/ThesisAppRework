# Thesis App Startup Script for Windows
# =====================================
# 
# PowerShell script for starting the Thesis App with Celery integration on Windows.

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "status", "worker-only", "beat-only", "flask-only")]
    [string]$Action = "start"
)

# Configuration
$FlaskApp = "main.py"
$CeleryApp = "app.tasks"
$RedisHost = if ($env:REDIS_HOST -and $env:REDIS_HOST.Trim() -ne '') { $env:REDIS_HOST } else { '127.0.0.1' }
$RedisPort = if ($env:REDIS_PORT -and $env:REDIS_PORT.Trim() -ne '') { $env:REDIS_PORT } else { '6379' }
# Default to Windows-safe Celery worker settings unless explicitly overridden
$WorkerConcurrency = if ($env:WORKER_CONCURRENCY -and $env:WORKER_CONCURRENCY.Trim() -ne '') { $env:WORKER_CONCURRENCY } else { "1" }
$UseSoloPool = if ($env:CELERY_POOL -and $env:CELERY_POOL.Trim() -ne '') { $env:CELERY_POOL -eq 'solo' } else { $true }

# Paths
$ScriptRoot = $PSScriptRoot
$RepoRoot = Split-Path -Parent $ScriptRoot

# Colors for output
$ColorMap = @{
    'Red' = 'Red'
    'Green' = 'Green'
    'Yellow' = 'Yellow'
    'Blue' = 'Blue'
    'Cyan' = 'Cyan'
}

function Write-Log {
    param([string]$Message, [string]$Color = 'Green')
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message" -ForegroundColor $ColorMap[$Color]
}

function Write-Error-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] ERROR: $Message" -ForegroundColor Red
}

function Write-Warning-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] WARNING: $Message" -ForegroundColor Yellow
}

function Write-Info-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] INFO: $Message" -ForegroundColor Blue
}

# Check if Redis is running
function Test-Redis {
    Write-Log "Checking Redis connection at ${RedisHost}:${RedisPort}..." "Blue"
    try {
        $tcp = Test-NetConnection -ComputerName $RedisHost -Port ([int]$RedisPort) -WarningAction SilentlyContinue -InformationLevel Quiet
        if ($tcp) {
            Write-Log "Redis TCP port reachable"
            return $true
        } else {
            Write-Error-Log "Redis not reachable at ${RedisHost}:${RedisPort}"
            return $false
        }
    } catch {
        Write-Error-Log "Redis check error: $_"
        return $false
    }
}

# Start Redis if not running
function Start-Redis {
    Write-Log "Starting Redis server..." "Blue"
    
    if (Get-Command redis-server -ErrorAction SilentlyContinue) {
        try {
            Start-Process redis-server -ArgumentList "--port", $RedisPort, "--bind", $RedisHost -WindowStyle Hidden
            Start-Sleep -Seconds 3
            
            if (Test-Redis) {
                Write-Log "Redis started successfully"
                return $true
            }
            else {
                Write-Error-Log "Failed to start Redis"
                return $false
            }
        }
        catch {
            Write-Error-Log "Error starting Redis: $_"
            return $false
        }
    }
    else {
        Write-Error-Log "Redis server not found. Please install Redis or use external Redis instance"
        return $false
    }
}

# Check dependencies
function Test-Dependencies {
    Write-Log "Checking dependencies..." "Blue"
    
    # Check Python
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Error-Log "Python not found"
        return $false
    }
    
    # Check pip packages
    try {
        python -c "import flask, celery, redis, sqlalchemy" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Log "Required Python packages not found. Run: pip install -r requirements.txt"
            return $false
        }
    }
    catch {
        Write-Error-Log "Error checking Python packages: $_"
        return $false
    }
    
    Write-Log "Dependencies check passed"
    return $true
}

# Initialize database
function Initialize-Database {
    Write-Log "Initializing database..." "Blue"
    try {
        # Prefer venv python when available
        $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
        $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }

        $initScript = @"
from app.factory import create_cli_app
from app.extensions import init_db

app = create_cli_app()
with app.app_context():
    init_db()
    print('Database initialized successfully')
"@
        $pinfo = New-Object System.Diagnostics.ProcessStartInfo
        $pinfo.FileName = $pythonExe
        $pinfo.RedirectStandardInput = $true
        $pinfo.RedirectStandardOutput = $true
        $pinfo.RedirectStandardError = $true
        $pinfo.UseShellExecute = $false
        $pinfo.WorkingDirectory = $ScriptRoot
        $p = New-Object System.Diagnostics.Process
        $p.StartInfo = $pinfo
        [void]$p.Start()
        $p.StandardInput.WriteLine($initScript)
        $p.StandardInput.Close()
        $stdout = $p.StandardOutput.ReadToEnd()
        $stderr = $p.StandardError.ReadToEnd()
        $p.WaitForExit()
        if ($p.ExitCode -eq 0) {
            Write-Log "Database initialization completed"
        } else {
            Write-Warning-Log "Database initialization had issues, continuing... ($stderr)"
        }
    }
    catch {
        Write-Warning-Log "Database initialization error: $_"
    }
}

# Start Celery worker
function Start-CeleryWorker {
    Write-Log "Starting Celery worker..." "Blue"
    
    try {
        $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
        $celeryExe = Join-Path $venvScripts "celery.exe"
        $pythonExe = Join-Path $venvScripts "python.exe"
        $args = @("-A", $CeleryApp, "worker", "--loglevel=info", "--concurrency=$WorkerConcurrency", "--pidfile=celery_worker.pid", "--logfile=celery_worker.log")
        if ($UseSoloPool) { $args = @("-A", $CeleryApp, "worker", "--loglevel=info", "-P", "solo", "--concurrency=$WorkerConcurrency", "--pidfile=celery_worker.pid", "--logfile=celery_worker.log") }

        if (Test-Path $celeryExe) {
            $workerProcess = Start-Process -FilePath $celeryExe -ArgumentList $args -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
        } elseif (Test-Path $pythonExe) {
            $workerProcess = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "celery") + $args -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
        } else {
            # Fallback to PATH celery
            $workerProcess = Start-Process -FilePath "celery" -ArgumentList $args -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
        }
        
        if ($workerProcess) {
            $workerProcess.Id | Out-File -FilePath "celery_worker_pid.txt"
            Write-Log "Celery worker started successfully (PID: $($workerProcess.Id))"
            return $true
        }
        else {
            Write-Error-Log "Failed to start Celery worker"
            return $false
        }
    }
    catch {
        Write-Error-Log "Error starting Celery worker: $_"
        return $false
    }
}

# Start Celery beat scheduler
function Start-CeleryBeat {
    Write-Log "Starting Celery beat scheduler..." "Blue"
    
    try {
    $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
        $celeryExe = Join-Path $venvScripts "celery.exe"
        $pythonExe = Join-Path $venvScripts "python.exe"

        $args = @("-A", $CeleryApp, "beat", "--loglevel=info", "--pidfile=celery_beat.pid", "--logfile=celery_beat.log", "--schedule=celerybeat-schedule")
        if (Test-Path $celeryExe) {
            $beatProcess = Start-Process -FilePath $celeryExe -ArgumentList $args -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
        } elseif (Test-Path $pythonExe) {
            $beatProcess = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "celery") + $args -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
        } else {
            # Fallback to PATH celery
            $beatProcess = Start-Process -FilePath "celery" -ArgumentList $args -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
        }
        
        if ($beatProcess) {
            $beatProcess.Id | Out-File -FilePath "celery_beat_pid.txt"
            Write-Log "Celery beat started successfully (PID: $($beatProcess.Id))"
            return $true
        }
        else {
            Write-Error-Log "Failed to start Celery beat"
            return $false
        }
    }
    catch {
        Write-Error-Log "Error starting Celery beat: $_"
        return $false
    }
}

# Start Flask application
function Start-FlaskApp {
    Write-Log "Starting Flask application..." "Blue"
    
    $env:FLASK_APP = $FlaskApp
    if (-not $env:FLASK_ENV -or $env:FLASK_ENV.Trim() -eq '') { $env:FLASK_ENV = "development" }
    if (-not $env:ANALYZER_AUTO_START -or $env:ANALYZER_AUTO_START.Trim() -eq '') { $env:ANALYZER_AUTO_START = "false" }
    
    try {
    # Prefer venv Python
    $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
    $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
    $flaskProcess = Start-Process $pythonExe -ArgumentList $FlaskApp -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
        
        if ($flaskProcess) {
            $flaskProcess.Id | Out-File -FilePath "flask_app_pid.txt"
            Write-Log "Flask application started successfully (PID: $($flaskProcess.Id))"
            return $true
        }
        else {
            Write-Error-Log "Failed to start Flask application"
            return $false
        }
    }
    catch {
        Write-Error-Log "Error starting Flask application: $_"
        return $false
    }
}

# Start analyzer services
function Start-AnalyzerServices {
    Write-Log "Starting analyzer services..." "Blue"
    
    $analyzerDir = Join-Path $RepoRoot "analyzer"
    $analyzerManager = Join-Path $analyzerDir "analyzer_manager.py"
    if (Test-Path $analyzerManager) {
        try {
            Push-Location $analyzerDir
            # Prefer venv Python
            $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
            $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
            & $pythonExe "analyzer_manager.py" start 2>$null
            
            if ($LASTEXITCODE -eq 0) {
                Write-Log "Analyzer services started successfully"
            }
            else {
                Write-Warning-Log "Failed to start analyzer services automatically"
            }
        }
        catch {
            Write-Warning-Log "Error starting analyzer services: $_"
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Warning-Log "Analyzer manager not found, skipping analyzer services"
    }
}

# Stop all services
function Stop-Services {
    Write-Log "Stopping all services..." "Blue"
    
    # Stop Flask app
    if (Test-Path "flask_app_pid.txt") {
        try {
            $flaskPid = Get-Content "flask_app_pid.txt"
            $flaskProcess = Get-Process -Id $flaskPid -ErrorAction SilentlyContinue
            if ($flaskProcess) {
                Stop-Process -Id $flaskPid -Force
                Write-Log "Flask application stopped"
            }
            Remove-Item "flask_app_pid.txt" -ErrorAction SilentlyContinue
        }
        catch {
            Write-Warning-Log "Error stopping Flask app: $_"
        }
    }
    
    # Stop Celery worker
    if (Test-Path "celery_worker_pid.txt") {
        try {
            $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
            $celeryExe = Join-Path $venvScripts "celery.exe"
            $pythonExe = Join-Path $venvScripts "python.exe"
            $args = @("-A", $CeleryApp, "control", "shutdown")
            if (Test-Path $celeryExe) {
                & $celeryExe @args 2>$null
            } elseif (Test-Path $pythonExe) {
                & $pythonExe -m celery @args 2>$null
            } else {
                & celery @args 2>$null
            }
            $workerPid = Get-Content "celery_worker_pid.txt"
            $workerProcess = Get-Process -Id $workerPid -ErrorAction SilentlyContinue
            if ($workerProcess) {
                Stop-Process -Id $workerPid -Force
            }
            Remove-Item "celery_worker_pid.txt" -ErrorAction SilentlyContinue
            Remove-Item "celery_worker.pid" -ErrorAction SilentlyContinue
            Write-Log "Celery worker stopped"
        }
        catch {
            Write-Warning-Log "Error stopping Celery worker: $_"
        }
    }
    
    # Stop Celery beat
    if (Test-Path "celery_beat_pid.txt") {
        try {
            $beatPid = Get-Content "celery_beat_pid.txt"
            $beatProcess = Get-Process -Id $beatPid -ErrorAction SilentlyContinue
            if ($beatProcess) {
                Stop-Process -Id $beatPid -Force
            }
            Remove-Item "celery_beat_pid.txt" -ErrorAction SilentlyContinue
            Remove-Item "celery_beat.pid" -ErrorAction SilentlyContinue
            Remove-Item "celerybeat-schedule*" -ErrorAction SilentlyContinue
            Write-Log "Celery beat stopped"
        }
        catch {
            Write-Warning-Log "Error stopping Celery beat: $_"
        }
    }
    
    # Stop analyzer services
    if (Test-Path "..\analyzer\analyzer_manager.py") {
        try {
            Push-Location "..\analyzer"
            python analyzer_manager.py stop 2>$null
            Pop-Location
            Write-Log "Analyzer services stopped"
        }
        catch {
            Write-Warning-Log "Error stopping analyzer services: $_"
        }
    }
}

# Check status of services
function Get-ServiceStatus {
    Write-Log "Checking service status..." "Blue"
    
    # Flask app
    if (Test-Path "flask_app_pid.txt") {
        try {
            $flaskPid = Get-Content "flask_app_pid.txt"
            $flaskProcess = Get-Process -Id $flaskPid -ErrorAction SilentlyContinue
            if ($flaskProcess) {
                Write-Info-Log "Flask app: RUNNING (PID: $flaskPid)"
            }
            else {
                Write-Warning-Log "Flask app: STOPPED (stale PID file)"
            }
        }
        catch {
            Write-Warning-Log "Flask app: STOPPED"
        }
    }
    else {
        Write-Warning-Log "Flask app: STOPPED"
    }
    
    # Celery worker
    if (Test-Path "celery_worker_pid.txt") {
        try {
            $workerPid = Get-Content "celery_worker_pid.txt"
            $workerProcess = Get-Process -Id $workerPid -ErrorAction SilentlyContinue
            if ($workerProcess) {
                Write-Info-Log "Celery worker: RUNNING (PID: $workerPid)"
            }
            else {
                Write-Warning-Log "Celery worker: STOPPED (stale PID file)"
            }
        }
        catch {
            Write-Warning-Log "Celery worker: STOPPED"
        }
    }
    else {
        Write-Warning-Log "Celery worker: STOPPED"
    }
    
    # Celery beat
    if (Test-Path "celery_beat_pid.txt") {
        try {
            $beatPid = Get-Content "celery_beat_pid.txt"
            $beatProcess = Get-Process -Id $beatPid -ErrorAction SilentlyContinue
            if ($beatProcess) {
                Write-Info-Log "Celery beat: RUNNING (PID: $beatPid)"
            }
            else {
                Write-Warning-Log "Celery beat: STOPPED (stale PID file)"
            }
        }
        catch {
            Write-Warning-Log "Celery beat: STOPPED"
        }
    }
    else {
        Write-Warning-Log "Celery beat: STOPPED"
    }
    
    # Redis
    if (Test-Redis) {
        Write-Info-Log "Redis: RUNNING"
    }
    else {
        Write-Warning-Log "Redis: NOT ACCESSIBLE"
    }
}

# Main function
function Invoke-Main {
    param([string]$Action)
    
    switch ($Action) {
        "start" {
            Write-Log "Starting Thesis App with Celery integration..." "Cyan"
            
            if (-not (Test-Dependencies)) {
                exit 1
            }
            
            # Check/start Redis
            if (-not (Test-Redis)) {
                if (-not (Start-Redis)) {
                    exit 1
                }
            }
            
            Initialize-Database
            Start-CeleryWorker
            Start-CeleryBeat
            Start-AnalyzerServices
            Start-FlaskApp
            
            Write-Log "All services started successfully!" "Green"
            Write-Log "Flask app available at: http://127.0.0.1:5000" "Cyan"
            Write-Log "Use 'powershell .\start.ps1 stop' to stop all services" "Cyan"
            Write-Log "Use 'powershell .\start.ps1 status' to check service status" "Cyan"
        }
        
        "stop" {
            Stop-Services
            Write-Log "All services stopped" "Green"
        }
        
        "restart" {
            Stop-Services
            Start-Sleep -Seconds 3
            Invoke-Main "start"
        }
        
        "status" {
            Get-ServiceStatus
        }
        
        "worker-only" {
            Write-Log "Starting Celery worker only..." "Cyan"
            if (-not (Test-Dependencies)) {
                exit 1
            }
            if (-not (Test-Redis)) {
                if (-not (Start-Redis)) {
                    exit 1
                }
            }
            Start-CeleryWorker
            Write-Log "Celery worker started" "Green"
        }
        
        "beat-only" {
            Write-Log "Starting Celery beat only..." "Cyan"
            if (-not (Test-Dependencies)) {
                exit 1
            }
            if (-not (Test-Redis)) {
                if (-not (Start-Redis)) {
                    exit 1
                }
            }
            Start-CeleryBeat
            Write-Log "Celery beat started" "Green"
        }
        
        "flask-only" {
            Write-Log "Starting Flask app only..." "Cyan"
            if (-not (Test-Dependencies)) {
                exit 1
            }
            Initialize-Database
            Start-FlaskApp
            Write-Log "Flask app started" "Green"
        }
        
        default {
            Write-Host "Usage: powershell .\start.ps1 [start|stop|restart|status|worker-only|beat-only|flask-only]" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Commands:" -ForegroundColor Yellow
            Write-Host "  start       - Start all services (default)" -ForegroundColor White
            Write-Host "  stop        - Stop all services" -ForegroundColor White
            Write-Host "  restart     - Restart all services" -ForegroundColor White
            Write-Host "  status      - Check service status" -ForegroundColor White
            Write-Host "  worker-only - Start only Celery worker" -ForegroundColor White
            Write-Host "  beat-only   - Start only Celery beat" -ForegroundColor White
            Write-Host "  flask-only  - Start only Flask app" -ForegroundColor White
            exit 1
        }
    }
}

# Handle script interruption and avoid ErrorAction restore warnings
$hadErrorActionDefault = $PSDefaultParameterValues.ContainsKey('*:ErrorAction')
$originalAction = $PSDefaultParameterValues['*:ErrorAction']
$PSDefaultParameterValues['*:ErrorAction'] = 'Stop'

try {
    # Run main function
    Invoke-Main $Action
}
catch {
    Write-Error-Log "Script interrupted: $_"
    Stop-Services
    exit 130
}
finally {
    if ($hadErrorActionDefault) {
        $PSDefaultParameterValues['*:ErrorAction'] = $originalAction
    } else {
        [void]$PSDefaultParameterValues.Remove('*:ErrorAction')
    }
}
