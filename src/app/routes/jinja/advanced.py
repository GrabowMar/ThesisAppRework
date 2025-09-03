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
    return render_template(
        'single_page.html',
        page_title='Applications Grid',
        page_icon='fas fa-th',
        main_partial='partials/apps_grid/apps_grid.html'
    )

@advanced_bp.route('/models')
def models_overview():
    """Main models overview page."""
    return render_template(
        'single_page.html',
        page_title='Models Overview',
        page_icon='fas fa-layer-group',
        main_partial='partials/models/overview.html'
    )