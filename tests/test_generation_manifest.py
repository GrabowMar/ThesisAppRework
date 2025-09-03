import json
from pathlib import Path

from app.services.sample_generation_service import get_sample_generation_service

def test_generation_creates_manifest(tmp_path, monkeypatch):
    # Redirect GENERATED_ROOT for isolation if needed (simple monkeypatch by chdir not implemented here)
    service = get_sample_generation_service()

    # Seed simple template if none
    if not service.template_registry.templates:
        service.template_registry.load_from_dicts([
            {"app_num": 1, "name": "demo", "content": "Example template", "requirements": ["flask"]}
        ])

    # Use mock model (no API key required)
    result_id, result = __import__('asyncio').run(service.generate_async('1', 'mock/test-model'))
    assert result.success

    manifest_path = Path('src/generated/indices/generation_manifest.json')
    assert manifest_path.exists(), 'Manifest file should exist'
    data = json.loads(manifest_path.read_text())
    assert any(entry['result_id'] == result_id for entry in data), 'Result id should be in manifest'
