"""Lightweight template render smoke tests.

Purpose: ensure key templates compile after refactors (layout + partial changes).
We don't assert on HTML content; just that render_template executes without TemplateNotFound
or syntax errors for a curated representative set of pages.
"""
from __future__ import annotations

import pytest
from flask import current_app
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'src' / 'templates'

def discover_main_templates():
    patterns = [
        '**/pages/**/*main.html',  # all *main.html page wrappers
        'layouts/base.html',
    ]
    seen = set()
    for pat in patterns:
        for p in ROOT.glob(pat):
            rel = p.relative_to(ROOT).as_posix()
            if rel not in seen:
                seen.add(rel)
                yield rel

@pytest.mark.parametrize('tpl', list(discover_main_templates()))
def test_template_renders(tpl, app):
    with current_app.app_context():
        dummy_model = type('M', (), {'display_name': 'Dummy Model', 'model_name': 'dummy-model'})()
        dummy_app_data = type('A', (), {'app_number': 1, 'model_slug': 'dummy-model'})()
        current_app.jinja_env.get_or_select_template(tpl).render({
            'model': dummy_model,
            'app_data': dummy_app_data,
            'tasks': [],
            'reports': [],
            'error_code': 404,
        })
