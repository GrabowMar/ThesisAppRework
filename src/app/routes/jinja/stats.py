"""
Statistics routes for the Flask application
=======================================

Statistics-related web routes that render Jinja templates.
"""

from flask import Blueprint, current_app

from app.utils.template_paths import render_template_compat as render_template

# Create blueprint
stats_bp = Blueprint('statistics', __name__, url_prefix='/statistics')

@stats_bp.route('/')
def statistics_overview():
    """Main statistics dashboard."""
    try:
        # Placeholder data - in real implementation this would fetch actual statistics
        context = {
            'page_title': 'Statistics Overview',
            'stats': {
                'total_models': 0,
                'total_applications': 0,
                'total_calls': 0,
                'success_rate': 85.0,
                'avg_generation_time': '2.5m',
                'successful_calls': 0,
                'recent_generations_7d': 0,
                'recent_generations_30d': 0,
                'avg_apps_per_model': 0,
                'total_providers': 0
            },
            'analysis_stats': {
                'total_security_analyses': 0,
                'total_performance_tests': 0,
                'total_zap_analyses': 0,
                'total_ai_analyses': 0,
                'total_analyses': 0,
                'avg_security_issues': 0.0,
                'avg_performance_score': 0.0,
                'critical_vulnerabilities': 0,
                'high_performance_apps': 0
            },
            'batch_stats': {
                'total_batches': 0,
                'completed_batches': 0,
                'failed_batches': 0,
                'success_rate': 0
            },
            'recent_activity': [],
            'top_models': [],
            'daily_stats': [],
            'error_analysis': {},
            'model_stats': {},
            'capability_stats': {},
            'cost_analysis': {},
            'framework_stats': {},
            'analysis_trends': {},
            'external_data': {}
        }
        return render_template('pages/statistics/statistics_main.html', **context)
    except Exception as e:
        current_app.logger.error(f"Error loading statistics overview: {e}")
        return render_template(
            'pages/errors/errors_main.html',
            error=str(e)
        )