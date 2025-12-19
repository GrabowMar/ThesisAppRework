"""
Statistics API Routes
=====================

Clean REST API for statistics dashboard data.
Provides a single consolidated endpoint returning all dashboard sections.
"""

import logging
from flask import Blueprint, jsonify, request

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

statistics_bp = Blueprint("statistics_api", __name__, url_prefix="/statistics")


@statistics_bp.route("/dashboard", methods=["GET"])
def get_dashboard_data():
    """
    Get complete dashboard data in a single request.
    
    Query params:
        days: int - Number of days for trends (default: 14, max: 90)
        activity_limit: int - Number of recent activities (default: 15, max: 50)
    
    Returns:
        JSON with all dashboard sections
    """
    try:
        # Parse query params
        days = min(int(request.args.get("days", 14)), 90)
        activity_limit = min(int(request.args.get("activity_limit", 15)), 50)
        
        # Gather all data
        data = {
            "success": True,
            "data": {
                "overview": get_system_overview(),
                "severity": get_severity_distribution(),
                "health": get_analyzer_health(),
                "trends": get_analysis_trends(days=days),
                "models": get_model_comparison(),
                "activity": get_recent_activity(limit=activity_limit),
                "tools": get_tool_effectiveness(),
                "quick": get_quick_stats(),
                "filesystem": get_filesystem_metrics(),
            }
        }
        
        return jsonify(data)
        
    except Exception as e:
        logger.exception(f"Error fetching dashboard data: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to fetch dashboard data"
        }), 500


@statistics_bp.route("/overview", methods=["GET"])
def get_overview():
    """Get system overview KPIs."""
    try:
        return jsonify({
            "success": True,
            "data": get_system_overview()
        })
    except Exception as e:
        logger.exception(f"Error fetching overview: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@statistics_bp.route("/severity", methods=["GET"])
def get_severity():
    """Get severity distribution."""
    try:
        return jsonify({
            "success": True,
            "data": get_severity_distribution()
        })
    except Exception as e:
        logger.exception(f"Error fetching severity: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@statistics_bp.route("/health", methods=["GET"])
def get_health():
    """Get analyzer health status."""
    try:
        return jsonify({
            "success": True,
            "data": get_analyzer_health()
        })
    except Exception as e:
        logger.exception(f"Error fetching health: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@statistics_bp.route("/trends", methods=["GET"])
def get_trends():
    """Get analysis trends.
    
    Query params:
        days: int - Number of days (default: 14, max: 90)
    """
    try:
        days = min(int(request.args.get("days", 14)), 90)
        return jsonify({
            "success": True,
            "data": get_analysis_trends(days=days)
        })
    except Exception as e:
        logger.exception(f"Error fetching trends: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@statistics_bp.route("/models", methods=["GET"])
def get_models():
    """Get model comparison data."""
    try:
        return jsonify({
            "success": True,
            "data": get_model_comparison()
        })
    except Exception as e:
        logger.exception(f"Error fetching models: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@statistics_bp.route("/activity", methods=["GET"])
def get_activity():
    """Get recent activity.
    
    Query params:
        limit: int - Number of items (default: 15, max: 50)
    """
    try:
        limit = min(int(request.args.get("limit", 15)), 50)
        return jsonify({
            "success": True,
            "data": get_recent_activity(limit=limit)
        })
    except Exception as e:
        logger.exception(f"Error fetching activity: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@statistics_bp.route("/tools", methods=["GET"])
def get_tools():
    """Get tool effectiveness data."""
    try:
        return jsonify({
            "success": True,
            "data": get_tool_effectiveness()
        })
    except Exception as e:
        logger.exception(f"Error fetching tools: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@statistics_bp.route("/quick", methods=["GET"])
def get_quick():
    """Get quick stats for widgets."""
    try:
        return jsonify({
            "success": True,
            "data": get_quick_stats()
        })
    except Exception as e:
        logger.exception(f"Error fetching quick stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@statistics_bp.route("/filesystem", methods=["GET"])
def get_filesystem():
    """Get filesystem metrics."""
    try:
        return jsonify({
            "success": True,
            "data": get_filesystem_metrics()
        })
    except Exception as e:
        logger.exception(f"Error fetching filesystem metrics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
