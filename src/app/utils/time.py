from __future__ import annotations
from datetime import datetime, timezone

def utc_now() -> datetime:
    """Get current UTC time - replacement for deprecated datetime.utcnow()"""
    return datetime.now(timezone.utc)
