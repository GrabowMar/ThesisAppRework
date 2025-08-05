from src.app import create_app

app = create_app()
with app.test_client() as client:
    response = client.get('/testing/api/models')
    print(f'Testing models API status: {response.status_code}')
    
    if response.status_code == 200:
        data = response.get_json()
        print(f'Success: {data.get("success")}')
        models = data.get('data', [])
        print(f'Found {len(models)} models')
        if models:
            print('First model:')
            model = models[0]
            print(f'  id: {model.get("id")}')
            print(f'  slug: {model.get("slug")}')
            print(f'  name: {model.get("name")}')
            print(f'  display_name: {model.get("display_name")}')
            print(f'  provider: {model.get("provider")}')
    else:
        print(f'Error response: {response.get_data(as_text=True)}')
