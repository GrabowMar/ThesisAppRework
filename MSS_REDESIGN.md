# Model Selection Score (MSS) Redesign - Chapter 4 Implementation

**Version:** 2.0
**Date:** 2026-01-10
**Based on:** Chapter 4: Model Evaluation and Selection
**Replaces:** Previous Chapter 3-based design (RANKINGS_REDESIGN.md)

---

## Executive Summary

This document outlines the complete redesign of the rankings system to align with **Chapter 4: Model Evaluation and Selection** methodology. The system will implement the Model Selection Score (MSS) formula:

```
MSS = 0.35×Adoption + 0.30×Benchmarks + 0.20×Cost + 0.15×Accessibility
```

This approach focuses on selecting models for empirical evaluation based on real-world usage patterns, comprehensive benchmarking, cost efficiency, and practical accessibility.

---

## 1. Model Selection Score (MSS) Components

### 1.1 Adoption Score (35% Weight)

**Purpose:** Measure real-world usage and community trust in production environments.

**Data Source:** OpenRouter usage analytics
- **Primary:** OpenRouter Rankings (https://openrouter.ai/rankings)
- **Metrics:**
  - Programming category token usage rank
  - Tool-calling usage rank
  - Overall popularity trends (daily/weekly/monthly)
  - Market share percentage

**Access Method:**
- OpenRouter maintains public rankings at `/rankings` but does not currently expose a dedicated public API for leaderboard data
- **Implementation Options:**
  1. **Web scraping** (primary): Parse HTML from https://openrouter.ai/rankings/programming
  2. **Manual tracking** (fallback): Periodic manual recording of top model ranks
  3. **App attribution** (future): If we integrate as OpenRouter app, track our own usage patterns

**Scoring Algorithm:**
```python
def compute_adoption_score(model_data: Dict[str, Any]) -> float:
    """
    Compute adoption score from OpenRouter usage rank.
    Lower rank = higher score (rank 1 is best).

    Normalize to [0, 1] scale:
    - Rank 1-5: 1.0 - 0.8
    - Rank 6-10: 0.8 - 0.6
    - Rank 11-20: 0.6 - 0.4
    - Rank 21-50: 0.4 - 0.2
    - Rank 51+: 0.2 - 0.0
    """
    programming_rank = model_data.get('openrouter_programming_rank')
    if not programming_rank:
        return 0.0

    if programming_rank <= 5:
        return 1.0 - (programming_rank - 1) * 0.04
    elif programming_rank <= 10:
        return 0.8 - (programming_rank - 6) * 0.04
    elif programming_rank <= 20:
        return 0.6 - (programming_rank - 11) * 0.02
    elif programming_rank <= 50:
        return 0.4 - (programming_rank - 21) * 0.00667
    else:
        return max(0.0, 0.2 - (programming_rank - 51) * 0.004)
```

### 1.2 Benchmark Performance Score (30% Weight)

**Purpose:** Evaluate model capabilities across multiple coding and reasoning benchmarks.

**Benchmarks (Chapter 4 Requirements):**

#### 1.2.1 BFCL (Berkeley Function-Calling Leaderboard)
- **What:** Function calling/tool use capability evaluation
- **Version:** BFCL V4 (2026) - includes multi-turn, multi-step agentic evaluation
- **Access:**
  - Official leaderboard: https://gorilla.cs.berkeley.edu/leaderboard.html
  - HuggingFace dataset: `gorilla-llm/Berkeley-Function-Calling-Leaderboard`
  - Python package: `pip install bfcl-eval`
- **Data Format:** JSON with model scores (0-100 scale)
- **Update Frequency:** Periodic (check monthly)
- **Weight in Benchmark Score:** 15%

#### 1.2.2 WebDev Arena
- **What:** Elo-based real-time web development coding competition
- **Access:**
  - Leaderboard: https://lmarena.ai/leaderboard/webdev
  - Alternative: https://web.lmarena.ai/leaderboard
- **Data Format:** Bradley-Terry (BT) scores (Elo-like ranking)
- **Scoring System:** Pairwise win/loss comparisons
- **Update Frequency:** Daily (95,449+ votes as of Jan 2026)
- **Access Method:** Web scraping (no public API found)
- **Weight in Benchmark Score:** 15%

#### 1.2.3 LiveBench
- **What:** Contamination-free evaluation on recent data
- **Access:**
  - Website: https://livebench.ai/
  - GitHub: Raw JSON from repository
- **Already Implemented:** Yes (in benchmark_fetchers.py)
- **Weight in Benchmark Score:** 10%

#### 1.2.4 LiveCodeBench
- **What:** Holistic coding evaluation with code execution
- **Access:**
  - Leaderboard: https://livecodebench.github.io/leaderboard.html
  - GitHub: Raw JSON from repository
- **Already Implemented:** Yes (in benchmark_fetchers.py)
- **Weight in Benchmark Score:** 10%

#### 1.2.5 ARC-AGI
- **What:** Abstract reasoning challenge
- **Version:** ARC-AGI-2 (with ARC-AGI-3 planned for 2026)
- **Access:**
  - Official leaderboard: https://arcprize.org/leaderboard
  - LLM Stats aggregator: https://llm-stats.com/benchmarks/arc-agi
  - GitHub: fchollet/ARC-AGI
- **Data Format:** Pass rate percentage
- **Access Method:** Web scraping or LLM Stats API (if available)
- **Weight in Benchmark Score:** 10%

#### 1.2.6 SimpleBench
- **What:** Common-sense reasoning (spatial, social, linguistic)
- **Access:**
  - Website: https://simple-bench.com/
  - Epoch AI aggregator: https://epoch.ai/benchmarks/simplebench
- **Data Format:** 213 multiple-choice questions, 6 options each
- **Human Baseline:** 83.7% (vs. best AI ~62.4%)
- **Access Method:** Web scraping (no dedicated API found)
- **Weight in Benchmark Score:** 10%

#### 1.2.7 CanAiCode
- **What:** Coding interview tasks with Docker sandbox validation
- **Access:**
  - HuggingFace Space: https://huggingface.co/spaces/mike-ravkine/can-ai-code-results
- **Data Format:** Pass/fail rates on interview questions
- **Languages:** Python, NodeJS
- **Access Method:** HuggingFace Spaces API or web scraping
- **Weight in Benchmark Score:** 10%

#### 1.2.8 SEAL Showdown
- **What:** Human preference voting based on real-world usage
- **Access:**
  - Main site: https://scale.com/showdown
  - Coding-specific: https://scale.com/leaderboard/coding
- **Data Format:** Bradley-Terry scores from pairwise comparisons
- **Dataset Size:** Millions of conversations, 12.4% coding tasks
- **Access Method:** Web scraping (coding category filter)
- **Weight in Benchmark Score:** 10%

#### 1.2.9 GPQA (via LLM Stats)
- **What:** Graduate-level science reasoning (physics, chemistry, biology)
- **Access:**
  - LLM Stats aggregator: https://llm-stats.com/benchmarks/gpqa
  - Direct dataset: GitHub idavidrein/gpqa
- **Variants:** Extended (546q), Main (448q), Diamond (198q)
- **Access Method:** LLM Stats platform (168 models evaluated)
- **Weight in Benchmark Score:** 10%

**Benchmark Score Calculation:**
```python
def compute_benchmark_score(model_data: Dict[str, Any]) -> float:
    """
    Aggregate normalized scores from all Chapter 4 benchmarks.
    Each benchmark is normalized to [0, 1] then weighted.
    """
    benchmarks = {
        'bfcl': (model_data.get('bfcl_score'), 0.15),
        'webdev_elo': (model_data.get('webdev_elo'), 0.15),
        'livebench': (model_data.get('livebench_score'), 0.10),
        'livecodebench': (model_data.get('livecodebench_score'), 0.10),
        'arc_agi': (model_data.get('arc_agi_score'), 0.10),
        'simplebench': (model_data.get('simplebench_score'), 0.10),
        'canaicode': (model_data.get('canaicode_score'), 0.10),
        'seal': (model_data.get('seal_coding_score'), 0.10),
        'gpqa': (model_data.get('gpqa_score'), 0.10),
    }

    total_score = 0.0
    total_weight = 0.0

    for bench_name, (score, weight) in benchmarks.items():
        if score is not None:
            # Normalize to [0, 1] based on benchmark-specific ranges
            normalized = normalize_benchmark_score(bench_name, score)
            total_score += normalized * weight
            total_weight += weight

    # If we have at least 50% of benchmarks, compute weighted average
    if total_weight >= 0.15:  # At least 50% of total weight (0.30)
        return total_score / total_weight * 0.30  # Scale to 30% of MSS
    else:
        return 0.0  # Not enough data

def normalize_benchmark_score(benchmark: str, score: float) -> float:
    """
    Normalize benchmark-specific scores to [0, 1] scale.
    """
    ranges = {
        'bfcl': (0, 100),  # Percentage
        'webdev_elo': (800, 1400),  # Elo range (estimated)
        'livebench': (0, 100),  # Percentage
        'livecodebench': (0, 100),  # Percentage
        'arc_agi': (0, 100),  # Pass rate percentage
        'simplebench': (0, 100),  # Accuracy percentage
        'canaicode': (0, 100),  # Pass rate percentage
        'seal': (800, 1400),  # Bradley-Terry score (Elo-like)
        'gpqa': (0, 100),  # Accuracy percentage
    }

    min_val, max_val = ranges.get(benchmark, (0, 100))
    return max(0.0, min(1.0, (score - min_val) / (max_val - min_val)))
```

### 1.3 Cost Efficiency Score (20% Weight)

**Purpose:** Evaluate value for money (performance per dollar).

**Metrics:**
- Average price per million tokens (prompt + completion)
- Benchmark performance (from component 1.2)
- Context length value

**Data Source:**
- OpenRouter API: `/api/v1/models` (pricing data)
- Already implemented in existing system

**Scoring Algorithm:**
```python
def compute_cost_efficiency_score(model_data: Dict[str, Any]) -> float:
    """
    Cost efficiency = benchmark_score / normalized_price
    Higher benchmark score + lower price = better efficiency
    """
    benchmark_score = model_data.get('benchmark_score', 0)
    avg_price = model_data.get('average_price_per_million')
    context_length = model_data.get('context_length', 0)

    if not avg_price or avg_price <= 0 or benchmark_score <= 0:
        return 0.0

    # Normalize price to [0, 1] (inverse: lower is better)
    # Assume price range: $0.10 - $100 per million tokens
    max_price = 100.0
    min_price = 0.10
    normalized_price = 1.0 - min(1.0, (avg_price - min_price) / (max_price - min_price))

    # Context length bonus (0.0 - 0.2 additional score)
    # Longer context = more value
    context_bonus = min(0.2, context_length / 1_000_000 * 0.1)

    # Efficiency = (70% price efficiency + 30% benchmark performance) + context bonus
    efficiency = (0.7 * normalized_price + 0.3 * benchmark_score) + context_bonus

    return min(1.0, efficiency)
```

### 1.4 Accessibility Score (15% Weight)

**Purpose:** Evaluate practical usability (licensing, API availability, documentation).

**Factors:**
1. **Licensing (40%)**
   - Open source (Apache, MIT, etc.): 1.0
   - Restricted open source (Llama license): 0.7
   - Commercial API only: 0.4
   - Unknown/Restrictive: 0.0

2. **API Stability (40%)**
   - Stable, well-established: 1.0
   - Recent but reliable: 0.7
   - Experimental/beta: 0.4
   - Unreliable/deprecated: 0.0

3. **Documentation Quality (20%)**
   - Comprehensive docs + examples: 1.0
   - Basic docs available: 0.7
   - Minimal documentation: 0.4
   - No documentation: 0.0

**Data Source:**
- OpenRouter model metadata
- Manual assessment (stored in database)
- Community feedback

**Scoring Algorithm:**
```python
def compute_accessibility_score(model_data: Dict[str, Any]) -> float:
    """
    Composite accessibility score based on licensing, API stability, docs.
    """
    license_score = get_license_score(model_data.get('license_type'))
    stability_score = get_stability_score(model_data.get('api_stability'))
    docs_score = get_documentation_score(model_data.get('documentation_quality'))

    return (0.40 * license_score +
            0.40 * stability_score +
            0.20 * docs_score)

def get_license_score(license_type: str) -> float:
    """Map license type to score."""
    license_scores = {
        'apache': 1.0, 'mit': 1.0, 'bsd': 1.0, 'cc-by': 1.0,
        'llama': 0.7, 'gemma': 0.7, 'yi': 0.7,
        'commercial': 0.4, 'api-only': 0.4,
        'unknown': 0.0, 'proprietary': 0.0
    }
    return license_scores.get(license_type.lower() if license_type else 'unknown', 0.0)

def get_stability_score(stability: str) -> float:
    """Map API stability to score."""
    stability_scores = {
        'stable': 1.0, 'production': 1.0,
        'reliable': 0.7, 'recent': 0.7,
        'beta': 0.4, 'experimental': 0.4,
        'deprecated': 0.0, 'unreliable': 0.0
    }
    return stability_scores.get(stability.lower() if stability else 'unknown', 0.7)

def get_documentation_score(docs_quality: str) -> float:
    """Map documentation quality to score."""
    docs_scores = {
        'comprehensive': 1.0, 'excellent': 1.0,
        'good': 0.7, 'basic': 0.7,
        'minimal': 0.4, 'poor': 0.4,
        'none': 0.0, 'missing': 0.0
    }
    return docs_scores.get(docs_quality.lower() if docs_quality else 'basic', 0.7)
```

---

## 2. Database Schema Extensions

### 2.1 New Columns for ModelBenchmarkCache

Add the following columns to support MSS calculation:

```python
# Chapter 4 Benchmarks
bfcl_score = db.Column(db.Float)  # Berkeley Function Calling 0-100
webdev_elo = db.Column(db.Float)  # WebDev Arena Elo score
arc_agi_score = db.Column(db.Float)  # ARC-AGI pass rate 0-100
simplebench_score = db.Column(db.Float)  # SimpleBench accuracy 0-100
canaicode_score = db.Column(db.Float)  # CanAiCode pass rate 0-100
seal_coding_score = db.Column(db.Float)  # SEAL Showdown coding BT score
gpqa_score = db.Column(db.Float)  # GPQA accuracy 0-100

# Adoption Metrics
openrouter_programming_rank = db.Column(db.Integer)  # Rank in programming category
openrouter_overall_rank = db.Column(db.Integer)  # Overall popularity rank
openrouter_market_share = db.Column(db.Float)  # Market share percentage

# Accessibility Metrics
license_type = db.Column(db.String(50))  # apache, mit, llama, commercial, etc.
api_stability = db.Column(db.String(20))  # stable, beta, experimental, deprecated
documentation_quality = db.Column(db.String(20))  # comprehensive, basic, minimal, none

# MSS Components
adoption_score = db.Column(db.Float)  # 0-1 normalized
benchmark_score = db.Column(db.Float)  # 0-1 normalized (replaces overall_score)
cost_efficiency_score = db.Column(db.Float)  # 0-1 normalized
accessibility_score = db.Column(db.Float)  # 0-1 normalized
mss = db.Column(db.Float)  # Final Model Selection Score

# Data freshness
adoption_data_updated_at = db.Column(db.DateTime(timezone=True))
benchmark_data_updated_at = db.Column(db.DateTime(timezone=True))  # Existing
accessibility_data_updated_at = db.Column(db.DateTime(timezone=True))
```

### 2.2 Migration Strategy

1. Add new columns with `ALTER TABLE` statements
2. Backfill with NULL values initially
3. Run fresh aggregation to populate new fields
4. Keep old columns (overall_score, composite_score) for transition period
5. Eventually deprecate Chapter 3 columns after frontend updates

---

## 3. Implementation Plan

### 3.1 Phase 1: Benchmark Fetchers (New Benchmarks)

Extend `benchmark_fetchers.py` with new fetcher classes:

#### BFCLFetcher
```python
class BFCLFetcher(BenchmarkFetcher):
    """Fetch BFCL scores from HuggingFace dataset."""

    def fetch_bfcl_leaderboard(self) -> Dict[str, float]:
        """
        Fetch from: gorilla-llm/Berkeley-Function-Calling-Leaderboard
        Returns: {model_name: overall_accuracy_percentage}
        """
        pass
```

#### WebDevArenaFetcher
```python
class WebDevArenaFetcher(BenchmarkFetcher):
    """Scrape WebDev Arena leaderboard."""

    def fetch_webdev_leaderboard(self) -> Dict[str, float]:
        """
        Scrape from: https://lmarena.ai/leaderboard/webdev
        Returns: {model_name: elo_score}
        """
        pass
```

#### ARCAGIFetcher
```python
class ARCAGIFetcher(BenchmarkFetcher):
    """Fetch ARC-AGI scores from LLM Stats or official site."""

    def fetch_arc_agi_leaderboard(self) -> Dict[str, float]:
        """
        Fetch from: https://llm-stats.com/benchmarks/arc-agi
        Returns: {model_name: pass_rate_percentage}
        """
        pass
```

#### SimpleBenchFetcher
```python
class SimpleBenchFetcher(BenchmarkFetcher):
    """Scrape SimpleBench results."""

    def fetch_simplebench_leaderboard(self) -> Dict[str, float]:
        """
        Scrape from: https://simple-bench.com/
        Returns: {model_name: accuracy_percentage}
        """
        pass
```

#### CanAiCodeFetcher
```python
class CanAiCodeFetcher(BenchmarkFetcher):
    """Fetch CanAiCode from HuggingFace Space."""

    def fetch_canaicode_leaderboard(self) -> Dict[str, float]:
        """
        Fetch from: https://huggingface.co/spaces/mike-ravkine/can-ai-code-results
        Returns: {model_name: pass_rate_percentage}
        """
        pass
```

#### SEALShowdownFetcher
```python
class SEALShowdownFetcher(BenchmarkFetcher):
    """Scrape SEAL Showdown coding leaderboard."""

    def fetch_seal_coding_leaderboard(self) -> Dict[str, float]:
        """
        Scrape from: https://scale.com/leaderboard/coding
        Returns: {model_name: bradley_terry_score}
        """
        pass
```

#### GPQAFetcher
```python
class GPQAFetcher(BenchmarkFetcher):
    """Fetch GPQA scores from LLM Stats."""

    def fetch_gpqa_leaderboard(self) -> Dict[str, float]:
        """
        Fetch from: https://llm-stats.com/benchmarks/gpqa
        Returns: {model_name: accuracy_percentage}
        """
        pass
```

### 3.2 Phase 2: OpenRouter Adoption Fetcher

```python
class OpenRouterAdoptionFetcher(BenchmarkFetcher):
    """Fetch model popularity rankings from OpenRouter."""

    def fetch_programming_rankings(self) -> Dict[str, int]:
        """
        Scrape from: https://openrouter.ai/rankings/programming
        Returns: {model_name: rank_position}
        """
        pass

    def fetch_overall_rankings(self) -> Dict[str, Dict[str, Any]]:
        """
        Scrape from: https://openrouter.ai/rankings
        Returns: {model_name: {rank, market_share, token_usage}}
        """
        pass
```

### 3.3 Phase 3: MSS Calculation in Service Layer

Update `model_rankings_service.py`:

```python
def aggregate_rankings(self, force_refresh: bool = False):
    """
    Main aggregation method - updated for Chapter 4 MSS.
    """
    # Fetch all data sources
    benchmark_data = self._fetch_all_benchmarks()
    adoption_data = self._fetch_adoption_metrics()
    pricing_data = self._fetch_pricing_data()

    # For each model, compute MSS
    for model_id, entry in models.items():
        # Component scores
        entry['adoption_score'] = self._compute_adoption_score(entry, adoption_data)
        entry['benchmark_score'] = self._compute_benchmark_score(entry, benchmark_data)
        entry['cost_efficiency_score'] = self._compute_cost_efficiency_score(entry)
        entry['accessibility_score'] = self._compute_accessibility_score(entry)

        # Final MSS
        entry['mss'] = (
            0.35 * entry['adoption_score'] +
            0.30 * entry['benchmark_score'] +
            0.20 * entry['cost_efficiency_score'] +
            0.15 * entry['accessibility_score']
        )

        # Store in database
        self._update_model_cache(model_id, entry)
```

### 3.4 Phase 4: Frontend Updates

Update `rankings_main.html` and `rankings.js`:

1. Replace "Overall Score" column with "MSS"
2. Add component breakdowns:
   - Adoption (35%)
   - Benchmarks (30%)
   - Cost Efficiency (20%)
   - Accessibility (15%)
3. Add detailed benchmark tooltips
4. Add OpenRouter ranking badge
5. Update sorting/filtering for MSS

---

## 4. Data Access Summary

### 4.1 API-Accessible Benchmarks
- ✅ **BFCL**: HuggingFace dataset API
- ✅ **LiveBench**: GitHub raw JSON
- ✅ **LiveCodeBench**: GitHub raw JSON
- ✅ **GPQA**: LLM Stats platform (potentially scrapable)
- ✅ **CanAiCode**: HuggingFace Spaces

### 4.2 Scraping-Required Benchmarks
- ⚠️ **WebDev Arena**: No public API, scrape HTML
- ⚠️ **ARC-AGI**: No public API, scrape from official site or LLM Stats
- ⚠️ **SimpleBench**: No public API, scrape HTML
- ⚠️ **SEAL Showdown**: No public API, scrape HTML
- ⚠️ **OpenRouter Rankings**: No public API for leaderboard data, scrape HTML

### 4.3 Existing Integrations
- ✅ **OpenRouter**: Model list, pricing, metadata
- ✅ **HuggingFace**: EvalPlus, BigCodeBench (already implemented)
- ✅ **GitHub**: SWE-bench (already implemented)

---

## 5. LaTeX Modification Recommendations

### 5.1 Benchmark Table Updates

If certain benchmarks are inaccessible or unreliable, modify Chapter 4 Table 4.X to reflect:

**Accessible with high confidence:**
- BFCL (HuggingFace dataset)
- LiveBench (GitHub JSON)
- LiveCodeBench (GitHub JSON)
- CanAiCode (HuggingFace Spaces)

**Accessible with moderate effort (scraping):**
- WebDev Arena (daily updates, scraping required)
- SEAL Showdown (Scale API, scraping required)
- GPQA (LLM Stats aggregator)

**May require alternatives:**
- SimpleBench → Consider replacing with MMLU or other reasoning benchmarks if scraping proves unreliable
- ARC-AGI → Can use LLM Stats aggregator or official GitHub data

### 5.2 Adoption Metrics Clarification

Update text to clarify:
> "Model adoption is measured using OpenRouter's public programming category rankings, which reflect real-world usage patterns across thousands of applications. Rankings are scraped from the OpenRouter public leaderboard due to the absence of a dedicated API for usage analytics."

### 5.3 Accessibility Scoring

Add implementation note:
> "Accessibility scoring combines automated metadata from OpenRouter API (licensing information) with manual assessment of API stability and documentation quality. Scores are reviewed quarterly to reflect changes in model availability and support."

---

## 6. Implementation Timeline

### Week 1: Benchmark Fetchers
- [ ] Implement BFCL fetcher (HuggingFace dataset)
- [ ] Implement WebDev Arena scraper
- [ ] Implement ARC-AGI fetcher (LLM Stats)
- [ ] Implement SimpleBench scraper

### Week 2: More Fetchers + Adoption
- [ ] Implement CanAiCode fetcher
- [ ] Implement SEAL Showdown scraper
- [ ] Implement GPQA fetcher
- [ ] Implement OpenRouter rankings scraper

### Week 3: Database + Service Layer
- [ ] Create database migration for new columns
- [ ] Update model_rankings_service.py with MSS calculation
- [ ] Add accessibility scoring logic
- [ ] Test aggregation with real data

### Week 4: Frontend + Testing
- [ ] Update rankings UI for MSS components
- [ ] Add detailed benchmark tooltips
- [ ] End-to-end testing
- [ ] Documentation updates

---

## 7. Success Metrics

1. **Data Coverage:** ≥80% of models have at least 5/9 benchmarks populated
2. **Adoption Data:** ≥90% of models have OpenRouter rank (top 100 models)
3. **Update Frequency:** Benchmarks refresh weekly, adoption data daily
4. **MSS Distribution:** Clear differentiation between top/mid/low-tier models
5. **User Validation:** MSS rankings align with practitioner expectations

---

## 8. Risk Mitigation

### 8.1 Scraping Reliability
- **Risk:** Websites change structure, breaking scrapers
- **Mitigation:**
  - Use robust parsing libraries (BeautifulSoup, lxml)
  - Implement fallback data sources
  - Cache last-known-good data
  - Add monitoring alerts for scraper failures

### 8.2 OpenRouter Ranking Access
- **Risk:** No public API for usage statistics
- **Mitigation:**
  - Primary: Web scraping with regular structure checks
  - Fallback: Manual recording of top 20 models monthly
  - Future: Request API access from OpenRouter team
  - Alternative: Use proxy metrics (GitHub stars, HuggingFace downloads)

### 8.3 Benchmark Availability
- **Risk:** Some benchmarks may discontinue or change methodology
- **Mitigation:**
  - Design modular fetcher system (easy to swap)
  - Document alternative benchmarks in LaTeX
  - Weight distribution allows missing benchmarks (need ≥50% coverage)
  - Maintain benchmark provenance metadata

### 8.4 Data Staleness
- **Risk:** Cached data becomes outdated
- **Mitigation:**
  - TTL per data source (adoption: 1 day, benchmarks: 7 days)
  - Force refresh API endpoint for manual updates
  - Automated weekly cron job
  - Display "last updated" timestamps in UI

---

## 9. Appendix: API Endpoints & Resources

### Benchmark Sources

| Benchmark | URL | Access Method | Update Freq |
|-----------|-----|---------------|-------------|
| BFCL | https://gorilla.cs.berkeley.edu/leaderboard.html | HuggingFace dataset API | Monthly |
| WebDev Arena | https://lmarena.ai/leaderboard/webdev | Web scraping | Daily |
| LiveBench | https://livebench.ai/ | GitHub raw JSON | Weekly |
| LiveCodeBench | https://livecodebench.github.io/ | GitHub raw JSON | Weekly |
| ARC-AGI | https://llm-stats.com/benchmarks/arc-agi | Web scraping (LLM Stats) | Monthly |
| SimpleBench | https://simple-bench.com/ | Web scraping | As updated |
| CanAiCode | https://huggingface.co/spaces/mike-ravkine/can-ai-code-results | HuggingFace Spaces API | Weekly |
| SEAL Showdown | https://scale.com/leaderboard/coding | Web scraping | Daily |
| GPQA | https://llm-stats.com/benchmarks/gpqa | Web scraping (LLM Stats) | Monthly |

### Adoption Sources

| Source | URL | Access Method | Update Freq |
|--------|-----|---------------|-------------|
| OpenRouter Rankings | https://openrouter.ai/rankings | Web scraping | Daily |
| OpenRouter Programming | https://openrouter.ai/rankings/programming | Web scraping | Daily |

### API Documentation

| API | Documentation | Authentication |
|-----|---------------|----------------|
| OpenRouter | https://openrouter.ai/docs/api/reference/overview | API Key (existing) |
| HuggingFace | https://huggingface.co/docs/api-inference/index | Token (existing) |
| GitHub Raw | Direct URL access | None |

---

## 10. References

Sources from research (2026-01-10):

**BFCL:**
- [Berkeley Function Calling Leaderboard (BFCL)](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard)
- [BFCL V4 Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html)
- [HuggingFace Dataset](https://huggingface.co/datasets/gorilla-llm/Berkeley-Function-Calling-Leaderboard)

**WebDev Arena:**
- [WebDev Leaderboard - Best AI Models for Coding](https://lmarena.ai/leaderboard/webdev)
- [WebDev Arena Leaderboard](https://web.lmarena.ai/leaderboard)
- [WebDev Arena | Epoch AI](https://epoch.ai/benchmarks/webdev-arena)

**ARC-AGI:**
- [ARC Prize 2025 Results and Analysis](https://arcprize.org/blog/arc-prize-2025-results-analysis)
- [ARC Prize - Leaderboard](https://arcprize.org/leaderboard)
- [ARC-AGI Leaderboard](https://llm-stats.com/benchmarks/arc-agi)

**SimpleBench:**
- [SimpleBench](https://simple-bench.com/)
- [SimpleBench | Epoch AI](https://epoch.ai/benchmarks/simplebench)

**CanAiCode:**
- [Can Ai Code Results - HuggingFace Space](https://huggingface.co/spaces/mike-ravkine/can-ai-code-results)

**SEAL Showdown:**
- [SEAL Showdown: Human-Evaluated AI Leaderboard](https://scale.com/showdown)
- [SEAL LLM Leaderboards: Expert-Driven Evaluations](https://scale.com/leaderboard)
- [Coding](https://scale.com/leaderboard/coding)

**GPQA:**
- [GPQA Leaderboard](https://llm-stats.com/benchmarks/gpqa)
- [[2311.12022] GPQA: A Graduate-Level Google-Proof Q&A Benchmark](https://arxiv.org/abs/2311.12022)

**OpenRouter:**
- [OpenRouter API Reference](https://openrouter.ai/docs/api/reference/overview)
- [LLM Rankings | OpenRouter](https://openrouter.ai/rankings)
- [Usage Accounting](https://openrouter.ai/docs/guides/guides/usage-accounting)

---

**End of Document**
