"""Examine the structure of result_summary for different tasks."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app import create_app
from app.models.analysis_models import AnalysisTask

app = create_app()

with app.app_context():
    # Get one task with "empty" results
    empty_task = AnalysisTask.query.filter_by(task_id='task_6654ce4e84c5').first()
    
    # Get one task with "full" results (the one we saw in the file)
    full_task = AnalysisTask.query.filter_by(task_id='task_4dbdb63beb74').first()
    
    print("=" * 80)
    print("TASK WITH 'EMPTY' RESULTS (task_6654ce4e84c5)")
    print("=" * 80)
    
    if empty_task and empty_task.result_summary:
        data = json.loads(empty_task.result_summary)
        print(f"\nTop-level keys: {list(data.keys())}")
        
        if 'services' in data:
            print(f"\nServices: {list(data['services'].keys())}")
            for service, service_data in data['services'].items():
                if isinstance(service_data, dict):
                    payload = service_data.get('payload', {})
                    tool_results = payload.get('tool_results', {})
                    print(f"  {service}:")
                    print(f"    Status: {service_data.get('status')}")
                    print(f"    Tools in payload: {list(tool_results.keys())}")
        
        if 'summary' in data:
            print(f"\nSummary: {data['summary']}")
    
    print("\n" + "=" * 80)
    print("TASK WITH 'FULL' RESULTS (task_4dbdb63beb74)")
    print("=" * 80)
    
    if full_task and full_task.result_summary:
        data = json.loads(full_task.result_summary)
        print(f"\nTop-level keys: {list(data.keys())}")
        
        if 'results' in data:
            results = data['results']
            print(f"\nResults keys: {list(results.keys())}")
            print(f"Tools requested: {results.get('tools_requested', [])}")
            print(f"Tool results: {list(results.get('tool_results', {}).keys())}")
            
            if 'raw_outputs' in results:
                raw = results['raw_outputs']
                print(f"Service: {raw.get('service', 'unknown')}")
                print(f"Status: {raw.get('status', 'unknown')}")
        
        if 'summary' in data:
            print(f"\nSummary: {data['summary']}")
    
    print("\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print("\nThe 'empty' tasks have:")
    print("  - services: {performance-tester, static-analyzer, dynamic-analyzer, ai-analyzer}")
    print("  - BUT: No tools executed within those services")
    print("  - Structure: task.services.SERVICE.payload.tool_results")
    print("\nThe 'full' tasks have:")
    print("  - results: {tool_results, raw_outputs}")
    print("  - Tools: requirements-scanner")
    print("  - Service: ai-analyzer")
    print("  - Structure: task.results.tool_results")
