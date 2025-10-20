#!/usr/bin/env pwsh
# Dashboard Fix Verification Script
# Tests both dashboard routes and confirms 7-tab layout

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Dashboard Fix Verification" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Test URLs
$taskDetailUrl = "http://127.0.0.1:5000/analysis/tasks/task_72d52d60c798"
$dashboardUrl = "http://127.0.0.1:5000/analysis/dashboard/app/anthropic_claude-4.5-haiku-20251001/2"

# Expected tabs
$expectedTabs = @(
    'Overview',
    'Security',
    'Performance',
    'Code Quality',
    'AI Requirements',
    'Tools',
    'Raw Data'
)

function Test-Route {
    param(
        [string]$Url,
        [string]$Name
    )
    
    Write-Host "Testing: $Name" -ForegroundColor Yellow
    Write-Host "  URL: $Url" -ForegroundColor Gray
    
    try {
        $tempFile = [System.IO.Path]::GetTempFileName()
        curl -s $Url -o $tempFile 2>&1 | Out-Null
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  ✗ Failed to load" -ForegroundColor Red
            return $false
        }
        
        $content = Get-Content $tempFile -Raw
        Remove-Item $tempFile -ErrorAction SilentlyContinue
        
        # Check for error page
        if ($content -match "Internal Server Error" -or $content -match "500") {
            Write-Host "  ✗ 500 Internal Server Error" -ForegroundColor Red
            return $false
        }
        
        if ($content -match "404" -or $content -match "Not Found") {
            Write-Host "  ✗ 404 Not Found" -ForegroundColor Red
            return $false
        }
        
        # Check for tabs
        $missingTabs = @()
        $foundTabs = @()
        
        foreach ($tab in $expectedTabs) {
            if ($content -match $tab) {
                $foundTabs += $tab
            } else {
                $missingTabs += $tab
            }
        }
        
        Write-Host "  ✓ Page loaded successfully" -ForegroundColor Green
        Write-Host "  ✓ Found $($foundTabs.Count)/$($expectedTabs.Count) tabs" -ForegroundColor Green
        
        foreach ($tab in $foundTabs) {
            Write-Host "    • $tab" -ForegroundColor Green
        }
        
        if ($missingTabs.Count -gt 0) {
            Write-Host "  ✗ Missing tabs:" -ForegroundColor Red
            foreach ($tab in $missingTabs) {
                Write-Host "    • $tab" -ForegroundColor Red
            }
            return $false
        }
        
        return $true
        
    } catch {
        Write-Host "  ✗ Error: $_" -ForegroundColor Red
        return $false
    }
}

# Run tests
Write-Host ""
$taskDetailResult = Test-Route -Url $taskDetailUrl -Name "Task Detail Page"
Write-Host ""
$dashboardResult = Test-Route -Url $dashboardUrl -Name "Dashboard View"
Write-Host ""

# Summary
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Results Summary" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if ($taskDetailResult) {
    Write-Host "✓ Task Detail Page: WORKING" -ForegroundColor Green
} else {
    Write-Host "✗ Task Detail Page: FAILED" -ForegroundColor Red
}

if ($dashboardResult) {
    Write-Host "✓ Dashboard View: WORKING" -ForegroundColor Green
} else {
    Write-Host "✗ Dashboard View: FAILED" -ForegroundColor Red
}

Write-Host ""

if ($taskDetailResult -and $dashboardResult) {
    Write-Host "🎉 ALL TESTS PASSED!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Both routes are serving the new 7-tab layout correctly." -ForegroundColor Green
    exit 0
} else {
    Write-Host "⚠ SOME TESTS FAILED" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please review the errors above." -ForegroundColor Yellow
    exit 1
}
