"""
Test Report Data Validation
Verifies that reports contain correct data from analysis results.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.services.service_locator import ServiceLocator
import json

def validate_app_analysis_report():
    """Generate and validate an app analysis report for Haiku app 1."""
    print("\n" + "="*80)
    print("VALIDATING APP ANALYSIS REPORT DATA")
    print("="*80)
    
    # Set testing flag to prevent Flask server startup
    import os
    os.environ['TESTING'] = '1'
    
    app = create_app('development')
    
    with app.app_context():
        report_service = ServiceLocator.get_report_generation_service()
        unified_service = ServiceLocator.get_unified_result_service()
        
        # Generate report for Haiku app 1
        model_slug = "anthropic_claude-4.5-haiku-20251001"
        app_number = 1
        
        print(f"\n📊 Generating report for {model_slug} - App {app_number}")
        
        # Get latest task for this app
        from app.models.analysis import AnalysisTask
        task = (AnalysisTask.query
                .filter_by(target_model=model_slug, target_app_number=app_number)
                .order_by(AnalysisTask.created_at.desc())
                .first())
        
        if not task:
            print(f"❌ No analysis tasks found for {model_slug} app {app_number}")
            return False
        
        print(f"\n✓ Found task: {task.task_id}")
        print(f"  Status: {task.status}")
        print(f"  Created: {task.created_at}")
        
        # Load analysis results
        print(f"\n🔍 Loading analysis results...")
        results = unified_service.load_analysis_results(task.task_id)
        
        if not results:
            print(f"❌ No results found for task {task.task_id}")
            return False
        
        print(f"✓ Results loaded successfully")
        
        # Extract key data points
        raw_data = results.raw_data if hasattr(results, 'raw_data') else {}
        findings = raw_data.get('findings', [])
        tools = raw_data.get('tools', {})
        summary = raw_data.get('summary', {})
        
        print(f"\n📈 Data Summary:")
        print(f"  Findings: {len(findings)}")
        print(f"  Tools: {len(tools)}")
        
        # Count findings by severity
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        for finding in findings:
            sev = finding.get('severity', 'low').lower()
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        print(f"\n  Severity Distribution:")
        for sev, count in severity_counts.items():
            print(f"    {sev.upper()}: {count}")
        
        print(f"\n  Tools Status:")
        for tool_name, tool_data in list(tools.items())[:5]:
            status = tool_data.get('status', 'unknown')
            count = tool_data.get('findings_count', 0)
            print(f"    {tool_name}: {status} ({count} findings)")
        
        # Generate HTML report
        print(f"\n📄 Generating HTML report...")
        report = report_service.create_app_analysis_report(
            model_slug=model_slug,
            app_number=app_number,
            format='html',
            title=f"Data Validation Report - {model_slug} - App {app_number}"
        )
        
        if not report or report.status != 'completed':
            print(f"❌ Report generation failed")
            if report:
                print(f"  Status: {report.status}")
                print(f"  Error: {report.error_message}")
            return False
        
        print(f"✓ Report generated successfully")
        print(f"  Report ID: {report.report_id}")
        print(f"  File: {report.file_path}")
        print(f"  Size: {report.file_size} bytes")
        
        # Read and validate report content
        report_path = Path(report_service.reports_dir) / report.file_path
        if not report_path.exists():
            print(f"❌ Report file not found: {report_path}")
            return False
        
        html_content = report_path.read_text(encoding='utf-8')
        
        print(f"\n🔍 Validating report content...")
        
        # Check for key data in HTML
        validations = [
            (model_slug in html_content, f"Model slug '{model_slug}' in report"),
            (f"App {app_number}" in html_content or f"#{app_number}" in html_content, "App number in report"),
            (str(len(findings)) in html_content, f"Total findings count ({len(findings)}) in report"),
            (str(severity_counts['critical']) in html_content, f"Critical count ({severity_counts['critical']}) in report"),
            (str(severity_counts['high']) in html_content, f"High count ({severity_counts['high']}) in report"),
            (str(len(tools)) in html_content, f"Tools count ({len(tools)}) in report"),
            ("Abstract" in html_content, "Abstract section present"),
            ("Table I:" in html_content or "Table 1:" in html_content, "IEEE-style table present"),
            ("Crimson Text" in html_content, "Academic font styling present"),
        ]
        
        all_valid = True
        for valid, description in validations:
            status = "✓" if valid else "❌"
            print(f"  {status} {description}")
            if not valid:
                all_valid = False
        
        # Sample findings validation
        if findings:
            print(f"\n📋 Sample Findings (first 3):")
            for idx, finding in enumerate(findings[:3], 1):
                severity = finding.get('severity', 'unknown').upper()
                title = finding.get('title', 'No title')
                print(f"  {idx}. [{severity}] {title}")
                
                # Check if this finding appears in HTML
                if title[:30] in html_content:
                    print(f"     ✓ Found in report")
                else:
                    print(f"     ⚠️ Not found in report (might be truncated)")
        
        return all_valid


def validate_all_apps_report():
    """Generate report for all Haiku apps and validate."""
    print("\n" + "="*80)
    print("VALIDATING ALL APPS REPORT")
    print("="*80)
    
    # Set testing flag
    import os
    os.environ['TESTING'] = '1'
    
    app = create_app('development')
    
    with app.app_context():
        from app.models.analysis import AnalysisTask
        
        model_slug = "anthropic_claude-4.5-haiku-20251001"
        
        # Find all apps for this model
        apps = (db.session.query(AnalysisTask.target_app_number)
                .filter_by(target_model=model_slug)
                .distinct()
                .all())
        
        app_numbers = sorted([app[0] for app in apps])
        
        print(f"\n📊 Found {len(app_numbers)} app(s) for {model_slug}")
        print(f"  App numbers: {app_numbers}")
        
        if not app_numbers:
            print(f"❌ No apps found for model")
            return False
        
        # Get task statistics
        total_tasks = AnalysisTask.query.filter_by(target_model=model_slug).count()
        completed_tasks = AnalysisTask.query.filter_by(
            target_model=model_slug,
            status='completed'
        ).count()
        
        print(f"\n📈 Task Statistics:")
        print(f"  Total tasks: {total_tasks}")
        print(f"  Completed: {completed_tasks}")
        print(f"  Success rate: {(completed_tasks/total_tasks*100):.1f}%")
        
        # For each app, show latest task
        print(f"\n📋 Latest Task per App:")
        for app_num in app_numbers:
            task = (AnalysisTask.query
                    .filter_by(target_model=model_slug, target_app_number=app_num)
                    .order_by(AnalysisTask.created_at.desc())
                    .first())
            
            if task:
                print(f"\n  App {app_num}:")
                print(f"    Task ID: {task.task_id}")
                print(f"    Status: {task.status}")
                print(f"    Created: {task.created_at}")
                
                # Try to get result summary
                if task.result_summary:
                    summary = task.get_result_summary()
                    if summary:
                        print(f"    Findings: {summary.get('total_findings', 'N/A')}")
        
        return True


if __name__ == '__main__':
    print("\n" + "="*80)
    print("REPORT DATA VALIDATION TEST SUITE")
    print("="*80)
    
    try:
        # Test 1: Validate single app report data
        result1 = validate_app_analysis_report()
        
        # Test 2: Validate all apps discovery
        result2 = validate_all_apps_report()
        
        print("\n" + "="*80)
        print("VALIDATION SUMMARY")
        print("="*80)
        print(f"  App Analysis Report: {'✓ PASSED' if result1 else '❌ FAILED'}")
        print(f"  All Apps Discovery: {'✓ PASSED' if result2 else '❌ FAILED'}")
        print("="*80)
        
        if result1 and result2:
            print("\n✓ All validations passed!")
        else:
            print("\n❌ Some validations failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
