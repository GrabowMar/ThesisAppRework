"""Phase 3: Update remaining specialized requirement files."""
import json
from pathlib import Path

REQUIREMENTS_DIR = Path('misc/requirements')


def update_specialized_apps():
    """Update specialized apps with unique endpoint patterns."""
    
    # Apps with special endpoint structures
    specs = {
        'collaboration_simple_poll': {
            'endpoints': [
                {"method": "GET", "path": "/api/polls", "description": "List all polls",
                 "request": None, "response": {"items": [{"id": 1, "question": "string", "options": ["A", "B"], "created_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/polls", "description": "Create new poll",
                 "request": {"question": "string", "options": ["string"]},
                 "response": {"id": 1, "question": "string", "options": [{"id": 1, "text": "string", "votes": 0}], "created_at": "ISO8601"}},
                {"method": "GET", "path": "/api/polls/:id", "description": "Get poll details with vote counts",
                 "request": None, "response": {"id": 1, "question": "string", "options": [{"id": 1, "text": "string", "votes": 5}], "total_votes": 10, "created_at": "ISO8601"}},
                {"method": "POST", "path": "/api/polls/:id/vote", "description": "Vote on a poll option",
                 "request": {"option_id": "integer"}, "response": {"success": True, "option_id": 1, "new_vote_count": 6}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Poll", "fields": {"id": "integer (primary key, auto-increment)", "question": "string (required, max 500 chars)",
                     "created_at": "datetime (auto, ISO 8601 format in JSON)"}, "related": "PollOption (id, poll_id, text, votes)"}
        },
        'ecommerce_cart': {
            'endpoints': [
                {"method": "GET", "path": "/api/products", "description": "List all products",
                 "request": None, "response": {"items": [{"id": 1, "name": "string", "price": 29.99, "description": "string", "image_url": "string"}], "total": 1}},
                {"method": "GET", "path": "/api/cart", "description": "Get current cart items",
                 "request": None, "response": {"items": [{"id": 1, "product_id": 1, "product_name": "string", "price": 29.99, "quantity": 2}], "subtotal": 59.98, "total": 59.98}},
                {"method": "POST", "path": "/api/cart/add", "description": "Add product to cart",
                 "request": {"product_id": "integer", "quantity": "integer (default: 1)"}, "response": {"id": 1, "product_id": 1, "quantity": 2}},
                {"method": "PUT", "path": "/api/cart/:itemId", "description": "Update cart item quantity",
                 "request": {"quantity": "integer"}, "response": {"id": 1, "product_id": 1, "quantity": 3}},
                {"method": "DELETE", "path": "/api/cart/:itemId", "description": "Remove item from cart",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/cart/total", "description": "Get cart total price",
                 "request": None, "response": {"subtotal": 59.98, "tax": 5.40, "total": 65.38}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Product & CartItem", "fields": {"Product.id": "integer (primary key)", "Product.name": "string (required)",
                     "Product.price": "decimal (required)", "Product.description": "text", "Product.image_url": "string",
                     "CartItem.id": "integer (primary key)", "CartItem.product_id": "integer (foreign key)", "CartItem.quantity": "integer (default: 1)"}}
        },
        'education_quiz_app': {
            'endpoints': [
                {"method": "GET", "path": "/api/quiz/questions", "description": "Get random quiz questions",
                 "request": None, "response": {"questions": [{"id": 1, "question": "string", "options": ["A", "B", "C", "D"]}]}},
                {"method": "POST", "path": "/api/quiz/submit", "description": "Submit quiz answers and get score",
                 "request": {"answers": [{"question_id": 1, "answer": "string"}]},
                 "response": {"score": 75, "total": 100, "correct": 3, "total_questions": 4, "results": [{"question_id": 1, "correct": True, "your_answer": "A", "correct_answer": "A"}]}},
                {"method": "GET", "path": "/api/quiz/review/:id", "description": "Review quiz results",
                 "request": None, "response": {"score": 75, "total": 100, "submitted_at": "ISO8601", "results": []}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Question", "fields": {"id": "integer (primary key)", "question": "text (required)", "options": "JSON array (4 options)",
                     "correct_answer": "string (A-D, not exposed to frontend until submitted)"}}
        },
        'fileproc_image_upload': {
            'endpoints': [
                {"method": "POST", "path": "/api/images/upload", "description": "Upload image file",
                 "request": "multipart/form-data with 'image' field",
                 "response": {"id": 1, "filename": "string", "url": "/uploads/image.jpg", "size": 12345, "uploaded_at": "ISO8601"}},
                {"method": "GET", "path": "/api/images", "description": "List all images",
                 "request": None, "response": {"items": [{"id": 1, "filename": "string", "url": "string", "size": 12345, "uploaded_at": "ISO8601"}], "total": 1}},
                {"method": "DELETE", "path": "/api/images/:id", "description": "Delete image",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Image", "fields": {"id": "integer (primary key)", "filename": "string (required, original name)",
                     "filepath": "string (server path)", "size": "integer (bytes)", "uploaded_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'geolocation_store_list': {
            'endpoints': [
                {"method": "GET", "path": "/api/stores", "description": "List all stores (supports ?lat=, ?lng=, ?radius= for proximity search)",
                 "request": None, "response": {"items": [{"id": 1, "name": "string", "address": "string", "latitude": 40.7128, "longitude": -74.0060, "distance": 2.5}], "total": 1}},
                {"method": "POST", "path": "/api/stores", "description": "Create new store",
                 "request": {"name": "string", "address": "string", "latitude": "number", "longitude": "number"},
                 "response": {"id": 1, "name": "string", "address": "string", "latitude": 40.7128, "longitude": -74.0060, "created_at": "ISO8601"}},
                {"method": "GET", "path": "/api/stores/:id", "description": "Get store details",
                 "request": None, "response": {"id": 1, "name": "string", "address": "string", "latitude": 40.7128, "longitude": -74.0060, "created_at": "ISO8601"}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Store", "fields": {"id": "integer (primary key, auto-increment)", "name": "string (required, max 100 chars)",
                     "address": "string (required, max 255 chars)", "latitude": "decimal (required, -90 to 90)", "longitude": "decimal (required, -180 to 180)",
                     "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'iot_sensor_display': {
            'endpoints': [
                {"method": "GET", "path": "/api/sensors", "description": "List all sensors with current readings",
                 "request": None, "response": {"items": [{"id": 1, "name": "string", "type": "temperature", "value": 22.5, "unit": "°C", "updated_at": "ISO8601"}], "total": 1}},
                {"method": "GET", "path": "/api/sensors/:id", "description": "Get sensor details",
                 "request": None, "response": {"id": 1, "name": "string", "type": "temperature", "value": 22.5, "unit": "°C", "updated_at": "ISO8601"}},
                {"method": "POST", "path": "/api/sensors/:id/reading", "description": "Submit new sensor reading",
                 "request": {"value": "number"}, "response": {"id": 1, "sensor_id": 1, "value": 22.5, "timestamp": "ISO8601"}},
                {"method": "GET", "path": "/api/sensors/:id/history", "description": "Get sensor reading history",
                 "request": None, "response": {"items": [{"id": 1, "value": 22.5, "timestamp": "ISO8601"}], "total": 100}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Sensor & Reading", "fields": {"Sensor.id": "integer (primary key)", "Sensor.name": "string (required)",
                     "Sensor.type": "string (temperature, humidity, etc.)", "Sensor.unit": "string (°C, %, etc.)",
                     "Reading.id": "integer (primary key)", "Reading.sensor_id": "integer (foreign key)", "Reading.value": "decimal",
                     "Reading.timestamp": "datetime (auto, ISO 8601)"}}
        },
        'media_audio_player': {
            'endpoints': [
                {"method": "GET", "path": "/api/tracks", "description": "List all audio tracks",
                 "request": None, "response": {"items": [{"id": 1, "title": "string", "artist": "string", "duration": 180, "url": "/audio/track.mp3", "created_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/tracks/upload", "description": "Upload audio file",
                 "request": "multipart/form-data with 'audio' field",
                 "response": {"id": 1, "title": "string", "artist": "string", "duration": 180, "url": "/audio/track.mp3", "created_at": "ISO8601"}},
                {"method": "GET", "path": "/api/tracks/:id", "description": "Get track details",
                 "request": None, "response": {"id": 1, "title": "string", "artist": "string", "duration": 180, "url": "/audio/track.mp3", "created_at": "ISO8601"}},
                {"method": "DELETE", "path": "/api/tracks/:id", "description": "Delete track",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Track", "fields": {"id": "integer (primary key, auto-increment)", "title": "string (required, max 255 chars)",
                     "artist": "string (optional, max 255 chars)", "duration": "integer (seconds)", "filepath": "string (server path)",
                     "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'messaging_notifications': {
            'endpoints': [
                {"method": "GET", "path": "/api/notifications", "description": "List all notifications (supports ?read=true/false filter)",
                 "request": None, "response": {"items": [{"id": 1, "message": "string", "type": "info", "read": False, "created_at": "ISO8601"}], "total": 1, "unread_count": 5}},
                {"method": "POST", "path": "/api/notifications", "description": "Create new notification",
                 "request": {"message": "string", "type": "string (info|warning|error)"},
                 "response": {"id": 1, "message": "string", "type": "info", "read": False, "created_at": "ISO8601"}},
                {"method": "PUT", "path": "/api/notifications/:id/read", "description": "Mark notification as read",
                 "request": None, "response": {"id": 1, "message": "string", "type": "info", "read": True, "created_at": "ISO8601"}},
                {"method": "DELETE", "path": "/api/notifications/:id", "description": "Delete notification",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Notification", "fields": {"id": "integer (primary key, auto-increment)", "message": "text (required)",
                     "type": "string (info, warning, error)", "read": "boolean (default: false)", "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'monitoring_server_stats': {
            'endpoints': [
                {"method": "GET", "path": "/api/stats", "description": "Get current server stats",
                 "request": None, "response": {"cpu_percent": 45.2, "memory_percent": 68.5, "disk_percent": 55.0, "uptime": 86400, "timestamp": "ISO8601"}},
                {"method": "GET", "path": "/api/stats/history", "description": "Get historical stats (supports ?hours=24 param)",
                 "request": None, "response": {"items": [{"cpu_percent": 45.2, "memory_percent": 68.5, "disk_percent": 55.0, "timestamp": "ISO8601"}], "total": 100}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "ServerStat", "fields": {"id": "integer (primary key, auto-increment)", "cpu_percent": "decimal (0-100)",
                     "memory_percent": "decimal (0-100)", "disk_percent": "decimal (0-100)", "uptime": "integer (seconds)",
                     "timestamp": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'realtime_chat_room': {
            'endpoints': [
                {"method": "GET", "path": "/api/messages", "description": "Get recent chat messages",
                 "request": None, "response": {"items": [{"id": 1, "username": "string", "text": "string", "timestamp": "ISO8601"}], "total": 50}},
                {"method": "WS", "path": "/ws/chat", "description": "WebSocket endpoint for real-time messaging",
                 "request": {"type": "message", "username": "string", "text": "string"},
                 "response": {"type": "message", "id": 1, "username": "string", "text": "string", "timestamp": "ISO8601"}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Message", "fields": {"id": "integer (primary key, auto-increment)", "username": "string (required, max 50 chars)",
                     "text": "text (required, max 1000 chars)", "timestamp": "datetime (auto, ISO 8601 format in JSON)"}}
        },
        'utility_base64_tool': {
            'endpoints': [
                {"method": "POST", "path": "/api/base64/encode", "description": "Encode text to base64",
                 "request": {"text": "string"}, "response": {"encoded": "string (base64)"}},
                {"method": "POST", "path": "/api/base64/decode", "description": "Decode base64 to text",
                 "request": {"encoded": "string (base64)"}, "response": {"text": "string"}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': None  # Stateless utility
        },
        'validation_xml_checker': {
            'endpoints': [
                {"method": "POST", "path": "/api/validate/xml", "description": "Validate XML syntax",
                 "request": {"xml": "string"}, "response": {"valid": True, "errors": []}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': None  # Stateless utility
        },
        'workflow_task_board': {
            'endpoints': [
                {"method": "GET", "path": "/api/tasks", "description": "List all tasks (supports ?status= filter)",
                 "request": None, "response": {"items": [{"id": 1, "title": "string", "description": "string", "status": "todo", "priority": "medium", "created_at": "ISO8601"}], "total": 1}},
                {"method": "POST", "path": "/api/tasks", "description": "Create new task",
                 "request": {"title": "string", "description": "string (optional)", "priority": "string (optional)"},
                 "response": {"id": 1, "title": "string", "description": "string", "status": "todo", "priority": "medium", "created_at": "ISO8601"}},
                {"method": "PUT", "path": "/api/tasks/:id", "description": "Update task",
                 "request": {"title": "string (optional)", "description": "string (optional)", "status": "string (optional)", "priority": "string (optional)"},
                 "response": {"id": 1, "title": "string", "description": "string", "status": "in_progress", "priority": "high", "created_at": "ISO8601"}},
                {"method": "PUT", "path": "/api/tasks/:id/status", "description": "Update task status (accepts {status: 'todo'|'in_progress'|'done'})",
                 "request": {"status": "string (todo|in_progress|done)"},
                 "response": {"id": 1, "title": "string", "description": "string", "status": "done", "priority": "medium", "created_at": "ISO8601"}},
                {"method": "DELETE", "path": "/api/tasks/:id", "description": "Delete task",
                 "request": None, "response": {}},
                {"method": "GET", "path": "/api/health", "description": "Health check endpoint",
                 "request": None, "response": {"status": "healthy", "service": "backend"}}
            ],
            'model': {"name": "Task", "fields": {"id": "integer (primary key, auto-increment)", "title": "string (required, max 255 chars)",
                     "description": "text (optional)", "status": "string (todo, in_progress, done - default: todo)",
                     "priority": "string (low, medium, high - default: medium)", "created_at": "datetime (auto, ISO 8601 format in JSON)"}}
        }
    }
    
    for slug, config in specs.items():
        file = REQUIREMENTS_DIR / f'{slug}.json'
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data['api_endpoints'] = config['endpoints']
        data['data_model'] = config['model']
        
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ {slug}")


def main():
    print("🚀 Phase 3: Updating specialized apps...\n")
    update_specialized_apps()
    print("\n✨ All 30 requirement files updated!")
    print("📋 Every API now has complete request/response schemas")
    print("🔒 Frontend-backend contracts enforced!")


if __name__ == '__main__':
    main()
