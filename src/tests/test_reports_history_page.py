def test_reports_history_page_renders(client):
    from app.constants import Paths
    # Ensure at least one dummy report file exists
    reports_dir = Paths.REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    dummy = reports_dir / 'dummy_report_0000.txt'
    if not dummy.exists():
        dummy.write_text('placeholder')
    resp = client.get('/reports/')
    assert resp.status_code == 200
    assert b'Analysis Results' in resp.data
