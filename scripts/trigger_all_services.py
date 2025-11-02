"""Trigger tasks for dynamic, performance, and AI analyzers."""
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
        apps = GeneratedApplication.query.order_by(
            GeneratedApplication.model_slug,
            GeneratedApplication.app_number
        ).limit(6).all()
        
        if not apps:
            print("No apps found!")
            return
        
        # Test cases for each analyzer service
        test_cases = [
            ('Dynamic: Security Testing', ['zap', 'nmap']),
            ('Dynamic: Full Security Scan', ['zap', 'nmap', 'nikto']),
            ('Performance: Load Testing', ['ab', 'locust']),
            ('Performance: Comprehensive', ['ab', 'locust', 'wrk']),
            ('AI: Code Quality', ['openrouter']),
            ('Multi-Service: Full Stack', ['bandit', 'pylint', 'eslint', 'zap', 'ab', 'openrouter']),
        ]
        
        print("\nCreating tasks for dynamic, performance, AI, and multi-service analysis:\n")
        
        tasks = []
        for idx, (name, tools) in enumerate(test_cases):
            app_obj = apps[idx % len(apps)]
            
            try:
                task = AnalysisTaskService.create_task(
                    model_slug=app_obj.model_slug,
                    app_number=app_obj.app_number,
                    tools=tools,
                    priority=Priority.HIGH.value,
                    custom_options={
                        'selected_tool_names': tools,
                        'source': 'comprehensive_test',
                        'description': name
                    }
                )
                
                tasks.append(task)
                print(f"✓ {task.task_id}: {name}")
                print(f"  Tools ({len(tools)}): {', '.join(tools)}")
                print(f"  Target: {app_obj.model_slug} app{app_obj.app_number}")
                print()
                
            except Exception as e:
                print(f"✗ Failed: {name} - {e}\n")
        
        print(f"{'='*80}")
        print(f"Created {len(tasks)} tasks for all analyzer services")
        print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
