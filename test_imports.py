#!/usr/bin/env python3
"""
Test script to verify web_routes imports
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from web_routes import main_bp, register_blueprints
    print("✅ Successfully imported main_bp and register_blueprints")
    print(f"main_bp: {main_bp}")
    print(f"register_blueprints: {register_blueprints}")
except ImportError as e:
    print(f"❌ Import error: {e}")
    
    # Try importing the module directly
    try:
        import web_routes
        print(f"✅ Successfully imported web_routes module: {web_routes}")
        print(f"Available attributes: {dir(web_routes)}")
    except ImportError as e2:
        print(f"❌ Cannot import web_routes module: {e2}")
