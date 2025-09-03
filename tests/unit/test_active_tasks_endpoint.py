def test_active_tasks_endpoint(app):
    with app.test_client() as c:
        resp = c.get('/analysis/api/active-tasks', headers={'HX-Request': 'true'})
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert 'active-tasks-fragment' in body
        assert 'No active tasks' in body