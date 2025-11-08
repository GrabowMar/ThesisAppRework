"""
Batch update all 30 requirement files with complete API schemas.
Processes files individually to avoid syntax issues with large embedded dicts.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional

REQUIREMENTS_DIR = Path('misc/requirements')

def add_health_endpoint(endpoints: list) -> list:
    """Ensure health endpoint exists with proper schema."""
    health_exists = any(e.get('path') == '/api/health' for e in endpoints)
    if not health_exists:
        endpoints.append({
            "method": "GET",
            "path": "/api/health",
            "description": "Health check endpoint",
            "request": None,
            "response": {"status": "healthy", "service": "backend"}
        })
    else:
        for e in endpoints:
            if e.get('path') == '/api/health':
                e['request'] = None
                e['response'] = {"status": "healthy", "service": "backend"}
    return endpoints


def update_api_url_shortener():
    file = REQUIREMENTS_DIR / 'api_url_shortener.json'
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data['api_endpoints'] = [
        {"method": "GET", "path": "/api/urls", "description": "List recently shortened URLs",
         "request": None, "response": {"items": [{"id": 1, "original_url": "string", "short_code": "string", "click_count": 0, "created_at": "ISO8601"}], "total": 1}},
        {"method": "POST", "path": "/api/shorten", "description": "Create short URL from original URL",
         "request": {"url": "string"}, "response": {"id": 1, "original_url": "string", "short_code": "string", "short_url": "string", "click_count": 0, "created_at": "ISO8601"}},
        {"method": "GET", "path": "/:code", "description": "Redirect short code to original URL",
         "request": None, "response": "302 redirect"},
        {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
         "request": None, "response": {"status": "healthy", "service": "backend"}}
    ]
    
    data['data_model'] = {
        "name": "URL",
        "fields": {"id": "integer (primary key, auto-increment)", "original_url": "string (required, max 2048 chars)",
                   "short_code": "string (unique, 6 chars)", "click_count": "integer (default: 0)", "created_at": "datetime (auto, ISO 8601 format in JSON)"}
    }
    
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ api_url_shortener")


def update_api_weather_display():
    file = REQUIREMENTS_DIR / 'api_weather_display.json'
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data['api_endpoints'] = [
        {"method": "GET", "path": "/api/weather", "description": "Get weather for a city (query param: city)",
         "request": None, "response": {"city": "string", "temperature": 20.5, "condition": "string", "humidity": 65, "feels_like": 19.0, "icon": "string"}},
        {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
         "request": None, "response": {"status": "healthy", "service": "backend"}}
    ]
    
    data['data_model'] = None  # External API proxy
    
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ api_weather_display")


def update_auth_user_login():
    file = REQUIREMENTS_DIR / 'auth_user_login.json'
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data['api_endpoints'] = [
        {"method": "POST", "path": "/api/auth/register", "description": "Register new user",
         "request": {"username": "string", "password": "string", "email": "string (optional)"},
         "response": {"id": 1, "username": "string", "email": "string", "created_at": "ISO8601"}},
        {"method": "POST", "path": "/api/auth/login", "description": "Login and get JWT token",
         "request": {"username": "string", "password": "string"},
         "response": {"token": "string (JWT)", "user": {"id": 1, "username": "string", "email": "string"}}},
        {"method": "GET", "path": "/api/auth/me", "description": "Get current user info (requires auth)",
         "request": None, "response": {"id": 1, "username": "string", "email": "string", "created_at": "ISO8601"}},
        {"method": "POST", "path": "/api/auth/logout", "description": "Logout user",
         "request": None, "response": {"message": "Logged out successfully"}},
        {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
         "request": None, "response": {"status": "healthy", "service": "backend"}}
    ]
    
    data['data_model'] = {
        "name": "User",
        "fields": {"id": "integer (primary key, auto-increment)", "username": "string (unique, required, 3-20 chars)",
                   "password_hash": "string (never exposed in responses)", "email": "string (optional)", "created_at": "datetime (auto, ISO 8601 format in JSON)"}
    }
    
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ auth_user_login")


def update_all_crud_apps():
    """Update all CRUD-pattern apps with standard schemas."""
    
    crud_apps = {
        'crud_book_library': {
            'resource': 'books',
            'item': {"id": 1, "title": "string", "author": "string", "year": 2020, "isbn": "string", "created_at": "ISO8601"},
            'create_req': {"title": "string", "author": "string", "year": "integer (optional)", "isbn": "string (optional)"},
            'update_req': {"title": "string (optional)", "author": "string (optional)", "year": "integer (optional)", "isbn": "string (optional)"},
            'model': {"name": "Book", "fields": {"id": "integer (primary key, auto-increment)", "title": "string (required, max 255 chars)",
                     "author": "string (required, max 255 chars)", "year": "integer (optional, 4 digits)", "isbn": "string (optional, max 20 chars)",
                     "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'crm_customer_list': {
            'resource': 'customers',
            'item': {"id": 1, "name": "string", "email": "string", "phone": "string", "company": "string", "created_at": "ISO8601"},
            'create_req': {"name": "string", "email": "string", "phone": "string (optional)", "company": "string (optional)"},
            'update_req': {"name": "string (optional)", "email": "string (optional)", "phone": "string (optional)", "company": "string (optional)"},
            'model': {"name": "Customer", "fields": {"id": "integer (primary key, auto-increment)", "name": "string (required, max 100 chars)",
                     "email": "string (required, valid email)", "phone": "string (optional, max 20 chars)", "company": "string (optional, max 100 chars)",
                     "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'finance_expense_list': {
            'resource': 'expenses',
            'item': {"id": 1, "amount": 50.75, "category": "string", "description": "string", "date": "ISO8601", "created_at": "ISO8601"},
            'create_req': {"amount": "number", "category": "string", "description": "string (optional)", "date": "string (optional)"},
            'update_req': {"amount": "number (optional)", "category": "string (optional)", "description": "string (optional)", "date": "string (optional)"},
            'model': {"name": "Expense", "fields": {"id": "integer (primary key, auto-increment)", "amount": "decimal (required, 2 decimal places)",
                     "category": "string (required, max 50 chars)", "description": "string (optional, max 255 chars)", "date": "date (default: today)",
                     "created_at": "datetime (auto, ISO 8601 format in JSON)"}},
            'extra_endpoints': [
                {"method": "GET", "path": "/api/expenses/total", "description": "Get sum of all expenses",
                 "request": None, "response": {"total": 1250.50, "count": 42}},
                {"method": "GET", "path": "/api/expenses/by-category", "description": "Get totals grouped by category",
                 "request": None, "response": {"categories": [{"category": "Food", "total": 450.25, "count": 15}]}}
            ]
        }
    }
    
    for slug, config in crud_apps.items():
        file = REQUIREMENTS_DIR / f'{slug}.json'
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        endpoints = [
            {"method": "GET", "path": f"/api/{config['resource']}", "description": f"List all {config['resource']}",
             "request": None, "response": {"items": [config['item']], "total": 1}},
            {"method": "POST", "path": f"/api/{config['resource']}", "description": f"Create new {config['resource'][:-1]}",
             "request": config['create_req'], "response": config['item']},
            {"method": "PUT", "path": f"/api/{config['resource']}/:id", "description": f"Update {config['resource'][:-1]}",
             "request": config['update_req'], "response": config['item']},
            {"method": "DELETE", "path": f"/api/{config['resource']}/:id", "description": f"Delete {config['resource'][:-1]}",
             "request": None, "response": {}}
        ]
        
        if 'extra_endpoints' in config:
            endpoints.extend(config['extra_endpoints'])
        
        endpoints.append({"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                         "request": None, "response": {"status": "healthy", "service": "backend"}})
        
        data['api_endpoints'] = endpoints
        data['data_model'] = config['model']
        
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ {slug}")


def main():
    print("🚀 Updating all 30 requirement files with complete API schemas...\n")
    
    update_api_url_shortener()
    update_api_weather_display()
    update_auth_user_login()
    update_all_crud_apps()
    
    # Continue with remaining apps in batches...
    print("\n✨ Phase 1 complete! (6 files updated)")
    print("📋 Run phase 2 script for remaining 24 files")


if __name__ == '__main__':
    main()
