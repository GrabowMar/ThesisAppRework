#!/usr/bin/env python
"""
Recount Pipeline Issues from SARIF Files
=========================================

This script fixes pipeline tasks that show 0 issues by re-hydrating SARIF files
and updating the database with correct issue counts.

It will:
1. Find all main pipeline tasks (is_main_task=True)
2. Check if they have SARIF files that weren't counted
3. Re-hydrate SARIF files and update issues_found in database
4. Update severity_breakdown based on actual findings

Usage:
    python scripts/recount_pipeline_issues.py [--dry-run]
"""
import sys
import os
from pathlib import Path
from typing import Dict, Any
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from app.utils.sarif_utils import load_sarif_from_reference, extract_issues_from_sarif, is_ruff_sarif, remap_ruff_sarif_severity

def count_sarif_issues(task: AnalysisTask) -> tuple[int, Dict[str, int]]:
    """Count issues from SARIF files for a task."""
    task_dir = Path('results') / task.target_model / f'app{task.target_app_number}' / task.task_id
    
    if not task_dir.exists():
        return 0, {}
    
    services_dir = task_dir / 'services'
    if not services_dir.exists():
        return 0, {}
    
    all_issues = []
    
    # Check each service JSON file
    for service_json in services_dir.glob('*.json'):
        try:
            with open(service_json) as f:
                service_data = json.load(f)
            
            # Check for tools with SARIF references
            results = service_data.get('results', {})
            if isinstance(results, dict):
                # Iterate through language groups (for static-analyzer)
                for lang_key, lang_tools in results.items():
                    if isinstance(lang_tools, dict):
                        for tool_name, tool_data in lang_tools.items():
                            if isinstance(tool_data, dict):
                                sarif_ref = tool_data.get('sarif_file') or tool_data.get('sarif')
                                if sarif_ref:
                                    # Load SARIF and extract issues
                                    sarif_data = load_sarif_from_reference(sarif_ref, task_dir)
                                    if sarif_data:
                                        if is_ruff_sarif(tool_name, sarif_data):
                                            remap_ruff_sarif_severity(sarif_data)
                                        
                                        extracted_issues = extract_issues_from_sarif(sarif_data)
                                        all_issues.extend(extracted_issues)
        except Exception as e:
            print(f"  Warning: Failed to process {service_json.name}: {e}")
    
    # Calculate severity breakdown
    breakdown = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    for issue in all_issues:
        severity = str(issue.get('severity', 'info')).lower()
        if severity in breakdown:
            breakdown[severity] += 1
        else:
            breakdown['info'] += 1
    
    # Remove zero counts
    breakdown = {k: v for k, v in breakdown.items() if v > 0}
    
    return len(all_issues), breakdown

def main():
    dry_run = '--dry-run' in sys.argv
    
    print("=" * 80)
    print("Recount Pipeline Issues from SARIF Files")
    print("=" * 80)
    print()
    
    if dry_run:
        print("DRY RUN MODE - No database changes will be made")
        print()
    
    app = create_app()
    with app.app_context():
        # Find all main pipeline tasks
        main_tasks = AnalysisTask.query.filter_by(is_main_task=True).order_by(AnalysisTask.created_at.desc()).all()
        
        print(f"Found {len(main_tasks)} main pipeline tasks")
        print()
        
        fixed_count = 0
        skipped_count = 0
        error_count = 0
        
        for task in main_tasks:
            current_count = task.issues_found if task.issues_found is not None else 0
            
            # Count actual issues from SARIF files
            try:
                sarif_count, breakdown = count_sarif_issues(task)
            except Exception as e:
                print(f"✗ {task.task_id} ({task.target_model} app{task.target_app_number}): ERROR - {e}")
                error_count += 1
                continue
            
            # Check if update is needed
            if sarif_count == current_count:
                skipped_count += 1
                if sarif_count > 0:  # Only show tasks with issues
                    print(f"✓ {task.task_id} ({task.target_model} app{task.target_app_number}): {current_count} issues (correct)")
                continue
            
            print(f"{'[DRY RUN] ' if dry_run else ''}Updating {task.task_id} ({task.target_model} app{task.target_app_number}):")
            print(f"  Database: {current_count} issues")
            print(f"  SARIF files: {sarif_count} issues")
            print(f"  Breakdown: {breakdown}")
            
            if not dry_run:
                # Update database
                task.issues_found = sarif_count
                task.set_severity_breakdown(breakdown)
                db.session.commit()
                print(f"  ✓ Updated successfully")
            
            fixed_count += 1
            print()
        
        print()
        print("=" * 80)
        print("Summary:")
        print("=" * 80)
        print(f"Total tasks checked: {len(main_tasks)}")
        print(f"Tasks {'that would be ' if dry_run else ''}updated: {fixed_count}")
        print(f"Tasks already correct: {skipped_count}")
        print(f"Tasks with errors: {error_count}")
        
        if dry_run:
            print()
            print("Run without --dry-run to apply changes to database")

if __name__ == '__main__':
    main()
