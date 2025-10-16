"""Generation V2 API - Scaffolding-First Approach
=================================================

The RIGHT way to generate apps:
1. Copy scaffolding (Docker infrastructure) FIRST
2. Generate application code with AI
3. Merge AI code into scaffolding structure
4. Result: Apps that look like scaffolding + app code

Endpoint:
POST /api/gen/v2/generate
{
  "model_slug": "x-ai/grok-code-fast-1",
  "app_num": 1,
  "template_id": 1,
  "generate_frontend": true,
  "generate_backend": true
}
"""

import asyncio
import logging

from flask import Blueprint, request

from app.services.generation_v2 import get_generation_service_v2
from app.utils.helpers import create_success_response, create_error_response

logger = logging.getLogger(__name__)

gen_v2_bp = Blueprint('generation_v2', __name__, url_prefix='/api/gen/v2')


@gen_v2_bp.route('/generate', methods=['POST'])
def generate_v2():
    """Generate application using scaffolding-first approach.
    
    This is the CORRECT way to generate apps.
    """
    try:
        data = request.get_json() or {}
        
        # Required parameters
        model_slug = data.get('model_slug')
        app_num = data.get('app_num')
        template_id = data.get('template_id', 1)
        
        if not model_slug or app_num is None:
            return create_error_response(
                "model_slug and app_num are required",
                400
            )
        
        # Optional flags
        gen_frontend = data.get('generate_frontend', True)
        gen_backend = data.get('generate_backend', True)
        
        logger.info(f"V2 Generation: {model_slug}/app{app_num}")
        logger.info(f"  Frontend: {gen_frontend}, Backend: {gen_backend}")
        
        # Run generation
        service = get_generation_service_v2()
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
            return create_error_response(
                f"Generation failed: {', '.join(result['errors'])}",
                500
            )
            
    except Exception as e:
        logger.exception("V2 generation failed")
        return create_error_response(str(e), 500)


@gen_v2_bp.route('/test-scaffold', methods=['POST'])
def test_scaffold():
    """Test scaffolding only (no AI generation).
    
    Use this to verify scaffolding works correctly.
    """
    try:
        data = request.get_json() or {}
        model_slug = data.get('model_slug', 'test-model/test-1')
        app_num = data.get('app_num', 999)
        
        service = get_generation_service_v2()
        success = service.scaffolding.scaffold(model_slug, app_num)
        
        if success:
            app_dir = service.scaffolding.get_app_dir(model_slug, app_num)
            backend_port, frontend_port = service.scaffolding.get_ports(app_num)
            
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
