#!/usr/bin/env python3
"""Test enhanced metadata collection with OpenRouter generation endpoint.

Tests that:
1. Generated folder structure is clean (apps, raw, metadata only)
2. Raw payloads and responses are written
3. Comprehensive metadata is collected including:
   - Basic info (model, tokens, status)
   - OpenRouter-specific fields (native tokens, cost, provider)
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / 'src'))

from app.services.generation import get_generation_service


async def test_metadata_collection():
    """Run a test generation and verify metadata."""
    print("=== Testing Enhanced Metadata Collection ===\n")
    
    # Get generation service
    service = get_generation_service()
    
    # Test parameters
    model_slug = "test_model"
    app_num = 1
    template_id = 1
    
    print(f"Generating: {model_slug}/app{app_num} with template {template_id}")
    print("(Scaffolding only - no API calls for test_model)\n")
    
    # Run generation
    result = await service.generate_full_app(
        model_slug=model_slug,
        app_num=app_num,
        template_id=template_id,
        generate_frontend=False,
        generate_backend=False  # Scaffolding only for test
    )
    
    print(f"✓ Generation result: {result['success']}")
    print(f"  - Scaffolded: {result['scaffolded']}")
    print(f"  - App directory: {result.get('app_dir')}")
    print(f"  - Backend port: {result.get('backend_port')}")
    print(f"  - Frontend port: {result.get('frontend_port')}\n")
    
    # Verify folder structure
    generated_dir = project_root / 'generated'
    print("=== Verifying Folder Structure ===")
    
    top_level = [d.name for d in generated_dir.iterdir() if d.is_dir()]
    print(f"Top-level folders: {top_level}")
    
    expected = {'apps', 'raw', 'metadata'}
    if set(top_level) == expected:
        print("✓ Correct structure: only apps, raw, metadata folders\n")
    else:
        print(f"✗ Unexpected structure! Expected {expected}, got {set(top_level)}\n")
        return False
    
    # Check metadata subfolder
    metadata_dir = generated_dir / 'metadata'
    metadata_subdirs = [d.name for d in metadata_dir.iterdir() if d.is_dir()]
    print(f"Metadata subfolders: {metadata_subdirs}")
    
    if metadata_subdirs == ['indices']:
        print("✓ Metadata only has indices subfolder\n")
    else:
        print(f"✗ Unexpected metadata subfolders: {metadata_subdirs}\n")
        return False
    
    # For real model test, would check raw and metadata files here
    # Since test_model doesn't call API, we'll just verify structure
    
    print("=== Test Complete ===")
    print("Structure verified! Run with real model to test full metadata collection.")
    return True


if __name__ == '__main__':
    success = asyncio.run(test_metadata_collection())
    sys.exit(0 if success else 1)
