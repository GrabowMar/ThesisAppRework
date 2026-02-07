"""Redis key isolation utilities for parallel test execution.

This module provides utilities to namespace Redis keys and select isolated
Redis databases for concurrent test execution, preventing conflicts between
parallel test sessions.
"""

import os


def get_redis_key_prefix() -> str:
    """Get Redis key prefix for current isolation context.

    Returns:
        str: 'test:{isolation_id}:' in isolated mode,
             '' in production mode (no prefix)

    Example:
        >>> os.environ['ANALYSIS_ISOLATION_ID'] = 'abc123'
        >>> get_redis_key_prefix()
        'test:abc123:'
    """
    isolation_id = os.environ.get('ANALYSIS_ISOLATION_ID', '')
    if isolation_id:
        return f'test:{isolation_id}:'
    return ''


def prefix_key(key: str) -> str:
    """Add isolation prefix to Redis key if in isolated mode.

    Args:
        key: Base Redis key

    Returns:
        str: Prefixed key in isolated mode, original key in production

    Example:
        >>> os.environ['ANALYSIS_ISOLATION_ID'] = 'abc123'
        >>> prefix_key('analysis:task:123')
        'test:abc123:analysis:task:123'
    """
    prefix = get_redis_key_prefix()
    return f'{prefix}{key}'


def get_redis_db_number() -> int:
    """Get Redis database number for isolation.

    Redis supports 16 databases (0-15). This function maps isolation IDs
    to databases 1-9, leaving DB 0 for production and 10-15 for manual use.

    Returns:
        int: DB 1-9 for isolated tests (based on isolation ID hash),
             DB 0 for production

    Example:
        >>> os.environ['ANALYSIS_ISOLATION_ID'] = 'test1'
        >>> db_num = get_redis_db_number()
        >>> assert 1 <= db_num <= 9
    """
    isolation_id = os.environ.get('ANALYSIS_ISOLATION_ID', '')
    if isolation_id:
        # Hash to DB 1-9 (avoid 0 for production)
        hash_val = sum(ord(c) for c in isolation_id)
        return (hash_val % 9) + 1
    return 0


def get_isolation_aware_redis_url(base_url: str) -> str:
    """Get Redis URL with isolation-aware database number.

    Args:
        base_url: Base Redis URL (e.g., 'redis://localhost:6379/0')

    Returns:
        str: URL with database number adjusted for isolation context

    Example:
        >>> os.environ['ANALYSIS_ISOLATION_ID'] = 'test1'
        >>> get_isolation_aware_redis_url('redis://localhost:6379/0')
        'redis://localhost:6379/3'  # (example - actual DB depends on hash)
    """
    db_num = get_redis_db_number()
    # Replace the database number in the URL
    if '/' in base_url:
        url_base = base_url.rsplit('/', 1)[0]
        return f'{url_base}/{db_num}'
    return f'{base_url}/{db_num}'
