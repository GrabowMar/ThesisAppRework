# Comprehensive Authentication Test Script
# Tests all routes to ensure they require authentication

Write-Host "=== AUTHENTICATION PROTECTION TEST ===" -ForegroundColor Cyan
Write-Host ""

$baseUrl = "http://localhost:5000"
$failures = @()
$successes = @()

function Test-Route {
    param(
        [string]$Path,
        [string]$Description,
        [int]$ExpectedStatus = 302  # Default: expect redirect
    )
    
    try {
        # Use curl.exe to avoid PowerShell's Invoke-WebRequest caching
        $output = & curl.exe -s -I "$baseUrl$Path" 2>&1 | Out-String
        if ($output -match "HTTP/[\d\.]+ (\d+)") {
            $status = [int]$matches[1]
        } else {
            $status = 0
        }
    } catch {
        $status = 0
    }
    
    if ($status -eq $ExpectedStatus -or ($ExpectedStatus -eq 302 -and $status -eq 401)) {
        Write-Host "[✓] $Description" -ForegroundColor Green
        Write-Host "    $Path -> $status" -ForegroundColor DarkGray
        $script:successes += $Path
    } else {
        Write-Host "[✗] $Description" -ForegroundColor Red
        Write-Host "    $Path -> Expected: $ExpectedStatus, Got: $status" -ForegroundColor Yellow
        $script:failures += "$Path (expected $ExpectedStatus, got $status)"
    }
}

Write-Host "Testing Protected Routes (should redirect or return 401)..." -ForegroundColor Yellow
Write-Host ""

# Main routes
Test-Route "/" "Root/Dashboard"
Test-Route "/about" "About page"
Test-Route "/models_overview" "Models overview"
Test-Route "/applications" "Applications index"
Test-Route "/system-status" "System status"
Test-Route "/test-platform" "Test platform"

# SPA routes
Test-Route "/spa/dashboard" "SPA Dashboard"
Test-Route "/spa/analysis" "SPA Analysis"
Test-Route "/spa/models" "SPA Models"
Test-Route "/spa/applications" "SPA Applications"

# Models routes
Test-Route "/models/" "Models index"
Test-Route "/models/filter" "Models filter"
Test-Route "/models/comparison" "Models comparison"

# Analysis routes
Test-Route "/analysis" "Analysis dashboard"
Test-Route "/analysis/task-detail/1" "Task detail"

# Stats routes
Test-Route "/stats/" "Stats index"
Test-Route "/stats/generation-data.json" "Stats data"

# Reports routes
Test-Route "/reports/" "Reports index"

# Docs routes
Test-Route "/docs/" "Docs index"

# Sample generator routes
Test-Route "/sample-generator/" "Sample generator"

# Dashboard routes
Test-Route "/analysis/dashboard/app/test/1" "Dashboard app detail"
Test-Route "/analysis/dashboard/model/test" "Dashboard model detail"
Test-Route "/analysis/dashboard/tools" "Dashboard tools"
Test-Route "/analysis/dashboard/compare" "Dashboard compare"

# WebSocket routes (should return 401 JSON for APIs)
Test-Route "/ws/analysis" "WebSocket analysis" 401
Test-Route "/socket.io/" "Socket.IO fallback" 401

# API routes (should return 401)
Test-Route "/api/models/list" "API Models list" 401
Test-Route "/api/applications/list" "API Applications list" 401
Test-Route "/api/analysis/tasks" "API Analysis tasks" 401
Test-Route "/api/dashboard/stats" "API Dashboard stats" 401
Test-Route "/api/websocket/status" "API WebSocket status" 401
Test-Route "/api/gen/status" "API Gen status" 401
Test-Route "/api/tasks/status" "API Tasks status" 401

Write-Host ""
Write-Host "Testing Unprotected Routes (should be accessible)..." -ForegroundColor Yellow
Write-Host ""

# These should work without authentication
Test-Route "/auth/login" "Login page" 200
Test-Route "/health" "Health check" 200
Test-Route "/api/health" "API Health check" 200

Write-Host ""
Write-Host "=== TEST SUMMARY ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Passed: $($successes.Count)" -ForegroundColor Green
Write-Host "Failed: $($failures.Count)" -ForegroundColor $(if ($failures.Count -eq 0) { "Green" } else { "Red" })

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Failed routes:" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host "  - $failure" -ForegroundColor Yellow
    }
    exit 1
} else {
    Write-Host ""
    Write-Host "✓ ALL ROUTES ARE PROPERLY PROTECTED!" -ForegroundColor Green
    exit 0
}
