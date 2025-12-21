#!/usr/bin/env python3
"""
One-time migration script to add subtasks to existing main tasks that don't have them.

This ensures consistent UI display where all tasks show their subtask breakdown,
regardless of whether they were created with single-service or multi-service tool selections.

Usage:
    python scripts/migrate_tasks_add_subtasks.py [--dry-run]

Options:
    --dry-run    Preview changes without committing to database
"""

import sys
import os
import uuid
import argparse
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from app.constants import AnalysisStatus, JobPriority


def migrate_tasks_add_subtasks(dry_run: bool = False):
    """
    Find main tasks without subtasks and create subtasks for them based on their
    tools_by_service metadata.
    """
    app = create_app()
    
    with app.app_context():
        # Find all main tasks (is_main_task=True) that have no subtasks
        main_tasks_without_subtasks = AnalysisTask.query.filter(
            AnalysisTask.is_main_task == True,  # noqa: E712
        ).all()
        
        # Filter to those with no subtasks
        tasks_to_migrate = []
        for task in main_tasks_without_subtasks:
            subtasks = AnalysisTask.query.filter_by(parent_task_id=task.task_id).all()
            if not subtasks:
                tasks_to_migrate.append(task)
        
        print(f"Found {len(tasks_to_migrate)} main tasks without subtasks")
        
        if not tasks_to_migrate:
            print("No tasks need migration.")
            return
        
        created_subtasks = 0
        skipped_tasks = 0
        
        for task in tasks_to_migrate:
            # Get metadata to find tools_by_service
            metadata = task.get_metadata() if hasattr(task, 'get_metadata') else {}
            custom_options = metadata.get('custom_options', {})
            tools_by_service = custom_options.get('tools_by_service', {})
            
            if not tools_by_service:
                # Try to infer from task_name or other metadata
                # If it starts with a service name like 'static-analyzer:', use that
                task_name = task.task_name or ''
                service_name = None
                
                for svc in ['static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer']:
                    if task_name.startswith(svc):
                        service_name = svc
                        break
                
                if not service_name:
                    # Check if there's a service_name field on the task itself
                    service_name = getattr(task, 'service_name', None)
                
                if not service_name:
                    # Default to static-analyzer as fallback
                    service_name = 'static-analyzer'
                    print(f"  Task {task.task_id}: No tools_by_service found, defaulting to {service_name}")
                
                tools_by_service = {service_name: []}
            
            print(f"\n  Task {task.task_id} ({task.task_name}):")
            print(f"    Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
            print(f"    Services: {list(tools_by_service.keys())}")
            
            if dry_run:
                print(f"    [DRY RUN] Would create {len(tools_by_service)} subtask(s)")
                created_subtasks += len(tools_by_service)
                continue
            
            # Create subtasks for each service
            for service_name, tool_ids in tools_by_service.items():
                subtask_uuid = f"task_{uuid.uuid4().hex[:12]}"
                
                subtask = AnalysisTask()
                subtask.task_id = subtask_uuid
                subtask.parent_task_id = task.task_id
                subtask.is_main_task = False
                subtask.service_name = service_name
                subtask.analyzer_config_id = task.analyzer_config_id
                
                # Mirror parent task status for completed/failed tasks
                if task.status in [AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL_SUCCESS]:
                    subtask.status = AnalysisStatus.COMPLETED
                    subtask.progress_percentage = 100.0
                elif task.status == AnalysisStatus.FAILED:
                    subtask.status = AnalysisStatus.FAILED
                    subtask.progress_percentage = 0.0
                elif task.status == AnalysisStatus.CANCELLED:
                    subtask.status = AnalysisStatus.CANCELLED
                    subtask.progress_percentage = 0.0
                else:
                    subtask.status = task.status
                    subtask.progress_percentage = task.progress_percentage or 0.0
                
                subtask.priority = task.priority
                subtask.target_model = task.target_model
                subtask.target_app_number = task.target_app_number
                subtask.task_name = f"{service_name}:{task.target_model}:{task.target_app_number}"
                subtask.description = f"Migrated subtask for {service_name} service"
                subtask.created_at = task.created_at
                subtask.started_at = task.started_at
                subtask.completed_at = task.completed_at
                
                # Copy relevant metadata
                subtask_options = {
                    'service_name': service_name,
                    'tool_ids': list(tool_ids) if tool_ids else [],
                    'parent_task_id': task.task_id,
                    'unified_analysis': True,
                    'migrated': True,
                    'migration_date': datetime.now(timezone.utc).isoformat()
                }
                
                try:
                    subtask.set_metadata({'custom_options': subtask_options})
                except Exception:
                    pass
                
                db.session.add(subtask)
                created_subtasks += 1
                print(f"    Created subtask {subtask_uuid} for service {service_name}")
        
        if not dry_run:
            db.session.commit()
            print(f"\n✓ Migration complete: Created {created_subtasks} subtask(s) for {len(tasks_to_migrate) - skipped_tasks} task(s)")
        else:
            print(f"\n[DRY RUN] Would create {created_subtasks} subtask(s) for {len(tasks_to_migrate) - skipped_tasks} task(s)")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate existing tasks to have subtasks for consistent UI display'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without committing to database'
    )
    
    args = parser.parse_args()
    migrate_tasks_add_subtasks(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
