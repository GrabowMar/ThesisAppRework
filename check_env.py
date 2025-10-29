"""
Quick diagnostic to check if ORCHESTRATOR_USE_CONTAINER_TOOLS is set
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Load .env like Flask does
from dotenv import load_dotenv
load_dotenv()

print("=" * 80)
print("ENVIRONMENT VARIABLE DIAGNOSTIC")
print("=" * 80)
print()
print(f"ORCHESTRATOR_USE_CONTAINER_TOOLS = '{os.environ.get('ORCHESTRATOR_USE_CONTAINER_TOOLS', 'NOT_SET')}'")
print()

# Test the actual check that find_executable uses
from app.engines.base import find_executable

print("Testing find_executable with bandit:")
result = find_executable('bandit')
print(f"  Result: {result}")
print()

if 'containerized' in str(result):
    print("[SUCCESS] Container tools are being recognized!")
else:
    print("[FAILURE] Container tools are NOT being recognized")
    print("  This means ORCHESTRATOR_USE_CONTAINER_TOOLS is not set correctly")
