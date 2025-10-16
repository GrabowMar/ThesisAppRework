"""
OpenRouter Service
==================

Service for fetching comprehensive model information from OpenRouter API.
Provides detailed model capabilities, pricing, and metadata with database caching.
"""

import logging
import os
import requests
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from flask import Flask

logger = logging.getLogger(__name__)
# Module-level guard to emit the missing-API-key message only once per process
_OPENROUTER_KEY_WARNED: bool = False


class OpenRouterService:
    """Service for integrating with OpenRouter API to fetch model details with caching."""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/models"
        self.site_url = os.getenv("OPENROUTER_SITE_URL", "https://thesis-app.local")
        self.site_name = os.getenv("OPENROUTER_SITE_NAME", "Thesis Research App")
        self.logger = logger
        
        # Cache configuration
        self.cache_duration_hours = int(os.getenv("OPENROUTER_CACHE_HOURS", "1"))  # Default 1 hour
        self.cache_enabled = os.getenv("OPENROUTER_CACHE_ENABLED", "true").lower() == "true"
        
        # In-memory cache for session-level caching
        self._memory_cache = {}
        self._memory_cache_expiry = None
        
        # Warn once per process about missing API key to reduce log spam
        global _OPENROUTER_KEY_WARNED
        if not self.api_key and not _OPENROUTER_KEY_WARNED:
            # Lower severity to INFO to keep logs cleaner
            self.logger.info("OpenRouter API key not found. Set OPENROUTER_API_KEY in .env file")
            _OPENROUTER_KEY_WARNED = True
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers for OpenRouter API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
            "Content-Type": "application/json"
        }
    
    def _is_memory_cache_valid(self) -> bool:
        """Check if in-memory cache is valid."""
        if not self._memory_cache or not self._memory_cache_expiry:
            return False
        return datetime.now(timezone.utc) < self._memory_cache_expiry
    
    def _update_memory_cache(self, models: List[Dict[str, Any]]) -> None:
        """Update in-memory cache with fresh data."""
        self._memory_cache = {model.get('id', ''): model for model in models if model.get('id')}
        self._memory_cache_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)  # 5-minute memory cache
    
    def _fetch_from_api(self) -> List[Dict[str, Any]]:
        """Fetch models directly from OpenRouter API."""
        if not self.api_key:
            self.logger.error("Cannot fetch models: OpenRouter API key not configured")
            return []
        
        try:
            self.logger.info("Fetching all models from OpenRouter API...")
            start_time = time.time()
            
            response = requests.get(
                self.api_url,
                headers=self.get_headers(),
                timeout=30
            )
            
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                self.logger.info(f"Successfully fetched {len(models)} models from OpenRouter in {duration:.2f}s")
                
                # Update in-memory cache
                self._update_memory_cache(models)
                
                # Update database cache if enabled
                if self.cache_enabled:
                    self._update_database_cache(models, duration, response.status_code)
                
                return models
            else:
                self.logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return []
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error fetching OpenRouter models: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching OpenRouter models: {e}")
            return []
    
    def _update_database_cache(self, models: List[Dict[str, Any]], fetch_duration: float, status_code: int) -> None:
        """Update database cache with fetched models."""
        try:
            from ..models import OpenRouterModelCache, db
            from ..models import utc_now
            
            # Calculate expiry time
            expiry_time = utc_now() + timedelta(hours=self.cache_duration_hours)
            
            # Batch update cache entries
            for model in models:
                model_id = model.get('id')
                if not model_id:
                    continue
                
                # Check if cache entry exists
                cache_entry = OpenRouterModelCache.query.filter_by(model_id=model_id).first()
                
                if cache_entry:
                    # Update existing entry
                    cache_entry.set_model_data(model)
                    cache_entry.cache_expires_at = expiry_time
                    cache_entry.fetch_duration = fetch_duration
                    cache_entry.api_response_status = status_code
                    cache_entry.updated_at = utc_now()
                else:
                    # Create new entry (set attributes explicitly to satisfy type checkers)
                    cache_entry = OpenRouterModelCache()
                    cache_entry.model_id = model_id
                    cache_entry.cache_expires_at = expiry_time
                    cache_entry.fetch_duration = fetch_duration
                    cache_entry.api_response_status = status_code
                    cache_entry.set_model_data(model)
                    db.session.add(cache_entry)
            
            # Commit all changes
            db.session.commit()
            self.logger.info(f"Updated cache for {len(models)} models with {self.cache_duration_hours}h expiry")
            
        except Exception as e:
            self.logger.error(f"Error updating database cache: {e}")
            # Rollback on error
            try:
                from ..models import db
                db.session.rollback()
            except Exception:
                pass
    
    def _get_from_database_cache(self) -> List[Dict[str, Any]]:
        """Get models from database cache if valid."""
        if not self.cache_enabled:
            return []
        
        try:
            from ..models import OpenRouterModelCache, utc_now
            
            # Get non-expired cache entries
            valid_entries = OpenRouterModelCache.query.filter(
                OpenRouterModelCache.cache_expires_at > utc_now()
            ).all()
            
            if not valid_entries:
                self.logger.debug("No valid cache entries found")
                return []
            
            # Extract model data and update access time
            models = []
            for entry in valid_entries:
                entry.mark_accessed()
                model_data = entry.get_model_data()
                if model_data:
                    models.append(model_data)
            
            # Commit access time updates
            from ..models import db
            db.session.commit()
            
            if models:
                self.logger.info(f"Retrieved {len(models)} models from database cache")
                # Also update memory cache
                self._update_memory_cache(models)
            
            return models
            
        except Exception as e:
            self.logger.error(f"Error reading from database cache: {e}")
            return []
    
    def fetch_all_models(self) -> List[Dict[str, Any]]:
        """
        Fetch all available models from cache or OpenRouter API.
        
        Returns:
            List of model dictionaries with comprehensive information
        """
        # First check in-memory cache
        if self._is_memory_cache_valid():
            models = list(self._memory_cache.values())
            self.logger.debug(f"Retrieved {len(models)} models from memory cache")
            return models
        
        # Then check database cache
        if self.cache_enabled:
            cached_models = self._get_from_database_cache()
            if cached_models:
                return cached_models
        
        # Finally fetch from API
        return self._fetch_from_api()
    
    def fetch_model_by_id(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information for a specific model.
        
        Args:
            model_id: The OpenRouter model ID (e.g., "anthropic/claude-3-sonnet")
            
        Returns:
            Dict with model information or None if not found
        """
        # Check memory cache first
        if self._is_memory_cache_valid() and model_id in self._memory_cache:
            self.logger.debug(f"Retrieved model {model_id} from memory cache")
            return self._memory_cache[model_id]
        
        # Check database cache for specific model
        if self.cache_enabled:
            try:
                from ..models import OpenRouterModelCache
                
                cache_entry = OpenRouterModelCache.query.filter_by(model_id=model_id).first()
                if cache_entry and not cache_entry.is_expired():
                    cache_entry.mark_accessed()
                    from ..models import db
                    db.session.commit()
                    
                    model_data = cache_entry.get_model_data()
                    if model_data:
                        self.logger.debug(f"Retrieved model {model_id} from database cache")
                        return model_data
            except Exception as e:
                self.logger.error(f"Error reading specific model from cache: {e}")
        
        # Fall back to fetching all models and finding the specific one
        models = self.fetch_all_models()
        for model in models:
            if model.get("id") == model_id:
                return model
        return None
    
    def enrich_model_data(self, db_model) -> Dict[str, Any]:
        """
        Enrich database model data with OpenRouter API information.
        
        Args:
            db_model: ModelCapability database instance
            
        Returns:
            Enhanced model data dictionary
        """
        base_data = {
            'id': db_model.id,
            'model_id': db_model.model_id,
            'canonical_slug': db_model.canonical_slug,
            'provider': db_model.provider,
            'model_name': db_model.model_name,
            'is_free': db_model.is_free,
            'context_window': db_model.context_window,
            'max_output_tokens': db_model.max_output_tokens,
            'supports_function_calling': db_model.supports_function_calling,
            'supports_vision': db_model.supports_vision,
            'supports_streaming': db_model.supports_streaming,
            'supports_json_mode': db_model.supports_json_mode,
            # Back-compat flags expected by some templates
            'supports_tool_calling': getattr(db_model, 'supports_function_calling', False),
            'supports_json': getattr(db_model, 'supports_json_mode', False),
            'input_price_per_token': db_model.input_price_per_token,
            'output_price_per_token': db_model.output_price_per_token,
            'cost_efficiency': db_model.cost_efficiency,
            'safety_score': db_model.safety_score,
            'created_at': db_model.created_at,
            'updated_at': db_model.updated_at
        }
        
        # Try to find matching OpenRouter model
        # Convert canonical_slug to OpenRouter format (provider/model-name)
        if '_' in db_model.canonical_slug:
            provider, model_part = db_model.canonical_slug.split('_', 1)
            openrouter_id = f"{provider}/{model_part}"

            api_model = self.fetch_model_by_id(openrouter_id)
            if api_model:
                # include extracted details and full raw object for templates expecting nested data
                base_data.update(self._extract_openrouter_details(api_model))
                base_data['openrouter_data'] = api_model
                base_data['openrouter_model_id'] = openrouter_id
            else:
                # Try without conversion
                api_model = self.fetch_model_by_id(db_model.model_id)
                if api_model:
                    base_data.update(self._extract_openrouter_details(api_model))
                    base_data['openrouter_data'] = api_model
                    base_data['openrouter_model_id'] = db_model.model_id
        
        return base_data
    
    def _extract_openrouter_details(self, api_model: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format OpenRouter model details."""
        details = {}
        
        # Basic identifiers
        if api_model.get("name"):
            details["openrouter_name"] = api_model.get("name")
        if api_model.get("canonical_slug"):
            details["openrouter_canonical_slug"] = api_model.get("canonical_slug")

        # Pricing information
        pricing = api_model.get("pricing", {})
        if pricing:
            details.update({
                'openrouter_prompt_price': pricing.get("prompt"),
                'openrouter_completion_price': pricing.get("completion"),
                'openrouter_pricing_request': pricing.get("request"),
                'openrouter_pricing_image': pricing.get("image"),
                'openrouter_pricing_web_search': pricing.get("web_search"),
                'openrouter_pricing_internal_reasoning': pricing.get("internal_reasoning"),
                'openrouter_pricing_input_cache_read': pricing.get("input_cache_read"),
                'openrouter_pricing_input_cache_write': pricing.get("input_cache_write"),
                'openrouter_is_free': (
                    float(pricing.get("prompt", "0") or "0") == 0 and 
                    float(pricing.get("completion", "0") or "0") == 0
                )
            })
        
        # Context length
        context_length = api_model.get("context_length")
        if context_length:
            details['openrouter_context_length'] = context_length
        
        # Top provider information
        top_provider = api_model.get("top_provider", {})
        if top_provider:
            details.update({
                'top_provider_max_completion_tokens': top_provider.get("max_completion_tokens"),
                'top_provider_is_moderated': top_provider.get("is_moderated"),
                'top_provider_name': top_provider.get("name"),
                'top_provider_latency_ms': top_provider.get("ttft") or top_provider.get("latency"),
                'top_provider_context_length': top_provider.get("context_length"),
            })
        
        # Architecture and capabilities
        architecture = api_model.get("architecture", {})
        if architecture:
            details.update({
                'architecture_modality': architecture.get("modality"),  # legacy single modality if present
                'architecture_input_modalities': architecture.get("input_modalities"),
                'architecture_output_modalities': architecture.get("output_modalities"),
                'architecture_tokenizer': architecture.get("tokenizer"),
                'architecture_instruct_type': architecture.get("instruct_type"),
            })
        
        # Additional metadata
        details.update({
            'openrouter_description': api_model.get("description"),
            'openrouter_created': api_model.get("created"),
            'openrouter_per_request_limits': api_model.get("per_request_limits"),
            'openrouter_supported_parameters': api_model.get("supported_parameters"),
        })

        # Variants (if provided in schema)
        variants = api_model.get("variants") or api_model.get("static_variants")
        if variants:
            try:
                # normalize to list of strings
                if isinstance(variants, dict):
                    variants = list(variants.keys())
                elif isinstance(variants, str):
                    variants = [variants]
                details['openrouter_variants'] = variants
            except Exception:
                pass
        
        return details
    
    def get_models_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all models with aggregated statistics.
        
        Returns:
            Dict with model counts, provider stats, and other aggregations
        """
        models = self.fetch_all_models()
        if not models:
            return {'error': 'Could not fetch models from OpenRouter'}
        
        # Calculate statistics
        total_models = len(models)
        providers = set()
        free_models = 0
        paid_models = 0
        modalities = set()
        
        for model in models:
            # Provider
            if '/' in model.get('id', ''):
                provider = model['id'].split('/')[0]
                providers.add(provider)
            
            # Pricing
            pricing = model.get('pricing', {})
            prompt_cost = float(pricing.get('prompt', '0') or '0')
            completion_cost = float(pricing.get('completion', '0') or '0')
            
            if prompt_cost == 0 and completion_cost == 0:
                free_models += 1
            else:
                paid_models += 1
            
            # Modalities
            arch = model.get('architecture', {})
            modality = arch.get('modality')
            if modality:
                modalities.add(modality)
        
        return {
            'total_models': total_models,
            'providers_count': len(providers),
            'providers': sorted(list(providers)),
            'free_models': free_models,
            'paid_models': paid_models,
            'modalities': sorted(list(modalities)),
            'last_updated': 'live'
        }
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the current cache state.
        
        Returns:
            Dict with cache statistics and status
        """
        cache_info = {
            'cache_enabled': self.cache_enabled,
            'cache_duration_hours': self.cache_duration_hours,
            'memory_cache_valid': self._is_memory_cache_valid(),
            'memory_cache_entries': len(self._memory_cache),
            'database_cache_entries': 0,
            'expired_cache_entries': 0,
            'api_key_configured': bool(self.api_key)
        }
        
        # Get database cache statistics
        if self.cache_enabled:
            try:
                from ..models import OpenRouterModelCache, utc_now
                
                total_entries = OpenRouterModelCache.query.count()
                expired_entries = OpenRouterModelCache.query.filter(
                    OpenRouterModelCache.cache_expires_at <= utc_now()
                ).count()
                
                cache_info.update({
                    'database_cache_entries': total_entries,
                    'expired_cache_entries': expired_entries,
                    'valid_cache_entries': total_entries - expired_entries
                })
                
            except Exception as e:
                cache_info['cache_error'] = str(e)
        
        return cache_info
    
    def clear_cache(self, include_database: bool = True) -> Dict[str, Any]:
        """
        Clear cached data.
        
        Args:
            include_database: Whether to clear database cache as well
            
        Returns:
            Dict with information about what was cleared
        """
        result = {
            'memory_cache_cleared': False,
            'database_cache_cleared': False,
            'entries_removed': 0
        }
        
        # Clear memory cache
        if self._memory_cache:
            count = len(self._memory_cache)
            self._memory_cache.clear()
            self._memory_cache_expiry = None
            result['memory_cache_cleared'] = True
            result['memory_entries_removed'] = count
        
        # Clear database cache
        if include_database and self.cache_enabled:
            try:
                from ..models import OpenRouterModelCache, db
                
                count = OpenRouterModelCache.query.count()
                OpenRouterModelCache.query.delete()
                db.session.commit()
                
                result['database_cache_cleared'] = True
                result['database_entries_removed'] = count
                result['entries_removed'] = count
                
            except Exception as e:
                result['cache_error'] = str(e)
                try:
                    from ..models import db
                    db.session.rollback()
                except Exception:
                    pass
        
        return result
