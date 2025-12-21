#!/usr/bin/env python3
"""
Migration script to fix pipeline results that have the wrong structure.

This script scans all result files and fixes those where services have 'payload'
instead of 'analysis' key, or where tool data is missing.

This is a ONE-TIME migration script (not permanent code) as requested by the user.
Run it once after deploying the fix to task_execution_service.py.

Usage:
    python scripts/migrate_pipeline_results.py [--dry-run]
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

RESULTS_DIR = Path(__file__).parent.parent / 'results'
BACKUP_SUFFIX = '.pre_migration.bak'


def is_pipeline_result(data: Dict[str, Any]) -> bool:
    """Check if this result was created by pipeline (old broken format)."""
    services = data.get('services', {})
    if not services:
        return False
    
    # Pipeline results have service entries with 'payload' key but no 'analysis' key
    for service_name, service_data in services.items():
        if isinstance(service_data, dict):
            # Old pipeline format: has payload, subtask_id, service_name
            has_payload_only = 'payload' in service_data and 'analysis' not in service_data
            has_pipeline_markers = 'subtask_id' in service_data
            
            if has_payload_only or has_pipeline_markers:
                return True
    
    return False


def needs_migration(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Check if this result file needs migration.
    
    Returns: (needs_migration: bool, reason: str)
    """
    services = data.get('services', {})
    
    if not services:
        return False, "No services found"
    
    for service_name, service_data in services.items():
        if not isinstance(service_data, dict):
            continue
        
        # Check for old pipeline format markers
        if 'subtask_id' in service_data and 'analysis' not in service_data:
            return True, f"Service '{service_name}' has subtask_id but no 'analysis' key"
        
        # Check for payload without analysis (old format)
        if 'payload' in service_data and 'analysis' not in service_data:
            return True, f"Service '{service_name}' has 'payload' but no 'analysis' key"
    
    return False, "Already migrated or correct format"


def migrate_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate a single result file from old pipeline format to new format.
    
    Old format:
        services[name] = {status, payload, subtask_id, service_name}
    
    New format:
        services[name] = {status, analysis, payload, service, error}
    """
    services = data.get('services', {})
    migrated_services = {}
    all_findings = []
    combined_tools = {}
    
    for service_name, service_data in services.items():
        if not isinstance(service_data, dict):
            migrated_services[service_name] = service_data
            continue
        
        # Extract payload (which contains the actual analysis data)
        payload = service_data.get('payload', {})
        
        # If analysis already exists, use it; otherwise promote payload to analysis
        analysis = service_data.get('analysis', {})
        if not analysis and payload:
            analysis = payload
        
        # Build migrated service entry
        migrated_services[service_name] = {
            'status': service_data.get('status', 'unknown'),
            'service': service_data.get('service_name', service_name),
            'analysis': analysis,
            'payload': payload,  # Keep for backward compatibility
            'error': service_data.get('error')
        }
        
        # Extract tool results for flat tools map
        if isinstance(analysis, dict):
            # Check analysis.results (for grouped tools by language)
            results = analysis.get('results', {})
            if isinstance(results, dict):
                for key, value in results.items():
                    if isinstance(value, dict):
                        for tool_name, tool_data in value.items():
                            if isinstance(tool_data, dict):
                                if any(k in tool_data for k in ['status', 'issues', 'total_issues']):
                                    combined_tools[tool_name] = tool_data
                                    # Extract findings
                                    issues = tool_data.get('issues', [])
                                    if isinstance(issues, list):
                                        for issue in issues:
                                            if isinstance(issue, dict):
                                                issue['tool'] = tool_name
                                                issue['service'] = service_name
                                                all_findings.append(issue)
            
            # Check analysis.tool_results (alternative location)
            tool_results = analysis.get('tool_results', {})
            if isinstance(tool_results, dict):
                for tool_name, tool_data in tool_results.items():
                    if isinstance(tool_data, dict):
                        combined_tools[tool_name] = tool_data
            
            # Extract findings from analysis.findings
            findings = analysis.get('findings', [])
            if isinstance(findings, list):
                for f in findings:
                    if isinstance(f, dict) and f not in all_findings:
                        f['service'] = service_name
                        all_findings.append(f)
    
    # Update data with migrated services
    data['services'] = migrated_services
    
    # Update tools map if we found any
    if combined_tools:
        existing_tools = data.get('tools', {})
        if not existing_tools:
            data['tools'] = combined_tools
        else:
            # Merge, preferring new extractions
            existing_tools.update(combined_tools)
    
    # Update findings if we found any new ones
    if all_findings:
        existing_findings = data.get('findings', [])
        if not existing_findings:
            data['findings'] = all_findings
        elif len(all_findings) > len(existing_findings):
            data['findings'] = all_findings
    
    # Update summary
    summary = data.get('summary', {})
    summary['total_findings'] = len(data.get('findings', []))
    summary['tools_executed'] = len(data.get('tools', {}))
    summary['migrated'] = True
    summary['migration_date'] = datetime.now().isoformat()
    data['summary'] = summary
    
    # Add migration metadata
    metadata = data.get('metadata', {})
    metadata['migrated'] = True
    metadata['migration_script'] = 'migrate_pipeline_results.py'
    metadata['migration_date'] = datetime.now().isoformat()
    data['metadata'] = metadata
    
    return data


def process_result_file(file_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Process a single result file.
    
    Returns: (migrated: bool, message: str)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"JSON parse error: {e}"
    except Exception as e:
        return False, f"Read error: {e}"
    
    # Check if migration needed
    needs_fix, reason = needs_migration(data)
    if not needs_fix:
        return False, f"No migration needed: {reason}"
    
    if dry_run:
        return True, f"Would migrate: {reason}"
    
    # Create backup
    backup_path = file_path.with_suffix(file_path.suffix + BACKUP_SUFFIX)
    try:
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        return False, f"Backup failed: {e}"
    
    # Migrate
    try:
        migrated_data = migrate_result(data)
    except Exception as e:
        return False, f"Migration failed: {e}"
    
    # Write migrated data
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(migrated_data, f, indent=2)
    except Exception as e:
        return False, f"Write failed: {e}"
    
    return True, f"Migrated: {reason}"


def find_result_files(results_dir: Path) -> list:
    """Find all main result JSON files (excluding SARIF, services subdirs)."""
    result_files = []
    
    for model_dir in results_dir.iterdir():
        if not model_dir.is_dir():
            continue
        
        for app_dir in model_dir.iterdir():
            if not app_dir.is_dir():
                continue
            
            for task_dir in app_dir.iterdir():
                if not task_dir.is_dir() or not task_dir.name.startswith('task_'):
                    continue
                
                # Find main result JSON (not manifest, not sarif)
                for json_file in task_dir.glob('*.json'):
                    if json_file.name == 'manifest.json':
                        continue
                    if 'sarif' in json_file.name.lower():
                        continue
                    if json_file.suffix == BACKUP_SUFFIX:
                        continue
                    result_files.append(json_file)
    
    return result_files


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate pipeline results to correct format')
    parser.add_argument('--dry-run', action='store_true', help='Check files without modifying')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all files checked')
    args = parser.parse_args()
    
    print(f"Pipeline Results Migration Script")
    print(f"=" * 50)
    print(f"Results directory: {RESULTS_DIR}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE (will modify files)'}")
    print()
    
    if not RESULTS_DIR.exists():
        print(f"ERROR: Results directory not found: {RESULTS_DIR}")
        sys.exit(1)
    
    result_files = find_result_files(RESULTS_DIR)
    print(f"Found {len(result_files)} result files to check")
    print()
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    
    for file_path in result_files:
        rel_path = file_path.relative_to(RESULTS_DIR)
        migrated, message = process_result_file(file_path, dry_run=args.dry_run)
        
        if migrated:
            migrated_count += 1
            print(f"  [MIGRATE] {rel_path}: {message}")
        elif message.startswith("No migration"):
            skipped_count += 1
            if args.verbose:
                print(f"  [SKIP] {rel_path}: {message}")
        else:
            error_count += 1
            print(f"  [ERROR] {rel_path}: {message}")
    
    print()
    print(f"Summary:")
    print(f"  Migrated: {migrated_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")
    
    if args.dry_run and migrated_count > 0:
        print()
        print(f"Run without --dry-run to apply migrations")


if __name__ == '__main__':
    main()
