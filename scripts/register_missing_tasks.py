#!/usr/bin/env python3
"""
Register Missing Tasks in Database
====================================

Finds analysis result directories on disk that don't have corresponding
AnalysisTask records in the database, and creates them. This ensures the
ReportService can discover all results via database queries.

Only registers tasks that are the "best" (most complete) for each model/app.

Usage:
    # Inside web container:
    python3 scripts/register_missing_tasks.py --dry-run
    python3 scripts/register_missing_tasks.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def get_template_for_app(model_slug: str, app_number: int) -> str:
    """Look up template_slug from GeneratedApplication or infer from app number."""
    from app.models import GeneratedApplication
    app = GeneratedApplication.query.filter_by(
        model_slug=model_slug,
        app_number=app_number
    ).first()
    if app and app.template_slug:
        return app.template_slug
    # Fallback: infer from misc/requirements
    template_map = {
        1: 'crud_todo_list',
        2: 'api_weather_display',
        3: 'auth_user_login',
        4: 'booking_reservations',
        5: 'chat_messaging',
        6: 'dashboard_analytics',
        7: 'ecommerce_product',
        8: 'file_manager',
        9: 'social_media_feed',
        10: 'blog_publishing',
    }
    return template_map.get(app_number, 'unknown')


def find_best_task(app_dir: Path) -> Path | None:
    """Find best task directory (most services, most recent)."""
    best = None
    best_score = -1
    for task_dir in sorted(app_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not task_dir.is_dir() or not task_dir.name.startswith('task'):
            continue
        svc_dir = task_dir / 'services'
        if not svc_dir.exists():
            continue
        score = sum(1 for f in svc_dir.glob('*.json')
                    if f.stem in ('static', 'dynamic', 'performance', 'ai'))
        # Also check file sizes for quality
        for f in svc_dir.glob('*.json'):
            if f.stem in ('static', 'dynamic', 'performance', 'ai') and f.stat().st_size > 100:
                score += 5
        if score > best_score:
            best_score = score
            best = task_dir
    return best


def register_missing_tasks(dry_run: bool = False):
    """Register disk-only best tasks into the database."""
    from app.factory import create_app
    from app.extensions import db
    from app.models import AnalysisTask, GeneratedApplication
    from app.constants import AnalysisStatus

    app = create_app()
    with app.app_context():
        # Get existing task IDs
        existing_ids = {t.task_id for t in AnalysisTask.query.all()}
        results_dir = Path('/app/results')

        registered = 0
        skipped = 0
        errors = []

        for model_dir in sorted(results_dir.iterdir()):
            if not model_dir.is_dir() or model_dir.name.endswith('.json'):
                continue

            model_slug = model_dir.name

            for app_dir in sorted(model_dir.iterdir()):
                if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                    continue

                app_name = app_dir.name
                try:
                    app_number = int(app_name[3:])
                except ValueError:
                    continue

                best_task_dir = find_best_task(app_dir)
                if not best_task_dir:
                    continue

                task_id = best_task_dir.name

                # Skip if already in DB
                if task_id in existing_ids:
                    skipped += 1
                    continue

                # Check what services exist
                svc_dir = best_task_dir / 'services'
                services = []
                if svc_dir.exists():
                    for f in svc_dir.glob('*.json'):
                        if f.stem in ('static', 'dynamic', 'performance', 'ai') and f.stat().st_size > 100:
                            services.append(f.stem)

                # Determine status
                has_static = 'static' in services
                has_ai = 'ai' in services
                if has_static and has_ai:
                    status = AnalysisStatus.COMPLETED
                elif has_static or has_ai:
                    status = AnalysisStatus.PARTIAL_SUCCESS
                else:
                    status = AnalysisStatus.FAILED

                template = get_template_for_app(model_slug, app_number)

                if dry_run:
                    print(f'[DRY-RUN] Register: {model_slug}/{app_name}/{task_id} '
                          f'({len(services)} services: {services}) status={status.value}')
                    registered += 1
                    continue

                try:
                    # Create main task
                    main_task = AnalysisTask(
                        task_id=task_id,
                        target_model=model_slug,
                        target_app_number=app_number,
                        task_name='comprehensive',
                        status=status,
                        is_main_task=True,
                        analyzer_config_id=1,
                        created_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                    )

                    # Load consolidated.json for result_summary
                    consolidated_path = best_task_dir / 'consolidated.json'
                    if consolidated_path.exists():
                        with open(consolidated_path) as f:
                            main_task.result_summary = f.read()

                    db.session.add(main_task)

                    # Create subtasks for each service
                    for svc_name in services:
                        subtask = AnalysisTask(
                            task_id=f'{task_id}_sub_{svc_name}',
                            parent_task_id=task_id,
                            target_model=model_slug,
                            target_app_number=app_number,
                            task_name=svc_name,
                            service_name=svc_name,
                            status=AnalysisStatus.COMPLETED,
                            is_main_task=False,
                            analyzer_config_id=1,
                            created_at=datetime.now(timezone.utc),
                            completed_at=datetime.now(timezone.utc),
                        )
                        db.session.add(subtask)

                    db.session.commit()
                    print(f'[OK] Registered: {model_slug}/{app_name}/{task_id} '
                          f'({len(services)} services)')
                    registered += 1
                    existing_ids.add(task_id)

                except Exception as e:
                    db.session.rollback()
                    errors.append(f'{model_slug}/{app_name}/{task_id}: {e}')
                    print(f'[ERROR] {model_slug}/{app_name}/{task_id}: {e}')

        print(f'\n=== Summary ===')
        print(f'Registered: {registered}')
        print(f'Already in DB: {skipped}')
        print(f'Errors: {len(errors)}')

        return registered, skipped, errors


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Register missing tasks in database')
    parser.add_argument('--dry-run', action='store_true', help='Preview without changes')
    args = parser.parse_args()

    register_missing_tasks(dry_run=args.dry_run)
