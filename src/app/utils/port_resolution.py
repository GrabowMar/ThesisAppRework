"""Shared port resolution utilities.

Provides a single implementation for resolving application ports with
progressive fallback strategies and detailed attempt tracing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import re

from app.models import PortConfiguration, ModelCapability  # type: ignore


@dataclass
class PortLookupResult:
    backend: Optional[int]
    frontend: Optional[int]
    source: Optional[str]
    attempts: List[str]

    def as_dict(self) -> Dict[str, Any]:  # convenience for templates/json
        return {
            'backend': self.backend,
            'frontend': self.frontend,
            'source': self.source,
            'attempts': self.attempts,
        }


def resolve_ports(model_slug: str, app_number: int, include_attempts: bool = True) -> Optional[Dict[str, Any]]:
    attempts: List[str] = []

    def _rec(label: str):
        if include_attempts:
            attempts.append(label)

    # 1. Exact
    pc = PortConfiguration.query.filter_by(model=model_slug, app_num=app_number).first()
    if pc:
        _rec('match:exact')
        return PortLookupResult(pc.backend_port, pc.frontend_port, 'exact', attempts).as_dict()
    _rec('miss:exact')

    # 2. ModelCapability attributes
    model_cap = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
    if model_cap:
        for attr in ('model_name', 'canonical_slug'):
            val = getattr(model_cap, attr, None)
            if not val:
                continue
            pc = PortConfiguration.query.filter_by(model=val, app_num=app_number).first()
            if pc:
                _rec(f'match:model_attr:{attr}')
                return PortLookupResult(pc.backend_port, pc.frontend_port, f'model_attr:{attr}', attempts).as_dict()
            _rec(f'miss:model_attr:{attr}')

    # 3. Separator normalizations
    norm_candidates = {
        model_slug.replace('-', '_'),
        model_slug.replace('_', '-'),
        model_slug.replace(' ', '_'),
        model_slug.replace(' ', '-')
    }
    for cand in {c for c in norm_candidates if c and c != model_slug}:
        pc = PortConfiguration.query.filter_by(model=cand, app_num=app_number).first()
        if pc:
            _rec(f'match:normalized:{cand}')
            return PortLookupResult(pc.backend_port, pc.frontend_port, f'normalized:{cand}', attempts).as_dict()
        _rec(f'miss:normalized:{cand}')

    # 4. Token-set fuzzy
    def _tokenize(slug: str):
        return [t for t in slug.replace('_','-').split('-') if any(c.isalpha() for c in t)]

    wanted_tokens = set(_tokenize(model_slug))
    if wanted_tokens:
        rows = PortConfiguration.query.filter_by(app_num=app_number).all()
        for cand in rows:
            if set(_tokenize(cand.model)) == wanted_tokens:
                _rec(f'match:fuzzy_tokens:{cand.model}')
                return PortLookupResult(cand.backend_port, cand.frontend_port, f'fuzzy_tokens:{cand.model}', attempts).as_dict()
        _rec('miss:fuzzy_tokens')

    # 5. Alphanumeric normalization across all rows
    def _norm(s: str):
        return re.sub(r'[^0-9a-z]+', '', (s or '').lower())

    target_norm = _norm(model_slug)
    if target_norm:
        rows = PortConfiguration.query.filter_by(app_num=app_number).all()
        for cand in rows:
            if _norm(cand.model) == target_norm:
                _rec(f'match:alnum_norm:{cand.model}')
                return PortLookupResult(cand.backend_port, cand.frontend_port, f'alnum_norm:{cand.model}', attempts).as_dict()
        _rec('miss:alnum_norm')

    _rec('final:unresolved')
    return None
