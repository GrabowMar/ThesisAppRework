# Web App API Usage & Testing Guide

## Overview
This guide demonstrates how to interact with the ThesisApp web application via API endpoints using curl/PowerShell, simulating real web app usage programmatically.

## Prerequisites

### 1. Start Flask App
```powershell
python src/main.py
```
The app runs on `http://localhost:5000`

### 2. Get API Token
Option A - Via Web UI:
1. Login at http://localhost:5000/auth/login
2. Navigate to User Menu → API Access
3. Click "Generate Token"
4. Copy the 48-character token

Option B - Via Script:
```powershell
python scripts/generate_api_token.py
```

### 3. Set Token Variable
```powershell
$token = "YOUR_48_CHAR_TOKEN_HERE"
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}
```

---

## API Endpoint Tests

### 1. Verify Authentication ✅

**Purpose:** Confirm your API token is valid

```powershell
# PowerShell
$verify = Invoke-RestMethod `
    -Uri "http://localhost:5000/api/tokens/verify" `
    -Headers $headers `
    -Method GET

Write-Host "Token valid: $($verify.valid)"
Write-Host "User: $($verify.user.username)"
```

```bash
# Bash/curl
curl -X GET http://localhost:5000/api/tokens/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response:**
```json
{
  "valid": true,
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com"
  },
  "token": {
    "created_at": "2025-11-03T20:00:00",
    "expires_at": null
  }
}
```

---

### 2. List Available Models 📋

**Purpose:** Get all AI models that have generated apps

```powershell
# PowerShell
$models = Invoke-RestMethod `
    -Uri "http://localhost:5000/api/models" `
    -Headers $headers `
    -Method GET

Write-Host "Found $($models.Count) models:"
$models | ForEach-Object {
    Write-Host "  - $($_.provider)/$($_.model_name)"
    Write-Host "    Apps: $($_.generated_apps_count)"
}
```

```bash
# Bash/curl
curl -X GET http://localhost:5000/api/models \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq '.[] | {provider, model_name, apps: .generated_apps_count}'
```

**Expected Response:**
```json
[
  {
    "id": 1,
    "provider": "anthropic",
    "model_name": "claude-4.5-haiku-20251001",
    "slug": "anthropic_claude-4.5-haiku-20251001",
    "generated_apps_count": 1,
    "is_available": true
  }
]
```

---

### 3. Get Model's Applications 📱

**Purpose:** List all generated apps for a specific model

```powershell
# PowerShell
$modelSlug = "anthropic_claude-4.5-haiku-20251001"
$apps = Invoke-RestMethod `
    -Uri "http://localhost:5000/api/models/$modelSlug/apps" `
    -Headers $headers `
    -Method GET

Write-Host "Model: $modelSlug"
Write-Host "Generated apps: $($apps.Count)"
$apps | ForEach-Object {
    Write-Host "  - App $($_.app_number) | Created: $($_.created_at)"
}
```

```bash
# Bash/curl
MODEL_SLUG="anthropic_claude-4.5-haiku-20251001"
curl -X GET "http://localhost:5000/api/models/$MODEL_SLUG/apps" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq
```

---

### 4. Create Security Analysis Task 🔒

**Purpose:** Start a security-focused analysis with specific tools

```powershell
# PowerShell
$body = @{
    model_slug = "anthropic_claude-4.5-haiku-20251001"
    app_number = 1
    analysis_type = "security"
    tools = @("bandit", "safety", "semgrep")
    priority = "normal"
} | ConvertTo-Json

$result = Invoke-RestMethod `
    -Uri "http://localhost:5000/api/analysis/run" `
    -Headers $headers `
    -Method POST `
    -Body $body

Write-Host "✓ Task created: $($result.task_id)"
Write-Host "  Status: $($result.data.status)"
Write-Host "  Type: $($result.data.analysis_type)"
```

```bash
# Bash/curl
curl -X POST http://localhost:5000/api/analysis/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_slug": "anthropic_claude-4.5-haiku-20251001",
    "app_number": 1,
    "analysis_type": "security",
    "tools": ["bandit", "safety", "semgrep"],
    "priority": "normal"
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "task_id": "task_5c6e7dd1bab9",
  "message": "Analysis task created successfully",
  "data": {
    "task_id": "task_5c6e7dd1bab9",
    "model_slug": "anthropic_claude-4.5-haiku-20251001",
    "app_number": 1,
    "analysis_type": "custom:anthropic_claude-4.5-haiku-20251001:1",
    "status": "pending",
    "created_at": "2025-11-03T20:55:00",
    "tools_count": 3,
    "priority": "normal"
  }
}
```

---

### 5. Create Comprehensive Analysis ⚡

**Purpose:** Run all analysis types (security, static, performance, dynamic)

```powershell
# PowerShell
$body = @{
    model_slug = "anthropic_claude-4.5-sonnet-20250929"
    app_number = 1
    analysis_type = "comprehensive"
} | ConvertTo-Json

$result = Invoke-RestMethod `
    -Uri "http://localhost:5000/api/analysis/run" `
    -Headers $headers `
    -Method POST `
    -Body $body

Write-Host "✓ Comprehensive task created!"
Write-Host "  Task ID: $($result.task_id)"
Write-Host "  Model: $($result.data.model_slug)"
Write-Host "  App: $($result.data.app_number)"
Write-Host ""
Write-Host "This task will run all 4 analyzer services:"
Write-Host "  - Security analysis (Bandit, Safety, Semgrep)"
Write-Host "  - Static analysis (Pylint, ESLint, Ruff, etc.)"
Write-Host "  - Performance testing (Locust, ab, aiohttp)"
Write-Host "  - Dynamic analysis (ZAP, nmap, curl)"
Write-Host ""
Write-Host "Results will be saved to:"
Write-Host "  results/$($result.data.model_slug)/app$($result.data.app_number)/task_$($result.task_id)/"
```

```bash
# Bash/curl
curl -X POST http://localhost:5000/api/analysis/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_slug": "anthropic_claude-4.5-sonnet-20250929",
    "app_number": 1,
    "analysis_type": "comprehensive"
  }'
```

---

### 6. Monitor Task Progress 📊

**Purpose:** Check analysis task status and results

```powershell
# PowerShell
$taskId = "task_50a9c0d47c25"

# Check task summary
$summary = Invoke-RestMethod `
    -Uri "http://localhost:5000/analysis/api/tasks/$taskId/summary" `
    -Headers $headers `
    -Method GET

Write-Host "Task Status: $($summary.status)"
Write-Host "Services:"
$summary.services.PSObject.Properties | ForEach-Object {
    Write-Host "  - $($_.Name): $($_.Value.status)"
}
```

```bash
# Bash/curl
TASK_ID="task_50a9c0d47c25"
curl -X GET "http://localhost:5000/analysis/api/tasks/$TASK_ID/summary" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq '.status, .services'
```

---

### 7. Get Full Task Results 📄

**Purpose:** Retrieve complete analysis results for a task

```powershell
# PowerShell
$taskId = "task_50a9c0d47c25"

$results = Invoke-RestMethod `
    -Uri "http://localhost:5000/analysis/api/tasks/$taskId/results" `
    -Headers $headers `
    -Method GET

Write-Host "Task: $($results.metadata.model_slug) app$($results.metadata.app_number)"
Write-Host "Status: $($results.results.summary.status)"
Write-Host "Total Findings: $($results.results.summary.total_findings)"
Write-Host "Tools Executed: $($results.results.summary.tools_executed)"
Write-Host ""
Write-Host "Severity Breakdown:"
$results.results.summary.severity_breakdown.PSObject.Properties | ForEach-Object {
    Write-Host "  $($_.Name): $($_.Value)"
}
```

```bash
# Bash/curl
TASK_ID="task_50a9c0d47c25"
curl -X GET "http://localhost:5000/analysis/api/tasks/$TASK_ID/results" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq '.results.summary'
```

**Expected Response Structure:**
```json
{
  "metadata": {
    "model_slug": "anthropic_claude-4.5-sonnet-20250929",
    "app_number": 1,
    "analysis_type": "comprehensive",
    "timestamp": "2025-11-03T20:55:00+00:00"
  },
  "results": {
    "task": {...},
    "summary": {
      "total_findings": 53,
      "services_executed": 4,
      "tools_executed": 18,
      "severity_breakdown": {
        "high": 1,
        "medium": 45,
        "low": 7
      },
      "status": "completed"
    },
    "services": {...},
    "tools": {...},
    "findings": [...]
  }
}
```

---

### 8. Get Security-Specific Data 🔐

**Purpose:** Fetch only security analysis results

```powershell
# PowerShell
$taskId = "task_50a9c0d47c25"

$security = Invoke-RestMethod `
    -Uri "http://localhost:5000/analysis/api/tasks/$taskId/security" `
    -Headers $headers `
    -Method GET

Write-Host "Security Analysis:"
Write-Host "  Status: $($security.status)"
Write-Host "  Issues: $($security.issues)"
Write-Host "  Severity Breakdown:"
$security.severity_breakdown.PSObject.Properties | ForEach-Object {
    Write-Host "    $($_.Name): $($_.Value)"
}
```

```bash
# Bash/curl
TASK_ID="task_50a9c0d47c25"
curl -X GET "http://localhost:5000/analysis/api/tasks/$TASK_ID/security" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq
```

---

### 9. Get Performance Data ⚡

**Purpose:** Fetch only performance test results

```powershell
# PowerShell
$taskId = "task_50a9c0d47c25"

$performance = Invoke-RestMethod `
    -Uri "http://localhost:5000/analysis/api/tasks/$taskId/performance" `
    -Headers $headers `
    -Method GET

Write-Host "Performance Test:"
Write-Host "  Status: $($performance.status)"
Write-Host "  Requests/sec: $($performance.requests_per_second)"
Write-Host "  Avg Response (ms): $($performance.avg_response_ms)"
Write-Host "  Failed: $($performance.failed_percent)%"
```

```bash
# Bash/curl
TASK_ID="task_50a9c0d47c25"
curl -X GET "http://localhost:5000/analysis/api/tasks/$TASK_ID/performance" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq
```

---

### 10. Get Tool Execution Details 🔧

**Purpose:** See which tools ran and their individual results

```powershell
# PowerShell
$taskId = "task_50a9c0d47c25"

$tools = Invoke-RestMethod `
    -Uri "http://localhost:5000/analysis/api/tasks/$taskId/tools" `
    -Headers $headers `
    -Method GET

Write-Host "Tools Executed:"
$tools.tools.PSObject.Properties | ForEach-Object {
    $tool = $_.Value
    Write-Host "  - $($_.Name)"
    Write-Host "    Status: $($tool.status)"
    Write-Host "    Issues: $($tool.issues_found)"
}
```

```bash
# Bash/curl
TASK_ID="task_50a9c0d47c25"
curl -X GET "http://localhost:5000/analysis/api/tasks/$TASK_ID/tools" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq '.tools'
```

---

## Complete PowerShell Test Script

Save as `test_api.ps1`:

```powershell
# Configuration
$token = "YOUR_TOKEN_HERE"
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}
$baseUrl = "http://localhost:5000"

Write-Host "`n=== WEB APP API TEST SUITE ===`n" -ForegroundColor Green

# Test 1: Authentication
Write-Host "[1/6] Verifying API Token..." -ForegroundColor Cyan
$verify = Invoke-RestMethod -Uri "$baseUrl/api/tokens/verify" -Headers $headers -Method GET
Write-Host "   ✓ User: $($verify.user.username)`n" -ForegroundColor Green

# Test 2: List Models
Write-Host "[2/6] Fetching Models..." -ForegroundColor Cyan
$models = Invoke-RestMethod -Uri "$baseUrl/api/models" -Headers $headers -Method GET
Write-Host "   ✓ Found $($models.Count) models`n" -ForegroundColor Green

# Test 3: Get Apps for Model
Write-Host "[3/6] Getting Model Apps..." -ForegroundColor Cyan
$apps = Invoke-RestMethod -Uri "$baseUrl/api/models/anthropic_claude-4.5-haiku-20251001/apps" -Headers $headers -Method GET
Write-Host "   ✓ Found $($apps.Count) apps`n" -ForegroundColor Green

# Test 4: Create Security Analysis
Write-Host "[4/6] Creating Security Analysis..." -ForegroundColor Cyan
$body = @{
    model_slug = "anthropic_claude-4.5-haiku-20251001"
    app_number = 1
    analysis_type = "security"
    tools = @("bandit", "safety")
} | ConvertTo-Json
$result = Invoke-RestMethod -Uri "$baseUrl/api/analysis/run" -Headers $headers -Method POST -Body $body
Write-Host "   ✓ Task: $($result.task_id)`n" -ForegroundColor Green

# Test 5: Create Comprehensive Analysis
Write-Host "[5/6] Creating Comprehensive Analysis..." -ForegroundColor Cyan
$body = @{
    model_slug = "anthropic_claude-4.5-sonnet-20250929"
    app_number = 1
    analysis_type = "comprehensive"
} | ConvertTo-Json
$result = Invoke-RestMethod -Uri "$baseUrl/api/analysis/run" -Headers $headers -Method POST -Body $body
$taskId = $result.task_id
Write-Host "   ✓ Task: $taskId`n" -ForegroundColor Green

# Test 6: Monitor Task (wait and check)
Write-Host "[6/6] Monitoring Task Progress..." -ForegroundColor Cyan
Write-Host "   Waiting 15 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 15
try {
    $summary = Invoke-RestMethod -Uri "$baseUrl/analysis/api/tasks/$taskId/summary" -Headers $headers -Method GET
    Write-Host "   ✓ Status: $($summary.status)" -ForegroundColor Green
} catch {
    Write-Host "   ⚠ Task still initializing" -ForegroundColor Yellow
}

Write-Host "`n=== ALL TESTS COMPLETE ===`n" -ForegroundColor Green
```

---

## Result File Structure

After analysis completes, results are saved to:
```
results/{model_slug}/app{app_number}/task_{task_id}/
├── {model}_app{N}_task_{id}_{timestamp}.json  (10+ MB consolidated results)
├── manifest.json                               (file inventory)
├── sarif/
│   ├── security_python_bandit.sarif.json
│   ├── security_python_semgrep.sarif.json
│   ├── static_python_pylint.sarif.json
│   └── ... (9 SARIF files total)
└── services/
    ├── security_snapshot.json
    ├── static_snapshot.json
    ├── performance_snapshot.json
    └── dynamic_snapshot.json
```

---

## Common Use Cases

### Batch Analysis
```powershell
# Analyze multiple models/apps
@("anthropic_claude-4.5-sonnet-20250929", "anthropic_claude-4.5-haiku-20251001") | ForEach-Object {
    $model = $_
    1..2 | ForEach-Object {
        $app = $_
        $body = @{
            model_slug = $model
            app_number = $app
            analysis_type = "comprehensive"
        } | ConvertTo-Json
        
        $result = Invoke-RestMethod `
            -Uri "http://localhost:5000/api/analysis/run" `
            -Headers $headers `
            -Method POST `
            -Body $body
        
        Write-Host "✓ Created: $model app$app - $($result.task_id)"
        Start-Sleep -Milliseconds 500
    }
}
```

### Poll Until Complete
```powershell
$taskId = "task_50a9c0d47c25"
$maxWait = 300  # 5 minutes
$elapsed = 0

Write-Host "Polling task $taskId..."
while ($elapsed -lt $maxWait) {
    try {
        $summary = Invoke-RestMethod `
            -Uri "http://localhost:5000/analysis/api/tasks/$taskId/summary" `
            -Headers $headers `
            -Method GET
        
        if ($summary.status -eq "completed") {
            Write-Host "✓ Task complete!"
            $summary.results.summary | Format-List
            break
        } elseif ($summary.status -eq "failed") {
            Write-Host "✗ Task failed: $($summary.error)"
            break
        }
        
        Write-Host "  Status: $($summary.status) (${elapsed}s elapsed)"
        Start-Sleep -Seconds 10
        $elapsed += 10
    } catch {
        Write-Host "  Task not ready yet..."
        Start-Sleep -Seconds 5
        $elapsed += 5
    }
}
```

---

## Error Handling

### Common Errors

**401 Unauthorized:**
```json
{
  "error": "Authentication required",
  "message": "Please log in to access this endpoint"
}
```
→ Check token is set correctly in headers

**404 Not Found:**
```json
{
  "error": "Application not found: model_slug/appN"
}
```
→ Verify model slug and app number exist

**500 Server Error:**
```json
{
  "success": false,
  "error": "Failed to run analysis: ...",
  "status_code": 500
}
```
→ Check Flask app logs for details

---

## Performance Notes

- **Security analysis:** ~30-45 seconds
- **Static analysis:** ~50-70 seconds
- **Performance test:** ~3-4 minutes
- **Dynamic analysis:** ~30-40 seconds
- **Total comprehensive:** ~5-6 minutes

---

## See Also

- `docs/API_AUTH_AND_METHODS.md` - Detailed API authentication guide
- `WEB_APP_INTEGRATION_COMPLETE.md` - Integration architecture
- `docs/reference/API_REFERENCE.md` - Full API endpoint documentation

---

**Last Updated:** 2025-11-03  
**Tested With:** anthropic_claude-4.5-haiku-20251001, anthropic_claude-4.5-sonnet-20250929
