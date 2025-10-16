"""
Test suite for Jinja routes in src/app/routes/jinja/

Tests all template rendering routes to ensure proper HTML output.
"""

import pytest


@pytest.fixture
def app():
    """Create test Flask app"""
    from app.factory import create_app
    app = create_app('testing')
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


class TestMainRoutes:
    """Test main Jinja routes"""
    
    def test_dashboard_route(self, client):
        """Test GET / (main dashboard)"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data
    
    def test_models_overview_route(self, client):
        """Test GET /models route"""
        response = client.get('/models')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data
    
    def test_applications_index_route(self, client):
        """Test GET /applications route"""
        response = client.get('/applications')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data


class TestAnalysisRoutes:
    """Test analysis Jinja routes"""
    
    def test_analysis_index(self, client):
        """Test GET /analysis route"""
        response = client.get('/analysis')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data
    
    def test_analysis_create(self, client):
        """Test GET /analysis/create route"""
        response = client.get('/analysis/create')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data


class TestSampleGeneratorRoutes:
    """Test sample generator Jinja routes"""
    
    def test_sample_generator_index(self, client):
        """Test GET /sample-generator route"""
        response = client.get('/sample-generator')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data


class TestReportsRoutes:
    """Test reports Jinja routes"""
    
    def test_reports_index(self, client):
        """Test GET /reports route"""
        response = client.get('/reports')
        assert response.status_code == 200


class TestDocsRoutes:
    """Test docs Jinja routes"""
    
    def test_docs_index(self, client):
        """Test GET /docs route"""
        response = client.get('/docs')
        assert response.status_code == 200


class TestStatsRoutes:
    """Test statistics Jinja routes"""
    
    def test_statistics_overview(self, client):
        """Test GET /statistics route"""
        response = client.get('/statistics')
        assert response.status_code == 200
