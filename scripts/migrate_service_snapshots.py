#!/usr/bin/env python3
"""
Migration script to regenerate service snapshot files with SARIF references.
This fixes the bloat caused by embedded SARIF data in service snapshots.

Regenerates all service snapshot files under results/**/task_*/services/
by extracting SARIF data to separate files and replacing with references.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import argparse
import shutil

def extract_sarif_from_result(result_data, service_name, sarif_dir):
    """
    Extract SARIF data from a service result and return data with references.
    
    Args:
        result_data: The service result dictionary
        service_name: Name of the service (e.g., 'static', 'dynamic')
        sarif_dir: Path to directory where SARIF files should be saved
        
    Returns:
        Modified result data with SARIF references instead of embedded data
    """
    modified = result_data.copy()
    sarif_files_created = []
    
    def process_tool_result(tool_name, tool_data, parent_path=""):
        """Recursively process tool results to extract SARIF."""
        if not isinstance(tool_data, dict):
            return tool_data
        
        result = tool_data.copy()
        
        # Check if this tool has embedded SARIF
        if 'sarif' in result and isinstance(result['sarif'], dict) and '$schema' in result['sarif']:
            # Extract SARIF to separate file
            sarif_filename = f"{service_name}_{tool_name}.sarif.json"
            sarif_path = sarif_dir / sarif_filename
            
            with open(sarif_path, 'w', encoding='utf-8') as f:
                json.dump(result['sarif'], f, indent=2)
            
            # Replace with reference
            result['sarif_file'] = f"sarif/{sarif_filename}"
            del result['sarif']
            sarif_files_created.append(sarif_filename)
        
        # Recursively process nested structures
        for key, value in result.items():
            if isinstance(value, dict):
                result[key] = process_tool_result(f"{tool_name}_{key}", value, f"{parent_path}.{key}" if parent_path else key)
        
        return result
    
    # Process results structure
    if 'results' in modified and 'analysis' in modified['results']:
        analysis = modified['results']['analysis']
        
        if 'results' in analysis:
            results_section = analysis['results']
            
            # Process each language section (python, javascript, css, etc.)
            for lang_key, lang_data in results_section.items():
                if isinstance(lang_data, dict) and lang_key != '_metadata':
                    for tool_name, tool_data in lang_data.items():
                        if tool_name != '_metadata':
                            lang_data[tool_name] = process_tool_result(tool_name, tool_data)
        
        # Process sarif_export if present (consolidated SARIF)
        if 'sarif_export' in analysis and isinstance(analysis['sarif_export'], dict):
            sarif_filename = f"{service_name}_consolidated.sarif.json"
            sarif_path = sarif_dir / sarif_filename
            
            with open(sarif_path, 'w', encoding='utf-8') as f:
                json.dump(analysis['sarif_export'], f, indent=2)
            
            analysis['sarif_export'] = {"sarif_file": f"sarif/{sarif_filename}"}
            sarif_files_created.append(sarif_filename)
    
    return modified, sarif_files_created

def migrate_service_snapshot(snapshot_path, dry_run=False):
    """
    Migrate a single service snapshot file.
    
    Args:
        snapshot_path: Path to service snapshot JSON file
        dry_run: If True, only analyze without making changes
        
    Returns:
        Dictionary with migration results
    """
    try:
        # Read current snapshot
        with open(snapshot_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        original_size = snapshot_path.stat().st_size
        
        # Extract service name from metadata or filename
        service_name = data.get('metadata', {}).get('service_name', 'unknown')
        if service_name == 'unknown':
            # Try to extract from filename (e.g., "model_app1_static.json" -> "static")
            filename = snapshot_path.stem
            parts = filename.split('_')
            if len(parts) >= 3:
                service_name = parts[-1]
        
        # Determine SARIF directory
        task_dir = snapshot_path.parent.parent
        sarif_dir = task_dir / "sarif"
        sarif_dir.mkdir(exist_ok=True)
        
        # Check if already migrated (has sarif_file references)
        has_refs = "sarif_file" in json.dumps(data)
        if has_refs and not dry_run:
            return {
                'path': str(snapshot_path),
                'status': 'skipped',
                'reason': 'already_migrated',
                'original_size': original_size
            }
        
        if dry_run:
            return {
                'path': str(snapshot_path),
                'status': 'needs_migration',
                'original_size': original_size,
                'service_name': service_name
            }
        
        # Create backup
        backup_path = snapshot_path.with_suffix('.json.backup')
        shutil.copy2(snapshot_path, backup_path)
        
        # Extract SARIF and modify data
        modified_data, sarif_files = extract_sarif_from_result(data, service_name, sarif_dir)
        
        # Write modified snapshot
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(modified_data, f, indent=2, default=str)
        
        new_size = snapshot_path.stat().st_size
        size_reduction = original_size - new_size
        size_reduction_pct = (size_reduction / original_size * 100) if original_size > 0 else 0
        
        return {
            'path': str(snapshot_path),
            'status': 'migrated',
            'service_name': service_name,
            'original_size': original_size,
            'new_size': new_size,
            'size_reduction': size_reduction,
            'size_reduction_pct': size_reduction_pct,
            'sarif_files_created': sarif_files,
            'backup_path': str(backup_path)
        }
        
    except Exception as e:
        return {
            'path': str(snapshot_path),
            'status': 'error',
            'error': str(e)
        }

def find_service_snapshots(results_dir):
    """Find all service snapshot files in results directory."""
    results_path = Path(results_dir)
    
    if not results_path.exists():
        return []
    
    # Find all files matching pattern: results/**/task_*/services/*.json
    snapshots = []
    for task_dir in results_path.glob("**/task_*"):
        services_dir = task_dir / "services"
        if services_dir.exists():
            for json_file in services_dir.glob("*.json"):
                snapshots.append(json_file)
    
    return snapshots

def main():
    parser = argparse.ArgumentParser(description='Migrate service snapshots to use SARIF references')
    parser.add_argument('--dry-run', action='store_true', help='Analyze without making changes')
    parser.add_argument('--results-dir', default='results', help='Path to results directory')
    args = parser.parse_args()
    
    print("=" * 80)
    print("Service Snapshot Migration - SARIF Extraction")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes)' if args.dry_run else 'LIVE (will modify files)'}")
    print(f"Results directory: {args.results_dir}")
    print()
    
    # Find all service snapshots
    snapshots = find_service_snapshots(args.results_dir)
    print(f"📁 Found {len(snapshots)} service snapshot files")
    print()
    
    if not snapshots:
        print("No service snapshots found.")
        return 0
    
    # Migrate each snapshot
    results = []
    total_size_before = 0
    total_size_after = 0
    
    for i, snapshot_path in enumerate(snapshots, 1):
        try:
            rel_path = snapshot_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = snapshot_path
        print(f"[{i}/{len(snapshots)}] Processing: {rel_path}")
        result = migrate_service_snapshot(snapshot_path, dry_run=args.dry_run)
        results.append(result)
        
        if result['status'] == 'migrated':
            total_size_before += result['original_size']
            total_size_after += result['new_size']
            print(f"  ✅ Migrated: {result['size_reduction'] / (1024*1024):.2f} MB saved ({result['size_reduction_pct']:.1f}%)")
            print(f"     SARIF files: {', '.join(result['sarif_files_created'])}")
        elif result['status'] == 'skipped':
            print(f"  ⏭️  Skipped: {result['reason']}")
        elif result['status'] == 'needs_migration':
            print(f"  📋 Needs migration: {result['original_size'] / (1024*1024):.2f} MB")
        elif result['status'] == 'error':
            print(f"  ❌ Error: {result['error']}")
        print()
    
    # Summary
    print("=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    
    migrated = [r for r in results if r['status'] == 'migrated']
    skipped = [r for r in results if r['status'] == 'skipped']
    needs_migration = [r for r in results if r['status'] == 'needs_migration']
    errors = [r for r in results if r['status'] == 'error']
    
    print(f"✅ Migrated: {len(migrated)}")
    print(f"⏭️  Skipped: {len(skipped)}")
    print(f"📋 Needs migration: {len(needs_migration)}")
    print(f"❌ Errors: {len(errors)}")
    print()
    
    if migrated:
        total_reduction = total_size_before - total_size_after
        total_reduction_pct = (total_reduction / total_size_before * 100) if total_size_before > 0 else 0
        print(f"💾 Total size reduction: {total_reduction / (1024*1024):.2f} MB ({total_reduction_pct:.1f}%)")
        print(f"   Before: {total_size_before / (1024*1024):.2f} MB")
        print(f"   After: {total_size_after / (1024*1024):.2f} MB")
        print()
    
    if args.dry_run and needs_migration:
        print("💡 Run without --dry-run to perform the migration")
    
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(main())
