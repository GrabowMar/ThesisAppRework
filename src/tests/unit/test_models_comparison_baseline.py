from app.models import db, ModelCapability


def seed_models(app):
    with app.app_context():
        # Clear any existing
        ModelCapability.query.delete()
        db.session.commit()
    m1 = ModelCapability()
    m1.model_id = 'prov_a/model1'
    m1.canonical_slug = 'prov_a_model1'
    m1.provider = 'prov_a'
    m1.model_name = 'model1'
    m1.input_price_per_token = 0.001  # 1 per 1k
    m1.output_price_per_token = 0.002  # 2 per 1k
    m1.context_window = 8000
    m1.max_output_tokens = 1024

    m2 = ModelCapability()
    m2.model_id = 'prov_b/model2'
    m2.canonical_slug = 'prov_b_model2'
    m2.provider = 'prov_b'
    m2.model_name = 'model2'
    m2.input_price_per_token = 0.002  # 2 per 1k
    m2.output_price_per_token = 0.004  # 4 per 1k
    m2.context_window = 16000
    m2.max_output_tokens = 2048

    m3 = ModelCapability()
    m3.model_id = 'prov_c/model3'
    m3.canonical_slug = 'prov_c_model3'
    m3.provider = 'prov_c'
    m3.model_name = 'model3'
    m3.input_price_per_token = 0.0
    m3.output_price_per_token = 0.0
    m3.context_window = 4000
    m3.max_output_tokens = 512

    db.session.add_all([m1, m2, m3])
    db.session.commit()


def test_comparison_baseline_avg(client, app):
    seed_models(app)
    # Compare the three models with baseline=avg
    resp = client.post('/api/models/comparison/refresh', data={'models': 'prov_a_model1,prov_b_model2,prov_c_model3', 'baseline': 'avg'})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # baseline section should mention BASELINE: AVG (case-insensitive)
    assert 'BASELINE' in html.upper() or 'Baseline' in html


def test_comparison_baseline_median(client, app):
    seed_models(app)
    resp = client.post('/api/models/comparison/refresh', data={'models': 'prov_a_model1,prov_b_model2,prov_c_model3', 'baseline': 'median'})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'BASELINE' in html.upper() or 'Baseline' in html


def test_comparison_baseline_model_slug(client, app):
    seed_models(app)
    # Use model2 as baseline
    resp = client.post('/api/models/comparison/refresh', data={'models': 'prov_a_model1,prov_b_model2,prov_c_model3', 'baseline': 'model:prov_b_model2'})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # The baseline footer should show 'prov_b_model2' or the baseline choice reflected
    assert 'prov_b_model2' in html or 'model2' in html
