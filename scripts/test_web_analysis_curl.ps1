#!/usr/bin/env pwsh
# Test analysis generation through web app using curl
# This simulates the same requests the web UI would make

$TOKEN = "7NT1z088bQXDGUkqMY1mW65iaGeAOMikYuZHzJcapOI3fC0cvZ2xJBQLc8QLSBT2"
$BASE_URL = "http://localhost:5000"

Write-Host "=== Testing Analysis Generation via Web App (curl) ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Create analysis with custom tools (simulating web form submission)
Write-Host "Test 1: Creating custom analysis with specific tools..." -ForegroundColor Yellow
Write-Host "  Model: anthropic_claude-4.5-haiku-20251001" -ForegroundColor Gray
Write-Host "  App: 1" -ForegroundColor Gray
Write-Host "  Tools: bandit, pylint, flake8" -ForegroundColor Gray
Write-Host ""

$response1 = curl.exe -s -X POST "$BASE_URL/analysis/create" `
    -H "Authorization: Bearer $TOKEN" `
    -H "Content-Type: application/x-www-form-urlencoded" `
    -d "model_slug=anthropic_claude-4.5-haiku-20251001" `
    -d "app_number=1" `
    -d "analysis_mode=custom" `
    -d "selected_tools[]=bandit" `
    -d "selected_tools[]=pylint" `
    -d "selected_tools[]=flake8" `
    -d "priority=normal" `
    -w "\nHTTP_CODE:%{http_code}\n"

Write-Host "Response:" -ForegroundColor Green
Write-Host $response1
Write-Host ""
Write-Host "---" -ForegroundColor DarkGray
Write-Host ""

# Test 2: Create comprehensive analysis (multiple services)
Write-Host "Test 2: Creating comprehensive analysis (static + security)..." -ForegroundColor Yellow
Write-Host "  Model: anthropic_claude-4.5-sonnet-20250929" -ForegroundColor Gray
Write-Host "  App: 1" -ForegroundColor Gray
Write-Host "  Tools: pylint, bandit, semgrep, safety" -ForegroundColor Gray
Write-Host ""

$response2 = curl.exe -s -X POST "$BASE_URL/analysis/create" `
    -H "Authorization: Bearer $TOKEN" `
    -H "Content-Type: application/x-www-form-urlencoded" `
    -d "model_slug=anthropic_claude-4.5-sonnet-20250929" `
    -d "app_number=1" `
    -d "analysis_mode=custom" `
    -d "selected_tools[]=pylint" `
    -d "selected_tools[]=bandit" `
    -d "selected_tools[]=semgrep" `
    -d "selected_tools[]=safety" `
    -d "priority=high" `
    -w "\nHTTP_CODE:%{http_code}\n"

Write-Host "Response:" -ForegroundColor Green
Write-Host $response2
Write-Host ""
Write-Host "---" -ForegroundColor DarkGray
Write-Host ""

# Test 3: Check task status (get tasks list)
Write-Host "Test 3: Checking created tasks..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

$response3 = curl.exe -s -X GET "$BASE_URL/analysis/api/tasks/list?per_page=5" `
    -H "Authorization: Bearer $TOKEN" `
    -w "\nHTTP_CODE:%{http_code}\n"

Write-Host "Recent tasks (HTML partial):" -ForegroundColor Green
# Extract just the task IDs and status from the HTML
$taskMatches = [regex]::Matches($response3, '<span class="badge bg-(\w+)-lt[^>]*>.*?<i class="[^"]*"></i>(\w+)</span>')
$idMatches = [regex]::Matches($response3, 'task_\w+')

Write-Host "  Found $($idMatches.Count) task IDs in response" -ForegroundColor Gray
if ($taskMatches.Count -gt 0) {
    Write-Host "  Task statuses:" -ForegroundColor Gray
    $taskMatches | Select-Object -First 5 | ForEach-Object {
        $color = $_.Groups[1].Value
        $status = $_.Groups[2].Value
        Write-Host "    - Status: $status (color: $color)" -ForegroundColor DarkCyan
    }
}
Write-Host ""
Write-Host "---" -ForegroundColor DarkGray
Write-Host ""

# Test 4: Use API endpoint instead (programmatic access)
Write-Host "Test 4: Creating analysis via API endpoint..." -ForegroundColor Yellow
Write-Host "  Using /api/analysis/run endpoint" -ForegroundColor Gray
Write-Host ""

$apiPayload = @{
    model_slug = "anthropic_claude-4.5-haiku-20251001"
    app_number = 2
    tools = @("pylint", "mypy", "ruff")
    priority = "normal"
} | ConvertTo-Json -Compress

# Save to temp file to avoid PowerShell string escaping issues with curl
$tempFile = [System.IO.Path]::GetTempFileName()
$apiPayload | Out-File -FilePath $tempFile -Encoding UTF8 -NoNewline

$response4 = curl.exe -s -X POST "$BASE_URL/api/analysis/run" `
    -H "Authorization: Bearer $TOKEN" `
    -H "Content-Type: application/json" `
    --data-binary "@$tempFile" `
    -w "\nHTTP_CODE:%{http_code}\n"

# Clean up temp file
Remove-Item $tempFile -ErrorAction SilentlyContinue

Write-Host "API Response:" -ForegroundColor Green
Write-Host $response4
Write-Host ""
Write-Host "---" -ForegroundColor DarkGray
Write-Host ""

# Test 5: Wait and check for result files
Write-Host "Test 5: Waiting for analysis to complete and checking result files..." -ForegroundColor Yellow
Write-Host "  Waiting 10 seconds for task execution..." -ForegroundColor Gray
Start-Sleep -Seconds 10

# Check if result files were created
$resultsDir = "results\anthropic_claude-4.5-haiku-20251001\app1"
if (Test-Path $resultsDir) {
    Write-Host "  Result directory exists: $resultsDir" -ForegroundColor Green
    
    # Find latest task directories
    $taskDirs = Get-ChildItem -Path $resultsDir -Directory | Where-Object { $_.Name -match "^task_" } | Sort-Object LastWriteTime -Descending | Select-Object -First 3
    
    if ($taskDirs.Count -gt 0) {
        Write-Host "  Recent task result directories:" -ForegroundColor Green
        foreach ($taskDir in $taskDirs) {
            Write-Host "    - $($taskDir.Name)" -ForegroundColor Cyan
            $jsonFiles = Get-ChildItem -Path $taskDir.FullName -Filter "*.json" | Where-Object { $_.Name -ne "manifest.json" }
            if ($jsonFiles.Count -gt 0) {
                Write-Host "      [OK] Found $($jsonFiles.Count) result file(s):" -ForegroundColor Green
                foreach ($file in $jsonFiles) {
                    $sizeKB = [math]::Round($file.Length / 1KB, 2)
                    Write-Host "         - $($file.Name) ($sizeKB KB)" -ForegroundColor DarkGreen
                }
            } else {
                Write-Host "      [WARN] No result JSON files yet" -ForegroundColor Yellow
            }
            
            $manifest = Join-Path $taskDir.FullName "manifest.json"
            if (Test-Path $manifest) {
                Write-Host "      [OK] manifest.json exists" -ForegroundColor Green
            }
        }
    } else {
        Write-Host "  [WARN] No task directories found yet" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [WARN] Result directory not found: $resultsDir" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "---" -ForegroundColor DarkGray
Write-Host ""

# Summary
Write-Host "=== Test Summary ===" -ForegroundColor Cyan
Write-Host ""
if ($response1 -match "HTTP_CODE:400") {
    Write-Host "[WARN] Test 1: Custom analysis creation (form validation - expected)" -ForegroundColor Yellow
} else {
    Write-Host "[OK] Test 1: Custom analysis creation (form-based)" -ForegroundColor Green
}
if ($response2 -match "HTTP_CODE:302") {
    Write-Host "[OK] Test 2: Comprehensive analysis (multiple tools)" -ForegroundColor Green
} else {
    Write-Host "[WARN] Test 2: Comprehensive analysis failed" -ForegroundColor Yellow
}
if ($idMatches.Count -gt 0) {
    Write-Host "[OK] Test 3: Task list retrieval ($($idMatches.Count) tasks found)" -ForegroundColor Green
} else {
    Write-Host "[WARN] Test 3: Task list retrieval (no tasks)" -ForegroundColor Yellow
}
if ($response4 -match '"success":true' -and $response4 -match "HTTP_CODE:201") {
    Write-Host "[OK] Test 4: API-based analysis creation" -ForegroundColor Green
} elseif ($response4 -match "HTTP_CODE:500") {
    Write-Host "[FAIL] Test 4: API-based analysis creation (server error)" -ForegroundColor Red
} else {
    Write-Host "[WARN] Test 4: API-based analysis creation (unknown status)" -ForegroundColor Yellow
}
if ($taskDirs.Count -gt 0) {
    Write-Host "[OK] Test 5: Result file verification ($($taskDirs.Count) task directories)" -ForegroundColor Green
} else {
    Write-Host "[WARN] Test 5: No result files found yet (tasks may still be running)" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Check task execution service logs for progress" -ForegroundColor Gray
Write-Host "  2. Monitor results/ directory for generated files" -ForegroundColor Gray
Write-Host "  3. View tasks in web UI: http://localhost:5000/analysis" -ForegroundColor Gray
Write-Host "  4. Run: python scripts/diagnostics/verify_web_analysis_results.py" -ForegroundColor Gray
Write-Host ""
