"""
Model ID Validator Service
==========================

Universal model ID validation against OpenRouter's live catalog.
Replaces pattern-matching with authoritative source validation.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class ModelValidator:
    """Validates model IDs against OpenRouter's live model catalog."""
    
    # Provider namespace mappings (organization names → OpenRouter provider names)
    PROVIDER_NAMESPACE_MAP = {
        'deepseek-ai': 'deepseek',
        'MiniMaxAI': 'minimax',
        'LiquidAI': 'liquid',
        'Alibaba-NLP': 'alibaba',
        'ai21labs': 'ai21',
        'ByteDance-Seed': 'bytedance',
        'CohereForAI': 'cohere',
        'meituan-longcat': 'meituan',
        'zai-org': 'zhipu',  # GLM models are under zhipu in OpenRouter
        'z-ai': 'zhipu',
    }
    
    def __init__(self):
        self._catalog_cache: Optional[Dict[str, Dict]] = None
        self._catalog_by_canonical: Optional[Dict[str, Dict]] = None
        
    def _fetch_openrouter_catalog(self) -> Optional[List[Dict]]:
        """Fetch live model catalog from OpenRouter API.
        
        Uses synchronous requests library to avoid async event loop conflicts
        when called from Celery workers or other async contexts.
        """
        try:
            import requests
            
            api_key = os.getenv('OPENROUTER_API_KEY')
            if not api_key:
                logger.warning("OPENROUTER_API_KEY not set, cannot validate model IDs")
                return None
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'HTTP-Referer': 'https://github.com/yourusername/yourrepo',
                'X-Title': 'ThesisAppRework'
            }
            
            response = requests.get(
                'https://openrouter.ai/api/v1/models',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            else:
                logger.error(f"OpenRouter API returned {response.status_code}")
                return None
            
        except Exception as e:
            logger.error(f"Failed to fetch OpenRouter catalog: {e}", exc_info=True)
            return None
    
    def refresh_catalog(self, force: bool = False) -> bool:
        """Refresh the model catalog cache.
        
        Args:
            force: Force refresh even if cache exists
            
        Returns:
            True if catalog was refreshed successfully
        """
        if not force and self._catalog_cache is not None:
            return True
        
        models = self._fetch_openrouter_catalog()
        if not models:
            return False
        
        # Build lookup dictionaries (normalized to lowercase for case-insensitive matching)
        by_id = {}
        by_canonical = {}
        
        for model in models:
            model_id = model.get('id')
            canonical_slug = model.get('canonical_slug')
            
            if model_id:
                # Store with lowercase key but preserve original ID in model data
                by_id[model_id.lower()] = model
            if canonical_slug:
                by_canonical[canonical_slug.lower()] = model
        
        self._catalog_cache = by_id
        self._catalog_by_canonical = by_canonical
        
        logger.info(f"Refreshed OpenRouter catalog: {len(by_id)} models (case-insensitive)")
        return True
    
    def normalize_provider_namespace(self, model_id: str) -> str:
        """Normalize provider namespace in model ID.
        
        Converts organization names to OpenRouter provider names:
        - deepseek-ai/DeepSeek-R1 → deepseek/deepseek-r1
        - MiniMaxAI/MiniMax-Text-01 → minimax/minimax-text-01
        - LiquidAI/LFM2-8B-A1B → liquid/lfm2-8b-a1b
        
        Args:
            model_id: Model ID that may have organization namespace
            
        Returns:
            Normalized model ID with correct provider namespace
        """
        if '/' not in model_id:
            return model_id
        
        provider, model_name = model_id.split('/', 1)
        
        # Check if provider needs normalization
        normalized_provider = self.PROVIDER_NAMESPACE_MAP.get(provider, provider)
        
        # Return with normalized provider and lowercase
        return f"{normalized_provider}/{model_name}".lower()
    
    def is_valid_model_id(self, model_id: str) -> bool:
        """Check if a model ID exists in OpenRouter catalog (case-insensitive).
        
        Automatically normalizes provider namespaces before validation.
        
        Args:
            model_id: OpenRouter model ID (e.g., "anthropic/claude-haiku-4.5")
            
        Returns:
            True if model ID exists in catalog, or True if catalog unavailable (fail-open)
        """
        if not self.refresh_catalog():
            logger.warning("Cannot validate without catalog; assuming valid (fail-open)")
            return True  # Fail-open: allow generation to proceed if catalog unavailable
        
        # Normalize provider namespace and convert to lowercase
        normalized_id = self.normalize_provider_namespace(model_id)
        assert self._catalog_cache is not None  # guarded by refresh_catalog()
        return normalized_id in self._catalog_cache
    
    def find_closest_match(self, invalid_id: str, provider: Optional[str] = None) -> Optional[Tuple[str, float, str]]:
        """Find closest matching model ID in catalog (case-insensitive).
        
        Args:
            invalid_id: Invalid model ID to match
            provider: Optional provider filter (e.g., "anthropic")
            
        Returns:
            Tuple of (model_id, similarity_score, description) or None
        """
        if not self.refresh_catalog():
            return None
        
        # Normalize input for comparison
        invalid_lower = invalid_id.lower()
        
        assert self._catalog_cache is not None  # guarded by refresh_catalog()
        
        # Filter by provider if specified
        candidates = list(self._catalog_cache.keys())
        if provider:
            provider_lower = provider.lower()
            candidates = [m for m in candidates if m.startswith(f"{provider_lower}/")]
        
        if not candidates:
            return None
        
        # Find best match using sequence similarity (already lowercase)
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            score = SequenceMatcher(None, invalid_lower, candidate).ratio()
            if score > best_score:
                best_score = score
                best_match = candidate
        
        if best_match and best_score > 0.6:  # Require 60% similarity
            model_data = self._catalog_cache[best_match]
            # Get the canonical model ID from the model data (not the lowercased key)
            canonical_id = model_data.get('id', best_match)
            description = f"Closest match: {model_data.get('name', canonical_id)} (similarity: {best_score:.1%})"
            return (canonical_id, best_score, description)
        
        return None
    
    def suggest_correction(self, model_id: str) -> Optional[Tuple[str, str]]:
        """Suggest correction for invalid model ID.
        
        Tries multiple strategies:
        1. Provider namespace normalization (deepseek-ai → deepseek)
        2. Case normalization (DeepSeek-R1 → deepseek-r1)
        3. Fuzzy matching for closest model
        
        Args:
            model_id: Model ID to validate/correct
            
        Returns:
            Tuple of (corrected_id, reason) or None if valid
        """
        if self.is_valid_model_id(model_id):
            return None  # Already valid
        
        # Check if catalog is available
        if not self._catalog_cache:
            logger.warning("Cannot suggest correction without catalog")
            return None
        
        # Strategy 1: Try provider namespace normalization
        normalized_id = self.normalize_provider_namespace(model_id)
        if normalized_id != model_id.lower() and normalized_id in self._catalog_cache:
            return (self._catalog_cache[normalized_id].get('id', normalized_id), 
                    "Provider namespace normalized")
        
        # Strategy 2: Extract provider and try fuzzy matching
        provider = None
        if '/' in model_id:
            provider = model_id.split('/')[0]
            # Also try normalized provider for fuzzy matching
            normalized_provider = self.PROVIDER_NAMESPACE_MAP.get(provider, provider)
            provider = normalized_provider
        
        match = self.find_closest_match(model_id, provider)
        if match:
            corrected_id, score, description = match
            return (corrected_id, description)
        
        return None
    
    def get_model_info(self, model_id: str) -> Optional[Dict]:
        """Get full model information from catalog (case-insensitive).
        
        Args:
            model_id: OpenRouter model ID
            
        Returns:
            Model data dictionary or None
        """
        if not self.refresh_catalog():
            return None
        
        assert self._catalog_cache is not None  # guarded by refresh_catalog()
        # Normalize to lowercase for lookup
        return self._catalog_cache.get(model_id.lower())
    
    def validate_all_database_models(self, app_context=None) -> Dict[str, Any]:
        """Validate all models in database against OpenRouter catalog.
        
        Args:
            app_context: Flask app context (required for database access)
            
        Returns:
            Dict with 'valid', 'invalid', and 'suggestions' lists
        """
        if not self.refresh_catalog():
            return {'error': 'Failed to fetch OpenRouter catalog'}
        
        if app_context is None:
            return {'error': 'app_context is required for database access'}
        
        assert self._catalog_cache is not None  # guarded by refresh_catalog()
        assert app_context is not None  # type narrowing for with statement
        
        with app_context:
            from app.models import ModelCapability
            
            valid_models = []
            invalid_models = []
            suggestions = []
            
            all_models = ModelCapability.query.all()
            
            for model in all_models:
                # Priority: hugging_face_id > base_model_id > model_id
                openrouter_id = model.hugging_face_id or model.base_model_id or model.model_id
                
                if self.is_valid_model_id(openrouter_id):
                    valid_models.append({
                        'canonical_slug': model.canonical_slug,
                        'model_id': openrouter_id,
                        'provider': model.provider
                    })
                else:
                    invalid_entry = {
                        'canonical_slug': model.canonical_slug,
                        'model_id': openrouter_id,
                        'provider': model.provider
                    }
                    invalid_models.append(invalid_entry)
                    
                    # Try to find correction
                    correction = self.suggest_correction(openrouter_id)
                    if correction:
                        corrected_id, reason = correction
                        suggestions.append({
                            **invalid_entry,
                            'suggested_id': corrected_id,
                            'reason': reason
                        })
            
            return {
                'valid': valid_models,
                'invalid': invalid_models,
                'suggestions': suggestions,
                'summary': {
                    'total': len(all_models),
                    'valid': len(valid_models),
                    'invalid': len(invalid_models),
                    'fixable': len(suggestions)
                }
            }


# Singleton instance
_validator_instance = None


def get_validator() -> ModelValidator:
    """Get singleton validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ModelValidator()
    return _validator_instance
