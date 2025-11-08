"""Phase 2: Update remaining requirement files with complete API schemas."""
import json
from pathlib import Path

REQUIREMENTS_DIR = Path('misc/requirements')


def update_simple_list_apps():
    """Update apps that list and manage items."""
    
    apps = {
        'booking_reservations': {
            'resource': 'reservations',
            'item': {"id": 1, "name": "string", "email": "string", "date": "ISO8601", "time": "string", "party_size": 4, "created_at": "ISO8601"},
            'create_req': {"name": "string", "email": "string", "date": "string", "time": "string", "party_size": "integer"},
            'model': {"name": "Reservation", "fields": {"id": "integer (primary key, auto-increment)", "name": "string (required, max 100 chars)",
                     "email": "string (required, valid email)", "date": "date (required)", "time": "string (required, HH:MM format)",
                     "party_size": "integer (required, min 1)", "created_at": "datetime (auto, ISO 8601 format in JSON)"}},
            'endpoints': [
                {"method": "GET", "path": "/api/reservations", "description": "List all reservations (supports ?date= filter)",
                 "request": None, "response": {"items": [{"id": 1, "name": "string", "email": "string", "date": "ISO8601", "time": "string", "party_size": 4, "created_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/reservations", "description": "Create new reservation",
                 "request": {"name": "string", "email": "string", "date": "string", "time": "string", "party_size": "integer"},
                 "response": {"id": 1, "name": "string", "email": "string", "date": "ISO8601", "time": "string", "party_size": 4, "created_at": "ISO8601"}},
                {"method": "DELETE", "path": "/api/reservations/:id", "description": "Cancel reservation",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ]
        },
        'content_recipe_list': {
            'resource': 'recipes',
            'endpoints': [
                {"method": "GET", "path": "/api/recipes", "description": "List all recipes (supports ?category= filter)",
                 "request": None, "response": {"items": [{"id": 1, "title": "string", "ingredients": ["string"], "instructions": "string", "category": "string", "created_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/recipes", "description": "Create new recipe",
                 "request": {"title": "string", "ingredients": ["string"], "instructions": "string", "category": "string (optional)"},
                 "response": {"id": 1, "title": "string", "ingredients": ["string"], "instructions": "string", "category": "string", "created_at": "ISO8601"}},
                {"method": "GET", "path": "/api/recipes/:id", "description": "Get recipe details",
                 "request": None, "response": {"id": 1, "title": "string", "ingredients": ["string"], "instructions": "string", "category": "string", "created_at": "ISO8601"}},
                {"method": "DELETE", "path": "/api/recipes/:id", "description": "Delete recipe",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Recipe", "fields": {"id": "integer (primary key, auto-increment)", "title": "string (required, max 200 chars)",
                     "ingredients": "JSON array of strings", "instructions": "text (required)", "category": "string (optional, max 50 chars)",
                     "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'dataviz_sales_table': {
            'resource': 'sales',
            'endpoints': [
                {"method": "GET", "path": "/api/sales", "description": "List all sales (supports ?start_date= and ?end_date= filters)",
                 "request": None, "response": {"items": [{"id": 1, "product": "string", "amount": 100.50, "quantity": 5, "date": "ISO8601", "created_at": "ISO8601"}], "total": 1, "sum": 100.50}},
                {"method": "POST", "path": "/api/sales", "description": "Create new sale record",
                 "request": {"product": "string", "amount": "number", "quantity": "integer", "date": "string (optional)"},
                 "response": {"id": 1, "product": "string", "amount": 100.50, "quantity": 5, "date": "ISO8601", "created_at": "ISO8601"}},
                {"method": "GET", "path": "/api/sales/summary", "description": "Get sales summary statistics",
                 "request": None, "response": {"total_sales": 1500.75, "total_transactions": 25, "average_sale": 60.03}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Sale", "fields": {"id": "integer (primary key, auto-increment)", "product": "string (required, max 100 chars)",
                     "amount": "decimal (required, 2 decimal places)", "quantity": "integer (required, min 1)", "date": "date (default: today)",
                     "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'gaming_leaderboard': {
            'resource': 'leaderboard',
            'endpoints': [
                {"method": "GET", "path": "/api/leaderboard", "description": "Get top players sorted by score",
                 "request": None, "response": {"items": [{"id": 1, "player_name": "string", "score": 9999, "rank": 1, "created_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/leaderboard", "description": "Submit new score",
                 "request": {"player_name": "string", "score": "integer"},
                 "response": {"id": 1, "player_name": "string", "score": 9999, "rank": 5, "created_at": "ISO8601"}},
                {"method": "GET", "path": "/api/leaderboard/top/:limit", "description": "Get top N players",
                 "request": None, "response": {"items": [{"id": 1, "player_name": "string", "score": 9999, "rank": 1}], "total": 10}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Score", "fields": {"id": "integer (primary key, auto-increment)", "player_name": "string (required, max 50 chars)",
                     "score": "integer (required, min 0)", "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'healthcare_appointments': {
            'resource': 'appointments',
            'endpoints': [
                {"method": "GET", "path": "/api/appointments", "description": "List all appointments (supports ?date= filter)",
                 "request": None, "response": {"items": [{"id": 1, "patient_name": "string", "doctor": "string", "date": "ISO8601", "time": "string", "reason": "string", "created_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/appointments", "description": "Schedule new appointment",
                 "request": {"patient_name": "string", "doctor": "string", "date": "string", "time": "string", "reason": "string (optional)"},
                 "response": {"id": 1, "patient_name": "string", "doctor": "string", "date": "ISO8601", "time": "string", "reason": "string", "created_at": "ISO8601"}},
                {"method": "PUT", "path": "/api/appointments/:id", "description": "Update appointment",
                 "request": {"date": "string (optional)", "time": "string (optional)", "reason": "string (optional)"},
                 "response": {"id": 1, "patient_name": "string", "doctor": "string", "date": "ISO8601", "time": "string", "reason": "string", "created_at": "ISO8601"}},
                {"method": "DELETE", "path": "/api/appointments/:id", "description": "Cancel appointment",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Appointment", "fields": {"id": "integer (primary key, auto-increment)", "patient_name": "string (required, max 100 chars)",
                     "doctor": "string (required, max 100 chars)", "date": "date (required)", "time": "string (required, HH:MM format)",
                     "reason": "text (optional)", "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'inventory_stock_list': {
            'resource': 'inventory',
            'endpoints': [
                {"method": "GET", "path": "/api/inventory", "description": "List all items (supports ?low_stock=true for items below threshold)",
                 "request": None, "response": {"items": [{"id": 1, "name": "string", "sku": "string", "quantity": 50, "min_quantity": 10, "low_stock": False, "created_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/inventory", "description": "Add new item",
                 "request": {"name": "string", "sku": "string", "quantity": "integer", "min_quantity": "integer (optional)"},
                 "response": {"id": 1, "name": "string", "sku": "string", "quantity": 50, "min_quantity": 10, "low_stock": False, "created_at": "ISO8601"}},
                {"method": "PUT", "path": "/api/inventory/:id", "description": "Update item quantity",
                 "request": {"quantity": "integer (optional)", "min_quantity": "integer (optional)"},
                 "response": {"id": 1, "name": "string", "sku": "string", "quantity": 75, "min_quantity": 10, "low_stock": False, "created_at": "ISO8601"}},
                {"method": "DELETE", "path": "/api/inventory/:id", "description": "Delete item",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "InventoryItem", "fields": {"id": "integer (primary key, auto-increment)", "name": "string (required, max 100 chars)",
                     "sku": "string (unique, required, max 50 chars)", "quantity": "integer (required, min 0)", "min_quantity": "integer (default: 10, low stock threshold)",
                     "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'learning_flashcards': {
            'resource': 'flashcards',
            'endpoints': [
                {"method": "GET", "path": "/api/flashcards", "description": "List all flashcards",
                 "request": None, "response": {"items": [{"id": 1, "question": "string", "answer": "string", "category": "string", "created_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/flashcards", "description": "Create new flashcard",
                 "request": {"question": "string", "answer": "string", "category": "string (optional)"},
                 "response": {"id": 1, "question": "string", "answer": "string", "category": "string", "created_at": "ISO8601"}},
                {"method": "GET", "path": "/api/flashcards/random", "description": "Get random flashcard",
                 "request": None, "response": {"id": 1, "question": "string", "answer": "string", "category": "string"}},
                {"method": "DELETE", "path": "/api/flashcards/:id", "description": "Delete flashcard",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Flashcard", "fields": {"id": "integer (primary key, auto-increment)", "question": "text (required)",
                     "answer": "text (required)", "category": "string (optional, max 50 chars)", "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'productivity_notes': {
            'resource': 'notes',
            'endpoints': [
                {"method": "GET", "path": "/api/notes", "description": "List all notes (supports ?query= search)",
                 "request": None, "response": {"items": [{"id": 1, "title": "string", "content": "string", "tags": ["tag1"], "created_at": "ISO8601", "updated_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/notes", "description": "Create new note",
                 "request": {"title": "string", "content": "string", "tags": "array (optional)"},
                 "response": {"id": 1, "title": "string", "content": "string", "tags": ["tag1"], "created_at": "ISO8601", "updated_at": "ISO8601"}},
                {"method": "GET", "path": "/api/notes/:id", "description": "Get note details",
                 "request": None, "response": {"id": 1, "title": "string", "content": "string", "tags": ["tag1"], "created_at": "ISO8601", "updated_at": "ISO8601"}},
                {"method": "PUT", "path": "/api/notes/:id", "description": "Update note",
                 "request": {"title": "string (optional)", "content": "string (optional)", "tags": "array (optional)"},
                 "response": {"id": 1, "title": "string", "content": "string", "tags": ["tag1"], "created_at": "ISO8601", "updated_at": "ISO8601"}},
                {"method": "DELETE", "path": "/api/notes/:id", "description": "Delete note",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Note", "fields": {"id": "integer (primary key, auto-increment)", "title": "string (required, max 255 chars)",
                     "content": "text (required)", "tags": "JSON array of strings", "created_at": "datetime (auto, ISO 8601 format in JSON)",
                     "updated_at": "datetime (auto-update, ISO 8601 format)"}}
        },
        'scheduling_event_list': {
            'resource': 'events',
            'endpoints': [
                {"method": "GET", "path": "/api/events", "description": "List all events (supports ?start_date= and ?end_date= filters)",
                 "request": None, "response": {"items": [{"id": 1, "title": "string", "description": "string", "start_time": "ISO8601", "end_time": "ISO8601", "location": "string", "created_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/events", "description": "Create new event",
                 "request": {"title": "string", "description": "string (optional)", "start_time": "string", "end_time": "string", "location": "string (optional)"},
                 "response": {"id": 1, "title": "string", "description": "string", "start_time": "ISO8601", "end_time": "ISO8601", "location": "string", "created_at": "ISO8601"}},
                {"method": "PUT", "path": "/api/events/:id", "description": "Update event",
                 "request": {"title": "string (optional)", "description": "string (optional)", "start_time": "string (optional)", "end_time": "string (optional)", "location": "string (optional)"},
                 "response": {"id": 1, "title": "string", "description": "string", "start_time": "ISO8601", "end_time": "ISO8601", "location": "string", "created_at": "ISO8601"}},
                {"method": "DELETE", "path": "/api/events/:id", "description": "Delete event",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Event", "fields": {"id": "integer (primary key, auto-increment)", "title": "string (required, max 255 chars)",
                     "description": "text (optional)", "start_time": "datetime (required, ISO 8601 format)", "end_time": "datetime (required, ISO 8601 format)",
                     "location": "string (optional, max 255 chars)", "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'social_blog_posts': {
            'resource': 'posts',
            'endpoints': [
                {"method": "GET", "path": "/api/posts", "description": "List all blog posts (supports ?tag= filter)",
                 "request": None, "response": {"items": [{"id": 1, "title": "string", "content": "string", "author": "string", "tags": ["tag1"], "published_at": "ISO8601", "created_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/posts", "description": "Create new blog post",
                 "request": {"title": "string", "content": "string", "author": "string", "tags": "array (optional)"},
                 "response": {"id": 1, "title": "string", "content": "string", "author": "string", "tags": ["tag1"], "published_at": "ISO8601", "created_at": "ISO8601"}},
                {"method": "GET", "path": "/api/posts/:id", "description": "Get post details",
                 "request": None, "response": {"id": 1, "title": "string", "content": "string", "author": "string", "tags": ["tag1"], "published_at": "ISO8601", "created_at": "ISO8601"}},
                {"method": "PUT", "path": "/api/posts/:id", "description": "Update blog post",
                 "request": {"title": "string (optional)", "content": "string (optional)", "tags": "array (optional)"},
                 "response": {"id": 1, "title": "string", "content": "string", "author": "string", "tags": ["tag1"], "published_at": "ISO8601", "created_at": "ISO8601"}},
                {"method": "DELETE", "path": "/api/posts/:id", "description": "Delete blog post",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Post", "fields": {"id": "integer (primary key, auto-increment)", "title": "string (required, max 255 chars)",
                     "content": "text (required)", "author": "string (required, max 100 chars)", "tags": "JSON array of strings",
                     "published_at": "datetime (auto, ISO 8601 format)", "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        }
    }
    
    for slug, config in apps.items():
        file = REQUIREMENTS_DIR / f'{slug}.json'
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data['api_endpoints'] = config['endpoints']
        data['data_model'] = config['model']
        
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ {slug}")


def main():
    print("🚀 Phase 2: Updating list-based apps...\n")
    update_simple_list_apps()
    print("\n✨ Phase 2 complete! (11 files updated)")
    print("📋 Run phase 3 script for remaining files")


if __name__ == '__main__':
    main()
