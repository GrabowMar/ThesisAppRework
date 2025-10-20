# 🚀 Fresh Start Complete - Testing Workflow

**Date**: October 20, 2025  
**Status**: Clean Slate Ready  
**Goal**: Generate 3 apps, analyze them, test dashboard holistically

---

## ✅ What Was Reset

### Database
- ✅ SQLite database wiped and reinitialized
- ✅ All tasks cleared
- ✅ All analysis records removed
- ✅ Fresh models data loaded (291 models)

### Generated Apps
- ✅ All previous apps removed from `generated/apps/`
- ✅ All metadata cleaned
- ✅ Port allocations reset

### Results
- ✅ All previous analysis results removed
- ✅ Only test data retained

### System State
- ✅ Flask running on http://127.0.0.1:5000
- ✅ Todo list cleared
- ✅ Clean logs

---

## 📋 Complete Testing Workflow

### Phase 1: Generate 3 Sample Apps

**Goal**: Create 3 new applications using different models

#### Option A: UI Generation (Recommended)
1. Open Sample Generator: http://127.0.0.1:5000/sample-generator/
2. Generate App #1:
   - Model: `openai/gpt-4o-mini` (fast, reliable)
   - Template: Task Manager or any template
   - Features: Select auth, crud, responsive
   - Click "Generate Application"
   - Wait for completion (~30-60 seconds)

3. Generate App #2:
   - Model: `anthropic/claude-3-5-sonnet-20241022` (best quality)
   - Template: Different from App #1
   - Generate and wait

4. Generate App #3:
   - Model: `google/gemini-2.0-flash-exp` (free, fast)
   - Template: Different from previous
   - Generate and wait

#### Option B: API Generation (Alternative)
```powershell
# App 1 - GPT-4o-mini
$payload1 = @{
    model_slug = "openai/gpt-4o-mini"
    app_num = 1
    template_id = 1
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/gen/generate" `
    -Method POST -ContentType "application/json" -Body $payload1

# Repeat for App 2 and 3 with different models
```

#### Verification
```powershell
# Check applications page
Start-Process "http://127.0.0.1:5000/applications"

# Or via API
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/gen/apps"
```

**Expected Result**:
- 3 apps in `generated/apps/` directory
- Each with scaffolding (Dockerfile, docker-compose.yml, etc.)
- Backend and frontend code generated
- Visible in Applications page

---

### Phase 2: Analyze Applications

**Goal**: Run static security and quality analysis on each app

#### Start Analyzer Services
```powershell
python analyzer/analyzer_manager.py start
```

Wait 15 seconds for services to initialize.

#### Check Service Health
```powershell
python analyzer/analyzer_manager.py health
```

Expected output:
```
✓ Static Analyzer: Running
✓ AI Analyzer: Running
✗ Dynamic Analyzer: Optional (requires running apps)
✗ Performance Tester: Optional (requires running apps)
```

#### Analyze Each App

**App 1 - Security Analysis**:
```powershell
python analyzer/analyzer_manager.py analyze openai/gpt-4o-mini 1 security --tools bandit safety
```

**App 1 - Quality Analysis**:
```powershell
python analyzer/analyzer_manager.py analyze openai/gpt-4o-mini 1 quality --tools pylint flake8 eslint
```

**App 2 - Security**:
```powershell
python analyzer/analyzer_manager.py analyze anthropic/claude-3-5-sonnet-20241022 2 security --tools bandit safety
```

**App 2 - Quality**:
```powershell
python analyzer/analyzer_manager.py analyze anthropic/claude-3-5-sonnet-20241022 2 quality --tools pylint flake8
```

**App 3 - Security**:
```powershell
python analyzer/analyzer_manager.py analyze google/gemini-2.0-flash-exp 3 security --tools bandit safety
```

**App 3 - Quality**:
```powershell
python analyzer/analyzer_manager.py analyze google/gemini-2.0-flash-exp 3 quality --tools pylint flake8
```

#### Verification
```powershell
# Check results directory
Get-ChildItem results/ -Recurse -File | Measure-Object

# Expected: 6+ result files (2 per app minimum)

# Check Analysis Hub
Start-Process "http://127.0.0.1:5000/analysis/"
```

**Expected Result**:
- Result files in `results/<model_slug>/app<num>/`
- Tasks visible in Analysis Hub
- Status: Completed
- Findings count > 0

---

### Phase 3: Test Dashboard Holistically

**Goal**: Verify dashboard displays results correctly for each app

#### Test App 1 Dashboard
```powershell
# Open dashboard
Start-Process "http://127.0.0.1:5000/analysis/dashboard/app/openai_gpt-4o-mini/1"
```

**Manual Checks**:
1. ✅ **Page Loads**: No 500 error, no infinite spinner
2. ✅ **7 Tabs Visible**: Overview, Security, Performance, Quality, AI Requirements, Tools, Raw Data
3. ✅ **Overview Tab**:
   - Summary cards show counts (Total Findings, Security Issues, etc.)
   - Severity breakdown chart
   - Category distribution
   - Top 5 priority issues table
4. ✅ **Security Tab**:
   - Security findings listed
   - Severity filter works (Critical, High, Medium, Low)
   - Findings have tool, message, file, line
5. ✅ **Quality Tab**:
   - Quality findings listed
   - Tool filter works (Pylint, Flake8, ESLint)
6. ✅ **Tools Tab**:
   - Lists all 18 tools
   - Shows execution status (Executed/Not Run)
   - Bandit, Safety shown as executed
7. ✅ **Raw Data Tab**:
   - HTMX loads JSON data
   - JSON explorer shows complete results
8. ✅ **Modals**:
   - Click any finding row
   - Detail modal opens
   - Shows full finding information

**Browser Console Check**:
- Press F12
- Check Console tab
- Expected: No red errors
- HTMX requests should return 200

#### Test App 2 Dashboard
```powershell
Start-Process "http://127.0.0.1:5000/analysis/dashboard/app/anthropic_claude-3-5-sonnet-20241022/2"
```

Repeat all checks from App 1.

#### Test App 3 Dashboard
```powershell
Start-Process "http://127.0.0.1:5000/analysis/dashboard/app/google_gemini-2.0-flash-exp/3"
```

Repeat all checks.

---

### Phase 4: Test Task Detail Pages

**Goal**: Verify task detail pages work correctly

#### Test Task List
```powershell
Start-Process "http://127.0.0.1:5000/analysis/"
```

**Checks**:
- All 6 tasks visible (2 per app: security + quality)
- Status badges show "Completed"
- Click "View Results" button on any task

#### Test Task Detail Page
From Analysis Hub, click any task's "View Results" button.

**Manual Checks**:
1. ✅ Task detail page loads
2. ✅ Same 7-tab structure as dashboard
3. ✅ Sidebar shows "Dashboard View" button
4. ✅ Click "Dashboard View" → redirects to dashboard
5. ✅ All tabs load data correctly

---

### Phase 5: End-to-End Workflow Test

**Goal**: Complete user journey from generation to analysis visualization

1. **Generate** new app via UI
2. **Wait** for completion notification
3. **Navigate** to Applications page
4. **Find** new app in list
5. **Click** "Start Container" (optional - for dynamic/performance)
6. **Navigate** to Analysis Hub
7. **Click** "New Analysis" button
8. **Select** model and app
9. **Choose** "Security" analysis type
10. **Run** analysis
11. **Wait** for task completion
12. **Click** "View Results"
13. **Verify** dashboard shows new results
14. **Test** all 7 tabs
15. **Export** CSV (if available)

---

## 🐛 Troubleshooting

### Dashboard Shows No Data
**Symptoms**: Tabs load but show "No findings" or empty tables

**Fixes**:
1. Check if analysis actually completed:
   ```powershell
   Get-ChildItem results/<model_slug>/app<num>/ -Recurse
   ```
2. Verify results.json exists and has findings
3. Check browser console for API errors
4. Verify Flask logs for 500 errors

### 500 Error on Dashboard
**Symptoms**: Internal Server Error page

**Fixes**:
1. Check Flask logs:
   ```powershell
   Get-Content logs/app.log -Tail 50
   ```
2. Verify task_id or model_slug/app_number is correct
3. Check if results file exists
4. Restart Flask if needed

### HTMX Raw Data Tab Not Loading
**Symptoms**: Raw Data tab shows spinner forever

**Fixes**:
1. Check browser console for HTMX errors
2. Verify endpoint `/api/tasks/<task_id>/results.json` works:
   ```powershell
   Invoke-RestMethod "http://127.0.0.1:5000/analysis/api/tasks/<task_id>/results.json"
   ```
3. Check if task has results payload

### Analysis Fails
**Symptoms**: Task status stays "Running" or fails

**Fixes**:
1. Check analyzer services:
   ```powershell
   python analyzer/analyzer_manager.py health
   ```
2. Check analyzer logs:
   ```powershell
   python analyzer/analyzer_manager.py logs static-analyzer 50
   ```
3. Restart analyzers:
   ```powershell
   python analyzer/analyzer_manager.py restart
   ```

---

## ✅ Success Criteria

### Generation Phase
- [ ] 3 apps generated successfully
- [ ] Each app has scaffolding files (15+ files)
- [ ] Each app visible in Applications page
- [ ] No generation errors in logs

### Analysis Phase
- [ ] 6+ analysis tasks completed
- [ ] Result files exist in `results/` directory
- [ ] Each result has findings (count > 0)
- [ ] No analyzer errors in logs

### Dashboard Phase
- [ ] All 3 dashboards load without 500 errors
- [ ] 7 tabs present on each dashboard
- [ ] Overview tab shows summary data
- [ ] Security/Quality tabs show findings
- [ ] Tools tab lists 18 tools
- [ ] Raw Data tab loads JSON
- [ ] Finding detail modal works
- [ ] No console errors in browser

### End-to-End
- [ ] Can generate new app via UI
- [ ] Can run analysis via UI
- [ ] Can view results in dashboard
- [ ] All tabs functional
- [ ] Data displays correctly
- [ ] No blocking errors

---

## 📊 Quick Status Check

```powershell
# System status check script
Write-Host "=== SYSTEM STATUS CHECK ===" -ForegroundColor Cyan

# Check Flask
try {
    $flask = Invoke-WebRequest "http://127.0.0.1:5000" -TimeoutSec 2 -UseBasicParsing
    Write-Host "✓ Flask: Running" -ForegroundColor Green
} catch {
    Write-Host "✗ Flask: Not running" -ForegroundColor Red
}

# Check generated apps
$apps = Get-ChildItem "generated/apps" -Directory -ErrorAction SilentlyContinue
Write-Host "✓ Generated Apps: $($apps.Count)" -ForegroundColor Green

# Check results
$results = Get-ChildItem "results" -Recurse -File -ErrorAction SilentlyContinue
Write-Host "✓ Result Files: $($results.Count)" -ForegroundColor Green

# Check analyzer services
$analyzerStatus = & python analyzer/analyzer_manager.py health 2>&1
if ($analyzerStatus -match "Running") {
    Write-Host "✓ Analyzers: Running" -ForegroundColor Green
} else {
    Write-Host "⚠ Analyzers: Check status" -ForegroundColor Yellow
}
```

---

## 🎯 Next Steps

After successful testing:

1. **Document Issues**: Note any bugs or unexpected behavior
2. **Iterate**: Fix any issues found during testing
3. **Enhance**: Add missing features or improvements
4. **Optimize**: Improve performance based on testing
5. **Deploy**: Prepare for production deployment

**Current Status**: ✅ Clean slate ready for testing!

**Flask**: Running on http://127.0.0.1:5000  
**Analyzers**: Ready to start  
**Database**: Fresh and initialized  

**Start testing now!** 🚀
