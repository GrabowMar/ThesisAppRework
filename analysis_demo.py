"""
Analysis Demo Script
===================

Simple demonstration of the improved analysis capabilities.
This script shows how to use the analysis system programmatically.
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def demo_analysis_result_structure():
    """Demonstrate the analysis result structure."""
    print("\n" + "="*60)
    print("ANALYSIS RESULT STRUCTURE DEMO")
    print("="*60)
    
    # Example analysis result
    analysis_result = {
        'analysis_type': 'backend_security',
        'model': 'anthropic_claude-3-sonnet',
        'app_num': 1,
        'timestamp': datetime.now().isoformat(),
        'issues': [
            {
                'tool': 'bandit',
                'severity': 'HIGH',
                'confidence': 'HIGH',
                'filename': 'app.py',
                'line_number': 15,
                'issue_text': 'SQL injection vulnerability detected',
                'issue_type': 'security',
                'category': 'security',
                'rule_id': 'B608',
                'line_range': [15, 15],
                'code': 'query = f"SELECT * FROM users WHERE id = {user_id}"',
                'fix_suggestion': 'Use parameterized queries to prevent SQL injection'
            },
            {
                'tool': 'safety',
                'severity': 'MEDIUM',
                'confidence': 'HIGH',
                'filename': 'requirements.txt',
                'line_number': 3,
                'issue_text': 'Vulnerable dependency: Flask 1.0.0',
                'issue_type': 'dependency',
                'category': 'security',
                'rule_id': 'CVE-2023-1234',
                'line_range': [3, 3],
                'code': 'Flask==1.0.0',
                'fix_suggestion': 'Upgrade Flask to version 2.3.0 or later'
            }
        ],
        'summary': {
            'total_issues': 2,
            'critical_count': 0,
            'high_count': 1,
            'medium_count': 1,
            'low_count': 0,
            'tools_run': ['bandit', 'safety'],
            'duration_seconds': 23.4
        },
        'tool_outputs': {
            'bandit': 'Run completed. Found 1 issue.',
            'safety': 'Vulnerability scan completed. Found 1 vulnerable package.'
        },
        'tool_errors': {}
    }
    
    print("Analysis Result JSON:")
    print(json.dumps(analysis_result, indent=2))
    
    # Demonstrate severity sorting
    issues = analysis_result['issues']
    severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2, 'INFO': 3}
    sorted_issues = sorted(issues, key=lambda x: severity_order.get(x['severity'], 999))
    
    print(f"\nIssues sorted by severity:")
    for issue in sorted_issues:
        print(f"  {issue['severity']}: {issue['issue_text']} ({issue['tool']})")

def demo_analysis_categories():
    """Demonstrate analysis categories and tools."""
    print("\n" + "="*60)
    print("ANALYSIS CATEGORIES & TOOLS DEMO")
    print("="*60)
    
    categories = {
        'backend_security': {
            'description': 'Python security analysis and vulnerability detection',
            'tools': ['bandit', 'safety', 'semgrep'],
            'file_types': ['.py', '.txt'],
            'example_issues': [
                'SQL injection vulnerabilities',
                'Insecure deserialization',
                'Hardcoded passwords',
                'Vulnerable dependencies'
            ]
        },
        'frontend_security': {
            'description': 'JavaScript security analysis and dependency scanning',
            'tools': ['eslint', 'npm_audit', 'retire'],
            'file_types': ['.js', '.jsx', '.ts', '.tsx', '.json'],
            'example_issues': [
                'XSS vulnerabilities',
                'Insecure eval() usage',
                'Vulnerable npm packages',
                'Open redirect vulnerabilities'
            ]
        },
        'backend_quality': {
            'description': 'Code quality, complexity, and style analysis',
            'tools': ['pylint', 'flake8', 'radon'],
            'file_types': ['.py'],
            'example_issues': [
                'Code complexity warnings',
                'Style violations',
                'Unused variables',
                'Import order issues'
            ]
        },
        'zap_security': {
            'description': 'Dynamic web application security testing',
            'tools': ['owasp_zap'],
            'file_types': ['running application'],
            'example_issues': [
                'Authentication bypass',
                'Session management flaws',
                'Input validation errors',
                'Information disclosure'
            ]
        }
    }
    
    for category, info in categories.items():
        print(f"\n{category.upper().replace('_', ' ')}:")
        print(f"  Description: {info['description']}")
        print(f"  Tools: {', '.join(info['tools'])}")
        print(f"  File Types: {', '.join(info['file_types'])}")
        print(f"  Example Issues:")
        for issue in info['example_issues']:
            print(f"    - {issue}")

def demo_batch_analysis_planning():
    """Demonstrate batch analysis planning."""
    print("\n" + "="*60)
    print("BATCH ANALYSIS PLANNING DEMO")
    print("="*60)
    
    # Configuration for batch analysis
    batch_config = {
        'models': ['anthropic_claude-3-sonnet', 'openai_gpt-4', 'google_gemini-pro'],
        'app_range': (1, 5),  # Apps 1-5
        'analysis_types': ['backend_security', 'frontend_security'],
        'parallel_limit': 3,
        'timeout_per_analysis': 300,
        'priority_order': ['backend_security', 'frontend_security']
    }
    
    print("Batch Configuration:")
    print(json.dumps(batch_config, indent=2))
    
    # Calculate and display analysis plan
    planned_analyses = []
    for model in batch_config['models']:
        for app_num in range(batch_config['app_range'][0], batch_config['app_range'][1] + 1):
            for analysis_type in batch_config['analysis_types']:
                priority = batch_config['priority_order'].index(analysis_type) + 1
                planned_analyses.append({
                    'model': model,
                    'app_num': app_num,
                    'analysis_type': analysis_type,
                    'priority': priority,
                    'estimated_duration': 120  # seconds
                })
    
    print(f"\nPlanned Analyses: {len(planned_analyses)} total")
    print(f"Estimated Total Duration: {len(planned_analyses) * 120 / 60:.1f} minutes")
    print(f"With {batch_config['parallel_limit']} parallel workers: {len(planned_analyses) * 120 / 60 / batch_config['parallel_limit']:.1f} minutes")
    
    # Show first few analyses
    print(f"\nFirst 10 planned analyses:")
    for i, analysis in enumerate(planned_analyses[:10]):
        print(f"  {i+1:2d}. {analysis['model'][:20]:20s} App{analysis['app_num']} {analysis['analysis_type']:18s} (Priority: {analysis['priority']})")

def demo_analysis_reporting():
    """Demonstrate analysis reporting capabilities."""
    print("\n" + "="*60)
    print("ANALYSIS REPORTING DEMO")
    print("="*60)
    
    # Mock multiple analysis results
    mock_results = [
        {'model': 'model_a', 'app_num': 1, 'total_issues': 5, 'high_severity': 2, 'timestamp': '2025-01-01T10:00:00'},
        {'model': 'model_a', 'app_num': 2, 'total_issues': 3, 'high_severity': 1, 'timestamp': '2025-01-01T10:15:00'},
        {'model': 'model_a', 'app_num': 3, 'total_issues': 0, 'high_severity': 0, 'timestamp': '2025-01-01T10:30:00'},
        {'model': 'model_b', 'app_num': 1, 'total_issues': 8, 'high_severity': 3, 'timestamp': '2025-01-01T10:45:00'},
        {'model': 'model_b', 'app_num': 2, 'total_issues': 2, 'high_severity': 0, 'timestamp': '2025-01-01T11:00:00'},
    ]
    
    # Calculate summary statistics
    total_analyses = len(mock_results)
    total_issues = sum(r['total_issues'] for r in mock_results)
    total_high_severity = sum(r['high_severity'] for r in mock_results)
    apps_with_issues = sum(1 for r in mock_results if r['total_issues'] > 0)
    clean_apps = total_analyses - apps_with_issues
    
    print("SUMMARY STATISTICS:")
    print(f"  Total Analyses: {total_analyses}")
    print(f"  Total Issues Found: {total_issues}")
    print(f"  High Severity Issues: {total_high_severity}")
    print(f"  Apps with Issues: {apps_with_issues} ({apps_with_issues/total_analyses*100:.1f}%)")
    print(f"  Clean Apps: {clean_apps} ({clean_apps/total_analyses*100:.1f}%)")
    print(f"  Average Issues per App: {total_issues/total_analyses:.1f}")
    
    # Model comparison
    print(f"\nMODEL COMPARISON:")
    model_stats = {}
    for result in mock_results:
        model = result['model']
        if model not in model_stats:
            model_stats[model] = {'apps': 0, 'total_issues': 0, 'high_severity': 0}
        model_stats[model]['apps'] += 1
        model_stats[model]['total_issues'] += result['total_issues']
        model_stats[model]['high_severity'] += result['high_severity']
    
    for model, stats in model_stats.items():
        avg_issues = stats['total_issues'] / stats['apps']
        print(f"  {model}: {avg_issues:.1f} avg issues/app, {stats['high_severity']} high severity")

def demo_export_formats():
    """Demonstrate export format options."""
    print("\n" + "="*60)
    print("EXPORT FORMATS DEMO")
    print("="*60)
    
    sample_issue = {
        'tool': 'bandit',
        'severity': 'HIGH',
        'filename': 'app.py',
        'line_number': 10,
        'issue_text': 'SQL injection vulnerability',
        'rule_id': 'B608',
        'fix_suggestion': 'Use parameterized queries'
    }
    
    # JSON Export
    print("JSON Export Format:")
    print(json.dumps(sample_issue, indent=2))
    
    # CSV Export
    print(f"\nCSV Export Format:")
    csv_header = "Tool,Severity,File,Line,Issue,Rule,Suggestion"
    csv_row = f"{sample_issue['tool']},{sample_issue['severity']},{sample_issue['filename']},{sample_issue['line_number']},\"{sample_issue['issue_text']}\",{sample_issue['rule_id']},\"{sample_issue['fix_suggestion']}\""
    print(csv_header)
    print(csv_row)
    
    # Summary Report
    print(f"\nSummary Report Format:")
    print(f"Analysis Summary Report")
    print(f"=====================")
    print(f"Severity: {sample_issue['severity']}")
    print(f"Tool: {sample_issue['tool']}")
    print(f"Location: {sample_issue['filename']}:{sample_issue['line_number']}")
    print(f"Issue: {sample_issue['issue_text']}")
    print(f"Rule: {sample_issue['rule_id']}")
    print(f"Recommendation: {sample_issue['fix_suggestion']}")

def main():
    """Run all demos."""
    print("IMPROVED ANALYSIS SYSTEM DEMONSTRATION")
    print("=" * 60)
    print("This demo shows the enhanced analysis capabilities including:")
    print("- Structured analysis results")
    print("- Multiple analysis categories")
    print("- Batch analysis planning")
    print("- Comprehensive reporting")
    print("- Multiple export formats")
    
    demo_analysis_result_structure()
    demo_analysis_categories()
    demo_batch_analysis_planning()
    demo_analysis_reporting()
    demo_export_formats()
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("The improved analysis system provides:")
    print("✓ Enhanced UI with better options and result presentation")
    print("✓ Comprehensive test coverage for analysis capabilities")
    print("✓ Structured analysis results with consistent formatting")
    print("✓ Multiple analysis types (security, quality, dynamic)")
    print("✓ Batch analysis support with progress tracking")
    print("✓ Advanced filtering and export options")
    print("✓ Real-time progress updates and queue management")

if __name__ == '__main__':
    main()
