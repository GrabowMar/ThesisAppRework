"""Integration tests for /models/export/models.csv endpoint."""

from app.models import ModelCapability, db


def seed_models(count: int = 3):
    for i in range(count):
        m = ModelCapability()
        m.model_id = f"provider{i%2}/model_{i}"
        m.canonical_slug = f"model_{i}"
        m.provider = f"provider{i%2}"
        m.model_name = f"Model {i}"
        m.is_free = (i % 2 == 0)
        db.session.add(m)
    db.session.commit()


def test_models_export_csv_headers_and_rows(client, app):
    """Ensure CSV export returns expected headers and row count == models count."""
    with app.app_context():
        seed_models(5)

    resp = client.get('/models/export/models.csv')
    assert resp.status_code == 200
    assert resp.mimetype == 'text/csv'

    content = resp.get_data(as_text=True).strip().splitlines()
    assert len(content) >= 2  # header + at least one row

    header = content[0].split(',')
    # Minimal expected columns
    for col in ['provider', 'model_name', 'slug']:
        assert col in header, f"Missing expected column {col} in header {header}"

    data_rows = content[1:]
    # 5 models seeded -> 5 rows
    assert len(data_rows) == 5, f"Expected 5 data rows, got {len(data_rows)}"

    # Basic sanity: each row has same number of columns as header
    for row in data_rows:
        assert len(row.split(',')) == len(header)