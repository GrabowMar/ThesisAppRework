"""
Fix Task Statuses Migration Script
===================================

Updates tasks that were incorrectly marked as FAILED but actually have results.
This fixes tasks that were analyzed before the partial_success status fix was applied.

Usage:
    python scripts/fix_task_statuses.py [--dry-run]
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.extensions import db
from app.paths import RESULTS_DIR


def check_task_has_results(task: AnalysisTask) -> bool:
    """Check if a task has actual result files on disk."""
    try:
        # Strip "task_" prefix if present in task.task_id to avoid duplication
        task_id_clean = task.task_id.replace('task_', '', 1) if task.task_id.startswith('task_') else task.task_id
        task_dir = RESULTS_DIR / task.target_model / f"app{task.target_app_number}" / f"task_{task_id_clean}"
        
        if not task_dir.exists():
            return False
        
        # Check for JSON result files
        json_files = list(task_dir.glob("*.json"))
        return len(json_files) > 0
    except Exception as e:
        print(f"  Error checking results for {task.task_id}: {e}")
        return False


def main(dry_run: bool = False):
    """Fix task statuses that were incorrectly marked as failed."""
    app = create_app()
    
    with app.app_context():
        # Find all FAILED tasks
        failed_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.FAILED).all()
        
        print(f"Found {len(failed_tasks)} tasks with FAILED status")
        print(f"Checking for tasks with actual results...")
        print()
        
        tasks_to_fix = []
        
        for task in failed_tasks:
            # Check if task has result_summary in DB
            has_db_results = task.result_summary is not None
            
            # Check if task has result files on disk
            has_file_results = check_task_has_results(task)
            
            if has_db_results or has_file_results:
                tasks_to_fix.append({
                    'task': task,
                    'has_db_results': has_db_results,
                    'has_file_results': has_file_results
                })
        
        print(f"Found {len(tasks_to_fix)} tasks with results that are marked as FAILED")
        print()
        
        if not tasks_to_fix:
            print("OK - No tasks need fixing!")
            return
        
        # Show what will be fixed
        print("Tasks to fix:")
        for item in tasks_to_fix:
            task = item['task']
            result_sources = []
            if item['has_db_results']:
                result_sources.append("DB")
            if item['has_file_results']:
                result_sources.append("Files")
            
            print(f"  - {task.task_id}: {task.target_model} app{task.target_app_number}")
            print(f"    Results in: {', '.join(result_sources)}")
            
            # Check summary to determine if partial or complete
            if task.result_summary:
                try:
                    summary = task.get_result_summary()
                    if isinstance(summary, dict):
                        summary_data = summary.get('summary', {})
                        tools_failed = summary_data.get('tools_failed', [])
                        tools_executed = summary_data.get('tools_executed', 0)
                        
                        if tools_failed and len(tools_failed) > 0:
                            print(f"    → Will mark as PARTIAL_SUCCESS ({len(tools_failed)} tools failed)")
                            item['new_status'] = AnalysisStatus.PARTIAL_SUCCESS
                        else:
                            print(f"    → Will mark as COMPLETED")
                            item['new_status'] = AnalysisStatus.COMPLETED
                    else:
                        print(f"    → Will mark as COMPLETED (no failure info)")
                        item['new_status'] = AnalysisStatus.COMPLETED
                except Exception as e:
                    print(f"    → Will mark as COMPLETED (error parsing summary: {e})")
                    item['new_status'] = AnalysisStatus.COMPLETED
            else:
                print(f"    → Will mark as COMPLETED (file results only)")
                item['new_status'] = AnalysisStatus.COMPLETED
        
        print()
        
        if dry_run:
            print("DRY RUN - No changes made")
            print(f"Run without --dry-run to apply fixes to {len(tasks_to_fix)} tasks")
            return
        
        # Apply fixes
        print("Applying fixes...")
        fixed_count = 0
        
        for item in tasks_to_fix:
            task = item['task']
            new_status = item.get('new_status', AnalysisStatus.COMPLETED)
            
            try:
                task.status = new_status
                db.session.commit()
                fixed_count += 1
                print(f"  OK Fixed {task.task_id} -> {new_status.value}")
            except Exception as e:
                print(f"  ✗ Failed to fix {task.task_id}: {e}")
                db.session.rollback()
        
        print()
        print(f"OK Successfully fixed {fixed_count} out of {len(tasks_to_fix)} tasks")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix task statuses that were incorrectly marked as failed')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without making changes')
    
    args = parser.parse_args()
    
    main(dry_run=args.dry_run)
