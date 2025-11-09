"""Debug script to understand the model lookup issue."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import os
os.environ.setdefault('DATABASE_URL', 'sqlite:///test.db')
os.environ.setdefault('SECRET_KEY', 'test-key')

from app import create_app
from app.models import ModelCapability

app = create_app()

print("Test 1: Direct query with app context")
with app.app_context():
    m = ModelCapability.query.filter_by(canonical_slug='openai_codex-mini').first()
    print(f"  Result: {m.canonical_slug if m else 'NOT FOUND'}")

print("\nTest 2: Inside async function with asyncio.run")
import asyncio

async def test_async_query():
    m = ModelCapability.query.filter_by(canonical_slug='openai_codex-mini').first()
    return m

with app.app_context():
    result = asyncio.run(test_async_query())
    print(f"  Result: {result.canonical_slug if result else 'NOT FOUND'}")

print("\nTest 3: Inside async function with manual event loop")
async def test_async_query2():
    m = ModelCapability.query.filter_by(canonical_slug='openai_codex-mini').first()
    return m

with app.app_context():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(test_async_query2())
        print(f"  Result: {result.canonical_slug if result else 'NOT FOUND'}")
    finally:
        loop.close()
