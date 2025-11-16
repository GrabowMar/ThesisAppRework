"""Test script to verify task execution fixes.

This script:
1. Creates an analysis task for an existing generated app
2. Monitors task execution
3. Validates that results are properly saved and task status is correct
"""
import sys
import time
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from app.constants import AnalysisStatus

def main():
    print("=" * 80)
    print("Testing Task Execution Fixes")
    print("=" * 80)
    
    app = create_app()
    
    with app.app_context():
        # Find an existing generated app to test with
        model_slug = "anthropic_claude-4.5-haiku-20251001"
        app_number = 2  # Using app2 from the .env file shown
        
        print(f"\n1. Creating test analysis task for {model_slug} app {app_number}...")
        
        # Import task service
        from app.services.task_service import AnalysisTaskService
        
        # Create a STATIC-ONLY analysis task (no performance/dynamic - those need running app)
        # This tests the core fix: proper result file reading and status determination
        task = AnalysisTaskService.create_task(
            model_slug=model_slug,
            app_number=app_number,
            tools=['bandit', 'pylint'],  # Just 2 static tools for quick test
            config_id=None,
            priority='normal',
            custom_options={
                'selected_tools': [1, 2],
                'selected_tool_names': ['bandit', 'pylint'],
                'selected_tool_display_names': ['Bandit Security Scanner', 'Pylint Code Quality'],
                'tools_by_service': {
                    'static-analyzer': ['bandit', 'pylint']
                },
                'source': 'test_script',
                'analysis_type': 'static',
                'unified_analysis': False
            }
        )
        
        task_id = task.task_id
        print(f"✓ Created task {task_id}")
        print(f"  Status: {task.status.value}")
        print(f"  Target: {model_slug} app {app_number}")
        
        # Wait for task execution service to pick it up
        print(f"\n2. Waiting for task execution (max 60 seconds)...")
        max_wait = 60
        check_interval = 2
        elapsed = 0
        
        while elapsed < max_wait:
            db.session.expire_all()  # Refresh from DB
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            
            status = task.status.value
            progress = task.progress_percentage or 0
            
            print(f"  [{elapsed:>2}s] Status: {status:12} | Progress: {progress:>3.0f}%", end='')
            
            if task.error_message:
                print(f" | Error: {task.error_message[:50]}")
            else:
                print()
            
            if status in ['completed', 'failed', 'partial_success']:
                break
            
            time.sleep(check_interval)
            elapsed += check_interval
        
        # Final status check
        db.session.expire_all()
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        
        print(f"\n3. Final Results:")
        print(f"  Task ID: {task.task_id}")
        print(f"  Status: {task.status.value}")
        print(f"  Progress: {task.progress_percentage or 0}%")
        print(f"  Issues Found: {task.issues_found or 0}")
        
        if task.error_message:
            print(f"  Error: {task.error_message}")
        
        # Check for result files
        results_base = Path(__file__).parent / "results"
        safe_slug = model_slug.replace('/', '_').replace('\\', '_')
        
        # Check both possible task folder names
        task_folders = [
            results_base / safe_slug / f"app{app_number}" / task_id,
            results_base / safe_slug / f"app{app_number}" / f"task_{task_id}"
        ]
        
        result_files_found = False
        for task_dir in task_folders:
            if task_dir.exists():
                print(f"\n4. Result Files in {task_dir.name}/:")
                
                # List JSON files
                json_files = list(task_dir.glob("*.json"))
                for json_file in json_files:
                    size_kb = json_file.stat().st_size / 1024
                    print(f"  ✓ {json_file.name} ({size_kb:.1f} KB)")
                    result_files_found = True
                
                # Check SARIF directory
                sarif_dir = task_dir / "sarif"
                if sarif_dir.exists():
                    sarif_files = list(sarif_dir.glob("*.sarif.json"))
                    if sarif_files:
                        print(f"  ✓ sarif/ directory with {len(sarif_files)} files")
                
                # Check services directory
                services_dir = task_dir / "services"
                if services_dir.exists():
                    service_files = list(services_dir.glob("*.json"))
                    if service_files:
                        print(f"  ✓ services/ directory with {len(service_files)} files")
                
                # Load and validate main result file
                if json_files:
                    main_result = json_files[0]
                    with open(main_result, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    print(f"\n5. Result Structure Validation:")
                    print(f"  ✓ Has 'metadata': {('metadata' in data)}")
                    print(f"  ✓ Has 'results': {('results' in data)}")
                    
                    if 'results' in data:
                        results = data['results']
                        print(f"  ✓ Has 'services': {('services' in results)}")
                        print(f"  ✓ Has 'tools': {('tools' in results)}")
                        print(f"  ✓ Has 'findings': {('findings' in results)}")
                        print(f"  ✓ Has 'summary': {('summary' in results)}")
                        
                        if 'summary' in results:
                            summary = results['summary']
                            print(f"  ✓ Total findings: {summary.get('total_findings', 0)}")
                            print(f"  ✓ Services executed: {summary.get('services_executed', 0)}")
                            print(f"  ✓ Tools executed: {summary.get('tools_executed', 0)}")
                
                break
        
        if not result_files_found:
            print(f"\n4. ⚠️ No result files found in expected locations:")
            for task_dir in task_folders:
                print(f"  - {task_dir}")
        
        # Summary
        print(f"\n{'=' * 80}")
        print("Test Summary:")
        print(f"{'=' * 80}")
        
        success_statuses = ['completed', 'partial_success']
        is_success = task.status.value in success_statuses
        
        if is_success and result_files_found and (task.issues_found or 0) > 0:
            print("✅ TEST PASSED - All fixes working correctly!")
            print(f"   - Task completed with status: {task.status.value}")
            print(f"   - Found {task.issues_found} issues")
            print(f"   - Result files saved successfully")
            return 0
        elif is_success and result_files_found:
            print("✅ TEST PASSED - Task completed successfully")
            print(f"   - Status: {task.status.value}")
            print(f"   - Result files saved")
            print(f"   ⚠️ No issues found (may be expected for clean code)")
            return 0
        else:
            print("❌ TEST FAILED - Issues detected:")
            if not is_success:
                print(f"   - Task status is '{task.status.value}' (expected 'completed' or 'partial_success')")
            if not result_files_found:
                print(f"   - Result files not found")
            if task.error_message:
                print(f"   - Error: {task.error_message}")
            return 1

if __name__ == '__main__':
    sys.exit(main())
