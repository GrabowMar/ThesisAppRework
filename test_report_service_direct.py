"""
Direct Report Service Test

Tests report generation directly via the service layer (no API/Flask).
"""
import sys
import platform
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.factory import create_app
from app.services.service_locator import ServiceLocator

# Check if PDF is available (requires GTK on Windows)
try:
    from app.services.report_renderers import PDF_AVAILABLE
except ImportError:
    PDF_AVAILABLE = False

IS_WINDOWS = platform.system() == "Windows"

def test_app_analysis_report():
    """Test generating an app analysis report."""
    format_type = "html"
    
    print("\n" + "="*70)
    print(f"TEST 1: App Analysis Report ({format_type.upper()})")
    print("="*70)
    
    app = create_app()
    
    with app.app_context():
        service_locator = ServiceLocator()
        report_service = service_locator.get_report_service()
        unified_service = service_locator.get_unified_result_service()
        
        model_slug = "anthropic_claude-4.5-haiku-20251001"
        app_number = 1
        
        # First, check what tasks exist
        from app.models.analysis import AnalysisTask
        tasks = (AnalysisTask.query
                .filter_by(target_model=model_slug, target_app_number=app_number)
                .order_by(AnalysisTask.created_at.desc())
                .all())
        
        print(f"\nFound {len(tasks)} task(s) for {model_slug} app {app_number}")
        if tasks:
            for task in tasks[:3]:
                print(f"  {task.task_id}: {task.status}")
                # Try to load results
                results = unified_service.load_analysis_results(task.task_id)
                if results and hasattr(results, 'raw_data'):
                    findings_count = len(results.raw_data.get('findings', []))
                    tools_count = len(results.raw_data.get('tools', {}))
                    print(f"    Findings: {findings_count}, Tools: {tools_count}")
        
        config = {
            "model_slug": model_slug,
            "app_number": app_number,
            "include_findings": True,
            "include_metrics": True,
            "severity_filter": ["critical", "high", "medium", "low"]
        }
        
        try:
            report = report_service.generate_report(
                report_type="app_analysis",
                format=format_type,
                config=config,
                title=f"App Analysis - Claude 4.5 Haiku - App 1 ({format_type.upper()})",
                description="Complete analysis report for app 1",
                user_id=None,
                expires_in_days=30
            )
            
            print(f"\n✓ Report Generated Successfully!")
            print(f"  Report ID: {report.report_id}")
            print(f"  Type: {report.report_type}")
            print(f"  Format: {report.format}")
            print(f"  Status: {report.status}")
            print(f"  File: {report.file_path}")
            print(f"  Size: {report.file_size} bytes")
            print(f"  Created: {report.created_at}")
            
            if report.error_message:
                print(f"  Error: {report.error_message}")
            
            # Check if file exists
            reports_dir = Path(__file__).parent / "reports"
            file_path = reports_dir / report.file_path
            if file_path.exists():
                print(f"\n✓ File exists: {file_path}")
                print(f"  Actual size: {file_path.stat().st_size} bytes")
            else:
                print(f"\n✗ File not found: {file_path}")
            
            return report
            
        except Exception as e:
            print(f"\n✗ Error generating report: {e}")
            import traceback
            traceback.print_exc()
            return None

def test_model_comparison_report():
    """Test generating a model comparison report."""
    print("\n" + "="*70)
    print("TEST 2: Model Comparison Report (HTML)")
    print("="*70)
    
    app = create_app()
    
    with app.app_context():
        service_locator = ServiceLocator()
        report_service = service_locator.get_report_service()
        
        config = {
            "model_slugs": [
                "anthropic_claude-4.5-haiku-20251001",
                "amazon_nova-pro-v1"
            ],
            "app_numbers": [1],
            "metrics": ["code_quality", "security", "performance"],
            "include_charts": True
        }
        
        try:
            report = report_service.generate_report(
                report_type="model_comparison",
                format="html",
                config=config,
                title="Model Comparison: Claude vs Nova",
                description="Comparison of app 1 across models",
                user_id=None,
                expires_in_days=30
            )
            
            print(f"\n✓ Report Generated Successfully!")
            print(f"  Report ID: {report.report_id}")
            print(f"  Type: {report.report_type}")
            print(f"  Format: {report.format}")
            print(f"  Status: {report.status}")
            print(f"  File: {report.file_path}")
            print(f"  Size: {report.file_size} bytes")
            
            return report
            
        except Exception as e:
            print(f"\n✗ Error generating report: {e}")
            import traceback
            traceback.print_exc()
            return None

def test_executive_summary():
    """Test generating an executive summary."""
    print("\n" + "="*70)
    print("TEST 3: Executive Summary (JSON)")
    print("="*70)
    
    app = create_app()
    
    with app.app_context():
        service_locator = ServiceLocator()
        report_service = service_locator.get_report_service()
        
        config = {
            "period_days": 30,
            "include_trends": True,
            "include_recommendations": True,
            "model_slugs": ["anthropic_claude-4.5-haiku-20251001"]
        }
        
        try:
            report = report_service.generate_report(
                report_type="executive_summary",
                format="json",
                config=config,
                title="Executive Summary - Last 30 Days",
                description="High-level overview of analysis activities",
                user_id=None,
                expires_in_days=30
            )
            
            print(f"\n✓ Report Generated Successfully!")
            print(f"  Report ID: {report.report_id}")
            print(f"  Type: {report.report_type}")
            print(f"  Format: {report.format}")
            print(f"  Status: {report.status}")
            print(f"  File: {report.file_path}")
            print(f"  Size: {report.file_size} bytes")
            
            # Print JSON content
            reports_dir = Path(__file__).parent / "reports"
            file_path = reports_dir / report.file_path
            if file_path.exists():
                import json
                content = json.loads(file_path.read_text())
                print(f"\n  JSON Summary:")
                print(f"    Total Apps: {content.get('total_apps', 'N/A')}")
                print(f"    Total Tasks: {content.get('total_tasks', 'N/A')}")
                print(f"    Critical Issues: {content.get('critical_issues_found', 'N/A')}")
            
            return report
            
        except Exception as e:
            print(f"\n✗ Error generating report: {e}")
            import traceback
            traceback.print_exc()
            return None

def list_reports():
    """List all generated reports."""
    print("\n" + "="*70)
    print("TEST 4: List All Reports")
    print("="*70)
    
    app = create_app()
    
    with app.app_context():
        service_locator = ServiceLocator()
        report_service = service_locator.get_report_service()
        
        try:
            reports = report_service.list_reports()
            
            print(f"\n✓ Found {len(reports)} reports:")
            for report in reports:
                print(f"\n  Report: {report.report_id}")
                print(f"    Type: {report.report_type}")
                print(f"    Format: {report.format}")
                print(f"    Status: {report.status}")
                print(f"    Title: {report.title}")
                print(f"    Created: {report.created_at}")
                print(f"    File: {report.file_path}")
                print(f"    Size: {report.file_size} bytes")
            
        except Exception as e:
            print(f"\n✗ Error listing reports: {e}")
            import traceback
            traceback.print_exc()

def verify_files():
    """Verify generated report files."""
    print("\n" + "="*70)
    print("TEST 5: Verify Report Files")
    print("="*70)
    
    reports_dir = Path(__file__).parent / "reports"
    
    if not reports_dir.exists():
        print(f"\n✗ Reports directory does not exist: {reports_dir}")
        return
    
    print(f"\n✓ Reports Directory: {reports_dir}")
    
    # List all report files by type
    for report_type_dir in reports_dir.iterdir():
        if report_type_dir.is_dir():
            print(f"\n  {report_type_dir.name}/")
            files = list(report_type_dir.iterdir())
            print(f"    Files: {len(files)}")
            for file in files:
                size_kb = file.stat().st_size / 1024
                print(f"      - {file.name} ({size_kb:.1f} KB)")

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print(" "*15 + "DIRECT REPORT SERVICE TEST SUITE")
    print("="*80)
    print("\nTesting report generation via service layer...")
    
    # Test 1: App Analysis (PDF)
    report1 = test_app_analysis_report()
    
    # Test 2: Model Comparison (HTML)
    report2 = test_model_comparison_report()
    
    # Test 3: Executive Summary (JSON)
    report3 = test_executive_summary()
    
    # Test 4: List reports
    list_reports()
    
    # Test 5: Verify files
    verify_files()
    
    # Summary
    print("\n" + "="*80)
    print(" "*30 + "TEST SUMMARY")
    print("="*80)
    
    reports_created = sum(1 for r in [report1, report2, report3] if r is not None)
    print(f"Reports created: {reports_created}/3")
    
    if reports_created == 3:
        print("\n✓ All tests passed!")
    else:
        print(f"\n⚠ Some tests failed ({3 - reports_created} failures)")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
