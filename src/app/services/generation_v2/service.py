"""Generation Service
====================

Main orchestration service for app generation.
Simple, linear flow: scaffold → generate → merge → persist.
"""

import logging
import time
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

from app.extensions import db
from app.models import GeneratedApplication, GenerationMode as DBGenerationMode
from app.paths import GENERATED_APPS_DIR
from app.utils.time import utc_now
from app.utils.async_utils import run_async_safely
from app.paths import REQUIREMENTS_DIR

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
                logger.warning("Skipping %s: missing 'slug' field", req_file.name)
                continue

            name = data.get('name')
            if not name:
                logger.warning("Skipping %s: missing 'name' field", req_file.name)
                continue

            normalized_slug = template_slug.lower().replace('-', '_')
            if req_file.stem.lower().replace('-', '_') != normalized_slug:
                logger.warning(
                    "Slug mismatch in %s: file has slug='%s', filename is %s",
                    req_file.name, template_slug, req_file.stem
                )
                continue

            if template_slug in seen_slugs:
                logger.error("Duplicate template slug %s in %s", template_slug, req_file.name)
                continue
            seen_slugs.add(template_slug)

            description = data.get('description', '')
            category = data.get('category', 'general')
            complexity = data.get('complexity') or data.get('difficulty') or 'medium'

            features = data.get('features') or data.get('key_features') or []
            if isinstance(features, str):
                features = [features]

            tech_stack = data.get('tech_stack') or data.get('stack') or {}
            if not isinstance(tech_stack, dict):
                tech_stack = {'value': tech_stack}

            catalog.append({
                'slug': template_slug,
                'name': name,
                'description': description,
                'category': category,
                'complexity': complexity,
                'features': features,
                'tech_stack': tech_stack,
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
        generation_mode: str = 'guarded',
        use_auto_fix: bool = True,
    ) -> dict:
        """Generate a complete app with standard response payload."""
        mode = GenerationMode.GUARDED if generation_mode == 'guarded' else GenerationMode.UNGUARDED
        app_number = app_num or self.get_next_app_number(model_slug)

        config = GenerationConfig(
            model_slug=model_slug,
            template_slug=template_slug,
            app_num=app_number,
            mode=mode,
            auto_fix=use_auto_fix,
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
            'generation_mode': generation_mode,
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

            # Step 3.5: Post-generation healing to fix common dependency/import issues
            if config.auto_fix:
                try:
                    from app.services.dependency_healer import get_dependency_healer, heal_generated_app
                    logger.info("Running dependency healer (auto-fix enabled)...")
                    pre_fix = get_dependency_healer(auto_fix=False).validate_app(app_dir)
                    healing_result = heal_generated_app(app_dir, auto_fix=True)
                    result.metrics['healing'] = {
                        'success': healing_result.success,
                        'issues_found': healing_result.issues_found,
                        'issues_fixed': healing_result.issues_fixed,
                        'changes_made': healing_result.changes_made,
                        'frontend_issues': healing_result.frontend_issues,
                        'backend_issues': healing_result.backend_issues,
                        'errors': healing_result.errors,
                        'pre_fix': {
                            'issues_found': pre_fix.issues_found,
                            'frontend_issues': pre_fix.frontend_issues,
                            'backend_issues': pre_fix.backend_issues,
                            'errors': pre_fix.errors,
                        }
                    }
                except Exception as healing_error:
                    logger.warning(f"Dependency healing failed (non-fatal): {healing_error}")
                    result.metrics['healing'] = {'error': str(healing_error)}
            else:
                result.metrics['healing'] = {'skipped': True, 'reason': 'auto_fix disabled'}
            
            # Step 4: Update database
            logger.info("Step 4/4: Persisting to database...")
            self._persist_to_database(config, app_dir, code)
            
            # Success!
            elapsed = time.time() - start_time
            result.success = True
            base_metrics = {
                'duration_seconds': elapsed,
                'files_written': len(written),
                'queries': 4 if config.is_guarded else 2,
            }
            if 'healing' in result.metrics:
                base_metrics['healing'] = result.metrics['healing']
            result.metrics = base_metrics
            
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

            if config.auto_fix:
                try:
                    from app.services.dependency_healer import get_dependency_healer, heal_generated_app
                    logger.info("Running dependency healer (auto-fix enabled)...")
                    pre_fix = get_dependency_healer(auto_fix=False).validate_app(app_dir)
                    healing_result = heal_generated_app(app_dir, auto_fix=True)
                    result.metrics['healing'] = {
                        'success': healing_result.success,
                        'issues_found': healing_result.issues_found,
                        'issues_fixed': healing_result.issues_fixed,
                        'changes_made': healing_result.changes_made,
                        'frontend_issues': healing_result.frontend_issues,
                        'backend_issues': healing_result.backend_issues,
                        'errors': healing_result.errors,
                        'pre_fix': {
                            'issues_found': pre_fix.issues_found,
                            'frontend_issues': pre_fix.frontend_issues,
                            'backend_issues': pre_fix.backend_issues,
                            'errors': pre_fix.errors,
                        }
                    }
                except Exception as healing_error:
                    logger.warning(f"Dependency healing failed (non-fatal): {healing_error}")
                    result.metrics['healing'] = {'error': str(healing_error)}
            else:
                result.metrics['healing'] = {'skipped': True, 'reason': 'auto_fix disabled'}
            
            # Step 4: Persist (sync operation)
            self._persist_to_database(config, app_dir, code)
            
            elapsed = time.time() - start_time
            result.success = True
            base_metrics = {
                'duration_seconds': elapsed,
                'files_written': len(written),
                'queries': 4 if config.is_guarded else 2,
            }
            if 'healing' in result.metrics:
                base_metrics['healing'] = result.metrics['healing']
            result.metrics = base_metrics
            
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
