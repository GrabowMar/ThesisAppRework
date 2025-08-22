"""Lightweight Analysis Config Models
=====================================

These dataclasses provide a slimmer, unified representation of analysis
configuration used by the service layer and engines. They intentionally
avoid duplicating the large, legacy configuration surfaces in
`analyzer_config.py` and `analyzer_config_service.py`.

Scope:
 - Booleans / simple fields that map to tool enablement & basic parameters
 - Simple (de-)serialization helpers

The goal is to converge callers (routes / tasks) onto a single shape
when preparing analysis requests. As deeper per-tool configuration is
required we can extend with optional nested structures.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List

__all__ = [
    'SecurityToolsConfig', 'PerformanceTestConfig', 'StaticAnalysisConfig',
    'DynamicScanConfig'
]


@dataclass
class SecurityToolsConfig:
    bandit: bool = True
    safety: bool = True
    pylint: bool = True
    eslint: bool = True
    npm_audit: bool = True
    snyk: bool = False
    zap: bool = False
    semgrep: bool = False
    timeout_minutes: int = 10
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:  # noqa: D401
        return asdict(self)

    @classmethod
    def from_security_analysis_row(cls, row) -> 'SecurityToolsConfig':  # type: ignore[override]
        return cls(
            bandit=getattr(row, 'bandit_enabled', True),
            safety=getattr(row, 'safety_enabled', True),
            pylint=getattr(row, 'pylint_enabled', True),
            eslint=getattr(row, 'eslint_enabled', True),
            npm_audit=getattr(row, 'npm_audit_enabled', True),
            snyk=getattr(row, 'snyk_enabled', False),
            zap=getattr(row, 'zap_enabled', False),
            semgrep=getattr(row, 'semgrep_enabled', False),
            timeout_minutes=getattr(row, 'timeout_minutes', 10) or 10,
            include_patterns=(row.get_include_patterns() if hasattr(row, 'get_include_patterns') else None),
            exclude_patterns=(row.get_exclude_patterns() if hasattr(row, 'get_exclude_patterns') else None),
        )


@dataclass
class PerformanceTestConfig:
    users: int = 10
    duration: int = 60  # seconds
    spawn_rate: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StaticAnalysisConfig:
    tools: Optional[List[str]] = None  # e.g. ['bandit', 'pylint']

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DynamicScanConfig:
    scan_type: str = 'baseline'
    target_url: str = ''
    timeout_minutes: int = 10
    include_paths: Optional[List[str]] = None
    exclude_paths: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
