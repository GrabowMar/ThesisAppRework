import pytest

pytestmark = [pytest.mark.integration, pytest.mark.analyzer]

"""Test unified analysis with WebSocket communication."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.factory import create_app
from app.services.task_service import AnalysisTaskService

def main():
    app = create_app()
    
    with app.app_context():
        print("Creating unified task with subtasks...")
        task = AnalysisTaskService.create_main_task_with_subtasks(
            model_slug='openai_gpt-4.1-2025-04-14',
            app_number=1,
            tools=['bandit', 'safety', 'eslint'],
            task_name='unified_websocket_test'
        )
        
        print(f"\n✓ Created unified task: {task.task_id}")
        print(f"  Main task: {task.is_main_task}")
        print(f"  Status: {task.status}")
        print(f"  Subtasks: {len(list(task.subtasks))}")
        
        for subtask in task.subtasks:
            print(f"    - {subtask.service_name}: {subtask.task_id}")
        
        print("\nTaskExecutionService will pick it up within 5 seconds.")
        print("Watch Flask console for [SUBTASK], [WebSocket], [AGGREGATE] logs.")

if __name__ == "__main__":
    main()
