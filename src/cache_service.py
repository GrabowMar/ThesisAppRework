"""
Caching Service for Performance Optimization
==========================================

Provides caching functionality to reduce database queries and improve response times.
"""

import logging
import time
from functools import wraps
from typing import Any, Dict, Optional, Callable
from flask import current_app

logger = logging.getLogger(__name__)


class CacheService:
    """Service for caching frequently accessed data."""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
    
    def get(self, key: str, default=None) -> Any:
        """Get value from cache."""
        if key in self._cache:
            entry = self._cache[key]
            
            # Check if expired
            if entry['expires_at'] > time.time():
                self._cache_stats['hits'] += 1
                return entry['value']
            else:
                # Remove expired entry
                del self._cache[key]
        
        self._cache_stats['misses'] += 1
        return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> None:
        """Set value in cache with optional timeout."""
        if timeout is None:
            timeout = getattr(current_app.config, 'CACHE_DEFAULT_TIMEOUT', 300)
        
        timeout_int = int(timeout) if timeout is not None else 300
        expires_at = time.time() + timeout_int
        
        self._cache[key] = {
            'value': value,
            'expires_at': expires_at,
            'created_at': time.time()
        }
        self._cache_stats['sets'] += 1
        
        # Simple cache size management
        max_entries = getattr(current_app.config, 'CACHE_THRESHOLD', 1000)
        if len(self._cache) > max_entries:
            self._evict_oldest()
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]
            self._cache_stats['deletes'] += 1
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared: {count} entries removed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._cache_stats['hits'] + self._cache_stats['misses']
        hit_rate = (self._cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'entries': len(self._cache),
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'hit_rate': round(hit_rate, 2),
            'sets': self._cache_stats['sets'],
            'deletes': self._cache_stats['deletes']
        }
    
    def _evict_oldest(self) -> None:
        """Remove oldest cache entries when cache is full."""
        if not self._cache:
            return
        
        # Remove the 10% oldest entries
        entries_to_remove = max(1, len(self._cache) // 10)
        
        # Sort by creation time and remove oldest
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1]['created_at']
        )
        
        for key, _ in sorted_entries[:entries_to_remove]:
            del self._cache[key]
        
        logger.debug(f"Evicted {entries_to_remove} cache entries")


# Global cache instance
cache = CacheService()


def cached(timeout: Optional[int] = None, key_func: Optional[Callable] = None):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        
        return wrapper
    return decorator


def cache_model_stats(timeout: int = 300):
    """Cache model statistics."""
    def key_func():
        return "model_stats"
    
    return cached(timeout=timeout, key_func=key_func)


def cache_dashboard_stats(timeout: int = 180):
    """Cache dashboard statistics."""
    def key_func():
        return "dashboard_stats"
    
    return cached(timeout=timeout, key_func=key_func)


def cache_system_health(timeout: int = 60):
    """Cache system health status."""
    def key_func():
        return "system_health"
    
    return cached(timeout=timeout, key_func=key_func)


def invalidate_model_cache():
    """Invalidate all model-related cache entries."""
    keys_to_delete = []
    for key in cache._cache.keys():
        if any(pattern in key for pattern in ['model', 'dashboard', 'stats']):
            keys_to_delete.append(key)
    
    for key in keys_to_delete:
        cache.delete(key)
    
    logger.info(f"Invalidated {len(keys_to_delete)} model-related cache entries")
