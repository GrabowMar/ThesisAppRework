#!/usr/bin/env python3
"""
Script to fix metadata for tasks that should use unified analysis with subtasks.
"""
import sys
import json

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
    parser = argparse.ArgumentParser(description='Fix metadata for tasks to use unified analysis')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        # Get all main tasks with RUNNING or PENDING status that have subtasks
        tasks = AnalysisTask.query.filter(
            AnalysisTask.is_main_task == True,
            AnalysisTask.status.in_([AnalysisStatus.RUNNING, AnalysisStatus.PENDING])
        ).all()

        tasks_to_fix = []
        for task in tasks:
            # Check if it has subtasks
            subtask_count = AnalysisTask.query.filter_by(
                parent_task_id=task.task_id,
                is_main_task=False
            ).count()

            if subtask_count > 0:
                # Check metadata
                meta = task.get_metadata()
                custom_options = meta.get('custom_options', {})
                if not custom_options.get('unified_analysis', False):
                    tasks_to_fix.append(task)

        if not tasks_to_fix:
            print("No tasks need fixing!")
            return 0

        print(f"Found {len(tasks_to_fix)} tasks that need unified_analysis flag")
        print("=" * 80)

        # Group by model
        by_model = defaultdict(list)
        for task in tasks_to_fix:
            by_model[task.target_model].append(task)

        print("\nTasks to fix:")
        for model in sorted(by_model.keys()):
            tasks_list = by_model[model]
            print(f"\n{model}: {len(tasks_list)} tasks")
            for task in sorted(tasks_list, key=lambda x: x.target_app_number):
                subtask_count = AnalysisTask.query.filter_by(
                    parent_task_id=task.task_id,
                    is_main_task=False
                ).count()
                print(f"  app{task.target_app_number}: {task.task_id} [{task.status.value}] ({subtask_count} subtasks)")

        print("\n" + "=" * 80)

        if not args.yes:
            response = input(f"\nFix metadata for {len(tasks_to_fix)} tasks and restart them? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return 0
        else:
            print(f"\nProceeding to fix {len(tasks_to_fix)} tasks (--yes flag provided)")

        # Fix metadata and reset to PENDING
        print("\nFixing tasks...")
        print("=" * 80)

        fixed_count = 0
        for task in tasks_to_fix:
            try:
                # Get current metadata
                meta = task.get_metadata()
                custom_options = meta.get('custom_options', {})

                # Set unified_analysis flag
                custom_options['unified_analysis'] = True
                meta['custom_options'] = custom_options

                # Update metadata
                task.set_metadata(meta)

                # Reset to PENDING so it gets picked up again
                if task.status == AnalysisStatus.RUNNING:
                    task.status = AnalysisStatus.PENDING
                    task.progress_percentage = 0.0
                    task.started_at = None

                db.session.commit()
                fixed_count += 1
                print(f"✓ Fixed {task.target_model}/app{task.target_app_number} (task={task.task_id})")
            except Exception as e:
                print(f"✗ Failed to fix {task.target_model}/app{task.target_app_number}: {e}")
                db.session.rollback()

        print("\n" + "=" * 80)
        print(f"\nSuccessfully fixed: {fixed_count}/{len(tasks_to_fix)} tasks")
        print("\nTasks have been set to PENDING with unified_analysis flag.")
        print("TaskExecutionService will pick them up and execute via subtasks.")

        return 0

if __name__ == '__main__':
    sys.exit(main())
