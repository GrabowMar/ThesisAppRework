from flask import Flask


def test_batch_overview_page_renders(app: Flask):
    client = app.test_client()
    rv = client.get('/batch/')
    assert rv.status_code == 200, rv.data[:200]
    body = rv.get_data(as_text=True)
    # Key sections / labels expected on page
    assert 'Active Operations' in body
    assert 'Recent History' in body
    assert 'Queue Overview' in body
    assert 'Active Workers' in body