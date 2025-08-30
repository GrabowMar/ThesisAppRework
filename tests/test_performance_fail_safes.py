"""Unit tests for performance_test_task fail-safe logic.

Covers:
- Service unavailable preflight (performance-tester not running)
- Target application unreachable (HTTP preflight fails)
- Successful path (engine returns completed)

We invoke the Celery task function directly (synchronous execution) and
monkeypatch dependencies (analyzer integration + HTTP probe) to isolate logic.
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
from app.models import GeneratedApplication, PerformanceTest  # type: ignore  # noqa: E402
from app.tasks import performance_test_task  # type: ignore  # noqa: E402
from app.constants import AnalysisStatus  # type: ignore  # noqa: E402

@pytest.fixture()
def app_ctx():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def _seed_app() -> GeneratedApplication:
    data = {
        'model_slug': 'perf_model',
        'app_number': 21,
        'app_type': 'web_app',
        'provider': 'test_provider',
    }
    g = GeneratedApplication(**data)  # type: ignore[arg-type]
    db.session.add(g)
    db.session.commit()
    return g


def _seed_perf(app_id: int) -> PerformanceTest:
    pt = PerformanceTest(application_id=app_id, test_type='load')  # type: ignore[arg-type]
    db.session.add(pt)
    db.session.commit()
    return pt


class DummyRequest:  # mimic minimal Celery request interface for retries
    retries = 0


class DummySelf:
    request = DummyRequest()
    def retry(self, exc, countdown, max_retries):  # noqa: ANN001
        # Instead of scheduling a retry, just raise the original exception to surface in test
        raise exc


def test_service_unavailable_preflight(app_ctx, monkeypatch):
    app = _seed_app()
    perf = _seed_perf(app.id)

    # Monkeypatch analyzer integration to report service not running
    class FakeIntegration:
        def get_services_status(self):  # noqa: D401
            return {'services': {'performance-tester': {'status': 'stopped'}}}
    monkeypatch.setattr('app.tasks.get_analyzer_integration', lambda: FakeIntegration())

    # Force service status via config override as additional guard
    result = performance_test_task.__wrapped__(DummySelf(), 'perf_model', app.app_number, {'test_id': perf.id, 'force_service_status': 'stopped'})  # type: ignore[attr-defined]
    assert result['status'] == 'failed'
    assert result.get('failure_classification') == 'infra_not_running'

    refreshed = db.session.get(PerformanceTest, perf.id)
    assert refreshed is not None
    assert refreshed.status == AnalysisStatus.FAILED
    md = refreshed.get_metadata()
    assert md.get('reason')


def test_target_unreachable_preflight(app_ctx, monkeypatch):
    app = _seed_app()
    perf = _seed_perf(app.id)

    class FakeIntegration:
        def get_services_status(self):
            return {'services': {'performance-tester': {'status': 'running'}}}
    monkeypatch.setattr('app.tasks.get_analyzer_integration', lambda: FakeIntegration())

    # Patch urllib.request.urlopen to raise error simulating unreachable host
    import urllib.request
    def fake_urlopen(req, timeout):  # noqa: ANN001
        raise OSError('Connection refused')
    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    result = performance_test_task.__wrapped__(DummySelf(), 'perf_model', app.app_number, {'test_id': perf.id, 'host': 'http://localhost:65500', 'force_service_status': 'running'})  # ensure service passes to reach preflight
    assert result['status'] == 'failed'
    assert result.get('failure_classification') == 'target_unreachable'

    refreshed = db.session.get(PerformanceTest, perf.id)
    assert refreshed is not None
    assert refreshed.status == AnalysisStatus.FAILED
    md = refreshed.get_metadata()
    assert md.get('reason')


def test_performance_success_path(app_ctx, monkeypatch):
    app = _seed_app()
    perf = _seed_perf(app.id)

    class FakeIntegration:
        def get_services_status(self):
            return {'services': {'performance-tester': {'status': 'running'}}}
    monkeypatch.setattr('app.tasks.get_analyzer_integration', lambda: FakeIntegration())

    # Use injection hook for deterministic result
    result = performance_test_task.__wrapped__(DummySelf(), 'perf_model', app.app_number, {'test_id': perf.id, 'force_engine_result': {'status': 'completed', 'summary': {'requests': 100}, '__marker__': 'stub'}})  # type: ignore[attr-defined]
    assert result['status'] == 'completed'
    # Ensure stub used
    assert result['result'].get('__marker__') == 'stub'
    assert result['result'].get('summary', {}).get('requests') == 100

    refreshed = db.session.get(PerformanceTest, perf.id)
    assert refreshed is not None
    assert refreshed.status == AnalysisStatus.COMPLETED
    md = refreshed.get_metadata()
    assert md.get('engine_status') == 'completed'
