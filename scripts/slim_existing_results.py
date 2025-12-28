#!/usr/bin/env python3
"""
Slim Existing Results
=====================

Retroactively process existing bloated result JSON files to reduce their size.

Operations:
1. Remove 'payload' duplication in services (keep only 'analysis')
2. Extract 'sarif_export' to separate files
3. Extract tool 'sarif' and 'output' (if large) to separate files
4. Strip SARIF rule definitions (keep only id, name, shortDescription)
5. Remove top-level 'findings' array (data is in tools/services)
6. Strip duplicate results between analysis and payload

Usage:
    python scripts/slim_existing_results.py [--dry-run] [--backup]
    
Options:
    --dry-run    Show what would be changed without modifying files
    --backup     Create .bak files before modifying (default: True)
    --no-backup  Skip backup creation
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

RESULTS_DIR = PROJECT_ROOT / 'results'

# Threshold for extracting to separate file (500KB)
EXTRACTION_THRESHOLD_KB = 500


def extract_sarif_export_to_file(data: dict, sarif_dir: Path, prefix: str, dry_run: bool = False) -> dict:
    """Extract sarif_export data to a separate file and replace with reference.
    
    Args:
        data: Dict containing 'sarif_export' key
        sarif_dir: Directory to save SARIF files
        prefix: Prefix for the filename (e.g., 'static')
        dry_run: If True, don't create files
        
    Returns:
        Modified data dict with sarif_export replaced by reference
    """
    if 'sarif_export' not in data:
        return data
    
    sarif_export = data['sarif_export']
    if not isinstance(sarif_export, dict):
        return data
    
    # Already a reference?
    if 'sarif_file' in sarif_export and len(sarif_export) <= 2:
        return data
    
    # Check size - only extract if large
    sarif_json = json.dumps(sarif_export, default=str)
    size_kb = len(sarif_json.encode('utf-8')) / 1024
    
    if size_kb < EXTRACTION_THRESHOLD_KB:
        # Just strip rules in place
        return data
    
    # Extract to file
    sarif_filename = f"{prefix}_sarif_export.sarif.json"
    sarif_path = sarif_dir / sarif_filename
    
    if not dry_run:
        sarif_dir.mkdir(parents=True, exist_ok=True)
        with open(sarif_path, 'w', encoding='utf-8') as f:
            json.dump(sarif_export, f, indent=2, default=str)
    
    # Replace with reference
    data['sarif_export'] = {
        'sarif_file': f"sarif/{sarif_filename}",
        'extracted_size_kb': round(size_kb, 2)
    }
    
    return data


def extract_tool_sarif_to_file(tool_data: dict, sarif_dir: Path, tool_name: str, dry_run: bool = False) -> tuple:
    """Extract tool's sarif/output data to separate files if large.
    
    Args:
        tool_data: Tool data dict
        sarif_dir: Directory to save files
        tool_name: Name of the tool
        dry_run: If True, don't create files
        
    Returns:
        Tuple of (modified tool_data, bytes_saved)
    """
    bytes_saved = 0
    
    # Extract 'sarif' key
    if 'sarif' in tool_data and isinstance(tool_data['sarif'], dict):
        sarif_data = tool_data['sarif']
        
        # Already a reference?
        if 'sarif_file' not in sarif_data:
            sarif_json = json.dumps(sarif_data, default=str)
            size_kb = len(sarif_json.encode('utf-8')) / 1024
            
            if size_kb >= EXTRACTION_THRESHOLD_KB:
                sarif_filename = f"tool_{tool_name}.sarif.json"
                sarif_path = sarif_dir / sarif_filename
                
                if not dry_run:
                    sarif_dir.mkdir(parents=True, exist_ok=True)
                    with open(sarif_path, 'w', encoding='utf-8') as f:
                        json.dump(sarif_data, f, indent=2, default=str)
                
                bytes_saved += len(sarif_json.encode('utf-8'))
                tool_data['sarif'] = {
                    'sarif_file': f"sarif/{sarif_filename}",
                    'extracted_size_kb': round(size_kb, 2)
                }
    
    # Extract 'output' key if it's large (often duplicate of sarif)
    if 'output' in tool_data:
        output_data = tool_data['output']
        if output_data:
            output_json = json.dumps(output_data, default=str) if not isinstance(output_data, str) else output_data
            size_kb = len(output_json.encode('utf-8')) / 1024
            
            if size_kb >= EXTRACTION_THRESHOLD_KB:
                output_filename = f"tool_{tool_name}_output.json"
                output_path = sarif_dir / output_filename
                
                if not dry_run:
                    sarif_dir.mkdir(parents=True, exist_ok=True)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        if isinstance(output_data, str):
                            f.write(output_data)
                        else:
                            json.dump(output_data, f, indent=2, default=str)
                
                bytes_saved += len(output_json.encode('utf-8'))
                tool_data['output'] = {
                    'output_file': f"sarif/{output_filename}",
                    'extracted_size_kb': round(size_kb, 2)
                }
    
    return tool_data, bytes_saved


def remove_payload_duplication(services: dict) -> tuple:
    """Remove 'payload' key from services, keeping only 'analysis'.
    
    Args:
        services: Services dict with potentially duplicated data
        
    Returns:
        Tuple of (cleaned services, bytes_saved)
    """
    bytes_saved = 0
    
    for service_name, service_data in services.items():
        if not isinstance(service_data, dict):
            continue
        
        # Check if both 'payload' and 'analysis' exist
        if 'payload' in service_data and 'analysis' in service_data:
            payload_json = json.dumps(service_data['payload'], default=str)
            bytes_saved += len(payload_json.encode('utf-8'))
            del service_data['payload']
        elif 'payload' in service_data and 'analysis' not in service_data:
            # Only payload exists - rename to analysis
            service_data['analysis'] = service_data['payload']
            del service_data['payload']
    
    return services, bytes_saved


def strip_sarif_rules(sarif_data: dict, aggressive: bool = False) -> dict:
    """Strip bulky rule definitions from SARIF, keeping only essential fields.
    
    Args:
        sarif_data: SARIF data dict
        aggressive: If True, strip ALL rules regardless of count. If False, only strip if >10 rules.
    """
    if not isinstance(sarif_data, dict):
        return sarif_data
    
    runs = sarif_data.get('runs', [])
    for run in runs:
        if not isinstance(run, dict):
            continue
        
        # Handle nested SARIF (sarif_export can have runs containing runs)
        if 'runs' in run:
            strip_sarif_rules(run, aggressive)
            
        tool = run.get('tool', {})
        if not isinstance(tool, dict):
            continue
        driver = tool.get('driver', {})
        if not isinstance(driver, dict):
            continue
        
        rules = driver.get('rules', [])
        # In aggressive mode, strip all rules. Otherwise only if >10
        if rules and (aggressive or len(rules) > 10):
            slim_rules = []
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                slim_rule = {'id': rule.get('id', '')}
                if rule.get('name'):
                    slim_rule['name'] = rule['name']
                if rule.get('shortDescription'):
                    short_desc = rule['shortDescription']
                    if isinstance(short_desc, dict) and 'text' in short_desc:
                        text = short_desc['text'][:200] if len(short_desc.get('text', '')) > 200 else short_desc['text']
                        slim_rule['shortDescription'] = {'text': text}
                slim_rules.append(slim_rule)
            driver['rules'] = slim_rules
    
    return sarif_data


def strip_all_sarif_rules_recursive(data, stats: dict, aggressive: bool = False):
    """Recursively find and strip ANY tool.driver.rules pattern throughout the structure.
    
    Args:
        data: Data structure to process
        stats: Stats dict to update
        aggressive: If True, strip ALL rules regardless of count
    """
    if isinstance(data, dict):
        # Check if this dict has tool.driver.rules pattern
        if 'tool' in data and isinstance(data.get('tool'), dict):
            driver = data['tool'].get('driver', {})
            if isinstance(driver, dict) and 'rules' in driver:
                rules = driver['rules']
                # In aggressive mode, strip all rules. Otherwise only if >10
                if isinstance(rules, list) and (aggressive or len(rules) > 10):
                    slim_rules = []
                    for rule in rules:
                        if not isinstance(rule, dict):
                            continue
                        slim_rule = {'id': rule.get('id', '')}
                        if rule.get('name'):
                            slim_rule['name'] = rule['name']
                        if rule.get('shortDescription'):
                            short_desc = rule['shortDescription']
                            if isinstance(short_desc, dict) and 'text' in short_desc:
                                text = short_desc['text'][:200]
                                slim_rule['shortDescription'] = {'text': text}
                        slim_rules.append(slim_rule)
                    driver['rules'] = slim_rules
                    stats['rules_stripped'] += 1
        
        # Recurse into all dict values
        for key, value in data.items():
            strip_all_sarif_rules_recursive(value, stats, aggressive)
            
    elif isinstance(data, list):
        for item in data:
            strip_all_sarif_rules_recursive(item, stats, aggressive)


def process_sarif_in_structure(data: dict, sarif_dir: Path, stats: dict, aggressive: bool = False) -> dict:
    """Recursively find and process SARIF data in the structure."""
    if not isinstance(data, dict):
        return data
    
    result = {}
    for key, value in data.items():
        if key == 'sarif' and isinstance(value, dict):
            # Check if already a file reference
            if 'sarif_file' in value:
                result[key] = value
                continue
            
            # Strip rules and potentially extract
            stripped = strip_sarif_rules(value, aggressive)
            stats['sarif_stripped'] += 1
            result[key] = stripped
            
        elif isinstance(value, dict):
            result[key] = process_sarif_in_structure(value, sarif_dir, stats, aggressive)
        elif isinstance(value, list):
            result[key] = [
                process_sarif_in_structure(item, sarif_dir, stats, aggressive) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


def slim_result_file(file_path: Path, dry_run: bool = False, backup: bool = True, aggressive: bool = True) -> dict:
    """Process a single result file and return stats.
    
    Args:
        file_path: Path to result JSON file
        dry_run: If True, don't modify files
        backup: If True, create .bak files
        aggressive: If True, strip ALL SARIF rules (default True for max reduction)
    """
    stats = {
        'original_size': file_path.stat().st_size,
        'new_size': 0,
        'sarif_stripped': 0,
        'rules_stripped': 0,
        'findings_removed': False,
        'empty_issues_removed': 0,
        'payload_removed': 0,
        'sarif_extracted': 0,
        'tool_sarif_extracted': 0,
        'bytes_saved_extraction': 0,
        'error': None
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        stats['error'] = f"Failed to read: {e}"
        return stats
    
    # Track if we made changes
    modified = False
    sarif_dir = file_path.parent / 'sarif'
    
    # 0. Remove 'payload' duplication in services (MAJOR savings)
    services = data.get('services', {})
    if isinstance(services, dict):
        services, payload_bytes_saved = remove_payload_duplication(services)
        if payload_bytes_saved > 0:
            stats['payload_removed'] = payload_bytes_saved
            stats['bytes_saved_extraction'] += payload_bytes_saved
            modified = True
    
    # 1. Extract sarif_export from services.*.analysis
    for service_name, service_data in services.items():
        if not isinstance(service_data, dict):
            continue
        
        analysis = service_data.get('analysis', {})
        if isinstance(analysis, dict) and 'sarif_export' in analysis:
            service_data['analysis'] = extract_sarif_export_to_file(
                analysis, sarif_dir, f"{service_name}", dry_run
            )
            if 'sarif_file' in service_data['analysis'].get('sarif_export', {}):
                stats['sarif_extracted'] += 1
                modified = True
    
    # 2. Extract large tool sarif/output from tools section
    tools = data.get('tools', {})
    if isinstance(tools, dict):
        for tool_name, tool_data in tools.items():
            if isinstance(tool_data, dict):
                tools[tool_name], bytes_saved = extract_tool_sarif_to_file(
                    tool_data, sarif_dir, tool_name, dry_run
                )
                if bytes_saved > 0:
                    stats['tool_sarif_extracted'] += 1
                    stats['bytes_saved_extraction'] += bytes_saved
                    modified = True
    
    # 3. Remove top-level 'findings' array if present
    if 'findings' in data:
        del data['findings']
        stats['findings_removed'] = True
        modified = True
    
    # Also check in results.findings (nested structure)
    if 'results' in data and isinstance(data['results'], dict):
        if 'findings' in data['results']:
            del data['results']['findings']
            stats['findings_removed'] = True
            modified = True
    
    # 4. Clean up empty issues arrays in tools section
    for tool_name, tool_data in tools.items():
        if isinstance(tool_data, dict) and 'issues' in tool_data:
            issues = tool_data.get('issues', [])
            if isinstance(issues, list) and len(issues) == 0:
                del tool_data['issues']
                stats['empty_issues_removed'] += 1
                modified = True
    
    # 5. Process remaining inline SARIF data throughout the structure
    data = process_sarif_in_structure(data, sarif_dir, stats, aggressive)
    if stats['sarif_stripped'] > 0:
        modified = True
    
    # 6. Strip any remaining tool.driver.rules patterns (deeply nested SARIF)
    rule_stats = {'rules_stripped': 0}
    strip_all_sarif_rules_recursive(data, rule_stats, aggressive)
    stats['rules_stripped'] = rule_stats['rules_stripped']
    if rule_stats['rules_stripped'] > 0:
        modified = True
    
    if not modified:
        stats['new_size'] = stats['original_size']
        return stats
    
    if dry_run:
        # Estimate new size
        new_json = json.dumps(data, indent=2, default=str)
        stats['new_size'] = len(new_json.encode('utf-8'))
        return stats
    
    # Create backup
    if backup:
        backup_path = file_path.with_suffix('.json.bak')
        if not backup_path.exists():
            shutil.copy2(file_path, backup_path)
    
    # Write slimmed file
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        stats['new_size'] = file_path.stat().st_size
    except Exception as e:
        stats['error'] = f"Failed to write: {e}"
    
    return stats


def find_result_files(results_dir: Path) -> list:
    """Find all consolidated result JSON files."""
    files = []
    
    for model_dir in results_dir.iterdir():
        if not model_dir.is_dir():
            continue
        
        for app_dir in model_dir.iterdir():
            if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                continue
            
            # Check task directories
            for task_dir in app_dir.iterdir():
                if not task_dir.is_dir() or not task_dir.name.startswith('task_'):
                    continue
                
                # Find main result JSON (not manifest, not sarif, not service snapshots)
                for json_file in task_dir.glob('*.json'):
                    if json_file.name == 'manifest.json':
                        continue
                    if json_file.name.endswith('.bak'):
                        continue
                    if json_file.parent.name == 'sarif':
                        continue
                    if json_file.parent.name == 'services':
                        continue
                    
                    files.append(json_file)
    
    return files


def find_sarif_files(results_dir: Path) -> list:
    """Find all extracted SARIF files."""
    files = []
    
    for sarif_file in results_dir.rglob('sarif/*.sarif.json'):
        if sarif_file.name.endswith('.bak'):
            continue
        files.append(sarif_file)
    
    return files


def find_service_files(results_dir: Path) -> list:
    """Find all service snapshot JSON files."""
    files = []
    
    for service_file in results_dir.rglob('services/*.json'):
        if service_file.name.endswith('.bak'):
            continue
        files.append(service_file)
    
    return files


def slim_service_file(file_path: Path, dry_run: bool = False, backup: bool = True, aggressive: bool = True) -> dict:
    """Process a service snapshot file and strip SARIF rules.
    
    Args:
        file_path: Path to service JSON file
        dry_run: If True, don't modify files
        backup: If True, create .bak files
        aggressive: If True, strip ALL SARIF rules
    """
    stats = {
        'original_size': file_path.stat().st_size,
        'new_size': 0,
        'sarif_stripped': 0,
        'rules_stripped': 0,
        'error': None
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        stats['error'] = f"Failed to read: {e}"
        return stats
    
    # Process SARIF throughout the structure (keys named 'sarif')
    sarif_dir = file_path.parent.parent / 'sarif'
    data = process_sarif_in_structure(data, sarif_dir, stats, aggressive)
    
    # Strip any remaining tool.driver.rules patterns (deeply nested)
    rule_stats = {'rules_stripped': 0}
    strip_all_sarif_rules_recursive(data, rule_stats, aggressive)
    stats['rules_stripped'] = rule_stats['rules_stripped']
    
    if stats['sarif_stripped'] == 0 and stats['rules_stripped'] == 0:
        stats['new_size'] = stats['original_size']
        return stats
    
    if dry_run:
        new_json = json.dumps(data, indent=2, default=str)
        stats['new_size'] = len(new_json.encode('utf-8'))
        return stats
    
    if backup:
        backup_path = file_path.with_suffix('.json.bak')
        if not backup_path.exists():
            shutil.copy2(file_path, backup_path)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        stats['new_size'] = file_path.stat().st_size
    except Exception as e:
        stats['error'] = f"Failed to write: {e}"
    
    return stats


def slim_sarif_file(file_path: Path, dry_run: bool = False, backup: bool = True, aggressive: bool = True) -> dict:
    """Process a single SARIF file and strip rules.
    
    Args:
        file_path: Path to SARIF JSON file
        dry_run: If True, don't modify files
        backup: If True, create .bak files
        aggressive: If True, strip ALL rules regardless of count
    """
    stats = {
        'original_size': file_path.stat().st_size,
        'new_size': 0,
        'rules_stripped': False,
        'error': None
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        stats['error'] = f"Failed to read: {e}"
        return stats
    
    # Count original rules
    original_rules = 0
    for run in data.get('runs', []):
        rules = run.get('tool', {}).get('driver', {}).get('rules', [])
        original_rules += len(rules) if isinstance(rules, list) else 0
    
    # Strip rules (always strip in aggressive mode, otherwise only if >10)
    stripped = strip_sarif_rules(data, aggressive)
    
    # Count new rules
    new_rules = 0
    for run in stripped.get('runs', []):
        rules = run.get('tool', {}).get('driver', {}).get('rules', [])
        new_rules += len(rules) if isinstance(rules, list) else 0
    
    # Skip if no change (non-aggressive mode and <=10 rules)
    if not aggressive and original_rules <= 10:
        stats['new_size'] = stats['original_size']
        return stats
    
    stats['rules_stripped'] = True
    
    if dry_run:
        new_json = json.dumps(stripped, indent=2, default=str)
        stats['new_size'] = len(new_json.encode('utf-8'))
        return stats
    
    if backup:
        backup_path = file_path.with_suffix('.json.bak')
        if not backup_path.exists():
            shutil.copy2(file_path, backup_path)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(stripped, f, indent=2, default=str)
        stats['new_size'] = file_path.stat().st_size
    except Exception as e:
        stats['error'] = f"Failed to write: {e}"
    
    return stats


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def cleanup_backup_files(results_dir: Path, dry_run: bool = False) -> dict:
    """Remove all .bak files created during slimming."""
    stats = {'count': 0, 'size': 0}
    
    for bak_file in results_dir.rglob('*.bak'):
        stats['count'] += 1
        stats['size'] += bak_file.stat().st_size
        if not dry_run:
            bak_file.unlink()
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Slim existing result JSON files')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without modifying')
    parser.add_argument('--backup', dest='backup', action='store_true', default=True, help='Create .bak files')
    parser.add_argument('--no-backup', dest='backup', action='store_false', help='Skip backup creation')
    parser.add_argument('--cleanup-backups', action='store_true', help='Remove all .bak files instead of slimming')
    parser.add_argument('--conservative', action='store_true', help='Only strip rules if >10 (default: strip ALL)')
    args = parser.parse_args()
    
    if not RESULTS_DIR.exists():
        print(f"Results directory not found: {RESULTS_DIR}")
        return 1
    
    # Handle backup cleanup mode
    if args.cleanup_backups:
        print(f"Cleaning up backup files in: {RESULTS_DIR}")
        stats = cleanup_backup_files(RESULTS_DIR, dry_run=args.dry_run)
        print(f"Found {stats['count']} backup file(s) totaling {format_size(stats['size'])}")
        if args.dry_run:
            print("[DRY RUN] No files were deleted.")
        else:
            print(f"Deleted {stats['count']} backup file(s), freed {format_size(stats['size'])}")
        return 0
    
    aggressive = not args.conservative
    
    print(f"Scanning for result files in: {RESULTS_DIR}")
    print(f"Mode: {'conservative (>10 rules)' if args.conservative else 'aggressive (ALL rules)'}")
    files = find_result_files(RESULTS_DIR)
    sarif_files = find_sarif_files(RESULTS_DIR)
    service_files = find_service_files(RESULTS_DIR)
    
    if not files and not sarif_files and not service_files:
        print("No result files found.")
        return 0
    
    print(f"Found {len(files)} result file(s), {len(sarif_files)} SARIF file(s), {len(service_files)} service file(s)")
    if args.dry_run:
        print("DRY RUN - no files will be modified\n")
    
    total_original = 0
    total_new = 0
    total_sarif_stripped = 0
    total_rules_stripped = 0
    total_findings_removed = 0
    errors = 0
    
    # Process main result files
    for file_path in files:
        rel_path = file_path.relative_to(RESULTS_DIR)
        stats = slim_result_file(file_path, dry_run=args.dry_run, backup=args.backup, aggressive=aggressive)
        
        if stats['error']:
            print(f"  ✗ {rel_path}: {stats['error']}")
            errors += 1
            continue
        
        total_original += stats['original_size']
        total_new += stats['new_size']
        
        has_changes = (stats['sarif_stripped'] > 0 or stats.get('rules_stripped', 0) > 0 or 
                      stats['findings_removed'] or stats.get('empty_issues_removed', 0) > 0 or
                      stats.get('payload_removed', 0) > 0 or stats.get('sarif_extracted', 0) > 0 or 
                      stats.get('tool_sarif_extracted', 0) > 0)
        if has_changes:
            reduction = (1 - stats['new_size'] / stats['original_size']) * 100 if stats['original_size'] > 0 else 0
            status = []
            if stats.get('payload_removed', 0) > 0:
                status.append(f"payload removed ({format_size(stats['payload_removed'])})")
            if stats.get('sarif_extracted', 0) > 0:
                status.append(f"{stats['sarif_extracted']} sarif_export extracted")
            if stats.get('tool_sarif_extracted', 0) > 0:
                status.append(f"{stats['tool_sarif_extracted']} tool SARIF extracted")
            if stats['findings_removed']:
                status.append("findings removed")
                total_findings_removed += 1
            if stats['sarif_stripped'] > 0:
                status.append(f"{stats['sarif_stripped']} SARIF stripped")
                total_sarif_stripped += stats['sarif_stripped']
            if stats.get('rules_stripped', 0) > 0:
                status.append(f"{stats['rules_stripped']} rule sets stripped")
                total_rules_stripped += stats['rules_stripped']
            if stats.get('empty_issues_removed', 0) > 0:
                status.append(f"{stats['empty_issues_removed']} empty issues removed")
            
            print(f"  ✓ {rel_path}")
            print(f"    {format_size(stats['original_size'])} → {format_size(stats['new_size'])} ({reduction:.1f}% reduction)")
            print(f"    {', '.join(status)}")
        else:
            print(f"  - {rel_path}: already slim ({format_size(stats['original_size'])})")
    
    # Process service files
    service_original = 0
    service_new = 0
    service_stripped_count = 0
    
    if service_files:
        print(f"\nProcessing {len(service_files)} service file(s)...")
        for file_path in service_files:
            rel_path = file_path.relative_to(RESULTS_DIR)
            stats = slim_service_file(file_path, dry_run=args.dry_run, backup=args.backup, aggressive=aggressive)
            
            if stats['error']:
                print(f"  ✗ {rel_path}: {stats['error']}")
                errors += 1
                continue
            
            service_original += stats['original_size']
            service_new += stats['new_size']
            
            has_changes = stats['sarif_stripped'] > 0 or stats.get('rules_stripped', 0) > 0
            if has_changes:
                reduction = (1 - stats['new_size'] / stats['original_size']) * 100 if stats['original_size'] > 0 else 0
                service_stripped_count += stats['sarif_stripped'] + stats.get('rules_stripped', 0)
                print(f"  ✓ {rel_path}: {format_size(stats['original_size'])} → {format_size(stats['new_size'])} ({reduction:.1f}%)")
            else:
                print(f"  - {rel_path}: no SARIF to strip ({format_size(stats['original_size'])})")
    
    # Process SARIF files
    sarif_original = 0
    sarif_new = 0
    sarif_stripped_count = 0
    
    if sarif_files:
        print(f"\nProcessing {len(sarif_files)} SARIF file(s)...")
        for file_path in sarif_files:
            rel_path = file_path.relative_to(RESULTS_DIR)
            stats = slim_sarif_file(file_path, dry_run=args.dry_run, backup=args.backup, aggressive=aggressive)
            
            if stats['error']:
                print(f"  ✗ {rel_path}: {stats['error']}")
                errors += 1
                continue
            
            sarif_original += stats['original_size']
            sarif_new += stats['new_size']
            
            if stats['rules_stripped']:
                reduction = (1 - stats['new_size'] / stats['original_size']) * 100 if stats['original_size'] > 0 else 0
                sarif_stripped_count += 1
                print(f"  ✓ {rel_path}: {format_size(stats['original_size'])} → {format_size(stats['new_size'])} ({reduction:.1f}%)")
    
    total_original += sarif_original + service_original
    total_new += sarif_new + service_new
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Result files processed: {len(files)}")
    print(f"Service files processed: {len(service_files)} ({service_stripped_count} SARIF sets stripped)")
    print(f"SARIF files processed: {len(sarif_files)} ({sarif_stripped_count} slimmed)")
    print(f"Errors: {errors}")
    print(f"Findings arrays removed: {total_findings_removed}")
    print(f"Total SARIF rule sets stripped: {total_sarif_stripped + sarif_stripped_count + service_stripped_count}")
    
    if total_original > 0:
        reduction = (1 - total_new / total_original) * 100
        print(f"\nSpace: {format_size(total_original)} → {format_size(total_new)}")
        print(f"Total reduction: {format_size(total_original - total_new)} ({reduction:.1f}%)")
    
    if args.dry_run:
        print("\n[DRY RUN] No files were modified. Run without --dry-run to apply changes.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
