#!/usr/bin/env python3
"""
Data Wipe Script
================
Clears database records and generated/results directories for fresh start.
"""

import sys
import os
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.app.factory import create_app
from src.app.extensions import db


def wipe_data(confirm: bool = False):
    """Wipe all app data: database records and file directories."""
    
    project_root = Path(__file__).parent.parent
    
    if not confirm:
        print("⚠️  This will DELETE all:")
        print("   - Pipeline executions")
        print("   - Analysis tasks")
        print("   - Generated applications records")
        print("   - generated/apps/ directory")
        print("   - results/ directory")
        print()
        response = input("Type 'YES' to confirm: ")
        if response != 'YES':
            print("Aborted.")
            return False
    
    app = create_app()
    
    with app.app_context():
        from src.app.models import (
            PipelineExecution, AnalysisTask, GeneratedApplication,
            PortConfiguration
        )
        
        # 1. Delete database records
        print("🗑️  Clearing database records...")
        
        # Delete in order to respect foreign keys
        deleted_pipelines = PipelineExecution.query.delete()
        print(f"   - Deleted {deleted_pipelines} pipeline executions")
        
        deleted_tasks = AnalysisTask.query.delete()
        print(f"   - Deleted {deleted_tasks} analysis tasks")
        
        deleted_apps = GeneratedApplication.query.delete()
        print(f"   - Deleted {deleted_apps} generated application records")
        
        # Reset port configurations to available
        ports_reset = PortConfiguration.query.update({'in_use': False, 'app_id': None})
        print(f"   - Reset {ports_reset} port configurations")
        
        db.session.commit()
        print("   ✅ Database cleared")
        
    # 2. Clear generated apps directory
    generated_apps_dir = project_root / 'generated' / 'apps'
    if generated_apps_dir.exists():
        print(f"🗑️  Clearing {generated_apps_dir}...")
        for item in generated_apps_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
                print(f"   - Removed {item.name}/")
        print("   ✅ Generated apps cleared")
    else:
        print(f"   ℹ️  {generated_apps_dir} does not exist")
    
    # 3. Clear results directory
    results_dir = project_root / 'results'
    if results_dir.exists():
        print(f"🗑️  Clearing {results_dir}...")
        for item in results_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
                print(f"   - Removed {item.name}/")
        print("   ✅ Results cleared")
    else:
        print(f"   ℹ️  {results_dir} does not exist")
    
    # 4. Stop any running containers from previous runs
    print("🐳 Cleaning up Docker containers...")
    import subprocess
    result = subprocess.run(
        ['docker', 'ps', '-a', '--filter', 'name=thesisapp-', '--format', '{{.Names}}'],
        capture_output=True, text=True
    )
    containers = [c for c in result.stdout.strip().split('\n') if c and 'thesisapp-' in c]
    # Filter out infrastructure containers
    app_containers = [c for c in containers if not any(x in c for x in ['analyzer', 'redis', 'web', 'celery', 'nginx', 'gateway'])]
    
    if app_containers:
        for container in app_containers:
            subprocess.run(['docker', 'rm', '-f', container], capture_output=True)
            print(f"   - Removed container: {container}")
        print(f"   ✅ Removed {len(app_containers)} app containers")
    else:
        print("   ℹ️  No app containers to remove")
    
    print()
    print("=" * 50)
    print("✅ DATA WIPE COMPLETE")
    print("=" * 50)
    return True


if __name__ == '__main__':
    confirm = '--confirm' in sys.argv or '-y' in sys.argv
    wipe_data(confirm=confirm)
