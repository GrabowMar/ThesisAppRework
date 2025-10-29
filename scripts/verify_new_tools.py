#!/usr/bin/env python3
"""
Verification script for newly registered AI analyzer tools.
Confirms requirements-checker and code-quality-analyzer are properly registered.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.engines.container_tool_registry import ContainerToolRegistry

def verify_tools():
    """Verify new AI analyzer tools are registered correctly."""
    print("\n" + "="*70)
    print("🔍 AI Analyzer Tool Registry Verification")
    print("="*70 + "\n")
    
    # Initialize registry
    registry = ContainerToolRegistry()
    registry.initialize()
    
    # Get all AI analyzer tools
    all_tools = registry.get_all_tools()
    ai_tools = [t for t in all_tools.values() if t.container.value == 'ai-analyzer']
    
    print(f"✅ Found {len(ai_tools)} AI analyzer tools total\n")
    
    # Focus on new tools
    new_tool_names = ['requirements-checker', 'code-quality-analyzer']
    new_tools = {name: all_tools.get(name) for name in new_tool_names}
    
    # Verify each new tool
    for tool_name, tool in new_tools.items():
        print(f"{'='*70}")
        if tool is None:
            print(f"❌ MISSING: {tool_name}")
            print(f"   Tool not found in registry!")
            continue
            
        print(f"✅ FOUND: {tool_name}")
        print(f"   Display Name: {tool.display_name}")
        print(f"   Available: {'YES ✓' if tool.available else 'NO ✗'}")
        print(f"   Container: {tool.container.value}")
        print(f"   Tags: {', '.join(tool.tags)}")
        print(f"   Languages: {', '.join(tool.supported_languages)}")
        
        # Check for gemini_model parameter
        if tool.config_schema:
            model_param = next((p for p in tool.config_schema.parameters if p.name == 'gemini_model'), None)
            if model_param:
                print(f"   Default Model: {model_param.default}")
                print(f"   Model Options: {', '.join(model_param.options)}")
            else:
                print(f"   ⚠️  No gemini_model parameter found!")
            
            print(f"   Total Parameters: {len(tool.config_schema.parameters)}")
            print(f"   Examples: {len(tool.config_schema.examples)} preset(s)")
        else:
            print(f"   ⚠️  No config schema defined!")
        print()
    
    # Check environment
    print(f"{'='*70}")
    print("🔑 Environment Check:")
    has_key = bool(os.getenv('OPENROUTER_API_KEY'))
    print(f"   OPENROUTER_API_KEY: {'SET ✓' if has_key else 'NOT SET ✗'}")
    if not has_key:
        print(f"   ⚠️  Tools will show as unavailable without API key")
    print()
    
    # Summary
    print(f"{'='*70}")
    found_count = sum(1 for t in new_tools.values() if t is not None)
    print(f"\n📊 Summary: {found_count}/{len(new_tool_names)} new tools registered")
    
    if found_count == len(new_tool_names):
        print("✅ All new tools successfully registered!")
    else:
        print("❌ Some tools missing - check registration code")
    print()

if __name__ == '__main__':
    verify_tools()
