#!/usr/bin/env python
"""
Fix Pipeline Issue Counts Without Rerunning
============================================

This script fixes pipeline tasks showing 0 issues by:
1. Checking for SARIF files in task directories
2. Checking for individual subtask result files
3. Checking for service JSON files with tool results
4. Recalculating issues_found and severity_breakdown
5. Updating database without rerunning pipelines

Usage:
    python scripts/fix_zero_issue_counts.py [--dry-run] [--verbose]
"""
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json
from collections import defaultdict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from app.utils.sarif_utils import load_sarif_from_reference, extract_issues_from_sarif, is_ruff_sarif, remap_ruff_sarif_severity

def find_all_sarif_files(task_dir: Path) -> List[Path]:
    """Find all SARIF files in task directory (any subdirectory)."""
    sarif_files = []
    if task_dir.exists():
        sarif_files.extend(task_dir.glob('**/*.sarif.json'))
    return sarif_files

def count_issues_from_sarif_files(task_dir: Path, verbose: bool = False) -> Tuple[List[Dict], Dict[str, int]]:
    """Extract all issues from SARIF files in task directory."""
    all_issues = []
    sarif_files = find_all_sarif_files(task_dir)
    
    if verbose and sarif_files:
        print(f"    Found {len(sarif_files)} SARIF files")
    
    for sarif_file in sarif_files:
        try:
            with open(sarif_file) as f:
                sarif_data = json.load(f)
            
            # Determine tool name from filename
            tool_name = sarif_file.stem.replace('.sarif', '')
            
            # Apply Ruff remapping if needed
            if is_ruff_sarif(tool_name, sarif_data):
                remap_ruff_sarif_severity(sarif_data)
            
            # Extract issues
            issues = extract_issues_from_sarif(sarif_data)
            if issues:
                if verbose:
                    print(f"      {sarif_file.name}: {len(issues)} issues")
                for issue in issues:
                    issue['source_file'] = str(sarif_file.relative_to(task_dir))
                all_issues.extend(issues)
        except Exception as e:
            if verbose:
                print(f"      Warning: Failed to process {sarif_file.name}: {e}")
    
    # Calculate breakdown
    breakdown = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    for issue in all_issues:
        severity = str(issue.get('severity', 'info')).lower()
        if severity in breakdown:
            breakdown[severity] += 1
        else:
            breakdown['info'] += 1
    
    # Remove zero counts
    breakdown = {k: v for k, v in breakdown.items() if v > 0}
    
    return all_issues, breakdown

def count_issues_from_service_json(task_dir: Path, verbose: bool = False) -> Tuple[List[Dict], Dict[str, int]]:
    """Count issues from service JSON files (static-analyzer, etc.)."""
    all_issues = []
    services_dir = task_dir / 'services'
    
    if not services_dir.exists():
        return all_issues, {}
    
    if verbose:
        print(f"    Checking services directory")
    
    for service_json in services_dir.glob('*.json'):
        try:
            with open(service_json) as f:
                service_data = json.load(f)
            
            service_name = service_json.stem
            
            # Check analysis.results for tool data
            analysis = service_data.get('analysis', {})
            results = analysis.get('results', {})
            
            if isinstance(results, dict):
                for lang_key, lang_tools in results.items():
                    if isinstance(lang_tools, dict):
                        for tool_name, tool_data in lang_tools.items():
                            if isinstance(tool_data, dict):
                                issues = tool_data.get('issues', [])
                                if issues and isinstance(issues, list):
                                    if verbose:
                                        print(f"      {service_name}/{tool_name}: {len(issues)} issues")
                                    for issue in issues:
                                        issue['service'] = service_name
                                        issue['tool'] = tool_name
                                    all_issues.extend(issues)
        except Exception as e:
            if verbose:
                print(f"      Warning: Failed to process {service_json.name}: {e}")
    
    # Calculate breakdown
    breakdown = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    for issue in all_issues:
        severity = str(issue.get('severity', 'info')).lower()
        if severity in breakdown:
            breakdown[severity] += 1
        else:
            breakdown['info'] += 1
    
    breakdown = {k: v for k, v in breakdown.items() if v > 0}
    
    return all_issues, breakdown

def check_main_result_file(task_dir: Path, verbose: bool = False) -> Tuple[int, Dict[str, int]]:
    """Check the main aggregated result file."""
    # Find main result file
    result_files = list(task_dir.glob('*.json'))
    result_files = [f for f in result_files if f.name != 'manifest.json']
    
    if not result_files:
        return 0, {}
    
    main_file = result_files[0]
    
    try:
        with open(main_file) as f:
            data = json.load(f)
        
        # Check summary
        summary = data.get('summary', {})
        total = summary.get('total_findings', 0)
        
        # Also count findings array
        findings = data.get('findings', [])
        if isinstance(findings, list) and len(findings) > total:
            total = len(findings)
        
        # Check services for tool-level counts
        services = data.get('services', {})
        service_total = 0
        for service_name, service_data in services.items():
            if isinstance(service_data, dict):
                analysis = service_data.get('analysis', {})
                if isinstance(analysis, dict):
                    results = analysis.get('results', {})
                    if isinstance(results, dict):
                        for lang_key, lang_tools in results.items():
                            if isinstance(lang_tools, dict):
                                for tool_name, tool_data in lang_tools.items():
                                    if isinstance(tool_data, dict):
                                        tool_issues = len(tool_data.get('issues', []))
                                        service_total += tool_issues
        
        if service_total > total:
            total = service_total
        
        return total, summary.get('severity_breakdown', {})
    except Exception as e:
        if verbose:
            print(f"      Warning: Failed to read main result file: {e}")
        return 0, {}

def fix_task_issues(task: AnalysisTask, dry_run: bool = False, verbose: bool = False) -> Tuple[bool, int, int]:
    """
    Fix issue count for a single task.
    Returns: (changed, old_count, new_count)
    """
    task_dir = Path('results') / task.target_model / f'app{task.target_app_number}' / task.task_id
    
    if not task_dir.exists():
        if verbose:
            print(f"    No results directory found")
        return False, 0, 0
    
    current_count = task.issues_found if task.issues_found is not None else 0
    
    # Strategy 1: Check main result file first
    main_count, main_breakdown = check_main_result_file(task_dir, verbose)
    
    # Strategy 2: Check service JSON files
    service_issues, service_breakdown = count_issues_from_service_json(task_dir, verbose)
    
    # Strategy 3: Check SARIF files directly
    sarif_issues, sarif_breakdown = count_issues_from_sarif_files(task_dir, verbose)
    
    # Use the highest count found
    new_count = max(main_count, len(service_issues), len(sarif_issues))
    
    # Choose the best breakdown
    if service_breakdown:
        new_breakdown = service_breakdown
    elif sarif_breakdown:
        new_breakdown = sarif_breakdown
    elif main_breakdown:
        new_breakdown = main_breakdown
    else:
        new_breakdown = {}
    
    # Check if update needed
    if new_count == current_count:
        return False, current_count, new_count
    
    if verbose:
        print(f"    Main file: {main_count} issues")
        print(f"    Service JSONs: {len(service_issues)} issues")
        print(f"    SARIF files: {len(sarif_issues)} issues")
        print(f"    Using: {new_count} issues")
        print(f"    Breakdown: {new_breakdown}")
    
    if not dry_run:
        task.issues_found = new_count
        task.set_severity_breakdown(new_breakdown)
        db.session.commit()
    
    return True, current_count, new_count

def main():
    dry_run = '--dry-run' in sys.argv
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    
    print("=" * 80)
    print("Fix Pipeline Issue Counts Without Rerunning")
    print("=" * 80)
    print()
    
    if dry_run:
        print("DRY RUN MODE - No database changes will be made")
        print()
    
    app = create_app()
    with app.app_context():
        # Find all main pipeline tasks with 0 or NULL issues
        tasks = AnalysisTask.query.filter(
            AnalysisTask.is_main_task == True,
            AnalysisTask.status.in_(['completed', 'partial_success'])
        ).filter(
            (AnalysisTask.issues_found == 0) | (AnalysisTask.issues_found == None)
        ).order_by(AnalysisTask.created_at.desc()).all()
        
        print(f"Found {len(tasks)} completed main pipeline tasks with 0 or NULL issues")
        print()
        
        fixed_count = 0
        skipped_count = 0
        error_count = 0
        
        for task in tasks:
            try:
                print(f"{'[DRY RUN] ' if dry_run else ''}Checking {task.task_id} ({task.target_model} app{task.target_app_number}):")
                
                changed, old_count, new_count = fix_task_issues(task, dry_run, verbose)
                
                if changed:
                    print(f"  ✓ Updated: {old_count} → {new_count} issues")
                    fixed_count += 1
                else:
                    if verbose:
                        print(f"  - No issues found to add (remains {old_count})")
                    skipped_count += 1
                
                print()
            except Exception as e:
                print(f"  ✗ ERROR: {e}")
                if verbose:
                    import traceback
                    traceback.print_exc()
                error_count += 1
                print()
        
        print()
        print("=" * 80)
        print("Summary:")
        print("=" * 80)
        print(f"Total tasks checked: {len(tasks)}")
        print(f"Tasks {'that would be ' if dry_run else ''}updated: {fixed_count}")
        print(f"Tasks with no issues found: {skipped_count}")
        print(f"Tasks with errors: {error_count}")
        
        if dry_run and fixed_count > 0:
            print()
            print("Run without --dry-run to apply changes to database")

if __name__ == '__main__':
    main()
