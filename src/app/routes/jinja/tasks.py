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
    """Render live tasks dashboard (websocket/poll hybrid)."""
    try:
        return render_template('pages/tasks/live.html')
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error loading live tasks page: {e}")
        return render_template('pages/errors/errors_main.html', error=str(e)), 500
