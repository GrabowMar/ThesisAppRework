# Full Web Analysis Test - Clean Version
$BaseUrl = "http://localhost:5000"
$Token = "7NT1z088bQXDGUkqMY1mW65iaGeAOMikYuZHzJcapOI3fC0cvZ2xJBQLc8QLSBT2"

Write-Host "=== Full Web Analysis Test ===" -ForegroundColor Cyan
Write-Host "Starting: $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Gray
Write-Host ""

# Test configurations - using only models/apps that exist
$tests = @(
    @{ Model = "anthropic_claude-4.5-sonnet-20250929"; App = 1; Tools = @("bandit", "safety"); Name = "Security - Sonnet App1" },
    @{ Model = "anthropic_claude-4.5-sonnet-20250929"; App = 2; Tools = @("pylint", "eslint"); Name = "Quality - Sonnet App2" },
    @{ Model = "anthropic_claude-4.5-haiku-20251001"; App = 1; Tools = @("mypy", "ruff"); Name = "Types - Haiku App1" }
)

Write-Host "Creating $($tests.Count) analysis tasks..." -ForegroundColor Yellow
Write-Host ""

$tasks = @()

foreach ($test in $tests) {
    Write-Host "[$($test.Name)]" -ForegroundColor Cyan
    Write-Host "  Model: $($test.Model)" -ForegroundColor Gray
    Write-Host "  App: $($test.App), Tools: $($test.Tools -join ', ')" -ForegroundColor Gray
    
    $json = @{
        model_slug = $test.Model
        app_number = $test.App
        tools = $test.Tools
        priority = "normal"
    } | ConvertTo-Json -Compress
    
    $tmpFile = [System.IO.Path]::GetTempFileName()
    try {
        $json | Out-File -FilePath $tmpFile -Encoding UTF8 -NoNewline
        
        $result = curl.exe -s -X POST "$BaseUrl/api/analysis/run" `
            -H "Authorization: Bearer $Token" `
            -H "Content-Type: application/json" `
            --data-binary "@$tmpFile"
        
        if ($result -match '"task_id"\s*:\s*"([^"]+)"') {
            $taskId = $matches[1]
            Write-Host "  [OK] Created task: $taskId" -ForegroundColor Green
            $tasks += @{ Id = $taskId; Name = $test.Name; Model = $test.Model; App = $test.App; Start = Get-Date }
        } else {
            Write-Host "  [FAIL] Creation failed" -ForegroundColor Red
            if ($result -match '"message"\s*:\s*"([^"]+)"') {
                Write-Host "  Error: $($matches[1])" -ForegroundColor DarkRed
            }
        }
    } finally {
        Remove-Item $tmpFile -ErrorAction SilentlyContinue
    }
    Write-Host ""
    Start-Sleep -Seconds 2
}

if ($tasks.Count -eq 0) {
    Write-Host "[ERROR] No tasks created!" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Created $($tasks.Count)/$($tests.Count) tasks" -ForegroundColor Green
Write-Host ""
Write-Host "Monitoring execution (checking every 20 seconds)..." -ForegroundColor Yellow
Write-Host ""

$maxMinutes = 10
$checkSec = 20
$start = Get-Date

while (((Get-Date) - $start).TotalMinutes -lt $maxMinutes) {
    $elapsed = [math]::Round(((Get-Date) - $start).TotalMinutes, 1)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Check at $elapsed min" -ForegroundColor Cyan
    
    $statuses = @{ pending=0; running=0; completed=0; failed=0 }
    
    foreach ($task in $tasks) {
        try {
            $statusResp = curl.exe -s "$BaseUrl/analysis/api/tasks/$($task.Id)/status" `
                -H "Authorization: Bearer $Token" 2>$null
            
            $status = "unknown"
            if ($statusResp -match '"status"\s*:\s*"([^"]+)"') {
                $status = $matches[1].ToLower()
            }
            
            $task.Status = $status
            $statuses[$status]++
            
            $color = switch ($status) {
                "pending" { "Yellow" }
                "running" { "Cyan" }
                "completed" { "Green" }
                "failed" { "Red" }
                default { "Gray" }
            }
            
            $dur = [math]::Round(((Get-Date) - $task.Start).TotalMinutes, 1)
            Write-Host "  $($task.Id): " -NoNewline
            Write-Host $status.ToUpper().PadRight(10) -NoNewline -ForegroundColor $color
            Write-Host " ($dur min) $($task.Name)" -ForegroundColor DarkGray
        } catch {
            Write-Host "  $($task.Id): ERROR checking status" -ForegroundColor Red
        }
    }
    
    Write-Host "  Summary: " -NoNewline
    Write-Host "Pending=$($statuses.pending) " -NoNewline -ForegroundColor Yellow
    Write-Host "Running=$($statuses.running) " -NoNewline -ForegroundColor Cyan
    Write-Host "Done=$($statuses.completed) " -NoNewline -ForegroundColor Green
    Write-Host "Failed=$($statuses.failed)" -ForegroundColor $(if ($statuses.failed -gt 0) { "Red" } else { "Gray" })
    Write-Host ""
    
    $active = $statuses.pending + $statuses.running
    if ($active -eq 0) {
        Write-Host "[OK] All tasks finished!" -ForegroundColor Green
        break
    }
    
    Write-Host "Waiting $checkSec seconds..." -ForegroundColor DarkGray
    Write-Host ""
    Start-Sleep -Seconds $checkSec
}

Write-Host ""
Write-Host "Checking result files..." -ForegroundColor Yellow
Write-Host ""

foreach ($task in $tasks) {
    $resDir = "results\$($task.Model)\app$($task.App)"
    Write-Host "[$($task.Name)]" -ForegroundColor Cyan
    
    if (Test-Path $resDir) {
        $taskDirs = Get-ChildItem -Path $resDir -Directory -Filter "task_*" |
                    Sort-Object LastWriteTime -Descending |
                    Select-Object -First 3
        
        if ($taskDirs) {
            foreach ($dir in $taskDirs) {
                $files = Get-ChildItem -Path $dir.FullName -Filter "*.json" |
                         Where-Object { $_.Name -notmatch "manifest" }
                $age = [math]::Round(((Get-Date) - $dir.LastWriteTime).TotalMinutes, 1)
                if ($files) {
                    $sizeKB = [math]::Round(($files | Measure-Object -Property Length -Sum).Sum / 1KB, 2)
                    Write-Host "  [OK] $($dir.Name): $($files.Count) file(s), $sizeKB KB, $age min ago" -ForegroundColor Green
                }
            }
        } else {
            Write-Host "  [WARN] No result files yet" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  [WARN] Result directory not found" -ForegroundColor Yellow
    }
    Write-Host ""
}

$totalMin = [math]::Round(((Get-Date) - $start).TotalMinutes, 1)
$done = ($tasks | Where-Object { $_.Status -eq "completed" }).Count
$failed = ($tasks | Where-Object { $_.Status -eq "failed" }).Count

Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "Duration: $totalMin minutes" -ForegroundColor Gray
Write-Host "Completed: $done / $($tasks.Count)" -ForegroundColor $(if ($done -eq $tasks.Count) { "Green" } else { "Yellow" })
if ($failed -gt 0) { Write-Host "Failed: $failed" -ForegroundColor Red }
Write-Host ""

if ($done -eq $tasks.Count) {
    Write-Host "[SUCCESS] All tests passed!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[INCOMPLETE] Check web UI for details" -ForegroundColor Yellow
    exit 1
}
