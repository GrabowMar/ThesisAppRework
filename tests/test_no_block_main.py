"""Ensure no new '{% block main %}' usages sneak back into templates.

Allowed: layouts/base.html (for backward compatibility shim only).
Fail if any other template contains '{% block main'.
"""
from __future__ import annotations

from pathlib import Path

ALLOWED = { 'layouts/base.html' }

ROOT = Path(__file__).resolve().parents[1] / 'src' / 'templates'

def find_block_main_usages():
    for path in ROOT.rglob('*.html'):
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            continue
        if '{% block main' in text and rel not in ALLOWED:
            yield rel

def test_no_block_main_outside_allowed():
    offenders = list(find_block_main_usages())
    assert not offenders, f"Found legacy '{{% block main %}}' in: {offenders}. Convert to 'block content'."
