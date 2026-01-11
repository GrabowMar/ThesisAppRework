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
        if self.cache_expires_at is None:
            return True

        now = utc_now()
        expires_at = self.cache_expires_at

        # SQLite stores datetimes as naive UTC, normalize both for comparison
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        if expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)

        return now > expires_at
    
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

    # Chapter 4 MSS Benchmarks
    bfcl_score = db.Column(db.Float)  # Berkeley Function Calling 0-100
    webdev_elo = db.Column(db.Float)  # WebDev Arena Elo score
    arc_agi_score = db.Column(db.Float)  # ARC-AGI pass rate 0-100
    simplebench_score = db.Column(db.Float)  # SimpleBench accuracy 0-100
    canaicode_score = db.Column(db.Float)  # CanAiCode pass rate 0-100
    seal_coding_score = db.Column(db.Float)  # SEAL Showdown coding BT score
    gpqa_score = db.Column(db.Float)  # GPQA accuracy 0-100

    # Performance metrics (from Artificial Analysis)
    ttft_median = db.Column(db.Float)  # Time to First Token median (seconds)
    ttft_p95 = db.Column(db.Float)  # Time to First Token P95 (seconds)
    throughput_median = db.Column(db.Float)  # Output tokens/second median
    throughput_p95 = db.Column(db.Float)  # Output tokens/second P95
    total_latency_median = db.Column(db.Float)  # Total response time median (seconds)
    total_latency_p95 = db.Column(db.Float)  # Total response time P95 (seconds)
    quality_index = db.Column(db.Float)  # Artificial Analysis quality/intelligence index

    # Composite scores (computed)
    coding_composite = db.Column(db.Float)  # Weighted composite coding score
    overall_score = db.Column(db.Float)  # Overall score (coding + performance + value) - Chapter 3 legacy

    # MSS Components (Chapter 4)
    adoption_score = db.Column(db.Float)  # 0-1 normalized adoption score (35% of MSS)
    benchmark_score = db.Column(db.Float)  # 0-1 normalized benchmark score (30% of MSS)
    cost_efficiency_score = db.Column(db.Float)  # 0-1 normalized cost efficiency (20% of MSS)
    accessibility_score = db.Column(db.Float)  # 0-1 normalized accessibility (15% of MSS)
    mss = db.Column(db.Float)  # Model Selection Score (final composite)

    # Adoption Metrics (for MSS calculation)
    openrouter_programming_rank = db.Column(db.Integer)  # Rank in programming category
    openrouter_overall_rank = db.Column(db.Integer)  # Overall popularity rank
    openrouter_market_share = db.Column(db.Float)  # Market share percentage

    # Accessibility Metrics (for MSS calculation)
    license_type = db.Column(db.String(50))  # apache, mit, llama, commercial, etc.
    api_stability = db.Column(db.String(20))  # stable, beta, experimental, deprecated
    documentation_quality = db.Column(db.String(20))  # comprehensive, basic, minimal, none

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

    # Data freshness tracking (per category)
    benchmark_data_updated_at = db.Column(db.DateTime(timezone=True))  # Last coding benchmark update
    performance_data_updated_at = db.Column(db.DateTime(timezone=True))  # Last performance metrics update
    pricing_data_updated_at = db.Column(db.DateTime(timezone=True))  # Last pricing update
    adoption_data_updated_at = db.Column(db.DateTime(timezone=True))  # Last OpenRouter ranking update
    accessibility_data_updated_at = db.Column(db.DateTime(timezone=True))  # Last accessibility data update

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
        if self.cache_expires_at is None:
            return True

        now = utc_now()
        expires_at = self.cache_expires_at

        # SQLite stores datetimes as naive UTC, normalize both for comparison
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        if expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)

        return now > expires_at
    
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

            # Chapter 4 MSS Benchmarks
            'bfcl_score': self.bfcl_score,
            'webdev_elo': self.webdev_elo,
            'arc_agi_score': self.arc_agi_score,
            'simplebench_score': self.simplebench_score,
            'canaicode_score': self.canaicode_score,
            'seal_coding_score': self.seal_coding_score,
            'gpqa_score': self.gpqa_score,

            # Performance metrics
            'ttft_median': self.ttft_median,
            'ttft_p95': self.ttft_p95,
            'throughput_median': self.throughput_median,
            'throughput_p95': self.throughput_p95,
            'total_latency_median': self.total_latency_median,
            'total_latency_p95': self.total_latency_p95,
            'quality_index': self.quality_index,

            # Composite scores (template expects 'composite_score')
            'composite_score': self.coding_composite,
            'overall_score': self.overall_score,  # Chapter 3 legacy

            # MSS Components (Chapter 4)
            'adoption_score': self.adoption_score,
            'benchmark_score': self.benchmark_score,
            'cost_efficiency_score': self.cost_efficiency_score,
            'accessibility_score': self.accessibility_score,
            'mss': self.mss,

            # Adoption Metrics
            'openrouter_programming_rank': self.openrouter_programming_rank,
            'openrouter_overall_rank': self.openrouter_overall_rank,
            'openrouter_market_share': self.openrouter_market_share,

            # Accessibility Metrics
            'license_type': self.license_type,
            'api_stability': self.api_stability,
            'documentation_quality': self.documentation_quality,

            # Pricing (template expects these names)
            'price_per_million_input': self.input_price_per_mtok or 0,
            'price_per_million_output': self.output_price_per_mtok or 0,
            'is_free': self.is_free,

            # Metadata
            'context_length': self.context_length,
            'huggingface_id': self.huggingface_id,
            'openrouter_id': self.openrouter_id,

            # Data freshness
            'benchmark_data_updated_at': self.benchmark_data_updated_at.isoformat() if self.benchmark_data_updated_at else None,
            'performance_data_updated_at': self.performance_data_updated_at.isoformat() if self.performance_data_updated_at else None,
            'pricing_data_updated_at': self.pricing_data_updated_at.isoformat() if self.pricing_data_updated_at else None,
            'adoption_data_updated_at': self.adoption_data_updated_at.isoformat() if self.adoption_data_updated_at else None,
            'accessibility_data_updated_at': self.accessibility_data_updated_at.isoformat() if self.accessibility_data_updated_at else None,

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
