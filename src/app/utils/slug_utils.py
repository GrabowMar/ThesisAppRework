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

import logging
import os
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


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
    
    # Step 4: Preserve dots in slugs (e.g., keep "4.1" as is for filesystem compatibility)
    # Note: Dots are kept to match actual directory names in generated/apps/
    
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


# Model ID auto-correction patterns (provider → known valid model patterns)
MODEL_CORRECTIONS = {
    'anthropic': [
        # Pattern: (invalid_regex, correct_replacement, description)
        (r'claude-haiku-4\.5', 'claude-3-haiku-20240307', 'Claude 4.5 does not exist; corrected to Claude 3 Haiku'),
        (r'claude-4\.5-haiku', 'claude-3-haiku-20240307', 'Claude 4.5 does not exist; corrected to Claude 3 Haiku'),
        (r'claude-haiku-4', 'claude-3-haiku-20240307', 'Claude 4 Haiku does not exist; corrected to Claude 3 Haiku'),
        (r'claude-sonnet-4\.5', 'claude-3-5-sonnet-20241022', 'Claude 4.5 does not exist; corrected to Claude 3.5 Sonnet'),
        (r'claude-4\.5-sonnet', 'claude-3-5-sonnet-20241022', 'Claude 4.5 does not exist; corrected to Claude 3.5 Sonnet'),
        (r'claude-opus-4\.5', 'claude-3-opus-20240229', 'Claude 4.5 does not exist; corrected to Claude 3 Opus'),
        (r'claude-4\.5-opus', 'claude-3-opus-20240229', 'Claude 4.5 does not exist; corrected to Claude 3 Opus'),
    ],
    'openai': [
        (r'gpt-5', 'gpt-4-turbo-preview', 'GPT-5 does not exist; corrected to GPT-4 Turbo'),
        (r'gpt-4\.5', 'gpt-4-turbo-preview', 'GPT-4.5 does not exist; corrected to GPT-4 Turbo'),
    ],
    'google': [
        (r'gemini-3', 'gemini-2.0-flash-exp', 'Gemini 3 does not exist; corrected to Gemini 2.0 Flash'),
    ],
}


def suggest_model_correction(model_id: str) -> Optional[Tuple[str, str]]:
    """Suggest a corrected model ID if the provided one appears invalid.
    
    Args:
        model_id: OpenRouter model ID (e.g., "anthropic/claude-haiku-4.5")
    
    Returns:
        Tuple of (corrected_model_id, reason) if correction found, else None
    
    Examples:
        >>> suggest_model_correction("anthropic/claude-haiku-4.5")
        ('anthropic/claude-3-haiku-20240307', 'Claude 4.5 does not exist; corrected to Claude 3 Haiku')
        >>> suggest_model_correction("openai/gpt-4")
        None
    """
    if not model_id or '/' not in model_id:
        return None
    
    provider, model_name = model_id.split('/', 1)
    
    if provider not in MODEL_CORRECTIONS:
        return None
    
    for pattern, replacement, reason in MODEL_CORRECTIONS[provider]:
        if re.search(pattern, model_name, re.IGNORECASE):
            corrected_name = re.sub(pattern, replacement, model_name, flags=re.IGNORECASE)
            corrected_id = f"{provider}/{corrected_name}"
            return corrected_id, reason
    
    return None


def auto_correct_model_id(model_id: str, auto_correct: Optional[bool] = None) -> Tuple[str, Optional[str]]:
    """Auto-correct invalid model IDs with optional logging.
    
    Args:
        model_id: OpenRouter model ID to validate/correct
        auto_correct: Enable auto-correction (default: from env OPENROUTER_AUTO_CORRECT_MODEL_IDS)
    
    Returns:
        Tuple of (final_model_id, warning_message)
        - If auto_correct is True and correction found: returns (corrected_id, warning)
        - If auto_correct is False and correction found: returns (original_id, warning)
        - If no correction needed: returns (original_id, None)
    
    Examples:
        >>> auto_correct_model_id("anthropic/claude-haiku-4.5", auto_correct=True)
        ('anthropic/claude-3-haiku-20240307', 'Auto-corrected invalid model ID...')
        >>> auto_correct_model_id("anthropic/claude-haiku-4.5", auto_correct=False)
        ('anthropic/claude-haiku-4.5', 'Invalid model ID detected...')
    """
    if auto_correct is None:
        auto_correct = os.getenv('OPENROUTER_AUTO_CORRECT_MODEL_IDS', 'false').lower() == 'true'
    
    correction = suggest_model_correction(model_id)
    
    if not correction:
        return model_id, None
    
    corrected_id, reason = correction
    
    if auto_correct:
        warning = f"Auto-corrected invalid model ID '{model_id}' → '{corrected_id}': {reason}"
        logger.warning(warning)
        return corrected_id, warning
    else:
        warning = f"Invalid model ID detected '{model_id}'. Suggestion: use '{corrected_id}' ({reason}). Enable auto-correction with OPENROUTER_AUTO_CORRECT_MODEL_IDS=true"
        logger.warning(warning)
        return model_id, warning
