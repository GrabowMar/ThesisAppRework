"""
Cache-related database models.
"""
import json
from datetime import timedelta
from typing import Dict, Any, Optional
from ..extensions import db

from ..utils.time import utc_now

class OpenRouterModelCache(db.Model):
    """Model for caching OpenRouter API model data to reduce API calls."""
    __tablename__ = 'openrouter_model_cache'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.String(200), unique=True, nullable=False, index=True)
    
    # Cached data from OpenRouter API
    model_data_json = db.Column(db.Text, nullable=False)  # Full OpenRouter model data
    
    # Cache metadata
    cache_expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    fetch_duration = db.Column(db.Float)  # Time taken to fetch from API
    api_response_status = db.Column(db.Integer)  # HTTP status code
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    last_accessed = db.Column(db.DateTime(timezone=True), default=utc_now)  # Track usage
    
    def get_model_data(self) -> Dict[str, Any]:
        """Get cached model data as dictionary."""
        if self.model_data_json:
            try:
                return json.loads(self.model_data_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_model_data(self, model_dict: Dict[str, Any]) -> None:
        """Set model data from dictionary."""
        self.model_data_json = json.dumps(model_dict)
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return utc_now() > self.cache_expires_at
    
    def mark_accessed(self) -> None:
        """Update last accessed timestamp."""
        self.last_accessed = utc_now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'model_id': self.model_id,
            'model_data': self.get_model_data(),
            'cache_expires_at': self.cache_expires_at,
            'fetch_duration': self.fetch_duration,
            'api_response_status': self.api_response_status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_accessed': self.last_accessed,
            'is_expired': self.is_expired()
        }
    
    def __repr__(self) -> str:
        return f'<OpenRouterModelCache {self.model_id}>'


class ModelBenchmarkCache(db.Model):
    """Cache for aggregated model benchmark scores from multiple sources.
    
    Stores coding-focused benchmark results: HumanEval+, MBPP+, SWE-bench,
    BigCodeBench, LiveBench coding category, etc.
    """
    __tablename__ = 'model_benchmark_cache'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.String(200), unique=True, nullable=False, index=True)
    model_name = db.Column(db.String(300))  # Human-readable name
    
    # Coding benchmark scores (0-100 scale, nullable if not available)
    humaneval_plus = db.Column(db.Float)  # HumanEval+ pass@1
    mbpp_plus = db.Column(db.Float)  # MBPP+ pass@1
    swe_bench_verified = db.Column(db.Float)  # SWE-bench Verified score
    swe_bench_lite = db.Column(db.Float)  # SWE-bench Lite score
    bigcodebench_hard = db.Column(db.Float)  # BigCodeBench Hard pass@1
    bigcodebench_full = db.Column(db.Float)  # BigCodeBench Full pass@1
    livebench_coding = db.Column(db.Float)  # LiveBench coding category
    livecodebench = db.Column(db.Float)  # LiveCodeBench score
    
    # General benchmarks (for context)
    mmlu = db.Column(db.Float)  # MMLU score
    math_score = db.Column(db.Float)  # Math benchmark
    
    # Composite scores (computed)
    coding_composite = db.Column(db.Float)  # Weighted composite coding score
    
    # Pricing info (from OpenRouter)
    input_price_per_mtok = db.Column(db.Float)  # Price per million input tokens
    output_price_per_mtok = db.Column(db.Float)  # Price per million output tokens
    is_free = db.Column(db.Boolean, default=False)
    
    # Model metadata
    provider = db.Column(db.String(100))
    context_length = db.Column(db.Integer)
    huggingface_id = db.Column(db.String(300))
    openrouter_id = db.Column(db.String(300))
    
    # Source tracking
    sources = db.Column(db.Text)  # JSON array of sources used
    raw_data_json = db.Column(db.Text)  # Full raw data for debugging
    
    # Cache metadata
    cache_expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    fetched_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    def get_sources(self) -> list:
        """Get list of data sources."""
        if self.sources:
            try:
                return json.loads(self.sources)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_sources(self, sources: list) -> None:
        """Set data sources list."""
        self.sources = json.dumps(sources)
    
    def get_raw_data(self) -> Dict[str, Any]:
        """Get raw data dictionary."""
        if self.raw_data_json:
            try:
                return json.loads(self.raw_data_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_raw_data(self, data: Dict[str, Any]) -> None:
        """Set raw data dictionary."""
        self.raw_data_json = json.dumps(data)
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return utc_now() > self.cache_expires_at
    
    def compute_composite_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """
        Compute weighted composite coding score.
        
        Default weights (all percentages):
        - HumanEval+: 25%
        - SWE-bench Verified: 25%
        - BigCodeBench Hard: 20%
        - LiveBench Coding: 15%
        - MBPP+: 15%
        """
        if weights is None:
            weights = {
                'humaneval_plus': 0.25,
                'swe_bench_verified': 0.25,
                'bigcodebench_hard': 0.20,
                'livebench_coding': 0.15,
                'mbpp_plus': 0.15
            }
        
        score = 0.0
        total_weight = 0.0
        
        benchmarks = {
            'humaneval_plus': self.humaneval_plus,
            'swe_bench_verified': self.swe_bench_verified,
            'bigcodebench_hard': self.bigcodebench_hard,
            'livebench_coding': self.livebench_coding,
            'mbpp_plus': self.mbpp_plus,
            'livecodebench': self.livecodebench,
            'swe_bench_lite': self.swe_bench_lite,
            'bigcodebench_full': self.bigcodebench_full
        }
        
        for key, weight in weights.items():
            value = benchmarks.get(key)
            if value is not None:
                score += value * weight
                total_weight += weight
        
        if total_weight > 0:
            return round(score / total_weight, 2)
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template and API responses.
        
        Returns flat structure matching aggregate_rankings() output.
        """
        return {
            'id': self.id,
            'model_id': self.model_id,
            'model_name': self.model_name,
            'provider': self.provider,
            
            # Flat benchmark scores (for template compatibility)
            'humaneval_plus': self.humaneval_plus,
            'mbpp_plus': self.mbpp_plus,
            'swe_bench_verified': self.swe_bench_verified,
            'swe_bench_lite': self.swe_bench_lite,
            'bigcodebench_hard': self.bigcodebench_hard,
            'bigcodebench_full': self.bigcodebench_full,
            'livebench_coding': self.livebench_coding,
            'livecodebench': self.livecodebench,
            
            # Composite score (template expects 'composite_score')
            'composite_score': self.coding_composite,
            
            # Pricing (template expects these names)
            'price_per_million_input': self.input_price_per_mtok or 0,
            'price_per_million_output': self.output_price_per_mtok or 0,
            'is_free': self.is_free,
            
            # Metadata
            'context_length': self.context_length,
            'huggingface_id': self.huggingface_id,
            'openrouter_id': self.openrouter_id,
            
            # Sources
            'sources': self.get_sources(),
            'fetched_at': self.fetched_at.isoformat() if self.fetched_at else None,
            'is_expired': self.is_expired()
        }
    
    def __repr__(self) -> str:
        return f'<ModelBenchmarkCache {self.model_id}>'


class ExternalModelInfoCache(db.Model):
    """Cache for external model info (primarily OpenRouter).

    Keyed by canonical model slug, stores JSON payload and expiry.
    """
    __tablename__ = 'external_model_info_cache'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    model_slug = db.Column(db.String(200), unique=True, nullable=False, index=True)

    # Cached merged JSON payload
    merged_json = db.Column(db.Text, nullable=False)

    # Cache metadata
    cache_expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    last_refreshed = db.Column(db.DateTime(timezone=True), default=utc_now)
    source_notes = db.Column(db.String(200))  # e.g., "openrouter+hf"

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_data(self) -> Dict[str, Any]:
        try:
            return json.loads(self.merged_json) if self.merged_json else {}
        except json.JSONDecodeError:
            return {}

    def set_data(self, data: Dict[str, Any]) -> None:
        self.merged_json = json.dumps(data)

    def is_expired(self) -> bool:
        return utc_now() > self.cache_expires_at

    def mark_refreshed(self, ttl_hours: int) -> None:
        self.last_refreshed = utc_now()
        self.cache_expires_at = utc_now().replace(microsecond=0) + timedelta(hours=ttl_hours)

    def __repr__(self) -> str:
        return f'<ExternalModelInfoCache {self.model_slug}>'
