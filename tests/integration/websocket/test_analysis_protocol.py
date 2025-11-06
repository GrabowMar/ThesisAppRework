import pytest

pytestmark = [pytest.mark.integration, pytest.mark.websocket]

"""Test WebSocket-based analysis by creating a task programmatically."""

import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.models import AnalysisTask, GeneratedApplication, AnalyzerConfiguration
from app.constants import AnalysisStatus
from app.extensions import db
from datetime import datetime, timezone
import uuid

def main():
    app = create_app()
    
    with app.app_context():
        # Find a test app
        test_app = GeneratedApplication.query.filter_by(
            model_slug='openai_gpt-4.1-2025-04-14',
            app_number=1
        ).first()
        
        if not test_app:
            print("ERROR: No test app found for openai_gpt-4.1-2025-04-14/app1")
            print("Creating one...")
            test_app = GeneratedApplication(
                model_slug='openai_gpt-4.1-2025-04-14',
                app_number=1,
                template_slug='crud_todo_list',
                status='completed',
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(test_app)
            db.session.commit()
            print(f"Created GeneratedApplication: {test_app.id}")
        
        # Ensure we have an analyzer config
        config = AnalyzerConfiguration.query.filter_by(is_default=True).first()
        if not config:
            print("Creating default analyzer configuration...")
            config = AnalyzerConfiguration(
                name='default',
                description='Default analyzer configuration',
                config_data='{}',
                is_default=True,
                is_active=True
            )
            db.session.add(config)
            db.session.commit()
        
        # Create a new unified analysis task
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = AnalysisTask(
            task_id=task_id,
            target_model='openai_gpt-4.1-2025-04-14',
            target_app_number=1,
            task_name='unified',
            status=AnalysisStatus.PENDING,
            analyzer_config_id=config.id,
            is_main_task=True,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(task)
        db.session.commit()
        
        print(f"\n✅ Created analysis task:")
        print(f"   Task ID: {task.task_id}")
        print(f"   Model: {task.target_model}")
        print(f"   App: {task.target_app_number}")
        print(f"   Type: {task.task_name}")
        print(f"   Status: {task.status}")
        print(f"\n📋 Task will be picked up by TaskExecutionService within 5 seconds...")
        print(f"   Monitor Flask logs for WebSocket connection attempts to ports 2001-2004")
        print(f"\n   Check task status with:")
        print(f"   python -c \"from app.factory import create_app; from app.models import AnalysisTask; app=create_app(); ctx=app.app_context(); ctx.push(); t=AnalysisTask.query.filter_by(task_id='{task_id}').first(); print(f'Status: {{t.status}}'); ctx.pop()\"")

if __name__ == '__main__':
    main()
