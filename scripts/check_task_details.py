"""Check detailed task information including metadata and subtasks."""
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from app.factory import create_app
from app.models import AnalysisTask
from sqlalchemy import desc
import json

app = create_app()

with app.app_context():
    # Get last 5 tasks ordered by completion time
    tasks = AnalysisTask.query.order_by(desc(AnalysisTask.completed_at)).limit(5).all()
    
    print("=" * 80)
    print("DETAILED TASK INFORMATION")
    print("=" * 80)
    print()
    
    for task in tasks:
        print(f"Task ID: {task.task_id}")
        print(f"  Status: {task.status.value if task.status else 'None'}")
        print(f"  Task Name: {task.task_name}")
        print(f"  Is Main Task: {task.is_main_task}")
        print(f"  Parent Task: {task.parent_task_id or 'None'}")
        print(f"  Service Name: {task.service_name or 'None'}")
        print(f"  Started: {task.started_at}")
        print(f"  Completed: {task.completed_at}")
        print(f"  Duration: {task.actual_duration}s" if task.actual_duration else "  Duration: None")
        
        # Check for subtasks
        subtasks = AnalysisTask.query.filter_by(parent_task_id=task.task_id).all()
        if subtasks:
            print(f"  Subtasks: {len(subtasks)}")
            for st in subtasks:
                print(f"    - {st.task_id} ({st.service_name}): {st.status.value if st.status else 'None'}")
        else:
            print("  Subtasks: None")
        
        # Get metadata
        try:
            metadata = task.get_metadata() if hasattr(task, 'get_metadata') else {}
            if metadata:
                print("  Metadata keys:", list(metadata.keys()))
                
                # Check for unified analysis flag
                unified = metadata.get('unified_analysis') or metadata.get('custom_options', {}).get('unified_analysis')
                if unified:
                    print("    unified_analysis: True")
                
                # Check for tools
                selected_tools = metadata.get('selected_tools') or metadata.get('custom_options', {}).get('selected_tools')
                if selected_tools:
                    print(f"    selected_tools: {selected_tools}")
                
                tools_by_service = metadata.get('tools_by_service') or metadata.get('custom_options', {}).get('tools_by_service')
                if tools_by_service:
                    print(f"    tools_by_service: {list(tools_by_service.keys()) if isinstance(tools_by_service, dict) else tools_by_service}")
            else:
                print("  Metadata: Empty")
        except Exception as e:
            print(f"  Metadata error: {e}")
        
        # Get result summary
        try:
            result_summary = task.get_result_summary() if hasattr(task, 'get_result_summary') else {}
            if result_summary:
                print("  Result Summary keys:", list(result_summary.keys()))
                
                # Check status
                status = result_summary.get('status')
                if status:
                    print(f"    status: {status}")
                
                # Check for error
                error = result_summary.get('error')
                if error:
                    print(f"    error: {error}")
                    
                # Check for findings
                findings = result_summary.get('findings', [])
                if isinstance(findings, list):
                    print(f"    findings count: {len(findings)}")
                    
                # Check for summary
                summary = result_summary.get('summary', {})
                if summary:
                    print(f"    summary.total_findings: {summary.get('total_findings', 0)}")
            else:
                print("  Result Summary: Empty")
        except Exception as e:
            print(f"  Result Summary error: {e}")
        
        print()
