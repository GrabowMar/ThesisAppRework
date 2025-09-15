def test_applications_table_partial_renders(client):
    resp = client.get('/applications/table', headers={'HX-Request': 'true'})
    assert resp.status_code == 200
    # Should include the wrapping block and the table id
    text = resp.get_data(as_text=True)
    assert 'id="applications-table-section"' in text
    assert 'id="applications-table"' in text


def test_applications_stats_partial_renders(client):
    resp = client.get('/applications/stats', headers={'HX-Request': 'true'})
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    # Expect known IDs from stats numbers partial
    assert 'id="total-applications"' in text
    assert 'id="running-applications"' in text
    assert 'id="analyzed-applications"' in text
    assert 'id="unique-models"' in text
