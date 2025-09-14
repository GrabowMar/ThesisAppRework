"""
Statistics routes for the Flask application
=======================================

Statistics-related web routes that render Jinja templates.
"""

from flask import Blueprint, redirect, url_for

# Create blueprint
stats_bp = Blueprint('statistics', __name__, url_prefix='/statistics')

@stats_bp.route('/')
def statistics_overview():
    """Redirect to main dashboard where statistics are now integrated."""
    return redirect(url_for('main.dashboard'))