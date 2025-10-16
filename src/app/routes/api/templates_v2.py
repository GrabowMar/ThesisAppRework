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
import asyncio
from flask import Blueprint, request

from app.utils.helpers import create_success_response, create_error_response
from app.services.template_renderer import get_template_renderer
from app.services.sample_generation_service import get_sample_generation_service, Template

logger = logging.getLogger(__name__)

templates_v2_bp = Blueprint('templates_v2_api', __name__, url_prefix='/api/v2/templates')


@templates_v2_bp.route('/requirements', methods=['GET'])
def list_requirements():
    """List all available requirement JSON files."""
    try:
        renderer = get_template_renderer()
        requirements = renderer.list_requirements()
        return create_success_response(requirements, message=f"Found {len(requirements)} requirements")
    except Exception as e:
        logger.exception("Failed to list requirements")
        return create_error_response(str(e), 500)


@templates_v2_bp.route('/requirements/<requirement_id>', methods=['GET'])
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


@templates_v2_bp.route('/scaffolding', methods=['GET'])
def list_scaffolding():
    """List all available scaffolding types."""
    try:
        renderer = get_template_renderer()
        scaffolding_types = renderer.list_scaffolding_types()
        return create_success_response(scaffolding_types, message=f"Found {len(scaffolding_types)} scaffolding types")
    except Exception as e:
        logger.exception("Failed to list scaffolding types")
        return create_error_response(str(e), 500)


@templates_v2_bp.route('/template-types', methods=['GET'])
def list_template_types():
    """List all available template types."""
    try:
        renderer = get_template_renderer()
        template_types = renderer.list_template_types()
        return create_success_response(template_types, message=f"Found {len(template_types)} template types")
    except Exception as e:
        logger.exception("Failed to list template types")
        return create_error_response(str(e), 500)


@templates_v2_bp.route('/preview', methods=['POST'])
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


@templates_v2_bp.route('/render/<component>', methods=['POST'])
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


@templates_v2_bp.route('/generate/backend', methods=['POST'])
def generate_backend():
    """
    Generate backend code using the V2 template system.
    
    Expected JSON body:
    {
        "requirement_id": "xsd_verifier",
        "model": "openai/gpt-4",
        "scaffolding_type": "react-flask",
        "template_type": "two-query",
        "temperature": 0.7,  // optional
        "max_tokens": 4000   // optional
    }
    
    Returns the app_num and generation result for tracking.
    """
    try:
        data = request.get_json(silent=True) or {}
        
        requirement_id = data.get('requirement_id')
        model = data.get('model')
        scaffolding_type = data.get('scaffolding_type', 'react-flask')
        template_type = data.get('template_type', 'two-query')
        temperature = data.get('temperature')
        max_tokens = data.get('max_tokens')
        
        if not requirement_id or not model:
            return create_error_response("'requirement_id' and 'model' are required", 400)
        
        renderer = get_template_renderer()
        gen_service = get_sample_generation_service()
        
        # Load and render backend template
        requirements = renderer.load_requirements(requirement_id)
        scaffolding = renderer.load_scaffolding(scaffolding_type)
        backend_prompt = renderer.render_template(
            template_type, 'backend', requirements, scaffolding
        )
        
        # Create Template object for generation service
        app_num = 100  # Use 100 for V2 templates (avoid conflicts with old templates)
        template = Template(
            app_num=app_num,
            name=f"{requirement_id}_backend_v2",
            content=backend_prompt,
            requirements=requirements.get('backend_requirements', []),
            template_type='backend',
            display_name=f"{requirements['name']} (Backend - V2)"
        )
        
        # Register template temporarily
        gen_service.template_registry.templates.append(template)
        gen_service.template_registry._by_name[template.name] = template
        gen_service.template_registry._resort()
        
        # Run generation asynchronously
        result_id, result = asyncio.run(
            gen_service.generate_async(
                template_id=str(app_num),
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                create_backup=True,
                generate_frontend=False,
                generate_backend=True
            )
        )
        
        return create_success_response({
            'result_id': result_id,
            'app_num': app_num,
            'success': result.success if hasattr(result, 'success') else True,
            'model': model,
            'requirement_id': requirement_id,
            'requirement_name': requirements.get('name', ''),
            'duration': result.duration if hasattr(result, 'duration') else 0.0,
            'total_tokens': result.total_tokens if hasattr(result, 'total_tokens') else 0
        }, message="Backend code generated successfully")
        
    except FileNotFoundError as e:
        return create_error_response(str(e), 404)
    except Exception as e:
        logger.exception("Failed to generate backend")
        return create_error_response(str(e), 500)


@templates_v2_bp.route('/generate/frontend', methods=['POST'])
def generate_frontend():
    """
    Generate frontend code using the V2 template system.
    
    Expected JSON body:
    {
        "requirement_id": "xsd_verifier",
        "model": "openai/gpt-4",
        "scaffolding_type": "react-flask",
        "template_type": "two-query",
        "temperature": 0.7,  // optional
        "max_tokens": 4000   // optional
    }
    
    Returns the app_num and generation result for tracking.
    """
    try:
        data = request.get_json(silent=True) or {}
        
        requirement_id = data.get('requirement_id')
        model = data.get('model')
        scaffolding_type = data.get('scaffolding_type', 'react-flask')
        template_type = data.get('template_type', 'two-query')
        temperature = data.get('temperature')
        max_tokens = data.get('max_tokens')
        
        if not requirement_id or not model:
            return create_error_response("'requirement_id' and 'model' are required", 400)
        
        renderer = get_template_renderer()
        gen_service = get_sample_generation_service()
        
        # Load and render frontend template
        requirements = renderer.load_requirements(requirement_id)
        scaffolding = renderer.load_scaffolding(scaffolding_type)
        frontend_prompt = renderer.render_template(
            template_type, 'frontend', requirements, scaffolding
        )
        
        # Create Template object for generation service
        app_num = 100  # Use 100 for V2 templates
        template = Template(
            app_num=app_num,
            name=f"{requirement_id}_frontend_v2",
            content=frontend_prompt,
            requirements=requirements.get('frontend_requirements', []),
            template_type='frontend',
            display_name=f"{requirements['name']} (Frontend - V2)"
        )
        
        # Register template temporarily
        gen_service.template_registry.templates.append(template)
        gen_service.template_registry._by_name[template.name] = template
        gen_service.template_registry._resort()
        
        # Run generation asynchronously
        result_id, result = asyncio.run(
            gen_service.generate_async(
                template_id=str(app_num),
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                create_backup=True,
                generate_frontend=True,
                generate_backend=False
            )
        )
        
        return create_success_response({
            'result_id': result_id,
            'app_num': app_num,
            'success': result.success if hasattr(result, 'success') else True,
            'model': model,
            'requirement_id': requirement_id,
            'requirement_name': requirements.get('name', ''),
            'duration': result.duration if hasattr(result, 'duration') else 0.0,
            'total_tokens': result.total_tokens if hasattr(result, 'total_tokens') else 0
        }, message="Frontend code generated successfully")
        
    except FileNotFoundError as e:
        return create_error_response(str(e), 404)
    except Exception as e:
        logger.exception("Failed to generate frontend")
        return create_error_response(str(e), 500)
