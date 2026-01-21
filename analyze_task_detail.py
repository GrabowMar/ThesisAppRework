import json
from pathlib import Path

task_id = 'task_33be9fd0826d'
result_file = Path('results/anthropic_claude-4.5-sonnet-20250929/app7') / task_id / f'anthropic_claude-4.5-sonnet-20250929_app7_{task_id}_20260121_212744.json'

if result_file.exists():
    with open(result_file) as f:
        data = json.load(f)
    
    print("="*80)
    print("TASK RESULT FILE ANALYSIS")
    print("="*80)
    print(f"\nTask: {task_id}")
    print(f"File: {result_file}")
    print()
    
    # Summary
    summary = data.get('summary', {})
    print(f"Summary:")
    print(f"  total_findings: {summary.get('total_findings')}")
    print(f"  services_executed: {summary.get('services_executed')}")
    print(f"  tools_executed: {summary.get('tools_executed')}")
    print(f"  status: {summary.get('status')}")
    print()
    
    # Services
    services = data.get('services', {})
    print(f"Services ({len(services)}):")
    for service_name, service_data in services.items():
        print(f"\n  {service_name}:")
        print(f"    status: {service_data.get('status')}")
        
        # Check for analysis data
        analysis = service_data.get('analysis', {})
        print(f"    analysis keys: {list(analysis.keys())[:10]}")
        
        # Check for findings
        findings = analysis.get('findings', [])
        print(f"    findings: {len(findings)}")
        
        # Check for tools/results
        if 'results' in analysis:
            results = analysis.get('results', {})
            if isinstance(results, dict):
                print(f"    results structure:")
                for key, value in results.items():
                    if isinstance(value, dict):
                        print(f"      {key}: {list(value.keys())[:5]}")
                        # Check for tools with issues
                        for tool_name, tool_data in value.items():
                            if isinstance(tool_data, dict):
                                issues = tool_data.get('issues', [])
                                if len(issues) > 0:
                                    print(f"        → {tool_name}: {len(issues)} issues")
        
        # Check tool_results
        if 'tool_results' in analysis:
            tool_results = analysis.get('tool_results', {})
            print(f"    tool_results: {list(tool_results.keys())[:5]}")
    
    print()
    print("="*80)
else:
    print(f"File not found: {result_file}")
