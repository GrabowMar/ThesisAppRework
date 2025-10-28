"""Unified Model Slug Normalization Utilities
===========================================

Centralizes all model slug normalization logic to ensure consistent behavior
across the entire application (Flask backend, analyzer services, scripts).

CONVENTION: All model slugs in filesystems and databases use underscore format:
  - provider_model-name (e.g., "anthropic_claude-3-5-sonnet")
  - Slashes from API formats (e.g., "anthropic/claude-3.5-sonnet") converted to underscores
  - Spaces converted to underscores
  - Hyphens in model names preserved (e.g., "gpt-4", "claude-3-5")
  - Lowercase preferred for consistency
"""

import re
from typing import List


def normalize_model_slug(raw_slug: str) -> str:
    """Normalize a model slug to the canonical filesystem format.
    
    Args:
        raw_slug: Raw model slug in any format (slash, underscore, mixed)
    
    Returns:
        Normalized slug in provider_model-name format
    
    Examples:
        >>> normalize_model_slug("anthropic/claude-3.5-sonnet")
        'anthropic_claude-3-5-sonnet'
        >>> normalize_model_slug("openai/gpt-4")
        'openai_gpt-4'
        >>> normalize_model_slug("google/gemini 2.0 flash")
        'google_gemini-2-0-flash'
    """
    if not raw_slug or not isinstance(raw_slug, str):
        return ""
    
    # Step 1: Basic cleanup
    slug = raw_slug.strip().lower()
    
    # Step 2: Convert slashes to underscores (API format → filesystem format)
    slug = slug.replace('/', '_')
    
    # Step 3: Convert spaces to hyphens (for readability in model names)
    slug = slug.replace(' ', '-')
    
    # Step 4: Normalize dots to hyphens (e.g., "3.5" → "3-5")
    slug = slug.replace('.', '-')
    
    # Step 5: Collapse multiple consecutive hyphens/underscores
    slug = re.sub(r'-+', '-', slug)
    slug = re.sub(r'_+', '_', slug)
    
    # Step 6: Strip leading/trailing separators
    slug = slug.strip('-_')
    
    return slug


def slug_to_api_format(filesystem_slug: str) -> str:
    """Convert filesystem slug back to API format (provider/model-name).
    
    Args:
        filesystem_slug: Normalized slug in provider_model-name format
    
    Returns:
        API format with slash separator
    
    Examples:
        >>> slug_to_api_format("anthropic_claude-3-5-sonnet")
        'anthropic/claude-3-5-sonnet'
        >>> slug_to_api_format("openai_gpt-4")
        'openai/gpt-4'
    """
    if not filesystem_slug or '_' not in filesystem_slug:
        return filesystem_slug
    
    # Split on first underscore only (provider_model-name)
    parts = filesystem_slug.split('_', 1)
    return f"{parts[0]}/{parts[1]}"


def generate_slug_variants(model_slug: str) -> List[str]:
    """Generate common slug variations for lookup/matching.
    
    Args:
        model_slug: Model slug in any format
    
    Returns:
        List of variant slugs including:
        - Normalized form (canonical)
        - Original form
        - Separator variations (underscore ↔ hyphen)
        - API format (slash)
    
    Examples:
        >>> generate_slug_variants("anthropic_claude-3-5-sonnet")
        ['anthropic_claude-3-5-sonnet', 'anthropic-claude-3-5-sonnet', 
         'anthropic/claude-3-5-sonnet', ...]
    """
    if not model_slug:
        return []
    
    normalized = normalize_model_slug(model_slug)
    api_format = slug_to_api_format(normalized)
    
    variants = [
        normalized,  # Canonical form
        model_slug,  # Original as-provided
        api_format,  # API format with slash
        normalized.replace('_', '-'),  # All hyphens
        normalized.replace('-', '_'),  # All underscores (except provider separator)
    ]
    
    # Deduplicate while preserving order
    seen = set()
    unique_variants = []
    for variant in variants:
        if variant and variant not in seen:
            seen.add(variant)
            unique_variants.append(variant)
    
    return unique_variants


def validate_model_slug_format(model_slug: str) -> bool:
    """Validate that a model slug follows expected format.
    
    Args:
        model_slug: Slug to validate
    
    Returns:
        True if slug is valid (provider_model-name format)
    
    Examples:
        >>> validate_model_slug_format("anthropic_claude-3-5-sonnet")
        True
        >>> validate_model_slug_format("invalid")
        False
        >>> validate_model_slug_format("openai_gpt-4")
        True
    """
    if not model_slug or not isinstance(model_slug, str):
        return False
    
    # Must contain exactly one underscore separator (provider_model)
    if model_slug.count('_') < 1:
        return False
    
    # Split and validate parts
    parts = model_slug.split('_', 1)
    provider = parts[0]
    model_name = parts[1] if len(parts) > 1 else ""
    
    # Both parts must be non-empty
    if not provider or not model_name:
        return False
    
    # Must not contain invalid filesystem characters
    invalid_chars = r'[<>:"/\\|?*\s]'
    if re.search(invalid_chars, model_slug):
        return False
    
    return True
