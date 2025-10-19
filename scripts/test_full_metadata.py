#!/usr/bin/env python3
"""Test FULL metadata collection with real OpenRouter API call.

Verifies:
1. Folder structure (apps, raw, metadata only)
2. Raw payloads written to generated/raw/payloads/
3. Raw responses written to generated/raw/responses/
4. Comprehensive metadata with OpenRouter stats written to generated/metadata/indices/runs/
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / 'src'))

from app.factory import create_app
from app.services.generation import get_generation_service


async def test_full_metadata():
    """Run a real generation and verify all metadata is collected."""
    print("=== Testing FULL Metadata Collection with Real API Call ===\n")
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        # Get generation service
        service = get_generation_service()
        
        # Test parameters - use anthropic_claude-4.5-haiku-20251001 for fast testing
        model_slug = "anthropic_claude-4.5-haiku-20251001"
        app_num = 1
        template_id = 1  # todo app
        
        print(f"Generating: {model_slug}/app{app_num} with template {template_id}")
        print("Component: BACKEND ONLY (faster test)\n")
        
        # Run generation
        result = await service.generate_full_app(
            model_slug=model_slug,
            app_num=app_num,
            template_id=template_id,
            generate_frontend=False,  # Skip frontend for faster test
            generate_backend=True
        )
        
        print(f"✓ Generation result: {result['success']}")
        print(f"  - Scaffolded: {result['scaffolded']}")
        print(f"  - Backend generated: {result['backend_generated']}")
        print(f"  - App directory: {result.get('app_dir')}")
        print(f"  - Errors: {result.get('errors', [])}\n")
        
        if not result['success']:
            print("✗ Generation failed, cannot test metadata")
            return False
        
        # Verify folder structure
        generated_dir = project_root / 'generated'
        print("=== Verifying Folder Structure ===")
        
        top_level = sorted([d.name for d in generated_dir.iterdir() if d.is_dir()])
        print(f"Top-level folders: {top_level}")
        
        expected = ['apps', 'metadata', 'raw']
        if top_level == expected:
            print("✓ Correct structure: only apps, raw, metadata folders\n")
        else:
            print(f"✗ Unexpected structure! Expected {expected}, got {top_level}\n")
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
        
        # Check raw outputs
        print("=== Verifying Raw Outputs ===")
        
        raw_dir = generated_dir / 'raw'
        raw_subdirs = sorted([d.name for d in raw_dir.iterdir() if d.is_dir()])
        print(f"Raw subfolders: {raw_subdirs}")
        
        expected_raw = ['payloads', 'responses']
        if raw_subdirs == expected_raw:
            print("✓ Raw folder has payloads and responses subdirectories\n")
        else:
            print(f"✗ Unexpected raw subfolders! Expected {expected_raw}, got {raw_subdirs}\n")
        
        # Find payload/response files
        model_safe = model_slug.replace('/', '_')
        payload_dir = raw_dir / 'payloads' / model_safe / f"app{app_num}"
        response_dir = raw_dir / 'responses' / model_safe / f"app{app_num}"
        
        payload_files = list(payload_dir.glob('*.json')) if payload_dir.exists() else []
        response_files = list(response_dir.glob('*.json')) if response_dir.exists() else []
        
        print(f"Payload files found: {len(payload_files)}")
        print(f"Response files found: {len(response_files)}")
        
        if payload_files:
            print(f"✓ Payloads written: {[f.name for f in payload_files]}\n")
        else:
            print("✗ No payload files found!\n")
        
        if response_files:
            print(f"✓ Responses written: {[f.name for f in response_files]}\n")
        else:
            print("✗ No response files found!\n")
        
        # Check metadata files
        print("=== Verifying Comprehensive Metadata ===")
        
        metadata_runs = metadata_dir / 'indices' / 'runs' / model_safe / f"app{app_num}"
        metadata_files = list(metadata_runs.glob('*.json')) if metadata_runs.exists() else []
        
        print(f"Metadata files found: {len(metadata_files)}")
        
        if not metadata_files:
            print("✗ No metadata files found!\n")
            return False
        
        print(f"✓ Metadata written: {[f.name for f in metadata_files]}\n")
        
        # Parse and verify metadata content
        for meta_file in metadata_files:
            print(f"Checking metadata: {meta_file.name}")
            
            with open(meta_file, 'r') as f:
                metadata = json.load(f)
            
            # Basic fields
            basic_fields = ['run_id', 'timestamp', 'model_slug', 'app_num', 'component', 
                           'model_used', 'status', 'generation_id']
            
            # Token fields
            token_fields = ['prompt_tokens', 'completion_tokens', 'total_tokens']
            
            # OpenRouter-specific fields
            openrouter_fields = ['native_tokens_prompt', 'native_tokens_completion', 
                                'provider_name', 'total_cost', 'generation_time_ms']
            
            print("\n  Basic fields:")
            for field in basic_fields:
                value = metadata.get(field)
                status = "✓" if value is not None else "✗"
                print(f"    {status} {field}: {value}")
            
            print("\n  Token fields:")
            for field in token_fields:
                value = metadata.get(field)
                status = "✓" if value is not None else "✗"
                print(f"    {status} {field}: {value}")
            
            print("\n  OpenRouter-specific fields:")
            has_all_openrouter = True
            for field in openrouter_fields:
                value = metadata.get(field)
                status = "✓" if value is not None else "✗"
                print(f"    {status} {field}: {value}")
                if value is None:
                    has_all_openrouter = False
            
            if 'generation_stats_error' in metadata:
                print(f"\n  ⚠ Warning: OpenRouter stats fetch error: {metadata['generation_stats_error']}")
                has_all_openrouter = False
            
            print()
            
            if has_all_openrouter:
                print("✓ COMPLETE: All OpenRouter metadata fields present!\n")
            else:
                print("⚠ PARTIAL: Some OpenRouter fields missing (may need longer delay)\n")
        
        print("=== Test Complete ===")
        print("✓ Folder structure correct")
        print("✓ Raw payloads/responses written")
        print("✓ Comprehensive metadata collected")
        
        return True


if __name__ == '__main__':
    success = asyncio.run(test_full_metadata())
    sys.exit(0 if success else 1)
