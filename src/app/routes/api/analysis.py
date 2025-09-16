"""
Analysis API module for managing code analysis operations.
Handles security analysis, performance testing, and analysis summaries.
"""

from flask import Blueprint, jsonify, request
from app.routes.api.common import api_error
from app.services.service_locator import ServiceLocator
import logging

logger = logging.getLogger(__name__)

# Create analysis blueprint
analysis_bp = Blueprint('api_analysis', __name__)

@analysis_bp.route('/tool-registry/tools')
def get_analysis_tools():
    """Get all available analysis tools."""
    try:
        tool_service = ServiceLocator.get_tool_registry_service()
        tools = tool_service.get_all_tools(enabled_only=True)
        return jsonify({
            'success': True,
            'data': tools,
            'message': f'Found {len(tools)} analysis tools'
        })
    except Exception as e:
        logger.error(f"Error fetching analysis tools: {str(e)}")
        return api_error(f"Failed to fetch analysis tools: {str(e)}", 500)

@analysis_bp.route('/tool-registry/tools/by-category')
def get_tools_by_category():
    """Get tools grouped by category."""
    try:
        tool_service = ServiceLocator.get_tool_registry_service()
        tools_by_category = tool_service.get_tools_by_category(enabled_only=True)
        return jsonify({
            'success': True,
            'data': tools_by_category,
            'message': 'Tools retrieved by category'
        })
    except Exception as e:
        logger.error(f"Error fetching tools by category: {str(e)}")
        return api_error(f"Failed to fetch tools by category: {str(e)}", 500)

@analysis_bp.route('/tool-registry/categories')
def get_tool_categories():
    """Get all available tool categories."""
    try:
        tool_service = ServiceLocator.get_tool_registry_service()
        categories = tool_service.get_tool_categories()
        return jsonify({
            'success': True,
            'data': categories,
            'message': f'Found {len(categories)} tool categories'
        })
    except Exception as e:
        logger.error(f"Error fetching tool categories: {str(e)}")
        return api_error(f"Failed to fetch tool categories: {str(e)}", 500)

@analysis_bp.route('/tool-registry/profiles')
def get_analysis_profiles():
    """Get all available analysis profiles."""
    try:
        tool_service = ServiceLocator.get_tool_registry_service()
        profiles = tool_service.get_analysis_profiles(include_builtin=True)
        return jsonify({
            'success': True,
            'data': profiles,
            'message': f'Found {len(profiles)} analysis profiles'
        })
    except Exception as e:
        logger.error(f"Error fetching analysis profiles: {str(e)}")
        return api_error(f"Failed to fetch analysis profiles: {str(e)}", 500)

@analysis_bp.route('/tool-registry/custom-analysis', methods=['POST'])
def create_custom_analysis():
    """Create a custom analysis request."""
    try:
        tool_service = ServiceLocator.get_tool_registry_service()
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['model_slug', 'app_number']
        for field in required_fields:
            if field not in data:
                return api_error(f"Missing required field: {field}", 400)
        
        result = tool_service.create_custom_analysis(data)
        return jsonify({
            'success': True,
            'data': result,
            'message': 'Custom analysis created successfully'
        })
    except Exception as e:
        logger.error(f"Error creating custom analysis: {str(e)}")
        return api_error(f"Failed to create custom analysis: {str(e)}", 500)

@analysis_bp.route('/tool-registry/execution-plan/<int:analysis_id>')
def get_execution_plan(analysis_id):
    """Get execution plan for a custom analysis."""
    try:
        tool_service = ServiceLocator.get_tool_registry_service()
        plan = tool_service.get_analysis_execution_plan(analysis_id)
        return jsonify({
            'success': True,
            'data': plan,
            'message': 'Execution plan retrieved successfully'
        })
    except Exception as e:
        logger.error(f"Error fetching execution plan: {str(e)}")
        return api_error(f"Failed to fetch execution plan: {str(e)}", 500)

@analysis_bp.route('/stats/analysis')
def get_analysis_stats():
    """Get analysis statistics."""
    # TODO: Move implementation from api.py
    return api_error("Analysis stats endpoint not yet migrated", 501)

@analysis_bp.route('/analysis/summary')
def get_analysis_summary():
    """Get analysis summary."""
    # TODO: Move implementation from api.py
    return api_error("Analysis summary endpoint not yet migrated", 501)

@analysis_bp.route('/analysis/active-tests')
def get_active_tests():
    """Get active analysis tests."""
    # TODO: Move implementation from api.py
    return api_error("Active tests endpoint not yet migrated", 501)