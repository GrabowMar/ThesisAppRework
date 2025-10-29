#!/usr/bin/env python3
"""Check which tools ran in the analysis task."""
import sys
sys.path.insert(0, 'src')

from app import create_app
from app.models import AnalysisTask

app = create_app()
with app.app_context():
    task = AnalysisTask.query.filter_by(task_id='task_c0e7bdb31730').first()
    if not task:
        print("Task not found")
        sys.exit(1)
    
    result = task.get_result_summary()
    services = result.get('services', {})
    
    # Check for tools at top level (new format)
    tool_results = result.get('tool_results') or result.get('tools', {})
    
    print("\n" + "="*60)
    print("ANALYSIS TOOL EXECUTION STATUS")
    print("="*60)
    
    if tool_results:
        print("\n🔧 TOP-LEVEL TOOL RESULTS (Aggregated)")
        print("-" * 60)
        
        for tool_name, tool_data in tool_results.items():
            status = tool_data.get('status', 'unknown')
            emoji = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
            
            findings = tool_data.get('total_issues', 0)
            executed = tool_data.get('executed', False)
            
            print(f"  {emoji} {tool_name:20s} - {status:10s} (executed: {executed}, issues: {findings})")
    
    # Also check service-level tool results (old format)
    for service_name, service_data in services.items():
        print(f"\n📦 {service_name.upper()}")
        print("-" * 60)
        
        tool_results = service_data.get('tool_results', {})
        if not tool_results:
            print("  ⚠️  No tool results found")
            continue
        
        for tool_name, tool_data in tool_results.items():
            status = tool_data.get('status', 'unknown')
            emoji = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
            
            findings = tool_data.get('findings', [])
            findings_count = len(findings) if isinstance(findings, list) else 0
            
            print(f"  {emoji} {tool_name:20s} - {status:10s} ({findings_count} findings)")
            
            if status == "error":
                error = tool_data.get('error', 'No error message')
                print(f"      Error: {error[:100]}")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    all_tools = list(tool_results.keys()) if tool_results else []
    
    # Also count from services if tool_results not at top level
    if not all_tools:
        for service_data in services.values():
            all_tools.extend(service_data.get('tool_results', {}).keys())
    
    success_count = len([t for t in tool_results.values() if t.get('status') == 'success']) if tool_results else 0
    error_count = len([t for t in tool_results.values() if t.get('status') == 'error']) if tool_results else 0
    
    # Also count from services if tool_results not at top level
    if not tool_results:
        for service_data in services.values():
            for tool_data in service_data.get('tool_results', {}).values():
                if tool_data.get('status') == 'success':
                    success_count += 1
                elif tool_data.get('status') == 'error':
                    error_count += 1
    
    print(f"Total tools: {len(all_tools)}")
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed: {error_count}")
    print("="*60 + "\n")
