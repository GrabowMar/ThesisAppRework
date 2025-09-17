#!/usr/bin/env python3
"""Debug script to check tool registration process."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def debug_tool_registration():
    """Debug the tool registration process step by step."""
    print("=== Debug Tool Registration ===")
    
    # Step 1: Check initial registry state
    print("Step 1: Initial registry state")
    from app.engines.base import get_tool_registry
    registry = get_tool_registry()
    print(f"Initial tools: {registry.get_available_tools()}")
    
    # Step 2: Import backend security
    print("\nStep 2: Import backend_security")
    import app.engines.backend_security
    print(f"After backend_security: {registry.get_available_tools()}")
    
    # Step 3: Import frontend security
    print("\nStep 3: Import frontend_security")
    import app.engines.frontend_security
    print(f"After frontend_security: {registry.get_available_tools()}")
    
    # Step 4: Import performance
    print("\nStep 4: Import performance")
    import app.engines.performance
    print(f"After performance: {registry.get_available_tools()}")
    
    # Step 5: Get detailed info
    print("\nStep 5: Detailed tool info")
    tools_info = registry.get_all_tools_info()
    for name, info in tools_info.items():
        print(f"  {name}: {info.get('category', 'unknown')} - {info.get('description', 'No description')[:50]}...")

if __name__ == "__main__":
    debug_tool_registration()