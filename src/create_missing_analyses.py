#!/usr/bin/env python3
"""
Script to create missing analysis tasks for apps.
Each app should have exactly one complete set of analyses:
- 1 main task
- 4 subtasks (static, dynamic, performance, ai)
"""
import sys
import secrets
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask, GeneratedApplication
from app.extensions import db
from app.constants import AnalysisStatus, JobPriority

def generate_task_id() -> str:
    """Generate a unique task ID."""
    return f"task_{secrets.token_hex(6)}"

def create_analysis_tasks_for_app(model_slug: str, app_number: int, batch_id: str) -> dict:
    """Create a complete set of analysis tasks for an app.

    Returns:
        dict with 'main_task' and 'subtasks' keys
    """
    analyzer_config_id = 1  # AutoDefault-Universal

    # Create main task
    main_task_id = generate_task_id()
    main_task = AnalysisTask(
        task_id=main_task_id,
        parent_task_id=None,
        is_main_task=True,
        service_name=None,
        analyzer_config_id=analyzer_config_id,
        status=AnalysisStatus.PENDING,  # PENDING so task executor picks it up
        priority=JobPriority.NORMAL,
        target_model=model_slug,
        target_app_number=app_number,
        task_name=f"pipeline:{model_slug}:{app_number}",
        description=f"Pipeline analysis for {model_slug} app{app_number}",
        batch_id=batch_id,
        progress_percentage=0.0,
        retry_count=0,
        max_retries=3
    )

    # Create subtasks (subtasks should have batch_id=None to avoid unique constraint violation)
    service_names = [
        'static-analyzer',
        'dynamic-analyzer',
        'performance-tester',
        'ai-analyzer'
    ]

    subtasks = []
    for service_name in service_names:
        subtask_id = generate_task_id()
        subtask = AnalysisTask(
            task_id=subtask_id,
            parent_task_id=main_task_id,
            is_main_task=False,
            service_name=service_name,
            analyzer_config_id=analyzer_config_id,
            status=AnalysisStatus.PENDING,  # PENDING so task executor picks it up
            priority=JobPriority.NORMAL,
            target_model=model_slug,
            target_app_number=app_number,
            task_name=f"{service_name}:{model_slug}:{app_number}",
            description=f"{service_name} analysis for {model_slug} app{app_number}",
            batch_id=None,  # Subtasks have None batch_id to avoid unique constraint
            progress_percentage=0.0,
            retry_count=0,
            max_retries=3
        )
        subtasks.append(subtask)

    return {
        'main_task': main_task,
        'subtasks': subtasks
    }

def main():
    """Main execution function."""
    import argparse
    parser = argparse.ArgumentParser(description='Create missing analysis tasks for apps')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        # Get the last pipeline execution timeframe
        from sqlalchemy import text
        result = db.session.execute(text('''
            SELECT id, pipeline_id, created_at, completed_at
            FROM pipeline_executions
            ORDER BY created_at DESC
            LIMIT 1
        '''))
        pipeline_row = result.fetchone()

        if not pipeline_row:
            print("No pipeline executions found!")
            return 1

        exec_id, pipeline_id, created_at, completed_at = pipeline_row
        print(f"Pipeline: {pipeline_id}")
        print(f"Execution ID: {exec_id}")
        print(f"Timeframe: {created_at} to {completed_at}\n")

        # Get all apps from this pipeline
        apps = GeneratedApplication.query.filter(
            GeneratedApplication.created_at >= created_at,
            GeneratedApplication.created_at <= completed_at
        ).order_by(GeneratedApplication.model_slug, GeneratedApplication.app_number).all()

        print(f"Total apps from pipeline: {len(apps)}\n")

        # Find apps without analyses
        apps_missing_analyses = []
        for app in apps:
            existing_tasks = AnalysisTask.query.filter_by(
                target_model=app.model_slug,
                target_app_number=app.app_number
            ).count()

            if existing_tasks == 0:
                apps_missing_analyses.append(app)

        print(f"Apps missing analyses: {len(apps_missing_analyses)}\n")

        if not apps_missing_analyses:
            print("All apps already have analyses!")
            return 0

        # Group by model for better reporting
        from collections import defaultdict
        by_model = defaultdict(list)
        for app in apps_missing_analyses:
            by_model[app.model_slug].append(app)

        print("Apps that will get analyses created:")
        print("=" * 80)
        for model in sorted(by_model.keys()):
            apps_list = by_model[model]
            print(f"\n{model}: {len(apps_list)} apps")
            for app in sorted(apps_list, key=lambda x: x.app_number):
                print(f"  app{app.app_number} (status: {app.generation_status.value})")

        print("\n" + "=" * 80)

        if not args.yes:
            response = input(f"\nCreate analyses for {len(apps_missing_analyses)} apps? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return 0
        else:
            print(f"\nProceeding to create analyses for {len(apps_missing_analyses)} apps (--yes flag provided)")

        # Create analyses for each app
        print("\nCreating analyses...")
        print("=" * 80)

        created_count = 0
        for app in apps_missing_analyses:
            try:
                # Use pipeline_id as batch_id for consistency
                tasks_dict = create_analysis_tasks_for_app(
                    app.model_slug,
                    app.app_number,
                    pipeline_id
                )

                # Add main task
                db.session.add(tasks_dict['main_task'])

                # Add subtasks
                for subtask in tasks_dict['subtasks']:
                    db.session.add(subtask)

                # Commit for this app
                db.session.commit()

                created_count += 1
                print(f"✓ Created analyses for {app.model_slug}/app{app.app_number}")

            except Exception as e:
                db.session.rollback()
                print(f"✗ Failed to create analyses for {app.model_slug}/app{app.app_number}: {e}")

        print("\n" + "=" * 80)
        print(f"\nSuccessfully created analyses for {created_count}/{len(apps_missing_analyses)} apps")
        print(f"Total tasks created: {created_count * 5} (main + 4 subtasks per app)")

        # Verify
        print("\n" + "=" * 80)
        print("Verification:")
        all_apps_complete = True
        for app in apps:
            task_count = AnalysisTask.query.filter_by(
                target_model=app.model_slug,
                target_app_number=app.app_number
            ).count()

            if task_count != 5:
                print(f"✗ {app.model_slug}/app{app.app_number}: {task_count} tasks (expected 5)")
                all_apps_complete = False

        if all_apps_complete:
            print("✓ All apps now have complete analysis sets (5 tasks each)")

        return 0

if __name__ == '__main__':
    sys.exit(main())
