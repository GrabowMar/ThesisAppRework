import pytest

pytestmark = [pytest.mark.integration, pytest.mark.websocket]

"""Test WebSocket-based unified analysis by creating a proper task with subtasks."""

import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.services.task_service import AnalysisTaskService

def main():
    app = create_app()
    
    with app.app_context():
        print("\n📋 Creating unified analysis task...")
        print("   Model: openai_gpt-4.1-2025-04-14")
        print("   App: 1")
        print("   This will create a main task + subtasks for each analyzer service")
        print()
        
        # Select tools from multiple services
        tools = ['bandit', 'safety', 'pylint', 'zap']  # Static + dynamic tools
        
        print(f"   Selected tools: {tools}")
        print()
        
        main_task = AnalysisTaskService.create_main_task_with_subtasks(
            model_slug='openai_gpt-4.1-2025-04-14',
            app_number=1,
            tools=tools,
            config_id=None,  # Use default
            custom_options={}
        )
        
        print(f"✅ Created unified analysis task:")
        print(f"   Main Task ID: {main_task.task_id}")
        print(f"   Subtasks: {len(main_task.subtasks)}")
        for subtask in main_task.subtasks:
            print(f"      - {subtask.task_id}: service={subtask.service_name}, status={subtask.status}")
        print()
        print("📋 Subtasks will be executed in parallel using WebSocket connections")
        print("   Monitor Flask logs for [WebSocket] messages on ports 2001-2004")
        print()
        print(f"   Check task status with:")
        print(f"   python -c \"from app.factory import create_app; from app.models import AnalysisTask; app=create_app(); ctx=app.app_context(); ctx.push(); t=AnalysisTask.query.filter_by(task_id='{main_task.task_id}').first(); print(f'Main task: {{t.status}}'); [print(f'  Sub {{st.service_name}}: {{st.status}}') for st in t.subtasks]; ctx.pop()\"")

if __name__ == '__main__':
    main()
