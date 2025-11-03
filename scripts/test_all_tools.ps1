#!/usr/bin/env pwsh
# Comprehensive tool testing script
# Tests all 15+ tools across all 4 analyzer services

param(
    [string]$Token = "NWD8q8Q67IH1li7k_4Jy30SLBlqj_j9mkCl--Yoj20hRmRCwzZYhvHUZBvle9Ib-",
    [string]$Model = "anthropic_claude-4.5-sonnet-20250929",
    [int]$App = 1
)

$ErrorActionPreference = "Stop"

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "  Comprehensive Analyzer Tool Testing" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

# Define test sets
$testSets = @(
    @{
        Name = "Static Analysis - Python"
        Tools = @("bandit", "semgrep")
        ExpectedService = "static-analyzer"
        Timeout = 30
    },
    @{
        Name = "Static Analysis - JavaScript"
        Tools = @("eslint")
        ExpectedService = "static-analyzer"
        Timeout = 25
    },
    @{
        Name = "Static Analysis - CSS"
        Tools = @("stylelint")
        ExpectedService = "static-analyzer"
        Timeout = 20
    },
    @{
        Name = "Combined Static Analysis"
        Tools = @("bandit", "semgrep", "eslint", "stylelint")
        ExpectedService = "static-analyzer"
        Timeout = 40
    }
)

function Invoke-AnalysisTest {
    param(
        [string]$TestName,
        [array]$Tools,
        [string]$ExpectedService,
        [int]$Timeout
    )
    
    Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
    Write-Host "  TEST: $TestName" -ForegroundColor Yellow
    Write-Host "  Tools: $($Tools -join ', ')" -ForegroundColor Gray
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
    
    # Create request
    $body = @{
        model_slug = $Model
        app_number = $App
        tools = $Tools
        priority = "high"
    } | ConvertTo-Json
    
    try {
        # Submit analysis
        Write-Host "[1/4] Submitting analysis request..." -ForegroundColor Cyan
        $response = Invoke-RestMethod `
            -Uri "http://localhost:5000/api/analysis/run" `
            -Method POST `
            -Body $body `
            -ContentType "application/json" `
            -Headers @{Authorization="Bearer $Token"}
        
        $taskId = $response.task_id
        Write-Host "  ✓ Task created: $taskId" -ForegroundColor Green
        
        # Wait for completion
        Write-Host "[2/4] Waiting for analysis to complete (max ${Timeout}s)..." -ForegroundColor Cyan
        Start-Sleep -Seconds $Timeout
        
        # Check for result file
        Write-Host "[3/4] Checking for result file..." -ForegroundColor Cyan
        $resultPath = "results\$Model\app$App\$taskId"
        
        if (-not (Test-Path $resultPath)) {
            Write-Host "  ✗ Result path not found: $resultPath" -ForegroundColor Red
            return @{Success=$false; Error="Result path not found"}
        }
        
        $jsonFile = Get-ChildItem $resultPath -Filter "*.json" -Exclude "manifest.json" | Select-Object -First 1
        
        if (-not $jsonFile) {
            Write-Host "  ✗ No result JSON file found" -ForegroundColor Red
            return @{Success=$false; Error="No JSON file"}
        }
        
        Write-Host "  ✓ Result file found: $($jsonFile.Name) ($([math]::Round($jsonFile.Length/1KB, 2)) KB)" -ForegroundColor Green
        
        # Parse and validate results
        Write-Host "[4/4] Validating results..." -ForegroundColor Cyan
        $result = Get-Content $jsonFile.FullName | ConvertFrom-Json
        
        $summary = $result.results.summary
        $tools = $result.results.tools
        $findings = $result.results.findings
        $services = $result.results.services
        
        Write-Host ""
        Write-Host "  Summary:" -ForegroundColor White
        Write-Host "    Services executed: $($summary.services_executed)" -ForegroundColor Gray
        Write-Host "    Tools executed: $($summary.tools_executed)" -ForegroundColor Gray
        Write-Host "    Total findings: $($summary.total_findings)" -ForegroundColor Gray
        Write-Host "    Status: $($summary.status)" -ForegroundColor $(if($summary.status -eq 'completed'){'Green'}else{'Yellow'})
        
        if ($summary.severity_breakdown) {
            Write-Host "    Severity: H=$($summary.severity_breakdown.high) M=$($summary.severity_breakdown.medium) L=$($summary.severity_breakdown.low) I=$($summary.severity_breakdown.info)" -ForegroundColor Gray
        }
        
        Write-Host ""
        Write-Host "  Tools:" -ForegroundColor White
        $toolsList = @()
        foreach ($toolProp in $tools.PSObject.Properties) {
            $tool = $toolProp.Value
            $status = $tool.status
            $issues = $tool.total_issues
            $color = switch ($status) {
                "success" { "Green" }
                "no_issues" { "Green" }
                "error" { "Red" }
                "timeout" { "Yellow" }
                default { "Gray" }
            }
            Write-Host "    $($toolProp.Name): status=$status, issues=$issues" -ForegroundColor $color
            $toolsList += $toolProp.Name
        }
        
        # Validate expected tools
        $missingTools = $Tools | Where-Object { $_ -notin $toolsList }
        if ($missingTools) {
            Write-Host ""
            Write-Host "  ⚠ Missing tools: $($missingTools -join ', ')" -ForegroundColor Yellow
        }
        
        # Show findings summary
        if ($findings -and $findings.Count -gt 0) {
            Write-Host ""
            Write-Host "  Findings:" -ForegroundColor White
            $findings | ForEach-Object {
                $sevColor = switch ($_.severity) {
                    "high" { "Red" }
                    "medium" { "Yellow" }
                    "low" { "Gray" }
                    default { "White" }
                }
                Write-Host "    [$($_.severity.ToUpper())] $($_.tool): $($_.message)" -ForegroundColor $sevColor
                if ($_.file -and $_.line) {
                    Write-Host "      @ $($_.file):$($_.line)" -ForegroundColor DarkGray
                }
            }
        }
        
        # Validation checks
        $checks = @()
        $checks += @{Name="Services executed"; Pass=($summary.services_executed -gt 0)}
        $checks += @{Name="Tools executed"; Pass=($summary.tools_executed -gt 0)}
        $checks += @{Name="Has severity breakdown"; Pass=($null -ne $summary.severity_breakdown)}
        $checks += @{Name="Has services data"; Pass=($services.PSObject.Properties.Count -gt 0)}
        $checks += @{Name="All requested tools present"; Pass=($missingTools.Count -eq 0)}
        
        Write-Host ""
        Write-Host "  Validation:" -ForegroundColor White
        foreach ($check in $checks) {
            $symbol = if ($check.Pass) { "✓" } else { "✗" }
            $color = if ($check.Pass) { "Green" } else { "Red" }
            Write-Host "    $symbol $($check.Name)" -ForegroundColor $color
        }
        
        $allPassed = ($checks | Where-Object { -not $_.Pass }).Count -eq 0
        
        Write-Host ""
        if ($allPassed) {
            Write-Host "  RESULT: PASS ✓" -ForegroundColor Green
        } else {
            Write-Host "  RESULT: PARTIAL ⚠" -ForegroundColor Yellow
        }
        
        return @{
            Success = $allPassed
            TaskId = $taskId
            ToolsExecuted = $summary.tools_executed
            TotalFindings = $summary.total_findings
            Status = $summary.status
            MissingTools = $missingTools
        }
        
    } catch {
        Write-Host ""
        Write-Host "  ✗ TEST FAILED: $_" -ForegroundColor Red
        return @{Success=$false; Error=$_.Exception.Message}
    }
}

# Run all test sets
$testResults = @()

foreach ($testSet in $testSets) {
    $result = Invoke-AnalysisTest `
        -TestName $testSet.Name `
        -Tools $testSet.Tools `
        -ExpectedService $testSet.ExpectedService `
        -Timeout $testSet.Timeout
    
    $testResults += @{
        TestName = $testSet.Name
        Result = $result
    }
    
    Start-Sleep -Seconds 3
}

# Final summary
Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "  TEST SUMMARY" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

$passed = ($testResults | Where-Object { $_.Result.Success }).Count
$total = $testResults.Count

foreach ($test in $testResults) {
    $symbol = if ($test.Result.Success) { "✓" } else { "✗" }
    $color = if ($test.Result.Success) { "Green" } else { "Red" }
    Write-Host "$symbol $($test.TestName)" -ForegroundColor $color
    if ($test.Result.TaskId) {
        Write-Host "    Task: $($test.Result.TaskId) | Tools: $($test.Result.ToolsExecuted) | Findings: $($test.Result.TotalFindings)" -ForegroundColor Gray
    }
    if ($test.Result.Error) {
        Write-Host "    Error: $($test.Result.Error)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Overall: $passed/$total tests passed" -ForegroundColor $(if($passed -eq $total){'Green'}else{'Yellow'})
Write-Host ""
