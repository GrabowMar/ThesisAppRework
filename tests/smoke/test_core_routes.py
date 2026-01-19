"""
Smoke Tests for Core Application Routes
=======================================

This module contains smoke tests that verify basic routing and page access.

Tests cover:
- Dashboard/root route accessibility and authentication redirects
- Login page direct access and content validation
- Basic route structure and response codes

These tests ensure that the fundamental web routes are working correctly
and provide a foundation for more detailed UI testing.
"""

@pytest.mark.smoke
def test_dashboard_access(client):
    """Check the dashboard endpoint (root)."""
    # Should redirect to login if not authenticated
    response = client.get('/', follow_redirects=True)
    assert response.status_code == 200
    # Verify we landed on login page
    assert b'Login' in response.data or b'Sign In' in response.data

@pytest.mark.smoke
def test_login_page(client):
    """Check the login page loads directly."""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Login' in response.data
