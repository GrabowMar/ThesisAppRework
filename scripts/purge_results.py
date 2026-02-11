#!/usr/bin/env python3
"""
Purge Analysis Results
======================
Clears all analysis results from database and filesystem.
Does NOT touch generated applications or their code.

Usage (via Docker):
    docker compose exec web python scripts/purge_results.py           # Interactive
    docker compose exec web python scripts/purge_results.py -y        # Skip confirmation
    docker compose exec web python scripts/purge_results.py --dry-run # Preview only

Usage (local, if dependencies installed):
    python scripts/purge_results.py
"""

import sys
import os
import shutil
import argparse
from pathlib import Path

# Support both local (src/) and Docker (/app/src/) environments
_script_dir = Path(__file__).parent
_project_root = _script_dir.parent
sys.path.insert(0, str(_project_root / 'src'))
sys.path.insert(0, str(_project_root))

from app.factory import create_app
from app.extensions import db


def purge_results(dry_run: bool = False, confirm: bool = False) -> bool:
    """Purge all analysis results from DB and filesystem."""

    if not confirm and not dry_run:
        print("⚠️  This will DELETE all analysis results:")
        print("   - Analysis results (AnalysisResult)")
        print("   - Analysis tasks (AnalysisTask)")
        print("   - Results cache (AnalysisResultsCache)")
        print("   - Reports (Report)")
        print("   - Pipeline executions (PipelineExecution)")
        print("   - results/ directory contents")
        print()
        print("   Generated applications will NOT be touched.")
        print()
        response = input("Type 'YES' to confirm: ")
        if response != 'YES':
            print("Aborted.")
            return False

    prefix = "[DRY RUN] " if dry_run else ""
    app = create_app()

    with app.app_context():
        from app.models import (
            AnalysisResult, AnalysisTask, AnalysisResultsCache,
            Report, PipelineExecution,
        )

        # Count records first
        counts = {
            'AnalysisResult': AnalysisResult.query.count(),
            'AnalysisTask': AnalysisTask.query.count(),
            'AnalysisResultsCache': AnalysisResultsCache.query.count(),
            'Report': Report.query.count(),
            'PipelineExecution': PipelineExecution.query.count(),
        }

        print(f"\n{prefix}🗑️  Clearing database records...")

        # Delete in FK-safe order
        if not dry_run:
            db.session.query(AnalysisResult).delete()
            db.session.query(AnalysisResultsCache).delete()
            db.session.query(Report).delete()
            db.session.query(AnalysisTask).delete()
            db.session.query(PipelineExecution).delete()
            db.session.commit()

        for table, count in counts.items():
            print(f"   {prefix}- {table}: {count} records")

        print(f"   {prefix}✅ Database cleared")

    # Resolve results directory (Docker: /app/results, local: ./results)
    from app.paths import RESULTS_DIR
    results_dir = Path(RESULTS_DIR)
    num_dirs = 0

    if results_dir.exists():
        dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        num_dirs = len(dirs)
        print(f"\n{prefix}🗑️  Clearing {results_dir}/ ({num_dirs} model directories)...")
        for item in dirs:
            if not dry_run:
                shutil.rmtree(item)
            print(f"   {prefix}- Removed {item.name}/")
        # Also remove any stray files
        for f in results_dir.iterdir():
            if f.is_file():
                if not dry_run:
                    f.unlink()
                print(f"   {prefix}- Removed {f.name}")
        print(f"   {prefix}✅ Results directory cleared")
    else:
        print(f"\n   ℹ️  {results_dir} does not exist")

    print()
    print("=" * 50)
    total = sum(counts.values())
    print(f"{prefix}✅ PURGE COMPLETE — {total} DB records, {num_dirs} result dirs")
    print("=" * 50)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Purge all analysis results')
    parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')
    parser.add_argument('--dry-run', action='store_true', help='Preview without deleting')
    args = parser.parse_args()

    purge_results(dry_run=args.dry_run, confirm=args.yes)
