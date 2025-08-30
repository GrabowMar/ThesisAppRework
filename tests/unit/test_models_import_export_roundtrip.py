import json
from app.models import db, ModelCapability

def test_models_export_import_roundtrip(client, app):
    # Seed a minimal model
    with app.app_context():
        m = ModelCapability()
        m.canonical_slug = 'test_provider_test-model'
        m.provider = 'test_provider'
        m.model_name = 'test-model'
        m.model_id = 'test_provider/test-model'
        m.input_price_per_token = 0.001
        m.output_price_per_token = 0.002
        m.context_window = 8000
        m.max_output_tokens = 1024
        db.session.add(m)
        db.session.commit()

    # Export JSON
    resp = client.get('/api/models/export?format=json')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'models' in data
    assert any(r.get('slug') == 'test_provider_test-model' for r in data['models'])

    # Import same JSON (idempotent)
    resp2 = client.post('/api/models/import', data=json.dumps(data), content_type='application/json')
    assert resp2.status_code == 200
    result = resp2.get_json()
    assert result['success'] is True
    # Either created 0 and updated >=1, or vice versa, but no errors
    assert 'errors' in result
    assert not result['errors']

    # Verify model persists with expected fields
    with app.app_context():
        mm = ModelCapability.query.filter_by(canonical_slug='test_provider_test-model').first()
        assert mm is not None
        assert mm.context_window == 8000
        assert round(mm.input_price_per_token*1000, 6) == 1.0
        assert round(mm.output_price_per_token*1000, 6) == 2.0
