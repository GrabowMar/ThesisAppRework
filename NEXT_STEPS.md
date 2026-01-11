# Next Steps - Rankings System Implementation

## ✅ What's Been Completed

1. ✅ **Research & Design** - Comprehensive analysis of available APIs
2. ✅ **Modular Fetchers** - `benchmark_fetchers.py` with 6 data sources
3. ✅ **Database Schema** - Enhanced `ModelBenchmarkCache` with performance metrics
4. ✅ **Service Integration** - Updated `model_rankings_service.py` with new fetchers
5. ✅ **Composite Scoring** - Methodology-aligned algorithm (50% coding, 30% performance, 20% value)

## 🔄 What Remains

### Step 1: Database Migration (REQUIRED) ⚠️

The new database columns need to be created before the system can function.

**Option A: Using Flask-Migrate (Recommended)**
```bash
# From your project root
cd src

# Create migration
flask db migrate -m "Add performance metrics to ModelBenchmarkCache"

# Review the migration file in migrations/versions/
# Make sure it includes all 10 new columns

# Apply migration
flask db upgrade
```

**Option B: Manual SQL (if Flask-Migrate not configured)**
```sql
ALTER TABLE model_benchmark_cache
ADD COLUMN ttft_median FLOAT,
ADD COLUMN ttft_p95 FLOAT,
ADD COLUMN throughput_median FLOAT,
ADD COLUMN throughput_p95 FLOAT,
ADD COLUMN total_latency_median FLOAT,
ADD COLUMN total_latency_p95 FLOAT,
ADD COLUMN quality_index FLOAT,
ADD COLUMN overall_score FLOAT,
ADD COLUMN benchmark_data_updated_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN performance_data_updated_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN pricing_data_updated_at TIMESTAMP WITH TIME ZONE;
```

### Step 2: Test the Backend (REQUIRED)

Verify the new fetchers and scoring work correctly.

```python
# Run this in Python shell or create test script
from app import create_app
from app.services.model_rankings_service import get_rankings_service
import json

app = create_app()
with app.app_context():
    service = get_rankings_service()

    # Test 1: Fetch benchmarks
    print("Testing benchmark fetchers...")
    bench_data = service.benchmark_aggregator.fetch_all_benchmarks()
    print(f"✓ EvalPlus: {len(bench_data['evalplus'])} models")
    print(f"✓ SWE-bench: {len(bench_data['swebench'])} models")
    print(f"✓ BigCodeBench: {len(bench_data['bigcodebench'])} models")
    print(f"✓ Performance: {len(bench_data['performance'])} models")

    # Test 2: Aggregate rankings
    print("\nAggregating rankings...")
    rankings = service.aggregate_rankings(force_refresh=True)
    print(f"✓ Total models: {len(rankings)}")

    # Test 3: Check data quality
    with_benchmarks = [r for r in rankings if r.get('composite_score')]
    with_performance = [r for r in rankings if r.get('ttft_median')]
    with_overall = [r for r in rankings if r.get('overall_score')]

    print(f"✓ Models with benchmark data: {len(with_benchmarks)}")
    print(f"✓ Models with performance data: {len(with_performance)}")
    print(f"✓ Models with overall score: {len(with_overall)}")

    # Test 4: Show sample model
    if rankings:
        sample = rankings[0]
        print(f"\n✓ Sample Model: {sample['model_name']}")
        print(f"  Coding Score: {sample.get('composite_score')}")
        print(f"  Overall Score: {sample.get('overall_score')}")
        print(f"  TTFT: {sample.get('ttft_median')}")
        print(f"  Throughput: {sample.get('throughput_median')}")
        print(f"  Data Sources: {sample.get('sources')}")
```

**Expected Results:**
- EvalPlus: 0-100 models (depends on GitHub availability)
- SWE-bench: 40-80 models
- BigCodeBench: 0-60 models (depends on HuggingFace)
- Performance: 10-20 models (fallback data)
- Composite scores: 70%+ of models
- Overall scores: 70%+ of models

### Step 3: Frontend Updates (OPTIONAL but RECOMMENDED)

**File:** `src/templates/pages/rankings/partials/_rankings_content.html`

Add new table headers:
```html
<th class="text-nowrap sortable" data-column="ttft" data-type="number" title="Time to First Token (seconds)">TTFT</th>
<th class="text-nowrap sortable" data-column="throughput" data-type="number" title="Tokens per second">Throughput</th>
<th class="text-nowrap sortable" data-column="quality" data-type="number" title="Quality Index">Quality</th>
<th class="text-nowrap sortable" data-column="overall" data-type="number" title="Overall Score">Overall</th>
```

**File:** `src/static/js/rankings.js`

Add sort key mapping:
```javascript
sort_key_map = {
    // ... existing mappings ...
    'ttft': 'ttft_median',
    'throughput': 'throughput_median',
    'quality': 'quality_index',
    'overall': 'overall_score'
}
```

Add rendering for new columns in `renderRankingsTable()`:
```javascript
return `
    <tr ...>
        ...existing columns...
        <td>${formatTime(model.ttft_median)}</td>
        <td>${formatThroughput(model.throughput_median)}</td>
        <td class="${getScoreClass(model.quality_index, 85, 70)}">
            ${formatScore(model.quality_index)}
        </td>
        <td class="fw-bold ${getScoreClass(model.overall_score, 80, 60)}">
            ${formatScore(model.overall_score)}
        </td>
    </tr>
`;
```

Add formatting helpers:
```javascript
function formatTime(seconds) {
    if (!seconds) return '—';
    return seconds.toFixed(2) + 's';
}

function formatThroughput(tps) {
    if (!tps) return '—';
    return Math.round(tps) + ' t/s';
}
```

### Step 4: Data Freshness Indicators (OPTIONAL)

Show when data was last updated:

```html
<!-- In rankings table or as a badge -->
<span class="badge bg-info-lt" title="Benchmark data updated {{ benchmark_data_updated_at }}">
    <i class="fas fa-clock"></i> Updated {{ time_ago(benchmark_data_updated_at) }}
</span>
```

Add JavaScript helper:
```javascript
function timeAgo(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    const now = new Date();
    const days = Math.floor((now - date) / (1000 * 60 * 60 * 24));

    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    if (days < 30) return `${Math.floor(days/7)} weeks ago`;
    return `${Math.floor(days/30)} months ago`;
}
```

### Step 5: Configuration (OPTIONAL)

Add environment variables to control data sources:

```bash
# .env file
HF_TOKEN=your_huggingface_token_here
OPENROUTER_API_KEY=your_openrouter_key_here

# Cache duration (hours)
RANKINGS_CACHE_HOURS=24

# Enable/disable specific fetchers
ENABLE_EVALPLUS=true
ENABLE_SWEBENCH=true
ENABLE_BIGCODEBENCH=true
ENABLE_LIVEBENCH=true
ENABLE_ARTIFICIAL_ANALYSIS=true
```

## 🎯 Testing Checklist

After completing the steps above:

### Backend Tests
- [ ] Database migration applied successfully
- [ ] Can fetch benchmarks from all sources (check logs for errors)
- [ ] Rankings aggregation completes without errors
- [ ] Cache saves correctly to database
- [ ] Composite scores calculated for all models with benchmark data
- [ ] Overall scores calculated for models with complete data
- [ ] Data freshness timestamps populated

### Frontend Tests (if updated)
- [ ] Rankings page loads without errors
- [ ] Performance columns visible in table
- [ ] Can sort by TTFT/throughput/quality/overall
- [ ] Data freshness indicators show correct ages
- [ ] Export to CSV includes new columns
- [ ] Filters work correctly with new metrics

### Data Quality Tests
- [ ] At least 70% of models have benchmark data
- [ ] Top 20 models have comprehensive scores
- [ ] Performance data present for major providers (OpenAI, Anthropic, DeepSeek, Google)
- [ ] Price efficiency scores look reasonable
- [ ] Model name matching works (OpenRouter ID → benchmark ID)

## ⚠️ Known Limitations

### Artificial Analysis Data
**Problem:** No official API available.
**Current Solution:** Manual fallback data for 10-20 top models.
**Impact:** Most models won't have TTFT/throughput data.
**Workaround:** Update fallback data monthly from artificialanalysis.ai/leaderboards/models

### HuggingFace Datasets
**Problem:** Some benchmark datasets may not have public JSON endpoints.
**Current Solution:** Fallback to GitHub raw JSON or manual data.
**Impact:** Lower data coverage for EvalPlus and BigCodeBench.
**Workaround:** Keep fallback data up to date in service methods.

### Model Name Matching
**Problem:** Different sources use different naming conventions.
**Current Solution:** Fuzzy matching with `normalize_model_name()` and manual mappings.
**Impact:** Some models may not match across sources.
**Workaround:** Add explicit mappings in `MODEL_NAME_MAPPINGS` for common models.

## 📚 Documentation

- **[RANKINGS_REDESIGN.md](RANKINGS_REDESIGN.md)** - Complete design document
- **[RANKINGS_IMPLEMENTATION_SUMMARY.md](RANKINGS_IMPLEMENTATION_SUMMARY.md)** - What's been built
- **This file** - Step-by-step guide to finish implementation

## 🤔 FAQ

**Q: Do I need to implement all the frontend changes?**
A: No, the backend will work fine without frontend updates. You just won't see the new performance columns in the UI. The data will still be returned via the API.

**Q: What if API fetchers fail?**
A: Each fetcher has fallback data. The system will gracefully degrade to using cached/fallback data and continue functioning.

**Q: How often should I refresh the rankings?**
A: The system caches for 24 hours by default. Force refresh only when:
- Deploying new benchmark data
- Major model releases
- Debugging data issues

**Q: Can I modify the composite scoring weights?**
A: Yes! Update the weights in:
- `_compute_overall_score()` - overall composition (coding/performance/value)
- `_compute_performance_score()` - performance sub-components
- `_compute_value_score()` - value sub-components
- `_compute_default_composite()` - coding benchmark weights

**Q: How do I add a new benchmark source?**
A:
1. Add fetcher method to appropriate class in `benchmark_fetchers.py`
2. Call it in `CombinedBenchmarkAggregator.fetch_all_benchmarks()`
3. Add mapping in `aggregate_rankings()` in `model_rankings_service.py`
4. Update database schema if needed

## 🚀 Quick Start Command

Run this to test everything at once:

```bash
# 1. Apply migration
flask db upgrade

# 2. Test in Python
python << 'EOF'
from app import create_app
from app.services.model_rankings_service import get_rankings_service

app = create_app()
with app.app_context():
    service = get_rankings_service()
    rankings = service.aggregate_rankings(force_refresh=True)

    print(f"\n{'='*60}")
    print(f"RANKINGS SYSTEM TEST RESULTS")
    print(f"{'='*60}")
    print(f"Total models: {len(rankings)}")
    print(f"With benchmarks: {len([r for r in rankings if r.get('composite_score')])}")
    print(f"With performance: {len([r for r in rankings if r.get('ttft_median')])}")
    print(f"With overall score: {len([r for r in rankings if r.get('overall_score')])}")
    print(f"{'='*60}\n")

    if rankings:
        top5 = rankings[:5]
        print("TOP 5 MODELS:")
        for i, model in enumerate(top5, 1):
            print(f"{i}. {model['model_name']}")
            print(f"   Coding: {model.get('composite_score')}")
            print(f"   Overall: {model.get('overall_score')}")
            print(f"   TTFT: {model.get('ttft_median')}s")
            print(f"   Throughput: {model.get('throughput_median')} t/s")
            print()
EOF

# 3. Check rankings page
echo "Now visit http://localhost:5000/rankings to see the results!"
```

## 📞 Support

If you encounter issues:
1. Check logs for API fetch errors
2. Verify environment variables are set
3. Ensure database migration completed
4. Review `fetch_status` in rankings data
5. Check [RANKINGS_IMPLEMENTATION_SUMMARY.md](RANKINGS_IMPLEMENTATION_SUMMARY.md) troubleshooting section

Good luck! 🎉
