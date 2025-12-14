"""
Script to add admin_requirements and admin_api_endpoints to all requirements JSON files
that don't already have them.
"""
import json
import os
from pathlib import Path

REQUIREMENTS_DIR = Path(__file__).parent.parent / "misc" / "requirements"

# Generic admin requirements that apply to most apps
GENERIC_ADMIN_REQUIREMENTS = [
    "1. Admin dashboard showing key statistics (total count, active count, etc.)",
    "2. Table listing ALL items including inactive/deleted with status badges",
    "3. Toggle button to activate/deactivate items",
    "4. Checkbox selection for bulk operations (delete, status change)",
    "5. Search and filter functionality"
]

# Generic admin API endpoints
def get_generic_admin_endpoints(main_entity="items"):
    return [
        {
            "method": "GET",
            "path": f"/api/admin/{main_entity}",
            "description": f"List ALL {main_entity} including inactive",
            "request": None,
            "response": {"items": [], "total": 0}
        },
        {
            "method": "POST",
            "path": f"/api/admin/{main_entity}/:id/toggle",
            "description": f"Toggle {main_entity[:-1] if main_entity.endswith('s') else main_entity} active status",
            "request": None,
            "response": {"id": 1, "is_active": True}
        },
        {
            "method": "POST",
            "path": f"/api/admin/{main_entity}/bulk-delete",
            "description": f"Delete multiple {main_entity}",
            "request": {"ids": [1, 2, 3]},
            "response": {"deleted": 3}
        },
        {
            "method": "GET",
            "path": "/api/admin/stats",
            "description": "Get dashboard statistics",
            "request": None,
            "response": {"total": 0, "active": 0, "inactive": 0}
        }
    ]

# Entity name mappings for different app types
ENTITY_MAPPINGS = {
    "api_url_shortener": "urls",
    "api_weather_display": "locations",
    "booking_reservations": "reservations",
    "collaboration_simple_poll": "polls",
    "content_recipe_list": "recipes",
    "crm_customer_list": "customers",
    "crud_book_library": "books",
    "dataviz_sales_table": "sales",
    "education_quiz_app": "quizzes",
    "fileproc_image_upload": "files",
    "finance_expense_list": "expenses",
    "gaming_leaderboard": "scores",
    "geolocation_store_list": "stores",
    "healthcare_appointments": "appointments",
    "inventory_stock_list": "items",
    "iot_sensor_display": "sensors",
    "learning_flashcards": "cards",
    "media_audio_player": "tracks",
    "messaging_notifications": "notifications",
    "monitoring_server_stats": "servers",
    "productivity_notes": "notes",
    "realtime_chat_room": "messages",
    "scheduling_event_list": "events",
    "social_blog_posts": "posts",
    "utility_base64_tool": "conversions",
    "validation_xml_checker": "validations",
    "workflow_task_board": "tasks"
}

def update_requirements_file(filepath: Path):
    """Add admin sections to a requirements file if missing."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Skip if already has admin sections
    if "admin_requirements" in data and "admin_api_endpoints" in data:
        print(f"Skipping {filepath.name} - already has admin sections")
        return False
    
    slug = data.get("slug", filepath.stem)
    entity = ENTITY_MAPPINGS.get(slug, "items")
    
    # Add admin_requirements if missing
    if "admin_requirements" not in data:
        data["admin_requirements"] = GENERIC_ADMIN_REQUIREMENTS
    
    # Add admin_api_endpoints if missing
    if "admin_api_endpoints" not in data:
        data["admin_api_endpoints"] = get_generic_admin_endpoints(entity)
    
    # Add is_active to data_model if it exists
    if "data_model" in data and data["data_model"] and "fields" in data["data_model"]:
        fields = data["data_model"]["fields"]
        if fields:
            # Find the main entity field pattern
            has_is_active = any("is_active" in k.lower() for k in fields.keys())
            if not has_is_active:
                # Add is_active field
                first_key = list(fields.keys())[0]
                main_entity = first_key.split('.')[0] if '.' in first_key else ""
                if main_entity:
                    data["data_model"]["fields"][f"{main_entity}.is_active"] = "boolean (default: true, for soft delete)"
                else:
                    data["data_model"]["fields"]["is_active"] = "boolean (default: true, for soft delete)"
    
    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Updated {filepath.name}")
    return True

def main():
    updated = 0
    for filepath in REQUIREMENTS_DIR.glob("*.json"):
        if update_requirements_file(filepath):
            updated += 1
    print(f"\nUpdated {updated} files")

if __name__ == "__main__":
    main()
