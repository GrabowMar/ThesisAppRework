"""Generation API - Scaffolding-First Approach
==============================================

Complete API for scaffolding-first code generation.

The RIGHT way to generate apps:
1. Copy scaffolding (Docker infrastructure) FIRST
2. Generate application code with AI
3. Merge AI code into scaffolding structure
4. Result: Apps that look like scaffolding + app code

Endpoints:
- GET  /api/gen/templates         - List app templates (requirements)
- POST /api/gen/generate          - Generate full application
- POST /api/gen/test-scaffold     - Test scaffolding only
- GET  /api/gen/apps              - List all generated apps
- GET  /api/gen/apps/<model>/<num> - Get app details
"""

import asyncio
import logging

from flask import Blueprint, request, jsonify
from flask_login import current_user

from app.services.generation import get_generation_service
from app.utils.helpers import create_success_response, create_error_response

logger = logging.getLogger(__name__)

gen_bp = Blueprint('generation', __name__, url_prefix='/api/gen')

# Require authentication for all generation API routes
@gen_bp.before_request
def require_authentication():
    """Require authentication for all generation API endpoints."""
    if not current_user.is_authenticated:
        return jsonify({
            'error': 'Authentication required',
            'message': 'Please log in to access this endpoint',
            'login_url': '/auth/login'
        }), 401


@gen_bp.route('/templates', methods=['GET'])
def list_templates():
    """List all available app templates (requirements JSON files).
    
    GET /api/gen/templates
    
    Returns:
    - templates: list of template objects with id, name, description, etc.
    """
    try:
        service = get_generation_service()
        templates = service.get_template_catalog()

        return create_success_response(
            templates,
            message=f"Found {len(templates)} app templates"
        )
    except Exception as e:
        logger.exception("Failed to list templates")
        return create_error_response(str(e), 500)


@gen_bp.route('/scaffold', methods=['POST'])
def scaffold():
    """Create scaffolding for an app (no code generation).
    
    POST /api/gen/scaffold
    {
        "model_slug": "x-ai/grok-code-fast-1",
        "app_num": 1,
        "force": false
    }
    
    Returns:
    - scaffolded: true/false
    - app_dir: path to app directory
    - backend_port, frontend_port
    - files: list of scaffolding files created
    """
    try:
        data = request.get_json() or {}
        model_slug = data.get('model_slug')
        app_num = data.get('app_num')
        
        if not model_slug or app_num is None:
            return create_error_response(
                "model_slug and app_num are required",
                400
            )
        
        service = get_generation_service()
        success = service.scaffolding.scaffold(model_slug, app_num)
        
        if success:
            app_dir = service.scaffolding.get_app_dir(model_slug, app_num)
            backend_port, frontend_port = service.scaffolding.get_ports(model_slug, app_num)
            
            # List scaffolding files created
            files = []
            if app_dir.exists():
                for f in app_dir.rglob('*'):
                    if f.is_file():
                        files.append(str(f.relative_to(app_dir)))
            
            return create_success_response({
                'scaffolded': True,
                'app_dir': str(app_dir),
                'backend_port': backend_port,
                'frontend_port': frontend_port,
                'files': sorted(files),
                'file_count': len(files)
            })
        else:
            return create_error_response("Scaffolding failed", 500)
            
    except Exception as e:
        logger.exception("Scaffold failed")
        return create_error_response(str(e), 500)


@gen_bp.route('/generate', methods=['POST'])
def generate():
    """Generate application using scaffolding-first approach.
    
    This is the CORRECT way to generate apps.
    """
    try:
        data = request.get_json() or {}
        
        # Required parameters
        model_slug_raw = data.get('model_slug')
        app_num = data.get('app_num')
        template_id = data.get('template_id', 1)
        
        # Normalize model slug to match database format (replace / with _)
        model_slug = model_slug_raw.replace('/', '_') if model_slug_raw else None
        
        if not model_slug or app_num is None:
            return create_error_response(
                "model_slug and app_num are required",
                400
            )
        
        # Validate model exists in database
        from app.models import ModelCapability
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            logger.error(f"Model not found in database: {model_slug} (raw: {model_slug_raw})")
            return create_error_response(
                f"Model '{model_slug}' not found in database. Please ensure the model is loaded.",
                404
            )
        
        logger.info(f"Found model: {model.model_name} (ID: {model.model_id})")
        
        # Optional flags
        gen_frontend = data.get('generate_frontend', True)
        gen_backend = data.get('generate_backend', True)
        
        logger.info(f"Generation: {model_slug}/app{app_num}")
        logger.info(f"  OpenRouter model_id: {model.model_id}")
        logger.info(f"  Frontend: {gen_frontend}, Backend: {gen_backend}")
        
        # Run generation
        service = get_generation_service()
        result = asyncio.run(service.generate_full_app(
            model_slug=model_slug,
            app_num=app_num,
            template_id=template_id,
            generate_frontend=gen_frontend,
            generate_backend=gen_backend
        ))
        
        if result['success']:
            return create_success_response(result, "Generation successful")
        else:
            # Provide detailed error information
            errors = result.get('errors', [])
            error_details = {
                'backend_generated': result.get('backend_generated', False),
                'frontend_generated': result.get('frontend_generated', False),
                'scaffolded': result.get('scaffolded', False),
                'errors': errors,
                'model_slug': model_slug,
                'model_id': model.model_id,
                'app_num': app_num
            }
            logger.error(f"Generation failed for {model_slug}/app{app_num}: {errors}")
            return create_error_response(
                f"Generation failed: {', '.join(errors)}",
                500,
                details=error_details
            )
            
    except Exception as e:
        logger.exception("V2 generation failed")
        return create_error_response(str(e), 500)


@gen_bp.route('/test-scaffold', methods=['POST'])
def test_scaffold():
    """Test scaffolding only (no AI generation).
    
    Use this to verify scaffolding works correctly.
    """
    try:
        data = request.get_json() or {}
        model_slug = data.get('model_slug', 'test-model/test-1')
        app_num = data.get('app_num', 999)
        
        service = get_generation_service()
        success = service.scaffolding.scaffold(model_slug, app_num)
        
        if success:
            app_dir = service.scaffolding.get_app_dir(model_slug, app_num)
            backend_port, frontend_port = service.scaffolding.get_ports(model_slug, app_num)
            
            # Check what files exist
            files = []
            for f in app_dir.rglob('*'):
                if f.is_file():
                    files.append(str(f.relative_to(app_dir)))
            
            return create_success_response({
                'scaffolded': True,
                'app_dir': str(app_dir),
                'backend_port': backend_port,
                'frontend_port': frontend_port,
                'files': sorted(files),
                'file_count': len(files)
            })
        else:
            return create_error_response("Scaffolding failed", 500)
            
    except Exception as e:
        logger.exception("Test scaffold failed")
        return create_error_response(str(e), 500)


@gen_bp.route('/apps', methods=['GET'])
def list_apps():
    """List all generated apps.
    
    GET /api/gen/apps
    
    Returns array of apps with metadata:
    - model_slug, app_num, path
    - has_docker_compose, has_backend, has_frontend
    - complete (true if has compose + code)
    """
    try:
        from app.paths import GENERATED_APPS_DIR
        
        apps = []
        
        if not GENERATED_APPS_DIR.exists():
            return create_success_response([])
        
        for model_dir in GENERATED_APPS_DIR.iterdir():
            if not model_dir.is_dir():
                continue
            
            model_slug = model_dir.name
            
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                    continue
                
                try:
                    app_num = int(app_dir.name.replace('app', ''))
                except ValueError:
                    continue
                
                # Check for key files
                has_docker_compose = (app_dir / 'docker-compose.yml').exists()
                has_backend = (app_dir / 'backend' / 'app.py').exists()
                has_frontend = (app_dir / 'frontend' / 'src' / 'App.jsx').exists()
                
                apps.append({
                    'model_slug': model_slug,
                    'app_num': app_num,
                    'path': str(app_dir),
                    'has_docker_compose': has_docker_compose,
                    'has_backend': has_backend,
                    'has_frontend': has_frontend,
                    'complete': has_docker_compose and (has_backend or has_frontend)
                })
        
        # Sort by model slug and app num
        apps.sort(key=lambda x: (x['model_slug'], x['app_num']))
        
        return create_success_response(apps)
        
    except Exception as e:
        logger.exception("Failed to list apps")
        return create_error_response(str(e), 500)


@gen_bp.route('/apps/<path:model_slug>/<int:app_num>', methods=['GET'])
def get_app_details(model_slug: str, app_num: int):
    """Get details for a specific app.
    
    GET /api/gen/apps/{model_slug}/{app_num}
    
    Returns detailed app information including:
    - model_slug, app_num, app_dir
    - backend_port, frontend_port
    - files list with paths, sizes, and generated flag
    - file_count
    """
    try:
        service = get_generation_service()
        app_dir = service.scaffolding.get_app_dir(model_slug, app_num)
        
        if not app_dir.exists():
            return create_error_response("App not found", 404)
        
        # Get all files
        files = []
        for file_path in app_dir.rglob('*'):
            if file_path.is_file():
                rel_path = file_path.relative_to(app_dir)
                files.append({
                    'path': str(rel_path),
                    'size': file_path.stat().st_size,
                    'is_generated': rel_path.parts[0] in ['backend', 'frontend']
                })

        backend_port, frontend_port = service.scaffolding.get_ports(model_slug, app_num)
        
        return create_success_response({
            'model_slug': model_slug,
            'app_num': app_num,
            'app_dir': str(app_dir),
            'backend_port': backend_port,
            'frontend_port': frontend_port,
            'files': files,
            'file_count': len(files)
        })
        
    except Exception as e:
        logger.exception("Failed to get app details")
        return create_error_response(str(e), 500)
