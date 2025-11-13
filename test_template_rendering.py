"""Test if report templates can be rendered"""
import sys
import os
from pathlib import Path

# Setup paths
project_root = Path(__file__).parent
src_path = project_root / 'src'
sys.path.insert(0, str(src_path))
os.chdir(str(project_root))

from app.factory import create_app

print("Testing template rendering...")
app = create_app()

with app.app_context():
    # Test data for each template (matches generator output structure)
    test_configs = [
        {
            'template': 'pages/reports/model_analysis.html',
            'context': {
                'report_type': 'model_analysis',
                'model_slug': 'openai_gpt-4',
                'timestamp': '2025-01-15T10:00:00',
                'apps_count': 3,
                'total_tasks': 5,
                'apps': [],
                'aggregated_stats': {
                    'total_findings': 42,
                    'findings_by_severity': {
                        'critical': 2,
                        'high': 10,
                        'medium': 15,
                        'low': 15
                    },
                    'average_findings_per_app': 14.0
                },
                'tools_statistics': {}
            }
        },
        {
            'template': 'pages/reports/app_comparison.html',
            'context': {
                'report_type': 'app_analysis',
                'app_number': 1,
                'timestamp': '2025-01-15T10:00:00',
                'models_count': 3,
                'total_tasks': 3,
                'models': [],
                'comparison': {
                    'best_performing_model': 'openai_gpt-4',
                    'worst_performing_model': 'test_model',
                    'common_findings': [],
                    'common_findings_count': 5,
                    'unique_findings': {},
                    'unique_findings_count': 10,
                    'tool_usage': {}
                }
            }
        },
        {
            'template': 'pages/reports/tool_analysis.html',
            'context': {
                'report_type': 'tool_analysis',
                'timestamp': '2025-01-15T10:00:00',
                'total_tasks': 10,
                'filters': {
                    'tool_name': None,
                    'filter_model': None,
                    'filter_app': None,
                    'date_range': {}
                },
                'tools': [],
                'tools_count': 5,
                'tasks_analyzed': 10,
                'overall_stats': {
                    'total_executions': 50,
                    'total_successful': 45,
                    'total_findings': 100,
                    'overall_success_rate': 90.0
                },
                'insights': {
                    'best_success_rate_tool': 'eslint',
                    'worst_success_rate_tool': 'bandit',
                    'fastest_tool': 'eslint',
                    'slowest_tool': 'zap',
                    'most_findings_tool': 'eslint'
                }
            }
        }
    ]
    
    from flask import render_template
    
    # Create a test request context so url_for works
    with app.test_request_context():
        for test in test_configs:
            try:
                html = render_template(test['template'], **test['context'])
                print(f"✓ {test['template']}: {len(html)} bytes rendered")
            except Exception as e:
                print(f"✗ {test['template']}: {e}")
                import traceback
                traceback.print_exc()

print("\n✓ Template rendering test complete!")
