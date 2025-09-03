import os
from app.services.sample_generation_service import get_sample_generation_service

def test_models_detail_endpoint(client):
    os.environ['OPENROUTER_API_KEY'] = ''
    svc = get_sample_generation_service()
    # Seed model registry minimally if empty
    if not svc.model_registry.get_available_models():
        # Simulate loading by manually appending (registry has public list attribute available_models)
        svc.model_registry.available_models.extend(['minimax/minimax-12b-chat:free', 'anthropic/claude-3'])
    resp = client.get('/api/sample-gen/models?detail=1&mode=all')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    models = data['data']
    assert isinstance(models, list) and models, 'Expected non-empty model list'
    sample = models[0]
    assert {'name','provider','is_free','capabilities'}.issubset(sample.keys())
    # Ensure free flag recognized for :free suffix
    free_entry = next((m for m in models if m['name'].endswith(':free')), None)
    if free_entry:
        assert free_entry['is_free'] is True
