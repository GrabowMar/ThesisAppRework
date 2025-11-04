"""
Diagnostic script to verify analysis workflow components
This can run without analyzer containers to check the plumbing
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

def check_imports():
    """Check that all required modules can be imported"""
    print("\n" + "="*60)
    print("CHECKING IMPORTS")
    print("="*60)
    
    checks = []
    
    try:
        from app.factory import create_app
        checks.append(("✅", "app.factory.create_app"))
    except Exception as e:
        checks.append(("❌", f"app.factory.create_app - {e}"))
    
    try:
        from app.services.analyzer_manager_wrapper import get_analyzer_wrapper
        checks.append(("✅", "analyzer_manager_wrapper"))
    except Exception as e:
        checks.append(("❌", f"analyzer_manager_wrapper - {e}"))
    
    try:
        from app.services.task_execution_service import TaskExecutionService
        checks.append(("✅", "task_execution_service"))
    except Exception as e:
        checks.append(("❌", f"task_execution_service - {e}"))
    
    try:
        from app.services.task_service import AnalysisTaskService
        checks.append(("✅", "task_service"))
    except Exception as e:
        checks.append(("❌", f"task_service - {e}"))
    
    try:
        from app.models import AnalysisTask
        checks.append(("✅", "models.AnalysisTask"))
    except Exception as e:
        checks.append(("❌", f"models.AnalysisTask - {e}"))
    
    for status, msg in checks:
        print(f"{status} {msg}")
    
    return all(status == "✅" for status, _ in checks)

def check_result_structure():
    """Check if reference result folder exists and has correct structure"""
    print("\n" + "="*60)
    print("CHECKING REFERENCE RESULT STRUCTURE")
    print("="*60)
    
    ref_path = Path("results/anthropic_claude-4.5-sonnet-20250929/app1/task_analysis_20251104_170200")
    
    if not ref_path.exists():
        print(f"❌ Reference path not found: {ref_path}")
        return False
    
    print(f"✅ Reference path exists: {ref_path}")
    
    # Check for expected files
    expected_files = [
        "manifest.json",
        "anthropic_claude-4.5-sonnet-20250929_app1_task_analysis_20251104_170200_20251104_170200.json"
    ]
    
    for filename in expected_files:
        filepath = ref_path / filename
        if filepath.exists():
            print(f"✅ Found: {filename} ({filepath.stat().st_size} bytes)")
        else:
            print(f"❌ Missing: {filename}")
    
    # Check for subdirectories
    if (ref_path / "sarif").exists():
        sarif_count = len(list((ref_path / "sarif").glob("*.sarif.json")))
        print(f"✅ SARIF directory exists with {sarif_count} files")
    else:
        print("❌ SARIF directory missing")
    
    if (ref_path / "services").exists():
        service_count = len(list((ref_path / "services").glob("*.json")))
        print(f"✅ Services directory exists with {service_count} files")
    else:
        print("❌ Services directory missing")
    
    return True

def check_analyzer_manager():
    """Check if analyzer_manager can be imported"""
    print("\n" + "="*60)
    print("CHECKING ANALYZER_MANAGER")
    print("="*60)
    
    analyzer_path = Path(__file__).parent / 'analyzer'
    sys.path.insert(0, str(analyzer_path))
    
    try:
        from analyzer_manager import AnalyzerManager
        print("✅ analyzer_manager.AnalyzerManager imported successfully")
        
        manager = AnalyzerManager()
        print(f"✅ AnalyzerManager instantiated")
        print(f"   Results dir: {manager.results_dir}")
        print(f"   Compose file: {manager.compose_file}")
        
        # Check method availability
        methods = [
            'run_comprehensive_analysis',
            'save_task_results',
            '_aggregate_findings',
            '_collect_normalized_tools',
            '_extract_sarif_to_files'
        ]
        
        for method_name in methods:
            if hasattr(manager, method_name):
                print(f"✅ Method available: {method_name}")
            else:
                print(f"❌ Method missing: {method_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to import analyzer_manager: {e}")
        return False

def check_flask_app():
    """Check if Flask app can be created"""
    print("\n" + "="*60)
    print("CHECKING FLASK APP")
    print("="*60)
    
    try:
        from app.factory import create_app
        
        app = create_app('development')
        print("✅ Flask app created successfully")
        
        with app.app_context():
            # Check if TaskExecutionService is available
            try:
                from app.services.task_execution_service import TaskExecutionService
                print("✅ TaskExecutionService available in app context")
            except Exception as e:
                print(f"❌ TaskExecutionService not available: {e}")
            
            # Check if database is accessible
            try:
                from app.extensions import db
                print("✅ Database extension available")
            except Exception as e:
                print(f"❌ Database extension not available: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create Flask app: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all diagnostic checks"""
    print("\n" + "="*60)
    print("ANALYSIS WORKFLOW DIAGNOSTIC")
    print("="*60)
    print("\nThis script verifies that all components are properly wired")
    print("and can be imported without errors.\n")
    
    results = []
    
    results.append(("Imports", check_imports()))
    results.append(("Result Structure", check_result_structure()))
    results.append(("Analyzer Manager", check_analyzer_manager()))
    results.append(("Flask App", check_flask_app()))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n✅ All checks passed! Workflow is correctly configured.")
        print("\nNext steps:")
        print("1. Ensure analyzer containers are running:")
        print("   python analyzer/analyzer_manager.py start")
        print("2. Run Flask app:")
        print("   cd src && python main.py")
        print("3. Test API:")
        print("   python test_analysis_api.py")
    else:
        print("\n❌ Some checks failed. Review errors above.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
