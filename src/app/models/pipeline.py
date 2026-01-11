"""
Pipeline Execution Model
========================

Persists automation pipeline state to the database for reliability.
Pipelines survive server restarts and can be resumed.
Pipeline stages:
- Generation: Create sample applications from templates
- Analysis: Run static/dynamic/performance/AI analysis on generated apps

Note: Reports stage was removed (Dec 2025) - use Reports module separately."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import json
import logging

logger = logging.getLogger('pipeline_model')
import uuid

from ..extensions import db
from ..constants import AnalysisStatus


class PipelineExecutionStatus:
    """Pipeline execution status constants."""
    PENDING = 'pending'
    RUNNING = 'running'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    PARTIAL_SUCCESS = 'partial_success'  # Some tasks succeeded, some failed
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class PipelineExecution(db.Model):
    """
    Pipeline execution model for persistent pipeline state.
    
    Stores the complete state of an automation pipeline including:
    - Configuration (models, templates, analysis settings)
    - Progress tracking for each stage
    - Job results
    - Error handling
    """
    
    __tablename__ = 'pipeline_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    pipeline_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Pipeline metadata
    name = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=PipelineExecutionStatus.PENDING, index=True)
    current_stage = db.Column(db.String(20), nullable=False, default='generation')
    current_job_index = db.Column(db.Integer, nullable=False, default=0)
    
    # Configuration (JSON)
    config_json = db.Column(db.Text, nullable=False)
    
    # Progress tracking (JSON)
    progress_json = db.Column(db.Text, nullable=False)
    
    # Results tracking
    error_message = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship to User
    user = db.relationship('User', backref=db.backref('pipeline_executions', lazy='dynamic'))
    
    def __init__(self, user_id: int, config: Dict[str, Any], name: Optional[str] = None):
        """Initialize a new pipeline execution.
        
        Config structure:
        {
            'generation': {
                'mode': 'generate' | 'existing',
                'models': [...],
                'templates': [...],
                'existingApps': [...],  # For existing mode
            },
            'analysis': {
                'enabled': True,
                'tools': [...],
                'options': {
                    'parallel': True,
                    'maxConcurrentTasks': 2,  # Default parallelism limit (match generation)
                    'autoStartContainers': True,
                    'stopAfterAnalysis': True,
                },
            },
        }
        """
        self.pipeline_id = f"pipeline_{uuid.uuid4().hex[:12]}"
        self.user_id = user_id
        self.name = name
        self.config_json = json.dumps(config)
        
        # Initialize progress based on config
        gen_config = config.get('generation', {})
        generation_mode = gen_config.get('mode', 'generate')
        
        if generation_mode == 'existing':
            # Existing apps mode - count selected apps (generation step is skipped)
            existing_apps = gen_config.get('existingApps', [])
            total_generation_jobs = len(existing_apps)
        else:
            # Generate mode - count model/template combinations
            models = gen_config.get('models', [])
            templates = gen_config.get('templates', [])
            total_generation_jobs = len(models) * len(templates)
        
        analysis_enabled = config.get('analysis', {}).get('enabled', True)
        analysis_options = config.get('analysis', {}).get('options', {})
        
        # Generation parallelism configuration (default: 2 concurrent to avoid overwhelming LLM APIs)
        gen_options = gen_config.get('options', {})
        gen_use_parallel = gen_options.get('parallel', True)  # Default to parallel for efficiency
        gen_max_concurrent = gen_options.get('maxConcurrentTasks', 2) if gen_use_parallel else 1
        
        # Analysis parallelism configuration (default: 2 concurrent tasks, matching generation)
        max_concurrent = analysis_options.get('maxConcurrentTasks', 2)
        use_parallel = analysis_options.get('parallel', True)  # Default to parallel for batch efficiency
        
        progress = {
            'generation': {
                'total': total_generation_jobs,
                'completed': 0,
                'failed': 0,
                'status': 'pending',
                'results': [],
                # Parallelism tracking for batch generation
                'max_concurrent': gen_max_concurrent,
                'in_flight': 0,  # Currently running jobs
            },
            'analysis': {
                'total': total_generation_jobs if analysis_enabled else 0,
                'completed': 0,
                'failed': 0,
                'status': 'pending' if analysis_enabled else 'skipped',
                # Task tracking (main_task_ids is authoritative, task_ids is deprecated)
                'main_task_ids': [],      # AUTHORITATIVE: Main analysis tasks (one per model:app)
                'subtask_ids': [],        # Subtasks created by create_main_task_with_subtasks
                'task_ids': [],           # DEPRECATED: Legacy for backwards compatibility only
                'submitted_apps': [],     # model:app_number pairs already submitted (duplicate prevention)
                'retryable_apps': [],     # NEW: model:app pairs that can be retried (transient failures)
                # Parallelism tracking for batch analysis
                'max_concurrent': max_concurrent if use_parallel else 1,
                'in_flight': 0,  # Currently running tasks
            },
        }
        self.progress_json = json.dumps(progress)
    
    def __repr__(self) -> str:
        return f'<PipelineExecution {self.pipeline_id} ({self.status})>'
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        return json.loads(self.config_json) if self.config_json else {}
    
    @config.setter
    def config(self, value: Dict[str, Any]):
        """Set configuration from dictionary."""
        self.config_json = json.dumps(value)
    
    @property
    def progress(self) -> Dict[str, Any]:
        """Get progress as dictionary."""
        return json.loads(self.progress_json) if self.progress_json else {}
    
    @progress.setter
    def progress(self, value: Dict[str, Any]):
        """Set progress from dictionary."""
        self.progress_json = json.dumps(value)
    
    def update_progress(self, stage: str, **updates) -> None:
        """Update progress for a specific stage."""
        progress = self.progress
        if stage in progress:
            progress[stage].update(updates)
            self.progress = progress
    
    def add_generation_result(self, result: Dict[str, Any]) -> bool:
        """Add a generation result to progress.
        
        Returns:
            True if this result caused a stage transition (generation -> analysis),
            False otherwise. Caller should NOT call advance_job_index() when True.
        """
        progress = self.progress
        
        # Track submitted job indices for duplicate prevention
        # Use job_index to allow multiple apps with same model:template
        job_index = result.get('job_index')
        model_slug = result.get('model_slug')
        template_slug = result.get('template_slug')
        
        # Check for duplicate result BEFORE incrementing counters
        is_duplicate = False
        if job_index is not None and model_slug and template_slug:
            if 'submitted_jobs' not in progress['generation']:
                progress['generation']['submitted_jobs'] = []
            # Include job_index in key to allow multiple apps with same model:template
            job_key = f"{job_index}:{model_slug}:{template_slug}"
            if job_key in progress['generation']['submitted_jobs']:
                # Duplicate result - don't increment counters
                is_duplicate = True
                logger.warning(
                    f"[add_generation_result] Duplicate result for job {job_index} "
                    f"({model_slug}:{template_slug}) - ignoring"
                )
            else:
                progress['generation']['submitted_jobs'].append(job_key)
        
        # Always append to results for debugging, but only increment counters for new results
        progress['generation']['results'].append(result)
        
        if not is_duplicate:
            if result.get('success', False):
                progress['generation']['completed'] += 1
            else:
                progress['generation']['failed'] += 1
        
        # Check if generation is complete
        total = progress['generation']['total']
        done = progress['generation']['completed'] + progress['generation']['failed']
        stage_transitioned = False
        if done >= total:
            progress['generation']['status'] = 'completed'
            self.current_stage = 'analysis'
            self.current_job_index = 0  # Reset for analysis stage
            stage_transitioned = True
            logger.debug(
                "[add_generation_result] Stage transition to analysis, reset job_index to 0"
            )
        else:
            progress['generation']['status'] = 'running'
        
        self.progress = progress
        return stage_transitioned
    
    def add_analysis_task_id(self, task_id: str, success: bool = True,
                             model_slug: Optional[str] = None, app_number: Optional[int] = None,
                             is_main_task: bool = True, subtask_ids: Optional[List[str]] = None) -> None:
        """Record an analysis task with proper tracking for main tasks and subtasks.
        
        IMPORTANT: main_task_ids is the AUTHORITATIVE source for task counting.
        task_ids is DEPRECATED and maintained only for backwards compatibility.
        Always use main_task_ids for counting and completion checks.
        
        Args:
            task_id: The task ID or error/skip marker
            success: Whether task creation succeeded (not execution)
            model_slug: Model slug for duplicate tracking
            app_number: App number for duplicate tracking
            is_main_task: True for main tasks, False for subtasks
            subtask_ids: List of subtask IDs if this is a main task with subtasks
        """
        progress = self.progress
        
        # Initialize tracking arrays if they don't exist (backwards compatibility)
        if 'main_task_ids' not in progress['analysis']:
            progress['analysis']['main_task_ids'] = []
        if 'subtask_ids' not in progress['analysis']:
            progress['analysis']['subtask_ids'] = []
        if 'task_ids' not in progress['analysis']:
            progress['analysis']['task_ids'] = []
        if 'submitted_apps' not in progress['analysis']:
            progress['analysis']['submitted_apps'] = []
        if 'retryable_apps' not in progress['analysis']:
            progress['analysis']['retryable_apps'] = []
        
        # Add to appropriate list based on task type
        # main_task_ids is AUTHORITATIVE for completion counting
        if is_main_task:
            progress['analysis']['main_task_ids'].append(task_id)
            # Also add subtask IDs if provided
            if subtask_ids:
                progress['analysis']['subtask_ids'].extend(subtask_ids)
        else:
            progress['analysis']['subtask_ids'].append(task_id)
        
        # DEPRECATED: Add to legacy task_ids for backwards compatibility only
        # New code should use main_task_ids instead
        progress['analysis']['task_ids'].append(task_id)
        
        # Track submitted model:app pairs to prevent race condition duplicates
        if model_slug and app_number is not None:
            job_key = f"{model_slug}:{app_number}"
            if job_key not in progress['analysis']['submitted_apps']:
                progress['analysis']['submitted_apps'].append(job_key)
            # Remove from retryable if it was there (successfully submitted now)
            retryable = progress['analysis'].get('retryable_apps', [])
            if job_key in retryable:
                retryable.remove(job_key)
                progress['analysis']['retryable_apps'] = retryable
        
        # For skipped or error tasks, mark as failed immediately
        if task_id.startswith('skipped') or task_id.startswith('error:'):
            progress['analysis']['failed'] += 1
            # Check if analysis is complete (all tasks are skipped/error)
            total = progress['analysis']['total']
            done = progress['analysis']['completed'] + progress['analysis']['failed']
            if done >= total:
                progress['analysis']['status'] = 'completed'
                self.current_stage = 'done'
                self.status = PipelineExecutionStatus.COMPLETED
                self.completed_at = datetime.now(timezone.utc)
        else:
            # For real task IDs, track them but don't mark completed yet
            # The pipeline executor will poll for actual completion
            progress['analysis']['status'] = 'running'
        
        self.progress = progress
    
    def mark_job_retryable(self, model_slug: str, app_number: int) -> None:
        """Mark a job as retryable after a transient failure.
        
        This removes the job from submitted_apps and adds it to retryable_apps,
        allowing it to be resubmitted on the next pipeline run.
        
        Args:
            model_slug: Model slug
            app_number: App number
        """
        progress = self.progress
        job_key = f"{model_slug}:{app_number}"
        
        # Initialize arrays if needed
        if 'submitted_apps' not in progress['analysis']:
            progress['analysis']['submitted_apps'] = []
        if 'retryable_apps' not in progress['analysis']:
            progress['analysis']['retryable_apps'] = []
        
        # Remove from submitted_apps
        submitted = progress['analysis']['submitted_apps']
        if job_key in submitted:
            submitted.remove(job_key)
            progress['analysis']['submitted_apps'] = submitted
        
        # Add to retryable_apps if not already there
        retryable = progress['analysis']['retryable_apps']
        if job_key not in retryable:
            retryable.append(job_key)
            progress['analysis']['retryable_apps'] = retryable
        
        self.progress = progress
        logger.info(f"[Pipeline] Marked {job_key} as retryable")
    
    def update_analysis_completion(self, completed: int, failed: int) -> bool:
        """Update analysis completion counts from actual task statuses.
        
        Args:
            completed: Number of MAIN tasks that reached COMPLETED status
            failed: Number of MAIN tasks that reached FAILED/CANCELLED status
            
        Returns:
            True if all analysis tasks are done (stage should transition)
        """
        progress = self.progress
        progress['analysis']['completed'] = completed
        progress['analysis']['failed'] = failed
        
        # Use main_task_ids for counting (not subtasks or legacy task_ids)
        # This gives accurate count of actual analysis jobs
        main_task_ids = progress['analysis'].get('main_task_ids', [])
        # Fallback to legacy task_ids if main_task_ids not populated
        if not main_task_ids:
            main_task_ids = progress['analysis'].get('task_ids', [])
        
        actual_total = len(main_task_ids) if main_task_ids else progress['analysis']['total']
        
        # Count skipped/error task_ids as part of failed (already counted in main_task_ids)
        skipped_count = sum(
            1 for tid in main_task_ids
            if tid.startswith('skipped') or tid.startswith('error:')
        )
        
        # Also count partial_success as completed (they produced results)
        partial_count = progress['analysis'].get('partial_success', 0)
        
        done = completed + failed + skipped_count + partial_count
        
        if done >= actual_total and actual_total > 0:
            progress['analysis']['status'] = 'completed'
            self.current_stage = 'done'
            
            # Determine final status:
            # - COMPLETED if all tasks succeeded (no failures)
            # - PARTIAL_SUCCESS if some tasks failed but at least one succeeded
            # - FAILED if all tasks failed (no successes)
            total_failures = failed + skipped_count
            total_successes = completed + partial_count
            
            if total_failures == 0:
                self.status = PipelineExecutionStatus.COMPLETED
            elif total_successes > 0:
                self.status = PipelineExecutionStatus.PARTIAL_SUCCESS
            else:
                self.status = PipelineExecutionStatus.FAILED
            
            self.completed_at = datetime.now(timezone.utc)
            self.progress = progress
            return True
        
        self.progress = progress
        return False
    
    def start(self) -> None:
        """Mark pipeline as started."""
        self.status = PipelineExecutionStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
        self.current_stage = 'generation'
        
        progress = self.progress
        progress['generation']['status'] = 'running'
        self.progress = progress
    
    def pause(self) -> None:
        """Pause the pipeline."""
        self.status = PipelineExecutionStatus.PAUSED
    
    def resume(self) -> None:
        """Resume a paused pipeline."""
        self.status = PipelineExecutionStatus.RUNNING
    
    def cancel(self) -> None:
        """Cancel the pipeline."""
        self.status = PipelineExecutionStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
    
    def fail(self, error_message: str) -> None:
        """Mark pipeline as failed."""
        self.status = PipelineExecutionStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now(timezone.utc)
    
    def get_overall_progress(self) -> float:
        """Calculate overall progress percentage (0-100).
        
        Progress is split between generation (50%) and analysis (50%).
        If analysis is disabled, generation is 100%.
        Result is always capped at 100% to prevent display issues.
        """
        progress = self.progress
        
        gen = progress.get('generation', {})
        analysis = progress.get('analysis', {})
        
        gen_total = gen.get('total', 0)
        gen_done = gen.get('completed', 0) + gen.get('failed', 0)
        
        analysis_total = analysis.get('total', 0)
        analysis_done = analysis.get('completed', 0) + analysis.get('failed', 0)
        
        # If both stages have 0 jobs, return 0
        if gen_total == 0 and analysis_total == 0:
            return 0.0
        
        # Calculate stage-weighted progress
        gen_weight = 0.5 if analysis_total > 0 else 1.0
        analysis_weight = 0.5 if analysis_total > 0 else 0.0
        
        # Cap individual stage progress at 100% (handles cases where done > total due to race conditions)
        gen_progress = min((gen_done / gen_total * 100) if gen_total > 0 else 100.0, 100.0)
        analysis_progress = min((analysis_done / analysis_total * 100) if analysis_total > 0 else 0.0, 100.0)
        
        # Cap overall progress at 100%
        return min(round(gen_progress * gen_weight + analysis_progress * analysis_weight, 1), 100.0)
    
    def get_next_job(self) -> Optional[Dict[str, Any]]:
        """Get the next job to execute based on current stage and index."""
        config = self.config
        progress = self.progress
        
        logger.debug(
            "[get_next_job] Pipeline %s: stage=%s, job_index=%d",
            getattr(self, 'pipeline_id', 'unknown'), self.current_stage, self.current_job_index
        )
        
        if self.current_stage == 'generation':
            gen_config = config.get('generation', {})
            generation_mode = gen_config.get('mode', 'generate')
            
            if generation_mode == 'existing':
                # Existing apps mode - skip generation entirely
                # Return None to trigger stage transition
                logger.debug("[get_next_job] Existing mode in generation stage - returning None")
                return None
            
            # Generate mode - need models and templates
            models = gen_config.get('models', [])
            templates = gen_config.get('templates', [])
            
            if not models or not templates:
                return None
            
            job_index = self.current_job_index
            num_templates = len(templates)
            model_idx = job_index // num_templates
            template_idx = job_index % num_templates
            
            if model_idx >= len(models):
                return None
            
            return {
                'stage': 'generation',
                'job_index': job_index,
                'model_slug': models[model_idx],
                'template_slug': templates[template_idx],
            }
        
        elif self.current_stage == 'analysis':
            analysis_config = config.get('analysis', {})
            if not analysis_config.get('enabled', True):
                logger.debug("[get_next_job] Analysis disabled - returning None")
                return None
            
            gen_config = config.get('generation', {})
            generation_mode = gen_config.get('mode', 'generate')
            
            if generation_mode == 'existing':
                # Existing apps mode - get jobs from existingApps
                existing_apps = gen_config.get('existingApps', [])
                job_index = self.current_job_index
                
                logger.debug(
                    "[get_next_job] Existing mode in analysis stage: job_index=%d, existing_apps_count=%d",
                    job_index, len(existing_apps)
                )
                
                if job_index >= len(existing_apps):
                    logger.debug("[get_next_job] Job index >= existing apps count - returning None")
                    return None
                
                app_ref = existing_apps[job_index]
                # app_ref can be dict {"model": "...", "app": N} or string "model_slug:N"
                if isinstance(app_ref, dict):
                    model_slug = app_ref.get('model')
                    app_number = app_ref.get('app')
                else:
                    model_slug, app_number = app_ref.rsplit(':', 1)
                
                logger.debug("[get_next_job] Returning analysis job for %s:%s", model_slug, app_number)
                return {
                    'stage': 'analysis',
                    'job_index': job_index,
                    'model_slug': model_slug,
                    'app_number': int(app_number) if app_number is not None else 0,  # type: ignore[arg-type]
                    'success': True,  # Existing apps are already generated
                }
            else:
                # Generate mode - get jobs from generation results
                gen_results = progress.get('generation', {}).get('results', [])
                job_index = self.current_job_index
                
                if job_index >= len(gen_results):
                    return None
                
                gen_result = gen_results[job_index]
                
                # Handle both 'app_number' and 'app_num' keys for compatibility
                # The generation service may use either key depending on the code path
                app_number = gen_result.get('app_number')
                if app_number is None:
                    app_number = gen_result.get('app_num')
                if app_number is None:
                    logger.warning(
                        "[get_next_job] No app_number found in generation result for job %d: %s",
                        job_index, gen_result
                    )
                    # Return failure if we can't determine app number
                    return {
                        'stage': 'analysis',
                        'job_index': job_index,
                        'model_slug': gen_result.get('model_slug'),
                        'app_number': -1,
                        'success': False,
                        'error': 'Missing app_number in generation result',
                    }
                
                return {
                    'stage': 'analysis',
                    'job_index': job_index,
                    'model_slug': gen_result.get('model_slug'),
                    'app_number': int(app_number),
                    'success': gen_result.get('success', False),
                }
        
        # Pipeline only has generation and analysis stages (reports removed Dec 2025)
        return None
    
    def advance_job_index(self) -> None:
        """Advance to the next job index."""
        self.current_job_index += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.pipeline_id,
            'user_id': self.user_id,
            'name': self.name,
            'status': self.status,
            'stage': self.current_stage,
            'config': self.config,
            'progress': self.progress,
            'overall_progress': self.get_overall_progress(),
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def get_by_id(cls, pipeline_id: str, user_id: Optional[int] = None) -> Optional['PipelineExecution']:
        """Get pipeline by ID, optionally filtered by user."""
        query = cls.query.filter_by(pipeline_id=pipeline_id)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.first()
    
    @classmethod
    def get_running_pipelines(cls) -> List['PipelineExecution']:
        """Get all pipelines that are currently running."""
        return cls.query.filter_by(status=PipelineExecutionStatus.RUNNING).all()
    
    @classmethod
    def get_user_pipelines(cls, user_id: int, limit: int = 20) -> List['PipelineExecution']:
        """Get recent pipelines for a user."""
        return cls.query.filter_by(user_id=user_id).order_by(cls.created_at.desc()).limit(limit).all()
