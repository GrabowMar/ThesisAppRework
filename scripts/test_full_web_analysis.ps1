# Full Web Analysis Test Script
# Tests analysis creation and monitors execution across multiple models

param(
    [string]$BaseUrl = "http://localhost:5000",
    [string]$Token = "7NT1z088bQXDGUkqMY1mW65iaGeAOMikYuZHzJcapOI3fC0cvZ2xJBQLc8QLSBT2"
)

Write-Host "=== Full Web Analysis Test ===" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Gray
Write-Host "Starting at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""

# Test configurations
$testConfigs = @(
    @{
        Model = "anthropic_claude-4.5-sonnet-20250929"
        App = 1
        Tools = @("bandit", "safety")
        Name = "Security Analysis - Sonnet App1"
    },
    @{
        Model = "anthropic_claude-4.5-sonnet-20250929"
        App = 2
        Tools = @("pylint", "eslint")
        Name = "Code Quality - Sonnet App2"
    },
    @{
        Model = "anthropic_claude-4.5-haiku-20251001"
        App = 1
        Tools = @("mypy", "ruff")
        Name = "Type Checking - Haiku App1"
    }
)

Write-Host "Test Plan:" -ForegroundColor Yellow
Write-Host "  - $($testConfigs.Count) analysis tasks to create" -ForegroundColor Gray
Write-Host "  - Models: $(($testConfigs | ForEach-Object { $_.Model }) -join ', ')" -ForegroundColor Gray
Write-Host ""

# Function to create analysis via API
function New-Analysis {
    param($Config)
    
    Write-Host "Creating analysis: $($Config.Name)" -ForegroundColor Yellow
    Write-Host "  Model: $($Config.Model)" -ForegroundColor Gray
    Write-Host "  App: $($Config.App)" -ForegroundColor Gray
    Write-Host "  Tools: $($Config.Tools -join ', ')" -ForegroundColor Gray
    
    $payload = @{
        model_slug = $Config.Model
        app_number = $Config.App
        tools = $Config.Tools
        priority = "normal"
    } | ConvertTo-Json -Compress
    
    $tempFile = [System.IO.Path]::GetTempFileName()
    $payload | Out-File -FilePath $tempFile -Encoding UTF8 -NoNewline
    
    try {
        $response = curl.exe -s -X POST "$BaseUrl/api/analysis/run" `
            -H "Authorization: Bearer $Token" `
            -H "Content-Type: application/json" `
            --data-binary "@$tempFile" `
            -w "\nHTTP_CODE:%{http_code}\n"
        
        # Extract task ID with better error handling
        $taskId = $null
        if ($response -match '"task_id":"([^"]+)"') {
            $taskId = $matches[1]
        }
        
        if ($response -match '"success"\s*:\s*true' -and $taskId) {
            Write-Host "  [OK] Task created: $taskId" -ForegroundColor Green
            return $taskId
        } else {
            Write-Host "  [FAIL] Failed to create task" -ForegroundColor Red
            if ($response -match '"message":"([^"]+)"') {
                Write-Host "  Error: $($matches[1])" -ForegroundColor Red
            }
            if ($response -match 'HTTP_CODE:(\d+)') {
                Write-Host "  HTTP Status: $($matches[1])" -ForegroundColor DarkGray
            }
            return $null
        }
    } finally {
        Remove-Item $tempFile -ErrorAction SilentlyContinue
    }
    Write-Host ""
}

# Function to check task status
function Get-TaskStatus {
    param([string]$TaskId)
    
    try {
        $response = curl.exe -s -X GET "$BaseUrl/analysis/api/tasks/$TaskId/status" `
            -H "Authorization: Bearer $Token" 2>&1
        
        if ($response -match '"status":"([^"]+)"') {
            return $matches[1]
        }
        return "unknown"
    } catch {
        return "error"
    }
}

# Function to check result files
function Test-ResultFiles {
    param($Model, $App)
    
    $resultsPath = "results\$Model\app$App"
    if (-not (Test-Path $resultsPath)) {
        return @{ Exists = $false; Count = 0 }
    }
    
    $taskDirs = Get-ChildItem -Path $resultsPath -Directory -Filter "task_*" | 
                Sort-Object LastWriteTime -Descending
    
    $recentTasks = @()
    foreach ($dir in ($taskDirs | Select-Object -First 5)) {
        $jsonFiles = Get-ChildItem -Path $dir.FullName -Filter "*.json" | 
                     Where-Object { $_.Name -notmatch "manifest" }
        
        if ($jsonFiles) {
            $recentTasks += @{
                TaskDir = $dir.Name
                Files = $jsonFiles.Count
                Size = ($jsonFiles | Measure-Object -Property Length -Sum).Sum
                Time = $dir.LastWriteTime
            }
        }
    }
    
    return @{
        Exists = $true
        Count = $recentTasks.Count
        Tasks = $recentTasks
    }
}

# Create all analysis tasks
Write-Host "Phase 1: Creating Analysis Tasks" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

$createdTasks = @()
foreach ($config in $testConfigs) {
    $taskId = New-Analysis -Config $config
    if ($taskId) {
        $createdTasks += @{
            TaskId = $taskId
            Config = $config
            StartTime = Get-Date
        }
    }
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "Created $($createdTasks.Count) of $($testConfigs.Count) tasks" -ForegroundColor $(if ($createdTasks.Count -eq $testConfigs.Count) { "Green" } else { "Yellow" })
Write-Host ""

if ($createdTasks.Count -eq 0) {
    Write-Host "[ERROR] No tasks were created. Exiting." -ForegroundColor Red
    exit 1
}

# Monitor task execution
Write-Host "Phase 2: Monitoring Task Execution" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Monitoring tasks for up to 10 minutes..." -ForegroundColor Gray
Write-Host "Tasks should take 1-5 minutes to complete depending on tools selected." -ForegroundColor Gray
Write-Host ""

$maxWaitMinutes = 10
$checkInterval = 15
$startTime = Get-Date
$allCompleted = $false

while (-not $allCompleted -and ((Get-Date) - $startTime).TotalMinutes -lt $maxWaitMinutes) {
    $elapsed = [math]::Round(((Get-Date) - $startTime).TotalMinutes, 1)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Checking task status (elapsed: $elapsed min)..." -ForegroundColor Cyan
    
    $statusCounts = @{
        pending = 0
        running = 0
        completed = 0
        failed = 0
        cancelled = 0
        unknown = 0
    }
    
    foreach ($task in $createdTasks) {
        $status = Get-TaskStatus -TaskId $task.TaskId
        $task.Status = $status
        $statusCounts[$status.ToLower()]++
        
        $statusColor = switch ($status.ToLower()) {
            "pending" { "Yellow" }
            "running" { "Cyan" }
            "completed" { "Green" }
            "failed" { "Red" }
            "cancelled" { "DarkGray" }
            default { "Gray" }
        }
        
        $duration = [math]::Round(((Get-Date) - $task.StartTime).TotalMinutes, 1)
        Write-Host "  $($task.TaskId): " -NoNewline -ForegroundColor Gray
        Write-Host "$($status.ToUpper())" -NoNewline -ForegroundColor $statusColor
        Write-Host " ($duration min) - $($task.Config.Name)" -ForegroundColor DarkGray
    }
    
    Write-Host ""
    Write-Host "  Summary: " -NoNewline -ForegroundColor Gray
    Write-Host "Pending: $($statusCounts.pending) " -NoNewline -ForegroundColor Yellow
    Write-Host "Running: $($statusCounts.running) " -NoNewline -ForegroundColor Cyan
    Write-Host "Completed: $($statusCounts.completed) " -NoNewline -ForegroundColor Green
    Write-Host "Failed: $($statusCounts.failed)" -ForegroundColor $(if ($statusCounts.failed -gt 0) { "Red" } else { "Gray" })
    Write-Host ""
    
    # Check if all tasks are done (completed, failed, or cancelled)
    $activeTasks = $statusCounts.pending + $statusCounts.running
    if ($activeTasks -eq 0) {
        $allCompleted = $true
        Write-Host "[OK] All tasks finished!" -ForegroundColor Green
        Write-Host ""
        break
    }
    
    Write-Host "Waiting $checkInterval seconds before next check..." -ForegroundColor DarkGray
    Write-Host ""
    Start-Sleep -Seconds $checkInterval
}

if (-not $allCompleted) {
    Write-Host "[WARN] Timeout reached. Some tasks may still be running." -ForegroundColor Yellow
    Write-Host ""
}

# Check result files
Write-Host "Phase 3: Verifying Result Files" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

foreach ($task in $createdTasks) {
    Write-Host "Checking results for: $($task.Config.Name)" -ForegroundColor Yellow
    Write-Host "  Model: $($task.Config.Model), App: $($task.Config.App)" -ForegroundColor Gray
    
    $results = Test-ResultFiles -Model $task.Config.Model -App $task.Config.App
    
    if ($results.Exists -and $results.Count -gt 0) {
        Write-Host "  [OK] Found $($results.Count) recent result(s)" -ForegroundColor Green
        
        foreach ($taskResult in $results.Tasks) {
            $sizeKB = [math]::Round($taskResult.Size / 1KB, 2)
            $age = [math]::Round(((Get-Date) - $taskResult.Time).TotalMinutes, 1)
            Write-Host "    - $($taskResult.TaskDir): $($taskResult.Files) file(s), $sizeKB KB, $age min ago" -ForegroundColor DarkGreen
        }
    } else {
        Write-Host "  [WARN] No result files found yet" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Final summary
Write-Host "=== Final Summary ===" -ForegroundColor Cyan
Write-Host ""

$totalDuration = [math]::Round(((Get-Date) - $startTime).TotalMinutes, 1)
Write-Host "Total execution time: $totalDuration minutes" -ForegroundColor Gray
Write-Host ""

$completedCount = ($createdTasks | Where-Object { $_.Status -eq "completed" }).Count
$failedCount = ($createdTasks | Where-Object { $_.Status -eq "failed" }).Count
$pendingCount = ($createdTasks | Where-Object { $_.Status -in @("pending", "running") }).Count

Write-Host "Task Results:" -ForegroundColor Yellow
Write-Host "  [OK] Completed: $completedCount / $($createdTasks.Count)" -ForegroundColor $(if ($completedCount -eq $createdTasks.Count) { "Green" } else { "Yellow" })
if ($failedCount -gt 0) {
    Write-Host "  [FAIL] Failed: $failedCount" -ForegroundColor Red
}
if ($pendingCount -gt 0) {
    Write-Host "  [WARN] Still running: $pendingCount" -ForegroundColor Yellow
}
Write-Host ""

if ($completedCount -eq $createdTasks.Count) {
    Write-Host "[SUCCESS] All analysis tasks completed successfully!" -ForegroundColor Green
    exit 0
} elseif ($failedCount -gt 0) {
    Write-Host "[PARTIAL] Some tasks failed. Check logs for details." -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "[INCOMPLETE] Some tasks are still running. Check web UI for progress." -ForegroundColor Yellow
    exit 2
}
