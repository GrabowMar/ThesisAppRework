"""Tests for security_analysis_task and static_analysis_task core behaviors.

Focus areas:
 - Success path with default tools
 - Explicit tools list honored
 - analysis_id persistence of status, results_json, duration (security)
 - Failure path classification (non-transient exception -> FAILED without retry)
 - Skip path already covered in test_disabled_models; only smoke here to ensure status shape
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from flask import Flask

SRC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from app.extensions import db  # type: ignore  # noqa: E402
from app.tasks import security_analysis_task, static_analysis_task  # type: ignore  # noqa: E402
from app.models import GeneratedApplication, SecurityAnalysis  # type: ignore  # noqa: E402
from app.constants import AnalysisStatus  # type: ignore  # noqa: E402


class DummyRequest:
    retries = 0


class DummySelf:
    request = DummyRequest()
    def retry(self, exc, countdown, max_retries):  # noqa: ANN001
        raise exc


def _make_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def _seed_app():
    g = GeneratedApplication(model_slug='sec_static_model', app_number=5, app_type='web_app', provider='p')  # type: ignore[arg-type]
    db.session.add(g)
    db.session.commit()
    return g


def _seed_security_analysis(app_obj: GeneratedApplication) -> SecurityAnalysis:
    sa = SecurityAnalysis(application_id=app_obj.id, analysis_name='baseline')  # type: ignore[arg-type]
    # Explicit tool flags (others remain default True in model, we can force determinism)
    sa.bandit_enabled = True
    sa.safety_enabled = True
    sa.pylint_enabled = True
    sa.eslint_enabled = False
    sa.npm_audit_enabled = False
    sa.semgrep_enabled = False
    db.session.add(sa)
    db.session.commit()
    return sa


def test_security_analysis_success_persists_results():
    app = _make_app()
    with app.app_context():
        db.create_all()
        g = _seed_app()
        sa = _seed_security_analysis(g)
        sa_id = sa.id
        db.session.expire_on_commit = False  # type: ignore[attr-defined]
        import app.extensions as ext_mod  # type: ignore
        @contextmanager
        def _fake_get_session():
            # Return existing session bound to current in-memory DB/app context
            yield db.session
        ext_mod.get_session = _fake_get_session  # type: ignore
        # Inject deterministic engine result via options and invoke inside context
        force_result = {'status': 'completed', 'summary': {'total_issues': 4, 'critical': 1, 'high': 1, 'medium': 1, 'low': 1}}
        result = security_analysis_task.run(g.model_slug, g.app_number, tools=None, options={'analysis_id': sa_id, 'force_engine_result': force_result})  # type: ignore[attr-defined]
        assert result['status'] in ('completed', 'success')
        refreshed = db.session.get(SecurityAnalysis, sa_id)
        assert refreshed is not None
        assert refreshed.status == AnalysisStatus.COMPLETED
        assert refreshed.total_issues == 4
        assert refreshed.critical_severity_count == 1
        assert refreshed.high_severity_count == 1
        assert refreshed.medium_severity_count == 1
        assert refreshed.low_severity_count == 1
        assert refreshed.tools_run_count == 3


def test_security_analysis_failure_marks_failed_without_retry():
    app = _make_app()
    with app.app_context():
        db.create_all()
        g = _seed_app()
        sa = _seed_security_analysis(g)
        sa_id = sa.id
        db.session.expire_on_commit = False  # type: ignore[attr-defined]
        import app.extensions as ext_mod  # type: ignore
        @contextmanager
        def _fake_get_session_fail():
            yield db.session
        ext_mod.get_session = _fake_get_session_fail  # type: ignore
        # Force exception via options flag; run inside context so session scope is valid
        try:
            security_analysis_task.run(g.model_slug, g.app_number, tools=None, options={'analysis_id': sa_id, 'force_engine_exception': 'explosive failure'})  # type: ignore[attr-defined]
        except RuntimeError:
            # Expected path (task re-raises non-transient)
            pass
        refreshed = db.session.get(SecurityAnalysis, sa_id)
        assert refreshed is not None
        assert refreshed.status == AnalysisStatus.FAILED
        assert refreshed.completed_at is not None


def test_static_analysis_success_default_tools():
    app = _make_app()
    with app.app_context():
        db.create_all()
        g = _seed_app()
        model_slug = str(g.model_slug)
        app_number = int(g.app_number)
    # Run outside context using primitive values (task is DB-independent)
    result = static_analysis_task.run(model_slug, app_number, tools=None, options={'force_engine_result': {'status': 'completed', 'summary': {}}})  # type: ignore[attr-defined]
    assert result['status'] in ('completed', 'success')
    assert set(result['tools']) == {'pylint', 'flake8'}


def test_static_analysis_custom_tools_passed():
    app = _make_app()
    with app.app_context():
        db.create_all()
        g = _seed_app()
        model_slug = str(g.model_slug)
        app_number = int(g.app_number)
    custom = ['pylint', 'mypy']
    force_res = {'status': 'completed'}
    result = static_analysis_task.run(model_slug, app_number, tools=custom, options={'force_engine_result': force_res})  # type: ignore[attr-defined]
    assert result['status'] in ('completed', 'success')
    assert result['tools'] == custom
