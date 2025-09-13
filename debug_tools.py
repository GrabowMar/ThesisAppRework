#!/usr/bin/env python3

from src.main import create_app
from app.services.tool_registry_service import ToolRegistryService

app = create_app()
with app.app_context():
    svc = ToolRegistryService()
    
    # Get all tools to see their IDs and service names
    tools = svc.get_all_tools()
    print("All available tools:")
    for tool in tools:
        print(f"ID: {tool.get('id')}, Name: {tool.get('name')}, Service: {tool.get('service_name')}")
    
    print("\n" + "="*50)
    print("Bandit and ZAP tools specifically:")
    for tool in tools:
        if 'bandit' in tool.get('name', '').lower() or 'zap' in tool.get('name', '').lower():
            print(f"ID: {tool.get('id')}, Name: {tool.get('name')}, Service: {tool.get('service_name')}")