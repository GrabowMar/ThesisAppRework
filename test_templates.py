"""Quick test of the templates API endpoint."""
import requests

TOKEN = "9242rD8R3F-dAfeQGKe_4EBJQiqIjNRi0pcxRAQKq9b9xAzM_ZCM1gK4vNuAH7UP"

print("Testing /api/gen/templates endpoint...\n")

try:
    response = requests.get(
        "http://127.0.0.1:5000/api/gen/templates",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        templates = data.get("data", [])
        
        print(f"✓ Successfully loaded {len(templates)} templates\n")
        print("First 5 templates:")
        print("-" * 80)
        
        for t in templates[:5]:
            slug = t.get("slug", "N/A")
            category = t.get("category", "N/A")
            name = t.get("name", "N/A")
            backend_reqs = len(t.get("backend_requirements", []))
            frontend_reqs = len(t.get("frontend_requirements", []))
            
            print(f"  • {slug:35} [{category:20}]")
            print(f"    {name}")
            print(f"    Backend: {backend_reqs} items, Frontend: {frontend_reqs} items")
            print()
        
        print("\nTemplate slugs (all 30):")
        print("-" * 80)
        for i, t in enumerate(templates, 1):
            print(f"{i:2}. {t['slug']}")
            
    else:
        print(f"✗ Error: {response.status_code}")
        print(response.text)
        
except requests.exceptions.ConnectionError:
    print("✗ Error: Could not connect to Flask server")
    print("   Make sure Flask is running on port 5000")
except Exception as e:
    print(f"✗ Error: {e}")
