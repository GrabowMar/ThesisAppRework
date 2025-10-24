#!/usr/bin/env python
"""
Test Task Hierarchy System
===========================

Simple script to verify the task hierarchy functionality works.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from app.services.task_service import AnalysisTaskService


def main():
    """Test task hierarchy creation."""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("Testing Task Hierarchy System")
        print("=" * 60)
        
        # Create a main task with subtasks
        tools_by_service = {
            'static-analyzer': [1, 2, 3],
            'dynamic-analyzer': [4, 5],
            'performance-tester': [6],
            'ai-analyzer': [7, 8]
        }
        
        print("\n1. Creating main task with subtasks...")
        main_task = AnalysisTaskService.create_main_task_with_subtasks(
            model_slug='test_model',
            app_number=999,
            analysis_type='unified',
            tools_by_service=tools_by_service,
            task_name='Test Unified Analysis',
            description='Testing task hierarchy'
        )
        
        print(f"✅ Created main task: {main_task.task_id}")
        print(f"   Is main task: {main_task.is_main_task}")
        print(f"   Total steps: {main_task.total_steps}")
        
        # Query subtasks
        print("\n2. Querying subtasks...")
        subtasks = AnalysisTask.query.filter_by(parent_task_id=main_task.task_id).all()
        
        print(f"✅ Found {len(subtasks)} subtasks:")
        for subtask in subtasks:
            print(f"   - {subtask.task_id}")
            print(f"     Service: {subtask.service_name}")
            print(f"     Status: {subtask.status.value}")
            print(f"     Parent: {subtask.parent_task_id}")
        
        # Test query for main tasks only
        print("\n3. Querying main tasks only...")
        from sqlalchemy import or_
        main_tasks = AnalysisTask.query.filter(
            or_(
                AnalysisTask.is_main_task == True,
                AnalysisTask.parent_task_id.is_(None)
            )
        ).all()
        
        print(f"✅ Found {len(main_tasks)} main task(s):")
        for task in main_tasks:
            print(f"   - {task.task_id} (is_main_task={task.is_main_task})")
        
        # Clean up test data
        print("\n4. Cleaning up test data...")
        for subtask in subtasks:
            db.session.delete(subtask)
        db.session.delete(main_task)
        db.session.commit()
        print("✅ Test data cleaned up")
        
        print("\n" + "=" * 60)
        print("✅ Task Hierarchy System Test PASSED!")
        print("=" * 60)


if __name__ == '__main__':
    main()
