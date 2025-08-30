from flask import Flask

def test_active_batches_partial(app: Flask):
    client = app.test_client()
    rv = client.get('/batch/partials/active')
    assert rv.status_code == 200
    assert b'batch-item' in rv.data or b'No Active Batch' in rv.data

def test_recent_batches_partial(app: Flask):
    client = app.test_client()
    rv = client.get('/batch/partials/recent')
    assert rv.status_code == 200
    assert b'No batch operations history' in rv.data or b'<table' in rv.data

def test_queue_overview_partial(app: Flask):
    client = app.test_client()
    rv = client.get('/batch/partials/queue')
    assert rv.status_code == 200
    assert b'Queue empty' in rv.data or b'list-group' in rv.data

def test_stats_summary_partial(app: Flask):
    client = app.test_client()
    rv = client.get('/batch/partials/stats')
    assert rv.status_code == 200
    assert b'Total' in rv.data or b'Workers' in rv.data

def test_dispatch_next_endpoint_no_jobs(app: Flask):
    client = app.test_client()
    rv = client.post('/batch/api/batch/dispatch-next')
    assert rv.status_code in (200,204)

def test_export_jobs_endpoint(app: Flask):
    client = app.test_client()
    rv = client.get('/batch/api/batch/export?format=csv')
    assert rv.status_code == 200
    assert rv.headers['Content-Type'].startswith('text/csv')
    header = rv.get_data(as_text=True).split('\n')[0]
    assert ('job_id' in header) or ('id' in header)