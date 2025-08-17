"""Tests for analysis_service layer.

Covers security & performance creation, listing, retrieval, start logic, state validation,
comprehensive analysis convenience, and results retrieval shape.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, Any

import pytest
from flask import Flask  # type: ignore

SRC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from app.extensions import db  # type: ignore  # noqa: E402
from app.services import analysis_service as svc  # type: ignore  # noqa: E402
from app.models import GeneratedApplication, SecurityAnalysis  # type: ignore  # noqa: E402
from app.constants import AnalysisStatus  # type: ignore  # noqa: E402


@pytest.fixture(scope="session")
def app_instance():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


@pytest.fixture()
def app_ctx(app_instance):
    with app_instance.app_context():
        db.drop_all()
        db.create_all()
        yield app_instance
        db.session.remove()


def _create_generated_app(**overrides):
    data: Dict[str, Any] = {
        'model_slug': 'm1',
        'app_number': overrides.get('app_number', 1),
        'app_type': 'web_app',
        'provider': 'test_provider',
    }
    app_obj = GeneratedApplication(**data)
    db.session.add(app_obj)
    db.session.commit()
    return app_obj


def test_create_security_analysis(app_ctx):
    g = _create_generated_app()
    created = svc.create_security_analysis({'application_id': g.id})
    assert created['application_id'] == g.id
    assert created['analysis_name'] == 'Security Analysis'


def test_missing_security_fields(app_ctx):
    with pytest.raises(svc.ValidationError):
        svc.create_security_analysis({})


def test_create_performance_test(app_ctx):
    g = _create_generated_app(app_number=2)
    created = svc.create_performance_test({'application_id': g.id, 'test_type': 'load'})
    assert created['application_id'] == g.id
    assert created['test_type'] == 'load'


def test_missing_performance_fields(app_ctx):
    with pytest.raises(svc.ValidationError):
        svc.create_performance_test({'application_id': 123})


def test_list_and_get_security(app_ctx):
    g = _create_generated_app(app_number=3)
    a1 = svc.create_security_analysis({'application_id': g.id, 'analysis_name': 'A1'})
    svc.create_security_analysis({'application_id': g.id, 'analysis_name': 'A2'})
    all_for_app = svc.list_security_analyses(application_id=g.id)
    names = {a['analysis_name'] for a in all_for_app}
    assert {'A1', 'A2'}.issubset(names)
    fetched = svc.get_security_analysis(a1['id'])
    assert fetched['analysis_name'] == 'A1'


def test_list_and_get_performance(app_ctx):
    g = _create_generated_app(app_number=4)
    t1 = svc.create_performance_test({'application_id': g.id, 'test_type': 'load'})
    svc.create_performance_test({'application_id': g.id, 'test_type': 'stress'})
    all_for_app = svc.list_performance_tests(application_id=g.id)
    types = {t['test_type'] for t in all_for_app}
    assert {'load', 'stress'}.issubset(types)
    fetched = svc.get_performance_test(t1['id'])
    assert fetched['test_type'] == 'load'


def test_start_security_analysis_state_validation(app_ctx, monkeypatch):
    g = _create_generated_app(app_number=5)
    created = svc.create_security_analysis({'application_id': g.id})

    # Patch celery task dispatch to avoid needing a worker
    class DummyResult:
        id = 'task-123'
    def dummy_delay(aid):  # noqa: ANN001
        return DummyResult()
    # Insert dummy task module target for lazy import path app.tasks.run_security_analysis
    import types, sys as _sys  # noqa: E401
    tasks_mod = types.ModuleType('app.tasks')
    setattr(tasks_mod, 'run_security_analysis', type('X', (), {'delay': staticmethod(dummy_delay)}))
    _sys.modules['app.tasks'] = tasks_mod

    started = svc.start_security_analysis(created['id'])
    assert started['status'] == AnalysisStatus.RUNNING.value
    assert started['task_id'] == 'task-123'

    # Attempt to restart should raise
    with pytest.raises(svc.InvalidStateError):
        svc.start_security_analysis(created['id'])


def test_start_security_analysis_not_found(app_ctx):
    with pytest.raises(svc.NotFoundError):
        svc.start_security_analysis(9999)


def test_start_performance_test_state_validation(app_ctx):
    g = _create_generated_app(app_number=6)
    t = svc.create_performance_test({'application_id': g.id, 'test_type': 'load'})
    started = svc.start_performance_test(t['id'])
    assert started['status'] == AnalysisStatus.RUNNING.value
    with pytest.raises(svc.InvalidStateError):
        svc.start_performance_test(t['id'])


def test_comprehensive_analysis_creation_and_start(app_ctx, monkeypatch):
    g = _create_generated_app(app_number=7)

    # Patch celery again
    class DummyResult:
        id = 'comp-1'
    def dummy_delay(aid):  # noqa: ANN001
        return DummyResult()
    import types, sys as _sys  # noqa: E401
    tasks_mod = types.ModuleType('app.tasks')
    setattr(tasks_mod, 'run_security_analysis', type('X', (), {'delay': staticmethod(dummy_delay)}))
    _sys.modules['app.tasks'] = tasks_mod

    started = svc.start_comprehensive_analysis(g.id)
    assert started['status'] == AnalysisStatus.RUNNING.value


def test_get_analysis_results_shape(app_ctx):
    g = _create_generated_app(app_number=8)
    created = svc.create_security_analysis({'application_id': g.id})
    # Simulate some result values
    sa = db.session.get(SecurityAnalysis, created['id'])
    assert sa is not None
    sa.total_issues = 5
    sa.critical_severity_count = 1
    sa.high_severity_count = 1
    sa.medium_severity_count = 2
    sa.low_severity_count = 1
    sa.tools_run_count = 4
    sa.tools_failed_count = 0
    sa.analysis_duration = 12.5
    sa.set_results({'issues': []})
    db.session.commit()

    results = svc.get_analysis_results(created['id'])
    assert results['summary']['total_issues'] == 5
    assert 'results' in results


def test_recent_activity(app_ctx):
    g = _create_generated_app(app_number=9)
    svc.create_security_analysis({'application_id': g.id, 'analysis_name': 'A'})
    svc.create_performance_test({'application_id': g.id, 'test_type': 'load'})
    recent = svc.get_recent_activity()
    assert 'security' in recent and 'performance' in recent
    assert len(recent['security']) >= 1 and len(recent['performance']) >= 1
