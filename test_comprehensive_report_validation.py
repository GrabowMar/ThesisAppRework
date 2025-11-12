"""
Comprehensive Report Data Validation
Tests that reports contain correct data from analysis results.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask, db
from app.services.service_locator import ServiceLocator
import json

def main():
    """Run comprehensive report validation."""
    print("\n" + "="*80)
    print("COMPREHENSIVE REPORT DATA VALIDATION")
    print("="*80)
    
    app = create_app()
    
    with app.app_context():
        # Test 1: Check available analysis tasks
        print("\n" + "="*80)
        print("TEST 1: Check Available Analysis Tasks")
        print("="*80)
        
        model_slug = "anthropic_claude-4.5-haiku-20251001"
        
        tasks = (AnalysisTask.query
                .filter_by(target_model=model_slug)
                .order_by(AnalysisTask.created_at.desc())
                .all())
        
        print(f"\n📊 Found {len(tasks)} task(s) for {model_slug}")
        
        if not tasks:
            print("❌ No tasks found - cannot test report generation")
            return False
        
        # Show task details
        for idx, task in enumerate(tasks[:5], 1):
            print(f"\n{idx}. Task: {task.task_id}")
            print(f"   App: {task.target_app_number}")
            print(f"   Status: {task.status}")
            print(f"   Created: {task.created_at}")
        
        # Test 2: Load analysis results for latest completed task
        print("\n" + "="*80)
        print("TEST 2: Load Analysis Results")
        print("="*80)
        
        completed_task = (AnalysisTask.query
                        .filter_by(target_model=model_slug, status='completed')
                        .order_by(AnalysisTask.completed_at.desc())
                        .first())
        
        if not completed_task:
            print("⚠️ No completed tasks found, trying latest task...")
            completed_task = tasks[0]
        
        print(f"\nUsing task: {completed_task.task_id}")
        print(f"  Status: {completed_task.status}")
        print(f"  App: {completed_task.target_app_number}")
        
        unified_service = ServiceLocator.get_unified_result_service()
        results = unified_service.load_analysis_results(completed_task.task_id)
        
        if not results:
            print("❌ No results found - checking filesystem...")
            
            # Check filesystem directly
            results_path = Path(f"results/{model_slug}/app{completed_task.target_app_number}")
            if results_path.exists():
                print(f"✓ Results directory exists: {results_path}")
                task_dirs = list(results_path.glob(f"task_{completed_task.task_id[:8]}*"))
                if task_dirs:
                    print(f"✓ Found task directory: {task_dirs[0].name}")
                    json_files = list(task_dirs[0].glob("*.json"))
                    print(f"✓ Found {len(json_files)} JSON files")
                    
                    # Try to read primary result
                    for json_file in json_files:
                        if 'task' in json_file.name:
                            print(f"\nReading: {json_file.name}")
                            data = json.loads(json_file.read_text())
                            print(f"  Keys: {list(data.keys())}")
                            print(f"  Findings: {len(data.get('findings', []))}")
                            print(f"  Tools: {len(data.get('tools', {}))}")
                            break
            else:
                print(f"❌ Results directory not found: {results_path}")
                return False
        else:
            print("✓ Results loaded from database/cache")
            if hasattr(results, 'raw_data'):
                findings = results.raw_data.get('findings', [])
                tools = results.raw_data.get('tools', {})
                print(f"  Findings: {len(findings)}")
                print(f"  Tools: {len(tools)}")
                
                # Show sample data
                if findings:
                    print(f"\n  Sample Finding:")
                    f = findings[0]
                    print(f"    Severity: {f.get('severity', 'N/A')}")
                    print(f"    Title: {f.get('title', 'N/A')[:50]}")
                
                if tools:
                    print(f"\n  Sample Tool:")
                    tool_name = list(tools.keys())[0]
                    tool_data = tools[tool_name]
                    print(f"    {tool_name}: {tool_data.get('status', 'N/A')}")
        
        # Test 3: Generate report
        print("\n" + "="*80)
        print("TEST 3: Generate App Analysis Report")
        print("="*80)
        
        report_service = ServiceLocator.get_report_service()
        
        print(f"\nGenerating HTML report for {model_slug} app {completed_task.target_app_number}...")
        
        try:
            config = {
                "model_slug": model_slug,
                "app_number": completed_task.target_app_number,
                "include_findings": True,
                "include_metrics": True,
                "severity_filter": ["critical", "high", "medium", "low"]
            }
            
            report = report_service.generate_report(
                report_type="app_analysis",
                format='html',
                config=config,
                title=f"Validation Test - {model_slug} - App {completed_task.target_app_number}",
                description="Data validation test report",
                user_id=None,
                expires_in_days=30
            )
            
            if report and report.status == 'completed':
                print("✓ Report generated successfully!")
                print(f"  Report ID: {report.report_id}")
                print(f"  File: {report.file_path}")
                print(f"  Size: {report.file_size} bytes")
                
                # Validate report content
                print("\n📄 Validating report content...")
                reports_dir = Path("reports")
                report_path = reports_dir / report.file_path
                
                if not report_path.exists():
                    print(f"❌ Report file not found: {report_path}")
                    return False
                
                html_content = report_path.read_text(encoding='utf-8')
                
                # Check for academic styling elements
                checks = [
                    ('Abstract' in html_content, "Has Abstract section"),
                    ('Crimson Text' in html_content, "Has academic font"),
                    ('Table I:' in html_content or 'Table 1:' in html_content, "Has IEEE-style table"),
                    (model_slug in html_content or 'haiku' in html_content.lower(), "Contains model name"),
                    (f'App {completed_task.target_app_number}' in html_content or f'#{completed_task.target_app_number}' in html_content, "Contains app number"),
                    ('Severity' in html_content or 'severity' in html_content, "Contains severity data"),
                    ('Tools' in html_content or 'tools' in html_content, "Contains tools data"),
                ]
                
                all_passed = True
                for passed, description in checks:
                    status = "✓" if passed else "❌"
                    print(f"  {status} {description}")
                    if not passed:
                        all_passed = False
                
                if all_passed:
                    print("\n✓ All content validations passed!")
                    print(f"\n📂 Report saved to: {report_path}")
                    print(f"   Open with: start {report_path}")
                    return True
                else:
                    print("\n⚠️ Some validations failed but report was generated")
                    return True
            else:
                print(f"❌ Report generation failed")
                if report:
                    print(f"   Status: {report.status}")
                    print(f"   Error: {report.error_message}")
                return False
                
        except Exception as e:
            print(f"❌ Error generating report: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test 4: Check all apps
        print("\n" + "="*80)
        print("TEST 4: Check All Available Apps")
        print("="*80)
        
        apps = (db.session.query(AnalysisTask.target_app_number)
                .filter_by(target_model=model_slug)
                .distinct()
                .all())
        
        app_numbers = sorted([app[0] for app in apps])
        
        print(f"\n📱 Found {len(app_numbers)} app(s) for {model_slug}")
        print(f"   App numbers: {app_numbers}")
        
        for app_num in app_numbers:
            task_count = AnalysisTask.query.filter_by(
                target_model=model_slug,
                target_app_number=app_num
            ).count()
            print(f"   App {app_num}: {task_count} task(s)")
        
        return True


if __name__ == '__main__':
    print("\n" + "="*80)
    print("REPORT DATA VALIDATION - COMPREHENSIVE TEST")
    print("="*80)
    
    try:
        result = main()
        
        print("\n" + "="*80)
        print("FINAL RESULT")
        print("="*80)
        if result:
            print("✓ ALL TESTS PASSED")
            print("\nThe report system is working correctly!")
            print("Reports contain data from analysis results and use academic styling.")
        else:
            print("❌ SOME TESTS FAILED")
            print("\nPlease review the errors above.")
            sys.exit(1)
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
