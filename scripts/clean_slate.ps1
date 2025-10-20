#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Fresh Start - Complete System Reset (Simplified)
.DESCRIPTION
    Clean slate approach:
    1. Stop services
    2. Wipe database
    3. Clean generated folder
    4. Initialize fresh database
    5. Manual generation of 3 apps
#>

$ErrorActionPreference = "Stop"

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  FRESH START - System Reset" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# Step 1: Stop all services
Write-Host "Step 1: Stopping services..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | 
    Where-Object {$_.MainModule.FileName -match "ThesisAppRework"} | 
    Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "  ✓ Services stopped`n" -ForegroundColor Green

Start-Sleep -Seconds 2

# Step 2: Clean database
Write-Host "Step 2: Cleaning database..." -ForegroundColor Yellow
$dbFiles = @(
    "src/data/app.db",
    "src/data/thesis_app.db",
    "src/data/app.db-shm",
    "src/data/app.db-wal"
)

foreach ($dbFile in $dbFiles) {
    if (Test-Path $dbFile) {
        Remove-Item $dbFile -Force
        Write-Host "  ✓ Removed $dbFile" -ForegroundColor Green
    }
}

# Step 3: Clean generated apps
Write-Host "`nStep 3: Cleaning generated apps..." -ForegroundColor Yellow
if (Test-Path "generated/apps") {
    Get-ChildItem "generated/apps" -Directory | ForEach-Object {
        Write-Host "  → Removing: $($_.Name)" -ForegroundColor Gray
        Remove-Item $_.FullName -Recurse -Force
    }
    Write-Host "  ✓ Generated apps cleaned" -ForegroundColor Green
}

# Clean metadata
if (Test-Path "generated/metadata") {
    Remove-Item "generated/metadata/*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  ✓ Metadata cleaned" -ForegroundColor Green
}

# Clean results
Write-Host "`nStep 4: Cleaning results..." -ForegroundColor Yellow
if (Test-Path "results") {
    $resultsToKeep = @("test", "batch")
    Get-ChildItem "results" -Directory | Where-Object {
        $_.Name -notin $resultsToKeep
    } | ForEach-Object {
        Write-Host "  → Removing results: $($_.Name)" -ForegroundColor Gray
        Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  ✓ Results cleaned" -ForegroundColor Green
}

# Step 5: Initialize database
Write-Host "`nStep 5: Initializing fresh database..." -ForegroundColor Yellow
Push-Location src
$initOutput = & python init_db.py 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Database initialized" -ForegroundColor Green
} else {
    Write-Host "  ✗ Database initialization failed" -ForegroundColor Red
    Write-Host $initOutput
    Pop-Location
    exit 1
}
Pop-Location

# Step 6: Summary
Write-Host "`n============================================" -ForegroundColor Green
Write-Host "  ✨ Clean Slate Ready!" -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Green

Write-Host "What was cleaned:" -ForegroundColor Cyan
Write-Host "  ✓ Database wiped and reinitialized" -ForegroundColor Green
Write-Host "  ✓ Generated apps removed" -ForegroundColor Green
Write-Host "  ✓ Metadata cleaned" -ForegroundColor Green
Write-Host "  ✓ Old results removed" -ForegroundColor Green
Write-Host ""

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Start Flask: " -ForegroundColor Gray -NoNewline
Write-Host "cd src && python main.py" -ForegroundColor White
Write-Host "  2. Use Sample Generator UI to create 3 apps" -ForegroundColor Gray
Write-Host "  3. Run analysis on each app" -ForegroundColor Gray
Write-Host "  4. Test dashboard with real data" -ForegroundColor Gray
Write-Host ""

Write-Host "Sample Generation URLs:" -ForegroundColor Cyan
Write-Host "  • Generator: http://127.0.0.1:5000/sample-generator/" -ForegroundColor White
Write-Host "  • Applications: http://127.0.0.1:5000/applications" -ForegroundColor White
Write-Host "  • Analysis Hub: http://127.0.0.1:5000/analysis/" -ForegroundColor White
Write-Host ""

Write-Host "Recommended models to test:" -ForegroundColor Cyan
Write-Host "  1. openai/gpt-4o-mini (fast, reliable)" -ForegroundColor Gray
Write-Host "  2. anthropic/claude-3-5-sonnet-20241022 (best quality)" -ForegroundColor Gray
Write-Host "  3. google/gemini-2.0-flash-exp (free, fast)" -ForegroundColor Gray
Write-Host ""

Write-Host "✅ System is ready for fresh start!" -ForegroundColor Green
Write-Host ""
