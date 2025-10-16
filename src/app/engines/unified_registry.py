"""Unified Tool Registry
========================

Single authoritative registry combining legacy dynamic ToolRegistry and
container-based ContainerToolRegistry. Provides one API surface so the
rest of the system no longer needs to juggle two registries.

Design Goals:
- Merge tool metadata (name, display_name, description, tags, languages, container)
- Provide availability & alias resolution in one place
- Support iteration by container, by tag, by language
- Provide stable numeric IDs (deterministic ordering) for UI forms
- Preserve existing container metadata (config_schema, version, etc.)
- Allow legacy dynamic tools (if any still instantiated) to surface as
  pseudo-container 'local' so they can be filtered consistently
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Iterable
from .container_tool_registry import get_container_tool_registry
from . import base as legacy_base  # legacy ToolRegistry (may be phased out)
import logging

logger = logging.getLogger(__name__)

@dataclass
class UnifiedTool:
    name: str
    display_name: str
    description: str
    container: str  # e.g. 'static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer', 'local'
    tags: Set[str] = field(default_factory=set)
    supported_languages: Set[str] = field(default_factory=set)
    available: bool = True
    version: Optional[str] = None
    config_schema: Optional[object] = None
    origin: str = "container"  # 'container' or 'legacy'

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "container": self.container,
            "tags": sorted(self.tags),
            "supported_languages": sorted(self.supported_languages),
            "available": self.available,
            "version": self.version,
            "origin": self.origin
        }

class UnifiedToolRegistry:
    def __init__(self) -> None:
        self._loaded = False
        self._tools: Dict[str, UnifiedTool] = {}
        self._aliases: Dict[str, str] = {}
        self._id_order: List[str] = []

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        # Load container tools first (canonical ordering)
        c_registry = get_container_tool_registry()
        container_tools = c_registry.get_all_tools()
        for name, ctool in container_tools.items():
            self._tools[name] = UnifiedTool(
                name=ctool.name,
                display_name=ctool.display_name,
                description=ctool.description,
                container=ctool.container.value,
                tags=set(ctool.tags),
                supported_languages=set(ctool.supported_languages),
                available=ctool.available,
                version=getattr(ctool, 'version', None),
                config_schema=getattr(ctool, 'config_schema', None),
                origin='container'
            )
        # Load legacy dynamic tools (if any) as 'local' container
        legacy = legacy_base.get_tool_registry()
        for name in legacy.get_all_tools_info().keys():
            if name in self._tools:
                continue  # container wins
            try:
                info = legacy.get_all_tools_info()[name]
                self._tools[name] = UnifiedTool(
                    name=name,
                    display_name=info.get('display_name') or name,
                    description=info.get('description') or info.get('name') or name,
                    container='local',
                    tags=set(info.get('tags') or []),
                    supported_languages=set(info.get('supported_languages') or []),
                    available=bool(info.get('available', True)),
                    version=info.get('version'),
                    origin='legacy'
                )
            except Exception as e:
                logger.warning(f"Failed loading legacy tool {name}: {e}")
        # Establish deterministic ID order (sorted by name for stability)
        self._id_order = sorted(self._tools.keys())
        # Aliases
        self._aliases.update({
            'zap-baseline': 'zap', 'zap_baseline': 'zap', 'owasp-zap': 'zap', 'owasp_zap': 'zap',
            'locust-performance': 'locust', 'ab-load-test': 'ab', 'apache-bench': 'ab',
            'requirements-analyzer': 'requirements-scanner', 'ai-requirements': 'requirements-scanner'
        })

    # Public API
    def list_tools(self) -> List[str]:
        self._load()
        return list(self._tools.keys())

    def list_tools_detailed(self) -> List[Dict[str, object]]:
        self._load()
        return [self._tools[n].to_dict() for n in self._id_order]

    def get(self, name_or_alias: str) -> Optional[UnifiedTool]:
        self._load()
        key = (name_or_alias or '').lower().strip()
        canonical = self._aliases.get(key, key)
        return self._tools.get(canonical)

    def resolve(self, names: Iterable[str]) -> List[str]:
        out: List[str] = []
        for n in names:
            ut = self.get(n)
            if ut and ut.name not in out:
                out.append(ut.name)
        return out

    def by_container(self, container: str) -> List[str]:
        self._load()
        return [n for n, t in self._tools.items() if t.container == container]

    def by_tags(self, tags: Set[str]) -> List[str]:
        self._load()
        return [n for n,t in self._tools.items() if t.tags.intersection(tags)]

    def by_language(self, lang: str) -> List[str]:
        self._load()
        return [n for n, t in self._tools.items() if lang.lower() in [lng.lower() for lng in t.supported_languages]]

    def tool_id(self, name: str) -> Optional[int]:
        self._load()
        try:
            return self._id_order.index(name) + 1
        except ValueError:
            return None

    def id_to_name(self, tool_id: int) -> Optional[str]:
        self._load()
        if 1 <= tool_id <= len(self._id_order):
            return self._id_order[tool_id-1]
        return None

    def containers(self) -> Set[str]:
        self._load()
        return {t.container for t in self._tools.values()}

    def info_summary(self) -> Dict[str, object]:
        self._load()
        by_container: Dict[str, List[str]] = {}
        for name, t in self._tools.items():
            by_container.setdefault(t.container, []).append(name)
        return {
            'total_tools': len(self._tools),
            'containers': {k: sorted(v) for k,v in by_container.items()},
            'aliases': self._aliases.copy()
        }

# Global singleton
_unified: Optional[UnifiedToolRegistry] = None

def get_unified_tool_registry() -> UnifiedToolRegistry:
    global _unified
    if _unified is None:
        _unified = UnifiedToolRegistry()
    return _unified
