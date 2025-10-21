"""
API Routes Orchestrator
=======================

This module serves as the main API blueprint that orchestrates and consolidates
routes from the various specialized API modules.

The actual route implementations are distributed across focused modules:
- core.py: Basic health, status, and core endpoints
- models.py: Model management and metadata (including /paginated endpoint)
- system.py: System monitoring and health
- dashboard.py: Dashboard stats and fragments
- applications.py: Application lifecycle management
- analysis.py: Analysis operations and statistics
- simple_generation.py: AI-powered code generation
- generation_v2.py: V2 generation with scaffolding-first approach
- container_tools.py: Container-based tool registry
- tool_registry.py: Legacy tool registry (shims to container_tools)

All routes have been migrated out of this file for better organization.
No route implementations should exist here - only blueprint registrations.

SECURITY: All API routes require authentication except /health endpoint.
"""

from flask import Blueprint, request, jsonify
from flask_login import current_user

# Import all the specialized blueprints
from .core import core_bp
from .models import models_bp
from .system import system_bp
from .dashboard import dashboard_bp
from .applications import applications_bp
from .tool_registry import tool_registry_bp
from .analysis import analysis_bp
from .container_tools import container_tools_bp

# Create the main API blueprint that will orchestrate all others
api_bp = Blueprint('api', __name__)

# Protect all API routes with authentication
@api_bp.before_request
def require_authentication():
    """
    Require authentication for all API endpoints except health checks.
    This prevents unauthorized access via direct API calls.
    """
    # Allow health check without authentication
    if request.endpoint and 'health' in request.endpoint:
        return None
    
    # Check if user is authenticated
    if not current_user.is_authenticated:
        return jsonify({
            'error': 'Authentication required',
            'message': 'Please log in to access this endpoint',
            'login_url': '/auth/login'
        }), 401

# Register all specialized blueprints as nested blueprints
# This allows them to share the same URL prefix while maintaining modularity
api_bp.register_blueprint(core_bp)
api_bp.register_blueprint(models_bp, url_prefix='/models')
api_bp.register_blueprint(system_bp)
api_bp.register_blueprint(dashboard_bp, url_prefix='/dashboard')
api_bp.register_blueprint(applications_bp)
api_bp.register_blueprint(analysis_bp)
api_bp.register_blueprint(tool_registry_bp)
api_bp.register_blueprint(container_tools_bp)
