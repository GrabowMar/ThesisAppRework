def test_sample_generation_flow(client):
    # 1. Upsert a template
    resp = client.post('/api/sample-gen/templates/upsert', json={
        'templates': [
            {
                'app_num': 1,
                'name': 'test_api',
                'content': 'Simple test API that returns hello',
                'requirements': ['Flask']
            }
        ]
    })
    assert resp.status_code == 200, resp.data
    data = resp.get_json()
    assert data['success']
    assert data['data']['count'] == 1

    # 2. List templates
    resp = client.get('/api/sample-gen/templates')
    assert resp.status_code == 200
    templates = resp.get_json()['data']
    assert len(templates) == 1
    assert templates[0]['name'] == 'test_api'

    # 3. Generate mock code (no external call)
    resp = client.post('/api/sample-gen/generate', json={
        'template_id': '1',
        'model': 'mock/local-model'
    })
    assert resp.status_code == 200, resp.data
    gen_payload = resp.get_json()['data']
    assert gen_payload['success'] is True
    result_id = gen_payload['result_id']
    assert result_id

    # 4. Fetch result metadata
    resp = client.get(f'/api/sample-gen/results/{result_id}')
    assert resp.status_code == 200
    result_meta = resp.get_json()['data']
    assert result_meta['app_name'] == 'test_api'
    assert result_meta['success'] is True

    # 5. Fetch result with content
    resp = client.get(f'/api/sample-gen/results/{result_id}?include_content=true')
    assert resp.status_code == 200
    result_full = resp.get_json()['data']
    assert 'content' in result_full
    assert 'mock backend' in result_full['content'].lower()

    # 6. List all results
    resp = client.get('/api/sample-gen/results')
    assert resp.status_code == 200
    results_list = resp.get_json()['data']
    assert any(r['app_name'] == 'test_api' for r in results_list)

    # 7. Project structure
    resp = client.get('/api/sample-gen/structure')
    assert resp.status_code == 200
    structure = resp.get_json()['data']
    # Should contain a model folder with at least one app1 directory
    assert any('app1' in apps for apps in structure.values())
