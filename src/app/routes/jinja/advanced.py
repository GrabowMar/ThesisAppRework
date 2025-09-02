"""
Advanced routes for the Flask application
=======================================

Advanced features web routes that render Jinja templates.
"""

from flask import Blueprint

from app.utils.template_paths import render_template_compat as render_template

# Create blueprint
advanced_bp = Blueprint('advanced', __name__, url_prefix='/advanced')

@advanced_bp.route('/apps')
def apps_grid():
    """Main apps grid page."""
    # Directly render new applications index template (replaces single_page wrapper)
    return render_template(
        'views/applications/index.html',
        page_title='Applications Grid'
    )

@advanced_bp.route('/models')
def models_overview():
    """Main models overview page."""
    # Reuse models overview page (new structure)
    return render_template(
        'pages/models/overview.html',
        page_title='Models Overview'
    )