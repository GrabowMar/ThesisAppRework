#!/usr/bin/env python3
"""Re-aggregate ALL completed analysis tasks."""
import sys
sys.path.insert(0, 'src')

from app import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.services.task_execution_service import TaskExecutionService
from app.extensions import db

app = create_app()
with app.app_context():
    task_service = TaskExecutionService()
    
    # Get all completed tasks
    completed_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.COMPLETED).all()
    
    print(f"Found {len(completed_tasks)} completed tasks to re-aggregate\n")
    
    success_count = 0
    for i, task in enumerate(completed_tasks, 1):
        print(f"[{i}/{len(completed_tasks)}] Processing {task.task_id}...")
        
        try:
            result_summary = task.get_result_summary()
            if not result_summary:
                print(f"  ⚠️  No result_summary, skipping")
                continue
            
            services_block = result_summary.get('services', {})
            if not services_block:
                print(f"  ⚠️  No services found, skipping")
                continue
            
            # Extract tool results from each service payload
            all_tool_results = {}
            for service_name, service_data in services_block.items():
                payload = service_data.get('payload', {})
                tools = task_service._extract_tool_results_from_payload(service_name, payload)
                all_tool_results.update(tools)
            
            if not all_tool_results:
                print(f"  ⚠️  No tools extracted, skipping")
                continue
            
            # Update the result_summary
            result_summary['tool_results'] = all_tool_results
            result_summary['tools'] = all_tool_results
            
            # Update summary metrics
            if 'summary' not in result_summary:
                result_summary['summary'] = {}
            result_summary['summary']['tools_executed'] = len([t for t in all_tool_results.values() if t.get('executed')])
            result_summary['summary']['tools_used'] = list(all_tool_results.keys())
            
            # Save back to database
            task.set_result_summary(result_summary)
            
            print(f"  ✅ Extracted {len(all_tool_results)} tools: {', '.join(list(all_tool_results.keys())[:5])}...")
            success_count += 1
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    # Commit all changes at once
    db.session.commit()
    
    print(f"\n{'='*60}")
    print(f"✅ Successfully re-aggregated {success_count}/{len(completed_tasks)} tasks")
    print(f"{'='*60}")
