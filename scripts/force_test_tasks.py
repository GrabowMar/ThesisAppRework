"""Force execute specific test tasks."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus

# Our three test task IDs
TEST_TASK_IDS = [
    'task_7ec2bff376c0',  # anthropic_claude-4.5-sonnet-20250929 app1 (bandit+safety)
    'task_29eb8f6bb3f3',  # anthropic_claude-4.5-sonnet-20250929 app2 (pylint+eslint)
    'task_9250a69f3c03',  # anthropic_claude-4.5-haiku-20251001 app1 (mypy+ruff)
]

def main():
    app = create_app()
    with app.app_context():
        from app.services.task_execution_service import TaskExecutionService
        from app.extensions import db
        from datetime import datetime, timezone
        
        print(f"Forcing execution of {len(TEST_TASK_IDS)} test tasks...\n")
        
        for task_id in TEST_TASK_IDS:
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            
            if not task:
                print(f"❌ Task {task_id} not found")
                continue
            
            print(f"\n{'='*80}")
            print(f"Processing task {task.task_id}:")
            print(f"  Model: {task.target_model}")
            print(f"  App: {task.target_app_number}")
            print(f"  Current Status: {task.status.value}")
            
            # Get metadata to see tools
            metadata = task.get_metadata() if hasattr(task, 'get_metadata') else {}
            custom_options = metadata.get('custom_options', {})
            tools = custom_options.get('tool_names', custom_options.get('selected_tools', []))
            print(f"  Tools: {tools}")
            
            if task.status != AnalysisStatus.PENDING:
                print(f"  ⚠️  Task is not PENDING, skipping")
                continue
            
            try:
                # Mark as RUNNING
                task.status = AnalysisStatus.RUNNING
                task.started_at = datetime.now(timezone.utc)
                db.session.commit()
                
                print(f"  ▶️  Status: RUNNING")
                
                # Create a temporary task execution service instance
                executor = TaskExecutionService(app=app)
                
                # Execute the analysis
                print(f"  🔧 Executing analysis...")
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
                    payload = result['payload']
                    if isinstance(payload, dict):
                        summary = payload.get('summary', {})
                        total_findings = summary.get('total_findings', 0)
                        tools_executed = summary.get('tools_executed', 0)
                        print(f"  📊 Results: {total_findings} findings from {tools_executed} tools")
                
                if result.get('error'):
                    task.error_message = result['error']
                
                db.session.commit()
                
                status_icon = "✅" if success else "❌"
                print(f"  {status_icon} Final Status: {task.status.value}")
                print(f"  ⏱️  Duration: {task.actual_duration:.1f}s" if task.actual_duration else "  ⏱️  Duration: N/A")
                
                if result.get('error'):
                    print(f"  ⚠️  Error: {result['error']}")
                
            except Exception as e:
                print(f"  ❌ ERROR: {e}")
                import traceback
                traceback.print_exc()
                task.status = AnalysisStatus.FAILED
                task.error_message = str(e)
                task.completed_at = datetime.now(timezone.utc)
                db.session.commit()
        
        print(f"\n{'='*80}")
        print("\n✅ All test tasks processed!")

if __name__ == "__main__":
    main()
