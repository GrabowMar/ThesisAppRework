"""Smoke test: Quick HTTP endpoint availability checks."""

import pytest
import requests

pytestmark = pytest.mark.smoke


@pytest.fixture
def base_url():
    """Base URL for Flask application."""
    return "http://localhost:5000"


def test_index_page(base_url):
    """Test main index page is accessible."""
    response = requests.get(base_url)
    assert response.status_code == 200


def test_health_endpoint(base_url):
    """Test health check endpoint."""
    response = requests.get(f"{base_url}/health")
    assert response.status_code == 200
    data = response.json()
    assert 'status' in data


def test_api_health(base_url):
    """Test API health endpoint."""
    response = requests.get(f"{base_url}/api/health")
    assert response.status_code == 200


def test_dashboard_accessible(base_url):
    """Test dashboard page is accessible."""
    response = requests.get(f"{base_url}/dashboard")
    assert response.status_code == 200
