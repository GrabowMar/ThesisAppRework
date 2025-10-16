"""Simple Generation API Routes
===============================

Clean, focused API for code generation with proper scaffolding.

Endpoints:
- POST /api/gen/scaffold       - Create scaffolding for an app
- POST /api/gen/generate        - Generate frontend or backend code
- POST /api/gen/generate-full   - Generate both frontend and backend
- GET  /api/gen/apps            - List all generated apps
- GET  /api/gen/apps/<model>/<app_num> - Get app details
"""

import asyncio
import logging
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app

from app.services.simple_generation_service import (
    get_simple_generation_service,
    GenerationRequest,
)
from app.utils.helpers import create_success_response, create_error_response

logger = logging.getLogger(__name__)

simple_gen_bp = Blueprint('simple_generation', __name__, url_prefix='/api/gen')


@simple_gen_bp.route('/scaffold', methods=['POST'])
def scaffold_app():
    """Create Docker scaffolding for an app.
    
    POST /api/gen/scaffold
    {
        "model_slug": "x-ai/grok-code-fast-1",
        "app_num": 1,
        "force": false
    }
    """
    try:
        data = request.get_json() or {}
        model_slug = data.get('model_slug')
        app_num = data.get('app_num')
        force = data.get('force', False)
        
        if not model_slug or app_num is None:
            return create_error_response(
                "model_slug and app_num are required",
                400
            )
        
        service = get_simple_generation_service()
        success = service.scaffold_app(model_slug, app_num, force)
        
        if success:
            app_dir = service.get_app_dir(model_slug, app_num)
            backend_port, frontend_port = service.get_ports(model_slug, app_num)
            
            return create_success_response({
                'scaffolded': True,
                'app_dir': str(app_dir),
                'backend_port': backend_port,
                'frontend_port': frontend_port
            })
        else:
            return create_error_response("Scaffolding failed", 500)
            
    except Exception as e:
        logger.exception("Scaffold failed")
        return create_error_response(str(e), 500)


@simple_gen_bp.route('/generate', methods=['POST'])
def generate_component():
    """Generate frontend or backend code.
    
    POST /api/gen/generate
    {
        "template_id": 1,
        "model_slug": "x-ai/grok-code-fast-1",
        "app_num": 1,
        "component": "frontend",  // or "backend"
        "temperature": 0.3,
        "max_tokens": 16000,
        "scaffold": true  // auto-scaffold before generating
    }
    """
    try:
        data = request.get_json() or {}
        
        # Extract parameters
        template_id = data.get('template_id')
        model_slug = data.get('model_slug')
        app_num = data.get('app_num')
        component = data.get('component', 'frontend')
        temperature = float(data.get('temperature', 0.3))
        max_tokens = int(data.get('max_tokens', 16000))
        auto_scaffold = data.get('scaffold', True)
        
        # Validate
        if not all([template_id, model_slug, app_num is not None]):
            return create_error_response(
                "template_id, model_slug, and app_num are required",
                400
            )
        
        if component not in ['frontend', 'backend']:
            return create_error_response(
                "component must be 'frontend' or 'backend'",
                400
            )
        
        service = get_simple_generation_service()
        
        # Auto-scaffold if requested
        if auto_scaffold:
            service.scaffold_app(model_slug, app_num)
        
        # Create request
        gen_request = GenerationRequest(
            template_id=int(template_id),
            model_slug=model_slug,
            component=component,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Generate code (async)
        result = asyncio.run(service.generate_code(gen_request))
        
        if not result.success:
            return create_error_response(result.error or "Generation failed", 500)
        
        # Save generated code
        save_result = service.save_generated_code(
            model_slug,
            app_num,
            component,
            result.content
        )
        
        return create_success_response({
            'success': True,
            'component': component,
            'tokens_used': result.tokens_used,
            'duration': result.duration,
            **save_result
        })
        
    except Exception as e:
        logger.exception("Generation failed")
        return create_error_response(str(e), 500)


@simple_gen_bp.route('/generate-full', methods=['POST'])
def generate_full_app():
    """Generate both frontend and backend code.
    
    POST /api/gen/generate-full
    {
        "template_id": 1,
        "model_slug": "x-ai/grok-code-fast-1",
        "app_num": 1,
        "temperature": 0.3,
        "max_tokens": 16000,
        "generate_frontend": true,
        "generate_backend": true
    }
    """
    try:
        data = request.get_json() or {}
        
        # Extract parameters
        template_id = data.get('template_id')
        model_slug = data.get('model_slug')
        app_num = data.get('app_num')
        temperature = float(data.get('temperature', 0.3))
        max_tokens = int(data.get('max_tokens', 16000))
        gen_frontend = data.get('generate_frontend', True)
        gen_backend = data.get('generate_backend', True)
        
        # Validate
        if not all([template_id, model_slug, app_num is not None]):
            return create_error_response(
                "template_id, model_slug, and app_num are required",
                400
            )
        
        service = get_simple_generation_service()
        
        # Scaffold first
        service.scaffold_app(model_slug, app_num)
        
        results = {
            'frontend': None,
            'backend': None,
            'total_tokens': 0,
            'total_duration': 0.0
        }
        
        # Generate frontend
        if gen_frontend:
            frontend_request = GenerationRequest(
                template_id=int(template_id),
                model_slug=model_slug,
                component='frontend',
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            frontend_result = asyncio.run(service.generate_code(frontend_request))
            
            if frontend_result.success:
                save_result = service.save_generated_code(
                    model_slug, app_num, 'frontend', frontend_result.content
                )
                results['frontend'] = {
                    'success': True,
                    'tokens_used': frontend_result.tokens_used,
                    'duration': frontend_result.duration,
                    **save_result
                }
                results['total_tokens'] += frontend_result.tokens_used
                results['total_duration'] += frontend_result.duration
            else:
                results['frontend'] = {
                    'success': False,
                    'error': frontend_result.error
                }
        
        # Generate backend
        if gen_backend:
            backend_request = GenerationRequest(
                template_id=int(template_id),
                model_slug=model_slug,
                component='backend',
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            backend_result = asyncio.run(service.generate_code(backend_request))
            
            if backend_result.success:
                save_result = service.save_generated_code(
                    model_slug, app_num, 'backend', backend_result.content
                )
                results['backend'] = {
                    'success': True,
                    'tokens_used': backend_result.tokens_used,
                    'duration': backend_result.duration,
                    **save_result
                }
                results['total_tokens'] += backend_result.tokens_used
                results['total_duration'] += backend_result.duration
            else:
                results['backend'] = {
                    'success': False,
                    'error': backend_result.error
                }
        
        # Get app info
        app_dir = service.get_app_dir(model_slug, app_num)
        backend_port, frontend_port = service.get_ports(model_slug, app_num)
        
        results.update({
            'app_dir': str(app_dir),
            'backend_port': backend_port,
            'frontend_port': frontend_port
        })
        
        return create_success_response(results)
        
    except Exception as e:
        logger.exception("Full generation failed")
        return create_error_response(str(e), 500)


@simple_gen_bp.route('/apps', methods=['GET'])
def list_apps():
    """List all generated apps.
    
    GET /api/gen/apps
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


@simple_gen_bp.route('/apps/<path:model_slug>/<int:app_num>', methods=['GET'])
def get_app_details(model_slug: str, app_num: int):
    """Get details for a specific app.
    
    GET /api/gen/apps/{model_slug}/{app_num}
    """
    try:
        service = get_simple_generation_service()
        app_dir = service.get_app_dir(model_slug, app_num)
        
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
        
        backend_port, frontend_port = service.get_ports(model_slug, app_num)
        
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
