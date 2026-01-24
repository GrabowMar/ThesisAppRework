"""Concurrent Generation Runner
================================

Clean, reliable concurrent app generation using asyncio.

Key features:
- asyncio.Semaphore for clean concurrency limiting
- Pre-allocates app numbers atomically before generation starts
- Proper error isolation per job
- Progress callbacks for UI updates
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable

from app.services.generation_v2.code_generator import CodeGenerator
from app.services.generation_v2.config import GenerationConfig
from app.services.generation_v2.scaffolding import ScaffoldingManager
from app.services.generation_v2.code_merger import CodeMerger
from app.constants import GenerationMode

logger = logging.getLogger(__name__)


@dataclass
class GenerationJob:
    """A single generation job specification."""
    model_slug: str
    template_slug: str = 'crud_todo_list'
    app_num: Optional[int] = None  # None = auto-allocate
    generate_frontend: bool = True
    generate_backend: bool = True
    batch_id: Optional[str] = None
    version: int = 1
    
    # Filled in during execution
    allocated_app_num: Optional[int] = None
    

@dataclass
class ConcurrentJobResult:
    """Result of a single concurrent generation job."""
    job_index: int
    model_slug: str
    template_slug: str
    app_number: Optional[int]
    success: bool
    error: Optional[str] = None
    duration_seconds: float = 0.0
    backend_chars: int = 0
    frontend_chars: int = 0
    

class ConcurrentGenerationRunner:
    """Asynchronous concurrent app generator with proper isolation.
    
    Uses asyncio.Semaphore for clean concurrency control instead of 
    ThreadPoolExecutor which has Flask context issues.
    
    Usage:
        runner = ConcurrentGenerationRunner(max_concurrent=3)
        jobs = [
            GenerationJob(model_slug='model_a', template_slug='crud_todo_list'),
            GenerationJob(model_slug='model_a', template_slug='crud_todo_list'),
            GenerationJob(model_slug='model_b', template_slug='crud_todo_list'),
        ]
        results = await runner.generate_batch(jobs)
    """
    
    def __init__(
        self, 
        max_concurrent: int = 2,
        inter_job_delay: float = 1.0,
        on_progress: Optional[Callable[[int, int, ConcurrentJobResult], None]] = None
    ):
        """Initialize runner.
        
        Args:
            max_concurrent: Maximum concurrent generation jobs
            inter_job_delay: Seconds to wait between starting jobs (reduces API pressure)
            on_progress: Optional callback(completed, total, result) for progress updates
        """
        self.max_concurrent = max_concurrent
        self.inter_job_delay = inter_job_delay
        self.on_progress = on_progress
        
        # Initialize services
        self._generator: Optional[CodeGenerator] = None
        self._scaffolding: Optional[ScaffoldingManager] = None
        
        # Tracking
        self._completed = 0
        self._total = 0
        self._lock = asyncio.Lock()
        
        logger.info(f"ConcurrentGenerationRunner initialized (max_concurrent={max_concurrent})")
    
    def _get_generator(self) -> CodeGenerator:
        """Lazy-init code generator."""
        if self._generator is None:
            self._generator = CodeGenerator()
        return self._generator
    
    def _get_scaffolding(self) -> ScaffoldingManager:
        """Lazy-init scaffolding service."""
        if self._scaffolding is None:
            self._scaffolding = ScaffoldingManager()
        return self._scaffolding
    
    async def generate_batch(
        self, 
        jobs: List[GenerationJob],
        batch_id: Optional[str] = None
    ) -> List[ConcurrentJobResult]:
        """Generate multiple apps concurrently.
        
        Args:
            jobs: List of generation job specifications
            batch_id: Optional batch identifier for all jobs
            
        Returns:
            List of ConcurrentJobResult for each job (in same order as input)
        """
        if not jobs:
            return []
        
        self._completed = 0
        self._total = len(jobs)
        
        # Generate batch_id if not provided
        if batch_id is None:
            batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        # Assign batch_id to all jobs
        for job in jobs:
            if job.batch_id is None:
                job.batch_id = batch_id
        
        logger.info(f"Starting batch generation: {len(jobs)} jobs, max_concurrent={self.max_concurrent}")
        
        # STEP 1: Pre-allocate ALL app numbers atomically
        # This prevents race conditions where multiple jobs get same app number
        await self._preallocate_app_numbers(jobs)
        
        # STEP 2: Run all jobs concurrently with semaphore limiting
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def run_with_sem(idx: int, job: GenerationJob) -> ConcurrentJobResult:
            async with semaphore:
                # Add small delay between job starts to reduce API pressure
                if idx > 0 and self.inter_job_delay > 0:
                    await asyncio.sleep(self.inter_job_delay * (idx % self.max_concurrent))
                return await self._run_single_job(idx, job)
        
        # Create tasks for all jobs
        tasks = [run_with_sem(i, job) for i, job in enumerate(jobs)]
        
        # Run all and collect results (exceptions are returned, not raised)
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        results: List[ConcurrentJobResult] = []
        for i, r in enumerate(raw_results):
            if isinstance(r, Exception):
                results.append(ConcurrentJobResult(
                    job_index=i,
                    model_slug=jobs[i].model_slug,
                    template_slug=jobs[i].template_slug,
                    app_number=jobs[i].allocated_app_num,
                    success=False,
                    error=str(r),
                ))
            else:
                results.append(r)
        
        # Log summary
        succeeded = sum(1 for r in results if r.success)
        failed = len(results) - succeeded
        logger.info(f"Batch generation complete: {succeeded}/{len(results)} succeeded, {failed} failed")
        
        return results
    
    async def _preallocate_app_numbers(self, jobs: List[GenerationJob]) -> None:
        """Pre-allocate app numbers for all jobs that need them.
        
        This runs synchronously before any generation starts to prevent
        race conditions in app number assignment.
        """
        from app.models import GeneratedApplication
        from app.extensions import db
        
        # Group by model to allocate sequentially per model
        by_model: Dict[str, List[GenerationJob]] = {}
        for job in jobs:
            if job.app_num is None:  # Only allocate if not specified
                by_model.setdefault(job.model_slug, []).append(job)
        
        for model_slug, model_jobs in by_model.items():
            # Get current max app number for this model
            max_app = db.session.query(
                db.func.max(GeneratedApplication.app_number)
            ).filter(
                GeneratedApplication.model_slug == model_slug
            ).scalar() or 0
            
            # Assign sequential numbers
            for i, job in enumerate(model_jobs):
                job.allocated_app_num = max_app + i + 1
                logger.info(f"Pre-allocated app number {job.allocated_app_num} for {model_slug}")
        
        # For jobs with explicit app_num, use that
        for job in jobs:
            if job.app_num is not None:
                job.allocated_app_num = job.app_num
    
    async def _run_single_job(self, job_index: int, job: GenerationJob) -> ConcurrentJobResult:
        """Execute a single generation job.
        
        Returns GenerationResult (never raises - errors are captured in result).
        """
        start_time = time.time()
        
        result = ConcurrentJobResult(
            job_index=job_index,
            model_slug=job.model_slug,
            template_slug=job.template_slug,
            app_number=job.allocated_app_num,
            success=False,
        )
        
        try:
            logger.info(f"[Job {job_index}] Starting: {job.model_slug}/app{job.allocated_app_num} ({job.template_slug})")
            
            if job.allocated_app_num is None:
                raise ValueError("App number not allocated - call _preallocate_app_numbers first")
            
            # Create config
            config = GenerationConfig(
                model_slug=job.model_slug,
                template_slug=job.template_slug,
                app_num=job.allocated_app_num,
                mode=GenerationMode.GUARDED,
            )
            
            # STEP 1: Create scaffolding
            scaffolding = self._get_scaffolding()
            app_dir = scaffolding.create_scaffolding(config)
            
            if app_dir is None:
                raise RuntimeError(f"Scaffolding creation failed for {config.model_slug}/app{config.app_num}")
            
            # STEP 2: Generate code
            generator = self._get_generator()
            code = await generator.generate(config)
            
            result.backend_chars = len(code.get('backend', ''))
            result.frontend_chars = len(code.get('frontend', ''))
            
            # STEP 3: Merge code into scaffolding
            merger = CodeMerger(app_dir)
            written = merger.merge(code)
            
            # STEP 4: Create DB record
            await self._create_db_record(job, config, code)
            
            result.success = True
            result.duration_seconds = time.time() - start_time
            
            logger.info(
                f"[Job {job_index}] SUCCESS: {job.model_slug}/app{job.allocated_app_num} "
                f"in {result.duration_seconds:.1f}s "
                f"(backend={result.backend_chars}, frontend={result.frontend_chars} chars)"
            )
            
        except Exception as e:
            result.error = str(e)
            result.duration_seconds = time.time() - start_time
            logger.error(f"[Job {job_index}] FAILED: {job.model_slug}/app{job.allocated_app_num}: {e}")
        
        # Update progress
        async with self._lock:
            self._completed += 1
            if self.on_progress:
                try:
                    self.on_progress(self._completed, self._total, result)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")
        
        return result
    
    async def _create_db_record(
        self, 
        job: GenerationJob, 
        config: GenerationConfig,
        code: Dict[str, str]
    ) -> None:
        """Create database record for generated app."""
        from app.models import GeneratedApplication, ModelCapability
        from app.extensions import db
        
        # Get model from DB
        model = ModelCapability.query.filter_by(canonical_slug=job.model_slug).first()
        if not model:
            logger.warning(f"Model {job.model_slug} not found in DB, skipping DB record")
            return
        
        # Check if record already exists
        existing = GeneratedApplication.query.filter_by(
            model_slug=job.model_slug,
            app_number=job.allocated_app_num
        ).first()
        
        if existing:
            # Update existing
            existing.template_slug = job.template_slug
            existing.backend_code = code.get('backend', '')
            existing.frontend_code = code.get('frontend', '')
            existing.generation_status = 'completed'
            existing.updated_at = datetime.now(timezone.utc)
        else:
            # Create new
            app_record = GeneratedApplication(
                model_id=model.model_id,
                model_slug=job.model_slug,
                app_number=job.allocated_app_num,
                template_slug=job.template_slug,
                backend_code=code.get('backend', ''),
                frontend_code=code.get('frontend', ''),
                generation_status='completed',
                version=job.version,
            )
            db.session.add(app_record)
        
        db.session.commit()
        logger.info(f"DB record created/updated for {job.model_slug}/app{job.allocated_app_num}")


# Convenience function for simple usage
async def generate_apps_concurrent(
    model_slugs: List[str],
    template_slug: str = 'crud_todo_list',
    apps_per_model: int = 1,
    max_concurrent: int = 2,
) -> List[ConcurrentJobResult]:
    """Generate multiple apps concurrently.
    
    Args:
        model_slugs: List of model slugs to generate for
        template_slug: Template to use for all apps
        apps_per_model: Number of apps to generate per model
        max_concurrent: Maximum concurrent generations
        
    Returns:
        List of ConcurrentJobResult
    """
    jobs = []
    for model_slug in model_slugs:
        for i in range(apps_per_model):
            jobs.append(GenerationJob(
                model_slug=model_slug,
                template_slug=template_slug,
            ))
    
    runner = ConcurrentGenerationRunner(max_concurrent=max_concurrent)
    return await runner.generate_batch(jobs)
