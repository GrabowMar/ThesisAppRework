"""
Smoke Tests for Core Application Health
=======================================

This module contains smoke tests that verify basic application functionality.

Tests cover:
- Application factory creates valid Flask app instance
- Health check endpoint responds correctly
- Basic API structure and response format validation

These tests run quickly and provide confidence that the core application
is functioning before running more comprehensive tests.
"""

@pytest.mark.smoke
def test_app_exists(app):
    """Check if the app is created successfully."""
    assert app is not None

@pytest.mark.smoke
def test_health_check(client):
    """Check the health endpoint."""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.get_json()
    # API returns wrapped response: {'success': True, 'data': {'status': 'healthy', ...}}
    assert data['success'] is True
    assert data['data']['status'] == 'healthy'
