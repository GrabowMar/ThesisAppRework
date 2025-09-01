"""
Tasks routes for the Flask application
=======================================

Tasks-related web routes that render Jinja templates.
"""

from flask import Blueprint, current_app

from app.utils.template_paths import render_template_compat as render_template

# Create blueprint
tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')

@tasks_bp.route('/')
def tasks_overview():
    """Unified tasks overview."""
    try:
        # Placeholder data - in real implementation this would fetch actual task data
        context = {
            'active': [],
            'queued': [],
            'recent': [],
            'metrics': {
                'active_count': 0,
                'queued_count': 0,
                'recent_24h': 0,
                'completed_today': 0,
            }
        }
        return render_template(
            'layouts/single-page.html',
            page_title='Tasks Overview',
            page_icon='fa-tasks',
            main_partial='pages/tasks/overview.html',
            **context
        )
    except Exception as e:
        current_app.logger.error(f"Error loading tasks overview: {e}")
        return render_template(
            'pages/errors/errors_main.html',
            error=str(e)
        ), 500