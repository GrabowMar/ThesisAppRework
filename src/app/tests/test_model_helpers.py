"""Tests for model helper JSON getters/setters and basic to_dict fields."""
from __future__ import annotations

import os
import sys
from flask import Flask

SRC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from app.extensions import db  # type: ignore  # noqa: E402
from app.models import (  # type: ignore  # noqa: E402
    ModelCapability, PortConfiguration, GeneratedApplication, SecurityAnalysis,
)
from app.constants import AnalysisStatus  # type: ignore  # noqa: E402


def _make_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def test_model_capability_json_helpers():
    app = _make_app()
    with app.app_context():
        db.create_all()
        mc = ModelCapability()  # type: ignore[call-arg]
        mc.model_id = 'm1'
        mc.canonical_slug = 'm1'
        mc.provider = 'prov'
        mc.model_name = 'Model 1'
        mc.set_capabilities({'supports': ['json']})
        mc.set_metadata({'tier': 'free'})
        db.session.add(mc)
        db.session.commit()
        loaded = ModelCapability.query.first()
        assert loaded.get_capabilities()['supports'] == ['json']
        assert loaded.get_metadata()['tier'] == 'free'
        d = loaded.to_dict()
        assert d['model_id'] == 'm1'


def test_security_analysis_default_configs():
    app = _make_app()
    with app.app_context():
        db.create_all()
        # Need a GeneratedApplication to satisfy FK
        g = GeneratedApplication(model_slug='smod', app_number=1, app_type='web_app', provider='x')
        db.session.add(g)
        db.session.commit()
        sa = SecurityAnalysis(application_id=g.id)  # type: ignore[arg-type]
        db.session.add(sa)
        db.session.commit()
        # Access default configs (should be dicts with expected keys)
        assert 'tests' in sa.get_bandit_config()
        assert 'severity' in sa.get_bandit_config()
        assert 'severity' in sa.get_safety_config()
        assert 'extends' in sa.get_eslint_config()
        assert 'disable' in sa.get_pylint_config()
        assert 'scan_type' in sa.get_zap_config()


def test_generated_application_ports_resolution_basic():
    app = _make_app()
    with app.app_context():
        db.create_all()
        # Insert a port configuration referencing canonical slug
        pc = PortConfiguration(model='model_slug_a', app_num=2, frontend_port=9002, backend_port=6002)  # type: ignore[arg-type]
        db.session.add(pc)
        app_obj = GeneratedApplication(model_slug='model_slug_a', app_number=2, app_type='web_app', provider='p')
        db.session.add(app_obj)
        db.session.commit()
        ports = app_obj.get_ports()
        assert ports['frontend'] == 9002 and ports['backend'] == 6002


def test_security_analysis_to_dict_and_status_enum_value():
    app = _make_app()
    with app.app_context():
        db.create_all()
        g = GeneratedApplication(model_slug='enum_app', app_number=1, app_type='web_app', provider='p')
        db.session.add(g)
        db.session.commit()
        sa = SecurityAnalysis(application_id=g.id)  # type: ignore[arg-type]
        sa.status = AnalysisStatus.RUNNING
        db.session.add(sa)
        db.session.commit()
        data = sa.to_dict()
        assert data['status'] == AnalysisStatus.RUNNING.value
        assert data['application_id'] == g.id
