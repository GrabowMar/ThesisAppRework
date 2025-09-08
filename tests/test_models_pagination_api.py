import json

def test_models_paginated_endpoint(client):
    # Basic request default params
    resp = client.get('/api/models/paginated')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'models' in data
    assert 'statistics' in data
    assert 'pagination' in data
    pg = data['pagination']
    for key in ('current_page','per_page','total_items','total_pages','has_prev','has_next'):
        assert key in pg

    # Request openrouter source (may be empty if key missing, but should still 200)
    resp2 = client.get('/api/models/paginated?source=openrouter&per_page=5')
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert 'models' in data2
    assert data2['pagination']['per_page'] == 5

    # Filtering & pagination interplay
    resp3 = client.get('/api/models/paginated?per_page=1&page=1')
    assert resp3.status_code == 200
    d3 = resp3.get_json()
    assert d3['pagination']['per_page'] == 1
    assert d3['pagination']['current_page'] == 1

    # Installed-only (used) filter
    resp4 = client.get('/api/models/paginated?installed_only=1')
    assert resp4.status_code == 200
    data4 = resp4.get_json()
    assert 'models' in data4
    # Should not error even if zero models installed in test DB
