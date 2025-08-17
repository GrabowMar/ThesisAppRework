# Thesis App Startup Script for Windows
# =====================================
# 
# PowerShell script for starting the Thesis App with Celery integration on Windows.

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "status", "worker-only", "beat-only", "flask-only")]
    [string]$Action = "start",
    # Optional: path to a log file. Defaults to logs/start.ps1.log under repo root
    [string]$LogPath,
    # Optional: skip starting analyzer services
    [switch]$NoAnalyzer,
    # Optional: maximum seconds to wait for DB init phase
    [int]$DbInitTimeoutSeconds = 30
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

# Logging setup
$LogsDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $LogsDir)) {
    try { New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null } catch {}
}
$Global:LogFile = if ($PSBoundParameters.ContainsKey('LogPath') -and $LogPath) { $LogPath } else { Join-Path $LogsDir "start.ps1.log" }

# Colors for output
$ColorMap = @{
    'Red' = 'Red'
    'Green' = 'Green'
    'Yellow' = 'Yellow'
    'Blue' = 'Blue'
    'Cyan' = 'Cyan'
}

# Utility: get Flask process IDs (by PID file, command line, and port)
function Get-FlaskPids {
    $pids = @()
    try {
        if (Test-Path "flask_app_pid.txt") {
            $pidFromFile = Get-Content "flask_app_pid.txt" | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^[0-9]+$' }
            foreach ($p in $pidFromFile) {
                $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
                if ($proc) { $pids += $proc.Id }
            }
        }
    } catch {}
    # Match on command line containing src\main.py (Windows path)
    try {
        $mainPath = [Regex]::Escape((Join-Path $ScriptRoot "main.py"))
        $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object { $_.CommandLine -match $mainPath }
        foreach ($p in $procs) { $pids += $p.ProcessId }
    } catch {}
    # Processes listening on port 5000 (default Flask dev port)
    try {
        $listeners = Get-NetTCPConnection -State Listen -LocalPort 5000 -ErrorAction SilentlyContinue
        foreach ($l in $listeners) { if ($l.OwningProcess) { $pids += $l.OwningProcess } }
    } catch {}
    $pids | Sort-Object -Unique
}

function Stop-FlaskApp {
    Write-Log "Stopping Flask application (if running)..." "Blue"
    try {
        $flaskPids = Get-FlaskPids
        if ($flaskPids -and $flaskPids.Count -gt 0) {
            foreach ($pidToKill in $flaskPids) {
                try { Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue; Write-Log "Stopped Flask process PID: $pidToKill" } catch {}
            }
        } else {
            Write-Info-Log "No Flask processes found"
        }
        Remove-Item "flask_app_pid.txt" -ErrorAction SilentlyContinue
    } catch {
        Write-Warning-Log "Error stopping Flask app: $_"
    }
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Color = 'Green',
        [string]$Level = 'INFO'
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [$Level] $Message"
    Write-Host $line -ForegroundColor $ColorMap[$Color]
    try { Add-Content -Path $Global:LogFile -Value $line } catch {}
}

function Write-Error-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [ERROR] $Message"
    Write-Host $line -ForegroundColor Red
    try { Add-Content -Path $Global:LogFile -Value $line } catch {}
}

function Write-Warning-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [WARN] $Message"
    Write-Host $line -ForegroundColor Yellow
    try { Add-Content -Path $Global:LogFile -Value $line } catch {}
}

function Write-Info-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [INFO] $Message"
    Write-Host $line -ForegroundColor Blue
    try { Add-Content -Path $Global:LogFile -Value $line } catch {}
}

# Generic TCP port test with timeout
function Test-TcpPort {
    param(
        [string]$TargetHost,
        [int]$Port,
        [int]$TimeoutMs = 1000
    )
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($TargetHost, $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if ($ok -and $client.Connected) { try { $client.EndConnect($iar) } catch {}; $client.Close(); return $true }
        try { $client.Close() } catch {}
        return $false
    } catch { return $false }
}

function Test-AnalyzerPorts {
    param([string]$HostName = '127.0.0.1')
    $ports = 2001..2005
    foreach ($p in $ports) {
        if (Test-TcpPort -TargetHost $HostName -Port $p -TimeoutMs 400) { return $true }
    }
    return $false
}

# Check if Redis is running
function Test-Redis {
    Write-Log "Checking Redis connection at ${RedisHost}:${RedisPort}..." "Blue"
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($RedisHost, [int]$RedisPort, $null, $null)
        $connected = $iar.AsyncWaitHandle.WaitOne(1500, $false)
        if ($connected -and $client.Connected) {
            try { $client.EndConnect($iar) } catch {}
            $client.Close()
            Write-Log "Redis TCP port reachable"
            return $true
        } else {
            try { $client.Close() } catch {}
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
    
    # Check Python (prefer venv)
    $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
    $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { (Get-Command python -ErrorAction SilentlyContinue)?.Source }
    if (-not $pythonExe) { Write-Error-Log "Python not found (checked .venv and PATH)"; return $false }
    
    # Check pip packages
    try {
    & $pythonExe -c "import flask, celery, redis, sqlalchemy" 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Error-Log "Required Python packages not found. Run: pip install -r src/requirements.txt"; return $false }
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
        # Wait with timeout to avoid hangs
        $exited = $p.WaitForExit(1000 * [Math]::Max(5, $DbInitTimeoutSeconds))
        $stdout = $p.StandardOutput.ReadToEnd()
        $stderr = $p.StandardError.ReadToEnd()
        if (-not $exited) {
            try { $p.Kill() } catch {}
            Write-Warning-Log "Database initialization timed out after $DbInitTimeoutSeconds seconds. Continuing startup."
        } elseif ($p.ExitCode -eq 0) {
            Write-Log "Database initialization completed"
        } else {
            Write-Warning-Log "Database initialization had issues, continuing... ($stderr)"
        }
        if ($stdout) { try { Add-Content -Path $Global:LogFile -Value ("DB INIT STDOUT:" + [Environment]::NewLine + $stdout) } catch {} }
        if ($stderr) { try { Add-Content -Path $Global:LogFile -Value ("DB INIT STDERR:" + [Environment]::NewLine + $stderr) } catch {} }
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
        $workerArgs = @("-A", $CeleryApp, "worker", "--loglevel=info", "--concurrency=$WorkerConcurrency", "--pidfile=celery_worker.pid", "--logfile=celery_worker.log")
        if ($UseSoloPool) { $workerArgs = @("-A", $CeleryApp, "worker", "--loglevel=info", "-P", "solo", "--concurrency=$WorkerConcurrency", "--pidfile=celery_worker.pid", "--logfile=celery_worker.log") }

        if (Test-Path $celeryExe) {
            $workerProcess = Start-Process -FilePath $celeryExe -ArgumentList $workerArgs -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
        } elseif (Test-Path $pythonExe) {
            $workerProcess = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "celery") + $workerArgs -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
        } else {
            # Fallback to PATH celery
            $workerProcess = Start-Process -FilePath "celery" -ArgumentList $workerArgs -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
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

        $beatArgs = @("-A", $CeleryApp, "beat", "--loglevel=info", "--pidfile=celery_beat.pid", "--logfile=celery_beat.log", "--schedule=celerybeat-schedule")
        if (Test-Path $celeryExe) {
            $beatProcess = Start-Process -FilePath $celeryExe -ArgumentList $beatArgs -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
        } elseif (Test-Path $pythonExe) {
            $beatProcess = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "celery") + $beatArgs -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
        } else {
            # Fallback to PATH celery
            $beatProcess = Start-Process -FilePath "celery" -ArgumentList $beatArgs -PassThru -WindowStyle Hidden -WorkingDirectory $ScriptRoot
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
    # Restart if already running
    $existing = Get-FlaskPids
    if ($existing -and $existing.Count -gt 0) { Write-Info-Log "Flask already running (PIDs: $($existing -join ', ')). Restarting..."; Stop-FlaskApp }
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
            if (Test-AnalyzerPorts) { Write-Info-Log "Analyzer services already running"; return }

            # Prefer venv Python
            $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
            $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
            Write-Info-Log "Attempting to start analyzer services via analyzer_manager.py"
            Push-Location $analyzerDir
            & $pythonExe "analyzer_manager.py" start 2>$null
            $startExit = $LASTEXITCODE
            Pop-Location
            if ($startExit -ne 0) { Write-Warning-Log "analyzer_manager.py start returned code $startExit" }

            Start-Sleep -Seconds 2
            if (Test-AnalyzerPorts) { Write-Log "Analyzer services started successfully"; return }

            Write-Warning-Log "Analyzer services not detected on ports 2001-2005. Attempting to build the analyzer stack (this may take several minutes)."
            Build-AnalyzerStack
            # Try start again after build
            Push-Location $analyzerDir
            & $pythonExe "analyzer_manager.py" start 2>$null
            $startExit2 = $LASTEXITCODE
            Pop-Location
            if ($startExit2 -ne 0) { Write-Warning-Log "analyzer_manager.py start after build returned code $startExit2" }
            Start-Sleep -Seconds 2
            if (Test-AnalyzerPorts) { Write-Log "Analyzer services started after build" } else { Write-Warning-Log "Analyzer ports still not reachable after build/start. Check Docker and analyzer logs." }
        }
        catch {
            Write-Warning-Log "Error starting analyzer services: $_"
        }
    }
    else {
        Write-Warning-Log "Analyzer manager not found, skipping analyzer services"
    }
}

function Build-AnalyzerStack {
    Write-Log "Building analyzer stack..." "Blue"
    $analyzerDir = Join-Path $RepoRoot "analyzer"
    $analyzerManager = Join-Path $analyzerDir "analyzer_manager.py"
    # Prefer venv Python
    $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
    $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }

    $built = $false
    try {
        if (Test-Path $analyzerManager) {
            Write-Info-Log "Trying: analyzer_manager.py build"
            Push-Location $analyzerDir
            & $pythonExe "analyzer_manager.py" build 2>$null
            if ($LASTEXITCODE -eq 0) { $built = $true }
            Pop-Location
        }
    } catch { Write-Warning-Log "analyzer_manager.py build failed: $_" }

    if (-not $built) {
        $composeFile = Join-Path $analyzerDir "docker-compose.yml"
        if (Test-Path $composeFile) {
            if (Get-Command docker -ErrorAction SilentlyContinue) {
                try {
                    Write-Info-Log "Trying: docker compose build"
                    $p = Start-Process -FilePath "docker" -ArgumentList @("compose", "-f", "docker-compose.yml", "build") -WorkingDirectory $analyzerDir -NoNewWindow -Wait -PassThru
                    if ($p.ExitCode -eq 0) { $built = $true } else { Write-Warning-Log "docker compose build exited with code $($p.ExitCode)" }
                } catch {
                    Write-Warning-Log "docker compose build failed: $_"
                }
                if (-not $built) {
                    try {
                        Write-Info-Log "Trying: docker-compose build"
                        $p2 = Start-Process -FilePath "docker-compose" -ArgumentList @("-f", "docker-compose.yml", "build") -WorkingDirectory $analyzerDir -NoNewWindow -Wait -PassThru
                        if ($p2.ExitCode -eq 0) { $built = $true } else { Write-Warning-Log "docker-compose build exited with code $($p2.ExitCode)" }
                    } catch { Write-Warning-Log "docker-compose build failed: $_" }
                }
            } else {
                Write-Warning-Log "Docker not found in PATH. Please install/start Docker Desktop."
            }
        } else {
            Write-Warning-Log "docker-compose.yml not found in analyzer directory."
        }
    }

    if ($built) { Write-Log "Analyzer stack build completed" } else { Write-Warning-Log "Analyzer stack build did not complete successfully" }
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
            $ctlArgs = @("-A", $CeleryApp, "control", "shutdown")
            if (Test-Path $celeryExe) {
                & $celeryExe @ctlArgs 2>$null
            } elseif (Test-Path $pythonExe) {
                & $pythonExe -m celery @ctlArgs 2>$null
            } else {
                & celery @ctlArgs 2>$null
            }
            $workerPidTxt = Get-Content "celery_worker_pid.txt"
            $workerProcess = Get-Process -Id $workerPidTxt -ErrorAction SilentlyContinue
            if ($workerProcess) {
                Stop-Process -Id $workerPidTxt -Force
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
    $analyzerDir = Join-Path $RepoRoot "analyzer"
    $analyzerManager = Join-Path $analyzerDir "analyzer_manager.py"
    if (Test-Path $analyzerManager) {
        try {
            $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
            $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
        & $pythonExe $analyzerManager stop 2>$null
            if (Test-Path "analyzer_manager_pid.txt") {
                try {
            $analyzerPid = Get-Content "analyzer_manager_pid.txt"
            $proc = Get-Process -Id $analyzerPid -ErrorAction SilentlyContinue
            if ($proc) { Stop-Process -Id $analyzerPid -Force }
                    Remove-Item "analyzer_manager_pid.txt" -ErrorAction SilentlyContinue
                } catch {}
            }
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
    Write-Info-Log "Log file: $Global:LogFile"
    
    # Flask app (robust detection)
    try {
        $flaskPids = Get-FlaskPids
        if ($flaskPids -and $flaskPids.Count -gt 0) {
            Write-Info-Log "Flask app: RUNNING (PIDs: $($flaskPids -join ', '))"
        } else {
            if (Test-Path "flask_app_pid.txt") { Write-Warning-Log "Flask app: STOPPED (stale PID file)" } else { Write-Warning-Log "Flask app: STOPPED" }
        }
    } catch { Write-Warning-Log "Flask app: UNKNOWN" }
    
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
                # Auto-clean stale pid
                try { Remove-Item "celery_beat_pid.txt" -ErrorAction SilentlyContinue } catch {}
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

    # Analyzer services
    if (Test-AnalyzerPorts) {
        Write-Info-Log "Analyzer services: RUNNING (ports 2001-2005)"
    } else {
        Write-Warning-Log "Analyzer services: NOT RUNNING"
    }
}

# Main function
function Invoke-Main {
    param([string]$Action)
    
    switch ($Action) {
        "start" {
            Write-Log "Starting Thesis App with Celery integration..." "Cyan"
            Write-Info-Log "Log file: $Global:LogFile"
            
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
            if (-not $NoAnalyzer) { Start-AnalyzerServices } else { Write-Info-Log "Skipping analyzer services (NoAnalyzer flag set)" }
            Start-FlaskApp
            
            Write-Log "All services start sequence triggered." "Green"
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
        "flask-restart" {
            Write-Log "Restarting Flask app..." "Cyan"
            Stop-FlaskApp
            Start-FlaskApp
            Write-Log "Flask app restarted" "Green"
        }
        "flask-stop" {
            Write-Log "Stopping Flask app..." "Cyan"
            Stop-FlaskApp
            Write-Log "Flask app stopped" "Green"
        }
        "analyzer-build" {
            Write-Log "Building analyzer stack (manual trigger)..." "Cyan"
            Build-AnalyzerStack
        }
        
        default {
            Write-Host "Usage: powershell .\start.ps1 [start|stop|restart|status|worker-only|beat-only|flask-only|flask-restart|flask-stop]" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Commands:" -ForegroundColor Yellow
            Write-Host "  start       - Start all services (default)" -ForegroundColor White
            Write-Host "  stop        - Stop all services" -ForegroundColor White
            Write-Host "  restart     - Restart all services" -ForegroundColor White
            Write-Host "  status      - Check service status" -ForegroundColor White
            Write-Host "  worker-only - Start only Celery worker" -ForegroundColor White
            Write-Host "  beat-only   - Start only Celery beat" -ForegroundColor White
            Write-Host "  flask-only    - Start only Flask app (restarts if already running)" -ForegroundColor White
            Write-Host "  flask-restart - Force-restart Flask app" -ForegroundColor White
            Write-Host "  flask-stop    - Stop only Flask app" -ForegroundColor White
            Write-Host "" -ForegroundColor Yellow
            Write-Host "Options:" -ForegroundColor Yellow
            Write-Host "  -NoAnalyzer               Skip starting analyzer services" -ForegroundColor White
            Write-Host "  -LogPath <path>           Write script logs to the specified file (default: .\\logs\\start.ps1.log)" -ForegroundColor White
            Write-Host "  -DbInitTimeoutSeconds N   Timeout for DB init phase (default: 30)" -ForegroundColor White
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
