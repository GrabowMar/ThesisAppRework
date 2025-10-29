#!/usr/bin/env python3
"""Port Allocation Management Script

Provides tools for managing port allocations, diagnosing conflicts,
and cleaning up orphaned allocations.

Usage:
    python scripts/manage_ports.py list                    # List all allocations
    python scripts/manage_ports.py check                   # Check for conflicts
    python scripts/manage_ports.py cleanup [model]         # Remove orphaned allocations
    python scripts/manage_ports.py release <model> <app>   # Release specific allocation
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.services.port_allocation_service import get_port_allocation_service


def list_allocations():
    """List all port allocations."""
    app = create_app()
    with app.app_context():
        service = get_port_allocation_service()
        allocations = service.get_all_allocations()
        
        if not allocations:
            print("No port allocations found.")
            return
        
        print(f"\n{'Model':<40} {'App':<5} {'Backend':<8} {'Frontend':<8} {'Available':<10}")
        print("-" * 80)
        
        for alloc in allocations:
            print(f"{alloc['model']:<40} "
                  f"{alloc['app_num']:<5} "
                  f"{alloc['backend_port']:<8} "
                  f"{alloc['frontend_port']:<8} "
                  f"{'Yes' if alloc['is_available'] else 'No':<10}")
        
        print(f"\nTotal: {len(allocations)} allocation(s)")


def check_conflicts():
    """Check for port conflicts."""
    app = create_app()
    with app.app_context():
        service = get_port_allocation_service()
        conflicts = service.check_port_conflicts()
        
        if not conflicts:
            print("✓ No port conflicts found.")
            return 0
        
        print(f"✗ Found {len(conflicts)} conflict(s):\n")
        for conflict in conflicts:
            print(f"  - {conflict}")
        
        return 1


def cleanup_orphaned(model_name=None):
    """Clean up orphaned port allocations."""
    app = create_app()
    with app.app_context():
        service = get_port_allocation_service()
        
        if model_name:
            print(f"Cleaning up orphaned allocations for model: {model_name}")
        else:
            print("Cleaning up all orphaned allocations...")
        
        removed = service.cleanup_orphaned_allocations(model_name)
        
        if removed > 0:
            print(f"✓ Removed {removed} orphaned allocation(s)")
        else:
            print("✓ No orphaned allocations found")
        
        return 0


def release_allocation(model_name, app_num):
    """Release a specific port allocation."""
    app = create_app()
    with app.app_context():
        service = get_port_allocation_service()
        
        try:
            app_num = int(app_num)
        except ValueError:
            print(f"Error: app_num must be an integer, got: {app_num}")
            return 1
        
        print(f"Releasing ports for {model_name}/app{app_num}...")
        
        success = service.release_ports(model_name, app_num)
        
        if success:
            print(f"✓ Released ports for {model_name}/app{app_num}")
            return 0
        else:
            print(f"✗ No allocation found for {model_name}/app{app_num}")
            return 1


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    
    command = sys.argv[1]
    
    if command == 'list':
        list_allocations()
        return 0
    
    elif command == 'check':
        return check_conflicts()
    
    elif command == 'cleanup':
        model = sys.argv[2] if len(sys.argv) > 2 else None
        return cleanup_orphaned(model)
    
    elif command == 'release':
        if len(sys.argv) < 4:
            print("Error: release requires model and app_num arguments")
            print("Usage: python scripts/manage_ports.py release <model> <app_num>")
            return 1
        
        model = sys.argv[2]
        app_num = sys.argv[3]
        return release_allocation(model, app_num)
    
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        return 1


if __name__ == '__main__':
    sys.exit(main())
