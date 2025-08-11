"""
OpenRouter Service
==================

Service for fetching comprehensive model information from OpenRouter API.
Provides detailed model capabilities, pricing, and metadata.
"""

import logging
import os
import requests
from typing import Dict, Any, List, Optional
from flask import Flask

logger = logging.getLogger(__name__)


class OpenRouterService:
    """Service for integrating with OpenRouter API to fetch model details."""
    
    def __init__(self, app: Flask = None):
        self.app = app
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/models"
        self.site_url = os.getenv("OPENROUTER_SITE_URL", "https://thesis-app.local")
        self.site_name = os.getenv("OPENROUTER_SITE_NAME", "Thesis Research App")
        self.logger = logger
        
        if not self.api_key:
            self.logger.warning("OpenRouter API key not found. Set OPENROUTER_API_KEY in .env file")
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers for OpenRouter API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
            "Content-Type": "application/json"
        }
    
    def fetch_all_models(self) -> List[Dict[str, Any]]:
        """
        Fetch all available models from OpenRouter API.
        
        Returns:
            List of model dictionaries with comprehensive information
        """
        if not self.api_key:
            self.logger.error("Cannot fetch models: OpenRouter API key not configured")
            return []
        
        try:
            self.logger.info("Fetching all models from OpenRouter API...")
            
            response = requests.get(
                self.api_url,
                headers=self.get_headers(),
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                self.logger.info(f"Successfully fetched {len(models)} models from OpenRouter")
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
    
    def fetch_model_by_id(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information for a specific model.
        
        Args:
            model_id: The OpenRouter model ID (e.g., "anthropic/claude-3-sonnet")
            
        Returns:
            Dict with model information or None if not found
        """
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
                base_data.update(self._extract_openrouter_details(api_model))
            else:
                # Try without conversion
                api_model = self.fetch_model_by_id(db_model.model_id)
                if api_model:
                    base_data.update(self._extract_openrouter_details(api_model))
        
        return base_data
    
    def _extract_openrouter_details(self, api_model: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format OpenRouter model details."""
        details = {}
        
        # Pricing information
        pricing = api_model.get("pricing", {})
        if pricing:
            details.update({
                'openrouter_prompt_price': pricing.get("prompt"),
                'openrouter_completion_price': pricing.get("completion"),
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
            })
        
        # Architecture and capabilities
        architecture = api_model.get("architecture", {})
        if architecture:
            details.update({
                'architecture_modality': architecture.get("modality"),
                'architecture_tokenizer': architecture.get("tokenizer"),
                'architecture_instruct_type': architecture.get("instruct_type"),
            })
        
        # Additional metadata
        details.update({
            'openrouter_description': api_model.get("description"),
            'openrouter_created': api_model.get("created"),
            'openrouter_per_request_limits': api_model.get("per_request_limits"),
        })
        
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
