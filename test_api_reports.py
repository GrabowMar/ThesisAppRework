#!/usr/bin/env python3
"""Test report generation via API endpoint"""
import requests
import json

# Start Flask app first if not running
# Then test the endpoint

API_URL = "http://localhost:5000/api/reports/generate"

def test_api_generation():
    """Test report generation via API"""
    
    payload = {
        "report_type": "model_analysis",
        "format": "html",
        "config": {
            "model_slug": "openai_gpt-4.1-2025-04-14"
        },
        "title": "API Test Report"
    }
    
    print(f"Testing POST {API_URL}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        # Note: This requires authentication token
        # For now, just test structure
        response = requests.post(API_URL, json=payload)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Success!")
            print(f"Report ID: {data.get('report_id')}")
            print(f"File: {data.get('file_path')}")
        else:
            print(f"\n⚠️ Status {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Flask app not running. Start with: python src/main.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == '__main__':
    test_api_generation()
