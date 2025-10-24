#!/usr/bin/env python
"""
Test Task Hierarchy System
===========================

This script demonstrates the new task hierarchy system.
Run this after starting the Flask app to test creating main tasks with subtasks.

Usage:
    python scripts/test_task_hierarchy.py
"""

import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.services.task_service import TaskService
from app.constants import AnalysisStatus


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_task(task, indent=0):
    """Print task details with indentation."""
    prefix = "  " * indent
    status_icon = {
        AnalysisStatus.PENDING: "⏳",
        AnalysisStatus.RUNNING: "▶️",
        AnalysisStatus.COMPLETED: "✅",
        AnalysisStatus.FAILED: "❌"
    }.get(task.status, "❓")
    
    print(f"{prefix}{status_icon} {task.task_id[:20]}... - {task.analysis_type}")
    if task.service_name:
        print(f"{prefix}   Service: {task.service_name}")
    print(f"{prefix}   Status: {task.status.value}")
    print(f"{prefix}   Main Task: {task.is_main_task}")


def main():
    """Test the task hierarchy system."""
    app = create_app()
    
    with app.app_context():
        task_service = TaskService()
        
        print_section("Creating Main Task with Subtasks")
        
        # Example: Create a unified analysis task
        model_name = "openai_gpt-4"
        app_number = 1
        analysis_type = "unified"
        
        # Define which tools to use for each service
        tools_by_service = {
            'static-analyzer': ['bandit', 'eslint'],
            'dynamic-analyzer': ['zap'],
            'performance-tester': ['locust'],
            'ai-analyzer': ['openrouter']
        }
        
        print(f"\nCreating unified analysis task:")
        print(f"  Model: {model_name}")
        print(f"  App: {app_number}")
        print(f"  Services: {', '.join(tools_by_service.keys())}")
        
        # Create main task with subtasks
        main_task = task_service.create_main_task_with_subtasks(
            model_name=model_name,
            app_number=app_number,
            analysis_type=analysis_type,
            tools_by_service=tools_by_service,
            metadata={
                'unified_analysis': True,
                'selected_tools': list(set(
                    tool for tools in tools_by_service.values() 
                    for tool in tools
                ))
            }
        )
        
        print(f"\n✅ Main task created: {main_task.task_id}")
        print(f"   Subtasks created: {len(main_task.subtasks)}")
        
        print_section("Task Hierarchy Structure")
        
        # Display main task
        print_task(main_task)
        
        # Display subtasks
        print("\nSubtasks:")
        for subtask in main_task.subtasks:
            print_task(subtask, indent=1)
        
        print_section("Testing Task Retrieval")
        
        # Test getting main tasks only
        main_tasks = task_service.get_main_tasks(limit=10)
        print(f"\nFound {len(main_tasks)} main task(s)")
        
        for task in main_tasks:
            print_task(task)
            if task.subtasks:
                print(f"  └─ Has {len(task.subtasks)} subtask(s)")
        
        print_section("Task List for UI Display")
        
        # This simulates what the API endpoint returns
        print("\nMain tasks (what UI will show):")
        for task in main_tasks:
            print(f"\n📋 {task.task_id[:20]}... ({task.analysis_type})")
            print(f"   Model: {model_name} | App: {app_number}")
            print(f"   Status: {task.status.value}")
            print(f"   Subtasks: {len(task.subtasks)}")
            
            for subtask in task.subtasks:
                service = subtask.service_name or 'unknown'
                print(f"     ├─ {service}: {subtask.status.value}")
        
        print_section("Summary")
        print("""
✅ Task Hierarchy Implementation Complete!

What was implemented:
1. AnalysisTask model now supports parent-child relationships
2. TaskService creates main tasks with subtasks for unified analysis
3. Each analyzer service gets its own subtask
4. UI will show main tasks with expandable subtask rows
5. Progress tracking per service/subtask

Next steps:
1. Start the Flask app: python src/main.py
2. Navigate to /analysis page
3. Click "Launch Analysis" with multiple services selected
4. See the main task with expandable subtasks in the table
5. Watch real-time progress updates as each service completes

The table will now show:
- One main task row (with expand/collapse icon)
- Subtask rows indented underneath
- Individual status/progress for each analyzer service
""")
        
        print("=" * 60)


if __name__ == '__main__':
    main()
