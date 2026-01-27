
import os
import asyncio
import sys
from pathlib import Path

# Mock environment
os.environ['STATIC_ANALYZER_URLS'] = "ws://static-analyzer:2001,ws://static-analyzer-2:2001,ws://static-analyzer-3:2001"
# Add src to path
sys.path.insert(0, str(Path(r"c:\Users\grabowmar\Desktop\ThesisAppRework\src")))

from app.services.analyzer_pool import AnalyzerPool, LoadBalancingStrategy

async def test_pool():
    print("Testing AnalyzerPool logic...")
    pool = AnalyzerPool()
    
    # Force load from env
    pool._load_endpoints_from_env()
    
    endpoints = pool.endpoints.get('static-analyzer', [])
    print(f"Loaded {len(endpoints)} endpoints for static-analyzer")
    for e in endpoints:
        print(f" - {e.url}")
        
    if len(endpoints) != 3:
        print("FAIL: Expected 3 endpoints")
        return

    # Simulate selection
    print("\nSimulating selection (LEAST_LOADED):")
    counts = {}
    for i in range(100):
        e = pool._select_endpoint('static-analyzer')
        if e:
            counts[e.url] = counts.get(e.url, 0) + 1
            
    print("Selection counts (should be roughly even):")
    for url, count in counts.items():
        print(f" - {url}: {count}")
        
    # Simulate single endpoint behavior (what user reports)
    print("\nSimulating what happens if we only find one:")
    os.environ['STATIC_ANALYZER_URLS'] = ""
    os.environ['STATIC_ANALYZER_URL'] = "ws://static-analyzer:2001"
    
    pool2 = AnalyzerPool()
    pool2._load_endpoints_from_env()
    endpoints2 = pool2.endpoints.get('static-analyzer', [])
    print(f"Loaded {len(endpoints2)} endpoints for static-analyzer (single mode)")
    for e in endpoints2:
        print(f" - {e.url}")

if __name__ == "__main__":
    asyncio.run(test_pool())
