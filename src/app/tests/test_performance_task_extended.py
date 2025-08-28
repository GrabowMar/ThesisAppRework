"""Extended tests for performance_test_task (failure classification + success timing)."""
from __future__ import annotations

import os
import sys
from flask import Flask

SRC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from app.extensions import db  # type: ignore  # noqa: E402
from app.models import GeneratedApplication, PerformanceTest  # type: ignore  # noqa: E402
from app.tasks import performance_test_task  # type: ignore  # noqa: E402
from app.constants import AnalysisStatus  # type: ignore  # noqa: E402


def _make_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_EXPIRE_ON_COMMIT=False,
    )
    db.init_app(app)
    return app


def _seed():
    g = GeneratedApplication(model_slug='pf_ext', app_number=12, app_type='web_app', provider='p')  # type: ignore[arg-type]
    db.session.add(g)
    db.session.commit()
    pt = PerformanceTest(application_id=g.id, test_type='load')  # type: ignore[arg-type]
    db.session.add(pt)
    db.session.commit()
    return g, pt


def _setup_integration():
    class FakeIntegration:
        def get_services_status(self):
            return {'services': {'performance-tester': {'status': 'running'}}}
    import app.tasks as task_mod  # type: ignore
    task_mod.get_analyzer_integration = lambda: FakeIntegration()  # type: ignore


def test_engine_failure_classification_exception():
    app = _make_app()
    with app.app_context():
        db.create_all()
        g, pt = _seed()
        _setup_integration()
        result = getattr(performance_test_task, 'run')(g.model_slug, g.app_number, {  # type: ignore[attr-defined]
            'test_id': pt.id,
            'force_service_status': 'running',
            'force_engine_exception': 'Injected failure'
        })
        assert result['status'] == 'failed'
        assert result.get('failure_classification') in {'unhandled_exception', 'transient_error'}
        refreshed = db.session.get(PerformanceTest, pt.id)
        assert refreshed and refreshed.status == AnalysisStatus.FAILED


def test_engine_failure_classification_transient():
    app = _make_app()
    with app.app_context():
        db.create_all()
        g, pt = _seed()
        _setup_integration()
        result = getattr(performance_test_task, 'run')(g.model_slug, g.app_number, {  # type: ignore[attr-defined]
            'test_id': pt.id,
            'force_service_status': 'running',
            'force_engine_transient': True
        })
        assert result['status'] == 'failed'
        assert result.get('failure_classification') == 'transient_error'
        refreshed = db.session.get(PerformanceTest, pt.id)
        assert refreshed and refreshed.status == AnalysisStatus.FAILED


def test_running_status_and_duration_recorded():
    app = _make_app()
    with app.app_context():
        db.create_all()
        g, pt = _seed()
        _setup_integration()
        result = getattr(performance_test_task, 'run')(g.model_slug, g.app_number, {  # type: ignore[attr-defined]
            'test_id': pt.id,
            'force_service_status': 'running',
            'force_engine_result': {'status': 'completed', 'summary': {'ok': True}}
        })
        assert result['status'] == 'completed'
        refreshed = db.session.get(PerformanceTest, pt.id)
        assert refreshed and refreshed.status == AnalysisStatus.COMPLETED
        if hasattr(refreshed, 'analysis_duration'):
            val = getattr(refreshed, 'analysis_duration')
            assert val is None or val >= 0.0
        else:
            assert refreshed.started_at and refreshed.completed_at and refreshed.completed_at >= refreshed.started_at
