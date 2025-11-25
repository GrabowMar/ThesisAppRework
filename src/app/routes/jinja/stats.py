"""Statistics routes - Big Picture Dashboard.

Provides high-level system statistics supplementary to the Reports module.
Focuses on aggregate data, trends, and health indicators.
"""
from __future__ import annotations

import logging
from flask import Blueprint, render_template, jsonify, url_for
from flask_login import current_user

from app.services.statistics_service import (
    get_system_overview,
    get_severity_distribution,
    get_analysis_trends,
    get_model_comparison,
    get_recent_activity,
    get_analyzer_health,
    get_tool_effectiveness,
    get_quick_stats,
    get_filesystem_metrics,
)

logger = logging.getLogger(__name__)

stats_bp = Blueprint("stats", __name__, url_prefix="/statistics")


@stats_bp.route("/")
def statistics_overview():
    """Render the main statistics dashboard."""
    context = {
        "page_title": "Statistics Dashboard",
        "page_icon": "fas fa-chart-line",
        # Core KPIs
        "overview": get_system_overview(),
        "severity": get_severity_distribution(),
        "health": get_analyzer_health(),
        # Detailed sections
        "trends": get_analysis_trends(days=14),
        "models": get_model_comparison(),
        "activity": get_recent_activity(limit=15),
        "tools": get_tool_effectiveness(),
        "quick": get_quick_stats(),
        "filesystem": get_filesystem_metrics(),
    }
    return render_template("pages/statistics/statistics_main.html", **context)


# ---------------------------------------------------------------------------
# JSON API Endpoints for dynamic updates / AJAX refresh
# ---------------------------------------------------------------------------

@stats_bp.route("/api/overview")
def api_overview():
    """Get system overview KPIs as JSON."""
    return jsonify(get_system_overview())


@stats_bp.route("/api/severity")
def api_severity():
    """Get severity distribution as JSON."""
    return jsonify(get_severity_distribution())


@stats_bp.route("/api/health")
def api_health():
    """Get analyzer health status as JSON."""
    return jsonify(get_analyzer_health())


@stats_bp.route("/api/trends")
@stats_bp.route("/api/trends/<int:days>")
def api_trends(days: int = 14):
    """Get analysis trends for specified days."""
    return jsonify(get_analysis_trends(days=min(days, 90)))


@stats_bp.route("/api/models")
def api_models():
    """Get model comparison data as JSON."""
    return jsonify(get_model_comparison())


@stats_bp.route("/api/activity")
def api_activity():
    """Get recent activity as JSON."""
    return jsonify(get_recent_activity(limit=20))


@stats_bp.route("/api/tools")
def api_tools():
    """Get tool effectiveness data as JSON."""
    return jsonify(get_tool_effectiveness())


@stats_bp.route("/api/quick")
def api_quick():
    """Get quick stats for widgets."""
    return jsonify(get_quick_stats())


@stats_bp.route("/api/filesystem")
def api_filesystem():
    """Get filesystem metrics as JSON."""
    return jsonify(get_filesystem_metrics())