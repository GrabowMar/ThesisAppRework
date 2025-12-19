"""Statistics routes - Big Picture Dashboard.

Provides high-level system statistics supplementary to the Reports module.
Focuses on aggregate data, trends, and health indicators.

Note: API endpoints have been moved to /api/statistics/ blueprint.
This file now only serves the dashboard shell template.
"""
from __future__ import annotations

import logging
from flask import Blueprint, render_template

logger = logging.getLogger(__name__)

stats_bp = Blueprint("stats", __name__, url_prefix="/statistics")


@stats_bp.route("/")
def statistics_overview():
    """Render the statistics dashboard shell (client-side rendered)."""
    return render_template(
        "pages/statistics/statistics_main.html",
        page_title="Statistics Dashboard",
        page_icon="fas fa-chart-line"
    )