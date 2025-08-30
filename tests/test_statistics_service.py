"""Tests for statistics_service layer.

Validates aggregation outputs for applications, models, analyses, recent activity,
model distribution, generation trends, summary, and export.
"""
from __future__ import annotations

import os
import sys

import pytest
from flask import Flask  # type: ignore

SRC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from app.extensions import db  # type: ignore  # noqa: E402
from app.services import statistics_service as stats  # type: ignore  # noqa: E402
from app.models import GeneratedApplication, ModelCapability, SecurityAnalysis, PerformanceTest  # type: ignore  # noqa: E402
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


def _seed_basic():
    # Applications
    apps = []
    for i in range(3):
        a = GeneratedApplication(model_slug=f"model_{i%2}", app_number=i+1, app_type='web_app', provider='prov', generation_status=AnalysisStatus.PENDING)
        db.session.add(a)
        apps.append(a)
    db.session.commit()
    return apps


def _seed_models():
    # Provide required fields based on current ModelCapability definition
    mc = ModelCapability()  # type: ignore[call-arg]
    mc.model_id = 'model_1'
    mc.canonical_slug = 'model_1'
    mc.provider = 'prov'
    mc.model_name = 'Model 1'
    mc.is_free = True
    mc.supports_function_calling = True
    mc.supports_vision = False
    mc.supports_streaming = False
    mc.supports_json_mode = True
    db.session.add(mc)
    db.session.commit()
    return mc


def _seed_analyses(app):  # noqa: ANN001
    sa = SecurityAnalysis()  # type: ignore[call-arg]
    sa.application_id = app.id
    sa.status = AnalysisStatus.COMPLETED
    pa = PerformanceTest()  # type: ignore[call-arg]
    pa.application_id = app.id
    pa.status = AnalysisStatus.COMPLETED
    db.session.add_all([sa, pa])
    db.session.commit()


def test_application_statistics(app_ctx):
    _seed_basic()
    data = stats.get_application_statistics()
    assert 'total' in data and data['total'] == 3
    assert 'by_status' in data
    assert 'by_type' in data


def test_model_statistics(app_ctx):
    _seed_models()
    data = stats.get_model_statistics()
    assert data['total'] == 1
    assert any(p['provider'] == 'prov' for p in data['by_provider'])


def test_analysis_statistics(app_ctx):
    apps = _seed_basic()
    _seed_analyses(apps[0])
    data = stats.get_analysis_statistics()
    assert data['security']['total'] == 1
    assert data['performance']['total'] == 1


def test_recent_statistics(app_ctx):
    apps = _seed_basic()
    _seed_analyses(apps[0])
    data = stats.get_recent_statistics()
    assert 'last_24h' in data
    assert 'popular_models' in data


def test_model_distribution(app_ctx):
    _seed_models()
    data = stats.get_model_distribution()
    assert 'providers' in data and 'capabilities' in data


def test_generation_trends(app_ctx):
    _seed_basic()
    data = stats.get_generation_trends(days=2)
    assert 'daily_trends' in data
    assert len(data['daily_trends']) == 3  # inclusive of start & end


def test_analysis_summary(app_ctx):
    apps = _seed_basic()
    _seed_analyses(apps[0])
    data = stats.get_analysis_summary()
    assert data['total_analyses'] == 2


def test_export_statistics(app_ctx):
    apps = _seed_basic()
    _seed_analyses(apps[0])
    _seed_models()
    data = stats.export_statistics(days=1)
    assert 'export_info' in data and 'models' in data and 'applications' in data and 'analyses' in data
