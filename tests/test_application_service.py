"""Tests for application_service layer.

Covers CRUD, container operations, and model-wide operations.
"""
from __future__ import annotations

import pytest

import os
import sys

# Ensure src directory on path
SRC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from flask import Flask  # type: ignore  # noqa: E402
from app.extensions import db  # type: ignore  # noqa: E402
from app.services import application_service as svc  # type: ignore  # noqa: E402
from app.models import GeneratedApplication  # type: ignore  # noqa: E402


@pytest.fixture(scope='session')
def app_instance():
    """Create a minimal Flask app (no blueprints) for pure service tests."""
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
    """Provide a fresh database for each test within a single app instance."""
    with app_instance.app_context():
        db.drop_all()
        db.create_all()
        yield app_instance
        db.session.remove()


def _create_sample(model_slug="test_model", app_number=1, **extra):
    data = {
        'model_slug': model_slug,
        'app_number': app_number,
        'app_type': 'web_app',
        'provider': 'test_provider',
        **extra
    }
    return svc.create_application(data)


def test_create_and_get_application(app_ctx):
    created = _create_sample()
    assert created['model_slug'] == 'test_model'
    # Ensure we can resolve ID via query if not included in dict
    obj = GeneratedApplication.query.filter_by(model_slug='test_model', app_number=1).first()
    assert obj is not None
    fetched = obj.to_dict()
    assert fetched['model_slug'] == 'test_model'


def test_update_application(app_ctx):
    _create_sample()
    obj = GeneratedApplication.query.filter_by(model_slug='test_model', app_number=1).first()
    assert obj is not None
    updated = svc.update_application(obj.id, {'generation_status': 'completed'})
    assert updated['generation_status'] == 'completed'


def test_delete_application(app_ctx):
    _create_sample(app_number=2)
    obj = GeneratedApplication.query.filter_by(model_slug='test_model', app_number=2).first()
    assert obj is not None
    svc.delete_application(obj.id)
    with pytest.raises(svc.NotFoundError):
        svc.get_application(obj.id)


def test_start_stop_restart(app_ctx):
    _create_sample(app_number=3)
    obj = GeneratedApplication.query.filter_by(model_slug='test_model', app_number=3).first()
    assert obj is not None
    started = svc.start_application(obj.id)
    assert started['status'] == 'running'
    stopped = svc.stop_application(obj.id)
    assert stopped['status'] == 'stopped'
    restarted = svc.restart_application(obj.id)
    assert restarted['status'] == 'running'


def test_model_wide_operations(app_ctx):
    _create_sample(app_number=10)
    _create_sample(app_number=11)
    result_start = svc.start_model_containers('test_model')
    assert result_start['started'] == 2
    result_stop = svc.stop_model_containers('test_model')
    assert result_stop['stopped'] == 2


def test_validation_missing_fields(app_ctx):
    with pytest.raises(svc.ValidationError):
        svc.create_application({'model_slug': 'x'})
