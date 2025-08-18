from app.factory import create_app
from app.services.service_locator import ServiceLocator

app = create_app()
with app.app_context():
    svc = ServiceLocator.get_model_service()
    try:
        svc.populate_database_from_files()
    except Exception as e:
        print('populate failed', e)
    client = app.test_client()
    slug = 'anthropic_claude-3.7-sonnet'
    app_num = 1
    url = f'/api/app/{slug}/{app_num}/proxy/frontend'
    print('GET', url)
    resp = client.get(url)
    print('status', resp.status_code)
    print('content-type', resp.headers.get('Content-Type'))
    text = resp.get_data(as_text=True)
    print('body preview:', text[:200])
