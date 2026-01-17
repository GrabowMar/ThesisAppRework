"""Generation Service
====================

Main orchestration service for app generation.
Simple, linear flow: scaffold → generate backend → scan → generate frontend → merge → persist.
"""

import logging
import time
import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Optional, Dict, Any

from app.extensions import db
from app.models import GeneratedApplication
from app.paths import GENERATED_APPS_DIR
from app.utils.time import utc_now
from app.utils.async_utils import run_async_safely
from app.paths import REQUIREMENTS_DIR

from .config import GenerationConfig, GenerationResult
from .scaffolding import ScaffoldingManager, get_scaffolding_manager
from .code_generator import CodeGenerator, get_code_generator
from .code_merger import CodeMerger

logger = logging.getLogger(__name__)


class GenerationService:
    """Orchestrates the complete app generation process.
    
    Flow:
    1. Reserve app number in database
    2. Create scaffolding
    3. Generate backend code via LLM
    4. Scan backend for API context
    5. Generate frontend code via LLM (with backend context)
    6. Merge code into scaffolding
    7. Update database record
    """
    
    def __init__(self):
        self.scaffolding = get_scaffolding_manager()
        self.generator = get_code_generator()

    def get_template_catalog(self) -> list[dict[str, Any]]:
        """Return available generation templates with metadata."""
        import json

        catalog: list[dict[str, Any]] = []
        seen_slugs = set()

        if not REQUIREMENTS_DIR.exists():
            logger.debug("Requirements directory missing: %s", REQUIREMENTS_DIR)
            return catalog

        for req_file in sorted(REQUIREMENTS_DIR.glob('*.json')):
            try:
                data = json.loads(req_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping invalid JSON in %s: %s", req_file.name, exc)
                continue
            except OSError as exc:
                logger.warning("Failed to read %s: %s", req_file.name, exc)
                continue

            template_slug = data.get('slug')
            if template_slug is None:
                continue

            name = data.get('name')
            if not name:
                continue

            normalized_slug = template_slug.lower().replace('-', '_')
            if req_file.stem.lower().replace('-', '_') != normalized_slug:
                continue

            if template_slug in seen_slugs:
                continue
            seen_slugs.add(template_slug)

            catalog.append({
                'slug': template_slug,
                'name': name,
                'description': data.get('description', ''),
                'category': data.get('category', 'general'),
                'complexity': data.get('complexity') or 'medium',
                'features': data.get('features') or [],
                'tech_stack': data.get('tech_stack') or {},
                'filename': req_file.name,
            })

        logger.info("Loaded %s valid templates from %s", len(catalog), REQUIREMENTS_DIR)
        return catalog

    def get_generation_status(self) -> dict[str, Any]:
        """Return basic generation system status for UI dashboards."""
        return {
            'in_flight_count': 0,
            'available_slots': 0,
            'max_concurrent': 0,
            'in_flight_keys': [],
            'system_healthy': True,
        }

    def get_summary_metrics(self) -> dict[str, Any]:
        """Return summary metrics for UI dashboards."""
        summary = {
            'total_results': 0,
            'total_templates': 0,
            'total_models': 0,
            'recent_results': 0,
        }

        try:
            from sqlalchemy import func
            from app.models import ModelCapability

            summary['total_results'] = GeneratedApplication.query.count()
            summary['total_models'] = ModelCapability.query.count()

            day_ago = utc_now() - timedelta(days=1)
            summary['recent_results'] = (
                GeneratedApplication.query
                .filter(GeneratedApplication.created_at >= day_ago)
                .count()
            )
        except Exception:
            pass

        summary['total_templates'] = len(self.get_template_catalog())
        return summary

    async def generate_full_app(
        self,
        model_slug: str,
        app_num: Optional[int],
        template_slug: str,
        generate_frontend: bool = True,
        generate_backend: bool = True,
        batch_id: Optional[str] = None,
        parent_app_id: Optional[int] = None,
        version: int = 1,
        **kwargs
    ) -> dict:
        """Generate a complete app with standard response payload."""
        app_number = app_num or self.get_next_app_number(model_slug)

        config = GenerationConfig(
            model_slug=model_slug,
            template_slug=template_slug,
            app_num=app_number,
        )

        loop = asyncio.get_running_loop()
        gen_result = await loop.run_in_executor(None, self.generate, config)

        success = gen_result.success
        errors = list(gen_result.errors) if gen_result.errors else ([] if success else [gen_result.error_message])

        return {
            'success': success,
            'scaffolded': gen_result.app_dir is not None,
            'backend_generated': bool(generate_backend) and success,
            'frontend_generated': bool(generate_frontend) and success,
            'errors': errors,
            'app_number': app_number,
            'app_num': app_number,
            'app_dir': str(gen_result.app_dir) if gen_result.app_dir else None,
            'metrics': gen_result.metrics,
        }
    
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
        
        try:
            # Step 1: Create scaffolding
            logger.info("Step 1/3: Creating scaffolding...")
            app_dir = self.scaffolding.create_scaffolding(config)
            result.app_dir = app_dir
            
            # Step 2: Generate code (backend → scan → frontend)
            logger.info("Step 2/3: Generating code via LLM...")
            code = run_async_safely(self.generator.generate(config))
            
            # Step 3: Merge code into scaffolding
            logger.info("Step 3/3: Merging generated code...")
            merger = CodeMerger(app_dir)
            written = merger.merge(code)
            result.artifacts = written
            
            # Persist to database
            logger.info("Persisting to database...")
            self._persist_to_database(config, app_dir, code)
            
            # Success!
            elapsed = time.time() - start_time
            result.success = True
            result.metrics = {
                'duration_seconds': elapsed,
                'files_written': len(written),
                'queries': 2,
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
        """Generate an application asynchronously."""
        start_time = time.time()
        result = GenerationResult(success=False)
        
        logger.info(f"Starting async generation: {config.model_slug}/app{config.app_num}")
        
        try:
            # Step 1: Create scaffolding
            app_dir = self.scaffolding.create_scaffolding(config)
            result.app_dir = app_dir
            
            # Step 2: Generate code
            code = await self.generator.generate(config)
            
            # Step 3: Merge code
            merger = CodeMerger(app_dir)
            written = merger.merge(code)
            result.artifacts = written
            
            # Persist to database
            self._persist_to_database(config, app_dir, code)
            
            elapsed = time.time() - start_time
            result.success = True
            result.metrics = {
                'duration_seconds': elapsed,
                'files_written': len(written),
                'queries': 2,
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
            existing = GeneratedApplication.query.filter_by(
                model_slug=config.model_slug,
                app_number=config.app_num,
            ).first()
            
            has_backend = bool(code.get('backend'))
            has_frontend = bool(code.get('frontend'))
            provider = config.model_slug.split('_')[0] if '_' in config.model_slug else 'unknown'
            
            if existing:
                existing.template_slug = config.template_slug
                existing.has_backend = has_backend
                existing.has_frontend = has_frontend
                existing.has_docker_compose = True
                existing.updated_at = utc_now()
                existing.generation_status = AnalysisStatus.COMPLETED
                existing.is_generation_failed = False
                existing.error_message = None
            else:
                app_record = GeneratedApplication(
                    model_slug=config.model_slug,
                    app_number=config.app_num,
                    app_type='fullstack',
                    provider=provider,
                    template_slug=config.template_slug,
                    has_backend=has_backend,
                    has_frontend=has_frontend,
                    has_docker_compose=True,
                    backend_framework='flask',
                    frontend_framework='react',
                    generation_status=AnalysisStatus.COMPLETED,
                )
                db.session.add(app_record)
            
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to persist to database: {e}")
    
    def get_next_app_number(self, model_slug: str) -> int:
        """Get the next available app number for a model."""
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
            return 1


# Singleton instance
_service: Optional[GenerationService] = None


def get_generation_service() -> GenerationService:
    """Get shared generation service instance."""
    global _service
    if _service is None:
        _service = GenerationService()
    return _service


def generate_app(
    model_slug: str,
    template_slug: str,
    app_num: Optional[int] = None,
    **kwargs
) -> GenerationResult:
    """Generate an app with minimal configuration."""
    service = get_generation_service()
    
    if app_num is None:
        app_num = service.get_next_app_number(model_slug)
    
    config = GenerationConfig(
        model_slug=model_slug,
        template_slug=template_slug,
        app_num=app_num,
        **kwargs
    )
    
    return service.generate(config)
