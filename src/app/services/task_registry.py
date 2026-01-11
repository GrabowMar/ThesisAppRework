"""
Global Task Registry for Cross-Service Coordination
====================================================

Thread-safe registry for tracking pending/in-flight tasks across services.
Prevents race conditions between PipelineExecutionService and TaskExecutionService.

This module provides a singleton registry that both services can use to check
if a task for a specific model:app combination is already being processed.

Usage:
    from app.services.task_registry import task_registry
    
    # Before creating a task
    if not task_registry.try_claim_task(model_slug, app_number, pipeline_id):
        # Task already being processed by another service
        return existing_task_id
    
    try:
        task = create_task(...)
        task_registry.mark_task_created(model_slug, app_number, pipeline_id, task.task_id)
    except Exception:
        task_registry.release_claim(model_slug, app_number, pipeline_id)
        raise
"""

import threading
from typing import Dict, Optional, Set, Tuple
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class TaskRegistry:
    """Thread-safe registry for tracking pending tasks across services.
    
    Tracks:
    - Claimed tasks: (model_slug, app_number, pipeline_id) currently being processed
    - Created tasks: Mapping from (model_slug, app_number, pipeline_id) to task_id
    
    Claims are temporary locks that prevent duplicate task creation.
    They should be released after task creation succeeds or fails.
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # Set of (model_slug, app_number, pipeline_id) tuples that are claimed
        self._claimed: Set[Tuple[str, int, Optional[str]]] = set()
        
        # Mapping from (model_slug, app_number, pipeline_id) to task_id
        self._task_map: Dict[Tuple[str, int, Optional[str]], str] = {}
        
        # Timestamp of last claim (for debugging/stale claim detection)
        self._claim_times: Dict[Tuple[str, int, Optional[str]], datetime] = {}
    
    def _make_key(self, model_slug: str, app_number: int, pipeline_id: Optional[str] = None) -> Tuple[str, int, Optional[str]]:
        """Create a standardized key for lookups."""
        return (model_slug, app_number, pipeline_id)
    
    def try_claim_task(
        self, 
        model_slug: str, 
        app_number: int, 
        pipeline_id: Optional[str] = None,
        caller: str = "unknown"
    ) -> bool:
        """Try to claim a task slot for the given model:app combination.
        
        Args:
            model_slug: Model identifier
            app_number: App number
            pipeline_id: Optional pipeline ID (for pipeline-scoped uniqueness)
            caller: Name of the calling service (for logging)
            
        Returns:
            True if claim was successful (slot was available)
            False if claim failed (another service already claimed it)
        """
        key = self._make_key(model_slug, app_number, pipeline_id)
        
        with self._lock:
            # Check if already claimed
            if key in self._claimed:
                logger.debug(
                    "[TaskRegistry] Claim DENIED for %s app %s (pipeline=%s) by %s - already claimed",
                    model_slug, app_number, pipeline_id, caller
                )
                return False
            
            # Check if task already exists
            if key in self._task_map:
                logger.debug(
                    "[TaskRegistry] Claim DENIED for %s app %s (pipeline=%s) by %s - task %s already exists",
                    model_slug, app_number, pipeline_id, caller, self._task_map[key]
                )
                return False
            
            # Claim the slot
            self._claimed.add(key)
            self._claim_times[key] = datetime.now(timezone.utc)
            
            logger.debug(
                "[TaskRegistry] Claim GRANTED for %s app %s (pipeline=%s) by %s",
                model_slug, app_number, pipeline_id, caller
            )
            return True
    
    def release_claim(
        self, 
        model_slug: str, 
        app_number: int, 
        pipeline_id: Optional[str] = None
    ) -> None:
        """Release a claim without recording a task (e.g., on error).
        
        Args:
            model_slug: Model identifier
            app_number: App number
            pipeline_id: Optional pipeline ID
        """
        key = self._make_key(model_slug, app_number, pipeline_id)
        
        with self._lock:
            self._claimed.discard(key)
            self._claim_times.pop(key, None)
            
            logger.debug(
                "[TaskRegistry] Claim RELEASED for %s app %s (pipeline=%s)",
                model_slug, app_number, pipeline_id
            )
    
    def mark_task_created(
        self, 
        model_slug: str, 
        app_number: int, 
        pipeline_id: Optional[str],
        task_id: str
    ) -> None:
        """Record a task as created and release the claim.
        
        Args:
            model_slug: Model identifier
            app_number: App number
            pipeline_id: Optional pipeline ID
            task_id: The created task's ID
        """
        key = self._make_key(model_slug, app_number, pipeline_id)
        
        with self._lock:
            # Record the task
            self._task_map[key] = task_id
            
            # Release the claim
            self._claimed.discard(key)
            self._claim_times.pop(key, None)
            
            logger.debug(
                "[TaskRegistry] Task %s recorded for %s app %s (pipeline=%s)",
                task_id, model_slug, app_number, pipeline_id
            )
    
    def get_existing_task_id(
        self, 
        model_slug: str, 
        app_number: int, 
        pipeline_id: Optional[str] = None
    ) -> Optional[str]:
        """Get the task ID if a task already exists for this model:app.
        
        Args:
            model_slug: Model identifier
            app_number: App number
            pipeline_id: Optional pipeline ID
            
        Returns:
            task_id if exists, None otherwise
        """
        key = self._make_key(model_slug, app_number, pipeline_id)
        
        with self._lock:
            return self._task_map.get(key)
    
    def is_claimed_or_exists(
        self, 
        model_slug: str, 
        app_number: int, 
        pipeline_id: Optional[str] = None
    ) -> bool:
        """Check if a task is claimed or already exists.
        
        Args:
            model_slug: Model identifier
            app_number: App number
            pipeline_id: Optional pipeline ID
            
        Returns:
            True if claimed or exists, False otherwise
        """
        key = self._make_key(model_slug, app_number, pipeline_id)
        
        with self._lock:
            return key in self._claimed or key in self._task_map
    
    def clear_pipeline(self, pipeline_id: str) -> int:
        """Clear all entries for a specific pipeline.
        
        Called when a pipeline completes or fails to clean up registry.
        
        Args:
            pipeline_id: Pipeline ID to clear
            
        Returns:
            Number of entries cleared
        """
        with self._lock:
            cleared = 0
            
            # Find and remove all keys for this pipeline
            keys_to_remove = [
                key for key in self._task_map.keys()
                if key[2] == pipeline_id
            ]
            
            for key in keys_to_remove:
                self._task_map.pop(key, None)
                self._claimed.discard(key)
                self._claim_times.pop(key, None)
                cleared += 1
            
            # Also clear any claims that weren't converted to tasks
            claim_keys_to_remove = [
                key for key in self._claimed
                if key[2] == pipeline_id
            ]
            
            for key in claim_keys_to_remove:
                self._claimed.discard(key)
                self._claim_times.pop(key, None)
                cleared += 1
            
            if cleared > 0:
                logger.info(
                    "[TaskRegistry] Cleared %d entries for pipeline %s",
                    cleared, pipeline_id
                )
            
            return cleared
    
    def cleanup_stale_claims(self, max_age_seconds: float = 300.0) -> int:
        """Remove claims that are older than max_age_seconds.
        
        Stale claims can occur if a service crashes mid-task-creation.
        
        Args:
            max_age_seconds: Maximum age of claims to keep (default: 5 minutes)
            
        Returns:
            Number of stale claims removed
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            stale = []
            
            for key, claim_time in self._claim_times.items():
                age = (now - claim_time).total_seconds()
                if age > max_age_seconds:
                    stale.append(key)
            
            for key in stale:
                self._claimed.discard(key)
                self._claim_times.pop(key, None)
                logger.warning(
                    "[TaskRegistry] Removed stale claim for %s app %s (pipeline=%s)",
                    key[0], key[1], key[2]
                )
            
            return len(stale)
    
    def get_stats(self) -> Dict[str, int]:
        """Get registry statistics."""
        with self._lock:
            return {
                'claimed_count': len(self._claimed),
                'task_count': len(self._task_map),
                'claim_times_count': len(self._claim_times)
            }


# Module-level singleton
task_registry = TaskRegistry()


def get_task_registry() -> TaskRegistry:
    """Get the global task registry singleton."""
    return task_registry
