"""Force execute all PENDING tasks directly (bypass daemon thread)."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus

def main():
    app = create_app()
    with app.app_context():
        # Find all PENDING tasks
        pending_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).all()
        
        if not pending_tasks:
            print("No PENDING tasks found")
            return
        
        print(f"Found {len(pending_tasks)} PENDING tasks")
        
        for task in pending_tasks:
            print(f"\nProcessing task {task.task_id}:")
            print(f"  Model: {task.target_model}")
            print(f"  App: {task.target_app_number}")
            print(f"  Type: {task.task_name}")
            
            # Get metadata to see tools
            metadata = task.get_metadata() if hasattr(task, 'get_metadata') else {}
            custom_options = metadata.get('custom_options', {})
            tools = custom_options.get('tool_names', custom_options.get('selected_tools', []))
            print(f"  Tools: {tools}")
            
            # Execute directly using task execution service logic
            from app.services.task_execution_service import TaskExecutionService
            from app.extensions import db
            from datetime import datetime, timezone
            
            try:
                # Mark as RUNNING
                task.status = AnalysisStatus.RUNNING
                task.started_at = datetime.now(timezone.utc)
                db.session.commit()
                
                print(f"  Status: RUNNING")
                
                # Create a temporary task execution service instance
                executor = TaskExecutionService(app=app)
                
                # Execute the analysis
                result = executor._execute_real_analysis(task)
                
                success = result.get('status') in ('success', 'completed')
                
                # Update task status
                task.status = AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED
                task.completed_at = datetime.now(timezone.utc)
                task.progress_percentage = 100.0
                
                if task.started_at and task.completed_at:
                    start = task.started_at if task.started_at.tzinfo else task.started_at.replace(tzinfo=timezone.utc)
                    end = task.completed_at if task.completed_at.tzinfo else task.completed_at.replace(tzinfo=timezone.utc)
                    task.actual_duration = (end - start).total_seconds()
                
                # Save result payload
                if result.get('payload'):
                    task.set_result_summary(result['payload'])
                
                if result.get('error'):
                    task.error_message = result['error']
                
                db.session.commit()
                
                print(f"  Status: {task.status.value}")
                print(f"  Duration: {task.actual_duration:.1f}s" if task.actual_duration else "  Duration: N/A")
                if result.get('error'):
                    print(f"  Error: {result['error']}")
                
            except Exception as e:
                print(f"  ERROR: {e}")
                task.status = AnalysisStatus.FAILED
                task.error_message = str(e)
                db.session.commit()

if __name__ == "__main__":
    main()
