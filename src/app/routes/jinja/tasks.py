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
    """Delegate tasks overview to analysis hub (embedded tasks list)."""
    try:
        from app.services.task_service import AnalysisTaskService
        tasks = AnalysisTaskService.get_recent_tasks(limit=25)
        return render_template('pages/analysis/hub_main.html', tasks=tasks)
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error loading tasks overview: {e}")
        return render_template('pages/errors/errors_main.html', error=str(e)), 500