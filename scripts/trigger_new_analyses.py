"""Trigger new analyses for testing the improved daemon system."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.services.task_service import AnalysisTaskService
from app.models import GeneratedApplication
from app.constants import JobPriority as Priority

def main():
    app = create_app()
    with app.app_context():
        # Get first 6 apps for testing
        apps = GeneratedApplication.query.order_by(
            GeneratedApplication.model_slug,
            GeneratedApplication.app_number
        ).limit(6).all()
        
        if not apps:
            print("No apps found in database!")
            return
        
        print(f"\nCreating analysis tasks for {len(apps)} applications:\n")
        
        # Create tasks with different tool combinations
        tool_sets = [
            ['bandit', 'safety'],           # Security focused
            ['pylint', 'eslint'],           # Code quality
            ['mypy', 'ruff'],               # Type checking + linting
            ['bandit', 'pylint', 'mypy'],   # Multi-tool
            ['eslint', 'stylelint'],        # Frontend
            ['bandit', 'safety', 'pylint']  # Comprehensive
        ]
        
        created_tasks = []
        
        for idx, app in enumerate(apps):
            tools = tool_sets[idx % len(tool_sets)]
            
            try:
                # Create task (will be picked up by daemon)
                task = AnalysisTaskService.create_task(
                    model_slug=app.model_slug,
                    app_number=app.app_number,
                    tools=tools,
                    priority=Priority.NORMAL.value,
                    custom_options={
                        'selected_tool_names': tools,
                        'source': 'test_script',
                        'description': f'Fresh analysis test {idx+1}'
                    }
                )
                
                created_tasks.append(task)
                print(f"✓ Created task {task.task_id}")
                print(f"  Model: {app.model_slug}")
                print(f"  App: {app.app_number}")
                print(f"  Tools: {', '.join(tools)}")
                print()
                
            except Exception as e:
                print(f"✗ Failed to create task for {app.model_slug} app{app.app_number}: {e}")
                print()
        
        print(f"\n{'='*80}")
        print(f"Summary: Created {len(created_tasks)} analysis tasks")
        print(f"Task IDs: {', '.join([t.task_id for t in created_tasks])}")
        print(f"\nThese tasks will be processed automatically by the daemon thread.")
        print(f"Monitor logs with: Get-Content logs/app.log | Select-String -Pattern 'Task.*started|Task.*completed'")
        print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
