#!/usr/bin/env python3
"""Test script for slug normalization utilities."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.utils.slug_utils import (
    normalize_model_slug,
    slug_to_api_format,
    generate_slug_variants,
    validate_model_slug_format
)

def test_normalize():
    """Test slug normalization."""
    print("\n=== Testing normalize_model_slug ===")
    tests = [
        ("anthropic/claude-3.5-sonnet", "anthropic_claude-3-5-sonnet"),
        ("openai/gpt-4", "openai_gpt-4"),
        ("google/gemini 2.0 flash", "google_gemini-2-0-flash"),
        ("openai_gpt-4", "openai_gpt-4"),  # already normalized
        ("ANTHROPIC/Claude-3.5-Sonnet", "anthropic_claude-3-5-sonnet"),  # case handling
    ]
    
    for input_slug, expected in tests:
        result = normalize_model_slug(input_slug)
        status = "✓" if result == expected else "✗"
        print(f"{status} normalize_model_slug('{input_slug}') = '{result}' (expected: '{expected}')")

def test_api_format():
    """Test conversion to API format."""
    print("\n=== Testing slug_to_api_format ===")
    tests = [
        ("anthropic_claude-3-5-sonnet", "anthropic/claude-3-5-sonnet"),
        ("openai_gpt-4", "openai/gpt-4"),
        ("google_gemini-2-0-flash", "google/gemini-2-0-flash"),
    ]
    
    for input_slug, expected in tests:
        result = slug_to_api_format(input_slug)
        status = "✓" if result == expected else "✗"
        print(f"{status} slug_to_api_format('{input_slug}') = '{result}' (expected: '{expected}')")

def test_variants():
    """Test variant generation."""
    print("\n=== Testing generate_slug_variants ===")
    slug = "anthropic_claude-3-5-sonnet"
    variants = generate_slug_variants(slug)
    print(f"Variants for '{slug}':")
    for v in variants:
        print(f"  - {v}")

def test_validation():
    """Test slug validation."""
    print("\n=== Testing validate_model_slug_format ===")
    tests = [
        ("anthropic_claude-3-5-sonnet", True),
        ("openai_gpt-4", True),
        ("invalid", False),  # no underscore
        ("_no_provider", False),  # empty provider
        ("provider_", False),  # empty model
        ("has spaces", False),  # spaces not allowed
    ]
    
    for input_slug, expected in tests:
        result = validate_model_slug_format(input_slug)
        status = "✓" if result == expected else "✗"
        print(f"{status} validate_model_slug_format('{input_slug}') = {result} (expected: {expected})")

if __name__ == "__main__":
    print("Testing Unified Slug Normalization Utilities")
    print("=" * 60)
    test_normalize()
    test_api_format()
    test_variants()
    test_validation()
    print("\n" + "=" * 60)
    print("✓ All tests completed")
