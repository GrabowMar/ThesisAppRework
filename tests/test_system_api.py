def test_analysis_count_endpoint(client):
    resp = client.get('/api/analysis/count')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert 'counts' in data and 'total' in data['counts']


def test_system_db_health_endpoint(client):
    resp = client.get('/api/system/db-health')
    # Can be 200 (healthy) or 500 (unhealthy); assert JSON shape
    assert resp.status_code in (200, 500)
    data = resp.get_json()
    assert 'success' in data and 'status' in data
