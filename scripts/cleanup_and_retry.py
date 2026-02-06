#!/usr/bin/env python3
"""
Cleanup old tasks and retry failed analyses.

Usage:
    python scripts/cleanup_and_retry.py                    # Dry-run (default)
    python scripts/cleanup_and_retry.py --execute          # Execute cleanup
    python scripts/cleanup_and_retry.py --retry            # Create retry tasks
    python scripts/cleanup_and_retry.py --execute --retry  # Both
"""
import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask, PipelineExecution, GeneratedApplication


# Configuration
OLD_CUTOFF = datetime(2026, 2, 4, 0, 0, 0)  # Tasks before this are "old"
MAX_APPS_PER_MODEL = 10

# Non-target model patterns (test runs to remove)
NON_TARGET_PATTERNS = ['arcee-ai', 'upstage', 'solar', 'trinity']

# Target models for 10x10 analysis (partial match)
TARGET_MODEL_PATTERNS = [
    'openai_gpt-5.2',
    'google_gemini-3-pro',
    'deepseek_deepseek-r1',
    'qwen_qwen3-coder',
    'z-ai_glm-4.7',
    'openai_gpt-4o-mini',
    'mistralai_mistral-small',
    'google_gemini-3-flash',
    'meta-llama_llama-3.1',
    'anthropic_claude'
]


class CleanupStats(NamedTuple):
    old_tasks: list
    non_target_tasks: list
    non_target_apps: list
    non_target_pipelines: list
    excess_apps: list
    excess_tasks: list
    excess_results: list
    failed_retryable: list


def is_target_model(model_slug: str) -> bool:
    """Check if model matches any target pattern."""
    if not model_slug:
        return False
    return any(pattern in model_slug for pattern in TARGET_MODEL_PATTERNS)


def is_non_target_model(model_slug: str) -> bool:
    """Check if model matches any non-target (test) pattern."""
    if not model_slug:
        return False
    return any(pattern in model_slug.lower() for pattern in NON_TARGET_PATTERNS)


def identify_old_tasks() -> list[AnalysisTask]:
    """Find tasks created before the 10x10 run started."""
    return AnalysisTask.query.filter(
        AnalysisTask.created_at < OLD_CUTOFF
    ).all()


def identify_non_target_models() -> tuple[list, list, list]:
    """Find all data for non-target (test) models."""
    import json
    tasks = []
    apps = []
    pipelines = []
    
    # Find tasks
    for task in AnalysisTask.query.all():
        if is_non_target_model(task.target_model):
            tasks.append(task)
    
    # Find apps
    for app in GeneratedApplication.query.all():
        if is_non_target_model(app.model_slug):
            apps.append(app)
    
    # Find pipelines (model is in config_json)
    for pipe in PipelineExecution.query.all():
        if pipe.config_json:
            try:
                config = json.loads(pipe.config_json) if isinstance(pipe.config_json, str) else pipe.config_json
                model = config.get('model_slug', '') or config.get('model', '')
                if is_non_target_model(model):
                    pipelines.append(pipe)
            except (json.JSONDecodeError, AttributeError):
                pass
    
    return tasks, apps, pipelines


def identify_excess_apps() -> tuple[list, list, list]:
    """Find apps and tasks for app_number > MAX_APPS_PER_MODEL."""
    excess_apps = []
    excess_tasks = []
    excess_results = []
    
    # Group apps by model
    apps_by_model: dict[str, list] = {}
    for app in GeneratedApplication.query.all():
        if not is_target_model(app.model_slug):
            continue
        if app.model_slug not in apps_by_model:
            apps_by_model[app.model_slug] = []
        apps_by_model[app.model_slug].append(app)
    
    # Find excess apps
    for model, apps in apps_by_model.items():
        for app in apps:
            if app.app_number > MAX_APPS_PER_MODEL:
                excess_apps.append(app)
    
    # Find tasks for excess apps
    for task in AnalysisTask.query.all():
        if not is_target_model(task.target_model):
            continue
        if task.target_app_number and task.target_app_number > MAX_APPS_PER_MODEL:
            excess_tasks.append(task)
    
    # Find excess result directories
    results_base = Path('/app/results')
    if not results_base.exists():
        results_base = Path(__file__).parent.parent / 'results'
    
    if results_base.exists():
        for model_dir in results_base.iterdir():
            if not model_dir.is_dir():
                continue
            if not is_target_model(model_dir.name):
                continue
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                    continue
                try:
                    app_num = int(app_dir.name.replace('app', ''))
                    if app_num > MAX_APPS_PER_MODEL:
                        excess_results.append(app_dir)
                except ValueError:
                    continue
    
    return excess_apps, excess_tasks, excess_results


def identify_failed_retryable() -> list[dict]:
    """Find failed tasks that can be retried (have generated code)."""
    retryable = []
    
    # Find code directories
    generated_base = Path('/app/generated/apps')
    if not generated_base.exists():
        generated_base = Path(__file__).parent.parent / 'generated' / 'apps'
    
    # Get all failed main tasks within 10x10 scope
    failed_main = AnalysisTask.query.filter(
        AnalysisTask.status == 'failed',
        AnalysisTask.is_main_task == True,
        AnalysisTask.created_at >= OLD_CUTOFF
    ).all()
    
    for task in failed_main:
        if not is_target_model(task.target_model):
            continue
        if task.target_app_number and task.target_app_number > MAX_APPS_PER_MODEL:
            continue
        
        # Check if generated code exists
        app_dir = generated_base / task.target_model / f'app{task.target_app_number}'
        backend_exists = (app_dir / 'backend').exists() if app_dir.exists() else False
        
        if backend_exists:
            # Check if there's already a successful analysis
            successful = AnalysisTask.query.filter(
                AnalysisTask.target_model == task.target_model,
                AnalysisTask.target_app_number == task.target_app_number,
                AnalysisTask.status == 'completed',
                AnalysisTask.is_main_task == True
            ).first()
            
            if not successful:
                retryable.append({
                    'task': task,
                    'model': task.target_model,
                    'app_number': task.target_app_number,
                    'error': task.error_message[:50] if task.error_message else 'No error'
                })
    
    return retryable


def collect_stats() -> CleanupStats:
    """Collect all cleanup statistics."""
    old_tasks = identify_old_tasks()
    non_target_tasks, non_target_apps, non_target_pipelines = identify_non_target_models()
    excess_apps, excess_tasks, excess_results = identify_excess_apps()
    failed_retryable = identify_failed_retryable()
    
    return CleanupStats(
        old_tasks=old_tasks,
        non_target_tasks=non_target_tasks,
        non_target_apps=non_target_apps,
        non_target_pipelines=non_target_pipelines,
        excess_apps=excess_apps,
        excess_tasks=excess_tasks,
        excess_results=excess_results,
        failed_retryable=failed_retryable
    )


def print_stats(stats: CleanupStats, verbose: bool = False) -> None:
    """Print cleanup statistics."""
    print("\n" + "=" * 60)
    print("CLEANUP & RETRY ANALYSIS")
    print("=" * 60)
    
    print(f"\n📅 OLD TASKS (before {OLD_CUTOFF.date()}):")
    print(f"   {len(stats.old_tasks)} tasks to remove")
    if verbose and stats.old_tasks:
        for t in stats.old_tasks[:5]:
            print(f"      - {t.task_id}: {t.target_model} app{t.target_app_number}")
        if len(stats.old_tasks) > 5:
            print(f"      ... and {len(stats.old_tasks) - 5} more")
    
    print(f"\n🧪 NON-TARGET MODELS (test runs):")
    print(f"   {len(stats.non_target_tasks)} tasks")
    print(f"   {len(stats.non_target_apps)} apps")
    print(f"   {len(stats.non_target_pipelines)} pipelines")
    if verbose and stats.non_target_apps:
        models = set(a.model_slug for a in stats.non_target_apps)
        for m in models:
            print(f"      - {m}")
    
    print(f"\n📦 EXCESS APPS (>{MAX_APPS_PER_MODEL} per model):")
    print(f"   {len(stats.excess_apps)} apps in DB")
    print(f"   {len(stats.excess_tasks)} tasks")
    print(f"   {len(stats.excess_results)} result directories")
    if verbose and stats.excess_apps:
        by_model: dict[str, list] = {}
        for a in stats.excess_apps:
            if a.model_slug not in by_model:
                by_model[a.model_slug] = []
            by_model[a.model_slug].append(a.app_number)
        for m, nums in by_model.items():
            print(f"      - {m}: apps {sorted(nums)}")
    
    print(f"\n🔄 FAILED TASKS (retryable):")
    print(f"   {len(stats.failed_retryable)} tasks can be retried")
    if verbose and stats.failed_retryable:
        for r in stats.failed_retryable[:10]:
            print(f"      - {r['model']} app{r['app_number']}: {r['error']}")
        if len(stats.failed_retryable) > 10:
            print(f"      ... and {len(stats.failed_retryable) - 10} more")
    
    print("\n" + "=" * 60)
    total_remove = (
        len(stats.old_tasks) + 
        len(stats.non_target_tasks) + 
        len(stats.excess_tasks)
    )
    print(f"SUMMARY: {total_remove} tasks to remove, {len(stats.failed_retryable)} to retry")
    print("=" * 60)


def execute_cleanup(stats: CleanupStats) -> None:
    """Execute the cleanup operations."""
    print("\n🗑️  EXECUTING CLEANUP...")
    
    # Collect all task IDs to delete
    task_ids_to_delete = set()
    
    # Old tasks
    for t in stats.old_tasks:
        task_ids_to_delete.add(t.id)
    
    # Non-target model tasks
    for t in stats.non_target_tasks:
        task_ids_to_delete.add(t.id)
    
    # Excess tasks
    for t in stats.excess_tasks:
        task_ids_to_delete.add(t.id)
    
    # Delete tasks
    if task_ids_to_delete:
        deleted = AnalysisTask.query.filter(
            AnalysisTask.id.in_(task_ids_to_delete)
        ).delete(synchronize_session=False)
        print(f"   ✓ Deleted {deleted} analysis tasks")
    
    # Delete non-target apps
    if stats.non_target_apps:
        app_ids = [a.id for a in stats.non_target_apps]
        deleted = GeneratedApplication.query.filter(
            GeneratedApplication.id.in_(app_ids)
        ).delete(synchronize_session=False)
        print(f"   ✓ Deleted {deleted} non-target apps")
    
    # Delete excess apps
    if stats.excess_apps:
        app_ids = [a.id for a in stats.excess_apps]
        deleted = GeneratedApplication.query.filter(
            GeneratedApplication.id.in_(app_ids)
        ).delete(synchronize_session=False)
        print(f"   ✓ Deleted {deleted} excess apps")
    
    # Delete non-target pipelines
    if stats.non_target_pipelines:
        pipe_ids = [p.id for p in stats.non_target_pipelines]
        deleted = PipelineExecution.query.filter(
            PipelineExecution.id.in_(pipe_ids)
        ).delete(synchronize_session=False)
        print(f"   ✓ Deleted {deleted} non-target pipelines")
    
    # Commit database changes
    db.session.commit()
    print("   ✓ Database changes committed")
    
    # Delete excess result directories
    for result_dir in stats.excess_results:
        if result_dir.exists():
            shutil.rmtree(result_dir)
            print(f"   ✓ Removed {result_dir}")
    
    print("\n✅ Cleanup complete!")


def execute_retry(stats: CleanupStats) -> None:
    """Create retry tasks for failed analyses."""
    print("\n🔄 CREATING RETRY TASKS...")
    
    if not stats.failed_retryable:
        print("   No tasks to retry")
        return
    
    created = 0
    for item in stats.failed_retryable:
        # Mark old failed task as cancelled (superseded)
        old_task = item['task']
        old_task.status = 'cancelled'
        
        # Create new analysis task with required fields
        import uuid
        new_task = AnalysisTask(
            task_id=f"task_{uuid.uuid4().hex[:12]}",
            is_main_task=True,
            status='pending',
            analyzer_config_id=1,  # Required field
            priority='normal',
            target_model=item['model'],
            target_app_number=item['app_number'],
            task_name=f"Retry analysis for {item['model']} app{item['app_number']}",
            description="Retrying failed analysis",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.session.add(new_task)
        created += 1
    
    db.session.commit()
    print(f"   ✓ Created {created} retry tasks")
    print("\n✅ Retry tasks created! They will be picked up by the scheduler.")


def main():
    parser = argparse.ArgumentParser(description='Cleanup old tasks and retry failed analyses')
    parser.add_argument('--execute', action='store_true', help='Execute cleanup (default: dry-run)')
    parser.add_argument('--retry', action='store_true', help='Create retry tasks for failed analyses')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed information')
    args = parser.parse_args()
    
    app = create_app()
    
    with app.app_context():
        # Collect statistics
        stats = collect_stats()
        
        # Print statistics
        print_stats(stats, verbose=args.verbose)
        
        if not args.execute and not args.retry:
            print("\n⚠️  DRY-RUN MODE - No changes made")
            print("   Use --execute to perform cleanup")
            print("   Use --retry to create retry tasks")
            return
        
        if args.execute:
            execute_cleanup(stats)
        
        if args.retry:
            execute_retry(stats)


if __name__ == '__main__':
    main()
