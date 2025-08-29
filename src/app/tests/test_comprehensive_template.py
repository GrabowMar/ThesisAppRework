"""Test to ensure comprehensive_start_result.html template renders correctly.

Covers a regression where TemplateNotFound intermittently occurred.
We force the comprehensive create route to render the template (bypassing
TESTING short-circuit) by setting COMPREHENSIVE_TEST_FORCE_RENDER.
"""
from __future__ import annotations

import os
import sys

import pytest
from flask import Flask

SRC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from app.extensions import db  # type: ignore  # noqa: E402
from app.models import GeneratedApplication  # type: ignore  # noqa: E402

@pytest.fixture()
def app_ctx():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        COMPREHENSIVE_TEST_FORCE_RENDER=True,  # force route to attempt real template render
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY='test'
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def _create_generated_app():
    g = GeneratedApplication(model_slug='tmpl_model', app_number=11, app_type='web_app', provider='test')
    db.session.add(g)
    db.session.commit()
    return g


def test_comprehensive_template_renders(app_ctx, monkeypatch):
    app = app_ctx

    # Monkeypatch needed analysis_service functions to avoid real Celery/task logic
    fake_ids = {'sec': 1, 'perf': 2, 'dyn': 3}
    import app.services.analysis_service as svc  # type: ignore

    def fake_create_security(application_id):  # noqa: ANN001
        return {'id': fake_ids['sec'], 'application_id': application_id}
    def fake_start_security(aid):  # noqa: ANN001
        return {'task_id': 'sec-task'}
    def fake_create_perf(data):  # noqa: ANN001
        return {'id': fake_ids['perf'], 'application_id': data['application_id']}
    def fake_start_perf(pid):  # noqa: ANN001
        return {'task_id': 'perf-task'}
    def fake_create_dyn(data):  # noqa: ANN001
        return {'id': fake_ids['dyn'], 'application_id': data['application_id']}
    def fake_start_dyn(did):  # noqa: ANN001
        return {'task_id': 'dyn-task'}

    monkeypatch.setattr(svc, 'create_comprehensive_security_analysis', fake_create_security)
    monkeypatch.setattr(svc, 'start_security_analysis', fake_start_security)
    monkeypatch.setattr(svc, 'create_performance_test', fake_create_perf)
    monkeypatch.setattr(svc, 'start_performance_test', fake_start_perf)
    monkeypatch.setattr(svc, 'create_dynamic_analysis', fake_create_dyn)
    monkeypatch.setattr(svc, 'start_dynamic_analysis', fake_start_dyn)

    # Register blueprint under same prefix as production route uses
    from app.routes.jinja.analysis import new_analysis_api  # type: ignore
    app.register_blueprint(new_analysis_api)

    g = _create_generated_app()

    client = app.test_client()
    resp = client.post('/analysis/create', json={
        'analysis_type': 'comprehensive',
        'model_slug': g.model_slug,
        'app_number': g.app_number
    })

    assert resp.status_code == 200
    json_response = resp.get_json()
    
    # New behavior: Should return JSON with redirect URL and analysis IDs
    assert json_response['success'] is True
    assert 'redirect_url' in json_response
    assert json_response['redirect_url'] == f"/analysis/results/{g.model_slug}/{g.app_number}"
    assert json_response['security_id'] == fake_ids['sec']
    assert json_response['performance_id'] == fake_ids['perf']
    assert json_response['dynamic_id'] == fake_ids['dyn']
    assert json_response['show_modal'] is True
    assert 'Comprehensive analysis started successfully!' in json_response['message']

