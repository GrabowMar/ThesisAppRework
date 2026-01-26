#!/usr/bin/env pwsh
#Requires -Version 7.0

<#
.SYNOPSIS
    ThesisApp Orchestrator - Modern service management for Flask + Analyzers

.DESCRIPTION
    Complete orchestration script for ThesisApp with:
    - Dependency-aware startup sequencing (Analyzers → Flask)
    - Real-time health monitoring with auto-refresh
    - Live log aggregation with color-coded output
    - Interactive mode selection and graceful shutdown
    - Developer mode with configurable analyzer stack

.PARAMETER Mode
    Operation mode: Interactive (default), Start, Dev, Stop, Status, Logs, Rebuild, CleanRebuild, Clean

.PARAMETER NoAnalyzer
    Skip analyzer microservices (faster dev startup)

.PARAMETER NoFollow
    Disable auto-follow for logs (show snapshot only)

.PARAMETER Background
    Run services in background without interactive console

.PARAMETER Concurrent
    Start analyzer services in concurrent mode with horizontal scaling.
    Deploys multiple replicas: 3x static, 2x dynamic, 2x performance, 2x AI analyzers.
    Total capacity: ~18 simultaneous analyses vs ~4 in standard mode.

.PARAMETER Port
    Flask application port (default: 5000)

.PARAMETER Verbose
    Enable verbose diagnostic output

.EXAMPLE
    .\start.ps1
    # Interactive mode with menu

.EXAMPLE
    .\start.ps1 -Mode Start
    # Start full stack with live monitoring

.EXAMPLE
    .\start.ps1 -Mode Start -Concurrent
    # Start with concurrent analyzer mode (9 replicas, high capacity)

.EXAMPLE
    .\start.ps1 -Mode Dev -NoAnalyzer
    # Quick dev mode without analyzers

.EXAMPLE
    .\start.ps1 -Mode Logs -NoFollow
    # Show logs without auto-follow
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('Interactive', 'Start', 'Docker', 'Local', 'Dev', 'Stop', 'Status', 'Logs', 'Rebuild', 'CleanRebuild', 'Clean', 'Wipeout', 'Nuke', 'Health', 'Help', 'Password', 'Maintenance', 'Reload')]
    [string]$Mode = 'Interactive',

    [switch]$NoAnalyzer,
    [switch]$NoFollow,
    [switch]$Background,
    [switch]$Concurrent,
    [int]$Port = 5000
)

# ============================================================================
# CONFIGURATION
# ============================================================================

$ErrorActionPreference = 'Stop'
$Script:ROOT_DIR = $PSScriptRoot
$Script:SRC_DIR = Join-Path $ROOT_DIR "src"
$Script:ANALYZER_DIR = Join-Path $ROOT_DIR "analyzer"
$Script:LOGS_DIR = Join-Path $ROOT_DIR "logs"
$Script:RUN_DIR = Join-Path $ROOT_DIR "run"

# Service configuration
$Script:CONFIG = @{
    Flask     = @{
        Name           = "Flask"
        PidFile        = Join-Path $RUN_DIR "flask.pid"
        LogFile        = Join-Path $LOGS_DIR "app.log"
        Port           = $Port
        HealthEndpoint = "http://127.0.0.1:$Port/api/health"
        StartupTime    = 10
        Color          = "Cyan"
    }
    Analyzers = @{
        Name            = "Analyzers"
        PidFile         = Join-Path $RUN_DIR "analyzer.pid"
        LogFile         = Join-Path $LOGS_DIR "analyzer.log"
        Services        = @('static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer')
        Ports           = @(2001, 2002, 2003, 2004)
        StartupTime     = 15
        Color           = "Green"
        # Concurrent mode configuration for horizontal scaling
        ConcurrentPorts = @{
            'static-analyzer'    = @(2001, 2051, 2052)
            'dynamic-analyzer'   = @(2002, 2053)
            'performance-tester' = @(2003, 2054)
            'ai-analyzer'        = @(2004, 2055)
        }
    }
}

# Global state
$Script:Services = @{}
$Script:HealthMonitor = $null
$Script:LogJobs = @()
$Script:PYTHON_CMD = $null

# ============================================================================
# UTILITY CLASSES
# ============================================================================

class ServiceState {
    [string]$Name
    [string]$Status  # Stopped, Starting, Running, Degraded, Failed
    [DateTime]$LastCheck
    [string]$Health  # Healthy, Unhealthy, Unknown
    [int]$Pid
    [string]$Error
    [hashtable]$Metadata

    ServiceState([string]$name) {
        $this.Name = $name
        $this.Status = 'Stopped'
        $this.Health = 'Unknown'
        $this.LastCheck = Get-Date
        $this.Metadata = @{}
    }

    [void]UpdateStatus([string]$status, [string]$health) {
        $this.Status = $status
        $this.Health = $health
        $this.LastCheck = Get-Date
    }

    [string]GetDisplayStatus() {
        $statusIcon = switch ($this.Status) {
            'Running' { '🟢' }
            'Starting' { '🟡' }
            'Degraded' { '🟠' }
            'Failed' { '🔴' }
            default { '⚪' }
        }
        return "$statusIcon $($this.Name): $($this.Status)"
    }
}

class HealthMonitor {
    [hashtable]$Services
    [bool]$Running
    [System.Management.Automation.Job]$MonitorJob

    HealthMonitor([hashtable]$services) {
        $this.Services = $services
        $this.Running = $false
    }

    [void]Start() {
        if ($this.Running) { return }
        $this.Running = $true
        Write-Verbose "Health monitor started"
    }

    [void]Stop() {
        $this.Running = $false
        if ($this.MonitorJob) {
            Stop-Job -Job $this.MonitorJob -ErrorAction SilentlyContinue
            Remove-Job -Job $this.MonitorJob -ErrorAction SilentlyContinue
        }
    }

    [hashtable]CheckAll() {
        $results = @{}
        foreach ($key in $this.Services.Keys) {
            $results[$key] = $this.CheckService($key)
        }
        return $results
    }

    [bool]CheckService([string]$serviceName) {
        $state = $this.Services[$serviceName]
        
        switch ($serviceName) {
            'Flask' {
                return $this.CheckFlask($state)
            }
            'Analyzers' {
                return $this.CheckAnalyzers($state)
            }
            default {
                return $false
            }
        }
        return $false  # Fallback (should never reach here)
    }

    [bool]CheckFlask([ServiceState]$state) {
        try {
            if (-not (Test-Path $Script:CONFIG.Flask.PidFile)) { return $false }
            
            $processId = Get-Content $Script:CONFIG.Flask.PidFile -Raw
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if (-not $process) { return $false }

            # Try health endpoint
            $response = Invoke-RestMethod -Uri $Script:CONFIG.Flask.HealthEndpoint -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.status -eq 'healthy') {
                $state.UpdateStatus('Running', 'Healthy')
                return $true
            }
            $state.UpdateStatus('Degraded', 'Unhealthy')
            return $true
        }
        catch {
            return $false
        }
    }

    [bool]CheckAnalyzers([ServiceState]$state) {
        try {
            Push-Location $Script:ANALYZER_DIR
            $runningServices = docker-compose ps --services --filter status=running 2>$null
            Pop-Location
            
            if ($runningServices -and $runningServices.Count -gt 0) {
                $state.UpdateStatus('Running', 'Healthy')
                $state.Metadata['ServiceCount'] = $runningServices.Count
                return $true
            }
            return $false
        }
        catch {
            Pop-Location -ErrorAction SilentlyContinue
            return $false
        }
    }
}

class LogAggregator {
    [hashtable]$LogFiles
    [System.Collections.ArrayList]$Jobs
    [bool]$Following

    LogAggregator([hashtable]$logFiles, [bool]$follow) {
        $this.LogFiles = $logFiles
        $this.Jobs = [System.Collections.ArrayList]::new()
        $this.Following = $follow
    }

    [void]Start() {
        if (-not $this.Following) {
            $this.ShowSnapshot()
            return
        }

        Write-Host "`n📜 Starting live log aggregation (Ctrl+C to stop)..." -ForegroundColor Cyan
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`n" -ForegroundColor DarkGray

        foreach ($key in $this.LogFiles.Keys) {
            $logFile = $this.LogFiles[$key]
            $color = $Script:CONFIG[$key].Color
            
            if (Test-Path $logFile) {
                $job = Start-Job -ScriptBlock {
                    param($LogPath, $ServiceName, $Color)
                    Get-Content -Path $LogPath -Tail 0 -Wait | ForEach-Object {
                        [PSCustomObject]@{
                            Service = $ServiceName
                            Message = $_
                            Color   = $Color
                            Time    = Get-Date -Format 'HH:mm:ss'
                        }
                    }
                } -ArgumentList $logFile, $key, $color

                $this.Jobs.Add($job) | Out-Null
            }
        }

        try {
            while ($true) {
                foreach ($job in $this.Jobs) {
                    $data = Receive-Job -Job $job -ErrorAction SilentlyContinue
                    foreach ($item in $data) {
                        $prefix = "[$($item.Time)] [$($item.Service.PadRight(9))]"
                        Write-Host $prefix -ForegroundColor $item.Color -NoNewline
                        Write-Host " $($item.Message)"
                    }
                }
                Start-Sleep -Milliseconds 100
            }
        }
        finally {
            $this.Stop()
        }
    }

    [void]ShowSnapshot() {
        Write-Host "`n📜 Log Snapshot (last 50 lines per service):`n" -ForegroundColor Cyan
        
        foreach ($key in $this.LogFiles.Keys) {
            $logFile = $this.LogFiles[$key]
            $color = $Script:CONFIG[$key].Color
            
            if (Test-Path $logFile) {
                Write-Host "━━━ $key " -ForegroundColor $color -NoNewline
                Write-Host ("━" * (70 - $key.Length)) -ForegroundColor DarkGray
                
                Get-Content -Path $logFile -Tail 50 | ForEach-Object {
                    Write-Host "  $_" -ForegroundColor Gray
                }
                Write-Host ""
            }
            else {
                Write-Host "━━━ $key " -ForegroundColor $color -NoNewline
                Write-Host ("━" * (70 - $key.Length)) -ForegroundColor DarkGray
                Write-Host "  (No log file found)" -ForegroundColor DarkGray
                Write-Host ""
            }
        }
    }

    [void]Stop() {
        foreach ($job in $this.Jobs) {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            Remove-Job -Job $job -ErrorAction SilentlyContinue
        }
        $this.Jobs.Clear()
    }
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

function Write-Banner {
    param([string]$Text, [string]$Color = 'Cyan')

    # Use a dynamic width to avoid line-wrapping in narrower terminals.
    $defaultInnerWidth = 80
    $innerWidth = $defaultInnerWidth
    try {
        $windowWidth = $Host.UI.RawUI.WindowSize.Width
        if ($windowWidth -gt 0) {
            # Leave a small safety margin; wrapping at the right edge looks like a broken box.
            $innerWidth = [Math]::Min($defaultInnerWidth, [Math]::Max(20, $windowWidth - 4))
        }
    }
    catch {
        $innerWidth = $defaultInnerWidth
    }

    $line = "═" * $innerWidth
    $content = " $Text "
    if ($content.Length -gt $innerWidth) {
        $content = $content.Substring(0, $innerWidth)
    }

    $leftPad = [int][Math]::Floor(($innerWidth - $content.Length) / 2)
    $rightPad = $innerWidth - $content.Length - $leftPad
    $middle = (" " * $leftPad) + $content + (" " * $rightPad)

    Write-Host ""
    Write-Host "╔$line╗" -ForegroundColor $Color
    Write-Host "║$middle║" -ForegroundColor $Color
    Write-Host "╚$line╝" -ForegroundColor $Color
    Write-Host ""
}

function Write-Status {
    param(
        [string]$Message,
        [string]$Type = 'Info'  # Info, Success, Warning, Error
    )
    
    $icon = switch ($Type) {
        'Success' { '✅'; $color = 'Green' }
        'Warning' { '⚠️ '; $color = 'Yellow' }
        'Error' { '❌'; $color = 'Red' }
        default { 'ℹ️ '; $color = 'Cyan' }
    }
    
    Write-Host "$icon $Message" -ForegroundColor $color
}

function Initialize-Environment {
    Write-Status "Initializing environment..." "Info"
    
    # Create required directories
    @($Script:LOGS_DIR, $Script:RUN_DIR) | ForEach-Object {
        if (-not (Test-Path $_)) {
            New-Item -ItemType Directory -Path $_ -Force | Out-Null
        }
    }

    # Ensure shared Docker network exists (prevents network pool exhaustion)
    Write-Status "Ensuring shared Docker network exists..." "Info"
    try {
        $networkExists = docker network ls --filter name=thesis-apps-network --format "{{.Name}}" 2>$null
        if (-not $networkExists) {
            docker network create thesis-apps-network 2>$null | Out-Null
            Write-Status "  Created shared network: thesis-apps-network" "Success"
        }
        else {
            Write-Status "  Shared network exists: thesis-apps-network" "Success"
        }
    }
    catch {
        Write-Status "  Warning: Could not create shared network (Docker may not be running)" "Warning"
    }

    # Set environment variables
    $env:FLASK_ENV = 'development'
    $env:HOST = '127.0.0.1'
    $env:PORT = $Port
    $env:DEBUG = 'false'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'

    # Initialize service states
    $Script:Services = @{
        Analyzers = [ServiceState]::new('Analyzers')
        Flask     = [ServiceState]::new('Flask')
    }

    # Initialize health monitor
    $Script:HealthMonitor = [HealthMonitor]::new($Script:Services)

    Write-Status "Environment initialized" "Success"
}

function Test-Dependencies {
    Write-Status "Checking dependencies..." "Info"
    
    $issues = @()

    # Check Python
    $venvPython = Join-Path $Script:ROOT_DIR ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        Write-Status "  Python: .venv virtual environment found" "Success"
        $Script:PYTHON_CMD = $venvPython
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Status "  Python: System Python found" "Warning"
        $Script:PYTHON_CMD = "python"
    }
    else {
        $issues += "Python not found (neither .venv nor system)"
    }

    # Check Docker
    try {
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Status "  Docker: Running" "Success"
        }
        else {
            $issues += "Docker is not running"
        }
    }
    catch {
        $issues += "Docker not found"
    }

    # Check required directories
    if (-not (Test-Path $Script:SRC_DIR)) {
        $issues += "Source directory not found: $Script:SRC_DIR"
    }
    if (-not (Test-Path $Script:ANALYZER_DIR)) {
        $issues += "Analyzer directory not found: $Script:ANALYZER_DIR"
    }

    if ($issues.Count -gt 0) {
        Write-Status "Dependency check failed:" "Error"
        $issues | ForEach-Object { Write-Host "  • $_" -ForegroundColor Red }
        return $false
    }

    Write-Status "All dependencies satisfied" "Success"
    return $true
}

function Test-RedisConnection {
    <#
    .SYNOPSIS
    Test Redis TCP connectivity
    #>
    param(
        [int]$Port = 6379,
        [int]$TimeoutSec = 5
    )

    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $async = $tcpClient.BeginConnect('127.0.0.1', $Port, $null, $null)
        $wait = $async.AsyncWaitHandle.WaitOne($TimeoutSec * 1000, $false)

        if ($wait -and $tcpClient.Connected) {
            $tcpClient.Close()
            return $true
        }
        $tcpClient.Close()
        return $false
    }
    catch {
        return $false
    }
}

function Start-RedisContainer {
    <#
    .SYNOPSIS
    Start Redis container using root docker-compose.yml
    #>
    Write-Status "Starting Redis container..." "Info"

    # Check if already running
    $existing = docker ps --filter "name=^thesisapprework-redis-1$" --format "{{.Names}}" 2>$null
    if ($existing -like "*redis*") {
        Write-Status "  ✓ Redis already running" "Success"
        return $true
    }

    # Start using root docker-compose
    Push-Location $Script:ROOT_DIR
    try {
        $output = docker compose up -d redis 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Status "  ✗ Failed to start Redis: $output" "Error"
            return $false
        }

        # Wait for Redis to be healthy
        Write-Host "  ⏳ Waiting for Redis health check" -NoNewline -ForegroundColor Cyan
        $maxWait = 30
        $waited = 0

        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 1
            $waited++
            Write-Host "." -NoNewline -ForegroundColor Yellow

            if (Test-RedisConnection) {
                Write-Host ""
                Write-Status "  ✓ Redis started and healthy (${waited}s)" "Success"
                return $true
            }
        }

        Write-Host ""
        Write-Status "  ✗ Redis health check timeout after ${maxWait}s" "Error"
        Write-Status "    Check logs: docker logs thesisapprework-redis-1" "Info"
        return $false
    }
    finally {
        Pop-Location
    }
}

function Start-CeleryWorkerContainer {
    <#
    .SYNOPSIS
    Start Celery worker container using root docker-compose.yml
    #>
    Write-Status "Starting Celery worker container..." "Info"

    # Check if already running
    $existing = docker ps --filter "name=^thesisapprework-celery-worker-1$" --format "{{.Names}}" 2>$null
    if ($existing -like "*celery-worker*") {
        Write-Status "  ✓ Celery worker already running" "Success"
        return $true
    }

    # Start using root docker-compose
    Push-Location $Script:ROOT_DIR
    try {
        $output = docker compose up -d celery-worker 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Status "  ✗ Failed to start Celery worker: $output" "Error"
            return $false
        }

        # Wait for Celery worker to be healthy (takes longer to start)
        Write-Host "  ⏳ Waiting for Celery worker health check" -NoNewline -ForegroundColor Cyan
        $maxWait = 60
        $waited = 0

        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 2
            $waited += 2
            Write-Host "." -NoNewline -ForegroundColor Yellow

            $health = docker inspect --format='{{.State.Health.Status}}' thesisapprework-celery-worker-1 2>$null
            if ($health -eq "healthy") {
                Write-Host ""
                Write-Status "  ✓ Celery worker started and healthy (${waited}s)" "Success"
                return $true
            }
        }

        Write-Host ""
        Write-Status "  ⚠ Celery worker health check timeout after ${maxWait}s" "Warning"
        Write-Status "    Tasks will fallback to ThreadPool execution" "Info"
        Write-Status "    Check logs: docker logs thesisapprework-celery-worker-1" "Info"
        return $false
    }
    finally {
        Pop-Location
    }
}

function Start-AnalyzerServices {
    if ($NoAnalyzer) {
        Write-Status "Skipping analyzer services (NoAnalyzer flag)" "Warning"
        return $true
    }

    # Always use root stack
    $composeFile = "docker-compose.yml"
    $targetDir = $Script:ROOT_DIR
    $modeLabel = "Standard"
    
    # Base analyzer services + redis
    $servicesToStart = @('analyzer-gateway', 'static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer', 'redis')
    $expectedServices = 6
    
    if ($Concurrent) {
        $modeLabel = "Concurrent (Horizontal Scaling)"
        $expectedServices = 11 # 1 gateway + 4 standards + 5 replicas + 1 redis
        
        Write-Status "Starting analyzers in CONCURRENT mode with horizontal scaling..." "Info"
        Write-Host "  📊 Deploying 9 analyzer replicas via Root Stack:" -ForegroundColor Cyan
        Write-Host "     • 3× static-analyzer    (ports 2001, 2051, 2052)" -ForegroundColor Gray
        Write-Host "     • 2× dynamic-analyzer   (ports 2002, 2053)" -ForegroundColor Gray
        Write-Host "     • 2× performance-tester (ports 2003, 2054)" -ForegroundColor Gray
        Write-Host "     • 2× ai-analyzer        (ports 2004, 2055)" -ForegroundColor Gray
        Write-Host ""
        
        # Add replicas to startup list
        $servicesToStart += @(
            'static-analyzer-2', 'static-analyzer-3', 
            'dynamic-analyzer-2', 
            'performance-tester-2', 
            'ai-analyzer-2'
        )
        
        # Set environment variables for pooled connections (using container names for internal docker comms if needed, 
        # but here we set them for the host if running local, though web container uses its own env)
        $env:STATIC_ANALYZER_URLS = "ws://localhost:2001,ws://localhost:2051,ws://localhost:2052"
        $env:DYNAMIC_ANALYZER_URLS = "ws://localhost:2002,ws://localhost:2053"
        $env:PERF_TESTER_URLS = "ws://localhost:2003,ws://localhost:2054"
        $env:AI_ANALYZER_URLS = "ws://localhost:2004,ws://localhost:2055"
    }
    else {
        Write-Status "Starting analyzer microservices (Standard mode via Root Stack)..." "Info"
    }
    
    # Ensure any legacy analyzer-project containers are stopped
    Write-Status "Ensuring clean state for analyzer services..." "Info"
    docker compose -p analyzer down 2>$null | Out-Null
    
    Push-Location $targetDir
    try {
        # Start selected services
        $cmdArgs = @("compose", "-f", $composeFile, "up", "-d") + $servicesToStart
        
        docker @cmdArgs 2>&1 | Out-File -FilePath $Script:CONFIG.Analyzers.LogFile -Append
        
        if ($LASTEXITCODE -ne 0) {
            Write-Status "  Failed to start analyzer services" "Error"
            return $false
        }

        # Wait for services to be ready
        $maxWait = $Script:CONFIG.Analyzers.StartupTime
        $waited = 0
        
        Write-Host "  Waiting for services" -NoNewline -ForegroundColor Cyan
        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 1
            $waited++
            Write-Host "." -NoNewline -ForegroundColor Yellow
            
            # Check only the services we intended to start
            $runningServices = docker compose -f $composeFile ps --services --filter status=running 2>$null
            $runningCount = 0
            foreach ($s in $servicesToStart) {
                if ($runningServices -contains $s) { $runningCount++ }
            }
            
            if ($runningCount -ge $expectedServices) {
                Write-Host ""
                Write-Status "  Analyzer services started (${waited}s) - Mode: $modeLabel" "Success"
                
                if ($Concurrent) {
                    Write-Host ""
                    Write-Host "  🚀 Total concurrent analysis capacity: ~18 simultaneous analyses" -ForegroundColor Cyan
                }
                
                # Store PID/mode info
                $Script:Services.Analyzers.UpdateStatus('Running', 'Healthy')
                $Script:Services.Analyzers.Metadata['Mode'] = $modeLabel
                $Script:Services.Analyzers.Metadata['ServiceCount'] = $runningCount
                
                # Save mode info to pid file for stop command
                $modeInfo = @{
                    compose_file = $composeFile
                    directory    = $targetDir
                    mode         = if ($Concurrent) { "concurrent" } else { "standard" }
                    services     = $servicesToStart
                } | ConvertTo-Json -Compress
                $modeInfo | Out-File -FilePath $Script:CONFIG.Analyzers.PidFile -Encoding ASCII
                
                return $true
            }
        }

        Write-Host ""
        Write-Status "  Some analyzer services may not have started (got $runningCount/$expectedServices)" "Warning"
        return $true
    }
    finally {
        Pop-Location
    }
}


function Start-FlaskApp {
    Write-Status "Starting Flask application..." "Info"
    
    # Check if already running
    if (Test-Path $Script:CONFIG.Flask.PidFile) {
        $processId = Get-Content $Script:CONFIG.Flask.PidFile -Raw
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) {
            Write-Status "  Flask already running (PID: $processId)" "Success"
            return $true
        }
    }

    try {
        $arguments = @(
            (Join-Path $Script:SRC_DIR "main.py")
        )

        if ($Background) {
            $stderrLog = Join-Path $Script:LOGS_DIR "flask_stderr.log"
            $process = Start-Process -FilePath $Script:PYTHON_CMD `
                -ArgumentList $arguments `
                -WorkingDirectory $Script:SRC_DIR `
                -WindowStyle Hidden `
                -PassThru `
                -RedirectStandardOutput $Script:CONFIG.Flask.LogFile `
                -RedirectStandardError $stderrLog

            $process.Id | Out-File -FilePath $Script:CONFIG.Flask.PidFile -Encoding ASCII
            
            Write-Status "  Flask started in background (PID: $($process.Id))" "Success"
            Write-Host "    URL: http://127.0.0.1:$Port" -ForegroundColor Gray
        }
        else {
            Write-Status "  Flask starting in foreground..." "Success"
            Write-Host "    URL: http://127.0.0.1:$Port" -ForegroundColor Gray
            Write-Host "    Press Ctrl+C to stop all services`n" -ForegroundColor Yellow
            
            # Run in foreground - will block
            & $Script:PYTHON_CMD @arguments
        }

        $Script:Services.Flask.UpdateStatus('Running', 'Healthy')
        return $true
    }
    catch {
        Write-Status "  Failed to start Flask: $_" "Error"
        return $false
    }
}

function Stop-Service {
    param(
        [string]$ServiceName
    )

    $config = $Script:CONFIG[$ServiceName]
    
    if ($ServiceName -eq 'Analyzers') {
        # Docker services - read mode info from pid file
        $composeFile = "docker-compose.yml"
        $targetDir = $Script:ANALYZER_DIR
        
        if ($config.PidFile -and (Test-Path $config.PidFile)) {
            try {
                $modeInfo = Get-Content $config.PidFile -Raw | ConvertFrom-Json -ErrorAction SilentlyContinue
                if ($modeInfo.compose_file) {
                    $composeFile = $modeInfo.compose_file
                }
                if ($modeInfo.directory) {
                    $targetDir = $modeInfo.directory
                }
            }
            catch {
                # Fall back to default if JSON parsing fails
            }
        }
        
        Push-Location $targetDir
        try {
            # Use specific services if we are in standard mode (Root stack) to avoid stopping web/celery?
            # Actually 'stop' stops specific services if listed?
            # But earlier we did 'up -d service1 service2'.
            # If we run 'docker compose stop', it stops ALL services defined in the file that are running.
            # If we are using Root Compose, 'stop' might stop web/celery?
            # Yes, if they are running.
            
            # BUT 'Stop-Service Analyzers' is usually called when stopping just Analyzers.
            # If we are in 'Local' mode, Web is running as a PROCESS, not container.
            # So stopping Root Compose containers won't affect Web Process.
            # If we are in 'Start' mode (Full Docker), 'Stop-AllServices' calls 'Stop-DockerStack' anyway?
            
            # Let's see Stop-AllServices (line 778):
            # if (Test-Path $modeFile) { Stop-DockerStack }
            # else { Stop-Service Flask; Stop-Service Analyzers }
            
            # If we are in Local mode (Start-LocalStack):
            # We used Start-AnalyzerServices (which now uses Root Compose).
            # We want to stop ONLY analyzer containers?
            # 'docker compose stop' stops defined services.
            # If 'web' is not running (because we didn't start it), 'stop' does nothing to it.
            # If 'web' IS running (e.g. from a previous Start run), 'stop' will stop it.
            # This is probably fine. 'Stop-Service Analyzers' implies stopping the containers.
            
            docker compose -f $composeFile stop 2>$null | Out-Null
            Write-Status "  $ServiceName stopped (compose: $composeFile)" "Success"
        }
        finally {
            Pop-Location
        }
        
        if ($config.PidFile -and (Test-Path $config.PidFile)) {
            Remove-Item $config.PidFile -Force
        }
    }
    else {
        # Process-based services (Flask)
        $stopped = $false
        
        # First try to stop via PID file
        if (Test-Path $config.PidFile) {
            $processId = Get-Content $config.PidFile -Raw
            $processId = $processId.Trim()
            
            if ($processId -match '^\d+$') {
                $process = Get-Process -Id ([int]$processId) -ErrorAction SilentlyContinue
                
                if ($process) {
                    Write-Status "  Stopping $ServiceName (PID: $processId)..." "Info"
                    try {
                        $process.Kill()
                        $process.WaitForExit(5000)
                        $stopped = $true
                        Write-Status "  $ServiceName stopped" "Success"
                    }
                    catch {
                        Write-Status "  Warning: Could not kill process $processId" "Warning"
                    }
                }
            }
            
            Remove-Item $config.PidFile -Force -ErrorAction SilentlyContinue
        }
        
        # Also try to find and kill any Flask processes running main.py (fallback)
        if (-not $stopped) {
            try {
                $flaskProcesses = Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object {
                    try {
                        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
                        $cmdLine -and $cmdLine -like "*main.py*"
                    }
                    catch { $false }
                }
                
                if ($flaskProcesses) {
                    foreach ($proc in $flaskProcesses) {
                        Write-Status "  Stopping $ServiceName process (PID: $($proc.Id))..." "Info"
                        try {
                            $proc | Stop-Process -Force -ErrorAction SilentlyContinue
                            $stopped = $true
                        }
                        catch {
                            # Process might have already exited
                        }
                    }
                    if ($stopped) {
                        Write-Status "  $ServiceName stopped" "Success"
                    }
                }
            }
            catch {
                # Ignore errors in fallback cleanup
            }
        }
        
        if (-not $stopped) {
            Write-Status "  $ServiceName was not running" "Info"
        }
    }

    $Script:Services[$ServiceName].UpdateStatus('Stopped', 'Unknown')
}

function Stop-AllServices {
    Write-Banner "Stopping ThesisApp Services"

    # Check if we're in Docker mode
    $modeFile = Join-Path $Script:RUN_DIR "docker.mode"
    if (Test-Path $modeFile) {
        Stop-DockerStack
    }

    # Stop in reverse dependency order (local services)
    $stopOrder = @('Flask', 'Analyzers')

    foreach ($service in $stopOrder) {
        Stop-Service $service
    }

    # Stop Celery worker and Redis containers
    Write-Status "Stopping Celery worker and Redis containers..." "Info"
    Push-Location $Script:ROOT_DIR
    try {
        docker compose stop celery-worker redis 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Status "  ✓ Celery worker and Redis stopped" "Success"
        }
    }
    catch {
        # Silently continue - containers may not be running
    }
    finally {
        Pop-Location
    }

    Write-Status "All services stopped" "Success"
}

function Show-StatusDashboard {
    param([bool]$ContinuousRefresh = $false)

    do {
        Clear-Host
        Write-Banner "ThesisApp Status Dashboard"
        
        $healthResults = $Script:HealthMonitor.CheckAll()
        
        Write-Host "Services Status:" -ForegroundColor Cyan
        Write-Host ("─" * 80) -ForegroundColor DarkGray
        
        foreach ($key in @('Analyzers', 'Flask')) {
            $state = $Script:Services[$key]
            $isHealthy = $healthResults[$key]
            
            $statusIcon = if ($isHealthy) { '🟢' } else { '🔴' }
            $statusText = if ($isHealthy) { 'Running' } else { 'Stopped' }
            $healthText = $state.Health
            
            Write-Host "  $statusIcon " -NoNewline
            Write-Host "$($key.PadRight(12))" -NoNewline -ForegroundColor White
            Write-Host " Status: " -NoNewline -ForegroundColor Gray
            Write-Host "$($statusText.PadRight(10))" -NoNewline -ForegroundColor $(if ($isHealthy) { 'Green' } else { 'Red' })
            Write-Host " Health: " -NoNewline -ForegroundColor Gray
            Write-Host "$healthText" -ForegroundColor $(if ($healthText -eq 'Healthy') { 'Green' } elseif ($healthText -eq 'Unhealthy') { 'Yellow' } else { 'Gray' })
            
            # Additional info
            if ($key -eq 'Flask' -and $isHealthy) {
                Write-Host "     URL: http://127.0.0.1:$($Script:CONFIG.Flask.Port)" -ForegroundColor DarkGray
                Write-Host "     Task Execution: Celery Distributed Task Queue" -ForegroundColor DarkGray
            }
            if ($key -eq 'Analyzers' -and $state.Metadata['ServiceCount']) {
                $expected = if ($state.Metadata['Mode'] -like '*Concurrent*') { 11 } else { 6 }
                Write-Host "     Services: $($state.Metadata['ServiceCount'])/$expected ($($state.Metadata['Mode']))" -ForegroundColor DarkGray
            }
        }
        
        Write-Host ("─" * 80) -ForegroundColor DarkGray
        Write-Host "Last check: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
        
        if ($ContinuousRefresh) {
            Write-Host "`nRefreshing in 5s... (Press Ctrl+C to stop)" -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    } while ($ContinuousRefresh)
}

function Start-LocalStack {
    Write-Banner "Starting ThesisApp Local Stack (Flask + Analyzers + Redis/Celery)"

    # Dependency-aware startup sequence
    $success = $true

    # 1. Redis (message broker for Celery - CRITICAL FIRST)
    if (-not (Start-RedisContainer)) {
        Write-Status "⚠ Failed to start Redis - analysis tasks may not work properly" "Warning"
        Write-Status "   Tasks will fallback to ThreadPool execution" "Info"
        $success = $false
    }

    # 2. Celery worker (task executor - DEPENDS ON REDIS)
    if (-not (Start-CeleryWorkerContainer)) {
        Write-Status "⚠ Failed to start Celery worker - will fallback to ThreadPool" "Warning"
        Write-Status "   Distributed task execution unavailable" "Info"
    }

    # 3. Analyzer services (optional but recommended)
    if (-not (Start-AnalyzerServices)) {
        Write-Status "⚠ Analyzer services failed, but continuing..." "Warning"
    }

    # 4. Flask app (can detect Redis/Celery availability)
    if (-not (Start-FlaskApp)) {
        Write-Status "✗ Failed to start Flask application" "Error"
        return $false
    }
    
    # Wait for Flask to be fully ready
    if ($Background) {
        Write-Host "`n⏳ Waiting for Flask to be ready..." -ForegroundColor Yellow
        $maxWait = 10
        $waited = 0
        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 1
            $waited++
            
            if ($Script:HealthMonitor.CheckFlask($Script:Services.Flask)) {
                Write-Status "`nFlask is ready! (${waited}s)" "Success"
                break
            }
            Write-Host "." -NoNewline -ForegroundColor Yellow
        }
        
        Write-Host ""
        Write-Banner "ThesisApp Started (Local Mode with Distributed Execution)"
        Write-Host "🌐 Application URL: " -NoNewline -ForegroundColor Cyan
        Write-Host "http://127.0.0.1:$Port" -ForegroundColor White
        Write-Host "⚡ Task Execution: Celery + Redis (distributed, scalable)" -ForegroundColor Green
        Write-Host "   Fallback: ThreadPoolExecutor if Redis/Celery unavailable" -ForegroundColor Gray
        Write-Host ""
        Write-Host "💡 Quick Commands:" -ForegroundColor Cyan
        Write-Host "   .\start.ps1 -Mode Status    - Check service status" -ForegroundColor Gray
        Write-Host "   .\start.ps1 -Mode Logs      - View aggregated logs" -ForegroundColor Gray
        Write-Host "   .\start.ps1 -Mode Stop      - Stop all services" -ForegroundColor Gray
        Write-Host ""
    }
    
    return $success
}

function Start-DockerStack {
    Write-Banner "Starting ThesisApp Docker Production Stack"
    
    Write-Host "🐳 Production Docker configuration:" -ForegroundColor Yellow
    Write-Host "  • Flask app running in container (production mode)" -ForegroundColor Gray
    Write-Host "  • Celery + Redis for distributed task execution" -ForegroundColor Gray
    Write-Host "  • All analyzer microservices containerized" -ForegroundColor Gray
    Write-Host "  • Shared thesis-network for inter-container communication" -ForegroundColor Gray
    Write-Host ""
    
    # Check if root docker-compose.yml exists
    $composeFile = Join-Path $Script:ROOT_DIR "docker-compose.yml"
    if (-not (Test-Path $composeFile)) {
        Write-Status "docker-compose.yml not found in project root" "Error"
        return $false
    }
    
    Write-Status "Building and starting Docker production stack..." "Info"
    Write-Host "  (This may take several minutes if images need to be rebuilt)" -ForegroundColor Gray
    Write-Host ""
    
    # Define services to start
    $servicesToStart = @('web', 'celery-worker', 'redis', 'analyzer-gateway', 'static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer')
    
    if ($Concurrent) {
        Write-Status "Enabling CONCURRENT mode for Docker stack..." "Info"
        $servicesToStart += @('static-analyzer-2', 'static-analyzer-3', 'dynamic-analyzer-2', 'performance-tester-2', 'ai-analyzer-2')
    }

    Push-Location $Script:ROOT_DIR
    try {
        # Build and start selected services
        $logFile = Join-Path $Script:LOGS_DIR "docker-compose.log"
        
        Write-Host "━━━━━━━━━━━━ Docker Build Output ━━━━━━━━━━━━" -ForegroundColor DarkGray
        $cmdArgs = @("compose", "up", "-d", "--build") + $servicesToStart
        docker @cmdArgs 2>&1 | Tee-Object -FilePath $logFile -Append | ForEach-Object {
            # Color-code the output for better readability
            $line = $_
            if ($line -match "error|failed|fatal" -and $line -notmatch "errorhandler") {
                Write-Host $line -ForegroundColor Red
            }
            elseif ($line -match "warning") {
                Write-Host $line -ForegroundColor Yellow
            }
            elseif ($line -match "Started|Running|Created|Built|Pulled") {
                Write-Host $line -ForegroundColor Green
            }
            elseif ($line -match "Building|Downloading|Extracting") {
                Write-Host $line -ForegroundColor Cyan
            }
            else {
                Write-Host $line -ForegroundColor Gray
            }
        }
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
        Write-Host ""
        
        $buildExitCode = $LASTEXITCODE
        
        if ($buildExitCode -ne 0) {
            Write-Status "Failed to start Docker stack (exit code: $buildExitCode)" "Error"
            Write-Host "Check logs at: $logFile" -ForegroundColor Yellow
            return $false
        }
        
        Write-Status "Docker containers starting..." "Success"
        
        # Wait for services to be healthy
        $maxWait = 120
        $waited = 0
        
        Write-Host "  Waiting for services to be ready" -NoNewline -ForegroundColor Cyan
        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 2
            $waited += 2
            Write-Host "." -NoNewline -ForegroundColor Yellow
            
            # Check web service health
            try {
                $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
                if ($response.StatusCode -eq 200) {
                    Write-Host ""
                    Write-Status "All services are ready! (${waited}s)" "Success"
                    break
                }
            }
            catch {
                # Not ready yet, continue waiting
            }
        }
        
        if ($waited -ge $maxWait) {
            Write-Host ""
            Write-Status "Timeout waiting for services (check docker compose logs)" "Warning"
        }
        
        # Show container status
        Write-Host ""
        Write-Host "📦 Container Status:" -ForegroundColor Cyan
        docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>$null | ForEach-Object {
            Write-Host "  $_" -ForegroundColor Gray
        }
        
        Write-Host ""
        Write-Banner "ThesisApp Docker Stack Started"
        Write-Host "🌐 Application URL: " -NoNewline -ForegroundColor Cyan
        Write-Host "http://127.0.0.1:$Port" -ForegroundColor White
        Write-Host "⚡ Task Execution: Celery + Redis (distributed)" -ForegroundColor Gray
        Write-Host "🔧 Analyzer Gateway: ws://127.0.0.1:8765" -ForegroundColor Gray
        Write-Host ""
        Write-Host "💡 Quick Commands:" -ForegroundColor Cyan
        Write-Host "   .\start.ps1 -Mode Status    - Check service status" -ForegroundColor Gray
        Write-Host "   docker compose logs -f      - View live container logs" -ForegroundColor Gray
        Write-Host "   .\start.ps1 -Mode Stop      - Stop all services" -ForegroundColor Gray
        Write-Host ""
        
        # Mark Docker mode for Stop-AllServices
        $Script:DockerMode = $true
        "docker-compose" | Out-File -FilePath (Join-Path $Script:RUN_DIR "docker.mode") -Encoding ASCII
        
        return $true
    }
    finally {
        Pop-Location
    }
}

function Stop-DockerStack {
    Write-Status "Stopping Docker production stack..." "Info"
    
    Push-Location $Script:ROOT_DIR
    try {
        docker compose down 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Docker stack stopped" "Success"
        }
        else {
            Write-Status "Warning: Some containers may not have stopped cleanly" "Warning"
        }
        
        # Clean up mode file
        $modeFile = Join-Path $Script:RUN_DIR "docker.mode"
        if (Test-Path $modeFile) {
            Remove-Item $modeFile -Force
        }
    }
    finally {
        Pop-Location
    }
}

function Start-FullStack {
    # Default Start mode now uses Docker production stack
    return Start-DockerStack
}

function Start-DevMode {
    Write-Banner "Starting ThesisApp (Developer Mode)"
    
    Write-Host "Developer mode configuration:" -ForegroundColor Yellow
    Write-Host "  • Flask with ThreadPoolExecutor (4 workers)" -ForegroundColor Gray
    Write-Host "  • Debug enabled" -ForegroundColor Gray
    Write-Host "  • Analyzer services: $(if ($NoAnalyzer) { 'Disabled' } else { 'Enabled' })" -ForegroundColor Gray
    Write-Host ""
    
    $env:DEBUG = 'true'
    $env:FLASK_ENV = 'development'
    
    # Start minimal stack
    if (-not $NoAnalyzer) {
        Start-AnalyzerServices | Out-Null
    }
    
    # Generate and set admin password for dev mode
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'
    $devPassword = -join ((1..16) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    
    $resetScript = @"
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from app.factory import create_app
from app.models import User
from app.extensions import db

app = create_app()
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', email='admin@thesis.local', full_name='System Administrator')
        admin.set_password('$devPassword')
        admin.is_admin = True
        admin.is_active = True
        db.session.add(admin)
    else:
        admin.set_password('$devPassword')
    db.session.commit()
    print('OK')
"@
    
    $tempScript = Join-Path $Script:ROOT_DIR "temp_dev_password.py"
    $resetScript | Out-File -FilePath $tempScript -Encoding UTF8
    
    try {
        $output = & $Script:PYTHON_CMD $tempScript 2>&1
        if ($LASTEXITCODE -eq 0 -and $output -match 'OK') {
            Write-Host "Admin Credentials:" -ForegroundColor Cyan
            Write-Host "  Username: " -NoNewline -ForegroundColor White
            Write-Host "admin" -ForegroundColor Green
            Write-Host "  Password: " -NoNewline -ForegroundColor White
            Write-Host "$devPassword" -ForegroundColor Green
            Write-Host ""
        }
    }
    catch {
        Write-Status "Warning: Could not set dev password" "Warning"
    }
    finally {
        if (Test-Path $tempScript) {
            Remove-Item $tempScript -Force -ErrorAction SilentlyContinue
        }
    }
    
    # Start Flask in foreground (dev mode is interactive)
    Start-FlaskApp | Out-Null
}

function Show-InteractiveMenu {
    Write-Banner "ThesisApp Orchestrator"
    
    Write-Host "Select an option:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  [S] Start        - 🐳 Start Docker production stack (containerized, Celery+Redis)" -ForegroundColor White
    Write-Host "  [K] Local        - Start local stack (Flask + Analyzers, non-containerized)" -ForegroundColor White
    Write-Host "  [D] Dev          - Developer mode (Flask + ThreadPoolExecutor, debug on)" -ForegroundColor White
    Write-Host "  [O] Reload       - 🔄 Quick reload (Stop → Start for live code changes)" -ForegroundColor White
    Write-Host "  [R] Rebuild      - Rebuild containers (fast, with cache)" -ForegroundColor White
    Write-Host "  [F] CleanRebuild - ⚠️  Force rebuild (no cache, slow)" -ForegroundColor White
    Write-Host "  [L] Logs         - View aggregated logs" -ForegroundColor White
    Write-Host "  [M] Monitor      - Live status monitoring" -ForegroundColor White
    Write-Host "  [H] Health       - Check service health" -ForegroundColor White
    Write-Host "  [X] Stop         - Stop all services" -ForegroundColor White
    Write-Host "  [C] Clean        - Clean logs and PID files" -ForegroundColor White
    Write-Host "  [W] Wipeout      - ⚠️  Reset to default state (DB, apps, results, reports)" -ForegroundColor White
    Write-Host "  [N] Nuke         - 🔥 Wipeout then Rebuild stack" -ForegroundColor Red
    Write-Host "  [P] Password     - Reset admin password to random value" -ForegroundColor White
    Write-Host "  [?] Help         - Show detailed help" -ForegroundColor White
    Write-Host "  [Q] Quit         - Exit" -ForegroundColor White
    Write-Host ""
    
    $choice = Read-Host "Enter choice"
    
    switch ($choice.ToUpper()) {
        'S' { 
            $Script:Background = $true
            Start-DockerStack
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'K' {
            $Script:Background = $true
            Start-LocalStack
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'D' {
            Start-DevMode
        }
        'O' {
            Invoke-Reload
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'R' {
            Invoke-RebuildContainers
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'F' {
            Invoke-CleanRebuild
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'L' {
            $logFiles = @{
                Flask     = $Script:CONFIG.Flask.LogFile
                Analyzers = $Script:CONFIG.Analyzers.LogFile
            }
            $aggregator = [LogAggregator]::new($logFiles, (-not $NoFollow))
            $aggregator.Start()
            Show-InteractiveMenu
        }
        'M' {
            Show-StatusDashboard -ContinuousRefresh $true
            Show-InteractiveMenu
        }
        'H' {
            Show-StatusDashboard -ContinuousRefresh $false
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'X' {
            Stop-AllServices
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'C' {
            Invoke-Cleanup
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'W' {
            Invoke-Wipeout
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'N' {
            Invoke-Nuke
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'P' {
            Invoke-ResetPassword
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        '?' {
            Show-Help
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'Q' {
            Write-Host "`nGoodbye! 👋" -ForegroundColor Cyan
            exit 0
        }
        default {
            Write-Status "Invalid choice. Please try again." "Warning"
            Start-Sleep -Seconds 1
            Show-InteractiveMenu
        }
    }
}

function Invoke-Nuke {
    Write-Banner "🔥 NUKING SYSTEM - Wipeout & Refresh" "Red"
    
    Write-Host "Performing full WIPEOUT and fast REBUILD." -ForegroundColor Yellow
    # Confirmation prompt removed for automation/convenience
    
    Write-Status "Phase 1: Wipeout..." "Warning"
    if (-not (Invoke-Wipeout)) {
        return $false
    }
    
    # RE-INITIALIZE environment after wipeout (recreates missing networks)
    Write-Status "Phase 1.5: Re-initializing environment..." "Info"
    Initialize-Environment
    
    Write-Status "Phase 2: Rebuilding stack..." "Info"
    Invoke-RebuildContainers -AutoStart $true
    
    Write-Banner "✅ Nuke Operation Complete" "Green"
    return $true
}

function Invoke-RebuildContainers {
    param([bool]$AutoStart = $false)

    Write-Banner "Rebuilding Docker Stack"
    
    # Use ROOT directory (same as Start-DockerStack) to avoid duplicate stacks
    Push-Location $Script:ROOT_DIR
    try {
        Write-Status "Stopping and removing existing containers..." "Info"
        docker compose down 2>&1 | Out-Null
        
        # Enable BuildKit for faster builds and cache mounts
        $env:DOCKER_BUILDKIT = 1
        $env:COMPOSE_DOCKER_CLI_BUILD = 1
        
        Write-Status "Building with BuildKit optimization..." "Info"
        Write-Host "  • Shared base image caching enabled" -ForegroundColor Gray
        Write-Host "  • Multi-stage builds with layer reuse" -ForegroundColor Gray
        Write-Host "  • BuildKit cache mounts for pip/npm" -ForegroundColor Gray
        Write-Host ""
        
        # Build all services in parallel with BuildKit optimizations
        Write-Status "Building all services (web, celery, analyzers)..." "Info"
        Write-Host "  • Services will share Python base image layers" -ForegroundColor Gray
        Write-Host "  • Node.js installation cached per service" -ForegroundColor Gray
        Write-Host ""
        
        # Build all services from root docker-compose.yml
        docker compose build --parallel
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Banner "✅ Rebuild Complete" "Green"
            
            Write-Host "Build Optimization Summary:" -ForegroundColor Cyan
            Write-Host "  ✓ BuildKit cache mounts enabled" -ForegroundColor Green
            Write-Host "  ✓ Python base image layers shared across services" -ForegroundColor Green
            Write-Host "  ✓ Multi-stage builds minimize final image size" -ForegroundColor Green
            Write-Host "  ✓ ZAP (390MB) cached in build layer" -ForegroundColor Green
            Write-Host "  ✓ Node.js installation cached per service" -ForegroundColor Green
            Write-Host ""
            
            Write-Host "Expected Build Times:" -ForegroundColor Cyan
            Write-Host "  • First build (clean):      ~12-18 minutes" -ForegroundColor Yellow
            Write-Host "  • Incremental (code only):  ~30-90 seconds" -ForegroundColor Green
            Write-Host "  • Dependency updates:       ~3-5 minutes" -ForegroundColor Yellow
            Write-Host ""
            
            # Ask if user wants to start the services (unless AutoStart is set)
            $shouldStart = $AutoStart
            
            if (-not $shouldStart) {
                Write-Host "Would you like to start all services now? (Y/N): " -NoNewline -ForegroundColor Yellow
                $response = Read-Host
                if ($response -eq 'Y' -or $response -eq 'y') {
                    $shouldStart = $true
                }
            }
            
            if ($shouldStart) {
                Write-Status "Starting all services..." "Info"
                try {
                    $upOutput = docker compose up -d 2>&1
                    if ($LASTEXITCODE -eq 0) {
                        Start-Sleep -Seconds 3
                    
                        # Show running services
                        Write-Status "Services started:" "Success"
                        docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>$null | ForEach-Object {
                            Write-Host "  $_" -ForegroundColor Gray
                        }
                    
                        # Mark Docker mode
                        "docker-compose" | Out-File -FilePath (Join-Path $Script:RUN_DIR "docker.mode") -Encoding ASCII
                    }
                    else {
                        Write-Status "Failed to start services" "Error"
                        Write-Host "Output: $upOutput" -ForegroundColor Red
                    }
                }
                catch {
                    Write-Status "Services not started (Try/Catch Error): $_" "Error"
                }
            
                return $true
            }
            else {
                Write-Status "Services not started - use [S] Start to launch them later" "Info"
                return $true
            }
        }
        else {
            Write-Status "Rebuild failed" "Error"
            return $false
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-CleanRebuild {
    Write-Banner "⚠️  Clean Rebuild - Complete Cache Wipe" "Yellow"
    
    Write-Host "This will:" -ForegroundColor Yellow
    Write-Host "  • Remove all Docker images and volumes" -ForegroundColor Yellow
    Write-Host "  • Clear BuildKit cache" -ForegroundColor Yellow
    Write-Host "  • Force complete rebuild from scratch" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "⚠️  Use this only if experiencing build issues!" -ForegroundColor Yellow
    Write-Host "    Normal rebuilds are much faster with caching." -ForegroundColor Gray
    Write-Host ""
    Write-Host "Type 'CLEAN' to confirm (or anything else to cancel): " -NoNewline -ForegroundColor Yellow
    $confirmation = Read-Host
    
    if ($confirmation -ne 'CLEAN') {
        Write-Status "Clean rebuild cancelled - use 'Rebuild' for faster cached builds" "Warning"
        return $false
    }
    
    # Use ROOT directory (same as Start-DockerStack) to avoid duplicate stacks
    Push-Location $Script:ROOT_DIR
    try {
        Write-Status "Performing deep clean..." "Info"
        
        # Full cleanup
        docker compose down --rmi all --volumes 2>&1 | Out-Null
        
        # Clear BuildKit cache
        Write-Status "Clearing BuildKit cache..." "Info"
        docker builder prune --all --force 2>&1 | Out-Null
        
        # Enable BuildKit
        $env:DOCKER_BUILDKIT = 1
        $env:COMPOSE_DOCKER_CLI_BUILD = 1
        
        Write-Status "Building from scratch (this will take 12-18 minutes)..." "Warning"
        docker compose build --no-cache --parallel
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Banner "✅ Clean Rebuild Complete" "Green"
            Write-Status "All caches rebuilt - subsequent builds will be fast again" "Success"
            return $true
        }
        else {
            Write-Status "Clean rebuild failed" "Error"
            return $false
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-ResetPassword {
    Write-Banner "Reset Admin Password"
    
    Write-Host ""
    Write-Host "This will reset the admin user password to a new random value." -ForegroundColor Yellow
    Write-Host "The new password will be displayed on screen." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Continue? (Y/N): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host
    
    if ($response -ne 'Y' -and $response -ne 'y') {
        Write-Status "Password reset cancelled" "Info"
        return
    }
    
    # Generate random password (16 characters, mixed case + numbers + symbols)
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'
    $newPassword = -join ((1..16) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    
    # Create Python script to reset password
    $resetScript = @"
import sys
from pathlib import Path

# Add src directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR
SRC_DIR = PROJECT_ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))

from app.factory import create_app
from app.models import User
from app.extensions import db

def main():
    app = create_app()
    
    with app.app_context():
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        
        if not admin:
            # Create admin user if it doesn't exist
            admin = User(
                username='admin',
                email='admin@thesis.local',
                full_name='System Administrator'
            )
            admin.set_password('$newPassword')
            admin.is_admin = True
            admin.is_active = True
            db.session.add(admin)
            db.session.commit()
            print('CREATED')
        else:
            # Update existing admin password
            admin.set_password('$newPassword')
            db.session.commit()
            print('SUCCESS')

if __name__ == '__main__':
    main()
"@
    
    # Write temporary script
    $tempScript = Join-Path $Script:ROOT_DIR "temp_reset_password.py"
    $resetScript | Out-File -FilePath $tempScript -Encoding UTF8
    
    try {
        Write-Status "Resetting admin password..." "Info"
        
        $output = $null
        $dockerModeFile = Join-Path $Script:RUN_DIR "docker.mode"
        
        if (Test-Path $dockerModeFile) {
            Write-Status "Detected Docker environment - executing inside container..." "Info"
            
            # Need to run docker commands from root where compose file is
            Push-Location $Script:ROOT_DIR
            try {
                # Get the container ID for the web service
                $containerId = docker compose ps -q web 2>$null
                
                if ([string]::IsNullOrWhiteSpace($containerId)) {
                    throw "Could not find running 'web' container. Ensure the stack is running with [S] Start."
                }
                $containerId = $containerId.Trim()
                
                # Copy the temp script into the container
                # Note: We can't write directly to /app because it's not a volume mount of root
                $containerScriptPath = "/app/temp_reset_password.py"
                docker cp "temp_reset_password.py" "$($containerId):$containerScriptPath"
                
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to copy password reset script to container"
                }
                
                # Execute the script inside the container
                $output = docker exec $containerId python $containerScriptPath 2>&1
                
                # Cleanup script inside container
                docker exec $containerId rm $containerScriptPath 2>$null | Out-Null
                
            }
            catch {
                $output = "Docker Error: $_"
                $LASTEXITCODE = 1
            }
            finally {
                Pop-Location
            }
        }
        else {
            # Local execution
            $output = & $Script:PYTHON_CMD $tempScript 2>&1
        }
        
        # Debug output to diagnose issue
        Write-Host ""
        Write-Host "DEBUG - Exit Code: $LASTEXITCODE" -ForegroundColor Cyan
        Write-Host "DEBUG - Output: $output" -ForegroundColor Cyan
        Write-Host "DEBUG - Password Length: $($newPassword.Length)" -ForegroundColor Cyan
        Write-Host ""
        
        if (($LASTEXITCODE -eq 0) -and ($output -match 'SUCCESS' -or $output -match 'CREATED')) {
            $action = if ($output -match 'CREATED') { "Created and Set" } else { "Reset" }
            Write-Host ""
            Write-Banner "✅ Password $action Successfully" "Green"
            Write-Host ""
            Write-Host "New Admin Credentials:" -ForegroundColor Cyan
            Write-Host "  Username: " -NoNewline -ForegroundColor White
            Write-Host "admin" -ForegroundColor Green
            Write-Host "  Password: " -NoNewline -ForegroundColor White
            Write-Host "$newPassword" -ForegroundColor Green
            Write-Host ""
            Write-Host "⚠️  IMPORTANT: Save this password now! It will not be shown again." -ForegroundColor Yellow
            Write-Host ""
        }
        else {
            Write-Status "Failed to reset password" "Error"
            Write-Host "Output: $output" -ForegroundColor Red
        }
    }
    catch {
        Write-Status "Error resetting password: $($_.Exception.Message)" "Error"
    }
    finally {
        # Clean up temporary script
        if (Test-Path $tempScript) {
            Remove-Item $tempScript -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-Reload {
    Write-Banner "🔄 Reloading ThesisApp" "Yellow"
    
    Write-Status "Quick reload for live code changes..." "Info"
    Write-Host "  This will stop and restart all services" -ForegroundColor Gray
    Write-Host ""
    
    # Stop all services
    Write-Status "Stopping services..." "Info"
    Stop-AllServices
    
    # Brief pause to ensure clean shutdown
    Start-Sleep -Seconds 1
    
    # Kill any remaining Flask/Python processes in our project directory
    Write-Status "Ensuring clean shutdown of Flask processes..." "Info"
    $killedCount = 0
    try {
        # Kill any Python processes running main.py from our project
        Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object {
            try {
                $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
                $cmdLine -and ($cmdLine -like "*$($Script:ROOT_DIR)*" -or $cmdLine -like "*main.py*")
            }
            catch { $false }
        } | ForEach-Object {
            Write-Host "    Killing process $($_.Id) ($($_.ProcessName))..." -ForegroundColor DarkGray
            $_ | Stop-Process -Force -ErrorAction SilentlyContinue
            $killedCount++
        }
    }
    catch {
        Write-Host "    Warning: Could not check for orphan processes" -ForegroundColor DarkYellow
    }
    
    if ($killedCount -gt 0) {
        Write-Status "  Killed $killedCount orphan process(es)" "Info"
        Start-Sleep -Seconds 1
    }
    
    # Clean up PID file to ensure fresh start
    if (Test-Path $Script:CONFIG.Flask.PidFile) {
        Remove-Item $Script:CONFIG.Flask.PidFile -Force -ErrorAction SilentlyContinue
        Write-Status "  Removed stale PID file" "Info"
    }
    
    # Brief pause to ensure ports are released
    Start-Sleep -Seconds 1
    
    # Reset stuck tasks
    Write-Status "Resetting stuck tasks..." "Info"
    $fixScript = Join-Path $Script:ROOT_DIR "scripts\fix_task_statuses.py"
    if (Test-Path $fixScript) {
        & $Script:PYTHON_CMD $fixScript 2>$null | Out-Null
    }

    # Start services again in background mode
    Write-Status "Restarting services..." "Info"
    
    # Set background mode for this reload
    $Script:Background = $true
    
    if (Start-FullStack) {
        Write-Host ""
        Write-Banner "✅ Reload Complete" "Green"
        Write-Host "🌐 Application URL: " -NoNewline -ForegroundColor Cyan
        Write-Host "http://127.0.0.1:$Port" -ForegroundColor White
        Write-Host "⚡ All services restarted with latest code" -ForegroundColor Gray
        Write-Host ""
        return $true
    }
    else {
        Write-Status "Reload failed - check logs for details" "Error"
        return $false
    }
}

function Invoke-Cleanup {
    Write-Banner "Cleaning ThesisApp"

    
    # Check if services are running
    $healthResults = $Script:HealthMonitor.CheckAll()
    $anyRunning = $false
    foreach ($key in $healthResults.Keys) {
        if ($healthResults[$key]) {
            $anyRunning = $true
            break
        }
    }
    
    if ($anyRunning) {
        Write-Status "Some services are still running!" "Warning"
        Write-Host "  Running services may have open log files." -ForegroundColor Yellow
        Write-Host "  Would you like to stop all services first? (Y/N): " -NoNewline -ForegroundColor Yellow
        $response = Read-Host
        
        if ($response -eq 'Y' -or $response -eq 'y') {
            Stop-AllServices
            Start-Sleep -Seconds 2
        }
        else {
            Write-Status "Cleanup cancelled - stop services first with [X] Stop" "Warning"
            return
        }
    }
    
    Write-Status "Removing PID files..." "Info"
    Get-ChildItem -Path $Script:RUN_DIR -Filter "*.pid" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    
    Write-Status "Rotating logs..." "Info"
    $rotated = 0
    $skipped = 0
    
    Get-ChildItem -Path $Script:LOGS_DIR -Filter "*.log" -ErrorAction SilentlyContinue | ForEach-Object {
        $archive = "$($_.FullName).old"
        try {
            # Remove old archive if exists
            if (Test-Path $archive) {
                Remove-Item $archive -Force -ErrorAction Stop
            }
            # Try to move current log
            Move-Item $_.FullName $archive -Force -ErrorAction Stop
            $rotated++
        }
        catch {
            Write-Host "  Skipped $($_.Name) (file in use)" -ForegroundColor DarkGray
            $skipped++
        }
    }
    
    if ($rotated -gt 0) {
        Write-Status "Rotated $rotated log file(s)" "Success"
    }
    if ($skipped -gt 0) {
        Write-Status "$skipped log file(s) skipped (in use by running services)" "Warning"
    }
    
    Write-Status "Cleanup completed" "Success"
}

function Invoke-Maintenance {
    Write-Banner "🔧 Manual Maintenance Cleanup" "Yellow"
    
    Write-Host "This will run the maintenance service to clean up:" -ForegroundColor Cyan
    Write-Host "  • Orphan app records (apps missing from filesystem for >7 days)" -ForegroundColor White
    Write-Host "  • Orphan tasks (tasks targeting non-existent apps)" -ForegroundColor White
    Write-Host "  • Stuck tasks (RUNNING for >2 hours, PENDING for >4 hours)" -ForegroundColor White
    Write-Host "  • Old completed/failed tasks (>30 days old)" -ForegroundColor White
    Write-Host ""
    Write-Host "NOTE: Apps missing for <7 days will be marked but NOT deleted." -ForegroundColor Yellow
    Write-Host "      This gives you time to restore backup/recover files." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press Enter to continue or Ctrl+C to cancel..." -ForegroundColor Gray
    Read-Host
    
    Write-Status "Running maintenance cleanup..." "Info"
    
    $maintenanceScript = @'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.services.maintenance_service import get_maintenance_service

app = create_app()

with app.app_context():
    service = get_maintenance_service()
    if service is None:
        print("ERROR: Maintenance service not initialized")
        sys.exit(1)
    
    print("\n=== Running Manual Maintenance Cleanup ===\n")
    service._run_maintenance()
    
    print("\n=== Maintenance Statistics ===")
    stats = service.stats
    print(f"Total runs: {stats['runs']}")
    print(f"Orphan apps cleaned: {stats['orphan_apps_cleaned']}")
    print(f"Orphan tasks cleaned: {stats['orphan_tasks_cleaned']}")
    print(f"Stuck tasks cleaned: {stats['stuck_tasks_cleaned']}")
    print(f"Old tasks cleaned: {stats['old_tasks_cleaned']}")
    print(f"Errors: {stats['errors']}")
    print()
'@
    
    $tempScript = Join-Path $Script:ROOT_DIR "temp_maintenance.py"
    try {
        $maintenanceScript | Out-File -FilePath $tempScript -Encoding UTF8 -Force
        
        & $Script:PYTHON_CMD $tempScript
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Status "Maintenance cleanup completed successfully" "Success"
        }
        else {
            Write-Status "Maintenance cleanup failed with exit code $LASTEXITCODE" "Error"
        }
    }
    finally {
        if (Test-Path $tempScript) {
            Remove-Item -Path $tempScript -Force -ErrorAction SilentlyContinue
        }
    }
    
    Write-Host ""
    Write-Host "View detailed logs at: $($Script:CONFIG.Flask.LogFile)" -ForegroundColor Gray
    Write-Host ""
    
    return $true
}

function Stop-BlockingProcesses {
    <#
    .SYNOPSIS
        Forcefully stops any processes that might be blocking database access.
    
    .DESCRIPTION
        This function kills Python processes related to the ThesisAppRework project
        that may be holding locks on the SQLite database file.
    #>
    
    Write-Status "Killing processes that may block database access..." "Info"
    
    $killedCount = 0
    
    # 1. Kill any Python processes in the project directory
    try {
        $projectPythonProcs = Get-Process -Name "python", "pythonw" -ErrorAction SilentlyContinue | 
        Where-Object { 
            $_.Path -like "*ThesisAppRework*" -or 
            $_.CommandLine -like "*ThesisAppRework*" 
        }
        
        foreach ($proc in $projectPythonProcs) {
            Write-Host "    • Killing Python process PID $($proc.Id): $($proc.Path)" -ForegroundColor Gray
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            $killedCount++
        }
    }
    catch {
        # Silently continue if no processes found
    }
    
    # 2. Kill any processes using python.exe from the .venv specifically
    try {
        $venvPythonProcs = Get-Process -Name "python", "pythonw" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "*$($Script:ROOT_DIR)*" }
        
        foreach ($proc in $venvPythonProcs) {
            if ($proc.Id -notin $projectPythonProcs.Id) {
                Write-Host "    • Killing venv Python process PID $($proc.Id)" -ForegroundColor Gray
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                $killedCount++
            }
        }
    }
    catch {
        # Silently continue
    }
    
    # 3. Kill Flask processes (they may hold DB connections)
    try {
        $flaskProcs = Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessName -like "*python*" -and $_.MainWindowTitle -like "*Flask*" }
        
        foreach ($proc in $flaskProcs) {
            Write-Host "    • Killing Flask process PID $($proc.Id)" -ForegroundColor Gray
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            $killedCount++
        }
    }
    catch {
        # Silently continue
    }
    
    # 4. Force kill any remaining python processes that might hold sqlite locks
    # This is a more aggressive approach - only used if database removal fails
    
    if ($killedCount -gt 0) {
        Write-Status "  Killed $killedCount process(es)" "Success"
        # Give OS time to release file handles
        Start-Sleep -Seconds 2
    }
    else {
        Write-Status "  No blocking processes found" "Info"
    }
    
    return $killedCount
}

function Stop-AllBlockingProcesses {
    <#
    .SYNOPSIS
        Aggressively kills ALL Python processes that could be blocking database access.
    
    .DESCRIPTION
        This is a more aggressive version that kills all Python/pythonw processes.
        Used as a fallback when Stop-BlockingProcesses is not sufficient.
    #>
    
    Write-Status "Force killing ALL Python processes..." "Warning"
    
    $killedCount = 0
    
    try {
        # Get all python processes
        $allPythonProcs = Get-Process -Name "python", "pythonw" -ErrorAction SilentlyContinue
        
        foreach ($proc in $allPythonProcs) {
            try {
                Write-Host "    • Force killing Python PID $($proc.Id)" -ForegroundColor Gray
                Stop-Process -Id $proc.Id -Force -ErrorAction Stop
                $killedCount++
            }
            catch {
                # Process may have already exited
            }
        }
    }
    catch {
        # No processes found
    }
    
    if ($killedCount -gt 0) {
        Write-Status "  Force killed $killedCount Python process(es)" "Success"
        # Give OS time to release file handles
        Start-Sleep -Seconds 3
    }
    
    return $killedCount
}

function Invoke-Wipeout {
    Write-Banner "⚠️  WIPEOUT - Reset to Default State" "Red"
    
    Write-Host "This will:" -ForegroundColor Yellow
    Write-Host "  • Stop all running services" -ForegroundColor Yellow
    Write-Host "  • Kill all Python processes that may block database" -ForegroundColor Yellow
    Write-Host "  • Delete the database (src/data/)" -ForegroundColor Yellow
    Write-Host "  • Remove all generated apps (generated/)" -ForegroundColor Yellow
    Write-Host "  • Remove all analysis results (results/)" -ForegroundColor Yellow
    Write-Host "  • Remove all reports (reports/)" -ForegroundColor Yellow
    Write-Host "  • Remove all Docker containers, images, and volumes (except analyzer-related)" -ForegroundColor Yellow
    Write-Host "  • Create fresh admin user" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "⚠️  THIS CANNOT BE UNDONE! ⚠️" -ForegroundColor Red -BackgroundColor Black
    Write-Host ""
    # Confirmation prompt removed
    
    Write-Host ""
    Write-Status "Starting wipeout procedure..." "Warning"
    
    # 1. Stop all services
    Write-Status "Stopping all services..." "Info"
    Stop-AllServices
    Start-Sleep -Seconds 2
    
    # 2. Kill any Python processes that might be blocking database access
    Stop-BlockingProcesses
    


    # 3. Remove Docker containers, images and volumes (Main Project)
    Write-Status "Removing Docker resources (ThesisApp project)..." "Info"
    try {
        Push-Location $Script:ROOT_DIR
        # Stop and remove ALL project containers, local images, and volumes
        docker compose down --rmi local --volumes --remove-orphans 2>&1 | Out-Null
        Pop-Location
        Write-Status "  ✓ Docker project resources wiped" "Success"
    }
    catch {
        Write-Status "  Error removing Docker resources: $_" "Warning"
    }
    
    # 4. Aggressive cleanup of any remaining analyzer-related containers/networks
    Write-Status "Ensuring total cleanup of analyzer resources..." "Info"
    try {
        # Catch any stray containers from the old 'analyzer' project or concurrent stack
        $strayContainers = docker ps -a --filter "name=analyzer" --format "{{.ID}}" 2>$null
        if ($strayContainers) {
            $strayContainers | ForEach-Object { docker rm -f $_ 2>$null | Out-Null }
        }
        
        # Prune unused images and networks to be sure
        docker network prune -f 2>$null | Out-Null
        Write-Status "  ✓ Stray analyzer resources pruned" "Success"
    }
    catch {
        Write-Status "  Error during stray resource pruning: $_" "Warning"
    }
    
    # 4. Remove database
    $dbDir = Join-Path $Script:SRC_DIR "data"
    if (Test-Path $dbDir) {
        Write-Status "Removing database..." "Info"
        
        $dbRemoved = $false
        $maxAttempts = 3
        
        for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
            try {
                Remove-Item -Path $dbDir -Recurse -Force -ErrorAction Stop
                Write-Status "  Database removed" "Success"
                $dbRemoved = $true
                break
            }
            catch {
                $errorMsg = $_.Exception.Message
                Write-Status "  Attempt $attempt/$maxAttempts failed: $errorMsg" "Warning"
                
                if ($attempt -lt $maxAttempts) {
                    # Try more aggressive process killing
                    Write-Status "  Attempting to release file locks..." "Info"
                    
                    if ($attempt -eq 1) {
                        # First retry: kill project-specific Python processes
                        Stop-BlockingProcesses
                    }
                    else {
                        # Second retry: kill ALL Python processes
                        Stop-AllBlockingProcesses
                    }
                    
                    Start-Sleep -Seconds 2
                }
            }
        }
        
        if (-not $dbRemoved) {
            Write-Status "  ⚠️ CRITICAL: Could not remove database after $maxAttempts attempts!" "Error"
            Write-Host "    Try manually:" -ForegroundColor Yellow
            Write-Host "      1. Run: taskkill /F /IM python.exe" -ForegroundColor Gray
            Write-Host "      2. Run: Remove-Item -Path '$dbDir' -Recurse -Force" -ForegroundColor Gray
        }
    }
    
    # 5. Remove generated apps AND their images (Recursive cleanup)
    $generatedDir = Join-Path $Script:ROOT_DIR "generated"
    if (Test-Path $generatedDir) {
        Write-Status "Cleaning generated apps and images..." "Info"
        
        # 5a. Clean Docker resources for ALL generated apps (recursive search)
        try {
            $composeFiles = Get-ChildItem -Path $generatedDir -Recurse -Filter "docker-compose.yml"
            foreach ($file in $composeFiles) {
                $appDir = $file.DirectoryName
                $appName = $file.Directory.Name
                
                Write-Host "  • Cleaning Docker resources for $appName..." -ForegroundColor Gray
                Push-Location $appDir
                try {
                    # Down + remove images + volumes + orphans
                    docker compose down --rmi all --volumes --remove-orphans 2>&1 | Out-Null
                }
                catch {
                    Write-Host "    Warning: Failed to clean docker resources for $appName" -ForegroundColor DarkGray
                }
                finally {
                    Pop-Location
                }
            }
        }
        catch {
            Write-Host "  Warning: Error iterating generated apps: $_" -ForegroundColor DarkGray
        }

        # 5b. Fallback: Aggressively remove any leftover containers matching sample patterns
        # Identify containers like "anthropic-claude-3-5-sonnet-app1", etc.
        Write-Status "Scanning for any leftover sample containers..." "Info"
        try {
            # Regex to match sample app container names
            $orphanContainers = docker ps -a --format "{{.Names}}" | Where-Object { 
                # Match common patterns: model-name-appN, etc.
                $_ -match "(anthropic|openai|mistral|llama|gemini).*-app\d+" -or 
                $_ -match "generated_app_\d+" 
            }
            
            if ($orphanContainers) {
                Write-Host "  • Found orphan containers: $($orphanContainers -join ', ')" -ForegroundColor Yellow
                $orphanContainers | ForEach-Object {
                    docker rm -f $_ 2>&1 | Out-Null
                }
                Write-Status "  ✓ Orphan sample containers removed" "Success"
            }
        }
        catch {
            Write-Host "  Warning checking for orphan containers: $_" -ForegroundColor DarkGray
        }

        # 5c. Fallback: Identify and remove orphan IMAGES
        try {
            $orphanImages = docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}" | Where-Object { 
                $_ -match "generated_app_\d+" -or 
                $_ -match "(anthropic|openai|mistral|llama|gemini).*-app\d+" 
            }
            
            if ($orphanImages) {
                Write-Host "  • Found orphan images..." -ForegroundColor Yellow
                $orphanImages | ForEach-Object {
                    $parts = $_ -split " "
                    $imgId = $parts[-1]
                    Write-Host "    Removing $imgId..." -ForegroundColor Gray
                    docker rmi -f $imgId 2>&1 | Out-Null
                }
                Write-Status "  ✓ Orphan sample images removed" "Success"
            }
        }
        catch {
            Write-Host "  Warning checking for orphan images: $_" -ForegroundColor DarkGray
        }

        # 5c. Remove the files
        Write-Status "Removing generated apps directory..." "Info"
        try {
            Get-ChildItem -Path $generatedDir -Exclude ".migration_done" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction Stop
            Write-Status "  Generated apps removed" "Success"
        }
        catch {
            Write-Status "  Failed to remove generated apps: $_" "Error"
        }
    }
    
    # 6. Remove results
    $resultsDir = Join-Path $Script:ROOT_DIR "results"
    if (Test-Path $resultsDir) {
        Write-Status "Removing analysis results..." "Info"
        try {
            Remove-Item -Path $resultsDir -Recurse -Force -ErrorAction Stop
            New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null
            Write-Status "  Results removed" "Success"
        }
        catch {
            Write-Status "  Failed to remove results: $_" "Error"
        }
    }

    # 7. Remove reports
    $reportsDir = Join-Path $Script:ROOT_DIR "reports"
    if (Test-Path $reportsDir) {
        Write-Status "Removing reports..." "Info"
        try {
            Remove-Item -Path $reportsDir -Recurse -Force -ErrorAction Stop
            New-Item -ItemType Directory -Path $reportsDir -Force | Out-Null
            Write-Status "  Reports removed" "Success"
        }
        catch {
            Write-Status "  Failed to remove reports: $_" "Error"
        }
    }
    
    # 8. Remove ALL logs (same as Clean menu option)
    Write-Status "Removing all logs..." "Info"
    
    # Remove all log files from logs directory
    if (Test-Path $Script:LOGS_DIR) {
        Get-ChildItem -Path $Script:LOGS_DIR -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
        Write-Status "  Application logs removed" "Success"
    }
    
    # Also check for any stderr logs
    $stderrLog = Join-Path $Script:LOGS_DIR "flask_stderr.log"
    if (Test-Path $stderrLog) {
        Remove-Item -Path $stderrLog -Force -ErrorAction SilentlyContinue
    }
    
    # 9. Remove PID files
    Write-Status "Removing PID files..." "Info"
    Get-ChildItem -Path $Script:RUN_DIR -Filter "*.pid" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    
    # 10. Recreate database and admin user with random password
    Write-Status "Initializing fresh database..." "Info"
    
    # First, run init_db.py to create tables and load data
    $initDbScript = Join-Path $Script:ROOT_DIR "src\init_db.py"
    if (Test-Path $initDbScript) {
        try {
            & $Script:PYTHON_CMD $initDbScript 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Status "  Database tables and data initialized" "Success"
            }
            else {
                Write-Status "  Warning: Database init returned non-zero exit code" "Warning"
            }
        }
        catch {
            Write-Status "  Error running init_db.py: $_" "Warning"
        }
    }
    else {
        Write-Status "  init_db.py not found - database may not be fully initialized" "Warning"
    }
    
    # Generate random password (16 characters, mixed case + numbers + symbols)
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'
    $newPassword = -join ((1..16) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    
    # Create admin user with the random password
    Write-Status "Creating admin user with secure password..." "Info"
    
    $adminScript = @"
import sys
from pathlib import Path

# Add src directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR
SRC_DIR = PROJECT_ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))

from app.factory import create_app
from app.models import User
from app.extensions import db

def main():
    app = create_app()
    
    with app.app_context():
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        
        if not admin:
            # Create admin user
            admin = User(
                username='admin',
                email='admin@thesis.local',
                full_name='System Administrator'
            )
            admin.set_password('$newPassword')
            admin.is_admin = True
            admin.is_active = True
            db.session.add(admin)
            db.session.commit()
            print('CREATED')
        else:
            # Update existing admin password
            admin.set_password('$newPassword')
            db.session.commit()
            print('SUCCESS')

if __name__ == '__main__':
    main()
"@
    
    # Write temporary script
    $tempScript = Join-Path $Script:ROOT_DIR "temp_create_admin.py"
    $adminScript | Out-File -FilePath $tempScript -Encoding UTF8
    
    $adminCreated = $false
    try {
        $output = & $Script:PYTHON_CMD $tempScript 2>&1
        
        if ($LASTEXITCODE -eq 0 -and ($output -match 'SUCCESS' -or $output -match 'CREATED')) {
            Write-Status "  Admin user created successfully" "Success"
            $adminCreated = $true
        }
        else {
            Write-Status "  Warning: Could not create admin user" "Warning"
            Write-Host "  Output: $output" -ForegroundColor DarkGray
        }
    }
    catch {
        Write-Status "  Error creating admin user: $($_.Exception.Message)" "Warning"
    }
    finally {
        # Clean up temporary script
        if (Test-Path $tempScript) {
            Remove-Item $tempScript -Force -ErrorAction SilentlyContinue
        }
    }
    
    Write-Host ""
    Write-Banner "✅ Wipeout Complete - System Reset" "Green"
    
    # 11. Auto-restart the application
    Write-Host ""
    Write-Status "Restarting application..." "Info"
    Write-Host ""
    
    # Set background mode for restart
    $Script:Background = $true
    
    # Brief pause before restart
    Start-Sleep -Seconds 1
    
    if (Start-FullStack) {
        Write-Host ""
        Write-Banner "🚀 Application Restarted" "Green"
        Write-Host "🌐 Application URL: " -NoNewline -ForegroundColor Cyan
        Write-Host "http://127.0.0.1:$Port" -ForegroundColor White
        Write-Host ""
    }
    else {
        Write-Host ""
        Write-Status "Application restart failed - try [S] Start manually" "Warning"
    }
    
    # Display credentials at the very end
    if ($adminCreated) {
        Write-Host ""
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
        Write-Host "  NEW ADMIN CREDENTIALS" -ForegroundColor Cyan
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
        Write-Host "  Username: " -NoNewline -ForegroundColor White
        Write-Host "admin" -ForegroundColor Green
        Write-Host "  Password: " -NoNewline -ForegroundColor White
        Write-Host "$newPassword" -ForegroundColor Green
        Write-Host "  Email:    " -NoNewline -ForegroundColor White
        Write-Host "admin@thesis.local" -ForegroundColor Green
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "⚠️  IMPORTANT: Save this password now! It will not be shown again." -ForegroundColor Yellow
        Write-Host ""
    }
    else {
        Write-Host ""
        Write-Host "⚠️  Admin user could not be created automatically." -ForegroundColor Yellow
        Write-Host "   Run [P] Password reset after starting the app." -ForegroundColor Yellow
        Write-Host ""
    }
    
    return $true
}

function Show-Help {
    Write-Banner "ThesisApp Orchestrator - Help"
    
    Write-Host "USAGE:" -ForegroundColor Cyan
    Write-Host "  .\start.ps1 [MODE] [OPTIONS]`n" -ForegroundColor White
    
    Write-Host "MODES:" -ForegroundColor Cyan
    Write-Host "  Interactive   Launch interactive menu (default)" -ForegroundColor White
    Write-Host "  Start         🐳 Start Docker production stack (full containerized deployment)" -ForegroundColor White
    Write-Host "  Docker        🐳 Alias for Start - Docker production stack" -ForegroundColor White
    Write-Host "  Local         Start local development (Flask via Python + Analyzer containers)" -ForegroundColor White
    Write-Host "  Dev           Developer mode (Flask with ThreadPoolExecutor, debug enabled)" -ForegroundColor White
    Write-Host "  Reload        Quick reload - stop and restart all services (for live code changes)" -ForegroundColor White
    Write-Host "  Stop          Stop all services gracefully" -ForegroundColor White
    Write-Host "  Status        Show service status (one-time check)" -ForegroundColor White
    Write-Host "  Health        Continuous health monitoring (auto-refresh)" -ForegroundColor White
    Write-Host "  Logs          View aggregated logs from all services" -ForegroundColor White
    Write-Host "  Rebuild       Rebuild containers (fast, with cache - 30-90 sec)" -ForegroundColor White
    Write-Host "  CleanRebuild  ⚠️  Force rebuild from scratch (no cache - 12-18 min)" -ForegroundColor White
    Write-Host "  Maintenance   Run manual database cleanup (7-day grace period)" -ForegroundColor White
    Write-Host "  Clean         Clean logs and PID files" -ForegroundColor White
    Write-Host "  Wipeout       ⚠️  Reset to default state (removes DB, apps, results, reports)" -ForegroundColor White
    Write-Host "  Nuke          🔥 Full Wipeout + Fast Rebuild" -ForegroundColor Red
    Write-Host "  Password      Reset admin password to random value" -ForegroundColor White
    Write-Host "  Help          Show this help message`n" -ForegroundColor White
    
    Write-Host "OPTIONS:" -ForegroundColor Cyan
    Write-Host "  -NoAnalyzer   Skip analyzer microservices (faster startup)" -ForegroundColor White
    Write-Host "  -NoFollow     Disable auto-follow for logs (show snapshot only)" -ForegroundColor White
    Write-Host "  -Background   Run services in background (no interactive console)" -ForegroundColor White
    Write-Host "  -Port <n>     Flask application port (default: 5000)" -ForegroundColor White
    Write-Host "  -Verbose      Enable verbose diagnostic output`n" -ForegroundColor White
    
    Write-Host "STARTUP SEQUENCE:" -ForegroundColor Cyan
    Write-Host "  1. Analyzers   (Optional - 4 microservices on ports 2001-2004)" -ForegroundColor Gray
    Write-Host "  2. Flask       (Required - web app with ThreadPoolExecutor on port 5000)`n" -ForegroundColor Gray
    
    Write-Host "EXAMPLES:" -ForegroundColor Cyan
    Write-Host "  .\start.ps1" -ForegroundColor Yellow
    Write-Host "    → Interactive menu for easy navigation`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Docker" -ForegroundColor Yellow
    Write-Host "    → 🐳 Start full Docker production stack (recommended)`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Docker -Background" -ForegroundColor Yellow
    Write-Host "    → 🐳 Start Docker stack in background mode`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Local" -ForegroundColor Yellow
    Write-Host "    → Local development mode (Flask via Python + Analyzer containers)`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Dev -NoAnalyzer" -ForegroundColor Yellow
    Write-Host "    → Quick dev mode without analyzer containers`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Reload" -ForegroundColor Yellow
    Write-Host "    → Quick reload for live code changes (Stop → Start)`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Logs" -ForegroundColor Yellow
    Write-Host "    → View live logs with auto-follow (Ctrl+C to stop)`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Logs -NoFollow" -ForegroundColor Yellow
    Write-Host "    → View log snapshot (last 50 lines per service)`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Status" -ForegroundColor Yellow
    Write-Host "    → Check service status once`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Health" -ForegroundColor Yellow
    Write-Host "    → Continuous monitoring with 5s auto-refresh`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Rebuild" -ForegroundColor Yellow
    Write-Host "    → Rebuild all analyzer containers from scratch`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Stop" -ForegroundColor Yellow
    Write-Host "    → Stop all running services`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Wipeout" -ForegroundColor Yellow
    Write-Host "    → Reset system to default state (removes all data)`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Password" -ForegroundColor Yellow
    Write-Host "    → Reset admin password to a new random value`n" -ForegroundColor DarkGray
    
    Write-Host "SERVICE URLS:" -ForegroundColor Cyan
    Write-Host "  Flask App:           http://127.0.0.1:5000" -ForegroundColor Gray
    Write-Host "  Static Analyzer:     ws://localhost:2001" -ForegroundColor Gray
    Write-Host "  Dynamic Analyzer:    ws://localhost:2002" -ForegroundColor Gray
    Write-Host "  Performance Tester:  ws://localhost:2003" -ForegroundColor Gray
    Write-Host "  AI Analyzer:         ws://localhost:2004" -ForegroundColor Gray
    Write-Host "  WebSocket Gateway:   ws://localhost:8765`n" -ForegroundColor Gray
    
    Write-Host "LOG FILES:" -ForegroundColor Cyan
    Write-Host "  Flask:     $($Script:CONFIG.Flask.LogFile)" -ForegroundColor Gray
    Write-Host "  Analyzers: $($Script:CONFIG.Analyzers.LogFile)`n" -ForegroundColor Gray
    
    Write-Host "DEPENDENCIES:" -ForegroundColor Cyan
    Write-Host "  • Python 3.8+ (virtual environment preferred: .venv)" -ForegroundColor Gray
    Write-Host "  • Docker Desktop (running)" -ForegroundColor Gray
    Write-Host "  • PowerShell 7.0+" -ForegroundColor Gray
    Write-Host ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

try {
    # Initialize
    Initialize-Environment
    
    if (-not (Test-Dependencies)) {
        exit 1
    }

    # Execute based on mode
    switch ($Mode) {
        'Interactive' {
            Show-InteractiveMenu
        }
        'Start' {
            $Script:Background = $Background
            if (Start-FullStack) {
                if (-not $Background) {
                    # Keep running and show status
                    Write-Host "`nPress Ctrl+C to stop all services" -ForegroundColor Yellow
                    try {
                        while ($true) {
                            Start-Sleep -Seconds 60
                        }
                    }
                    finally {
                        Stop-AllServices
                    }
                }
            }
            else {
                exit 1
            }
        }
        'Dev' {
            Start-DevMode
        }
        'Reload' {
            Invoke-Reload
        }
        'Stop' {
            Stop-AllServices
        }
        'Status' {
            Show-StatusDashboard -ContinuousRefresh $false
        }
        'Health' {
            Show-StatusDashboard -ContinuousRefresh $true
        }
        'Logs' {
            $logFiles = @{
                Flask     = $Script:CONFIG.Flask.LogFile
                Analyzers = $Script:CONFIG.Analyzers.LogFile
            }
            $aggregator = [LogAggregator]::new($logFiles, (-not $NoFollow))
            $aggregator.Start()
        }
        'Rebuild' {
            Invoke-RebuildContainers
        }
        'CleanRebuild' {
            Invoke-CleanRebuild
        }
        'Clean' {
            Invoke-Cleanup
        }
        'Wipeout' {
            Invoke-Wipeout
        }
        'Nuke' {
            Invoke-Nuke
        }
        'Maintenance' {
            Invoke-Maintenance
        }
        'Password' {
            Invoke-ResetPassword
        }
        'Docker' {
            # Direct CLI mode for Docker production stack
            $Script:Background = $Background
            if (Start-DockerStack) {
                if (-not $Background) {
                    Write-Host "`nPress Ctrl+C to stop Docker stack" -ForegroundColor Yellow
                    try {
                        while ($true) {
                            Start-Sleep -Seconds 60
                        }
                    }
                    finally {
                        Stop-DockerStack
                    }
                }
            }
            else {
                exit 1
            }
        }
        'Local' {
            # Direct CLI mode for local development (Flask + Analyzers without full Docker)
            $Script:Background = $Background
            if (Start-LocalStack) {
                if (-not $Background) {
                    Write-Host "`nPress Ctrl+C to stop local services" -ForegroundColor Yellow
                    try {
                        while ($true) {
                            Start-Sleep -Seconds 60
                        }
                    }
                    finally {
                        Stop-AllServices
                    }
                }
            }
            else {
                exit 1
            }
        }
        'Help' {
            Show-Help
        }
    }
}
catch {
    Write-Status "Fatal error: $_" "Error"
    Write-Host $_.ScriptStackTrace -ForegroundColor Red
    exit 1
}
finally {
    # Cleanup on exit
    if ($Script:HealthMonitor) {
        $Script:HealthMonitor.Stop()
    }
}
