"""
Container Tools API Routes
=========================

API endpoints for the new container-based tool registry.
Provides access to tools grouped by analyzer containers with configuration schemas.
"""

from flask import Blueprint, jsonify, request
import logging
import socket
from typing import Dict

from ...engines.container_tool_registry import (
    get_container_tool_registry,
    AnalyzerContainer,
    container_tool_detail_dict,
)

logger = logging.getLogger(__name__)

# Service port mapping for health checks
SERVICE_PORTS: Dict[str, int] = {
    'static-analyzer': 2001,
    'dynamic-analyzer': 2002,
    'performance-tester': 2003,
    'ai-analyzer': 2004,
}


def _check_service_port(service_name: str, timeout: float = 2.0) -> bool:
    """Check if an analyzer service port is accessible via TCP.
    
    Args:
        service_name: Name of the analyzer service
        timeout: Connection timeout in seconds
        
    Returns:
        True if port is accessible, False otherwise
    """
    port = SERVICE_PORTS.get(service_name)
    if not port:
        return False
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0
    except socket.error:
        return False

# Create blueprint (no URL prefix since it's registered under /api)
container_tools_bp = Blueprint('container_tools', __name__, url_prefix='/container-tools')


@container_tools_bp.route('/all', methods=['GET'])
def get_all_tools():
    """Get all tools from the container registry."""
    try:
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        
        # Convert to serializable format
        tools_data = []
        for tool_name, tool in all_tools.items():
            tool_data = container_tool_detail_dict(tool, schema_as_dict=True)
            tools_data.append(tool_data)
        
        return jsonify({
            'success': True,
            'data': tools_data,
            'total': len(tools_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting all tools: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_tools_bp.route('/containers', methods=['GET'])
def get_containers():
    """Get information about all analyzer containers."""
    try:
        registry = get_container_tool_registry()
        container_info = registry.get_container_info()
        
        return jsonify({
            'success': True,
            'data': container_info
        })
        
    except Exception as e:
        logger.error(f"Error getting containers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_tools_bp.route('/container/<container_name>', methods=['GET'])
def get_container_tools(container_name: str):
    """Get tools for a specific container."""
    try:
        # Map container name to enum
        container_map = {
            'static-analyzer': AnalyzerContainer.STATIC,
            'dynamic-analyzer': AnalyzerContainer.DYNAMIC,
            'performance-tester': AnalyzerContainer.PERFORMANCE,
            'ai-analyzer': AnalyzerContainer.AI
        }
        
        if container_name not in container_map:
            return jsonify({
                'success': False,
                'error': f'Unknown container: {container_name}'
            }), 400
        
        registry = get_container_tool_registry()
        container = container_map[container_name]
        tools = registry.get_tools_by_container(container)
        
        # Convert to serializable format
        tools_data = []
        for tool in tools:
            tool_data = {
                'name': tool.name,
                'display_name': tool.display_name,
                'description': tool.description,
                'container': tool.container.value,
                'tags': list(tool.tags),
                'supported_languages': list(tool.supported_languages),
                'available': tool.available,
                'version': tool.version
            }
            tools_data.append(tool_data)
        
        return jsonify({
            'success': True,
            'data': tools_data,
            'container': container_name,
            'total': len(tools_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting tools for container {container_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_tools_bp.route('/availability', methods=['GET'])
def get_tool_availability():
    """Get real-time tool and container availability."""
    try:
        registry = get_container_tool_registry()
        
        # Check analyzer service availability
        availability_data = {}
        
        # Get container status from analyzer bridge
        try:
            # Check each container service via TCP port check
            for container in AnalyzerContainer:
                service_name = container.value
                try:
                    is_available = _check_service_port(service_name)
                    availability_data[f'{service_name}_status'] = 'running' if is_available else 'stopped'
                except Exception as e:
                    logger.warning(f"Could not check {service_name} status: {e}")
                    availability_data[f'{service_name}_status'] = 'unknown'
            
            # Get tool availability within each container
            all_tools = registry.get_all_tools()
            for tool_name, tool in all_tools.items():
                # Tool is available if its container is running
                container_status = availability_data.get(f'{tool.container.value}_status', 'unknown')
                availability_data[tool_name] = container_status == 'running'
                
        except Exception as e:
            logger.warning(f"Error checking service availability: {e}")
            # Fallback: assume all tools are available
            all_tools = registry.get_all_tools()
            for tool_name in all_tools.keys():
                availability_data[tool_name] = True
        
        return jsonify({
            'success': True,
            'data': availability_data
        })
        
    except Exception as e:
        logger.error(f"Error getting tool availability: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_tools_bp.route('/tool/<tool_name>', methods=['GET'])
def get_tool_details(tool_name: str):
    """Get detailed information about a specific tool."""
    try:
        registry = get_container_tool_registry()
        tool = registry.get_tool(tool_name)
        
        if not tool:
            return jsonify({
                'success': False,
                'error': f'Tool not found: {tool_name}'
            }), 404
        
        tool_data = {
            'name': tool.name,
            'display_name': tool.display_name,
            'description': tool.description,
            'container': tool.container.value,
            'tags': list(tool.tags),
            'supported_languages': list(tool.supported_languages),
            'available': tool.available,
            'version': tool.version,
            'cli_flags': tool.cli_flags,
            'output_formats': tool.output_formats
        }
        
        # Include detailed config schema
        if tool.config_schema:
            tool_data['config_schema'] = {
                'parameters': [
                    {
                        'name': p.name,
                        'type': p.type,
                        'description': p.description,
                        'default': p.default,
                        'required': p.required,
                        'options': p.options,
                        'min_value': p.min_value,
                        'max_value': p.max_value,
                        'pattern': p.pattern
                    }
                    for p in tool.config_schema.parameters
                ],
                'examples': tool.config_schema.examples,
                'documentation_url': tool.config_schema.documentation_url
            }
        
        return jsonify({
            'success': True,
            'data': tool_data
        })
        
    except Exception as e:
        logger.error(f"Error getting tool details for {tool_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_tools_bp.route('/tags', methods=['GET'])
def get_available_tags():
    """Get all available tool tags."""
    try:
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        
        all_tags = set()
        for tool in all_tools.values():
            all_tags.update(tool.tags)
        
        return jsonify({
            'success': True,
            'data': sorted(list(all_tags))
        })
        
    except Exception as e:
        logger.error(f"Error getting available tags: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_tools_bp.route('/languages', methods=['GET'])
def get_supported_languages():
    """Get all supported programming languages."""
    try:
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        
        all_languages = set()
        for tool in all_tools.values():
            all_languages.update(tool.supported_languages)
        
        return jsonify({
            'success': True,
            'data': sorted(list(all_languages))
        })
        
    except Exception as e:
        logger.error(f"Error getting supported languages: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_tools_bp.route('/tools/by-language/<language>', methods=['GET'])
def get_tools_by_language(language: str):
    """Get tools that support a specific programming language."""
    try:
        registry = get_container_tool_registry()
        tools = registry.get_tools_for_language(language)
        
        return jsonify({
            'success': True,
            'data': [tool.name for tool in tools],
            'language': language,
            'total': len(tools)
        })
        
    except Exception as e:
        logger.error(f"Error getting tools for language {language}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@container_tools_bp.route('/tools/by-tags', methods=['POST'])
def get_tools_by_tags():
    """Get tools that have specific tags."""
    try:
        data = request.get_json()
        if not data or 'tags' not in data:
            return jsonify({
                'success': False,
                'error': 'Tags array required in request body'
            }), 400
        
        tags = set(data['tags'])
        registry = get_container_tool_registry()
        tools = registry.get_tools_by_tags(tags)
        
        tools_data = []
        for tool in tools:
            tools_data.append({
                'name': tool.name,
                'display_name': tool.display_name,
                'description': tool.description,
                'container': tool.container.value,
                'tags': list(tool.tags),
                'supported_languages': list(tool.supported_languages)
            })
        
        return jsonify({
            'success': True,
            'data': tools_data,
            'requested_tags': list(tags),
            'total': len(tools_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting tools by tags: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500