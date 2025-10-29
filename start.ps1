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
    Operation mode: Interactive (default), Start, Dev, Stop, Status, Logs, Rebuild, Clean

.PARAMETER NoAnalyzer
    Skip analyzer microservices (faster dev startup)

.PARAMETER NoFollow
    Disable auto-follow for logs (show snapshot only)

.PARAMETER Background
    Run services in background without interactive console

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
    .\start.ps1 -Mode Dev -NoAnalyzer
    # Quick dev mode without analyzers

.EXAMPLE
    .\start.ps1 -Mode Logs -NoFollow
    # Show logs without auto-follow
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('Interactive', 'Start', 'Dev', 'Stop', 'Status', 'Logs', 'Rebuild', 'Clean', 'Wipeout', 'Health', 'Help')]
    [string]$Mode = 'Interactive',

    [switch]$NoAnalyzer,
    [switch]$NoFollow,
    [switch]$Background,
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
    Flask = @{
        Name = "Flask"
        PidFile = Join-Path $RUN_DIR "flask.pid"
        LogFile = Join-Path $LOGS_DIR "app.log"
        Port = $Port
        HealthEndpoint = "http://127.0.0.1:$Port/health"
        StartupTime = 10
        Color = "Cyan"
    }
    Analyzers = @{
        Name = "Analyzers"
        PidFile = Join-Path $RUN_DIR "analyzer.pid"
        LogFile = Join-Path $LOGS_DIR "analyzer.log"
        Services = @('static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer')
        Ports = @(2001, 2002, 2003, 2004)
        StartupTime = 15
        Color = "Green"
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
        } catch {
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
        } catch {
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
                            Color = $Color
                            Time = Get-Date -Format 'HH:mm:ss'
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
        } finally {
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
            } else {
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
    
    $width = 80
    $padding = [Math]::Max(0, ($width - $Text.Length - 4) / 2)
    $line = "═" * $width
    
    Write-Host ""
    Write-Host "╔$line╗" -ForegroundColor $Color
    Write-Host "║$(' ' * $padding) $Text $(' ' * $padding)║" -ForegroundColor $Color
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
        Flask = [ServiceState]::new('Flask')
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
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Status "  Python: System Python found" "Warning"
        $Script:PYTHON_CMD = "python"
    } else {
        $issues += "Python not found (neither .venv nor system)"
    }

    # Check Docker
    try {
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Status "  Docker: Running" "Success"
        } else {
            $issues += "Docker is not running"
        }
    } catch {
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

function Start-AnalyzerServices {
    if ($NoAnalyzer) {
        Write-Status "Skipping analyzer services (NoAnalyzer flag)" "Warning"
        return $true
    }

    Write-Status "Starting analyzer microservices..." "Info"
    
    Push-Location $Script:ANALYZER_DIR
    try {
        # Start all analyzer services
        docker-compose up -d 2>&1 | Out-File -FilePath $Script:CONFIG.Analyzers.LogFile -Append
        
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
            
            $services = docker-compose ps --services --filter status=running 2>$null
            if ($services -and $services.Count -ge 4) {
                Write-Host ""
                Write-Status "  Analyzer services started (${waited}s)" "Success"
                
                # Show service status
                $services | ForEach-Object {
                    Write-Host "    • $_" -ForegroundColor Green
                }
                
                $Script:Services.Analyzers.UpdateStatus('Running', 'Healthy')
                "analyzer-compose" | Out-File -FilePath $Script:CONFIG.Analyzers.PidFile -Encoding ASCII
                return $true
            }
        }

        Write-Host ""
        Write-Status "  Some analyzer services may not have started" "Warning"
        return $true
    } finally {
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
        } else {
            Write-Status "  Flask starting in foreground..." "Success"
            Write-Host "    URL: http://127.0.0.1:$Port" -ForegroundColor Gray
            Write-Host "    Press Ctrl+C to stop all services`n" -ForegroundColor Yellow
            
            # Run in foreground - will block
            & $Script:PYTHON_CMD @arguments
        }

        $Script:Services.Flask.UpdateStatus('Running', 'Healthy')
        return $true
    } catch {
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
        # Docker services
        Push-Location $Script:ANALYZER_DIR
        try {
            docker-compose stop static-analyzer dynamic-analyzer performance-tester ai-analyzer gateway 2>$null | Out-Null
            Write-Status "  $ServiceName stopped" "Success"
        } finally {
            Pop-Location
        }
        
        if ($config.PidFile -and (Test-Path $config.PidFile)) {
            Remove-Item $config.PidFile -Force
        }
    } else {
        # Process-based services
        if (Test-Path $config.PidFile) {
            $processId = Get-Content $config.PidFile -Raw
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            
            if ($process) {
                Write-Status "  Stopping $ServiceName (PID: $processId)..." "Info"
                $process.Kill()
                $process.WaitForExit(5000)
                Write-Status "  $ServiceName stopped" "Success"
            }
            
            Remove-Item $config.PidFile -Force
        }
    }

    $Script:Services[$ServiceName].UpdateStatus('Stopped', 'Unknown')
}

function Stop-AllServices {
    Write-Banner "Stopping ThesisApp Services"
    
    # Stop in reverse dependency order
    $stopOrder = @('Flask', 'Analyzers')
    
    foreach ($service in $stopOrder) {
        Stop-Service $service
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
                Write-Host "     Task Execution: ThreadPoolExecutor (4 workers)" -ForegroundColor DarkGray
            }
            if ($key -eq 'Analyzers' -and $state.Metadata['ServiceCount']) {
                Write-Host "     Services: $($state.Metadata['ServiceCount'])/4" -ForegroundColor DarkGray
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

function Start-FullStack {
    Write-Banner "Starting ThesisApp Full Stack"
    
    # Dependency-aware startup sequence
    $success = $true
    
    # 1. Analyzer services (optional but recommended)
    if (-not (Start-AnalyzerServices)) {
        Write-Status "Analyzer services failed, but continuing..." "Warning"
    }
    
    # 2. Flask app (with built-in ThreadPoolExecutor task execution)
    if (-not (Start-FlaskApp)) {
        Write-Status "Failed to start Flask application" "Error"
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
        Write-Banner "ThesisApp Started Successfully"
        Write-Host "🌐 Application URL: " -NoNewline -ForegroundColor Cyan
        Write-Host "http://127.0.0.1:$Port" -ForegroundColor White
        Write-Host "⚡ Task Execution: ThreadPoolExecutor (4 workers)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "💡 Quick Commands:" -ForegroundColor Cyan
        Write-Host "   .\start.ps1 -Mode Status    - Check service status" -ForegroundColor Gray
        Write-Host "   .\start.ps1 -Mode Logs      - View aggregated logs" -ForegroundColor Gray
        Write-Host "   .\start.ps1 -Mode Stop      - Stop all services" -ForegroundColor Gray
        Write-Host ""
    }
    
    return $success
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
    
    # Start Flask in foreground (dev mode is interactive)
    Start-FlaskApp | Out-Null
}

function Show-InteractiveMenu {
    Write-Banner "ThesisApp Orchestrator"
    
    Write-Host "Select an option:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  [S] Start     - Start full stack (Flask + Analyzers)" -ForegroundColor White
    Write-Host "  [D] Dev       - Developer mode (Flask + ThreadPoolExecutor, debug on)" -ForegroundColor White
    Write-Host "  [R] Rebuild   - Rebuild analyzer containers" -ForegroundColor White
    Write-Host "  [L] Logs      - View aggregated logs" -ForegroundColor White
    Write-Host "  [M] Monitor   - Live status monitoring" -ForegroundColor White
    Write-Host "  [H] Health    - Check service health" -ForegroundColor White
    Write-Host "  [X] Stop      - Stop all services" -ForegroundColor White
    Write-Host "  [C] Clean     - Clean logs and PID files" -ForegroundColor White
    Write-Host "  [W] Wipeout   - ⚠️  Reset to default state (DB, apps, results)" -ForegroundColor White
    Write-Host "  [?] Help      - Show detailed help" -ForegroundColor White
    Write-Host "  [Q] Quit      - Exit" -ForegroundColor White
    Write-Host ""
    
    $choice = Read-Host "Enter choice"
    
    switch ($choice.ToUpper()) {
        'S' { 
            $Script:Background = $true
            Start-FullStack
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'D' {
            Start-DevMode
        }
        'R' {
            Invoke-RebuildContainers
            Read-Host "`nPress Enter to return to menu"
            Show-InteractiveMenu
        }
        'L' {
            $logFiles = @{
                Flask = $Script:CONFIG.Flask.LogFile
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

function Invoke-RebuildContainers {
    Write-Banner "Rebuilding Analyzer Containers"
    
    Push-Location $Script:ANALYZER_DIR
    try {
        Write-Status "Stopping and removing existing containers..." "Info"
        docker-compose down --rmi all --volumes 2>&1 | Out-Null
        
        Write-Status "Building from scratch (this may take a few minutes)..." "Info"
        docker-compose build --no-cache
        
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Rebuild completed successfully" "Success"
            
            # Ask if user wants to start the services
            Write-Host ""
            Write-Host "Would you like to start the analyzer services now? (Y/N): " -NoNewline -ForegroundColor Yellow
            $response = Read-Host
            
            if ($response -eq 'Y' -or $response -eq 'y') {
                Write-Status "Starting analyzer services..." "Info"
                docker-compose up -d 2>&1 | Out-Null
                
                if ($LASTEXITCODE -eq 0) {
                    Start-Sleep -Seconds 3
                    
                    # Show running services
                    $runningServices = docker-compose ps --services --filter status=running 2>$null
                    if ($runningServices) {
                        Write-Status "Services started successfully:" "Success"
                        $runningServices | ForEach-Object {
                            Write-Host "  • $_" -ForegroundColor Green
                        }
                    }
                } else {
                    Write-Status "Failed to start services" "Error"
                }
            } else {
                Write-Status "Services not started - use [S] Start to launch them later" "Info"
            }
            
            return $true
        } else {
            Write-Status "Rebuild failed" "Error"
            return $false
        }
    } finally {
        Pop-Location
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
        } else {
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
        } catch {
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

function Invoke-Wipeout {
    Write-Banner "⚠️  WIPEOUT - Reset to Default State" "Red"
    
    Write-Host "This will:" -ForegroundColor Yellow
    Write-Host "  • Stop all running services" -ForegroundColor Yellow
    Write-Host "  • Delete the database (src/data/)" -ForegroundColor Yellow
    Write-Host "  • Remove all generated apps (generated/)" -ForegroundColor Yellow
    Write-Host "  • Remove all analysis results (results/)" -ForegroundColor Yellow
    Write-Host "  • Create fresh admin user" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "⚠️  THIS CANNOT BE UNDONE! ⚠️" -ForegroundColor Red -BackgroundColor Black
    Write-Host ""
    Write-Host "Type 'WIPEOUT' to confirm (or anything else to cancel): " -NoNewline -ForegroundColor Yellow
    $confirmation = Read-Host
    
    if ($confirmation -ne 'WIPEOUT') {
        Write-Status "Wipeout cancelled" "Warning"
        return $false
    }
    
    Write-Host ""
    Write-Status "Starting wipeout procedure..." "Warning"
    
    # 1. Stop all services
    Write-Status "Stopping all services..." "Info"
    Stop-AllServices
    Start-Sleep -Seconds 2
    
    # 2. Remove database
    $dbDir = Join-Path $Script:SRC_DIR "data"
    if (Test-Path $dbDir) {
        Write-Status "Removing database..." "Info"
        try {
            Remove-Item -Path $dbDir -Recurse -Force -ErrorAction Stop
            Write-Status "  Database removed" "Success"
        } catch {
            Write-Status "  Failed to remove database: $_" "Error"
        }
    }
    
    # 3. Remove generated apps
    $generatedDir = Join-Path $Script:ROOT_DIR "generated"
    if (Test-Path $generatedDir) {
        Write-Status "Removing generated apps..." "Info"
        try {
            Get-ChildItem -Path $generatedDir -Exclude ".migration_done" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction Stop
            Write-Status "  Generated apps removed" "Success"
        } catch {
            Write-Status "  Failed to remove generated apps: $_" "Error"
        }
    }
    
    # 4. Remove results
    $resultsDir = Join-Path $Script:ROOT_DIR "results"
    if (Test-Path $resultsDir) {
        Write-Status "Removing analysis results..." "Info"
        try {
            Remove-Item -Path $resultsDir -Recurse -Force -ErrorAction Stop
            New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null
            Write-Status "  Results removed" "Success"
        } catch {
            Write-Status "  Failed to remove results: $_" "Error"
        }
    }
    
    # 5. Remove logs
    Write-Status "Removing logs..." "Info"
    Get-ChildItem -Path $Script:LOGS_DIR -Filter "*.log" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $Script:LOGS_DIR -Filter "*.log.old" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    
    # 6. Remove PID files
    Write-Status "Removing PID files..." "Info"
    Get-ChildItem -Path $Script:RUN_DIR -Filter "*.pid" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    
    # 7. Recreate database and admin user
    Write-Status "Initializing fresh database..." "Info"
    $createAdminScript = Join-Path $Script:ROOT_DIR "scripts\create_admin.py"
    
    if (Test-Path $createAdminScript) {
        try {
            & $Script:PYTHON_CMD $createAdminScript
            if ($LASTEXITCODE -eq 0) {
                Write-Status "  Database and admin user created" "Success"
            } else {
                Write-Status "  Failed to create admin user" "Error"
            }
        } catch {
            Write-Status "  Error running create_admin.py: $_" "Error"
        }
    } else {
        Write-Status "  create_admin.py not found at $createAdminScript" "Warning"
    }
    
    Write-Host ""
    Write-Banner "✅ Wipeout Complete - System Reset" "Green"
    Write-Host "Default credentials:" -ForegroundColor Cyan
    Write-Host "  Username: admin" -ForegroundColor White
    Write-Host "  Password: ia5aeQE2wR87J8w" -ForegroundColor White
    Write-Host "  Email: admin@thesis.local" -ForegroundColor White
    Write-Host ""
    Write-Status "You can now start the application with [S] Start" "Info"
    
    return $true
}

function Show-Help {
    Write-Banner "ThesisApp Orchestrator - Help"
    
    Write-Host "USAGE:" -ForegroundColor Cyan
    Write-Host "  .\start.ps1 [MODE] [OPTIONS]`n" -ForegroundColor White
    
    Write-Host "MODES:" -ForegroundColor Cyan
    Write-Host "  Interactive   Launch interactive menu (default)" -ForegroundColor White
    Write-Host "  Start         Start full stack (Flask + Analyzers)" -ForegroundColor White
    Write-Host "  Dev           Developer mode (Flask with ThreadPoolExecutor, debug enabled)" -ForegroundColor White
    Write-Host "  Stop          Stop all services gracefully" -ForegroundColor White
    Write-Host "  Status        Show service status (one-time check)" -ForegroundColor White
    Write-Host "  Health        Continuous health monitoring (auto-refresh)" -ForegroundColor White
    Write-Host "  Logs          View aggregated logs from all services" -ForegroundColor White
    Write-Host "  Rebuild       Rebuild analyzer Docker containers" -ForegroundColor White
    Write-Host "  Clean         Clean logs and PID files" -ForegroundColor White
    Write-Host "  Wipeout       ⚠️  Reset to default state (removes DB, apps, results)" -ForegroundColor White
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
    
    Write-Host "  .\start.ps1 -Mode Start -Background" -ForegroundColor Yellow
    Write-Host "    → Start full stack in background`n" -ForegroundColor DarkGray
    
    Write-Host "  .\start.ps1 -Mode Dev -NoAnalyzer" -ForegroundColor Yellow
    Write-Host "    → Quick dev mode without analyzer containers`n" -ForegroundColor DarkGray
    
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
                    } finally {
                        Stop-AllServices
                    }
                }
            } else {
                exit 1
            }
        }
        'Dev' {
            Start-DevMode
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
                Flask = $Script:CONFIG.Flask.LogFile
                Analyzers = $Script:CONFIG.Analyzers.LogFile
            }
            $aggregator = [LogAggregator]::new($logFiles, (-not $NoFollow))
            $aggregator.Start()
        }
        'Rebuild' {
            Invoke-RebuildContainers
        }
        'Clean' {
            Invoke-Cleanup
        }
        'Wipeout' {
            Invoke-Wipeout
        }
        'Help' {
            Show-Help
        }
    }
} catch {
    Write-Status "Fatal error: $_" "Error"
    Write-Host $_.ScriptStackTrace -ForegroundColor Red
    exit 1
} finally {
    # Cleanup on exit
    if ($Script:HealthMonitor) {
        $Script:HealthMonitor.Stop()
    }
}
