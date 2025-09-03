import os
import asyncio
from app.services.sample_generation_service import get_sample_generation_service, Template

def setup_service():
    os.environ['OPENROUTER_API_KEY'] = ''  # force mock path
    svc = get_sample_generation_service()
    svc.template_registry.templates.clear()
    svc.port_allocator.reset()
    svc._results.clear()
    return svc

def test_generation_metadata_endpoint(client):  # uses flask test client fixture if available
    svc = setup_service()
    # Add a template and generate a mock result
    t = Template(app_num=1, name='meta_api', content='Return a hello world endpoint', requirements=['Flask'])
    svc.template_registry.templates.append(t)
    rid, res = asyncio.run(svc.generate_async('1', 'mock/test-model'))
    assert res.success
    # Fetch metadata endpoint
    meta_resp = client.get(f'/api/sample-gen/results/{rid}/meta')
    assert meta_resp.status_code == 200, meta_resp.data
    payload = meta_resp.get_json()
    assert payload['success'] is True
    data = payload['data']
    # Ensure expected keys present
    for key in ['app_num','app_name','model','success','attempts','duration','extracted_blocks']:
        assert key in data
    assert 'content' not in data  # metadata endpoint should not include raw content
    # Blocks should expose port_replacements field
    if data['extracted_blocks']:
        blk = data['extracted_blocks'][0]
        assert 'port_replacements' in blk
