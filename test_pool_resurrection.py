
import os
import asyncio
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add src to path
sys.path.insert(0, str(Path(r"c:\Users\grabowmar\Desktop\ThesisAppRework\src")))

from app.services.analyzer_pool import AnalyzerPool, LoadBalancingStrategy, AnalyzerEndpoint

# Configure logging to see what's happening
logging.basicConfig(level=logging.DEBUG)

async def test_resurrection():
    print("Testing AnalyzerPool Resurrection Logic...")
    
    # Mock environment for multiple replicas
    os.environ['STATIC_ANALYZER_URLS'] = "ws://sa1:2001,ws://sa2:2001"
    
    pool = AnalyzerPool()
    await pool.initialize()
    
    endpoints = pool.endpoints['static-analyzer']
    e1 = endpoints[0] # sa1
    e2 = endpoints[1] # sa2
    
    print(f"Initial State: E1={e1.is_healthy}, E2={e2.is_healthy}")
    
    # Simulate E1 failing
    e1.is_healthy = False
    e1.last_health_check = datetime.now() - timedelta(seconds=61) # Past cooldown (60s default)
    
    # Simulate E2 failing recently
    e2.is_healthy = False
    e2.last_health_check = datetime.now() # Recent failure
    
    print(f"Simulated Failure: E1(stale)={e1.is_healthy}, E2(recent)={e2.is_healthy}")

    # Mock _check_endpoint_health to return True (success)
    # We want to see if select_best_endpoint CALLS it for E1
    with patch.object(pool, '_check_endpoint_health', new_callable=AsyncMock) as mock_check:
        mock_check.return_value = True # Resurrection successful
        
        # This call should trigger a health check for E1 because it is stale
        selected = await pool.select_best_endpoint('static-analyzer')
        
        print(f"Selected: {selected.url if selected else 'None'}")
        
        # Verification
        if selected and selected.url == e1.url:
             print("SUCCESS: Stale endpoint E1 was selected (resurrected)")
        else:
             print(f"FAIL: Expected E1, got {selected.url if selected else 'None'}")

        if mock_check.call_count > 0:
             print(f"SUCCESS: Health check was called {mock_check.call_count} times")
        else:
             print("FAIL: Health check was NOT called")

    # Now verify E2 is NOT checked if it's recent failure
    e1.is_healthy = False # Reset
    e1.last_health_check = datetime.now() # Recent
    
    with patch.object(pool, '_check_endpoint_health', new_callable=AsyncMock) as mock_check:
        mock_check.return_value = True 
        
        selected = await pool.select_best_endpoint('static-analyzer')
        
        if selected is None:
            print("SUCCESS: No endpoints selected (all recent failures)")
        else:
            print(f"FAIL: Should have returned None, got {selected.url}")
            
if __name__ == "__main__":
    asyncio.run(test_resurrection())
