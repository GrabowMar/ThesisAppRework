# Test Unified Analysis with Celery
$token = "wbvrEHH0Mw8yTJfOZ8yGEkXMIG2Zj8d3D2SJk6QkbPQQjXeQlp1ShvH01Mg4WvtR"

Write-Host "=== Testing Unified Analysis (Celery-based) ===" -ForegroundColor Cyan

# Create a comprehensive analysis task (this should trigger Celery)
$body = @{
    model_slug = "google_gemini-2.5-pro"
    app_number = 3
    analysis_type = "comprehensive"  # This triggers unified/parallel execution
} | ConvertTo-Json

Write-Host "`nSubmitting comprehensive analysis request..." -ForegroundColor Yellow
$response = Invoke-RestMethod -Method POST -Uri "http://localhost:5000/api/analysis/run" `
    -Headers @{"Authorization"="Bearer $token"; "Content-Type"="application/json"} `
    -Body $body

$taskId = $response.task_id
Write-Host "Task created: $taskId" -ForegroundColor Green
Write-Host "Status: $($response.data.status)" -ForegroundColor Green

# Wait a bit for task to start
Write-Host "`nWaiting 3 seconds for task to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Check Celery worker log
Write-Host "`nChecking Celery worker activity..." -ForegroundColor Yellow
$celeryLog = Get-Content "logs\celery_worker.log" -Tail 10
if ($celeryLog -match $taskId) {
    Write-Host "✓ Celery received the task!" -ForegroundColor Green
} else {
    Write-Host "✗ Celery did not receive the task" -ForegroundColor Red
    Write-Host "`nRecent Celery log:" -ForegroundColor Yellow
    $celeryLog | ForEach-Object { Write-Host $_ }
}

# Check app log
Write-Host "`nChecking application log..." -ForegroundColor Yellow
$appLog = Get-Content "logs\app.log" | Select-String $taskId | Select-Object -Last 10
$appLog | ForEach-Object { Write-Host $_.Line }

Write-Host "`n=== Test Complete ===" -ForegroundColor Cyan
