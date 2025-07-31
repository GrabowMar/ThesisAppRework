"""
Test NPX tool availability directly
"""
import subprocess
import sys
from pathlib import Path

def test_npx_tools():
    """Test NPX tool availability."""
    tools = ["eslint", "prettier", "jshint", "retire", "snyk"]
    
    print("🔧 Testing NPX Tool Availability")
    print("=" * 40)
    
    # Test NPX itself
    try:
        result = subprocess.run(["npx", "--version"], capture_output=True, timeout=5, check=False, shell=True)
        print(f"NPX available: {result.returncode == 0} (version: {result.stdout.decode().strip()})")
    except Exception as e:
        print(f"NPX test failed: {e}")
        return
    
    # Test each tool
    for tool in tools:
        try:
            result = subprocess.run(
                ["npx", tool, "--version"],
                capture_output=True, timeout=10, check=False, shell=True
            )
            status = "✅" if result.returncode == 0 else "❌"
            output = result.stdout.decode().strip() or result.stderr.decode().strip()
            print(f"{status} {tool}: {output[:50]}")
        except Exception as e:
            print(f"❌ {tool}: Error - {e}")
    
    # Test NPM audit specifically
    print("\n📦 Testing NPM:")
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, timeout=5, check=False, shell=True)
        print(f"✅ npm: {result.stdout.decode().strip()}")
    except Exception as e:
        print(f"❌ npm: {e}")

if __name__ == "__main__":
    test_npx_tools()
