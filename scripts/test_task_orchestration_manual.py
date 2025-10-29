"""
Manual Test Script for Task Orchestration
==========================================

Quick script to test task creation and verify Celery dispatch works.
Run this with Flask app and Celery worker running.

Prerequisites:
1. Flask app running: cd src && python main.py
2. Celery worker running: cd src && celery -A app.tasks worker --loglevel=info --pool=solo
3. Test model/app exists (or use dummy data)

Usage:
    python scripts/test_task_orchestration_manual.py
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from app.factory import create_app
from app.services.task_service import AnalysisTaskService
from app.extensions import db
from app.models import AnalysisTask
from app.constants import AnalysisStatus
import time


def print_section(title):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def test_single_task():
    """Test single task creation and dispatch."""
    print_section("TEST 1: Single Task Creation")
    
    task = AnalysisTaskService.create_task(
        model_slug="test_model",
        app_number=1,
        tools=["bandit"],
        priority="normal",
        custom_options={'test': 'manual_single_task'},
        dispatch=True  # Actually dispatch to Celery
    )
    
    print(f"✓ Task created: {task.task_id}")
    print(f"  - Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
    print(f"  - Model: {task.target_model}")
    print(f"  - App: {task.target_app_number}")
    print(f"  - Is Main: {task.is_main_task}")
    
    metadata = task.get_metadata()
    tools = metadata.get('custom_options', {}).get('tools', [])
    print(f"  - Tools: {tools}")
    
    return task


def test_multi_service_task():
    """Test multi-service task with subtasks."""
    print_section("TEST 2: Multi-Service Task Creation")
    
    tools = ["bandit", "safety", "eslint"]
    
    task = AnalysisTaskService.create_main_task_with_subtasks(
        model_slug="test_model",
        app_number=2,
        tools=tools,
        priority="high",
        custom_options={'test': 'manual_multi_service_task'}
    )
    
    print(f"✓ Main task created: {task.task_id}")
    print(f"  - Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
    print(f"  - Is Main: {task.is_main_task}")
    print(f"  - Total Steps: {task.total_steps}")
    print(f"  - Completed Steps: {task.completed_steps}")
    
    metadata = task.get_metadata()
    tools_by_service = metadata.get('custom_options', {}).get('tools_by_service', {})
    print(f"  - Tools by service: {tools_by_service}")
    
    # Check subtasks
    db.session.refresh(task)
    subtasks = list(task.subtasks)
    print(f"\n  Subtasks created: {len(subtasks)}")
    
    for idx, subtask in enumerate(subtasks, 1):
        sub_metadata = subtask.get_metadata()
        tool_names = sub_metadata.get('custom_options', {}).get('tool_names', [])
        print(f"    {idx}. {subtask.task_id}")
        print(f"       - Service: {subtask.service_name}")
        print(f"       - Status: {subtask.status.value if hasattr(subtask.status, 'value') else subtask.status}")
        print(f"       - Tools: {tool_names}")
        print(f"       - Has tool_ids? {('tool_ids' in sub_metadata.get('custom_options', {}))}")
    
    return task


def test_mixed_services():
    """Test task with tools from multiple different services."""
    print_section("TEST 3: Mixed Services Task")
    
    from app.engines.container_tool_registry import get_container_tool_registry
    
    registry = get_container_tool_registry()
    all_tools = registry.get_all_tools()
    
    # Get tools from different services
    static_tools = []
    dynamic_tools = []
    perf_tools = []
    
    for tool_name, tool_obj in all_tools.items():
        if tool_obj.available:
            service = tool_obj.container.value if tool_obj.container else None
            if service == 'static-analyzer' and len(static_tools) < 2:
                static_tools.append(tool_name)
            elif service == 'dynamic-analyzer' and len(dynamic_tools) < 1:
                dynamic_tools.append(tool_name)
            elif service == 'performance-tester' and len(perf_tools) < 1:
                perf_tools.append(tool_name)
    
    mixed_tools = static_tools + dynamic_tools + perf_tools
    
    if len(mixed_tools) < 2:
        print("⚠ Skipping - not enough tools from different services available")
        return None
    
    print(f"Testing with mixed tools: {mixed_tools}")
    
    task = AnalysisTaskService.create_main_task_with_subtasks(
        model_slug="test_model",
        app_number=3,
        tools=mixed_tools,
        priority="normal"
    )
    
    print(f"\n✓ Task created: {task.task_id}")
    
    metadata = task.get_metadata()
    tools_by_service = metadata.get('custom_options', {}).get('tools_by_service', {})
    
    print(f"  Tools grouped by service:")
    for service, tools in tools_by_service.items():
        print(f"    - {service}: {tools}")
    
    db.session.refresh(task)
    subtasks = list(task.subtasks)
    print(f"  Subtasks: {len(subtasks)} (one per service)")
    
    return task


def check_task_status(task_id, wait_seconds=5):
    """Check task status after waiting."""
    print_section(f"Checking Status After {wait_seconds}s")
    
    print(f"Waiting {wait_seconds} seconds for Celery worker...")
    time.sleep(wait_seconds)
    
    task = AnalysisTask.query.filter_by(task_id=task_id).first()
    
    if not task:
        print(f"✗ Task {task_id} not found!")
        return
    
    print(f"Task {task_id}:")
    print(f"  - Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
    print(f"  - Progress: {task.progress_percentage}%")
    print(f"  - Error: {task.error_message or 'None'}")
    
    if task.is_main_task:
        print(f"  - Steps: {task.completed_steps}/{task.total_steps}")
        db.session.refresh(task)
        subtasks = list(task.subtasks)
        print(f"\n  Subtask statuses:")
        for subtask in subtasks:
            print(f"    - {subtask.service_name}: {subtask.status.value if hasattr(subtask.status, 'value') else subtask.status}")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  TASK ORCHESTRATION MANUAL TEST")
    print("=" * 60)
    print("\nThis script tests the fixed task orchestration system.")
    print("Make sure Flask and Celery worker are running!")
    print("\nPress Ctrl+C to cancel...\n")
    
    try:
        time.sleep(2)
    except KeyboardInterrupt:
        print("\n\nTest cancelled.\n")
        return
    
    app = create_app('development')
    
    with app.app_context():
        # Test 1: Single task
        task1 = test_single_task()
        
        # Test 2: Multi-service
        task2 = test_multi_service_task()
        
        # Test 3: Mixed services
        task3 = test_mixed_services()
        
        # Check statuses
        if task1:
            check_task_status(task1.task_id)
        
        if task2:
            check_task_status(task2.task_id)
        
        # Summary
        print_section("TEST SUMMARY")
        print("✓ All task creation tests completed successfully!")
        print("\nCheck Celery worker logs to verify dispatch:")
        print("  - Look for 'execute_analysis' or 'run_analyzer_subtask' calls")
        print("  - Verify tasks are processing")
        print("\nCheck Flask app logs:")
        print("  - Look for 'Task dispatched to Celery successfully' messages")
        print("\nIf tasks are stuck in PENDING:")
        print("  - Verify Celery worker is running: ps aux | grep celery")
        print("  - Check Redis connection: redis-cli ping")
        print("  - Review Celery worker logs for errors")


if __name__ == '__main__':
    main()
