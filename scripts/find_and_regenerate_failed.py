#!/usr/bin/env python3
"""
Find apps with failed generation and optionally regenerate them.

Usage:
    python scripts/find_and_regenerate_failed.py                           # Dry-run (default)
    python scripts/find_and_regenerate_failed.py --execute                 # Execute regeneration
    python scripts/find_and_regenerate_failed.py --model openai_gpt-5.2    # Filter by model
    python scripts/find_and_regenerate_failed.py --template crud_todo_list  # Filter by template
    python scripts/find_and_regenerate_failed.py --max 5 --execute         # Limit regenerations
"""
import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.constants import AnalysisStatus
from app.models import GeneratedApplication

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

MAX_APPS_PER_MODEL = 10


def is_target_model(model_slug: str) -> bool:
    """Check if model matches any target pattern."""
    if not model_slug:
        return False
    return any(pattern in model_slug for pattern in TARGET_MODEL_PATTERNS)


def find_failed_apps(
    model_filter: str | None = None,
    template_filter: str | None = None,
) -> list[dict]:
    """Find apps whose latest version has a failed generation.

    Returns a list of dicts with keys:
        app, model_slug, app_number, template_slug, version, failure_stage, error_message
    """
    # Query all failed apps (dual-condition like maintenance_service.py:316)
    failed_query = GeneratedApplication.query.filter(
        db.or_(
            GeneratedApplication.is_generation_failed == True,  # noqa: E712
            GeneratedApplication.generation_status == AnalysisStatus.FAILED,
        )
    )

    failed_apps = failed_query.all()

    results: list[dict] = []
    # Group by (model_slug, app_number) to find the latest version
    grouped: dict[tuple[str, int], list[GeneratedApplication]] = {}
    for app in failed_apps:
        key = (app.model_slug, app.app_number)
        grouped.setdefault(key, []).append(app)

    for (model_slug, app_number), versions in grouped.items():
        # Only target models within app range
        if not is_target_model(model_slug):
            continue
        if app_number > MAX_APPS_PER_MODEL:
            continue

        # Apply filters
        if model_filter and model_filter not in model_slug:
            continue

        # Find the latest version across ALL versions for this (model, app_number)
        all_versions = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number,
        ).order_by(GeneratedApplication.version.desc()).all()

        if not all_versions:
            continue

        latest = all_versions[0]

        # Skip if the latest version succeeded (e.g. v1 failed but v2 succeeded)
        if not latest.is_generation_failed and latest.generation_status != AnalysisStatus.FAILED:
            continue

        # Apply template filter
        if template_filter and latest.template_slug != template_filter:
            continue

        results.append({
            'app': latest,
            'model_slug': model_slug,
            'app_number': app_number,
            'template_slug': latest.template_slug or '(none)',
            'version': latest.version,
            'failure_stage': latest.failure_stage or '(unknown)',
            'error_message': latest.error_message or '(no error recorded)',
        })

    # Sort by model then app_number for consistent display
    results.sort(key=lambda r: (r['model_slug'], r['app_number']))
    return results


def print_failed_summary(failed: list[dict], verbose: bool = False) -> None:
    """Print a grouped summary of failed apps."""
    print("\n" + "=" * 70)
    print("FAILED GENERATION APPS")
    print("=" * 70)

    if not failed:
        print("\n  No failed generation apps found.")
        print("=" * 70)
        return

    # Group by model
    by_model: dict[str, list[dict]] = {}
    for item in failed:
        by_model.setdefault(item['model_slug'], []).append(item)

    for model_slug in sorted(by_model.keys()):
        items = by_model[model_slug]
        print(f"\n  {model_slug} ({len(items)} failed)")
        print(f"  {'-' * 60}")
        for item in sorted(items, key=lambda x: x['app_number']):
            error_trunc = item['error_message'][:60].replace('\n', ' ')
            print(
                f"    app{item['app_number']:>2d}  v{item['version']}  "
                f"template={item['template_slug']:<25s}  "
                f"stage={item['failure_stage']}"
            )
            if verbose:
                print(f"           error: {error_trunc}")

    print(f"\n  TOTAL: {len(failed)} failed apps across {len(by_model)} models")
    print("=" * 70)


def regenerate_app(app: GeneratedApplication) -> dict:
    """Regenerate a single failed app, creating a new version.

    Follows the same pattern as the regenerate endpoint in models.py:1227-1236.
    Returns a result dict with 'success' key.
    """
    from app.services.generation_v2 import get_generation_service
    from app.utils.async_utils import run_async_safely

    model_slug = app.model_slug
    app_number = app.app_number
    template_slug = app.template_slug or 'crud_todo_list'

    # Find latest version (might have changed since discovery)
    latest = GeneratedApplication.query.filter_by(
        model_slug=model_slug,
        app_number=app_number,
    ).order_by(GeneratedApplication.version.desc()).first()

    if not latest:
        return {'success': False, 'errors': ['App not found in DB']}

    new_version = latest.version + 1
    batch_id = f"regen_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    print(f"    Regenerating {model_slug}/app{app_number}: "
          f"v{latest.version} -> v{new_version} (template={template_slug})")

    service = get_generation_service()
    result = run_async_safely(service.generate_full_app(
        model_slug=model_slug,
        app_num=app_number,
        template_slug=template_slug,
        generate_frontend=True,
        generate_backend=True,
        batch_id=batch_id,
        parent_app_id=latest.id,
        version=new_version,
    ))

    return result


def execute_regeneration(
    failed: list[dict],
    max_count: int | None = None,
) -> None:
    """Regenerate failed apps sequentially."""
    to_process = failed[:max_count] if max_count else failed
    total = len(to_process)

    print(f"\n  Regenerating {total} app(s)...\n")

    succeeded = 0
    errored = 0

    for i, item in enumerate(to_process, 1):
        app: GeneratedApplication = item['app']
        print(f"  [{i}/{total}] {item['model_slug']}/app{item['app_number']}")
        try:
            result = regenerate_app(app)
            if result.get('success'):
                print("    -> SUCCESS")
                succeeded += 1
            else:
                errors = ', '.join(result.get('errors', ['unknown error']))
                print(f"    -> FAILED: {errors}")
                errored += 1
        except Exception as e:
            print(f"    -> ERROR: {e}")
            errored += 1

    print(f"\n  Done: {succeeded} succeeded, {errored} failed out of {total}")


def main():
    parser = argparse.ArgumentParser(
        description='Find failed generation apps and optionally regenerate them'
    )
    parser.add_argument(
        '--execute', action='store_true',
        help='Execute regeneration (default: dry-run)'
    )
    parser.add_argument(
        '--model', type=str, default=None,
        help='Filter by model slug (substring match)'
    )
    parser.add_argument(
        '--template', type=str, default=None,
        help='Filter by template slug (exact match)'
    )
    parser.add_argument(
        '--max', type=int, default=None, dest='max_count',
        help='Maximum number of apps to regenerate'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Show error messages in summary'
    )
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        # Discover failed apps
        failed = find_failed_apps(
            model_filter=args.model,
            template_filter=args.template,
        )

        # Display summary
        print_failed_summary(failed, verbose=args.verbose)

        if not args.execute:
            print("\n  DRY-RUN MODE - No changes made")
            print("  Use --execute to regenerate failed apps")
            if args.max_count:
                print(f"  Will regenerate up to {args.max_count} app(s) when --execute is used")
            return

        if not failed:
            print("\n  Nothing to regenerate.")
            return

        execute_regeneration(failed, max_count=args.max_count)


if __name__ == '__main__':
    main()
