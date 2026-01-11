"""
Time Utilities
==============

Utility functions for timezone-aware datetime operations.

This module provides helper functions for working with UTC timestamps,
replacing deprecated datetime methods with modern timezone-aware alternatives.
"""
from __future__ import annotations
from datetime import datetime, timezone

def utc_now() -> datetime:
    """Get current UTC time - replacement for deprecated datetime.utcnow().

    Returns:
        Timezone-aware datetime object representing the current UTC time.
    """
    return datetime.now(timezone.utc)
