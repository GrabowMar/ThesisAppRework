"""
Unit tests for DockerStatusCache service.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        """Test basic CacheEntry creation."""
        from app.services.docker_status_cache import CacheEntry
        
        entry = CacheEntry(
            status='running',
            containers=[{'name': 'test-backend', 'status': 'running'}],
            states=['running'],
            compose_exists=True,
            docker_connected=True,
            project_name='test-app1'
        )
        
        assert entry.status == 'running'
        assert len(entry.containers) == 1
        assert entry.compose_exists is True
        assert entry.docker_connected is True

    def test_cache_entry_is_stale(self):
        """Test staleness detection."""
        from app.services.docker_status_cache import CacheEntry
        
        # Fresh entry
        entry = CacheEntry(
            status='running',
            updated_at=datetime.now(timezone.utc)
        )
        assert entry.is_stale(max_age_seconds=30) is False
        
        # Stale entry
        old_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        entry = CacheEntry(
            status='running',
            updated_at=old_time
        )
        assert entry.is_stale(max_age_seconds=30) is True

    def test_cache_entry_to_dict(self):
        """Test CacheEntry serialization."""
        from app.services.docker_status_cache import CacheEntry
        
        entry = CacheEntry(
            status='stopped',
            containers=[],
            states=[],
            compose_exists=True,
            docker_connected=True,
            project_name='test-project'
        )
        
        result = entry.to_dict()
        
        assert result['status'] == 'stopped'
        assert result['compose_exists'] is True
        assert result['docker_connected'] is True
        assert result['project_name'] == 'test-project'
        assert 'updated_at' in result
        assert 'is_stale' in result


class TestDockerStatusCache:
    """Tests for DockerStatusCache service."""

    def test_cache_initialization(self):
        """Test cache initializes with correct defaults."""
        from app.services.docker_status_cache import DockerStatusCache
        
        cache = DockerStatusCache()
        
        assert cache._stale_threshold == 30
        assert len(cache._cache) == 0
        
        stats = cache.get_cache_stats()
        assert stats['total_entries'] == 0
        assert stats['stale_threshold_seconds'] == 30

    def test_cache_initialization_custom_threshold(self):
        """Test cache with custom stale threshold."""
        from app.services.docker_status_cache import DockerStatusCache
        
        cache = DockerStatusCache(stale_threshold=60)
        
        assert cache._stale_threshold == 60

    def test_get_project_name(self):
        """Test project name generation."""
        from app.services.docker_status_cache import DockerStatusCache
        
        cache = DockerStatusCache()
        
        # Test underscore conversion
        assert cache._get_project_name('anthropic_claude-3', 1) == 'anthropic-claude-3-app1'
        assert cache._get_project_name('openai_gpt-4', 5) == 'openai-gpt-4-app5'
        
        # Test dot conversion
        assert cache._get_project_name('model.v1', 1) == 'model-v1-app1'

    def test_generate_project_name_variants(self):
        """Test variant generation for container matching."""
        from app.services.docker_status_cache import DockerStatusCache
        
        cache = DockerStatusCache()
        
        variants = cache._generate_project_name_variants('anthropic_claude-3', 1)
        
        # Should include multiple variants
        assert 'anthropic-claude-3-app1' in variants
        assert 'anthropic_claude-3-app1' in variants
        # Should include variant without provider prefix
        assert 'claude-3-app1' in variants

    def test_determine_status_from_states(self):
        """Test status determination logic."""
        from app.services.docker_status_cache import DockerStatusCache
        
        cache = DockerStatusCache()
        
        # Running container
        assert cache._determine_status_from_states(['running'], True) == 'running'
        
        # Mixed states - running wins
        assert cache._determine_status_from_states(['running', 'exited'], True) == 'running'
        
        # Stopped states
        assert cache._determine_status_from_states(['exited'], True) == 'stopped'
        assert cache._determine_status_from_states(['dead'], True) == 'stopped'
        
        # No containers, compose exists
        assert cache._determine_status_from_states([], True) == 'not_created'
        
        # No containers, no compose
        assert cache._determine_status_from_states([], False) == 'no_compose'

    def test_match_containers_to_app(self):
        """Test container matching logic."""
        from app.services.docker_status_cache import DockerStatusCache
        
        cache = DockerStatusCache()
        
        all_containers = {
            'anthropic-claude-3-app1-backend-1': 'running',
            'anthropic-claude-3-app1-frontend-1': 'running',
            'openai-gpt-4-app2-backend-1': 'stopped',
            'unrelated-container': 'running'
        }
        
        names, states = cache._match_containers_to_app('anthropic_claude-3', 1, all_containers)
        
        # Should match the anthropic containers
        assert len(names) == 2
        assert 'anthropic-claude-3-app1-backend-1' in names
        assert 'anthropic-claude-3-app1-frontend-1' in names
        assert states == ['running', 'running']

    def test_invalidate_entry(self):
        """Test cache invalidation."""
        from app.services.docker_status_cache import DockerStatusCache, CacheEntry
        
        cache = DockerStatusCache()
        
        # Add entry manually
        cache._cache[('test-model', 1)] = CacheEntry(status='running')
        
        assert len(cache._cache) == 1
        
        # Invalidate
        cache.invalidate('test-model', 1)
        
        assert len(cache._cache) == 0

    def test_invalidate_all(self):
        """Test bulk cache invalidation."""
        from app.services.docker_status_cache import DockerStatusCache, CacheEntry
        
        cache = DockerStatusCache()
        
        # Add multiple entries
        cache._cache[('model1', 1)] = CacheEntry(status='running')
        cache._cache[('model2', 1)] = CacheEntry(status='stopped')
        cache._cache[('model3', 2)] = CacheEntry(status='not_created')
        
        assert len(cache._cache) == 3
        
        # Invalidate all
        cache.invalidate_all()
        
        assert len(cache._cache) == 0

    def test_get_cache_stats(self):
        """Test cache statistics."""
        from app.services.docker_status_cache import DockerStatusCache, CacheEntry
        
        cache = DockerStatusCache(stale_threshold=30)
        
        # Add fresh entry
        cache._cache[('model1', 1)] = CacheEntry(
            status='running',
            updated_at=datetime.now(timezone.utc)
        )
        
        # Add stale entry
        cache._cache[('model2', 1)] = CacheEntry(
            status='stopped',
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=60)
        )
        
        stats = cache.get_cache_stats()
        
        assert stats['total_entries'] == 2
        assert stats['fresh_entries'] == 1
        assert stats['stale_entries'] == 1
        assert stats['status_counts'] == {'running': 1, 'stopped': 1}


class TestGetDockerStatusCache:
    """Tests for singleton functions."""

    def test_get_singleton(self):
        """Test singleton access."""
        from app.services.docker_status_cache import (
            get_docker_status_cache, 
            reset_docker_status_cache
        )
        
        # Reset first
        reset_docker_status_cache()
        
        cache1 = get_docker_status_cache()
        cache2 = get_docker_status_cache()
        
        # Should be same instance
        assert cache1 is cache2
        
        # Clean up
        reset_docker_status_cache()

    def test_reset_singleton(self):
        """Test singleton reset."""
        from app.services.docker_status_cache import (
            get_docker_status_cache, 
            reset_docker_status_cache,
            CacheEntry
        )
        
        # Get cache and add data
        cache = get_docker_status_cache()
        cache._cache[('test', 1)] = CacheEntry(status='running')
        
        # Reset
        reset_docker_status_cache()
        
        # Get new cache - should be empty
        new_cache = get_docker_status_cache()
        assert len(new_cache._cache) == 0
        
        # Clean up
        reset_docker_status_cache()
