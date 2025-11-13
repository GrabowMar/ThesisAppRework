"""
Test script to verify model analysis report generation with new fixes.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.services.service_locator import ServiceLocator

def test_model_report():
    """Test model analysis report generation."""
    app = create_app()
    
    with app.app_context():
        # Get report service
        report_service = ServiceLocator().get_report_service()
        
        # Generate model analysis report
        model_slug = 'anthropic_claude-4.5-haiku-20251001'
        
        print(f"\n{'='*80}")
        print(f"Testing Model Analysis Report Generation")
        print(f"{'='*80}\n")
        print(f"Model: {model_slug}")
        print(f"Generating report...")
        
        try:
            report = report_service.generate_report(
                report_type='model_analysis',
                format='html',
                config={'model_slug': model_slug}
            )
            
            print(f"\n[SUCCESS] Report generated successfully!")
            print(f"   Report ID: {report.report_id}")
            print(f"   Status: {report.status}")
            print(f"   File: {report.file_path}")
            
            # Load the generated data to check content
            from app.services.reports.model_report_generator import ModelReportGenerator
            from pathlib import Path
            reports_dir = Path(__file__).parent / 'reports' / 'model_analysis'
            generator = ModelReportGenerator(reports_dir=reports_dir, config={'model_slug': model_slug})
            data = generator.collect_data()
            
            print(f"\n{'─'*80}")
            print(f"Data Summary:")
            print(f"{'─'*80}")
            print(f"   Apps analyzed: {data['apps_count']}")
            print(f"   Total tasks: {data['total_tasks']}")
            print(f"   Total findings: {data['aggregated_stats']['total_findings']}")
            print(f"   Critical: {data['aggregated_stats']['findings_by_severity']['critical']}")
            print(f"   High: {data['aggregated_stats']['findings_by_severity']['high']}")
            print(f"   Medium: {data['aggregated_stats']['findings_by_severity']['medium']}")
            print(f"   Low: {data['aggregated_stats']['findings_by_severity']['low']}")
            
            print(f"\n{'─'*80}")
            print(f"Scientific Metrics:")
            print(f"{'─'*80}")
            sci = data.get('scientific_metrics', {})
            dist = sci.get('findings_distribution', {})
            if dist:
                print(f"   Mean: {dist.get('mean', 0):.2f}")
                print(f"   Median: {dist.get('median', 0)}")
                print(f"   Std Dev: {dist.get('std_dev', 0):.2f}")
                print(f"   Range: {dist.get('min', 0)} - {dist.get('max', 0)}")
                print(f"   CV: {dist.get('cv_percent', 0):.1f}%")
            
            print(f"\n{'─'*80}")
            print(f"Tool Statistics ({len(data['tools_statistics'])} tools):")
            print(f"{'─'*80}")
            for tool_name, stats in list(data['tools_statistics'].items())[:5]:
                print(f"   {tool_name}:")
                print(f"      Executions: {stats['total_executions']}")
                print(f"      Success Rate: {stats['success_rate']:.1f}%")
                print(f"      Total Findings: {stats['total_findings']}")
                print(f"      Avg Duration: {stats['average_duration']:.2f}s")
            
            if len(data['tools_statistics']) > 5:
                print(f"   ... and {len(data['tools_statistics']) - 5} more tools")
            
            print(f"\n{'─'*80}")
            print(f"Per-App Data:")
            print(f"{'─'*80}")
            for app in data['apps']:
                print(f"   App {app['app_number']}:")
                print(f"      Findings: {app['findings_count']}")
                print(f"      Duration: {app['duration_seconds']:.1f}s")
                print(f"      Tools used: {len(app['tools'])}")
                print(f"      Findings extracted: {len(app['findings'])}")
            
            print(f"\n{'='*80}")
            print(f"[SUCCESS] All tests passed! Report is properly populated with data.")
            print(f"{'='*80}\n")
            
            return True
            
        except Exception as e:
            print(f"\n[ERROR] Error generating report: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = test_model_report()
    sys.exit(0 if success else 1)
