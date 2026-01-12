"""Generation Service
====================

Main orchestration service for app generation.
Simple, linear flow: scaffold → generate → merge → persist.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from app.extensions import db
from app.models import GeneratedApplication, GenerationMode as DBGenerationMode
from app.paths import GENERATED_APPS_DIR
from app.utils.time import utc_now
from app.utils.async_utils import run_async_safely

from .config import GenerationConfig, GenerationMode, GenerationResult
from .scaffolding import ScaffoldingManager, get_scaffolding_manager
from .code_generator import CodeGenerator, get_code_generator
from .code_merger import CodeMerger

logger = logging.getLogger(__name__)


class GenerationService:
    """Orchestrates the complete app generation process.
    
    Flow:
    1. Reserve app number in database
    2. Create scaffolding
    3. Generate code via LLM
    4. Merge code into scaffolding
    5. Update database record
    
    No queues, no workers, no complex retry logic.
    Just simple, synchronous execution.
    """
    
    def __init__(self):
        self.scaffolding = get_scaffolding_manager()
        self.generator = get_code_generator()
    
    def generate(self, config: GenerationConfig) -> GenerationResult:
        """Generate an application synchronously.
        
        Args:
            config: Generation configuration
            
        Returns:
            GenerationResult with success status and details
        """
        start_time = time.time()
        result = GenerationResult(success=False)
        
        logger.info(f"Starting generation: {config.model_slug}/app{config.app_num}")
        logger.info(f"  Template: {config.template_slug}")
        logger.info(f"  Mode: {config.mode.value}")
        
        try:
            # Step 1: Create scaffolding
            logger.info("Step 1/4: Creating scaffolding...")
            app_dir = self.scaffolding.create_scaffolding(config)
            result.app_dir = app_dir
            
            # Step 2: Generate code
            logger.info("Step 2/4: Generating code via LLM...")
            code = run_async_safely(self.generator.generate(config))
            
            # Step 3: Merge code into scaffolding
            logger.info("Step 3/4: Merging generated code...")
            merger = CodeMerger(app_dir)
            
            if config.is_guarded:
                written = merger.merge_guarded(code)
            else:
                written = merger.merge_unguarded(code)
            
            result.artifacts = written
            
            # Step 4: Update database
            logger.info("Step 4/4: Persisting to database...")
            self._persist_to_database(config, app_dir, code)
            
            # Success!
            elapsed = time.time() - start_time
            result.success = True
            result.metrics = {
                'duration_seconds': elapsed,
                'files_written': len(written),
                'queries': 4 if config.is_guarded else 2,
            }
            
            logger.info(f"✅ Generation complete in {elapsed:.1f}s")
            logger.info(f"   App directory: {app_dir}")
            
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            logger.error(f"❌ Generation failed after {elapsed:.1f}s: {error_msg}")
            result.add_error(error_msg)
            result.metrics = {'duration_seconds': elapsed, 'error': error_msg}
        
        return result
    
    async def generate_async(self, config: GenerationConfig) -> GenerationResult:
        """Generate an application asynchronously.
        
        Same as generate() but async-native.
        """
        start_time = time.time()
        result = GenerationResult(success=False)
        
        logger.info(f"Starting async generation: {config.model_slug}/app{config.app_num}")
        
        try:
            # Step 1: Create scaffolding (sync operation)
            app_dir = self.scaffolding.create_scaffolding(config)
            result.app_dir = app_dir
            
            # Step 2: Generate code (async)
            code = await self.generator.generate(config)
            
            # Step 3: Merge code (sync operation)
            merger = CodeMerger(app_dir)
            if config.is_guarded:
                written = merger.merge_guarded(code)
            else:
                written = merger.merge_unguarded(code)
            
            result.artifacts = written
            
            # Step 4: Persist (sync operation)
            self._persist_to_database(config, app_dir, code)
            
            elapsed = time.time() - start_time
            result.success = True
            result.metrics = {
                'duration_seconds': elapsed,
                'files_written': len(written),
                'queries': 4 if config.is_guarded else 2,
            }
            
            logger.info(f"✅ Generation complete in {elapsed:.1f}s")
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Generation failed: {e}")
            result.add_error(str(e))
            result.metrics = {'duration_seconds': elapsed}
        
        return result
    
    def _persist_to_database(self, config: GenerationConfig, app_dir: Path, code: Dict[str, str]) -> None:
        """Persist generation result to database."""
        from app.constants import AnalysisStatus
        
        try:
            # Check if record already exists
            existing = GeneratedApplication.query.filter_by(
                model_slug=config.model_slug,
                app_number=config.app_num,
            ).first()
            
            # Determine what was generated
            has_backend = bool(code.get('backend') or code.get('backend_user'))
            has_frontend = bool(code.get('frontend') or code.get('frontend_user'))
            
            # Get provider from model slug
            provider = config.model_slug.split('_')[0] if '_' in config.model_slug else 'unknown'
            
            if existing:
                # Update existing record
                existing.template_slug = config.template_slug
                existing.generation_mode = (
                    DBGenerationMode.GUARDED if config.is_guarded 
                    else DBGenerationMode.UNGUARDED
                )
                existing.has_backend = has_backend
                existing.has_frontend = has_frontend
                existing.has_docker_compose = True  # Scaffolding includes docker-compose
                existing.updated_at = utc_now()
                existing.generation_status = AnalysisStatus.COMPLETED
                existing.is_generation_failed = False
                existing.error_message = None
            else:
                # Create new record
                app_record = GeneratedApplication(
                    model_slug=config.model_slug,
                    app_number=config.app_num,
                    app_type='fullstack',
                    provider=provider,
                    template_slug=config.template_slug,
                    generation_mode=(
                        DBGenerationMode.GUARDED if config.is_guarded 
                        else DBGenerationMode.UNGUARDED
                    ),
                    has_backend=has_backend,
                    has_frontend=has_frontend,
                    has_docker_compose=True,
                    backend_framework='flask',
                    frontend_framework='react',
                    generation_status=AnalysisStatus.COMPLETED,
                )
                db.session.add(app_record)
            
            db.session.commit()
            logger.debug(f"Persisted generation to database")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to persist to database: {e}")
            # Don't fail the generation for DB errors
    
    def get_next_app_number(self, model_slug: str) -> int:
        """Get the next available app number for a model.
        
        Uses database MAX + 1 in a transaction for atomicity.
        """
        from sqlalchemy import func
        
        try:
            max_num = db.session.query(
                func.max(GeneratedApplication.app_number)
            ).filter_by(
                model_slug=model_slug
            ).scalar()
            
            return (max_num or 0) + 1
            
        except Exception as e:
            logger.warning(f"Error getting next app number: {e}")
            # Fallback: count existing directories
            safe_model = config.safe_model_slug
            model_dir = GENERATED_APPS_DIR / safe_model
            if model_dir.exists():
                existing = [d for d in model_dir.iterdir() if d.is_dir() and d.name.startswith('app')]
                return len(existing) + 1
            return 1


# Singleton instance
_service: Optional[GenerationService] = None


def get_generation_service() -> GenerationService:
    """Get shared generation service instance."""
    global _service
    if _service is None:
        _service = GenerationService()
    return _service


# Convenience function for simple generation
def generate_app(
    model_slug: str,
    template_slug: str,
    app_num: Optional[int] = None,
    mode: str = 'guarded',
    **kwargs
) -> GenerationResult:
    """Generate an app with minimal configuration.
    
    Args:
        model_slug: Model identifier (e.g., 'anthropic_claude-3-5-haiku')
        template_slug: Template identifier (e.g., 'crud_todo_list')
        app_num: App number (auto-assigned if None)
        mode: 'guarded' (4-query) or 'unguarded' (2-query)
        **kwargs: Additional config options
        
    Returns:
        GenerationResult
    """
    service = get_generation_service()
    
    if app_num is None:
        app_num = service.get_next_app_number(model_slug)
    
    config = GenerationConfig(
        model_slug=model_slug,
        template_slug=template_slug,
        app_num=app_num,
        mode=GenerationMode.GUARDED if mode == 'guarded' else GenerationMode.UNGUARDED,
        **kwargs
    )
    
    return service.generate(config)
