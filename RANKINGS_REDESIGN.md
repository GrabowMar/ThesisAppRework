# Rankings System Redesign - January 2026

## Executive Summary

Complete overhaul of the AI model rankings system to align with research methodology requirements and leverage real-time API data sources instead of static fallback data.

## Problems Identified

### Current System Issues
1. **Limited Real API Integration** - Only OpenRouter API is actively used
2. **Static Fallback Data** - Hardcoded benchmark scores from Dec 2024/Jan 2025
3. **Incomplete Benchmark Coverage** - Missing several methodology-required metrics
4. **No Performance Metrics** - Lacks speed/latency/throughput data
5. **Manual Data Updates** - Requires code changes to update benchmark scores
6. **Poor Data Freshness** - No way to know if data is current

## Research Methodology Alignment

### Required Metrics (from Chapter 3: Research Methodology)

The methodology defines evaluation across **4 dimensions**:

#### 1. Security Evaluation Metrics
- ❌ Vulnerability Count (SAST/DAST) - **NOT APPLICABLE** (requires generated code)
- ❌ CWE Distribution - **NOT APPLICABLE** (requires generated code)
- ❌ OWASP Coverage - **NOT APPLICABLE** (requires generated code)

#### 2. Code Quality Evaluation Metrics
- ❌ Python/JavaScript Linting - **NOT APPLICABLE** (requires generated code)
- ❌ Cyclomatic Complexity - **NOT APPLICABLE** (requires generated code)
- ❌ Type Coverage - **NOT APPLICABLE** (requires generated code)

#### 3. Performance Evaluation Metrics
- ✅ **Response Time** (p50, p95, p99 latency) - **CAN BE FETCHED** from Artificial Analysis
- ✅ **Throughput** (requests/sec) - **CAN BE FETCHED** from Artificial Analysis
- ✅ **Error Rate** - **CAN BE FETCHED** from Artificial Analysis

#### 4. Requirements Compliance / Coding Benchmarks
- ✅ **HumanEval+** - **CAN BE FETCHED** from HuggingFace Datasets / EvalPlus
- ✅ **MBPP+** - **CAN BE FETCHED** from HuggingFace Datasets / EvalPlus
- ✅ **SWE-bench Verified** - **CAN BE FETCHED** from GitHub / HuggingFace
- ✅ **BigCodeBench Hard/Full** - **CAN BE FETCHED** from HuggingFace Space
- ✅ **LiveBench Coding** - **CAN BE FETCHED** from LiveBench GitHub/HuggingFace
- ✅ **LiveCodeBench** - **CAN BE FETCHED** from LiveCodeBench GitHub

**Note:** Security and Code Quality metrics require analyzing generated code, which is beyond the scope of a model ranking/comparison page. Those metrics belong to the **application analysis** phase (Chapter 4).

The rankings page should focus on:
1. **Coding Benchmarks** (measure code generation capability)
2. **Performance Metrics** (measure API speed/cost)
3. **Model Metadata** (pricing, context length, availability)

## Available Data Sources with API Access

### 1. **OpenRouter API** ✅ ALREADY INTEGRATED
- **Endpoint:** `https://openrouter.ai/api/v1/models`
- **Provides:** Pricing, context length, availability, model descriptions
- **Auth:** API key optional (rate limited without)
- **Update Frequency:** Real-time
- **Format:** JSON REST API

### 2. **HuggingFace Datasets** ✅ NEW - HIGHLY RELIABLE
- **Endpoint:** `datasets.load_dataset()` via HuggingFace API
- **Datasets Available:**
  - `evalplus/humanevalplus` - HumanEval+ scores
  - `evalplus/mbppplus` - MBPP+ scores
  - `princeton-nlp/SWE-bench` - SWE-bench results
  - `livebench/leaderboard` - LiveBench scores
  - `bigcode/bigcodebench` - BigCodeBench leaderboard
- **Auth:** HuggingFace token (free)
- **Update Frequency:** Weekly/Monthly (depends on benchmark)
- **Format:** Parquet/CSV via Datasets API

### 3. **GitHub Raw JSON** ✅ NEW - DIRECT LEADERBOARD ACCESS
- **SWE-bench:** `https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/main/data/leaderboards.json`
- **LiveBench:** `https://huggingface.co/datasets/livebench/leaderboard`
- **EvalPlus:** `https://raw.githubusercontent.com/evalplus/evalplus/master/leaderboard/`
- **Auth:** None required
- **Update Frequency:** Updated when leaderboards change
- **Format:** JSON

### 4. **Artificial Analysis** ✅ NEW - PERFORMANCE METRICS
- **Website:** `https://artificialanalysis.ai/leaderboards/models`
- **Provides:**
  - Response time (TTFT - Time to First Token)
  - Throughput (tokens/second)
  - Latency percentiles (P5, P25, P50, P75, P95)
  - Quality index
  - Price comparisons
- **Auth:** Web scraping (no official API) OR HuggingFace Space dataset
- **Update Frequency:** Every 14 days
- **Format:** **Must be scraped** or use HuggingFace Space

### 5. **LiveCodeBench** ✅ NEW
- **GitHub:** `https://github.com/LiveBench/LiveCodeBench`
- **HuggingFace:** `https://huggingface.co/datasets/livecodebench/code_generation_lite`
- **Provides:** Competitive programming scores
- **Auth:** None
- **Update Frequency:** Monthly
- **Format:** JSON/Dataset

## Proposed Architecture

### Data Fetching Strategy

```
┌─────────────────────────────────────────────────┐
│         Rankings Service (Orchestrator)         │
└─────────────────────────────────────────────────┘
                     ↓
        ┌────────────┼────────────┐
        ↓            ↓            ↓
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │OpenRouter│ │HuggingFace│ │GitHub Raw│
  │   API    │ │ Datasets  │ │   JSON   │
  └──────────┘ └──────────┘ └──────────┘
        ↓            ↓            ↓
┌─────────────────────────────────────────────────┐
│      ModelBenchmarkCache (Database Cache)       │
│  TTL: 24h pricing, 7d benchmarks, 1d performance│
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│     Frontend Rankings UI (Filters & Sorting)    │
└─────────────────────────────────────────────────┘
```

### Database Schema Enhancements

Add to `ModelBenchmarkCache`:

```python
# Performance metrics (from Artificial Analysis)
ttft_median = db.Column(db.Float)  # Time to first token (seconds)
ttft_p95 = db.Column(db.Float)
throughput_median = db.Column(db.Float)  # Tokens/second
throughput_p95 = db.Column(db.Float)
total_latency_median = db.Column(db.Float)  # Total response time
total_latency_p95 = db.Column(db.Float)
quality_index = db.Column(db.Float)  # Artificial Analysis quality index

# Additional benchmarks
humaneval_complete = db.Column(db.Float)  # BigCodeBench Complete
humaneval_instruct = db.Column(db.Float)  # BigCodeBench Instruct
arc_prize = db.Column(db.Float)  # ARC reasoning benchmark

# Data freshness tracking
benchmark_data_updated_at = db.Column(db.DateTime(timezone=True))
performance_data_updated_at = db.Column(db.DateTime(timezone=True))
pricing_data_updated_at = db.Column(db.DateTime(timezone=True))
```

### Service Layer Architecture

```
model_rankings_service.py
├── OpenRouterFetcher
│   └── fetch_openrouter_models() → pricing, context, availability
├── HuggingFaceFetcher
│   ├── fetch_evalplus_leaderboard() → HumanEval+, MBPP+
│   ├── fetch_swebench_leaderboard() → SWE-bench Verified/Lite
│   ├── fetch_bigcodebench_leaderboard() → BigCodeBench Hard/Full
│   └── fetch_livebench_leaderboard() → LiveBench coding
├── GitHubRawFetcher
│   ├── fetch_swebench_json() → Direct JSON download
│   └── fetch_livecodebench_json() → Direct JSON download
├── ArtificialAnalysisFetcher
│   └── fetch_performance_metrics() → TTFT, throughput, quality
└── RankingsAggregator
    ├── aggregate_all_sources()
    ├── normalize_model_names()
    ├── compute_composite_scores()
    └── cache_to_database()
```

### Composite Scoring Algorithm

Align with methodology (Chapter 3, Section 3.6):

```python
# Coding Capability Score (50%)
coding_weights = {
    'humaneval_plus': 0.15,      # 15%
    'swe_bench_verified': 0.15,  # 15%
    'bigcodebench_hard': 0.10,   # 10%
    'livebench_coding': 0.05,    # 5%
    'mbpp_plus': 0.05,           # 5%
}

# Performance Score (30%)
performance_weights = {
    'throughput_normalized': 0.15,      # 15% (higher is better)
    'ttft_normalized': 0.10,            # 10% (lower is better, inverse)
    'quality_index': 0.05,              # 5%
}

# Value Score (20%)
value_weights = {
    'price_efficiency': 0.10,   # 10% (composite / price ratio)
    'context_length': 0.05,     # 5% (normalized to 0-100)
    'availability': 0.05,       # 5% (uptime, free tier, etc.)
}

overall_score = (coding_score * 0.5) + (performance_score * 0.3) + (value_score * 0.2)
```

## Implementation Plan

### Phase 1: Data Fetching Infrastructure ✅ PRIORITY
1. ✅ Add HuggingFace Datasets client
2. ✅ Add GitHub raw JSON fetcher
3. ✅ Add Artificial Analysis scraper/dataset fetcher
4. ✅ Implement source-specific error handling
5. ✅ Add per-source TTL configuration

### Phase 2: Service Layer Enhancement
1. ✅ Refactor `model_rankings_service.py` to use new fetchers
2. ✅ Implement intelligent model name matching (handle variants)
3. ✅ Add composite scoring with methodology-aligned weights
4. ✅ Implement incremental cache updates (only refresh stale data)

### Phase 3: Database Migration
1. ✅ Create Alembic migration for new columns
2. ✅ Add indexes for performance queries
3. ✅ Implement data backfill from new sources

### Phase 4: Frontend UI Updates
1. ✅ Add performance metrics columns (TTFT, Throughput)
2. ✅ Add data freshness indicators
3. ✅ Implement advanced filtering (by benchmark coverage, performance tier)
4. ✅ Add visualization dashboard (charts for benchmark comparison)
5. ✅ Add "Last Updated" timestamps per metric

### Phase 5: Testing & Validation
1. ✅ Test all API integrations
2. ✅ Validate model name matching accuracy
3. ✅ Test cache refresh logic
4. ✅ Performance testing (page load with 500+ models)

## Success Metrics

1. **Data Coverage:** >80% of OpenRouter models have at least 3 benchmark scores
2. **Data Freshness:** All benchmark data <30 days old
3. **Performance:** Leaderboard loads in <2 seconds
4. **API Reliability:** <5% fetch failure rate across all sources
5. **Model Matching Accuracy:** >95% correct model-to-benchmark mapping

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| API rate limiting | Implement exponential backoff, cache aggressively |
| Model name mismatches | Maintain explicit mapping table, fuzzy matching fallback |
| Missing benchmark data | Show "—" in UI, don't penalize composite score |
| GitHub/HF downtime | Use cached data, show staleness warning |
| Artificial Analysis scraping breaks | Fallback to manual data, implement change detection |

## Resources & Documentation

### API Documentation
- [OpenRouter API](https://openrouter.ai/docs#models)
- [HuggingFace Datasets](https://huggingface.co/docs/datasets)
- [EvalPlus Leaderboard](https://evalplus.github.io/leaderboard.html)
- [BigCodeBench GitHub](https://github.com/bigcode-project/bigcodebench/)
- [SWE-bench Official](https://www.swebench.com/)
- [LiveBench AI](https://livebench.ai/)
- [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models)

### Research References
- Chapter 3 (Methodology) - Evaluation Metrics Framework
- Table 3.2 - Security Evaluation Metrics
- Table 3.3 - Code Quality Evaluation Metrics
- Table 3.4 - Performance Evaluation Metrics
- Table 3.5 - Requirements Compliance Metrics

## Timeline

- **Week 1:** Phase 1 - Data fetching infrastructure
- **Week 2:** Phase 2 - Service layer enhancement
- **Week 3:** Phase 3 - Database migration + Phase 4 start
- **Week 4:** Phase 4 completion + Phase 5 testing

**Total Duration:** ~4 weeks for complete implementation
