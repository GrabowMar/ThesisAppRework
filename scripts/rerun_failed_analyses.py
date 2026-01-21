#!/usr/bin/env python3
"""
Rerun Failed/Empty Analysis Tasks
=================================

This script:
1. Finds all analysis tasks with 0 issues or failed status
2. Deletes those tasks from the database
3. Creates new analysis tasks for the same apps
4. Lets TaskExecutionService automatically pick them up

Usage:
    python scripts/rerun_failed_analyses.py [options]

Options:
    --dry-run           Show what would be deleted without actually deleting
    --model MODEL       Only process specific model (e.g., anthropic_claude-4.5-sonnet-20250929)
    --status STATUS     Filter by status (e.g., completed, failed)
    --zero-issues-only  Only process tasks that show 0 issues
    --yes              Skip confirmation prompt
"""
import sys
import argparse
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask, GeneratedApplication
from app.extensions import db
from app.constants import AnalysisStatus, JobPriority
from app.services.task_service import AnalysisTaskService


def find_tasks_to_rerun(model_slug=None, status_filter=None, zero_issues_only=False):
    """Find tasks that should be rerun."""
    query = AnalysisTask.query.filter_by(is_main_task=True)
    
    if model_slug:
        query = query.filter_by(target_model=model_slug)
    
    if status_filter:
        try:
            status_enum = AnalysisStatus[status_filter.upper()]
            query = query.filter_by(status=status_enum)
        except KeyError:
            print(f"Warning: Invalid status '{status_filter}', ignoring filter")
    
    if zero_issues_only:
        query = query.filter_by(issues_found=0)
    
    tasks = query.order_by(AnalysisTask.target_model, AnalysisTask.target_app_number).all()
    
    # Additional filtering: exclude tasks with > 0 issues unless explicitly filtered
    if not status_filter and not zero_issues_only:
        # Default: only tasks with 0 issues or failed status
        tasks = [t for t in tasks if (t.issues_found == 0 or 
                                      t.status in [AnalysisStatus.FAILED, AnalysisStatus.ERROR])]
    
    return tasks


def get_app_tools():
    """Get default tool set for comprehensive analysis."""
    return [
        # Static analyzers
        'bandit', 'semgrep', 'eslint', 'safety', 'trivy',
        # Dynamic analyzers
        'zap', 'nuclei',
        # Performance
        'lighthouse', 'k6',
        # AI
        'deepcode-ai'
    ]


def delete_task_and_subtasks(task_id, dry_run=False):
    """Delete a task and all its subtasks."""
    task = AnalysisTask.query.filter_by(task_id=task_id).first()
    if not task:
        return 0
    
    # Find all subtasks
    subtasks = AnalysisTask.query.filter_by(parent_task_id=task_id).all()
    
    count = 1 + len(subtasks)
    
    if not dry_run:
        # Delete subtasks first
        for subtask in subtasks:
            db.session.delete(subtask)
        
        # Delete main task
        db.session.delete(task)
    
    return count


def create_new_analysis(model_slug, app_number, dry_run=False):
    """Create new analysis task for the app."""
    if dry_run:
        return "DRY_RUN_TASK_ID"
    
    try:
        # Verify app exists
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        if not app:
            print(f"  ⚠️  App not found in database: {model_slug}/app{app_number}")
            return None
        
        # Create main task with subtasks
        tools = get_app_tools()
        task = AnalysisTaskService.create_main_task_with_subtasks(
            model_slug=model_slug,
            app_number=app_number,
            tools=tools,
            priority=JobPriority.NORMAL.value,
            task_name=f"reanalysis:{model_slug}:{app_number}",
            description=f"Reanalysis of {model_slug} app{app_number}"
        )
        
        return task.task_id
    except Exception as e:
        print(f"  ❌ Error creating task: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Rerun failed/empty analysis tasks')
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen without making changes')
    parser.add_argument('--model', type=str, help='Only process specific model')
    parser.add_argument('--status', type=str, help='Filter by status (completed, failed, etc.)')
    parser.add_argument('--zero-issues-only', action='store_true', help='Only process tasks with 0 issues')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    app = create_app()
    with app.app_context():
        print("=" * 80)
        print("RERUN FAILED/EMPTY ANALYSIS TASKS")
        print("=" * 80)
        
        if args.dry_run:
            print("\n🔍 DRY RUN MODE - No changes will be made\n")
        
        # Find tasks to rerun
        print("\nFinding tasks to rerun...")
        tasks = find_tasks_to_rerun(
            model_slug=args.model,
            status_filter=args.status,
            zero_issues_only=args.zero_issues_only
        )
        
        if not tasks:
            print("\n✅ No tasks found matching criteria")
            return 0
        
        # Group by model for better reporting
        by_model = defaultdict(list)
        for task in tasks:
            by_model[task.target_model].append(task)
        
        print(f"\nFound {len(tasks)} tasks to rerun:")
        print("=" * 80)
        
        for model in sorted(by_model.keys()):
            model_tasks = by_model[model]
            print(f"\n{model}: {len(model_tasks)} tasks")
            for task in sorted(model_tasks, key=lambda t: t.target_app_number):
                status_str = task.status.value if hasattr(task.status, 'value') else str(task.status)
                print(f"  app{task.target_app_number}: {task.issues_found} issues, status={status_str}, task_id={task.task_id}")
        
        print("\n" + "=" * 80)
        
        # Confirm
        if not args.yes and not args.dry_run:
            response = input(f"\nDelete and recreate {len(tasks)} tasks? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return 0
        elif args.yes:
            print(f"\nProceeding to delete and recreate {len(tasks)} tasks (--yes flag provided)")
        
        # Process each task
        print("\nProcessing tasks...")
        print("=" * 80)
        
        deleted_count = 0
        created_count = 0
        failed_count = 0
        
        for task in tasks:
            model_slug = task.target_model
            app_number = task.target_app_number
            task_id = task.task_id
            
            print(f"\n{model_slug}/app{app_number}:")
            
            # Delete old task
            print(f"  🗑️  Deleting task {task_id}...")
            count = delete_task_and_subtasks(task_id, dry_run=args.dry_run)
            deleted_count += count
            print(f"  ✓ Would delete {count} records" if args.dry_run else f"  ✓ Deleted {count} records")
            
            if not args.dry_run:
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"  ❌ Failed to delete: {e}")
                    failed_count += 1
                    continue
            
            # Create new task
            print(f"  📝 Creating new analysis task...")
            new_task_id = create_new_analysis(model_slug, app_number, dry_run=args.dry_run)
            
            if new_task_id:
                created_count += 1
                if args.dry_run:
                    print(f"  ✓ Would create new task")
                else:
                    print(f"  ✓ Created task {new_task_id}")
                    try:
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        print(f"  ❌ Failed to commit: {e}")
                        failed_count += 1
            else:
                failed_count += 1
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        if args.dry_run:
            print(f"\nWould delete: {deleted_count} records ({len(tasks)} main tasks + subtasks)")
            print(f"Would create: {created_count} new tasks")
        else:
            print(f"\nDeleted: {deleted_count} records ({len(tasks)} main tasks + subtasks)")
            print(f"Created: {created_count} new tasks")
            print(f"Failed: {failed_count} tasks")
            
            if created_count > 0:
                print(f"\n✅ Successfully requeued {created_count} tasks for analysis")
                print("📊 TaskExecutionService will automatically pick them up and run the analysis")
        
        return 0 if failed_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
