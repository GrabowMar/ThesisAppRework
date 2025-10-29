"""
Quick verification script to test container tool availability
"""
import os
import sys

# Set the environment variable
os.environ['ORCHESTRATOR_USE_CONTAINER_TOOLS'] = '1'

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.engines.unified_registry import get_unified_tool_registry
from app.engines.base import find_executable

def main():
    print("=" * 80)
    print("CONTAINER TOOL AVAILABILITY TEST")
    print("=" * 80)
    print(f"\nORCHESTRATOR_USE_CONTAINER_TOOLS = {os.environ.get('ORCHESTRATOR_USE_CONTAINER_TOOLS')}")
    print()
    
    # Test individual tool lookups
    tools_to_check = ['bandit', 'safety', 'pylint', 'eslint', 'flake8']
    
    print("Testing find_executable() with container tools enabled:")
    print("-" * 80)
    for tool in tools_to_check:
        result = find_executable(tool)
        status = "✅ AVAILABLE" if result else "❌ NOT FOUND"
        print(f"{tool:20s} {status:20s} {result or '(not in PATH)'}")
    
    print()
    print("=" * 80)
    print("UNIFIED REGISTRY REPORT")
    print("=" * 80)
    
    # Get registry
    registry = get_unified_tool_registry()
    
    # Get detailed tool info
    tools = registry.list_tools_detailed()
    
    print(f"\nTotal tools registered: {len(tools)}")
    print()
    
    # Filter to container tools
    container_tools = [t for t in tools if t.get('container') != 'local']
    print(f"Container-based tools: {len(container_tools)}")
    print()
    
    # Show static-analyzer tools
    static_tools = [t for t in tools if t.get('container') == 'static-analyzer']
    print(f"Static analyzer tools ({len(static_tools)}):")
    print("-" * 80)
    for tool in static_tools:
        name = tool.get('name', 'unknown')
        available = tool.get('available', False)
        tags = ', '.join(tool.get('tags', []))
        status = "✅" if available else "❌"
        print(f"  {status} {name:20s} | tags: {tags}")
    
    print()
    print("=" * 80)
    print("VERDICT")
    print("=" * 80)
    
    bandit_available = any(t['name'] == 'bandit' and t.get('available') for t in tools)
    safety_available = any(t['name'] == 'safety' and t.get('available') for t in tools)
    pylint_available = any(t['name'] == 'pylint' and t.get('available') for t in tools)
    
    if bandit_available and safety_available and pylint_available:
        print("✅ SUCCESS: Critical tools (bandit, safety, pylint) are now AVAILABLE!")
        print("   The system is ready to execute containerized analysis.")
        return 0
    else:
        print("❌ FAILURE: Some critical tools are still not available:")
        if not bandit_available:
            print("   - bandit: NOT AVAILABLE")
        if not safety_available:
            print("   - safety: NOT AVAILABLE")
        if not pylint_available:
            print("   - pylint: NOT AVAILABLE")
        print("\n   Check that analyzer containers are running:")
        print("   python analyzer/analyzer_manager.py status")
        return 1

if __name__ == '__main__':
    sys.exit(main())
