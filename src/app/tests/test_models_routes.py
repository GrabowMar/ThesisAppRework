from __future__ import annotations

import os
import sys
import pytest

# Ensure src on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from flask import Flask  # type: ignore  # noqa: E402
from app.factory import create_app  # type: ignore  # noqa: E402
from app.extensions import db  # type: ignore  # noqa: E402
from app.models import ModelCapability  # type: ignore  # noqa: E402


@pytest.fixture()
def app_ctx():
    os.environ.setdefault('OPENROUTER_CACHE_ENABLED', 'false')
    app = create_app('test')
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        WTF_CSRF_ENABLED=False,
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
        # Seed one model
    mc = ModelCapability()  # type: ignore[call-arg]
    mc.model_id = 'anthropic/claude-3.7-sonnet'
    mc.canonical_slug = 'anthropic_claude-3.7-sonnet'
    mc.provider = 'anthropic'
    mc.model_name = 'claude-3.7-sonnet'
    mc.is_free = False
    mc.supports_function_calling = True
    mc.supports_json_mode = True
    db.session.add(mc)
    db.session.commit()
    yield app
    db.session.remove()


def test_model_more_info_endpoint_renders(app_ctx: Flask):
    client = app_ctx.test_client()
    rv = client.get('/models/model/anthropic_claude-3.7-sonnet/more-info')
    # Should always return 200 with HTML body (best-effort enrichment)
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'OpenRouter' in html
    assert 'Hugging Face' in html


def test_export_models_csv(app_ctx: Flask):
    client = app_ctx.test_client()
    rv = client.get('/models/export/models.csv')
    assert rv.status_code == 200
    assert rv.mimetype == 'text/csv'
    text = rv.get_data(as_text=True)
    # At minimum, headers should be present
    assert 'provider,model_name,slug' in text.splitlines()[0]
