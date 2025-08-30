"""
Basic Functionality Tests
========================

Test basic application functionality and structure.
"""


def test_app_creation(app):
    """Test application creation."""
    assert app is not None
    assert app.config['TESTING'] is True


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'healthy'


def test_dashboard_loads(client):
    """Test dashboard page loads."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Dashboard' in response.data


def test_models_page_loads(client):
    """Test models page loads."""
    response = client.get('/models/')
    assert response.status_code == 200


def test_404_error_handling(client):
    """Test 404 error handling."""
    response = client.get('/nonexistent-page')
    assert response.status_code == 404
