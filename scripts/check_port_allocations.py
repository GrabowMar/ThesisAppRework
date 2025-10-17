"""Check port allocations in the database."""
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).resolve().parent.parent / 'src'
sys.path.insert(0, str(src_path))

from app import create_app
from app.services.port_allocation_service import get_port_allocation_service

def check_port_allocations():
    """Display all port allocations."""
    app = create_app()
    
    with app.app_context():
        port_service = get_port_allocation_service()
        
        # Get all allocations
        allocations = port_service.get_all_allocations()
        
        print("\n📊 Port Allocations Database")
        print("=" * 80)
        print(f"{'Model':<50} {'App':<6} {'Backend':<10} {'Frontend':<10}")
        print("=" * 80)
        
        for alloc in sorted(allocations, key=lambda x: (x['model'], x['app_num'])):
            print(f"{alloc['model']:<50} {alloc['app_num']:<6} {alloc['backend_port']:<10} {alloc['frontend_port']:<10}")
        
        print("=" * 80)
        print(f"Total allocations: {len(allocations)}")
        
        # Check for conflicts
        conflicts = port_service.check_port_conflicts()
        if conflicts:
            print("\n⚠️  Port Conflicts:")
            for conflict in conflicts:
                print(f"   {conflict}")
        else:
            print("\n✅ No port conflicts detected")

if __name__ == '__main__':
    check_port_allocations()
