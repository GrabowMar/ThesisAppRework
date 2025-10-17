"""Fix port allocations and PROJECT_NAME in generated apps.

This script:
1. Re-scaffolds all generated apps with correct PROJECT_NAME
2. Uses PortAllocationService to get unique ports per model+app
3. Updates .env.example and docker-compose.yml files
4. Ensures no port conflicts
"""
import sys
from pathlib import Path
import re

# Add src to path
src_path = Path(__file__).resolve().parent.parent / 'src'
sys.path.insert(0, str(src_path))

from app import create_app
from app.services.simple_generation_service import SimpleGenerationService
from app.paths import GENERATED_APPS_DIR

def fix_all_generated_apps():
    """Fix all generated application configurations."""
    app = create_app()
    
    with app.app_context():
        service = SimpleGenerationService()
        
        fixed_count = 0
        error_count = 0
        
        print("\n🔧 Fixing Generated App Configurations")
        print("=" * 60)
        
        for model_dir in GENERATED_APPS_DIR.iterdir():
            if not model_dir.is_dir():
                continue
            
            model_slug = model_dir.name
            print(f"\n📁 Model: {model_slug}")
            
            # Process each app for this model
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                    continue
                
                # Extract app number
                match = re.match(r'app(\d+)', app_dir.name)
                if not match:
                    continue
                
                app_num = int(match.group(1))
                print(f"  🔹 {app_dir.name}: ", end="")
                
                try:
                    # Re-scaffold with correct ports and PROJECT_NAME
                    success = service.scaffold_app(model_slug, app_num, force=True)
                    
                    if success:
                        # Get the allocated ports
                        backend_port, frontend_port = service.get_ports(model_slug, app_num)
                        print(f"✅ Fixed (ports: {backend_port}/{frontend_port})")
                        fixed_count += 1
                    else:
                        print("❌ Failed to scaffold")
                        error_count += 1
                        
                except Exception as e:
                    print(f"❌ Error: {e}")
                    error_count += 1
        
        print("\n" + "=" * 60)
        print(f"✅ Fixed: {fixed_count} apps")
        if error_count > 0:
            print(f"❌ Errors: {error_count} apps")
        
        # Check for port conflicts
        from app.services.port_allocation_service import get_port_allocation_service
        port_service = get_port_allocation_service()
        conflicts = port_service.check_port_conflicts()
        
        if conflicts:
            print("\n⚠️  Port Conflicts Detected:")
            for conflict in conflicts:
                print(f"   {conflict}")
        else:
            print("\n✅ No port conflicts detected")

if __name__ == '__main__':
    fix_all_generated_apps()
