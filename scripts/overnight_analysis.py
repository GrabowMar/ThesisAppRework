#!/usr/bin/env python3
"""Purge old analysis data and run overnight analysis for apps 1-10 across all models."""
import sys
import argparse
import shutil
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, 'src')

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask, AnalysisResult, GeneratedApplication, PipelineExecution, User
from app.engines.container_tool_registry import get_container_tool_registry


def purge_analysis_data(results_dir: Path) -> None:
    """Delete analysis DB records and results files (non-destructive to generated apps)."""
    # Delete AnalysisResult first due to FK
    db.session.query(AnalysisResult).delete()
    db.session.query(AnalysisTask).delete()
    db.session.commit()

    # Remove results/* (keep root folder)
    if results_dir.exists() and results_dir.is_dir():
        for child in results_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except Exception:
                    pass


def get_existing_apps(max_app: int) -> List[Dict[str, int]]:
    """Build existingApps list for apps 1..max_app across all models."""
    apps = (
        GeneratedApplication.query
        .filter(GeneratedApplication.app_number <= max_app)
        .order_by(GeneratedApplication.model_slug, GeneratedApplication.app_number)
        .all()
    )

    seen = set()
    existing_apps: List[Dict[str, int]] = []
    for app in apps:
        key = (app.model_slug, app.app_number)
        if key in seen:
            continue
        seen.add(key)
        # NOTE: Pipeline expects keys: {"model": ..., "app": ...}
        existing_apps.append({
            'model': app.model_slug,
            'app': app.app_number,
        })

    return existing_apps


def get_all_tool_names() -> List[str]:
    registry = get_container_tool_registry()
    all_tools = registry.get_all_tools()
    return sorted(all_tools.keys())


def main() -> int:
    parser = argparse.ArgumentParser(description="Overnight analysis for apps 1-10 across all models")
    parser.add_argument('--max-app', type=int, default=10, help='Max app number to include (default: 10)')
    parser.add_argument('--max-concurrent', type=int, default=2, help='Max concurrent analysis tasks (default: 2)')
    parser.add_argument('--dry-run', action='store_true', help='Show actions without modifying data')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        # Get admin user
        user = User.query.filter_by(username='admin').first()
        if not user:
            print("Admin user not found")
            return 1

        results_dir = Path('results')

        # Build existing apps list
        existing_apps = get_existing_apps(args.max_app)
        if not existing_apps:
            print("No generated apps found for requested range")
            return 1

        tools = get_all_tool_names()

        print("=" * 80)
        print("OVERNIGHT ANALYSIS SETUP")
        print("=" * 80)
        print(f"User: {user.username} (id={user.id})")
        print(f"Apps included: {len(existing_apps)}")
        print(f"Max app number: {args.max_app}")
        print(f"Tools: {len(tools)} total")
        print(f"Max concurrent tasks: {args.max_concurrent}")
        print("Dry run:" + (" YES" if args.dry_run else " NO"))
        print("=" * 80)

        if args.dry_run:
            print("\nDRY RUN - No changes made")
            return 0

        # Purge old analysis data
        print("\nPurging analysis records and results files...")
        purge_analysis_data(results_dir)
        print("✓ Analysis data purged")

        # Create pipeline config
        config = {
            'generation': {
                'mode': 'existing',
                'existingApps': existing_apps,
            },
            'analysis': {
                'enabled': True,
                'tools': tools,
                'autoStartContainers': True,
                'stopAfterAnalysis': False,
                'options': {
                    'parallel': True,
                    'maxConcurrentTasks': args.max_concurrent,
                }
            }
        }

        pipeline = PipelineExecution(
            user_id=user.id,
            config=config,
            name=f"Overnight analysis apps1-{args.max_app} (all models)"
        )
        pipeline.start()

        # Existing-app pipelines should skip generation stage
        prog = pipeline.progress
        prog['generation']['completed'] = prog['generation']['total']
        prog['generation']['status'] = 'completed'
        prog['analysis']['total'] = len(existing_apps)
        prog['analysis']['status'] = 'running'
        pipeline.progress = prog
        pipeline.current_stage = 'analysis'
        pipeline.current_job_index = 0

        db.session.add(pipeline)
        db.session.commit()

        print("\n✓ Pipeline created and started")
        print(f"Pipeline ID: {pipeline.pipeline_id}")
        print(f"Status: {pipeline.status}, Stage: {pipeline.current_stage}")
        print("\nYou can monitor with:")
        print(f"  python scripts/check_pipeline_detail.py {pipeline.pipeline_id}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
