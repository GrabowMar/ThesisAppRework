"""Template System V2 API Routes
================================

New template system using Jinja2 templates, JSON requirements, and modular scaffolding.
This works alongside the existing template system without breaking backward compatibility.

Endpoints (prefixed with /api/v2/templates):
 - GET    /requirements           List available requirement JSONs
 - GET    /requirements/<id>      Get specific requirement details
 - GET    /scaffolding            List available scaffolding types
 - GET    /template-types         List available template types
 - POST   /preview                Preview rendered templates
 - POST   /generate/backend       Generate backend code
 - POST   /generate/frontend      Generate frontend code
"""

from __future__ import annotations

import logging
from flask import Blueprint, request

from app.utils.helpers import create_success_response, create_error_response
from app.services.template_renderer import get_template_renderer
# Note: Template class removed - templates_v2 uses template_renderer service

logger = logging.getLogger(__name__)

templates_bp = Blueprint('templates_api', __name__, url_prefix='/api/templates')


@templates_bp.route('/requirements', methods=['GET'])
def list_requirements():
    """List all available requirement JSON files."""
    try:
        renderer = get_template_renderer()
        requirements = renderer.list_requirements()
        return create_success_response(requirements, message=f"Found {len(requirements)} requirements")
    except Exception as e:
        logger.exception("Failed to list requirements")
        return create_error_response(str(e), 500)


@templates_bp.route('/requirements/<requirement_id>', methods=['GET'])
def get_requirement(requirement_id: str):
    """Get details of a specific requirement."""
    try:
        renderer = get_template_renderer()
        requirement = renderer.load_requirements(requirement_id)
        return create_success_response(requirement, message="Requirement loaded")
    except FileNotFoundError as e:
        return create_error_response(str(e), 404)
    except Exception as e:
        logger.exception("Failed to get requirement")
        return create_error_response(str(e), 500)


@templates_bp.route('/scaffolding', methods=['GET'])
def list_scaffolding():
    """List all available scaffolding types."""
    try:
        renderer = get_template_renderer()
        scaffolding_types = renderer.list_scaffolding_types()
        return create_success_response(scaffolding_types, message=f"Found {len(scaffolding_types)} scaffolding types")
    except Exception as e:
        logger.exception("Failed to list scaffolding types")
        return create_error_response(str(e), 500)


@templates_bp.route('/template-types', methods=['GET'])
def list_template_types():
    """List all available template types."""
    try:
        renderer = get_template_renderer()
        template_types = renderer.list_template_types()
        return create_success_response(template_types, message=f"Found {len(template_types)} template types")
    except Exception as e:
        logger.exception("Failed to list template types")
        return create_error_response(str(e), 500)


@templates_bp.route('/preview', methods=['POST'])
def preview_templates():
    """
    Preview rendered backend and frontend templates without generating code.
    
    Expected JSON body:
    {
        "requirement_id": "xsd_verifier",
        "scaffolding_type": "react-flask",
        "template_type": "two-query"
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        requirement_id = data.get('requirement_id')
        scaffolding_type = data.get('scaffolding_type', 'react-flask')
        template_type = data.get('template_type', 'two-query')
        
        if not requirement_id:
            return create_error_response("'requirement_id' is required", 400)
        
        renderer = get_template_renderer()
        preview = renderer.preview(template_type, requirement_id, scaffolding_type)
        
        return create_success_response({
            'backend_prompt': preview['backend'],
            'frontend_prompt': preview['frontend'],
            'requirement_id': requirement_id,
            'scaffolding_type': scaffolding_type,
            'template_type': template_type
        }, message="Templates rendered successfully")
        
    except FileNotFoundError as e:
        return create_error_response(str(e), 404)
    except Exception as e:
        logger.exception("Failed to preview templates")
        return create_error_response(str(e), 500)


@templates_bp.route('/render/<component>', methods=['POST'])
def render_template(component: str):
    """
    Render a specific template component (backend or frontend).
    
    URL parameter:
        component: 'backend' or 'frontend'
    
    Expected JSON body:
    {
        "requirement_id": "xsd_verifier",
        "scaffolding_type": "react-flask",
        "template_type": "two-query"
    }
    """
    if component not in ['backend', 'frontend']:
        return create_error_response("Component must be 'backend' or 'frontend'", 400)
    
    try:
        data = request.get_json(silent=True) or {}
        
        requirement_id = data.get('requirement_id')
        scaffolding_type = data.get('scaffolding_type', 'react-flask')
        template_type = data.get('template_type', 'two-query')
        
        if not requirement_id:
            return create_error_response("'requirement_id' is required", 400)
        
        renderer = get_template_renderer()
        
        # Load requirements and scaffolding
        requirements = renderer.load_requirements(requirement_id)
        scaffolding = renderer.load_scaffolding(scaffolding_type)
        
        # Render the specific component
        rendered = renderer.render_template(
            template_type, component, requirements, scaffolding
        )
        
        return create_success_response({
            'prompt': rendered,
            'component': component,
            'requirement_id': requirement_id,
            'requirement_name': requirements.get('name', ''),
            'scaffolding_type': scaffolding_type,
            'template_type': template_type
        }, message=f"{component.capitalize()} template rendered successfully")
        
    except FileNotFoundError as e:
        return create_error_response(str(e), 404)
    except Exception as e:
        logger.exception(f"Failed to render {component} template")
        return create_error_response(str(e), 500)




# NOTE: The following endpoints have been removed because they depended on
# the deprecated sample_generation_service which was deleted:

# NOTE: The following endpoints have been removed because they depended on
# the deprecated sample_generation_service which was deleted:
# - POST /generate/backend
# - POST /generate/frontend
#
# Use the new simple_generation or generation_v2 endpoints instead:
# - POST /api/gen/generate (simple_generation.py)
# - POST /api/gen/v2/generate (generation_v2.py)
