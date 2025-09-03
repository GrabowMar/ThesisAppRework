def test_applications_route_basic(client):
    resp = client.get('/applications')
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert 'Applications' in text
    assert 'Generate Application' in text or 'Generate App' in text
