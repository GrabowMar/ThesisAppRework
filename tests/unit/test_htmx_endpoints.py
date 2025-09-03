
def test_analysis_htmx_lists_ok(client):
    r = client.get('/analysis/api/list/combined', headers={'HX-Request': 'true'})
    assert r.status_code in (200, 204, 429)

    r = client.get('/analysis/api/list/security', headers={'HX-Request': 'true'})
    assert r.status_code in (200, 204, 429)

    r = client.get('/analysis/api/list/dynamic', headers={'HX-Request': 'true'})
    assert r.status_code in (200, 204, 429)

    r = client.get('/analysis/api/list/performance', headers={'HX-Request': 'true'})
    assert r.status_code in (200, 204, 429)


def test_analysis_htmx_active_tasks_ok(client):
    r = client.get('/analysis/api/active-tasks', headers={'HX-Request': 'true'})
    assert r.status_code in (200, 204, 429)
