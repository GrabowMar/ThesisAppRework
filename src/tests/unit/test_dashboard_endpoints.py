
def test_dashboard_stats_fragment(client):
    resp = client.get('/api/dashboard/stats-fragment')
    assert resp.status_code == 200
    # Should contain the stat-card markers from template
    assert b"stat-card" in resp.data


def test_dashboard_docker_status_fragment(client):
    resp = client.get('/api/dashboard/docker-status')
    assert resp.status_code == 200
    # Should render inner docker status fragment
    assert b"Docker Engine" in resp.data or b"empty-state" in resp.data


def test_dashboard_system_health_fragment(client):
    resp = client.get('/api/dashboard/system-health-fragment')
    assert resp.status_code == 200
    # Should render health component structure or empty state
    assert b"Overall Health" in resp.data or b"Health data unavailable" in resp.data


def test_dashboard_recent_activity_htmx(client):
    resp = client.get('/api/recent_activity')
    assert resp.status_code == 200
    # Template used by recent activity timeline
    assert b"activity-item" in resp.data or b"Unable to load activity" in resp.data


def test_dashboard_analyzer_services_fragment(client):
    resp = client.get('/api/dashboard/analyzer-services')
    assert resp.status_code == 200
    # Either services list or empty-state
    assert b"Analyzer Services" in resp.data or b"No Analyzer Services" in resp.data


def test_dashboard_overview_json(client):
    resp = client.get('/api/dashboard/overview')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'totals' in data and 'activity' in data and 'success_rates' in data


def test_api_system_health_json(client):
    resp = client.get('/api/system/health')
    assert resp.status_code == 200
    data = resp.get_json()
    # basic keys should exist
    assert 'docker' in data and 'database' in data
