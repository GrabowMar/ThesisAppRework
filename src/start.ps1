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
$RedisHost = $env:REDIS_HOST -or "127.0.0.1"
$RedisPort = $env:REDIS_PORT -or "6379"
$WorkerConcurrency = $env:WORKER_CONCURRENCY -or "4"

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
    Write-Log "Checking Redis connection..." "Blue"
    
    try {
        $redisTest = redis-cli -h $RedisHost -p $RedisPort ping 2>$null
        if ($redisTest -eq "PONG") {
            Write-Log "Redis is running and accessible"
            return $true
        }
    }
    catch {
        Write-Error-Log "Redis is not accessible at ${RedisHost}:${RedisPort}"
        return $false
    }
    
    Write-Error-Log "Redis connection failed"
    return $false
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
    
    if (Test-Path "app\models.py") {
        try {
            $initScript = @"
from app.factory import create_cli_app
from app.models import init_db

app = create_cli_app()
with app.app_context():
    init_db()
    print('Database initialized successfully')
"@
            
            $initScript | python 2>$null
            
            if ($LASTEXITCODE -eq 0) {
                Write-Log "Database initialization completed"
            }
            else {
                Write-Warning-Log "Database initialization had issues, continuing..."
            }
        }
        catch {
            Write-Warning-Log "Database initialization error: $_"
        }
    }
    else {
        Write-Warning-Log "Models file not found, skipping database initialization"
    }
}

# Start Celery worker
function Start-CeleryWorker {
    Write-Log "Starting Celery worker..." "Blue"
    
    try {
        $workerProcess = Start-Process celery -ArgumentList "-A", $CeleryApp, "worker", "--loglevel=info", "--concurrency=$WorkerConcurrency", "--pidfile=celery_worker.pid", "--logfile=celery_worker.log" -PassThru -WindowStyle Hidden
        
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
        $beatProcess = Start-Process celery -ArgumentList "-A", $CeleryApp, "beat", "--loglevel=info", "--pidfile=celery_beat.pid", "--logfile=celery_beat.log", "--schedule=celerybeat-schedule" -PassThru -WindowStyle Hidden
        
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
    $env:FLASK_ENV = $env:FLASK_ENV -or "development"
    $env:ANALYZER_AUTO_START = $env:ANALYZER_AUTO_START -or "false"
    
    try {
        $flaskProcess = Start-Process python -ArgumentList $FlaskApp -PassThru -WindowStyle Hidden
        
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
    
    if (Test-Path "..\analyzer\analyzer_manager.py") {
        try {
            Push-Location "..\analyzer"
            python analyzer_manager.py start 2>$null
            
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
            celery -A $CeleryApp control shutdown 2>$null
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

# Handle script interruption
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
    $PSDefaultParameterValues['*:ErrorAction'] = $originalAction
}
