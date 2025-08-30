# Thesis App Startup Script for Windows
# =====================================
# 
# PowerShell script for starting the Thesis App with Celery integration on Windows.

param(
    [Parameter(Position=0)]
    [ValidateSet(
        "start", "stop", "restart", "status",
        "worker-only", "beat-only", "flask-only",
        "flask-restart", "flask-stop", "analyzer-build",
    "logs", "rebuild-service"
    )]
    [string]$Action = "start",
    # Optional: path to a log file. Defaults to logs/start.ps1.log under repo root
    [string]$LogPath,
    # Optional: skip starting analyzer services
    [switch]$NoAnalyzer,
    # Optional: maximum seconds to wait for DB init phase
    [int]$DbInitTimeoutSeconds = 30,
    # Logs: target to stream: flask | celery | analyzer | all
    [ValidateSet("flask", "celery", "analyzer", "all")]
    [string]$Target = "all",
    # Logs: number of tail lines per stream
    [int]$TailLines = 200,
    # Logs: optional analyzer service name (matches docker compose service)
    [string]$Service,
    # Logs: output format: raw (no processing), compact (default), http (HTTP-centric)
    [ValidateSet("raw","compact","http")]
    [string]$Format = "compact",
    # Logs: print aggregated HTTP status stats every N seconds (0 disables)
    [int]$StatsIntervalSeconds = 0,
    # Logs: disable ANSI colorization
    [switch]$NoColor,
    # Logs: truncate very long lines to keep output readable (0 disables)
    [int]$MaxLineLength = 200,
    # Global help flag (aliases: -h, -?)
    [Alias('h','?')]
    [switch]$Help,
    # Option: force (re)build and recreate analyzer containers on start
    [switch]$Rebuild,
    # Option: skip Celery queue purge during start (enabled by default)
    [switch]$NoPurge
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
$RepoRoot = $ScriptRoot

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

# =====================
# Help/Usage
# =====================
function Show-GeneralHelp {
    Write-Host "Usage: powershell .\\start.ps1 [command] [options]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Yellow
    Write-Host "  start          Start all services (default)" -ForegroundColor White
    Write-Host "  stop           Stop all services" -ForegroundColor White
    Write-Host "  restart        Restart all services" -ForegroundColor White
    Write-Host "  status         Check service status" -ForegroundColor White
    Write-Host "  worker-only    Start only Celery worker" -ForegroundColor White
    Write-Host "  beat-only      Start only Celery beat" -ForegroundColor White
    Write-Host "  flask-only     Start only Flask app (restarts if already running)" -ForegroundColor White
    Write-Host "  flask-restart  Force-restart Flask app" -ForegroundColor White
    Write-Host "  flask-stop     Stop only Flask app" -ForegroundColor White
    Write-Host "  analyzer-build Build analyzer stack (Docker)" -ForegroundColor White
    Write-Host "  logs           Stream live logs (see: .\\start.ps1 logs -help)" -ForegroundColor White
    Write-Host ""
    Write-Host "Global Options:" -ForegroundColor Yellow
    Write-Host "  -NoAnalyzer                 Skip starting analyzer services" -ForegroundColor White
    Write-Host "  -LogPath <path>             Write script logs to the specified file (default: .\\logs\\start.ps1.log)" -ForegroundColor White
    Write-Host "  -DbInitTimeoutSeconds <N>   Timeout for DB init phase (default: 30)" -ForegroundColor White
    Write-Host "  -Rebuild                    Recreate analyzer containers/images (docker compose down; up --build --force-recreate)" -ForegroundColor White
    Write-Host "  -NoPurge                   Skip purging Celery queues on start (default is to purge)" -ForegroundColor White
    Write-Host "  -Help | -h | -?             Show this help and exit" -ForegroundColor White
}

function Show-LogsHelp {
    Write-Host "Thesis App Startup Script — Logs Mode" -ForegroundColor Yellow
    Write-Host "Stream and aggregate live logs from Flask, Celery, and Analyzer with readable formatting and optional HTTP summaries." -ForegroundColor White
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  powershell .\start.ps1 logs `[Target (flask|celery|analyzer|all)] `[TailLines (N)] `[Service (name)]" -ForegroundColor White
    Write-Host "                                   `[Format (raw|compact|http)] `[StatsIntervalSeconds (N)] `[MaxLineLength (N)] `[NoColor]" -ForegroundColor White
    Write-Host ""
    Write-Host "Targets:" -ForegroundColor Yellow
    Write-Host "  flask      Stream logs/app.log (Flask/Werkzeug)" -ForegroundColor White
    Write-Host "  celery     Stream logs/celery_worker.log and logs/celery_beat.log" -ForegroundColor White
    Write-Host "  analyzer   Stream analyzer docker compose logs (supports -Service filter)" -ForegroundColor White
    Write-Host "  all        Stream all of the above (default)" -ForegroundColor White
    Write-Host ""
    Write-Host "Formats:" -ForegroundColor Yellow
    Write-Host "  compact (default)  Tidies noise; HTTP shown as 'METHOD path -> CODE' with color by status" -ForegroundColor White
    Write-Host "  http               Emphasizes HTTP request lines; dims non-request lines" -ForegroundColor White
    Write-Host "  raw                Pass-through with minimal severity coloring" -ForegroundColor White
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "  -Target flask|celery|analyzer|all   Select logs to stream (default: all)" -ForegroundColor White
    Write-Host "  -TailLines N                         Initial lines per stream (default: 200)" -ForegroundColor White
    Write-Host "  -Service name                        Analyzer compose service (e.g. ai-analyzer)" -ForegroundColor White
    Write-Host "  -Format raw|compact|http             Output style (default: compact)" -ForegroundColor White
    Write-Host "  -StatsIntervalSeconds N              Print HTTP summary (2xx/3xx/4xx/5xx) every N seconds (0=disable, default: 0)" -ForegroundColor White
    Write-Host "  -MaxLineLength N                     Truncate long lines (0=disable, default: 200)" -ForegroundColor White
    Write-Host "  -NoColor                               Disable colored output" -ForegroundColor White
    Write-Host ""
    Write-Host "Notes:" -ForegroundColor Yellow
    Write-Host "  • Ctrl+C exits the stream without stopping services." -ForegroundColor White
    Write-Host "  • Analyzer logs require Docker (tries 'docker compose', then 'docker-compose')." -ForegroundColor White
}

# Helper to prefix and colorize log lines
function Write-TaggedLine {
    param(
        [string]$Tag,
        [string]$Line,
        [string]$Color = 'White'
    )
    if ($script:DisableColor) { $Color = 'White' }
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts][$Tag] $Line" -ForegroundColor $Color
}

# Tail a file in the foreground (blocking)
## Removed unused Tail-LogFile function (replaced by Start-TailJob)

# Start a background job to tail a file; returns the Job with metadata
function Start-TailJob {
    param(
        [Parameter(Mandatory)][string]$Path,
        [int]$Tail = 200,
        [string]$Tag = 'LOG',
        [string]$Color = 'White'
    )
    $script = {
        param($p, $t)
        if (-not (Test-Path $p)) {
            $attempts = 0
            while (-not (Test-Path $p) -and $attempts -lt 300) { Start-Sleep -Milliseconds 100; $attempts++ }
        }
        if (Test-Path $p) {
            Get-Content -Path $p -Tail $t -Wait
        }
    }
    $job = Start-Job -ScriptBlock $script -ArgumentList @($Path, $Tail)
    # Attach metadata using notes
    $job | Add-Member -NotePropertyName Tag -NotePropertyValue $Tag -Force
    $job | Add-Member -NotePropertyName Color -NotePropertyValue $Color -Force
    return $job
}

# Stream analyzer logs using docker compose; runs as a background job and returns the Job
function Start-AnalyzerLogsJob {
    param(
        [string]$ServiceName,
        [int]$Tail = 200
    )
    $analyzerDir = Join-Path $RepoRoot "analyzer"
    $composePath = Join-Path $analyzerDir "docker-compose.yml"
    if (-not (Test-Path $composePath)) {
        Write-TaggedLine 'ANALYZER' "docker-compose.yml not found in analyzer directory" 'Red'
        return $null
    }
    $scriptBlock = {
        param($dir, $svc, $tail)
        Set-Location $dir
        $useDockerCompose = $false
        if (Get-Command docker -ErrorAction SilentlyContinue) { $useDockerCompose = $true }
        if ($useDockerCompose) {
            try {
                if ($svc) {
                    & docker compose -f "docker-compose.yml" logs -f --tail $tail -- $svc 2>&1
                } else {
                    & docker compose -f "docker-compose.yml" logs -f --tail $tail 2>&1
                }
            } catch {
                # Fallback to docker-compose if available
                if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
                    if ($svc) {
                        & docker-compose -f "docker-compose.yml" logs -f --tail $tail -- $svc 2>&1
                    } else {
                        & docker-compose -f "docker-compose.yml" logs -f --tail $tail 2>&1
                    }
                } else {
                    Write-Output "Docker is not available in PATH to stream analyzer logs."
                }
            }
        } else {
            if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
                if ($svc) {
                    & docker-compose -f "docker-compose.yml" logs -f --tail $tail -- $svc 2>&1
                } else {
                    & docker-compose -f "docker-compose.yml" logs -f --tail $tail 2>&1
                }
            } else {
                Write-Output "Docker is not available in PATH to stream analyzer logs."
            }
        }
    }
    $job = Start-Job -ScriptBlock $scriptBlock -ArgumentList @($analyzerDir, $ServiceName, $Tail)
    $job | Add-Member -NotePropertyName Tag -NotePropertyValue "ANALYZER" -Force
    $job | Add-Member -NotePropertyName Color -NotePropertyValue "Magenta" -Force
    return $job
}

# Format a single log line into a compact, readable form and infer severity/status
function Format-LogObject {
    param(
        [string]$Tag,
        [string]$Line,
        [string]$Mode = 'compact'
    )

    $text = $Line -replace "\r", ''
    # unify whitespace
    $text = ($text -replace "\s+", ' ').Trim()
    $outTag = $Tag
    $color = 'White'
    $codeClass = $null

    # Detect docker compose service prefix: "service | message"
    if ($Tag -eq 'ANALYZER' -and $text -match '^([\w\.-]+)\s*\|\s*(.+)$') {
        $svc = $Matches[1]
        $msg = $Matches[2]
        $outTag = "ANZ:$svc"
        $text = $msg
    }

    if ($Mode -eq 'raw') {
        # Attempt only color by severity keywords
        if ($text -match '\bERROR\b') { $color = 'Red' }
        elseif ($text -match '\bWARN(ING)?\b') { $color = 'Yellow' }
        elseif ($text -match '\bDEBUG\b') { $color = 'DarkGray' }
        else { $color = 'White' }
    }
    else {
        # HTTP log compaction (Werkzeug style)
        # e.g., 127.0.0.1 - - [date] "GET /path HTTP/1.1" 200 -
        $pattern = '"(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+([^"]+)\s+(?:\s+HTTP/\d+\.\d+)?"\s+(\d{3})'
        $httpPattern = $pattern
        if ($text -match $httpPattern) {
            $method = $Matches[1]; $path = $Matches[2]; $code = [int]::Parse($Matches[3])
            $text = "$method $path -> $code"
            if     ($code -ge 500) { $color = 'Red';      $codeClass = '5xx' }
            elseif ($code -ge 400) { $color = 'Yellow';   $codeClass = '4xx' }
            elseif ($code -ge 300) { $color = 'Cyan';     $codeClass = '3xx' }
            else                   { $color = 'Green';    $codeClass = '2xx' }
        }
        else {
            # Color by common severity words
            if ($text -match '\bERROR\b|\bTraceback\b') { $color = 'Red' }
            elseif ($text -match '\bWARN(ING)?\b') { $color = 'Yellow' }
            elseif ($text -match '\bDEBUG\b') { $color = 'DarkGray' }
            elseif ($text -match '\bINFO\b') { $color = 'White' }
            else { $color = 'White' }
        }

        if ($Mode -eq 'http' -and -not $codeClass) {
            # For http mode, de-emphasize non-request lines
            $color = 'DarkGray'
        }
    }

    # Optional truncation
    if ($MaxLineLength -gt 0 -and $text.Length -gt $MaxLineLength) {
        $text = $text.Substring(0, [Math]::Max(0, $MaxLineLength - 1)) + '…'
    }

    if ($script:DisableColor) { $color = 'White' }
    [PSCustomObject]@{ Text = $text; Color = $color; Tag = $outTag; CodeClass = $codeClass }
}

# Utility: get Flask process IDs (by database lookup)
function Get-FlaskPids {
    $pids = @()
    try {
        # Prefer venv Python
        $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
        $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
        
        # Query database for Flask app PID
        $pidOutput = & $pythonExe "process_manager.py" "pid" "flask_app" 2>$null
        if ($LASTEXITCODE -eq 0 -and $pidOutput) {
            $flaskPid = $pidOutput.Trim()
            if ($flaskPid -match '^[0-9]+$') {
                $proc = Get-Process -Id $flaskPid -ErrorAction SilentlyContinue
                if ($proc) { $pids += $proc.Id }
            }
        }
    } catch {}
    
    # Fallback: Match on command line containing src\main.py (Windows path)
    try {
        $mainPath = [Regex]::Escape((Join-Path $ScriptRoot "src\main.py"))
        $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object { $_.CommandLine -match $mainPath }
        foreach ($p in $procs) { $pids += $p.ProcessId }
    } catch {}
    
    # Fallback: Processes listening on port 5000 (default Flask dev port)
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
        
        # Mark process as stopped in database
        $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
        $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
        $srcDir = Join-Path $ScriptRoot "src"
        $stopArgs = @("process_manager.py", "stop", "flask_app")
        $stopProcess = Start-Process -FilePath $pythonExe -ArgumentList $stopArgs -WorkingDirectory $srcDir -NoNewWindow -Wait -PassThru
        if ($stopProcess.ExitCode -eq 0) {
            Write-Log "Flask application marked as stopped in database"
        } else {
            Write-Warning-Log "Failed to mark Flask application as stopped in database"
        }
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

# Remove stale PID and schedule files that can confuse restarts
function Clear-StaleArtifacts {
    Write-Log "Cleaning up stale runtime artifacts (PID/schedule files and database entries)..." "Blue"
    try {
        $srcDir = Join-Path $ScriptRoot "src"
        Remove-Item -Path (Join-Path $srcDir "celery_worker.pid") -ErrorAction SilentlyContinue
        Remove-Item -Path (Join-Path $srcDir "celery_beat.pid") -ErrorAction SilentlyContinue
        Get-ChildItem -Path $srcDir -Filter "celerybeat-schedule*" -ErrorAction SilentlyContinue | ForEach-Object { $_ | Remove-Item -Force -ErrorAction SilentlyContinue }
        
        # Clean up dead processes in database
        $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
        $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
        $cleanupArgs = @("process_manager.py", "cleanup")
        $cleanupProcess = Start-Process -FilePath $pythonExe -ArgumentList $cleanupArgs -WorkingDirectory $srcDir -NoNewWindow -Wait -PassThru
        if ($cleanupProcess.ExitCode -eq 0) {
            Write-Log "Database cleanup completed"
        } else {
            Write-Warning-Log "Database cleanup may have encountered issues"
        }
    } catch {
        Write-Warning-Log "Cleanup encountered issues: $_"
    }
}

# Purge Celery queues to avoid replaying old tasks from Redis on fresh starts
function Clear-CeleryQueues {
    param(
        [string[]]$Queues
    )
    if ($NoPurge) {
        Write-Info-Log "Queue purge skipped (-NoPurge set)"
        return
    }
    try {
        # Prefer venv Python and use python -m celery for reliability
        $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
        $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
        if (-not (Test-Redis)) {
            Write-Warning-Log "Redis not reachable; skipping Celery queue purge"
            return
        }
        $totalPurged = 0
        foreach ($q in $Queues) {
            try {
                $celeryArgs = @("-m","celery","-A",$CeleryApp,"purge","-f","-Q",$q)
                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = $pythonExe
                $psi.Arguments = ($celeryArgs -join ' ')
                $psi.RedirectStandardOutput = $true
                $psi.RedirectStandardError = $true
                $psi.UseShellExecute = $false
                $psi.WorkingDirectory = Join-Path $ScriptRoot "src"
                $p = [System.Diagnostics.Process]::Start($psi)
                $p.WaitForExit()
                $out = $p.StandardOutput.ReadToEnd()
                $err = $p.StandardError.ReadToEnd()
                if ($out) { try { Add-Content -Path $Global:LogFile -Value ("PURGE $q => " + $out.Trim()) } catch {} }
                if ($err) { try { Add-Content -Path $Global:LogFile -Value ("PURGE $q ERR => " + $err.Trim()) } catch {} }
                # Celery outputs like "Purged N messages"
                if ($out -match 'Purged\s+(\d+)\s+messages') {
                    $purged = [int]$Matches[1]
                    $totalPurged += $purged
                    if ($purged -gt 0) { Write-Log "Purged $purged messages from queue '$q'" "Yellow" }
                }
            } catch {
                Write-Warning-Log "Failed to purge queue '$q': $_"
            }
        }
        if ($totalPurged -gt 0) {
            Write-Log "Total purged messages across queues: $totalPurged" "Yellow"
        } else {
            Write-Info-Log "Celery queues appear empty"
        }
    } catch {
        Write-Warning-Log "Queue purge encountered issues: $_"
    }
}

# After start, quickly hit Flask /health to verify basic readiness
function Invoke-HealthSanityCheck {
    param(
        [int]$Retries = 10,
        [int]$DelayMs = 800
    )
    $url = "http://127.0.0.1:5000/health"
    $ok = $false
    $respObj = $null
    for ($i = 0; $i -lt $Retries; $i++) {
        try {
            $respObj = Invoke-RestMethod -Method GET -Uri $url -TimeoutSec 3
            if ($respObj -and $respObj.status) { $ok = $true; break }
        } catch {
            Start-Sleep -Milliseconds $DelayMs
        }
    }
    if ($ok) {
        $overall = $respObj.status
        $db = $respObj.components.database
        $celery = $respObj.components.celery
        $analyzer = $respObj.components.analyzer
        $ts = $respObj.timestamp
        $color = if ($overall -eq 'healthy') { 'Green' } else { 'Yellow' }
        Write-Log "Health: overall=$overall db=$db celery=$celery analyzer=$analyzer ts=$ts" -Color $color
    } else {
        Write-Warning-Log "Health check failed to respond after $Retries attempts; services may still be initializing"
    }
}

# Ensure Redis is available, preferring the analyzer's Redis container if present
function Test-RedisAvailable {
    param(
        [switch]$NoAnalyzer
    )
    Write-Log "Ensuring Redis availability..." "Blue"
    # First, quick check
    if (Test-Redis) { return $true }

    # If analyzer services are allowed, try to start them which include Redis
    if (-not $NoAnalyzer) {
        try {
            Write-Info-Log "Redis not reachable yet; attempting to start analyzer services (which include Redis)"
            Start-AnalyzerServices
            Start-Sleep -Seconds 2
            if (Test-Redis) {
                Write-Log "Redis is reachable after starting analyzer services"
                return $true
            }
        } catch {
            Write-Warning-Log "Attempt to start analyzer services for Redis failed: $_"
        }
    }

    # Fallback to local Redis server if available on PATH
    try {
        Write-Info-Log "Trying to start local Redis server as fallback"
        if (Start-Redis) { return $true }
    } catch {
        Write-Warning-Log "Local Redis start attempt failed: $_"
    }

    # Final check
    if (Test-Redis) { return $true }
    Write-Error-Log "Redis still not reachable. Please ensure Docker Desktop is running or provide REDIS_URL."
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
    
    # Check Python (prefer venv)
    $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
    $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { 
        Join-Path $venvScripts "python.exe" 
    } else { 
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCmd) { $pythonCmd.Source } else { $null }
    }
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
from app.models import ModelCapability
from app.services.data_initialization import DataInitializationService

app = create_cli_app()
with app.app_context():
    init_db()
    try:
        count = ModelCapability.query.count()
    except Exception as e:
        print(f'Warning: could not query ModelCapability count: {e}')
        count = 0

    if count == 0:
        try:
            svc = DataInitializationService()
            res = svc.initialize_all_data()
            print(f"Database initialized and seeded: models={res.get('models_loaded')}, apps={res.get('applications_loaded')}, success={res.get('success')}")
        except Exception as se:
            print(f'Warning: database seeding failed: {se}')
            print('Database initialized without seed data')
    else:
        print(f'Database initialized successfully; existing models: {count}')
"@
        $pinfo = New-Object System.Diagnostics.ProcessStartInfo
        $pinfo.FileName = $pythonExe
        $pinfo.RedirectStandardInput = $true
        $pinfo.RedirectStandardOutput = $true
        $pinfo.RedirectStandardError = $true
        $pinfo.UseShellExecute = $false
        $pinfo.WorkingDirectory = Join-Path $ScriptRoot "src"
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
        $pythonExe = Join-Path $venvScripts "python.exe"
    # Clear stale pid files before attempting start
    $srcDir = Join-Path $ScriptRoot "src"
    Remove-Item -Path (Join-Path $srcDir "celery_worker.pid") -ErrorAction SilentlyContinue
        # Ensure PYTHONPATH includes src so 'app' package is importable
        if ($env:PYTHONPATH -and $env:PYTHONPATH.Trim() -ne '') {
            if (-not $env:PYTHONPATH.Split([IO.Path]::PathSeparator) -contains $srcDir) {
                $env:PYTHONPATH = $env:PYTHONPATH + [IO.Path]::PathSeparator + $srcDir
            }
        } else {
            $env:PYTHONPATH = $srcDir
        }

        # Always invoke via python -m celery for reliable import resolution
        $workerArgs = @("-m", "celery", "-A", $CeleryApp, "worker", "--loglevel=info", "--pidfile=celery_worker.pid", "--logfile=../logs/celery_worker.log", "--concurrency=$WorkerConcurrency", "-n", "worker@%h")
        if ($UseSoloPool) { $workerArgs += @("-P", "solo") }

        if (Test-Path $pythonExe) {
            $workerProcess = Start-Process -FilePath $pythonExe -ArgumentList $workerArgs -PassThru -WindowStyle Hidden -WorkingDirectory $srcDir
        } else {
            # Fallback to system python
            $workerProcess = Start-Process -FilePath "python" -ArgumentList $workerArgs -PassThru -WindowStyle Hidden -WorkingDirectory $srcDir
        }
        
        if ($workerProcess) {
            # Try to capture the real Celery worker PID from Celery's pidfile
            $realPid = $null
            $attempts = 0
            while ($attempts -lt 50) { # wait up to ~5s
                if (Test-Path (Join-Path $srcDir "celery_worker.pid")) {
                    try {
                        $realPid = (Get-Content (Join-Path $srcDir "celery_worker.pid")).Trim()
                        if ($realPid -match '^[0-9]+$') {
                            $pidVal = $null
                            try { $pidVal = [int]::Parse($realPid) } catch {}
                            $proc = $null
                            if ($pidVal) { $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue }
                            if ($proc) { break }
                        }
                    } catch {}
                }
                Start-Sleep -Milliseconds 100
                $attempts++
            }

            if ($realPid -and ($realPid -match '^[0-9]+$')) {
                # Double-check the process is still alive after a brief grace period
                Start-Sleep -Milliseconds 300
                $pidVal2 = $null
                try { $pidVal2 = [int]::Parse($realPid) } catch {}
                $procCheck = $null
                if ($pidVal2) { $procCheck = Get-Process -Id $pidVal2 -ErrorAction SilentlyContinue }
                if ($procCheck) {
                    # Register the real Celery worker PID in database
                    $registerArgs = @("process_manager.py", "register", "celery_worker", "--pid", $realPid, "--command", "`"$pythonExe -m celery -A $CeleryApp worker`"")
                    $registerProcess = Start-Process -FilePath $pythonExe -ArgumentList $registerArgs -WorkingDirectory $srcDir -NoNewWindow -Wait -PassThru
                    if ($registerProcess.ExitCode -eq 0) {
                        Write-Log "Celery worker started and registered successfully (PID: $realPid)"
                    } else {
                        Write-Warning-Log "Celery worker started but failed to register in database (PID: $realPid)"
                    }
                } else {
                    Write-Warning-Log "Celery worker PID file found ($realPid) but process not running; check logs/celery_worker.log for errors."
                }
            } else {
                Write-Log "Celery worker start triggered (launcher PID: $($workerProcess.Id)); awaiting readiness..." "Yellow"
            }
            return $true
        } else {
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
        $pythonExe = Join-Path $venvScripts "python.exe"

        # Ensure PYTHONPATH includes src
        $srcDir = Join-Path $ScriptRoot "src"
        if ($env:PYTHONPATH -and $env:PYTHONPATH.Trim() -ne '') {
            if (-not $env:PYTHONPATH.Split([IO.Path]::PathSeparator) -contains $srcDir) {
                $env:PYTHONPATH = $env:PYTHONPATH + [IO.Path]::PathSeparator + $srcDir
            }
        } else {
            $env:PYTHONPATH = $srcDir
        }

    # Default Celery beat log level to WARNING to reduce minute-by-minute scheduler noise
    $beatLogLevel = if ($env:CELERY_BEAT_LOGLEVEL -and $env:CELERY_BEAT_LOGLEVEL.Trim() -ne '') { $env:CELERY_BEAT_LOGLEVEL } else { 'warning' }
    $beatArgs = @("-m", "celery", "-A", $CeleryApp, "beat", "--loglevel=$beatLogLevel", "--pidfile=celery_beat.pid", "--logfile=../logs/celery_beat.log", "--schedule=celerybeat-schedule", "-n", "beat@%h")
        if (Test-Path $pythonExe) {
            $beatProcess = Start-Process -FilePath $pythonExe -ArgumentList $beatArgs -PassThru -WindowStyle Hidden -WorkingDirectory $srcDir
        } else {
            $beatProcess = Start-Process -FilePath "python" -ArgumentList $beatArgs -PassThru -WindowStyle Hidden -WorkingDirectory $srcDir
        }
        
        if ($beatProcess) {
            # Try to capture the real beat PID from Celery's pidfile
            $realPid = $null
            $attempts = 0
            while ($attempts -lt 50) {
                if (Test-Path (Join-Path $srcDir "celery_beat.pid")) {
                    try {
                        $realPid = (Get-Content (Join-Path $srcDir "celery_beat.pid")).Trim()
                        if ($realPid -match '^[0-9]+$') {
                            $proc = Get-Process -Id [int]$realPid -ErrorAction SilentlyContinue
                            if ($proc) { break }
                        }
                    } catch {}
                }
                Start-Sleep -Milliseconds 100
                $attempts++
            }

            if ($realPid -and ($realPid -match '^[0-9]+$')) {
                # Register the real Celery beat PID in database
                $registerArgs = @("process_manager.py", "register", "celery_beat", "--pid", $realPid, "--command", "`"$pythonExe -m celery -A $CeleryApp beat`"")
                $registerProcess = Start-Process -FilePath $pythonExe -ArgumentList $registerArgs -WorkingDirectory $srcDir -NoNewWindow -Wait -PassThru
                if ($registerProcess.ExitCode -eq 0) {
                    Write-Log "Celery beat started and registered successfully (PID: $realPid)"
                } else {
                    Write-Warning-Log "Celery beat started but failed to register in database (PID: $realPid)"
                }
            } else {
                Write-Log "Celery beat start triggered (launcher PID: $($beatProcess.Id)); awaiting readiness..." "Yellow"
            }
            return $true
        } else {
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
    # Enforce Celery-backed WebSocket strict mode for runtime (prevents mock fallback)
    # Can be overridden by explicitly setting environment variables before invoking the script.
    if (-not $env:WEBSOCKET_STRICT_CELERY -or $env:WEBSOCKET_STRICT_CELERY.Trim() -eq '') { $env:WEBSOCKET_STRICT_CELERY = "true" }
    # Ensure service preference points to celery when strict mode is in effect
    if (($env:WEBSOCKET_STRICT_CELERY -eq 'true') -and (-not $env:WEBSOCKET_SERVICE -or $env:WEBSOCKET_SERVICE.Trim() -eq '' -or $env:WEBSOCKET_SERVICE -eq 'auto')) { $env:WEBSOCKET_SERVICE = 'celery' }
    
    try {
    # Restart if already running
    $existing = Get-FlaskPids
    if ($existing -and $existing.Count -gt 0) { Write-Info-Log "Flask already running (PIDs: $($existing -join ', ')). Restarting..."; Stop-FlaskApp }
    # Prefer venv Python
    $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
    $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
    $srcDir = Join-Path $ScriptRoot "src"
    $flaskProcess = Start-Process $pythonExe -ArgumentList $FlaskApp -PassThru -WindowStyle Hidden -WorkingDirectory $srcDir
        
        if ($flaskProcess) {
            # Register process in database instead of writing PID file
            $registerArgs = @("process_manager.py", "register", "flask_app", "--pid", $flaskProcess.Id, "--command", "`"$pythonExe $FlaskApp`"")
            $registerProcess = Start-Process -FilePath $pythonExe -ArgumentList $registerArgs -WorkingDirectory $srcDir -NoNewWindow -Wait -PassThru
            if ($registerProcess.ExitCode -eq 0) {
                Write-Log "Flask application started and registered successfully (PID: $($flaskProcess.Id))"
            } else {
                Write-Warning-Log "Flask application started but failed to register in database (PID: $($flaskProcess.Id))"
            }
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
    param(
        [switch]$Rebuild
    )
    Write-Log "Starting analyzer services..." "Blue"
    
    $analyzerDir = Join-Path $RepoRoot "analyzer"
    $analyzerManager = Join-Path $analyzerDir "analyzer_manager.py"
    
    # If Rebuild flag is set, do a hard recreate of containers/images via docker compose
    if ($Rebuild) {
        try {
            Write-Info-Log "Recreating analyzer containers (docker compose down; up --build --force-recreate)"
            if (-not (Test-Path (Join-Path $analyzerDir "docker-compose.yml"))) {
                Write-Warning-Log "docker-compose.yml not found in analyzer directory. Skipping rebuild."
            } else {
                $composeArgsDown = @("-f", "docker-compose.yml", "down")
                $composeArgsUp = @("-f", "docker-compose.yml", "up", "--build", "--force-recreate", "-d")
                $usedCompose = $false
                if (Get-Command docker -ErrorAction SilentlyContinue) {
                    try {
                        Write-Info-Log "Running: docker compose down"
                        Start-Process -FilePath "docker" -ArgumentList @("compose") + $composeArgsDown -WorkingDirectory $analyzerDir -NoNewWindow -Wait | Out-Null
                        Write-Info-Log "Running: docker compose up --build --force-recreate -d"
                        Start-Process -FilePath "docker" -ArgumentList @("compose") + $composeArgsUp -WorkingDirectory $analyzerDir -NoNewWindow -Wait | Out-Null
                        $usedCompose = $true
                    } catch {
                        Write-Warning-Log "docker compose failed: $_"
                    }
                }
                if (-not $usedCompose -and (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
                    try {
                        Write-Info-Log "Running: docker-compose down"
                        Start-Process -FilePath "docker-compose" -ArgumentList $composeArgsDown -WorkingDirectory $analyzerDir -NoNewWindow -Wait | Out-Null
                        Write-Info-Log "Running: docker-compose up --build --force-recreate -d"
                        Start-Process -FilePath "docker-compose" -ArgumentList $composeArgsUp -WorkingDirectory $analyzerDir -NoNewWindow -Wait | Out-Null
                        $usedCompose = $true
                    } catch {
                        Write-Warning-Log "docker-compose failed: $_"
                    }
                }
                if (-not $usedCompose) {
                    Write-Warning-Log "Docker not available in PATH to rebuild analyzer services."
                }
                # Give services a moment to come up
                Start-Sleep -Seconds 2
                if (Test-AnalyzerPorts) { Write-Log "Analyzer services started successfully (recreated)" } else { Write-Warning-Log "Analyzer ports not reachable after recreate. Check Docker/analyzer logs." }
            }
        } catch {
            Write-Warning-Log "Error during analyzer services rebuild: $_"
        }
        return
    }
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
    try {
        $flaskPids = Get-FlaskPids
        if ($flaskPids -and $flaskPids.Count -gt 0) {
            foreach ($pidToKill in $flaskPids) {
                try { Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue; Write-Log "Stopped Flask process PID: $pidToKill" } catch {}
            }
        } else {
            Write-Info-Log "No Flask processes found"
        }
        
        # Mark process as stopped in database
        $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
        $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
        $stopArgs = @("process_manager.py", "stop", "flask_app")
        $stopProcess = Start-Process -FilePath $pythonExe -ArgumentList $stopArgs -WorkingDirectory $srcDir -NoNewWindow -Wait -PassThru
        if ($stopProcess.ExitCode -eq 0) {
            Write-Log "Flask application marked as stopped in database"
        } else {
            Write-Warning-Log "Failed to mark Flask application as stopped in database"
        }
    } catch {
        Write-Warning-Log "Error stopping Flask app: $_"
    }
    
    # Stop Celery worker
    try {
        $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
        $celeryExe = Join-Path $venvScripts "celery.exe"
        $pythonExe = Join-Path $venvScripts "python.exe"
        $ctlArgs = @("-A", $CeleryApp, "control", "shutdown")
        Push-Location $srcDir
        if (Test-Path $celeryExe) {
            & $celeryExe @ctlArgs 2>$null
        } elseif (Test-Path $pythonExe) {
            & $pythonExe -m celery @ctlArgs 2>$null
        } else {
            & celery @ctlArgs 2>$null
        }
        Pop-Location
        Remove-Item (Join-Path $srcDir "celery_worker.pid") -ErrorAction SilentlyContinue
        Write-Log "Celery worker stopped"
    }
    catch {
        Write-Warning-Log "Error stopping Celery worker: $_"
    }
    
    # Stop Celery beat
    try {
        Remove-Item (Join-Path $srcDir "celery_beat.pid") -ErrorAction SilentlyContinue
        Get-ChildItem -Path $srcDir -Filter "celerybeat-schedule*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
        Write-Log "Celery beat stopped"
    }
    catch {
        Write-Warning-Log "Error stopping Celery beat: $_"
    }
    
    # Mark all processes as stopped in database
    try {
        $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
        $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
        
        # Stop Flask app in database
        $stopFlaskArgs = @("process_manager.py", "stop", "flask_app")
        $stopFlaskProcess = Start-Process -FilePath $pythonExe -ArgumentList $stopFlaskArgs -WorkingDirectory $srcDir -NoNewWindow -Wait -PassThru
        if ($stopFlaskProcess.ExitCode -eq 0) {
            Write-Log "Flask app marked as stopped in database"
        }
        
        # Stop Celery worker in database
        $stopWorkerArgs = @("process_manager.py", "stop", "celery_worker")
        $stopWorkerProcess = Start-Process -FilePath $pythonExe -ArgumentList $stopWorkerArgs -WorkingDirectory $srcDir -NoNewWindow -Wait -PassThru
        if ($stopWorkerProcess.ExitCode -eq 0) {
            Write-Log "Celery worker marked as stopped in database"
        }
        
        # Stop Celery beat in database
        $stopBeatArgs = @("process_manager.py", "stop", "celery_beat")
        $stopBeatProcess = Start-Process -FilePath $pythonExe -ArgumentList $stopBeatArgs -WorkingDirectory $srcDir -NoNewWindow -Wait -PassThru
        if ($stopBeatProcess.ExitCode -eq 0) {
            Write-Log "Celery beat marked as stopped in database"
        }
    } catch {
        Write-Warning-Log "Error updating database with stopped processes: $_"
    }
    
    # Stop analyzer services
    $analyzerDir = Join-Path $RepoRoot "analyzer"
    $analyzerManager = Join-Path $analyzerDir "analyzer_manager.py"
    if (Test-Path $analyzerManager) {
        try {
            $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
            $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
        Push-Location $analyzerDir
        & $pythonExe $analyzerManager stop 2>$null
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
    Write-Info-Log "Log file: $Global:LogFile"
    
    # Use process_manager.py to get status from database
    $venvScripts = Join-Path $RepoRoot ".venv\Scripts"
    $pythonExe = if (Test-Path (Join-Path $venvScripts "python.exe")) { Join-Path $venvScripts "python.exe" } else { "python" }
    $srcDir = Join-Path $ScriptRoot "src"
    
    try {
        # Use Start-Process like other functions for consistency
        $statusArgs = @("process_manager.py", "status")
        $statusProcess = Start-Process -FilePath $pythonExe -ArgumentList $statusArgs -WorkingDirectory $srcDir -NoNewWindow -Wait -PassThru
        if ($statusProcess.ExitCode -eq 0) {
            Write-Log "Database status retrieved successfully"
        } else {
            Write-Warning-Log "Failed to get status from database (Exit code: $($statusProcess.ExitCode))"
        }
    } catch {
        Write-Warning-Log "Error getting status from database: $_"
    }
    
    # Fallback to individual checks if database query fails
    Write-Info-Log "Performing fallback status checks..."
    
    # Flask app (robust detection)
    try {
        $flaskPids = Get-FlaskPids
        if ($flaskPids -and $flaskPids.Count -gt 0) {
            Write-Info-Log "Flask app: RUNNING (PIDs: $($flaskPids -join ', '))"
        } else {
            Write-Warning-Log "Flask app: STOPPED"
        }
    } catch { Write-Warning-Log "Flask app: UNKNOWN" }
    
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
            
            # Ensure Redis (prefer analyzer's Redis if available)
            if (-not (Test-RedisAvailable -NoAnalyzer:$NoAnalyzer)) { exit 1 }
            
            # Clean up stale files and purge Celery queues to avoid replaying old tasks
            Clear-StaleArtifacts
            Clear-CeleryQueues -Queues @(
                'security_analysis', 'performance_testing', 'static_analysis', 'dynamic_analysis',
                'ai_analysis', 'batch_processing', 'container_ops', 'monitoring', 'celery'
            )
            
            Initialize-Database
            $null = Start-CeleryWorker
            $null = Start-CeleryBeat
            if (-not $NoAnalyzer) { $null = Start-AnalyzerServices -Rebuild:$Rebuild } else { Write-Info-Log "Skipping analyzer services (NoAnalyzer flag set)" }
            $null = Start-FlaskApp
            
            # Quick sanity/health check after starting everything
            Invoke-HealthSanityCheck
            
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
            if (-not (Test-RedisAvailable -NoAnalyzer:$false)) { exit 1 }
            $ok = Start-CeleryWorker
            if ($ok) {
                Write-Log "Celery worker started" "Green"
            } else {
                Write-Warning-Log "Celery worker did not start successfully; see logs/celery_worker.log for details"
                exit 1
            }
        }
        
        "beat-only" {
            Write-Log "Starting Celery beat only..." "Cyan"
            if (-not (Test-Dependencies)) {
                exit 1
            }
            if (-not (Test-RedisAvailable -NoAnalyzer:$false)) { exit 1 }
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

        "rebuild-service" {
            if (-not $Service -or $Service.Trim() -eq "") {
                Write-Warning-Log "Specify -Service <name> (e.g. performance-tester) for rebuild-service action"
                break
            }
            Write-Log "Rebuilding analyzer service '$Service'..." "Cyan"
            $analyzerDir = Join-Path $RepoRoot "analyzer"
            $composeFile = Join-Path $analyzerDir "docker-compose.yml"
            if (-not (Test-Path $composeFile)) { Write-Warning-Log "docker-compose.yml not found in analyzer directory"; break }
            $usedCompose = $false
            try {
                if (Get-Command docker -ErrorAction SilentlyContinue) {
                    Write-Info-Log "Running: docker compose build $Service"
                    Start-Process -FilePath "docker" -ArgumentList @("compose","-f","docker-compose.yml","build",$Service) -WorkingDirectory $analyzerDir -NoNewWindow -Wait | Out-Null
                    $usedCompose = $true
                    Write-Info-Log "Running: docker compose up -d --no-deps --force-recreate $Service"
                    Start-Process -FilePath "docker" -ArgumentList @("compose","-f","docker-compose.yml","up","-d","--no-deps","--force-recreate",$Service) -WorkingDirectory $analyzerDir -NoNewWindow -Wait | Out-Null
                }
            } catch { Write-Warning-Log "docker compose rebuild failed: $_" }
            if (-not $usedCompose -and (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
                try {
                    Write-Info-Log "Running: docker-compose build $Service"
                    Start-Process -FilePath "docker-compose" -ArgumentList @("-f","docker-compose.yml","build",$Service) -WorkingDirectory $analyzerDir -NoNewWindow -Wait | Out-Null
                    Write-Info-Log "Running: docker-compose up -d --no-deps --force-recreate $Service"
                    Start-Process -FilePath "docker-compose" -ArgumentList @("-f","docker-compose.yml","up","-d","--no-deps","--force-recreate",$Service) -WorkingDirectory $analyzerDir -NoNewWindow -Wait | Out-Null
                    $usedCompose = $true
                } catch { Write-Warning-Log "docker-compose rebuild failed: $_" }
            }
            if ($usedCompose) {
                Write-Log "Rebuild triggered for analyzer service '$Service'" "Green"
            } else {
                Write-Warning-Log "Could not rebuild service '$Service' (Docker not available)"
            }
        }
        
        "logs" {
            # Stream live logs from selected targets
            Write-Log "Starting live log streaming..." "Cyan"
            Write-Info-Log "Targets: $Target | Tail: $TailLines | Service: $Service | Format: $Format | StatsInterval: $StatsIntervalSeconds s"

            # Configure color policy
            $script:DisableColor = $NoColor.IsPresent

            $jobs = @()
            # Stats structures
            $stats = @{ '2xx' = 0; '3xx' = 0; '4xx' = 0; '5xx' = 0; 'total' = 0 }
            $lastStatsPrint = Get-Date
            try {
                if ($Target -in @('flask','all')) {
                    $flaskLog = Join-Path $RepoRoot "logs/app.log"
                    Write-TaggedLine 'FLASK' "Preparing to stream $flaskLog" 'Blue'
                    $jobs += Start-TailJob -Path $flaskLog -Tail $TailLines -Tag 'FLASK' -Color 'Blue'
                }
                if ($Target -in @('celery','all')) {
                    $workerLog = Join-Path $RepoRoot "logs/celery_worker.log"
                    $beatLog = Join-Path $RepoRoot "logs/celery_beat.log"
                    Write-TaggedLine 'CELERY' "Preparing to stream $workerLog" 'Green'
                    $jobs += Start-TailJob -Path $workerLog -Tail $TailLines -Tag 'WORKER' -Color 'Green'
                    Write-TaggedLine 'CELERY' "Preparing to stream $beatLog" 'Green'
                    $jobs += Start-TailJob -Path $beatLog -Tail $TailLines -Tag 'BEAT' -Color 'DarkGreen'
                }
                if ($Target -in @('analyzer','all')) {
                    Write-TaggedLine 'ANALYZER' "Preparing to stream analyzer container logs" 'Magenta'
                    $jobs += Start-AnalyzerLogsJob -ServiceName $Service -Tail $TailLines
                }

                $jobs = $jobs | Where-Object { $_ -ne $null }
                if (-not $jobs -or $jobs.Count -eq 0) {
                    Write-Warning-Log "No log streams started. Check parameters or availability."
                    break
                }

                Write-Log "Streaming started. Press Ctrl+C to stop." "Cyan"
                while ($true) {
                    foreach ($j in $jobs) {
                        $out = Receive-Job -Job $j -ErrorAction SilentlyContinue
                        if ($out) {
                            foreach ($line in $out) {
                                $obj = Format-LogObject -Tag $j.Tag -Line $line -Mode $Format
                                Write-TaggedLine $obj.Tag $obj.Text $obj.Color
                                if ($obj.CodeClass) { $stats[$obj.CodeClass]++ }
                                $stats['total']++
                            }
                        }
                    }
                    # Clean up completed/failed jobs
                    $jobs = $jobs | Where-Object { $_.State -in @('Running','NotStarted') }
                    if (-not $jobs -or $jobs.Count -eq 0) { break }
                    # Periodic stats output
                    if ($StatsIntervalSeconds -gt 0) {
                        $now = Get-Date
                        if (($now - $lastStatsPrint).TotalSeconds -ge $StatsIntervalSeconds) {
                            $summary = "HTTP summary: total=$($stats.total) 2xx=$($stats['2xx']) 3xx=$($stats['3xx']) 4xx=$($stats['4xx']) 5xx=$($stats['5xx'])"
                            Write-TaggedLine 'STATS' $summary 'Cyan'
                            # Reset counters
                            $stats['2xx'] = 0; $stats['3xx'] = 0; $stats['4xx'] = 0; $stats['5xx'] = 0; $stats['total'] = 0
                            $lastStatsPrint = $now
                        }
                    }
                    Start-Sleep -Milliseconds 200
                }
            } catch {
                Write-Error-Log "Logs streaming interrupted: $_"
            } finally {
                foreach ($j in $jobs) { try { Stop-Job -Job $j -Force -ErrorAction SilentlyContinue } catch {} }
                foreach ($j in $jobs) { try { Remove-Job -Job $j -Force -ErrorAction SilentlyContinue } catch {} }
            }
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
            Write-Host "  analyzer-build- Build analyzer stack (Docker)" -ForegroundColor White
            Write-Host "  logs         - Stream live logs (use -Target, -TailLines, -Service, -Format, -StatsIntervalSeconds)" -ForegroundColor White
            Write-Host "" -ForegroundColor Yellow
            Write-Host "Options:" -ForegroundColor Yellow
            Write-Host "  -NoAnalyzer               Skip starting analyzer services" -ForegroundColor White
            Write-Host "  -LogPath <path>           Write script logs to the specified file (default: .\\logs\\start.ps1.log)" -ForegroundColor White
            Write-Host "  -DbInitTimeoutSeconds N   Timeout for DB init phase (default: 30)" -ForegroundColor White
            Write-Host "  -NoPurge                  Skip Celery queue purge on start" -ForegroundColor White
            Write-Host "  -Target <flask|celery|analyzer|all>  Select logs to stream (default: all)" -ForegroundColor White
            Write-Host "  -TailLines N              Number of lines to tail initially (default: 200)" -ForegroundColor White
            Write-Host "  -Service <name>           Analyzer service to filter (docker compose service name)" -ForegroundColor White
            Write-Host "  -Format <raw|compact|http> Output format for logs (default: compact)" -ForegroundColor White
            Write-Host "  -StatsIntervalSeconds N   Periodic HTTP status summary; 0 to disable (default: 0)" -ForegroundColor White
            Write-Host "  -NoColor                  Disable colored output" -ForegroundColor White
            Write-Host "  -MaxLineLength N          Truncate lines to N chars; 0 to disable (default: 200)" -ForegroundColor White
            exit 1
        }
    }
}

# Handle script interruption and avoid ErrorAction restore warnings
$hadErrorActionDefault = $PSDefaultParameterValues.ContainsKey('*:ErrorAction')
$originalAction = $PSDefaultParameterValues['*:ErrorAction']
$PSDefaultParameterValues['*:ErrorAction'] = 'Stop'

try {
    # Global help interception (before executing any action)
    if ($Help) {
        if ($Action -eq 'logs') { Show-LogsHelp } else { Show-GeneralHelp }
        exit 0
    }
    $Global:CurrentAction = $Action
    # Run main function
    Invoke-Main $Action
}
catch {
    Write-Error-Log "Script interrupted: $_"
    # Do not stop services if we were only viewing logs or status
    if ($Global:CurrentAction -in @('logs','status')) {
        exit 130
    } else {
        Stop-Services
        exit 130
    }
}
finally {
    if ($hadErrorActionDefault) {
        $PSDefaultParameterValues['*:ErrorAction'] = $originalAction
    } else {
        [void]$PSDefaultParameterValues.Remove('*:ErrorAction')
    }
}


