import asyncio
import json
import sys
import os

# Ensure app is in path
sys.path.insert(0, '/app')

from app.services.analyzer_pool import get_analyzer_pool

async def run():
    print("Initializing pool...")
    pool = await get_analyzer_pool()
    stats = pool.get_pool_stats()
    
    static_eps = stats.get('static-analyzer', {}).get('endpoints', [])
    print(f"Found {len(static_eps)} endpoints for static-analyzer")
    
    for ep in static_eps:
        print(f"- {ep['url']} (Healthy: {ep['healthy']})")

if __name__ == '__main__':
    asyncio.run(run())
