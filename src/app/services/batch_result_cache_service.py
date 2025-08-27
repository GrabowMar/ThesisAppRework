"""Batch result caching service.

Provides a lightweight, pluggable caching layer for batch analysis results so
duplicate batch requests with identical (analysis_type, model, app_number,
options hash) can be short‑circuited. Initially pure in‑memory with best‑effort
optional DB persistence hook (future migration can add a dedicated table).

Design goals:
 - Zero external dependency beyond stdlib & existing app context helpers.
 - Safe to import outside an app context (no immediate DB access).
 - Deterministic cache key hashing using a normalized JSON serialization so
   option dict ordering differences don't create distinct keys.
 - TTL expiration (default 6 hours) with lazy sweeping on access.

Public API:
    get_cached(key_parts) -> dict | None
    store_result(key_parts, result_dict, ttl_seconds=None) -> CachedEntry
    get_or_set(key_parts, producer_fn) -> (result_dict, was_cached)
    mark_job_reference(key_parts, job_id)

Key parts tuple structure:
    (analysis_type: str, model_slug: str, app_number: int, options: dict|None)

Result structure is arbitrary JSON‑serializable dict. We additionally track:
    created_at, expires_at, hits, last_accessed, job_ids referencing the cache.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, Optional, Tuple

# (No direct Flask app context usage needed here; keep import surface minimal.)

CacheKeyParts = Tuple[str, str, int, Optional[Dict[str, Any]]]


def _normalize_options(options: Optional[Dict[str, Any]]) -> str:
    if not options:
        return '{}'
    # sort keys recursively to ensure stability
    return json.dumps(options, sort_keys=True, separators=(',', ':'))


def build_cache_key(parts: CacheKeyParts) -> str:
    analysis_type, model_slug, app_number, options = parts
    base = f"{analysis_type}|{model_slug}|{app_number}|" + _normalize_options(options)
    # hash to keep key size bounded
    digest = hashlib.sha256(base.encode('utf-8')).hexdigest()[:32]
    return digest


@dataclass
class CachedEntry:
    key: str
    data: Dict[str, Any]
    created_at: datetime
    expires_at: datetime
    hits: int = 0
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    job_ids: set[str] = field(default_factory=set)

    def to_metadata(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'hits': self.hits,
            'last_accessed': self.last_accessed.isoformat(),
            'job_ids': list(self.job_ids),
            'size_bytes': len(json.dumps(self.data).encode('utf-8')),
        }

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


class BatchResultCacheService:
    def __init__(self, default_ttl_hours: int = 6, max_entries: int = 500) -> None:
        self.default_ttl = timedelta(hours=default_ttl_hours)
        self.max_entries = max_entries
        self._cache: Dict[str, CachedEntry] = {}

    # ---------------- internal helpers -----------------
    def _evict_if_needed(self) -> None:
        if len(self._cache) <= self.max_entries:
            return
        # Evict oldest by last_accessed
        sorted_entries = sorted(self._cache.values(), key=lambda e: e.last_accessed)
        for entry in sorted_entries[: max(1, len(self._cache) - self.max_entries)]:
            self._cache.pop(entry.key, None)

    def _sweep_expired(self) -> None:
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for k in expired_keys:
            self._cache.pop(k, None)

    # ---------------- public API -----------------------
    def get_cached(self, parts: CacheKeyParts) -> Optional[Dict[str, Any]]:
        key = build_cache_key(parts)
        entry = self._cache.get(key)
        if not entry:
            return None
        if entry.is_expired():
            self._cache.pop(key, None)
            return None
        entry.hits += 1
        entry.last_accessed = datetime.now(timezone.utc)
        return entry.data

    def store_result(self, parts: CacheKeyParts, result: Dict[str, Any], ttl_seconds: Optional[int] = None) -> CachedEntry:
        key = build_cache_key(parts)
        now = datetime.now(timezone.utc)
        ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else self.default_ttl
        entry = CachedEntry(key=key, data=result, created_at=now, expires_at=now + ttl)
        self._cache[key] = entry
        self._evict_if_needed()
        return entry

    def get_or_set(self, parts: CacheKeyParts, producer: Callable[[], Dict[str, Any]]) -> Tuple[Dict[str, Any], bool]:
        cached = self.get_cached(parts)
        if cached is not None:
            return cached, True
        data = producer()
        self.store_result(parts, data)
        return data, False

    def mark_job_reference(self, parts: CacheKeyParts, job_id: str) -> None:
        key = build_cache_key(parts)
        entry = self._cache.get(key)
        if entry:
            entry.job_ids.add(job_id)

    # Introspection / diagnostics
    def stats(self) -> Dict[str, Any]:
        self._sweep_expired()
        total = len(self._cache)
        hits = sum(e.hits for e in self._cache.values())
        return {
            'entries': total,
            'aggregate_hits': hits,
            'max_entries': self.max_entries,
            'default_ttl_hours': self.default_ttl.total_seconds() / 3600,
        }

    def list_entries(self, limit: int = 50) -> list[Dict[str, Any]]:
        self._sweep_expired()
        entries = sorted(self._cache.values(), key=lambda e: e.last_accessed, reverse=True)[:limit]
        return [e.to_metadata() for e in entries]

    def clear(self) -> int:
        n = len(self._cache)
        self._cache.clear()
        return n


# Global singleton
batch_result_cache = BatchResultCacheService()

__all__ = [
    'batch_result_cache',
    'BatchResultCacheService',
    'build_cache_key',
    'CacheKeyParts',
]
