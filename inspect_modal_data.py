#!/usr/bin/env python3
"""
Detailed Modal Data Inspection
===============================

Extracts and displays the exact data being passed to the modal.
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent / 'src'))

def inspect_modal_data():
    """Extract and display modal data."""
    from app.factory import create_app
    
    app = create_app()
    
    with app.app_context():
        from app.routes.jinja.reports import new_report
        import re
        
        with app.test_request_context():
            response = new_report()
            html = str(response)
            
            print("=" * 60)
            print("MODAL DATA INSPECTION")
            print("=" * 60)
            
            # Extract modelsCache
            models_match = re.search(r'const modelsCache = (\[.*?\]);', html, re.DOTALL)
            if models_match:
                try:
                    models_json = models_match.group(1)
                    models_data = json.loads(models_json)
                    
                    print(f"\n📊 modelsCache array length: {len(models_data)}")
                    
                    if len(models_data) == 0:
                        print("   ❌ Array is EMPTY - modal will show 'No models available'")
                    else:
                        print(f"   ✅ Array contains {len(models_data)} models")
                        print("\n   Models data:")
                        for i, model in enumerate(models_data, 1):
                            print(f"\n   {i}. {model.get('provider')} / {model.get('model_name')}")
                            print(f"      canonical_slug: {model.get('canonical_slug')}")
                            print(f"      model_id: {model.get('model_id')}")
                except json.JSONDecodeError as e:
                    print(f"   ❌ Failed to parse JSON: {e}")
                    print(f"   Raw JSON: {models_json[:200]}...")
            else:
                print("   ❌ Could not find modelsCache in HTML")
            
            # Extract appsCache
            apps_match = re.search(r'const appsCache = (\{.*?\});', html, re.DOTALL)
            if apps_match:
                try:
                    apps_json = apps_match.group(1)
                    apps_data = json.loads(apps_json)
                    
                    print(f"\n📋 appsCache object keys: {len(apps_data)}")
                    
                    if len(apps_data) == 0:
                        print("   ❌ Object is EMPTY")
                    else:
                        print(f"   ✅ Object contains {len(apps_data)} model slugs")
                        print("\n   Apps by model:")
                        for slug, app_numbers in sorted(apps_data.items()):
                            print(f"      {slug}: {app_numbers}")
                except json.JSONDecodeError as e:
                    print(f"   ❌ Failed to parse JSON: {e}")
            else:
                print("   ❌ Could not find appsCache in HTML")
            
            # Check JavaScript logic
            has_check = 'if (!Array.isArray(modelsCache) || modelsCache.length === 0)' in html
            print(f"\n🔍 JavaScript validation present: {has_check}")
            
            print("\n" + "=" * 60)

if __name__ == '__main__':
    inspect_modal_data()
