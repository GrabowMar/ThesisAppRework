
def test_batch_export_creates_files(client):
    # Trigger batch jobs export (CSV + PDF + XLSX) and single job JSON export to ensure persistence
    # Ensure reports directory starts clean (allowed if already present)
    from app.constants import Paths
    reports_dir = Paths.REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    def _purge(pattern: str):
        for p in reports_dir.glob(pattern):
            try:
                p.unlink()
            except Exception:
                pass
    _purge('batch_jobs*.csv')
    _purge('batch_jobs*.pdf')
    _purge('batch_jobs*.xlsx')

    # Call list export endpoints in different formats
    resp_csv = client.get('/batch/api/batch/export?format=csv')
    assert resp_csv.status_code == 200
    resp_pdf = client.get('/batch/api/batch/export?format=pdf')
    assert resp_pdf.status_code == 200
    resp_xlsx = client.get('/batch/api/batch/export?format=xlsx')
    assert resp_xlsx.status_code == 200

    csv_files = sorted(reports_dir.glob('batch_jobs*.csv'))
    pdf_files = sorted(reports_dir.glob('batch_jobs*.pdf'))
    xlsx_files = sorted(reports_dir.glob('batch_jobs*.xlsx'))
    assert csv_files, 'Expected at least one timestamped CSV export'
    assert pdf_files, 'Expected at least one timestamped PDF export'
    assert xlsx_files, 'Expected at least one timestamped XLSX export'
    for path in (csv_files[0], pdf_files[0], xlsx_files[0]):
        assert path.stat().st_size > 10
    pdf_bytes = pdf_files[0].read_bytes()[:4]
    assert pdf_bytes.startswith(b'%PDF')
    xlsx_bytes = xlsx_files[0].read_bytes()[:2]
    assert xlsx_bytes == b'PK'
