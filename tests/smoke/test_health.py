import pytest

@pytest.mark.smoke
def test_app_exists(app):
    """Check if the app is created successfully."""
    assert app is not None

@pytest.mark.smoke
def test_health_check(client):
    """Check the health endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    # API returns wrapped response: {'success': True, 'data': {'status': 'healthy', ...}}
    assert data['success'] is True
    assert data['data']['status'] == 'healthy'
