"""
Reports routes for the Flask application
=======================================

Reports-related web routes that render Jinja templates.
"""

from flask import Blueprint, send_file, flash, redirect, url_for, request
from flask_login import current_user

from app.utils.template_paths import render_template_compat as render_template
from app.paths import REPORTS_DIR

# Import shared utilities
from ..shared_utils import _gather_file_reports, _get_recent_analyses

# Create blueprint
reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

# Require authentication
@reports_bp.before_request
def require_authentication():
    """Require authentication for all report endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access reports.', 'info')
        return redirect(url_for('auth.login', next=request.url))

@reports_bp.route('/')
def reports_index():
    """Show analysis results dashboard."""
    analyses = _get_recent_analyses()
    files = _gather_file_reports(10)

    # Template name adjusted after header removal refactor: index_main.html now holds the content.
    return render_template(
        'pages/reports/index_main.html',
        analyses=analyses,
        files=files
    )

@reports_bp.route('/download/<path:fname>')
def download_report(fname: str):
    """Download generated report files."""
    target = REPORTS_DIR / fname
    if not target.exists() or not target.is_file():
        from flask import abort
        abort(404)
    if target.resolve().parent != REPORTS_DIR.resolve():
        from flask import abort
        abort(400)
    return send_file(target, as_attachment=True, download_name=target.name)