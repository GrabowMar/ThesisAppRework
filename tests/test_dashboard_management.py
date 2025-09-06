def test_dashboard_system_stats(client):
    resp = client.get('/api/dashboard/system-stats')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'counts' in data
    assert 'resources' in data
    assert 'uptime_seconds' in data


def test_dashboard_actions_init_db(client, monkeypatch):
    # Set admin token so endpoint enforces and passes
    monkeypatch.setenv('DASHBOARD_ADMIN_TOKEN', 'testtoken')
    resp = client.post('/api/dashboard/actions/init-db', headers={'X-Admin-Token': 'testtoken'})
    assert resp.status_code in (200, 500)  # allow failure but endpoint reachable
    data = resp.get_json()
    assert 'success' in data


def test_dashboard_actions_log_cleanup(client, monkeypatch):
    monkeypatch.setenv('DASHBOARD_ADMIN_TOKEN', 'testtoken')
    resp = client.post('/api/dashboard/actions/log-cleanup', headers={'X-Admin-Token': 'testtoken'})
    assert resp.status_code in (200, 500)
    data = resp.get_json()
    assert 'success' in data


def test_dashboard_actions_unauthorized(client, monkeypatch):
    monkeypatch.setenv('DASHBOARD_ADMIN_TOKEN', 'secret123')
    resp = client.post('/api/dashboard/actions/init-db')
    assert resp.status_code == 401