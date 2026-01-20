#!/usr/bin/env python3
"""
Script to trigger execution of analysis tasks with status CREATED.
Changes status from CREATED -> PENDING so TaskExecutionService picks them up.
"""
import sys

# Add src to path for imports
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.extensions import db
from collections import defaultdict

def main():
    """Main execution function."""
    import argparse
    parser = argparse.ArgumentParser(description='Trigger execution of pending analysis tasks')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        # Get all main tasks with CREATED status
        main_tasks = AnalysisTask.query.filter_by(
            is_main_task=True,
            status=AnalysisStatus.CREATED
        ).order_by(AnalysisTask.target_model, AnalysisTask.target_app_number).all()

        if not main_tasks:
            print("No main tasks found with status=CREATED")
            return 0

        print(f"Found {len(main_tasks)} main tasks with status=CREATED")
        print("=" * 80)

        # Group by model for reporting
        by_model = defaultdict(list)
        for task in main_tasks:
            by_model[task.target_model].append(task)

        print("\nTasks to trigger:")
        for model in sorted(by_model.keys()):
            tasks_list = by_model[model]
            print(f"\n{model}: {len(tasks_list)} tasks")
            for task in sorted(tasks_list, key=lambda x: x.target_app_number):
                # Count subtasks
                subtask_count = AnalysisTask.query.filter_by(
                    parent_task_id=task.task_id,
                    is_main_task=False
                ).count()
                print(f"  app{task.target_app_number}: task_id={task.task_id}, subtasks={subtask_count}")

        print("\n" + "=" * 80)

        if not args.yes:
            response = input(f"\nTrigger {len(main_tasks)} analysis tasks? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return 0
        else:
            print(f"\nProceeding to trigger {len(main_tasks)} tasks (--yes flag provided)")

        # Change status from CREATED to PENDING
        print("\nTriggering tasks...")
        print("=" * 80)

        triggered_count = 0
        failed_count = 0

        for task in main_tasks:
            try:
                # Change status to PENDING - TaskExecutionService will pick it up
                task.status = AnalysisStatus.PENDING
                db.session.commit()

                triggered_count += 1
                print(f"✓ Triggered {task.target_model}/app{task.target_app_number} (task={task.task_id})")
            except Exception as e:
                failed_count += 1
                print(f"✗ Failed to trigger {task.target_model}/app{task.target_app_number}: {e}")
                db.session.rollback()

        print("\n" + "=" * 80)
        print(f"\nSuccessfully triggered: {triggered_count}/{len(main_tasks)} tasks")
        if failed_count > 0:
            print(f"Failed to trigger: {failed_count} tasks")

        print("\nTasks have been set to PENDING status.")
        print("The TaskExecutionService or Celery workers will pick them up automatically.")
        print("\nMonitor progress via:")
        print("  - Web UI: http://localhost:5000/analysis")
        print("  - Celery logs: docker compose logs -f celery-worker")
        print("  - Database: Query analysis_tasks table for status updates")

        return 0

if __name__ == '__main__':
    sys.exit(main())
