#!/usr/bin/env python3
"""Test the /reports/new endpoint to verify models appear"""
import os
import sys
import re

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
from app.models import User
from flask_login import login_user

def test_modal_endpoint():
    """Test that /reports/new returns models"""
    app = create_app()
    
    with app.app_context():
        # Get or create a test user
        user = User.query.filter_by(username='admin').first()
        if not user:
            print("⚠️ No admin user found - creating test data might fail")
            print("   Run: python scripts/create_admin.py")
            return
        
        # Create test client
        client = app.test_client()
        
        # Log in the user
        with client:
            # Simulate login by posting to login endpoint
            login_response = client.post('/auth/login', data={
                'username': 'admin',
                'password': 'admin'  # Default admin password
            }, follow_redirects=False)
            
            if login_response.status_code not in (200, 302):
                print(f"⚠️ Login failed with status {login_response.status_code}")
                print("   Trying direct session approach...")
            
            # Request the modal endpoint
            response = client.get('/reports/new')
        
        print("=" * 70)
        print("MODAL ENDPOINT TEST")
        print("=" * 70)
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.content_type}")
        
        if response.status_code == 200:
            html = response.data.decode('utf-8')
            
            # Check if modelsCache is populated
            models_match = re.search(r'const modelsCache = (\[.*?\]);', html, re.DOTALL)
            
            if models_match:
                models_json = models_match.group(1)
                print(f"\n✅ modelsCache found in response")
                print(f"   Length: {len(models_json)} characters")
                
                # Check if it's empty array
                if models_json.strip() == '[]':
                    print("   ⚠️ WARNING: modelsCache is empty array []")
                else:
                    # Count how many models
                    model_count = models_json.count('"canonical_slug"')
                    print(f"   📊 Contains {model_count} models")
                    
                    # Show snippet
                    snippet = models_json[:200] + '...' if len(models_json) > 200 else models_json
                    print(f"   Preview: {snippet}")
            else:
                print("\n❌ modelsCache NOT found in response")
            
            # Check for "No models available" text
            if 'No models available' in html:
                print("\n⚠️ Found 'No models available' in HTML")
            else:
                print("\n✅ 'No models available' NOT in HTML (good)")
                
        elif response.status_code == 302:
            print(f"\n⚠️ Redirect to: {response.location}")
            print("   Authentication issue - make sure admin user exists")
        else:
            print(f"\n❌ Failed with status {response.status_code}")
            print(response.data.decode('utf-8')[:500])

if __name__ == '__main__':
    test_modal_endpoint()
