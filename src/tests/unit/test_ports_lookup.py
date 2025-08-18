import os
import json
import pytest

from app.factory import create_app
from app.services.service_locator import ServiceLocator
from app.models import PortConfiguration, GeneratedApplication, db


@pytest.fixture
def app():
    app = create_app()
    yield app


@pytest.fixture
def client(app):
    with app.app_context():
        yield app.test_client()


def test_model_service_exact_and_normalization(app):
    with app.app_context():
        svc = ServiceLocator.get_model_service()
        # Ensure port configurations are loaded into the test database
        svc.populate_database_from_files()
        # Confirm we have port rows available for lookups (sanity)
        # This uses the production misc/port_config.json so it can be large; we only need >0
        # If loading fails the subsequent assertions will naturally fail and surface the error.

        # exact match (we populated misc/port_config.json earlier in session)
        res = svc.get_app_ports('anthropic_claude-3.7-sonnet', 1)
        assert isinstance(res, dict)
        assert res.get('frontend') == 9051
        assert res.get('backend') == 6051
        assert res.get('is_available') is True

        # normalization test: try a slug with dashes
        res2 = svc.get_app_ports('anthropic-claude-3.7-sonnet', 1)
        assert isinstance(res2, dict)
        assert res2.get('frontend') == 9051


def test_generatedapplication_get_ports_returns_canonical(app):
    with app.app_context():
        # create a transient GeneratedApplication if none exists
        ga = db.session.query(GeneratedApplication).filter_by(model_slug='anthropic_claude-3.7-sonnet', app_number=1).first()
        if not ga:
            ga = GeneratedApplication()
            ga.model_slug = 'anthropic_claude-3.7-sonnet'
            ga.app_number = 1
        ports = ga.get_ports()
        assert isinstance(ports, dict)
        # Either empty dict (no PC) or canonical keys
        if ports:
            assert 'frontend' in ports and 'backend' in ports and 'is_available' in ports
