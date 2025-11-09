"""Test maintenance service functionality."""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import GeneratedApplication, AnalysisTask
from app.constants import AnalysisStatus
from app.services.maintenance_service import get_maintenance_service

def test_maintenance_service():
    """Test maintenance service basic functionality."""
    print("=== Testing Maintenance Service ===\n")
    
    # Create app
    app = create_app('development')
    
    with app.app_context():
        # Get maintenance service
        maintenance_svc = get_maintenance_service()
        
        if not maintenance_svc:
            print("❌ Maintenance service not initialized!")
            return False
        
        print(f"✅ Maintenance service initialized")
        print(f"   - Interval: {maintenance_svc.interval}s ({maintenance_svc._format_interval(maintenance_svc.interval)})")
        print(f"   - Running: {maintenance_svc._running}")
        print(f"   - Thread: {maintenance_svc._thread.name if maintenance_svc._thread else 'None'}")
        
        # Wait a moment for initial run to complete
        print("\n⏳ Waiting for initial maintenance run to complete...")
        time.sleep(3)
        
        # Check status
        status = maintenance_svc.get_status()
        print(f"\n📊 Status after initial run:")
        print(f"   - Runs completed: {status['stats']['runs']}")
        print(f"   - Last run: {status['stats']['last_run']}")
        print(f"   - Orphan apps cleaned: {status['stats']['orphan_apps_cleaned']}")
        print(f"   - Orphan tasks cleaned: {status['stats']['orphan_tasks_cleaned']}")
        print(f"   - Stuck tasks cleaned: {status['stats']['stuck_tasks_cleaned']}")
        print(f"   - Old tasks cleaned: {status['stats']['old_tasks_cleaned']}")
        print(f"   - Errors: {status['stats']['errors']}")
        
        # Check current database state
        print("\n📁 Current database state:")
        total_apps = GeneratedApplication.query.count()
        pending_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).count()
        running_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).count()
        
        print(f"   - Total apps: {total_apps}")
        print(f"   - Pending tasks: {pending_tasks}")
        print(f"   - Running tasks: {running_tasks}")
        
        # Verify configuration
        print(f"\n⚙️  Configuration:")
        for key, value in status['config'].items():
            print(f"   - {key}: {value}")
        
        print(f"\n✅ Test completed successfully!")
        print(f"\nℹ️  Next maintenance run in: {status['interval_human']}")
        print(f"   Estimated next run: {status.get('next_run', 'N/A')}")
        
        return True

if __name__ == '__main__':
    try:
        success = test_maintenance_service()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
