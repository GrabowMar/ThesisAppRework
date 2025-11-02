"""Generate comprehensive validation report for all analyzer services and tools."""
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.models import AnalysisTask

def main():
    app = create_app()
    with app.app_context():
        # All comprehensive test tasks
        task_ids = [
            'task_a0f9698aeee2', 'task_04dc0a4792d7', 'task_426bcba6fa08', 
            'task_420e917ab03d', 'task_050c2d2813d0', 'task_c6d2526628a3', 
            'task_cb4eae4fb1bf', 'task_9e31aff0a44a', 'task_0a66abbd65f6', 
            'task_e39fd2ed305e'
        ]
        
        print("\n" + "="*80)
        print("COMPREHENSIVE ANALYZER VALIDATION REPORT")
        print("="*80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Track all tools tested
        all_tools_requested = set()
        all_tools_executed = set()
        all_services_used = set()
        
        completed_count = 0
        running_count = 0
        pending_count = 0
        
        for task_id in task_ids:
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if not task:
                continue
            
            # Get task metadata
            try:
                meta = task.get_metadata() or {}
                custom = meta.get('custom_options', {})
                tools_requested = custom.get('selected_tool_names', [])
                desc = custom.get('description', 'N/A')
            except:
                tools_requested = []
                desc = 'N/A'
            
            all_tools_requested.update(tools_requested)
            
            # Count by status
            if task.status == 'completed':
                completed_count += 1
            elif task.status == 'running':
                running_count += 1
            else:
                pending_count += 1
            
            print(f"\nTask: {task_id}")
            print(f"  Type: {desc}")
            print(f"  Status: {task.status}")
            print(f"  Tools Requested ({len(tools_requested)}): {', '.join(tools_requested)}")
            
            # Check result file if completed
            if task.status == 'completed':
                result_path = Path("results")
                result_files = list(result_path.rglob(f"*{task_id}*.json"))
                
                if result_files:
                    result_file = result_files[0]
                    print(f"  Result File: {result_file.name}")
                    print(f"  File Size: {result_file.stat().st_size / 1024:.1f} KB")
                    
                    # Parse result to see what actually executed
                    try:
                        with open(result_file) as f:
                            result_data = json.load(f)
                        
                        results = result_data.get('results', {})
                        summary = results.get('summary', {})
                        tools = results.get('tools', {})
                        services = results.get('services', {})
                        
                        tools_executed = [t for t in tools.keys()]
                        services_executed = [s for s in services.keys()]
                        
                        all_tools_executed.update(tools_executed)
                        all_services_used.update(services_executed)
                        
                        print(f"  Tools Executed ({len(tools_executed)}): {', '.join(tools_executed) if tools_executed else 'None'}")
                        print(f"  Services Used ({len(services_executed)}): {', '.join(services_executed) if services_executed else 'None'}")
                        print(f"  Total Findings: {summary.get('total_findings', 0)}")
                        
                    except Exception as e:
                        print(f"  ✗ Error parsing result: {e}")
                else:
                    print(f"  ✗ No result file found")
        
        # Summary
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"\nTask Status:")
        print(f"  Completed: {completed_count}/{len(task_ids)}")
        print(f"  Running:   {running_count}/{len(task_ids)}")
        print(f"  Pending:   {pending_count}/{len(task_ids)}")
        
        print(f"\nTools Coverage:")
        print(f"  Tools Requested: {len(all_tools_requested)}")
        print(f"    {', '.join(sorted(all_tools_requested))}")
        print(f"  Tools Executed: {len(all_tools_executed)}")
        print(f"    {', '.join(sorted(all_tools_executed))}")
        
        print(f"\nAnalyzer Services Used:")
        if all_services_used:
            print(f"  {', '.join(sorted(all_services_used))}")
        else:
            print(f"  (Service-level execution data not captured)")
        
        print(f"\n{'='*80}\n")

if __name__ == "__main__":
    main()
