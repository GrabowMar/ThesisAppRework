"""
Tasks routes for the Flask application
=======================================

Tasks-related web routes that render Jinja templates.
"""

from flask import Blueprint

# Create blueprint
tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')

@tasks_bp.route('/')
def tasks_overview():
    """Deprecated: redirect to main dashboard live tasks section."""
    from flask import redirect, url_for
    return redirect(url_for('main.dashboard') + '#live-tasks')
