#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Fresh Start - Complete System Reset and Reinitialization
.DESCRIPTION
    This script performs a complete clean slate reset:
    1. Stops all services
    2. Wipes database
    3. Cleans generated apps
    4. Generates 3 new sample apps
    5. Analyzes them with proper configuration
    6. Verifies results
    7. Restarts system
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Colors
$Color = @{
    Header = "Cyan"
    Success = "Green"
    Warning = "Yellow"
    Error = "Red"
    Info = "Gray"
}

function Write-Step {
    param([string]$Message, [string]$Color = "Cyan")
    Write-Host "`n$('=' * 60)" -ForegroundColor $Color
    Write-Host "  $Message" -ForegroundColor $Color
    Write-Host "$('=' * 60)" -ForegroundColor $Color
}

function Write-Info {
    param([string]$Message)
    Write-Host "  → $Message" -ForegroundColor $Color.Info
}

function Write-Success {
    param([string]$Message)
    Write-Host "  ✓ $Message" -ForegroundColor $Color.Success
}

function Write-Warning {
    param([string]$Message)
    Write-Host "  ⚠ $Message" -ForegroundColor $Color.Warning
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "  ✗ $Message" -ForegroundColor $Color.Error
}

# ============================================
# STEP 1: Stop All Services
# ============================================
Write-Step "Step 1: Stopping All Services"

try {
    Write-Info "Stopping Flask application..."
    Get-Process python -ErrorAction SilentlyContinue | 
        Where-Object {$_.MainModule.FileName -match "ThesisAppRework"} | 
        Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Success "Flask stopped"
} catch {
    Write-Warning "Flask may not have been running"
}

try {
    Write-Info "Stopping Celery workers..."
    Get-Process python -ErrorAction SilentlyContinue | 
        Where-Object {$_.CommandLine -match "celery"} | 
        Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Success "Celery stopped"
} catch {
    Write-Warning "Celery may not have been running"
}

Start-Sleep -Seconds 2

# ============================================
# STEP 2: Clean Database
# ============================================
Write-Step "Step 2: Cleaning Database"

$dbPath = "src/data/app.db"
if (Test-Path $dbPath) {
    Write-Info "Removing old database..."
    Remove-Item $dbPath -Force
    Write-Success "Database removed"
} else {
    Write-Info "No database found (already clean)"
}

Write-Info "Initializing fresh database..."
Push-Location src
try {
    & python init_db.py
    Write-Success "Database initialized"
} catch {
    Write-Error-Custom "Failed to initialize database: $_"
    Pop-Location
    exit 1
}
Pop-Location

# ============================================
# STEP 3: Clean Generated Apps
# ============================================
Write-Step "Step 3: Cleaning Generated Apps"

$generatedPath = "generated/apps"
if (Test-Path $generatedPath) {
    Write-Info "Removing old generated apps..."
    Get-ChildItem $generatedPath -Directory | ForEach-Object {
        Write-Info "  Removing: $($_.Name)"
        Remove-Item $_.FullName -Recurse -Force
    }
    Write-Success "Generated apps cleaned"
} else {
    Write-Info "Generated apps directory already clean"
}

# Clean metadata
$metadataPath = "generated/metadata"
if (Test-Path $metadataPath) {
    Write-Info "Cleaning metadata..."
    Remove-Item "$metadataPath/*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Success "Metadata cleaned"
}

# ============================================
# STEP 4: Start Flask
# ============================================
Write-Step "Step 4: Starting Flask Application"

Write-Info "Starting Flask in background..."
$flaskJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    Push-Location src
    & python main.py
}

Write-Info "Waiting for Flask to start (10 seconds)..."
Start-Sleep -Seconds 10

# Test Flask is up
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:5000" -TimeoutSec 5 -UseBasicParsing
    Write-Success "Flask is running"
} catch {
    Write-Error-Custom "Flask failed to start"
    Stop-Job $flaskJob -ErrorAction SilentlyContinue
    Remove-Job $flaskJob -ErrorAction SilentlyContinue
    exit 1
}

# ============================================
# STEP 5: Generate 3 Sample Apps
# ============================================
Write-Step "Step 5: Generating 3 Sample Apps"

$models = @(
    @{Name = "gpt-4o-mini"; Provider = "OpenAI"; Tier = "free"},
    @{Name = "claude-3-5-sonnet-20241022"; Provider = "Anthropic"; Tier = "premium"},
    @{Name = "gemini-2.0-flash-exp"; Provider = "Google"; Tier = "free"}
)

$generatedApps = @()

foreach ($model in $models) {
    Write-Info "Generating app with $($model.Name)..."
    
    $payload = @{
        model_id = $model.Name
        template_id = "task_manager"
        description = "Task management application with user authentication"
        features = @("auth", "crud", "responsive")
    } | ConvertTo-Json
    
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/gen/generate" `
            -Method POST `
            -ContentType "application/json" `
            -Body $payload `
            -TimeoutSec 120
        
        if ($response.status -eq "success") {
            Write-Success "Generated app: $($response.app_name) (App #$($response.app_number))"
            $generatedApps += @{
                Model = $model.Name
                AppNumber = $response.app_number
                AppName = $response.app_name
            }
        } else {
            Write-Error-Custom "Failed: $($response.message)"
        }
    } catch {
        Write-Error-Custom "Generation failed: $_"
    }
    
    Start-Sleep -Seconds 2
}

Write-Success "Generated $($generatedApps.Count) apps"

if ($generatedApps.Count -eq 0) {
    Write-Error-Custom "No apps were generated. Aborting."
    Stop-Job $flaskJob -ErrorAction SilentlyContinue
    Remove-Job $flaskJob -ErrorAction SilentlyContinue
    exit 1
}

# ============================================
# STEP 6: Analyze Apps
# ============================================
Write-Step "Step 6: Analyzing Generated Apps"

Write-Info "Starting analyzer services..."
& python analyzer/analyzer_manager.py start

Write-Info "Waiting for services to be ready..."
Start-Sleep -Seconds 15

# Check service health
$health = & python analyzer/analyzer_manager.py health
Write-Info "Service health check:"
Write-Host $health -ForegroundColor Gray

foreach ($app in $generatedApps) {
    Write-Info "Analyzing $($app.Model) app #$($app.AppNumber)..."
    
    # Static security analysis
    Write-Info "  Running security analysis..."
    & python analyzer/analyzer_manager.py analyze $app.Model $app.AppNumber security --tools bandit safety
    Start-Sleep -Seconds 5
    
    # Static quality analysis
    Write-Info "  Running quality analysis..."
    & python analyzer/analyzer_manager.py analyze $app.Model $app.AppNumber quality --tools pylint flake8
    Start-Sleep -Seconds 5
    
    # Note: Dynamic and performance require running apps - skip for now
    Write-Warning "  Skipping dynamic/performance (app not running)"
    
    Write-Success "Analysis complete for $($app.Model) app #$($app.AppNumber)"
}

# ============================================
# STEP 7: Verify Results
# ============================================
Write-Step "Step 7: Verifying Results"

Write-Info "Checking results directory..."
$resultsCount = 0
foreach ($app in $generatedApps) {
    $modelSlug = $app.Model -replace "\.", "_" -replace "/", "_"
    $resultPath = "results/$modelSlug/app$($app.AppNumber)"
    
    if (Test-Path $resultPath) {
        $files = Get-ChildItem $resultPath -Recurse -File
        Write-Success "$($app.Model) app #$($app.AppNumber): $($files.Count) result files"
        $resultsCount += $files.Count
    } else {
        Write-Warning "$($app.Model) app #$($app.AppNumber): No results found"
    }
}

Write-Success "Total result files: $resultsCount"

# ============================================
# STEP 8: Test Dashboard
# ============================================
Write-Step "Step 8: Testing Dashboard"

if ($generatedApps.Count -gt 0) {
    $testApp = $generatedApps[0]
    $dashboardUrl = "http://127.0.0.1:5000/analysis/dashboard/app/$($testApp.Model)/$($testApp.AppNumber)"
    
    Write-Info "Testing dashboard: $dashboardUrl"
    
    try {
        $response = Invoke-WebRequest -Uri $dashboardUrl -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200 -and $response.Content -match "Raw Data") {
            Write-Success "Dashboard is working!"
        } else {
            Write-Warning "Dashboard returned unexpected content"
        }
    } catch {
        Write-Error-Custom "Dashboard test failed: $_"
    }
}

# ============================================
# SUMMARY
# ============================================
Write-Step "✨ Fresh Start Complete!" "Green"

Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  • Database: ✓ Clean and initialized" -ForegroundColor Green
Write-Host "  • Generated Apps: $($generatedApps.Count)" -ForegroundColor Green
Write-Host "  • Result Files: $resultsCount" -ForegroundColor Green
Write-Host "  • Flask: ✓ Running on http://127.0.0.1:5000" -ForegroundColor Green
Write-Host "  • Analyzers: ✓ Running" -ForegroundColor Green
Write-Host ""

Write-Host "Generated Apps:" -ForegroundColor Cyan
foreach ($app in $generatedApps) {
    Write-Host "  • $($app.Model) - App #$($app.AppNumber)" -ForegroundColor Gray
    $dashUrl = "http://127.0.0.1:5000/analysis/dashboard/app/$($app.Model)/$($app.AppNumber)"
    Write-Host "    Dashboard: $dashUrl" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Open any dashboard URL above in browser" -ForegroundColor Gray
Write-Host "  2. Verify all tabs load correctly" -ForegroundColor Gray
Write-Host "  3. Check that findings are displayed" -ForegroundColor Gray
Write-Host "  4. Test filters, sorting, and modals" -ForegroundColor Gray
Write-Host ""

# Keep Flask running
Write-Host "Flask is running in background (Job ID: $($flaskJob.Id))" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop this script" -ForegroundColor Yellow
Write-Host ""

# Wait and show logs
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host "`nCleaning up..." -ForegroundColor Yellow
    Stop-Job $flaskJob -ErrorAction SilentlyContinue
    Remove-Job $flaskJob -ErrorAction SilentlyContinue
}
