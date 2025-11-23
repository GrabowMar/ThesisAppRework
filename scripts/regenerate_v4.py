import asyncio
import logging
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from app.factory import create_app
from app.services.generation import get_generation_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def regenerate_app(model_slug, app_num, template_slug, version):
    logger.info(f"Starting regeneration for {model_slug} app {app_num} v{version}...")
    service = get_generation_service()
    
    try:
        result = await service.generate_full_app(
            model_slug=model_slug,
            app_num=app_num,
            template_slug=template_slug,
            version=version
        )
        logger.info(f"Finished {model_slug}: Success={result.get('success')}")
        return result
    except Exception as e:
        logger.error(f"Error regenerating {model_slug}: {e}")
        return {'success': False, 'error': str(e)}

async def main():
    app = create_app()
    with app.app_context():
        # Gemini
        await regenerate_app(
            model_slug="google_gemini-3-pro-preview-20251117",
            app_num=1,
            template_slug="api_url_shortener",
            version=4
        )
        
        # Codex
        await regenerate_app(
            model_slug="openai_gpt-5.1-codex-mini-20251113",
            app_num=1,
            template_slug="api_url_shortener",
            version=4
        )

if __name__ == "__main__":
    asyncio.run(main())
