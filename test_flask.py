#!/usr/bin/env python3
"""
Test script for Flask application
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app

def test_health_endpoint():
    """Test the health endpoint using Flask test client."""
    print("Creating Flask application...")
    app = create_app()
    print("App created successfully")

    print("Testing health endpoint...")
    with app.test_client() as client:
        response = client.get('/health')
        print(f"Status: {response.status_code}")
        print(f"Response: {response.get_json()}")

    print("Testing main route...")
    with app.test_client() as client:
        response = client.get('/')
        print(f"Status: {response.status_code}")
        print(f"Response length: {len(response.get_data())}")

if __name__ == '__main__':
    test_health_endpoint()