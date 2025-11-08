"""Update all requirement files with complete request/response schemas."""
import json
from pathlib import Path

REQUIREMENTS_DIR = Path('misc/requirements')


def process_crud_app(slug, resource_name, fields):
    """Generate standard CRUD endpoints."""
    return [
        {
            "method": "GET",
            "path": f"/api/{resource_name}",
            "description": f"List all {resource_name}",
            "request": None,
            "response": {"items": [fields], "total": 1}
        },
        {
            "method": "POST",
            "path": f"/api/{resource_name}",
            "description": f"Create new {resource_name[:-1]}",
            "request": {k: v for k, v in fields.items() if k not in ['id', 'created_at', 'updated_at']},
            "response": fields
        },
        {
            "method": "PUT",
            "path": f"/api/{resource_name}/:id",
            "description": f"Update {resource_name[:-1]}",
            "request": {k: f"{v} (optional)" for k, v in fields.items() if k not in ['id', 'created_at', 'updated_at']},
            "response": fields
        },
        {
            "method": "DELETE",
            "path": f"/api/{resource_name}/:id",
            "description": f"Delete {resource_name[:-1]}",
            "request": None,
            "response": {}
        },
        {
            "method": "GET",
            "path": "/api/health",
            "description": "Health check endpoint",
            "request": None,
            "response": {"status": "healthy", "service": "backend"}
        }
    ]


def update_file(filepath):
    """Update a single requirement file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    slug = data.get('slug')
    print(f"Processing {slug}...")
    
    # Keep existing api_endpoints structure, just add request/response where missing
    if 'api_endpoints' in data:
        for endpoint in data['api_endpoints']:
            if 'request' not in endpoint:
                endpoint['request'] = None
            if 'response' not in endpoint:
                # Add basic response based on endpoint type
                if endpoint['method'] == 'GET' and 'health' in endpoint['path']:
                    endpoint['response'] = {"status": "healthy", "service": "backend"}
                elif endpoint['method'] == 'DELETE':
                    endpoint['response'] = {}
                else:
                    endpoint['response'] = {"status": "success"}
    
    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return True


def main():
    json_files = sorted(REQUIREMENTS_DIR.glob('*.json'))
    print(f"Found {len(json_files)} requirement files\n")
    
    for filepath in json_files:
        try:
            update_file(filepath)
            print(f"✅ {filepath.name}")
        except Exception as e:
            print(f"❌ {filepath.name}: {e}")
    
    print(f"\n✨ Complete!")


if __name__ == '__main__':
    main()
