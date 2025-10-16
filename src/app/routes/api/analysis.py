"""
Analysis API module for managing code analysis operations.
Handles security analysis, performance testing, and analysis summaries.
All tool operations are now delegated to the container-based tool registry.
"""

from flask import Blueprint, jsonify, request
from app.routes.api.common import api_error
from app.engines.container_tool_registry import get_container_tool_registry
import logging

logger = logging.getLogger(__name__)

# Create analysis blueprint
analysis_bp = Blueprint('api_analysis', __name__)

@analysis_bp.route('/tool-registry/custom-analysis', methods=['POST'])
def create_custom_analysis():
    """Create a custom analysis request using container tools."""
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['model_slug', 'app_number']
        for field in required_fields:
            if field not in data:
                return api_error(f"Missing required field: {field}", 400)
        
        # Create custom analysis configuration
        result = {
            'analysis_id': f"custom_{data['app_number']}_{data['model_slug']}",
            'app_number': data['app_number'],
            'model_slug': data['model_slug'],
            'tools': data.get('tools', []),
            'containers': data.get('containers', ['static-analyzer']),
            'created_at': __import__('time').time()
        }
        
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
        # Basic execution plan based on container tools
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        
        plan = {
            'analysis_id': analysis_id,
            'steps': [],
            'estimated_duration': 0
        }
        
        # Create steps for each container
        for container in ['static-analyzer', 'dynamic-analyzer', 'performance-tester']:
            tools = [tool for tool in all_tools.values() if tool.container.value == container]
            if tools:
                plan['steps'].append({
                    'step': len(plan['steps']) + 1,
                    'container': container,
                    'tools': [tool.name for tool in tools if tool.available],
                    'estimated_duration': 60  # seconds
                })
                plan['estimated_duration'] += 60
        
        return jsonify({
            'success': True,
            'data': plan,
            'message': 'Execution plan retrieved successfully'
        })
    except Exception as e:
        logger.error(f"Error fetching execution plan: {str(e)}")
        return api_error(f"Failed to fetch execution plan: {str(e)}", 500)

