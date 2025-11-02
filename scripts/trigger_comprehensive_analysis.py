"""Trigger comprehensive analyses testing all tools across all analyzer services."""
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
        # Get first 4 apps for testing
        apps = GeneratedApplication.query.order_by(
            GeneratedApplication.model_slug,
            GeneratedApplication.app_number
        ).limit(4).all()
        
        if not apps:
            print("No apps found in database!")
            return
        
        print(f"\nCreating comprehensive analysis tasks testing ALL tools:\n")
        
        # Comprehensive tool sets per analyzer service
        tool_sets = [
            # Static Analysis - All available linters/scanners
            {
                'name': 'Static: All Python Security',
                'tools': ['bandit', 'safety', 'semgrep']
            },
            {
                'name': 'Static: All Python Quality',
                'tools': ['pylint', 'flake8', 'mypy', 'ruff']
            },
            {
                'name': 'Static: All JavaScript/Frontend',
                'tools': ['eslint', 'jshint', 'stylelint']
            },
            {
                'name': 'Static: Comprehensive Mixed',
                'tools': ['bandit', 'safety', 'pylint', 'mypy', 'eslint', 'semgrep']
            },
            # Dynamic Analysis - Security testing
            {
                'name': 'Dynamic: Security Testing',
                'tools': ['zap', 'nmap']
            },
            {
                'name': 'Dynamic: Full Security Scan',
                'tools': ['zap', 'nmap', 'nikto']
            },
            # Performance Testing - Load testing
            {
                'name': 'Performance: Load Testing',
                'tools': ['ab', 'locust']
            },
            {
                'name': 'Performance: Comprehensive',
                'tools': ['ab', 'locust', 'wrk']
            },
            # AI Analysis - OpenRouter-backed analysis
            {
                'name': 'AI: Code Quality Analysis',
                'tools': ['openrouter']
            },
            # Multi-service comprehensive
            {
                'name': 'Multi-Service: Full Stack',
                'tools': ['bandit', 'safety', 'pylint', 'eslint', 'zap', 'ab', 'openrouter']
            },
        ]
        
        created_tasks = []
        
        for idx, app in enumerate(apps):
            # Cycle through tool sets
            tool_set = tool_sets[idx % len(tool_sets)]
            tools = tool_set['tools']
            
            try:
                # Create task (will be picked up by daemon)
                task = AnalysisTaskService.create_task(
                    model_slug=app.model_slug,
                    app_number=app.app_number,
                    tools=tools,
                    priority=Priority.HIGH.value,
                    custom_options={
                        'selected_tool_names': tools,
                        'source': 'comprehensive_test',
                        'description': tool_set['name']
                    }
                )
                
                created_tasks.append(task)
                print(f"✓ Created task {task.task_id}")
                print(f"  Type: {tool_set['name']}")
                print(f"  Model: {app.model_slug}")
                print(f"  App: {app.app_number}")
                print(f"  Tools ({len(tools)}): {', '.join(tools)}")
                print()
                
            except Exception as e:
                print(f"✗ Failed to create task for {app.model_slug} app{app.app_number}: {e}")
                print()
        
        print(f"\n{'='*80}")
        print(f"Summary: Created {len(created_tasks)} comprehensive analysis tasks")
        print(f"\nTask breakdown by analyzer service:")
        print(f"  Static analysis: 4 tasks (security, quality, frontend, mixed)")
        print(f"  Dynamic analysis: 2 tasks (security testing)")
        print(f"  Performance testing: 2 tasks (load testing)")
        print(f"  AI analysis: 1 task (code quality)")
        print(f"  Multi-service: 1 task (full stack)")
        print(f"\nTask IDs:")
        for task in created_tasks:
            print(f"  - {task.task_id}")
        print(f"\nThese tasks will be processed automatically by the daemon thread.")
        print(f"Monitor progress with:")
        print(f"  Get-Content logs/app.log -Tail 200 | Select-String -Pattern 'Task.*started|Task.*completed|\\[POLL\\]|\\[QUEUE\\]'")
        print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
