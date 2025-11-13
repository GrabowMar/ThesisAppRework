"""Integration test for reports with Flask app context"""
import sys
import os
from pathlib import Path

# Setup paths
project_root = Path(__file__).parent
src_path = project_root / 'src'
sys.path.insert(0, str(src_path))
os.chdir(str(project_root))

from app.factory import create_app
from app.services.report_generation_service import ReportGenerationService
from app.models import AnalysisTask, GeneratedApplication

print("="*60)
print("Integration Test: Reports with Flask App")
print("="*60)

# Create Flask app
print("\n1. Creating Flask app...")
app = create_app()

with app.app_context():
    # Test 2: Check if report service is registered
    print("\n2. Checking service locator...")
    try:
        from app.services.service_locator import ServiceLocator
        service_locator = ServiceLocator()
        report_service = service_locator.get_report_service()
        
        if report_service:
            print(f"   ✓ Report service registered: {type(report_service).__name__}")
        else:
            print("   ✗ Report service not found in service locator")
    except Exception as e:
        print(f"   ⚠ Service locator check failed: {e}")
        print("   (This is OK if service registration happens later)")
    
    # Test 3: Check database tables
    print("\n3. Checking database...")
    try:
        from app.extensions import db
        
        # Check if reports table exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'reports' in tables:
            print("   ✓ 'reports' table exists")
        else:
            print("   ✗ 'reports' table NOT FOUND")
        
        if 'analysis_tasks' in tables:
            print("   ✓ 'analysis_tasks' table exists")
        else:
            print("   ✗ 'analysis_tasks' table NOT FOUND")
            
    except Exception as e:
        print(f"   ⚠ Database check error: {e}")
        print("   (This is OK if database is not initialized)")
    
    # Test 4: Check for available data
    print("\n4. Checking for analysis data...")
    try:
        # Count tasks
        task_count = AnalysisTask.query.filter_by(status='completed').count()
        print(f"   ℹ Completed tasks in database: {task_count}")
        
        # Count generated apps
        app_count = GeneratedApplication.query.count()
        print(f"   ℹ Generated applications: {app_count}")
        
        if task_count > 0:
            # Get unique models
            models = AnalysisTask.query.with_entities(AnalysisTask.target_model).distinct().all()
            print(f"   ℹ Models with data: {[m[0] for m in models[:5]]}")
            
            # Get app numbers
            apps = AnalysisTask.query.with_entities(AnalysisTask.target_app_number).distinct().all()
            print(f"   ℹ App numbers analyzed: {sorted([a[0] for a in apps])}")
        
    except Exception as e:
        print(f"   ⚠ Data check error: {e}")
        print("   (This is OK if database is empty)")
    
    # Test 5: Test report type validation
    print("\n5. Testing report type validation...")
    try:
        from app.models.report import Report
        
        # Test model_analysis config
        report = Report()
        report.report_type = 'model_analysis'
        report.set_config({'model_slug': 'openai_gpt-4'})
        assert report.validate_config_for_type() == True
        print("   ✓ model_analysis with model_slug: Valid")
        
        report.set_config({})
        assert report.validate_config_for_type() == False
        print("   ✓ model_analysis without model_slug: Invalid")
        
        # Test app_analysis config
        report.report_type = 'app_analysis'
        report.set_config({'app_number': 1})
        assert report.validate_config_for_type() == True
        print("   ✓ app_analysis with app_number: Valid")
        
        report.set_config({})
        assert report.validate_config_for_type() == False
        print("   ✓ app_analysis without app_number: Invalid")
        
        # Test tool_analysis config (flexible)
        report.report_type = 'tool_analysis'
        report.set_config({})
        assert report.validate_config_for_type() == True
        print("   ✓ tool_analysis with no config: Valid (global)")
        
        report.set_config({'tool_name': 'bandit'})
        assert report.validate_config_for_type() == True
        print("   ✓ tool_analysis with tool_name: Valid")
        
    except Exception as e:
        print(f"   ✗ Config validation test error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 6: Check if routes are registered
    print("\n6. Checking API routes...")
    try:
        routes = [str(rule) for rule in app.url_map.iter_rules()]
        
        report_routes = [r for r in routes if 'report' in r.lower()]
        if report_routes:
            print(f"   ✓ Found {len(report_routes)} report-related routes:")
            for route in sorted(report_routes)[:10]:
                print(f"     - {route}")
        else:
            print("   ✗ No report routes found")
            
    except Exception as e:
        print(f"   ⚠ Route check error: {e}")
    
    # Test 7: Check templates
    print("\n7. Checking template availability...")
    try:
        template_dir = app.jinja_loader.searchpath[0] if hasattr(app.jinja_loader, 'searchpath') else None
        if template_dir:
            template_path = Path(template_dir) / 'pages' / 'reports'
            if template_path.exists():
                templates = list(template_path.glob('*.html'))
                print(f"   ✓ Found {len(templates)} report templates:")
                for t in templates:
                    print(f"     - {t.name}")
            else:
                print(f"   ⚠ Template directory not found: {template_path}")
        else:
            print("   ⚠ Could not determine template directory")
    except Exception as e:
        print(f"   ⚠ Template check error: {e}")

print("\n" + "="*60)
print("✓ Integration test completed!")
print("="*60)
print("\nNext steps:")
print("  1. Start the Flask app: python src/main.py")
print("  2. Navigate to /reports in the web UI")
print("  3. Click 'Generate New Report' button")
print("  4. Select a report type and configure options")
print("  5. Generate and view the report")
