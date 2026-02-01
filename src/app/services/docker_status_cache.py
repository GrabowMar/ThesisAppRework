"""
Docker Status Cache Service
===========================

In-memory cache for Docker container statuses to avoid expensive
Docker API calls on every request. Statuses are refreshed on-demand
with staleness checking, and persisted to database on change.

Design principles:
1. On-demand refresh: Status is checked when requested if stale
2. On-change persistence: Database is updated when status changes
3. Batch lookup: Single `docker ps` call resolves all container statuses
4. Invalidation: Cache entries are invalidated after container operations
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger('svc.docker_status_cache')


@dataclass
class CacheEntry:
    """Single cache entry for an application's Docker status."""
    status: str  # running, stopped, not_created, no_compose, error, unknown
    containers: List[Dict[str, Any]] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    compose_exists: bool = False
    docker_connected: bool = True
    project_name: str = ''
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None

    def is_stale(self, max_age_seconds: int = 30) -> bool:
        """Check if this cache entry is stale."""
        age = datetime.now(timezone.utc) - self.updated_at
        return age > timedelta(seconds=max_age_seconds)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'status': self.status,
            'containers': self.containers,
            'states': self.states,
            'compose_exists': self.compose_exists,
            'docker_connected': self.docker_connected,
            'project_name': self.project_name,
            'updated_at': self.updated_at.isoformat(),
            'is_stale': self.is_stale(),
            'error': self.error
        }


class DockerStatusCache:
    """
    In-memory cache for Docker container statuses.
    
    Usage:
        cache = DockerStatusCache(docker_manager)
        status = cache.get_status('model_slug', 1)
        cache.invalidate('model_slug', 1)  # After container operations
    """

    # Default staleness threshold in seconds
    DEFAULT_STALE_THRESHOLD = 30

    # Status constants
    STATUS_RUNNING = 'running'
    STATUS_STOPPED = 'stopped'
    STATUS_NOT_CREATED = 'not_created'
    STATUS_NO_COMPOSE = 'no_compose'
    STATUS_ERROR = 'error'
    STATUS_UNKNOWN = 'unknown'

    # Docker states that indicate "stopped"
    STOPPED_STATES = frozenset({'exited', 'dead', 'created', 'removing', 'stopped', 'paused'})

    def __init__(self, docker_manager=None, stale_threshold: int = DEFAULT_STALE_THRESHOLD):
        """
        Initialize the Docker status cache.
        
        Args:
            docker_manager: DockerManager instance (optional, will fetch from ServiceLocator if needed)
            stale_threshold: Seconds after which a cache entry is considered stale
        """
        self._cache: Dict[Tuple[str, int], CacheEntry] = {}
        self._lock = threading.RLock()
        self._docker_manager = docker_manager
        self._stale_threshold = stale_threshold
        self._all_statuses_cache: Optional[Dict[str, str]] = None
        self._all_statuses_updated_at: Optional[datetime] = None
        logger.info("DockerStatusCache initialized with stale_threshold=%ds", stale_threshold)

    def _get_docker_manager(self):
        """Get the Docker manager, fetching from ServiceLocator if needed."""
        if self._docker_manager is not None:
            return self._docker_manager
        try:
            from app.services.service_locator import ServiceLocator
            self._docker_manager = ServiceLocator.get_docker_manager()
        except Exception as e:
            logger.warning("Failed to get DockerManager from ServiceLocator: %s", e)
        return self._docker_manager

    def _cache_key(self, model_slug: str, app_number: int) -> Tuple[str, int]:
        """Generate cache key for a model/app pair."""
        return (model_slug, app_number)

    def _get_project_name(self, model_slug: str, app_number: int) -> str:
        """
        Get Docker Compose project name for model/app.
        
        Mirrors the logic in DockerManager._get_project_name() but handles
        the underscore/hyphen conversion carefully.
        """
        # Replace underscores and dots with hyphens for Docker compatibility
        # This must match DockerManager._get_project_name exactly
        safe_model = model_slug.replace('_', '-').replace('.', '-')
        return f"{safe_model}-app{app_number}"

    def _generate_project_name_variants(self, model_slug: str, app_number: int, 
                                        build_id: Optional[str] = None) -> List[str]:
        """
        Generate all possible project name variants for container matching.
        
        Docker Compose project names can vary based on:
        - Underscore vs hyphen in model name
        - With/without dots
        - With/without build_id suffix
        - Legacy naming conventions
        
        Returns list of possible project name prefixes to search for.
        """
        variants = set()
        
        # Standard conversion (what DockerManager does)
        safe_model = model_slug.replace('_', '-').replace('.', '-')
        base_name = f"{safe_model}-app{app_number}"
        variants.add(base_name)
        
        # With build_id suffix (new naming scheme)
        if build_id:
            variants.add(f"{base_name}-{build_id}")
        
        # Try to get build_id from database if not provided
        if not build_id:
            try:
                from app.models import GeneratedApplication
                app = GeneratedApplication.query.filter_by(
                    model_slug=model_slug, app_number=app_number
                ).first()
                if app and app.build_id:
                    variants.add(f"{base_name}-{app.build_id}")
            except Exception:
                pass  # Silently ignore - we'll still match without build_id
        
        # Keep underscores (some older containers may use this)
        variants.add(f"{model_slug}-app{app_number}")
        
        # Alternative with underscores for app separator
        variants.add(f"{safe_model}_app{app_number}")
        variants.add(f"{model_slug}_app{app_number}")
        
        # Without the provider prefix if present (e.g., "claude-3" from "anthropic_claude-3")
        if '_' in model_slug:
            model_part = model_slug.split('_', 1)[1]
            safe_part = model_part.replace('_', '-').replace('.', '-')
            variants.add(f"{safe_part}-app{app_number}")
            variants.add(f"{model_part}-app{app_number}")
        
        return list(variants)

    def get_all_container_statuses_batch(self) -> Dict[str, str]:
        """
        Get status of ALL Docker containers in a single API call.
        
        Returns a dict mapping container names to their status.
        This is much more efficient than individual lookups.
        """
        docker_mgr = self._get_docker_manager()
        if not docker_mgr or not getattr(docker_mgr, 'client', None):
            logger.debug("Docker client not available for batch status lookup")
            return {}

        try:
            # Use the existing list_all_containers method
            containers = docker_mgr.list_all_containers()  # type: ignore[union-attr]
            result: Dict[str, str] = {}
            for c in containers:
                name = c.get('name', '')
                status = c.get('status', 'unknown')
                if name:
                    result[name] = status
            
            logger.debug("Batch status lookup found %d containers", len(result))
            return result
        except Exception as e:
            logger.error("Error in batch container status lookup: %s", e)
            return {}

    def _match_containers_to_app(
        self, 
        model_slug: str, 
        app_number: int, 
        all_containers: Dict[str, str]
    ) -> Tuple[List[str], List[str]]:
        """
        Match containers from batch lookup to a specific app.
        
        Returns (container_names, states) for containers belonging to this app.
        """
        project_variants = self._generate_project_name_variants(model_slug, app_number)
        
        matched_names = []
        matched_states = []
        
        for container_name, status in all_containers.items():
            # Check if container name starts with any project variant
            for variant in project_variants:
                # Container names are typically: {project}_{service}_1 or {project}-{service}-1
                if (container_name.startswith(f"{variant}_") or 
                    container_name.startswith(f"{variant}-") or
                    container_name == variant):
                    matched_names.append(container_name)
                    matched_states.append(status)
                    break
        
        return matched_names, matched_states

    def _determine_status_from_states(
        self, 
        states: List[str], 
        compose_exists: bool
    ) -> str:
        """
        Determine overall app status from container states.
        
        Priority:
        1. Any 'running' -> running
        2. Any stopped states -> stopped  
        3. Containers exist but unknown state -> stopped (safe assumption)
        4. No containers + compose exists -> not_created
        5. No containers + no compose -> no_compose
        """
        normalized_states = [s.lower().strip() for s in states if s]
        
        if any(s == 'running' for s in normalized_states):
            return self.STATUS_RUNNING
        
        if any(s in self.STOPPED_STATES for s in normalized_states):
            return self.STATUS_STOPPED
        
        if normalized_states:
            # Containers exist but state is unusual
            return self.STATUS_STOPPED
        
        if compose_exists:
            return self.STATUS_NOT_CREATED
        
        return self.STATUS_NO_COMPOSE

    def _check_compose_exists(self, model_slug: str, app_number: int) -> bool:
        """Check if docker-compose.yml exists for this app."""
        docker_mgr = self._get_docker_manager()
        if not docker_mgr:
            return False
        
        try:
            compose_path = docker_mgr._get_compose_path(model_slug, app_number)  # type: ignore[union-attr]
            return compose_path.exists()
        except Exception as e:
            logger.debug("Error checking compose path for %s/app%s: %s", model_slug, app_number, e)
            return False

    def _refresh_status(self, model_slug: str, app_number: int) -> CacheEntry:
        """
        Refresh status for a specific app by checking Docker.
        
        This method uses the cached batch lookup if available and fresh,
        otherwise performs a new batch lookup.
        """
        docker_mgr = self._get_docker_manager()
        
        # Check if Docker is available
        docker_connected = docker_mgr is not None and getattr(docker_mgr, 'client', None) is not None
        
        if not docker_connected:
            # Can't check Docker, return unknown with compose check
            compose_exists = self._check_compose_exists(model_slug, app_number)
            status = self.STATUS_NOT_CREATED if compose_exists else self.STATUS_NO_COMPOSE
            return CacheEntry(
                status=status,
                containers=[],
                states=[],
                compose_exists=compose_exists,
                docker_connected=False,
                project_name=self._get_project_name(model_slug, app_number),
                error="Docker client not available"
            )

        try:
            # Check if we have a recent batch lookup
            now = datetime.now(timezone.utc)
            use_cached_batch = (
                self._all_statuses_cache is not None and
                self._all_statuses_updated_at is not None and
                (now - self._all_statuses_updated_at) < timedelta(seconds=self._stale_threshold)
            )
            
            if use_cached_batch and self._all_statuses_cache is not None:
                all_containers = self._all_statuses_cache
            else:
                # Perform new batch lookup
                all_containers = self.get_all_container_statuses_batch()
                self._all_statuses_cache = all_containers
                self._all_statuses_updated_at = now
            
            # Ensure all_containers is not None (should never happen but type checker needs this)
            if all_containers is None:
                all_containers = {}
            
            # Match containers to this app
            container_names, states = self._match_containers_to_app(
                model_slug, app_number, all_containers
            )
            
            # Check compose file exists
            compose_exists = self._check_compose_exists(model_slug, app_number)
            
            # Determine overall status
            status = self._determine_status_from_states(states, compose_exists)
            
            # Build container info dicts
            containers = [
                {'name': name, 'status': all_containers.get(name, 'unknown')}
                for name in container_names
            ]
            
            return CacheEntry(
                status=status,
                containers=containers,
                states=states,
                compose_exists=compose_exists,
                docker_connected=True,
                project_name=self._get_project_name(model_slug, app_number)
            )
            
        except Exception as e:
            logger.error("Error refreshing status for %s/app%s: %s", model_slug, app_number, e)
            compose_exists = self._check_compose_exists(model_slug, app_number)
            return CacheEntry(
                status=self.STATUS_ERROR,
                containers=[],
                states=[],
                compose_exists=compose_exists,
                docker_connected=docker_connected,
                project_name=self._get_project_name(model_slug, app_number),
                error=str(e)
            )

    def get_status(
        self, 
        model_slug: str, 
        app_number: int, 
        force_refresh: bool = False
    ) -> CacheEntry:
        """
        Get Docker status for an application.
        
        Returns cached status if fresh, otherwise refreshes from Docker.
        
        Args:
            model_slug: The model identifier
            app_number: The application number
            force_refresh: Force a refresh even if cache is fresh
            
        Returns:
            CacheEntry with status information
        """
        key = self._cache_key(model_slug, app_number)
        
        with self._lock:
            # Check if we have a cached entry
            entry = self._cache.get(key)
            
            if entry is not None and not force_refresh and not entry.is_stale(self._stale_threshold):
                logger.debug("Cache hit for %s/app%s: %s", model_slug, app_number, entry.status)
                return entry
            
            # Need to refresh
            logger.debug("Cache miss/stale for %s/app%s, refreshing", model_slug, app_number)
            new_entry = self._refresh_status(model_slug, app_number)
            self._cache[key] = new_entry
            
            # Persist to database if status changed
            if entry is None or entry.status != new_entry.status:
                self._persist_status_change(model_slug, app_number, new_entry)
            
            return new_entry

    def _persist_status_change(
        self, 
        model_slug: str, 
        app_number: int, 
        entry: CacheEntry
    ) -> None:
        """
        Persist status change to database.
        
        This updates the GeneratedApplication.container_status and
        last_status_check fields.
        """
        try:
            from app.models import GeneratedApplication
            from app.extensions import db
            
            app = GeneratedApplication.query.filter_by(
                model_slug=model_slug,
                app_number=app_number
            ).first()
            
            if app:
                old_status = app.container_status
                app.container_status = entry.status
                app.last_status_check = entry.updated_at
                db.session.commit()
                logger.debug(
                    "Persisted status change for %s/app%s: %s -> %s",
                    model_slug, app_number, old_status, entry.status
                )
        except Exception as e:
            logger.warning(
                "Failed to persist status change for %s/app%s: %s",
                model_slug, app_number, e
            )
            try:
                from app.extensions import db
                db.session.rollback()
            except Exception:
                pass

    def invalidate(self, model_slug: str, app_number: int) -> None:
        """
        Invalidate cache entry for an application.
        
        Call this after container operations (start, stop, build, etc.)
        to force a refresh on next status check.
        """
        key = self._cache_key(model_slug, app_number)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug("Invalidated cache for %s/app%s", model_slug, app_number)
            
            # Also invalidate the batch cache to ensure fresh data
            self._all_statuses_cache = None
            self._all_statuses_updated_at = None

    def invalidate_all(self) -> None:
        """Invalidate all cached entries."""
        with self._lock:
            self._cache.clear()
            self._all_statuses_cache = None
            self._all_statuses_updated_at = None
            logger.debug("Invalidated all cache entries")

    def get_bulk_status(
        self, 
        apps: List[Tuple[str, int]], 
        force_refresh: bool = False
    ) -> Dict[Tuple[str, int], CacheEntry]:
        """
        Get status for multiple applications efficiently.
        
        This performs a single batch Docker lookup and matches
        containers to all requested apps.
        
        Args:
            apps: List of (model_slug, app_number) tuples
            force_refresh: Force refresh even if cache entries are fresh
            
        Returns:
            Dict mapping (model_slug, app_number) to CacheEntry
        """
        results: Dict[Tuple[str, int], CacheEntry] = {}
        apps_to_refresh: List[Tuple[str, int]] = []
        
        with self._lock:
            # First pass: check cache for fresh entries
            for model_slug, app_number in apps:
                key = self._cache_key(model_slug, app_number)
                entry = self._cache.get(key)
                
                if entry is not None and not force_refresh and not entry.is_stale(self._stale_threshold):
                    results[key] = entry
                else:
                    apps_to_refresh.append((model_slug, app_number))
            
            if not apps_to_refresh:
                return results
            
            # Perform single batch lookup
            all_containers = self.get_all_container_statuses_batch()
            self._all_statuses_cache = all_containers
            self._all_statuses_updated_at = datetime.now(timezone.utc)
            
            # Process apps that need refresh
            for model_slug, app_number in apps_to_refresh:
                key = self._cache_key(model_slug, app_number)
                entry = self._refresh_single_from_batch(model_slug, app_number, all_containers)
                self._cache[key] = entry
                results[key] = entry
                
                # Persist if status changed
                old_entry = self._cache.get(key)
                if old_entry is None or old_entry.status != entry.status:
                    self._persist_status_change(model_slug, app_number, entry)
        
        return results

    def _refresh_single_from_batch(
        self, 
        model_slug: str, 
        app_number: int, 
        all_containers: Dict[str, str]
    ) -> CacheEntry:
        """Refresh a single app's status using pre-fetched batch data."""
        docker_mgr = self._get_docker_manager()
        docker_connected = docker_mgr is not None and getattr(docker_mgr, 'client', None) is not None
        
        # Match containers to this app
        container_names, states = self._match_containers_to_app(
            model_slug, app_number, all_containers
        )
        
        # Check compose file exists
        compose_exists = self._check_compose_exists(model_slug, app_number)
        
        # Determine overall status
        status = self._determine_status_from_states(states, compose_exists)
        
        # Build container info dicts
        containers = [
            {'name': name, 'status': all_containers.get(name, 'unknown')}
            for name in container_names
        ]
        
        return CacheEntry(
            status=status,
            containers=containers,
            states=states,
            compose_exists=compose_exists,
            docker_connected=docker_connected,
            project_name=self._get_project_name(model_slug, app_number)
        )

    def get_single_status(
        self,
        model_slug: str,
        app_number: int,
        force_refresh: bool = False,
        return_stale_on_error: bool = True
    ) -> CacheEntry:
        """
        Convenience method to get status for a single application.
        
        This is a wrapper around get_status() that provides graceful degradation
        when Docker is unavailable - it will return stale cached data rather than
        failing completely.
        
        Args:
            model_slug: The model identifier
            app_number: The application number
            force_refresh: Force a refresh even if cache is fresh
            return_stale_on_error: If True, return stale cache on Docker errors
            
        Returns:
            CacheEntry with status information
        """
        key = self._cache_key(model_slug, app_number)
        
        # First try normal get_status
        try:
            return self.get_status(model_slug, app_number, force_refresh)
        except Exception as e:
            logger.warning("Error in get_single_status for %s/app%s: %s", model_slug, app_number, e)
            
            # If we have stale cache and return_stale_on_error is True, return it
            if return_stale_on_error:
                with self._lock:
                    entry = self._cache.get(key)
                    if entry is not None:
                        logger.info("Returning stale cache for %s/app%s due to error", model_slug, app_number)
                        # Mark as stale in the entry for client awareness
                        return CacheEntry(
                            status=entry.status,
                            containers=entry.containers,
                            states=entry.states,
                            compose_exists=entry.compose_exists,
                            docker_connected=False,  # Mark as disconnected
                            project_name=entry.project_name,
                            updated_at=entry.updated_at,
                            error=f"Docker unavailable, showing cached status: {e}"
                        )
            
            # No cache available, return error entry
            compose_exists = self._check_compose_exists(model_slug, app_number)
            return CacheEntry(
                status=self.STATUS_ERROR,
                containers=[],
                states=[],
                compose_exists=compose_exists,
                docker_connected=False,
                project_name=self._get_project_name(model_slug, app_number),
                error=str(e)
            )

    def get_bulk_status_dict(
        self, 
        apps: List[Tuple[str, int]], 
        force_refresh: bool = False,
        return_stale_on_error: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get status for multiple applications as a simple dictionary.
        
        This is a convenience method that returns a dict with string keys
        for easier use in templates and API responses.
        
        Args:
            apps: List of (model_slug, app_number) tuples
            force_refresh: Force refresh even if cache entries are fresh
            return_stale_on_error: If True, return stale cache on Docker errors
            
        Returns:
            Dict mapping "model_slug:app_number" to status dict
        """
        results: Dict[str, Dict[str, Any]] = {}
        
        try:
            entries = self.get_bulk_status(apps, force_refresh)
            for (model_slug, app_number), entry in entries.items():
                key = f"{model_slug}:{app_number}"
                results[key] = entry.to_dict()
        except Exception as e:
            logger.error("Error in get_bulk_status_dict: %s", e)
            
            # Return stale entries if available
            if return_stale_on_error:
                with self._lock:
                    for model_slug, app_number in apps:
                        key = f"{model_slug}:{app_number}"
                        cache_key = self._cache_key(model_slug, app_number)
                        entry = self._cache.get(cache_key)
                        if entry is not None:
                            entry_dict = entry.to_dict()
                            entry_dict['stale'] = True
                            entry_dict['error'] = f"Docker unavailable: {e}"
                            results[key] = entry_dict
                        else:
                            # No cache, return minimal error entry
                            results[key] = {
                                'status': self.STATUS_UNKNOWN,
                                'containers': [],
                                'states': [],
                                'docker_connected': False,
                                'is_stale': True,
                                'stale': True,
                                'error': f"Docker unavailable: {e}"
                            }
        
        return results

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache."""
        with self._lock:
            total_entries = len(self._cache)
            stale_entries = sum(
                1 for entry in self._cache.values() 
                if entry.is_stale(self._stale_threshold)
            )
            status_counts = {}
            for entry in self._cache.values():
                status_counts[entry.status] = status_counts.get(entry.status, 0) + 1
            
            return {
                'total_entries': total_entries,
                'fresh_entries': total_entries - stale_entries,
                'stale_entries': stale_entries,
                'stale_threshold_seconds': self._stale_threshold,
                'status_counts': status_counts,
                'batch_cache_fresh': (
                    self._all_statuses_updated_at is not None and
                    (datetime.now(timezone.utc) - self._all_statuses_updated_at) < timedelta(seconds=self._stale_threshold)
                )
            }


# Module-level singleton instance (lazy initialization)
_cache_instance: Optional[DockerStatusCache] = None
_cache_lock = threading.Lock()


def get_docker_status_cache() -> DockerStatusCache:
    """Get the singleton DockerStatusCache instance."""
    global _cache_instance
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = DockerStatusCache()
    return _cache_instance


def reset_docker_status_cache() -> None:
    """Reset the singleton instance (for testing)."""
    global _cache_instance
    with _cache_lock:
        if _cache_instance is not None:
            _cache_instance.invalidate_all()
        _cache_instance = None
