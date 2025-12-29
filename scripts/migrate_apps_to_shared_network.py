#!/usr/bin/env python3
"""
Migrate existing generated apps to use the shared thesis-apps-network.

This script:
1. Scans all generated apps' docker-compose.yml files
2. Removes the obsolete 'version' attribute
3. Changes from per-app isolated network to shared external network
4. Optionally creates the shared network if it doesn't exist

Usage:
    python scripts/migrate_apps_to_shared_network.py [--dry-run] [--create-network]
"""

import os
import re
import sys
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

APPS_DIR = PROJECT_ROOT / 'generated' / 'apps'
SHARED_NETWORK = 'thesis-apps-network'


def ensure_network_exists():
    """Create the shared Docker network if it doesn't exist."""
    try:
        result = subprocess.run(
            ['docker', 'network', 'ls', '--filter', f'name={SHARED_NETWORK}', '--format', '{{.Name}}'],
            capture_output=True, text=True, check=True
        )
        if SHARED_NETWORK not in result.stdout:
            print(f"Creating shared network: {SHARED_NETWORK}")
            subprocess.run(['docker', 'network', 'create', SHARED_NETWORK], check=True)
            print(f"  ✓ Network created")
        else:
            print(f"Shared network already exists: {SHARED_NETWORK}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Failed to create network: {e}")
        return False
    except FileNotFoundError:
        print("  ✗ Docker not found - skipping network creation")
        return False


def migrate_docker_compose(file_path: Path, dry_run: bool = False) -> tuple[bool, str]:
    """
    Migrate a docker-compose.yml file to use the shared network.
    
    Returns:
        tuple of (was_modified, message)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # Check if already migrated
        if 'thesis-apps-network' in content and 'external: true' in content:
            return False, "Already migrated"
        
        # 1. Remove version attribute (including any with '3.x')
        content = re.sub(r"^version:\s*['\"]?[\d.]+['\"]?\s*\n+", '', content, flags=re.MULTILINE)
        
        # 2. Replace network references in services section
        # Match "networks:" followed by "- app-network" in service definitions
        content = re.sub(
            r'(^\s+networks:\s*\n\s+- )app-network(\s*)$',
            r'\1thesis-apps-network\2',
            content,
            flags=re.MULTILINE
        )
        
        # 3. Replace the networks definition at the end
        # Match the entire networks block at root level
        networks_pattern = re.compile(
            r'^networks:\s*\n\s+app-network:\s*\n\s+driver:\s*bridge\s*$',
            re.MULTILINE
        )
        content = networks_pattern.sub(
            'networks:\n  thesis-apps-network:\n    external: true',
            content
        )
        
        # 4. Add comment at the top if not present
        if not content.startswith('#'):
            content = f"# Uses shared thesis-apps-network to prevent Docker network pool exhaustion\n\n{content}"
        
        if content == original_content:
            return False, "No changes needed (already correct format)"
        
        if dry_run:
            return True, "Would be modified (dry run)"
        
        file_path.write_text(content, encoding='utf-8')
        return True, "Migrated successfully"
        
    except Exception as e:
        return False, f"Error: {e}"


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Migrate apps to shared Docker network')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without modifying files')
    parser.add_argument('--create-network', action='store_true', help='Create the shared network if it does not exist')
    args = parser.parse_args()
    
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Migrating generated apps to shared network")
    print(f"Apps directory: {APPS_DIR}")
    print("-" * 60)
    
    if args.create_network and not args.dry_run:
        ensure_network_exists()
        print("-" * 60)
    
    if not APPS_DIR.exists():
        print("No generated apps directory found")
        return 0
    
    migrated = 0
    skipped = 0
    errors = 0
    
    # Find all docker-compose.yml files in generated apps
    for model_dir in APPS_DIR.iterdir():
        if not model_dir.is_dir():
            continue
            
        for app_dir in model_dir.iterdir():
            if not app_dir.is_dir():
                continue
                
            compose_file = app_dir / 'docker-compose.yml'
            if not compose_file.exists():
                continue
            
            relative_path = compose_file.relative_to(PROJECT_ROOT)
            modified, message = migrate_docker_compose(compose_file, args.dry_run)
            
            if modified:
                print(f"  ✓ {relative_path}: {message}")
                migrated += 1
            elif "Error" in message:
                print(f"  ✗ {relative_path}: {message}")
                errors += 1
            else:
                print(f"  - {relative_path}: {message}")
                skipped += 1
    
    print("-" * 60)
    print(f"Summary: {migrated} migrated, {skipped} skipped, {errors} errors")
    
    if errors > 0:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
