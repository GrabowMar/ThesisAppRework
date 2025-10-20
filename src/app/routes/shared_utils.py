"""
Shared utilities for Flask routes
=================================

Common utility functions, constants, and helpers used across all route modules.
"""

import logging
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Any, Iterable

from flask import current_app

# Import models and extensions
from app.extensions import db
from app.models import ModelCapability, SecurityAnalysis, GeneratedApplication
from app.services.openrouter_service import OpenRouterService

# Configure logging
logger = logging.getLogger(__name__)

# Provider color mapping for templates
PROVIDER_COLORS = {
    'anthropic': '#D97706',
    'openai': '#14B8A6',
    'google': '#3B82F6',
    'deepseek': '#9333EA',
    'mistralai': '#8B5CF6',
    'qwen': '#F43F5E',
    'minimax': '#7E22CE',
    'x-ai': '#B91C1C',
    'moonshotai': '#10B981',
    'nvidia': '#0D9488',
    'nousresearch': '#059669'
}

# Initialize services
openrouter_service = OpenRouterService()
_openrouter_service = OpenRouterService()  # Legacy alias

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_provider_color(provider):
    """Get color for a provider."""
    return PROVIDER_COLORS.get(provider, '#666666')

def _norm_caps(value: Any) -> List[str]:
    """Normalize various capability shapes into a list of strings."""
    try:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(x) for x in value]
        if isinstance(value, dict):
            keys = []
            any_bool = any(isinstance(v, bool) for v in value.values())
            if any_bool:
                keys = [str(k) for k, v in value.items() if v]
            else:
                keys = [str(k) for k in value.keys()]
            return keys
        if isinstance(value, str):
            return [value]
        if isinstance(value, Iterable):
            return [str(x) for x in value]
    except Exception:
        pass
    return []

def calculate_cost_efficiency(context_window: int, input_price: float, output_price: float) -> float:
    """
    Calculate cost efficiency score (0-1 scale) based on context window and pricing.
    
    Formula:
    - Free models get perfect score (1.0)
    - Paid models: efficiency = (context_value / cost_factor) normalized to 0-1
    - Context value: normalized context window (128K = baseline 1.0)
    - Cost factor: average of input and output price per 1M tokens
    - Higher context + lower price = higher efficiency
    
    Args:
        context_window: Context window size in tokens
        input_price: Input price per token
        output_price: Output price per token
    
    Returns:
        Float between 0.0 and 1.0 representing cost efficiency
    """
    try:
        # Free models get perfect score
        if input_price == 0 and output_price == 0:
            return 1.0
        
        # Need valid context and pricing
        if context_window <= 0 or (input_price <= 0 and output_price <= 0):
            return 0.0
        
        # Convert to per-million-token pricing for easier calculation
        input_price_per_1m = input_price * 1_000_000
        output_price_per_1m = output_price * 1_000_000
        avg_price = (input_price_per_1m + output_price_per_1m) / 2
        
        # Normalize context window (128K = 1.0, 32K = 0.25, 512K = 4.0)
        context_normalized = context_window / 128_000
        
        # Calculate raw efficiency: context value per dollar
        # A model with 128K context at $1/1M tokens = efficiency of 1.0
        raw_efficiency = context_normalized / avg_price if avg_price > 0 else 0
        
        # Apply logarithmic scaling to compress the range
        # log(x + 1) gives smooth curve: very cheap models don't dominate
        import math
        scaled_efficiency = math.log(raw_efficiency + 1) / math.log(101)  # log base normalizes to ~0-1 range
        
        # Clamp to 0-1 range
        efficiency = max(0.0, min(1.0, scaled_efficiency))
        
        return efficiency
    except Exception as e:
        logger.warning(f"Error calculating cost efficiency: {e}")
        return 0.0

def _upsert_openrouter_models(models_payload: list) -> int:
    """Upsert a list of OpenRouter model payloads into ModelCapability."""
    upserted = 0
    for model_data in models_payload:
        model_id = model_data.get('id')
        if not model_id:
            continue

        canonical = model_id.replace('/', '_').replace(':', '_')
        raw_cs = model_data.get('canonical_slug') or ''
        if raw_cs:
            try:
                cs_norm = raw_cs.replace('/', '_').replace(':', '_').replace(' ', '_')
                canonical = cs_norm
            except Exception:
                pass

        # Extract base model ID (without variant suffixes like :free)
        base_id = model_id.split(':')[0] if ':' in model_id else model_id

        provider = model_id.split('/')[0] if '/' in model_id else 'unknown'
        model_name = model_id.split('/')[-1]

        # Pricing extraction
        pricing = model_data.get('pricing', {}) or {}
        try:
            prompt_price = float(pricing.get('prompt') or pricing.get('prompt_tokens') or pricing.get('prompt_price') or 0)
        except Exception:
            prompt_price = 0.0
        try:
            completion_price = float(pricing.get('completion') or pricing.get('completion_price') or pricing.get('completion_tokens') or 0)
        except Exception:
            completion_price = 0.0

        context_window = None
        top_provider = model_data.get('top_provider') or {}
        if top_provider and top_provider.get('context_length'):
            try:
                context_window = int(top_provider.get('context_length') or 0)
            except Exception:
                context_window = None
        elif model_data.get('context_length'):
            try:
                context_window = int(model_data.get('context_length') or 0)
            except Exception:
                context_window = None

        # Try to find existing by model_id first, then by canonical_slug to avoid constraint violations
        existing = ModelCapability.query.filter_by(model_id=model_id).first()
        if not existing:
            existing = ModelCapability.query.filter_by(canonical_slug=canonical).first()
        
        if not existing:
            existing = ModelCapability()
            existing.model_id = model_id
            existing.canonical_slug = canonical
            existing.base_model_id = base_id
            existing.hugging_face_id = model_data.get('hugging_face_id')  # NEW: Store case-sensitive HF ID
            existing.provider = provider
            existing.model_name = model_name
            db.session.add(existing)
        else:
            # Update existing record
            existing.model_id = model_id
            existing.canonical_slug = canonical
            existing.base_model_id = base_id
            existing.hugging_face_id = model_data.get('hugging_face_id')  # NEW: Update case-sensitive HF ID
            existing.provider = provider
            existing.model_name = model_name

        # Core numeric/boolean fields
        existing.is_free = bool(model_data.get('is_free', (prompt_price == 0 and completion_price == 0)))
        if context_window is not None:
            existing.context_window = context_window
        try:
            existing.input_price_per_token = prompt_price
        except Exception:
            pass
        try:
            existing.output_price_per_token = completion_price
        except Exception:
            pass

        # max output tokens
        try:
            existing.max_output_tokens = int(top_provider.get('max_completion_tokens') or model_data.get('max_output_tokens') or existing.max_output_tokens or 0)
        except Exception:
            pass

        # Performance metrics - calculate cost efficiency
        try:
            # Compute cost efficiency based on context window and pricing
            computed_efficiency = calculate_cost_efficiency(
                context_window or existing.context_window or 0,
                prompt_price,
                completion_price
            )
            # Use computed value, fallback to existing or provided value
            existing.cost_efficiency = computed_efficiency if computed_efficiency > 0 else float(
                model_data.get('cost_efficiency') or 
                model_data.get('cost_efficiency_score') or 
                existing.cost_efficiency or 
                0.0
            )
        except Exception as e:
            logger.warning(f"Error setting cost_efficiency for {model_id}: {e}")
            pass
        try:
            existing.safety_score = float(model_data.get('safety_score') or existing.safety_score or 0.0)
        except Exception:
            pass

        # Capability booleans - extract from multiple possible locations
        # Check architecture.modality for vision support
        arch = model_data.get('architecture', {})
        modality = arch.get('modality', '')
        has_image_modality = 'image' in modality.lower() if modality else False
        
        # Check supported_parameters for tool/function calling support
        supported_params = model_data.get('supported_parameters', [])
        has_tools_param = any(p in ['tools', 'tool_choice'] for p in (supported_params or []))
        
        existing.supports_function_calling = bool(
            model_data.get('supports_tool_calling') or 
            model_data.get('supports_function_calling') or 
            has_tools_param or
            existing.supports_function_calling
        )
        existing.supports_json_mode = bool(
            model_data.get('supports_json') or 
            model_data.get('supports_json_mode') or 
            'response_format' in (supported_params or []) or
            existing.supports_json_mode
        )
        existing.supports_streaming = bool(
            model_data.get('supports_streaming') or 
            'stream' in (supported_params or []) or
            existing.supports_streaming
        )
        existing.supports_vision = bool(
            model_data.get('supports_vision') or 
            has_image_modality or
            existing.supports_vision
        )

        # Save the full OpenRouter payload in capabilities_json for later use
        try:
            existing.capabilities_json = json.dumps(model_data)
        except Exception:
            existing.capabilities_json = '{}'

        # Merge selected fields into metadata_json for quick access
        try:
            meta = existing.get_metadata() or {}
            
            # Basic OpenRouter metadata
            meta.update({
                'openrouter_model_id': model_data.get('id'),
                'openrouter_name': model_data.get('name') or model_data.get('model_name'),
                'openrouter_created': model_data.get('created'),
                'openrouter_canonical_slug': model_data.get('canonical_slug'),
                'openrouter_description': model_data.get('description') or model_data.get('openrouter_description'),
                'openrouter_pricing': model_data.get('pricing', {}),
                'openrouter_supported_parameters': model_data.get('supported_parameters') or model_data.get('openrouter_supported_parameters'),
                'openrouter_top_provider': model_data.get('top_provider', {})
            })
            
            # Architecture data - extract from architecture object
            arch = model_data.get('architecture', {})
            if arch:
                meta['architecture_modality'] = arch.get('modality')
                meta['architecture_input_modalities'] = arch.get('input_modalities')
                meta['architecture_output_modalities'] = arch.get('output_modalities')
                meta['architecture_tokenizer'] = arch.get('tokenizer')
                meta['architecture_instruct_type'] = arch.get('instruct_type')
            
            # Provider data - store provider list from pricing object
            pricing = model_data.get('pricing', {})
            if isinstance(pricing, dict) and 'providers' in pricing:
                meta['openrouter_providers'] = pricing.get('providers', [])
                meta['openrouter_provider_count'] = len(pricing.get('providers', []))
            
            # Additional fields
            for k in ('analyses_count', 'apps_count'):
                if k in model_data:
                    meta[k] = model_data.get(k)
            
            existing.set_metadata(meta)
        except Exception as e:
            logger.error(f"Error setting metadata for {model_id}: {e}")
            pass

        # Set installed flag by checking generated/<canonical_slug>
        try:
            repo_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
            models_base = os.path.join(repo_root, 'generated')
            existing.installed = os.path.isdir(os.path.join(models_base, existing.canonical_slug))
        except Exception:
            pass

        try:
            existing.updated_at = datetime.now(timezone.utc)
        except Exception:
            pass
        upserted += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return upserted

def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]

def _gather_file_reports(limit: int | None = None):
    """Get generated file reports for download."""
    from app.paths import REPORTS_DIR
    reports_dir = REPORTS_DIR
    if not reports_dir.exists():
        return []
    files = []
    for p in sorted(reports_dir.glob('*'), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file():
            continue
        stat = p.stat()
        files.append({
            'name': p.name,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'ext': p.suffix.lower().lstrip('.'),
        })
        if limit and len(files) >= limit:
            break
    return files

def _get_recent_analyses(limit: int = 20):
    """Get recent completed analyses across all types."""
    analyses = []
    
    from app.extensions import get_session
    with get_session() as session:
        security_analyses = session.query(SecurityAnalysis).join(GeneratedApplication).filter(
            SecurityAnalysis.status.in_(['completed', 'failed'])
        ).order_by(SecurityAnalysis.created_at.desc()).limit(limit).all()
        
        for analysis in security_analyses:
            analyses.append({
                'id': analysis.id,
                'type': 'security',
                'model_slug': analysis.application.model_slug if analysis.application else 'Unknown',  # type: ignore[attr-defined]
                'app_number': analysis.application.app_number if analysis.application else 0,  # type: ignore[attr-defined]
                'status': analysis.status,
                'created_at': analysis.created_at,
                'completed_at': analysis.completed_at,
                'has_results': bool(analysis.results_json),
                'results_summary': None
            })

    analyses.sort(key=lambda x: x['created_at'], reverse=True)
    return analyses[:limit]

def _find_models_root() -> Optional[Path]:
    """Locate repo's generated directory by walking up parents."""
    try:
        for parent in Path(__file__).resolve().parents:
            candidate = parent / 'generated'
            if candidate.exists() and candidate.is_dir():
                return candidate
    except Exception:
        pass
    return None

def _pick_available_model_slug(preferred: Optional[List[str]] = None) -> Optional[str]:
    root = _find_models_root()
    if not root:
        return None
    def has_app1(p: Path) -> bool:
        return (p / 'app1').exists()

    if preferred:
        for slug in preferred:
            cp = root / slug
            if cp.exists() and cp.is_dir() and has_app1(cp):
                return slug

    for entry in sorted(root.iterdir()):
        try:
            if entry.is_dir() and has_app1(entry):
                return entry.name
        except Exception:
            continue
    return None

# ============================================================================
# TEMPLATE GLOBALS AND FILTERS
# ============================================================================

def register_template_globals_and_filters(app):
    """Register template globals and filters."""

    @app.template_global('get_provider_color')
    def template_get_provider_color(provider):
        """Template global function for getting provider colors."""
        return get_provider_color(provider)

    @app.template_global('make_safe_dom_id')
    def template_make_safe_dom_id(value, prefix=None):
        """Expose helper to templates for creating safe DOM ids."""
        try:
            from app.utils.helpers import make_safe_dom_id
            return make_safe_dom_id(value, prefix=prefix)
        except Exception:
            return (prefix or '') + 'invalid-id'

    @app.template_filter('abbreviate_number')
    def abbreviate_number_filter(value):
        """Format large integers as human-readable abbreviations."""
        try:
            num = float(value or 0)
        except (ValueError, TypeError):
            return value

        sign = '-' if num < 0 else ''
        n = abs(num)
        for threshold, suffix in ((1_000_000_000_000, 'T'), (1_000_000_000, 'B'), (1_000_000, 'M'), (1_000, 'K')):
            if n >= threshold:
                val = n / threshold
                s = f"{val:.1f}"
                if s.endswith('.0'):
                    s = s[:-2]
                return f"{sign}{s}{suffix}"
        if n.is_integer():
            return f"{int(num)}"
        return f"{num:.2f}"

    @app.template_filter('timestamp_to_date')
    def timestamp_to_date_filter(value):
        """Convert Unix timestamp to human-readable date."""
        from datetime import datetime
        try:
            timestamp = int(value or 0)
            if timestamp <= 0:
                return 'N/A'
            # Convert Unix timestamp to datetime
            dt = datetime.fromtimestamp(timestamp)
            # Format as "Month DD, YYYY"
            return dt.strftime('%B %d, %Y')
        except (ValueError, TypeError, OSError):
            return 'Invalid Date'