#!/usr/bin/env python3
"""
Debug the web UI tool selection issue.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
from app.services.service_locator import ServiceLocator

def test_tool_registry():
    app = create_app()
    
    with app.app_context():
        print('Testing tool registry service...')
        
        tool_service = ServiceLocator.get_tool_registry_service()
        if not tool_service:
            print('❌ Tool registry service not available')
            return False
        
        tools = tool_service.get_all_tools()
        perf_tools = [t for t in tools if 'performance' in str(t.get('category', '')).lower()]
        print(f'Performance tools available: {len(perf_tools)}')
        for tool in perf_tools:
            tid = tool.get('id')
            name = tool.get('name')
            enabled = tool.get('is_enabled')
            print(f'  ID: {tid}, Name: {name}, Enabled: {enabled}')
        
        # Test tool ID resolution
        print('\nTesting tool ID resolution:')
        for tool_id in [11, 12]:
            try:
                tool = tool_service.get_tool(tool_id)
                name = tool.get('name') if tool else None
                print(f'  Tool ID {tool_id} -> Name: {name}')
            except Exception as e:
                print(f'  Tool ID {tool_id} -> Error: {e}')
        
        return len(perf_tools) > 0

if __name__ == "__main__":
    success = test_tool_registry()
    print("✅ Tool registry working!" if success else "❌ Tool registry broken!")