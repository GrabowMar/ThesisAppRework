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
- statistics.py: Statistics dashboard API

All routes have been migrated out of this file for better organization.
No route implementations should exist here - only blueprint registrations.

SECURITY: All API routes require authentication except /health endpoint.
"""

from flask import Blueprint, request, jsonify
from flask_login import current_user, login_user

# Import all the specialized blueprints
from .core import core_bp
from .models import models_bp
from .system import system_bp
from .dashboard import dashboard_bp
from .applications import applications_bp
from .tool_registry import tool_registry_bp
from .analysis import analysis_bp
from .container_tools import container_tools_bp
from .reports import reports_bp
from .statistics import statistics_bp

# Create the main API blueprint that will orchestrate all others
api_bp = Blueprint('api', __name__)

# Protect all API routes with authentication
@api_bp.before_request
def require_authentication():
    """
    Require authentication for all API endpoints except health checks.
    Supports both session-based auth and Bearer token auth.
    This prevents unauthorized access via direct API calls.
    """
    # Allow health check without authentication
    if request.endpoint and 'health' in request.endpoint:
        return None
    
    # Check if already authenticated via session
    if current_user.is_authenticated:
        return None
    
    # Try Bearer token authentication
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        try:
            from app.models import User
            user = User.verify_api_token(token)
            if user:
                login_user(user, remember=False)
                return None
        except Exception:
            pass
    
    # Not authenticated
    return jsonify({
        'error': 'Authentication required',
        'message': 'Please log in or provide a valid Bearer token',
        'login_url': '/auth/login'
    }), 401

# Register all specialized blueprints as nested blueprints
# This allows them to share the same URL prefix while maintaining modularity
api_bp.register_blueprint(core_bp)
api_bp.register_blueprint(models_bp, url_prefix='/models')
api_bp.register_blueprint(system_bp)
api_bp.register_blueprint(dashboard_bp, url_prefix='/dashboard')
api_bp.register_blueprint(applications_bp)
api_bp.register_blueprint(analysis_bp, url_prefix='/analysis')
api_bp.register_blueprint(tool_registry_bp)
api_bp.register_blueprint(container_tools_bp)
api_bp.register_blueprint(reports_bp)
api_bp.register_blueprint(statistics_bp)
