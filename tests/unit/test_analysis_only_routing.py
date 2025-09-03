from app.factory import create_app


def get_client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_analysis_main_page_ok():
    client = get_client()
    # Analysis hub should be available
    resp = client.get('/analysis/')
    assert resp.status_code == 200


def test_testing_blueprint_removed():
    client = get_client()
    # Legacy testing blueprint endpoints should be gone
    resp = client.get('/testing/')
    assert resp.status_code in (301, 302, 404)


def test_legacy_test_platform_redirects():
    client = get_client()
    resp = client.get('/test-platform', follow_redirects=False)
    assert resp.status_code in (301, 302)
    # Redirect target should be the analysis hub
    location = resp.headers.get('Location', '')
    assert '/analysis' in location


def test_websocket_fallback_path():
    client = get_client()
    resp = client.get('/ws/analysis')
    # Fallback indicates upgrade required
    assert resp.status_code == 426


def test_api_testing_namespace_absent():
    client = get_client()
    resp = client.get('/api/testing/dashboard/stats')
    assert resp.status_code in (404, 405)
