#!/usr/bin/env python3
"""
End-to-End Test: Report Modal Data Flow
========================================

Tests the complete data flow from database to modal rendering.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_modal_endpoint():
    """Test the /reports/new endpoint that serves the modal."""
    from app.factory import create_app
    
    app = create_app()
    
    with app.app_context():
        # Import after app context is created
        from app.routes.jinja.reports import new_report
        from flask import Flask
        
        # Call the view function directly
        with app.test_request_context():
            response = new_report()
            
            print("=" * 60)
            print("MODAL ENDPOINT TEST")
            print("=" * 60)
            
            # Check if response contains models data
            if isinstance(response, str):
                html = response
                
                # Check for key indicators
                has_models = 'modelsCache' in html
                has_apps = 'appsCache' in html
                has_no_models_msg = 'No models available' in html
                
                print(f"\n✅ Modal HTML generated")
                print(f"   Contains modelsCache: {has_models}")
                print(f"   Contains appsCache: {has_apps}")
                print(f"   Shows 'No models available': {has_no_models_msg}")
                
                if has_models and has_apps and not has_no_models_msg:
                    print("\n🎉 SUCCESS: Modal should display models correctly!")
                    
                    # Extract model count from JavaScript
                    import re
                    models_match = re.search(r'const modelsCache = (\[.*?\]);', html, re.DOTALL)
                    if models_match:
                        import json
                        try:
                            models_data = json.loads(models_match.group(1))
                            print(f"\n📊 Models in modal: {len(models_data)}")
                            for model in models_data:
                                print(f"   • {model.get('provider')} / {model.get('model_name')}")
                        except:
                            pass
                else:
                    print("\n❌ ISSUE: Modal may not display correctly")
                    if has_no_models_msg:
                        print("   'No models available' message is present!")
            else:
                print(f"\n⚠️  Unexpected response type: {type(response)}")
            
            print("\n" + "=" * 60)

if __name__ == '__main__':
    test_modal_endpoint()
