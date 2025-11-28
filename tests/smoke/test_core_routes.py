import pytest

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
