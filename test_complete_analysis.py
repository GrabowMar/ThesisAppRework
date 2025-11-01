#!/usr/bin/env python3
"""
Complete Analysis Test
======================

Tests all analyzer services including:
- Static Analysis (Bandit, Pylint, ESLint, etc.)
- Dynamic Analysis (ZAP, nmap, curl)
- Performance Testing (ab, locust, artillery)
- AI Analysis (Claude 3.5 Haiku via OpenRouter)
"""

import asyncio
import sys
import json
from pathlib import Path
from analyzer.analyzer_manager import AnalyzerManager

async def test_complete_analysis():
    """Run a complete analysis to test all services."""
    manager = AnalyzerManager()
    
    print("=" * 80)
    print("COMPLETE ANALYSIS TEST")
    print("=" * 80)
    print()
    print("Testing model: anthropic_claude-4.5-haiku-20251001 app 1")
    print()
    
    # Run comprehensive analysis
    print("[1/5] Running comprehensive analysis...")
    task_name = f"analysis_{asyncio.get_event_loop().time():.0f}"
    service_results = await manager.run_comprehensive_analysis(
        model_slug="anthropic_claude-4.5-haiku-20251001",
        app_number=1,
        task_name=task_name
    )
    
    # Find and load the saved consolidated results
    results_base = Path("c:/Users/grabowmar/Desktop/ThesisAppRework/results")
    model_dir = results_base / "anthropic_claude-4.5-haiku-20251001" / "app1"
    
    # Find the latest task directory
    task_dirs = [d for d in model_dir.glob("task_*") if d.is_dir()]
    if not task_dirs:
        print("[X] No task results found!")
        return service_results
    
    latest_task_dir = max(task_dirs, key=lambda p: p.stat().st_mtime)
    
    # Load the consolidated JSON (not the universal one or manifest)
    result_files = [f for f in latest_task_dir.glob("*.json") 
                   if "universal" not in f.name and f.name != "manifest.json"]
    if not result_files:
        print("[X] No result files found!")
        return service_results
    
    with open(result_files[0], 'r') as f:
        result = json.load(f)
    
    print(f"[+] Loaded results from: {result_files[0].name}")
    
    # Extract data from the consolidated structure
    summary = result.get('results', {}).get('summary', {})
    services = result.get('results', {}).get('services', {})
    tools = result.get('tools', {})
    findings = result.get('findings', [])
    
    print(f"\n[+] Analysis Status: {summary.get('status', 'unknown')}")
    
    # Check services
    print(f"\n[2/5] Services Executed: {summary.get('services_executed', 0)}")
    for service_name, service_data in services.items():
        status = service_data.get('status', 'unknown')
        symbol = "[OK]" if status == "success" else "[X]"
        print(f"  {symbol} {service_name}: {status}")
    
    # Check tools
    tools_used = summary.get('tools_used', [])
    tools_failed = summary.get('tools_failed', [])
    print(f"\n[3/5] Tools Executed: {len(tools_used)}")
    successful_tools = [t for t in tools_used if t not in tools_failed]
    
    print(f"  [+] Successful: {len(successful_tools)}")
    print(f"      {', '.join(successful_tools[:10])}")
    if len(successful_tools) > 10:
        print(f"      ... and {len(successful_tools) - 10} more")
    
    if tools_failed:
        print(f"  [!] Failed: {len(tools_failed)}")
        print(f"      {', '.join(tools_failed)}")
    
    # Check findings
    total_findings = summary.get('total_findings', 0)
    print(f"\n[4/5] Findings: {total_findings}")
    
    severity_breakdown = summary.get('severity_breakdown', {})
    for severity in ['high', 'medium', 'low']:
        count = severity_breakdown.get(severity, 0)
        if count > 0:
            print(f"  {severity.upper()}: {count}")
    
    # Check ZAP results
    print(f"\n[5/5] Checking ZAP Integration...")
    dynamic_service = services.get('dynamic', {})
    if dynamic_service:
        dynamic_analysis = dynamic_service.get('analysis', {})
        zap_results = dynamic_analysis.get('results', {}).get('zap_security_scan', [])
        if zap_results:
            for zap_result in zap_results:
                url = zap_result.get('url', 'unknown')
                total_alerts = zap_result.get('total_alerts', 0)
                status = zap_result.get('status', 'unknown')
                print(f"  [>] {url}")
                print(f"      Status: {status}")
                print(f"      Alerts: {total_alerts}")
                
                alerts_by_risk = zap_result.get('alerts_by_risk', {})
                for risk, alerts in alerts_by_risk.items():
                    if alerts:
                        print(f"      {risk}: {len(alerts)} issues")
        else:
            # Check the flat tools map
            zap_tool = tools.get('zap', {})
            print(f"  ZAP Tool Status: {zap_tool.get('status', 'unknown')}")
            print(f"  ZAP Executed: {zap_tool.get('executed', False)}")
            if zap_tool.get('details'):
                print(f"  ZAP Details: {zap_tool['details']}")
    
    # Summary
    print()
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Status: {summary.get('status')}")
    print(f"Services: {summary.get('services_executed', 0)} executed")
    print(f"Tools: {len(successful_tools)} successful, {len(tools_failed)} failed")
    print(f"Findings: {total_findings} total")
    print()
    print(f"Results saved to: {latest_task_dir.relative_to(results_base)}/")
    
    return result

if __name__ == '__main__':
    try:
        result = asyncio.run(test_complete_analysis())
        # Check status from the consolidated results
        status = result.get('results', {}).get('summary', {}).get('status')
        sys.exit(0 if status == 'completed' else 1)
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
