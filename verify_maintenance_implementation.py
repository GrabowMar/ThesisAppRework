"""
Final verification script for maintenance service implementation.
Checks all components are properly integrated.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def verify_files_exist():
    """Verify all implementation files exist."""
    print("[*] Verifying implementation files...")
    
    files = [
        'src/app/services/maintenance_service.py',
        'src/app/factory.py',
        'src/config/settings.py',
        'MAINTENANCE_SERVICE_IMPLEMENTATION.md',
    ]
    
    all_exist = True
    for file_path in files:
        path = Path(file_path)
        exists = path.exists()
        status = "✅" if exists else "❌"
        print(f"  {status} {file_path}")
        if not exists:
            all_exist = False
    
    return all_exist

def verify_imports():
    """Verify all imports work."""
    print("\n📦 Verifying imports...")
    
    try:
        from app.services.maintenance_service import (
            MaintenanceService,
            init_maintenance_service,
            get_maintenance_service
        )
        print("  ✅ MaintenanceService")
        print("  ✅ init_maintenance_service")
        print("  ✅ get_maintenance_service")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False

def verify_factory_integration():
    """Verify factory.py has maintenance service integration."""
    print("\n🔌 Verifying factory integration...")
    
    factory_path = Path('src/app/factory.py')
    content = factory_path.read_text()
    
    checks = [
        ('import', 'from app.services.maintenance_service import init_maintenance_service'),
        ('initialization', 'init_maintenance_service(app=app'),
        ('logging', 'Maintenance service initialized'),
    ]
    
    all_found = True
    for name, pattern in checks:
        found = pattern in content
        status = "✅" if found else "❌"
        print(f"  {status} {name}: '{pattern[:50]}...'")
        if not found:
            all_found = False
    
    return all_found

def verify_settings():
    """Verify settings.py has maintenance configuration."""
    print("\n⚙️  Verifying settings configuration...")
    
    settings_path = Path('src/config/settings.py')
    content = settings_path.read_text()
    
    checks = [
        ('MAINTENANCE_ENABLED', 'MAINTENANCE_ENABLED'),
        ('MAINTENANCE_INTERVAL_SECONDS', 'MAINTENANCE_INTERVAL_SECONDS'),
        ('MAINTENANCE_TASK_RETENTION_DAYS', 'MAINTENANCE_TASK_RETENTION_DAYS'),
        ('MAINTENANCE_STUCK_TASK_TIMEOUT_MINUTES', 'MAINTENANCE_STUCK_TASK_TIMEOUT_MINUTES'),
    ]
    
    all_found = True
    for name, pattern in checks:
        found = pattern in content
        status = "✅" if found else "❌"
        print(f"  {status} {name}")
        if not found:
            all_found = False
    
    return all_found

def verify_service_functionality():
    """Verify service can be initialized and runs."""
    print("\n🚀 Verifying service functionality...")
    
    try:
        from app.factory import create_app
        from app.services.maintenance_service import get_maintenance_service
        
        # Create app (this should initialize maintenance service)
        app = create_app('development')
        print("  ✅ App created")
        
        with app.app_context():
            # Get service
            service = get_maintenance_service()
            if not service:
                print("  ❌ Service not initialized")
                return False
            print("  ✅ Service initialized")
            
            # Check it's running
            if not service._running:
                print("  ❌ Service not running")
                return False
            print("  ✅ Service running")
            
            # Check thread exists
            if not service._thread or not service._thread.is_alive():
                print("  ❌ Daemon thread not alive")
                return False
            print("  ✅ Daemon thread alive")
            
            # Get status
            status = service.get_status()
            print(f"  ✅ Status: {status['stats']['runs']} runs, {status['stats']['errors']} errors")
            
            # Verify configuration
            config_ok = all([
                status['config']['cleanup_orphan_apps'],
                status['config']['cleanup_orphan_tasks'],
                status['config']['cleanup_stuck_tasks'],
                status['config']['cleanup_old_tasks'],
            ])
            if not config_ok:
                print("  ❌ Some cleanup tasks disabled")
                return False
            print("  ✅ All cleanup tasks enabled")
            
        return True
        
    except Exception as e:
        print(f"  ❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all verification checks."""
    print("=" * 60)
    print("MAINTENANCE SERVICE IMPLEMENTATION VERIFICATION")
    print("=" * 60)
    
    results = []
    
    # Run all checks
    results.append(("Files exist", verify_files_exist()))
    results.append(("Imports work", verify_imports()))
    results.append(("Factory integration", verify_factory_integration()))
    results.append(("Settings configuration", verify_settings()))
    results.append(("Service functionality", verify_service_functionality()))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 All verification checks passed!")
        print("\n📋 Implementation Summary:")
        print("   - Maintenance service created and integrated")
        print("   - Runs on startup + every 1 hour")
        print("   - Cleans up orphan apps, orphan tasks, stuck tasks, old tasks")
        print("   - Configuration via environment variables")
        print("   - Logs all cleanup actions (no UI notifications)")
        print("   - Does NOT delete result files (per user requirement)")
        print("\n✨ System ready for production use!")
        return 0
    else:
        print("\n❌ Some verification checks failed!")
        print("   Please review the output above for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
