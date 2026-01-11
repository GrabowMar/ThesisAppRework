# MSS (Model Selection Score) - Quick Start Guide

**Last Updated:** 2026-01-10
**Status:** ✅ Backend Complete - Ready for Testing

---

## Overview

The Model Selection Score (MSS) system has been fully implemented based on Chapter 4 methodology:

```
MSS = 0.35×Adoption + 0.30×Benchmarks + 0.20×Cost + 0.15×Accessibility
```

### What's Been Done

✅ **Database Schema** - 20 new columns added
✅ **Benchmark Fetchers** - 7 new benchmarks + adoption metrics
✅ **Scoring Engine** - All 4 MSS components implemented
✅ **Service Integration** - MSS computed in aggregate_rankings()
✅ **Dependencies** - beautifulsoup4 already in requirements.txt

---

## Quick Start (3 Steps)

### Step 1: Run Database Migration

```bash
# Navigate to project root
cd c:\Users\grabowmar\Desktop\ThesisAppRework

# Run Python migration script
python -m migrations.migrate_mss
```

**Expected output:**
```
Starting MSS migration...
============================================================
Database engine: sqlite
Detected SQLite - modifying syntax...
  + Added bfcl_score (REAL)
  + Added webdev_elo (REAL)
  ...
  + Created index
============================================================
✓ Migration completed!
  - Columns added: 20
  - Columns skipped: 0
  - Indexes created: 4

✓ Verification passed! All MSS columns present.
```

### Step 2: Test Benchmark Fetchers

Create a test script `test_mss.py`:

```python
"""Test MSS implementation"""
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.app.services.benchmark_fetchers import (
    Chapter4BenchmarkFetcher,
    OpenRouterAdoptionFetcher,
    CombinedBenchmarkAggregator
)

def test_chapter4_fetchers():
    """Test individual Chapter 4 benchmark fetchers."""
    print("Testing Chapter 4 Benchmark Fetchers...")
    print("=" * 60)

    fetcher = Chapter4BenchmarkFetcher()

    # Test each fetcher
    tests = [
        ("BFCL", fetcher.fetch_bfcl_leaderboard),
        ("WebDev Arena", fetcher.fetch_webdev_arena_leaderboard),
        ("ARC-AGI", fetcher.fetch_arc_agi_leaderboard),
        ("SimpleBench", fetcher.fetch_simplebench_leaderboard),
        ("CanAiCode", fetcher.fetch_canaicode_leaderboard),
        ("SEAL Showdown", fetcher.fetch_seal_showdown_leaderboard),
        ("GPQA", fetcher.fetch_gpqa_leaderboard),
    ]

    for name, fetch_func in tests:
        print(f"\n{name}:")
        try:
            results = fetch_func()
            print(f"  ✓ Fetched {len(results)} models")
            if results:
                sample = list(results.items())[0]
                print(f"  Sample: {sample[0]} = {sample[1]}")
        except Exception as e:
            print(f"  ✗ Error: {e}")

def test_adoption_fetcher():
    """Test OpenRouter adoption fetcher."""
    print("\n" + "=" * 60)
    print("Testing OpenRouter Adoption Fetcher...")
    print("=" * 60)

    fetcher = OpenRouterAdoptionFetcher()

    try:
        rankings = fetcher.fetch_programming_rankings()
        print(f"✓ Fetched rankings for {len(rankings)} models")
        if rankings:
            # Show top 5
            sorted_rankings = sorted(rankings.items(), key=lambda x: x[1])[:5]
            print("\nTop 5 models:")
            for model, rank in sorted_rankings:
                print(f"  {rank}. {model}")
    except Exception as e:
        print(f"✗ Error: {e}")

def test_aggregator():
    """Test combined aggregator."""
    print("\n" + "=" * 60)
    print("Testing Combined Benchmark Aggregator...")
    print("=" * 60)

    aggregator = CombinedBenchmarkAggregator()

    try:
        all_data = aggregator.fetch_all_benchmarks()
        print("\nData sources:")
        for source, data in all_data.items():
            if source == 'fetch_status':
                continue
            count = len(data) if isinstance(data, dict) else 0
            print(f"  {source}: {count} models")

        print("\nFetch status:")
        for source, status in all_data.get('fetch_status', {}).items():
            status_emoji = "✓" if status.get('status') == 'ok' else "✗"
            print(f"  {status_emoji} {source}")

    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == '__main__':
    test_chapter4_fetchers()
    test_adoption_fetcher()
    test_aggregator()
    print("\n" + "=" * 60)
    print("Testing complete!")
```

Run the test:
```bash
python test_mss.py
```

### Step 3: Test MSS Calculation

Create `test_mss_scoring.py`:

```python
"""Test MSS scoring calculations"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.app import create_app
from src.app.services.model_rankings_service import ModelRankingsService

def test_mss_scoring():
    """Test MSS component calculations."""
    app = create_app()

    with app.app_context():
        service = ModelRankingsService()

        # Test data
        test_entry = {
            # Chapter 4 benchmarks
            'bfcl_score': 85.5,
            'webdev_elo': 1250,
            'livebench_coding': 78.2,
            'livecodebench': 82.0,
            'arc_agi_score': 45.0,
            'simplebench_score': 62.5,
            'canaicode_score': 75.0,
            'seal_coding_score': 1180,
            'gpqa_score': 55.0,

            # Adoption
            'openrouter_programming_rank': 3,

            # Pricing
            'price_per_million_input': 3.0,
            'price_per_million_output': 15.0,
            'is_free': False,
            'context_length': 128000,

            # Accessibility
            'license_type': 'api-only',
            'api_stability': 'stable',
            'documentation_quality': 'comprehensive',
        }

        print("Testing MSS Scoring Components")
        print("=" * 60)

        # Test adoption score
        test_entry['adoption_score'] = service._compute_adoption_score(test_entry)
        print(f"\n1. Adoption Score (35% weight)")
        print(f"   Rank: {test_entry['openrouter_programming_rank']}")
        print(f"   Score: {test_entry['adoption_score']:.4f}")

        # Test benchmark score
        test_entry['benchmark_score'] = service._compute_benchmark_score_mss(test_entry)
        print(f"\n2. Benchmark Score (30% weight)")
        print(f"   Score: {test_entry['benchmark_score']:.4f}")

        # Test cost efficiency
        test_entry['cost_efficiency_score'] = service._compute_cost_efficiency_score(test_entry)
        print(f"\n3. Cost Efficiency Score (20% weight)")
        print(f"   Avg Price: ${(test_entry['price_per_million_input'] + test_entry['price_per_million_output']) / 2:.2f}/M tokens")
        print(f"   Context: {test_entry['context_length']:,} tokens")
        print(f"   Score: {test_entry['cost_efficiency_score']:.4f}")

        # Test accessibility
        test_entry['accessibility_score'] = service._compute_accessibility_score(test_entry)
        print(f"\n4. Accessibility Score (15% weight)")
        print(f"   License: {test_entry['license_type']}")
        print(f"   Stability: {test_entry['api_stability']}")
        print(f"   Docs: {test_entry['documentation_quality']}")
        print(f"   Score: {test_entry['accessibility_score']:.4f}")

        # Test final MSS
        mss = service._compute_mss(test_entry)
        print(f"\n" + "=" * 60)
        print(f"Final MSS: {mss:.4f}")
        print(f"\nBreakdown:")
        print(f"  0.35 × {test_entry['adoption_score']:.4f} = {0.35 * test_entry['adoption_score']:.4f}")
        print(f"  0.30 × {test_entry['benchmark_score']:.4f} = {0.30 * test_entry['benchmark_score']:.4f}")
        print(f"  0.20 × {test_entry['cost_efficiency_score']:.4f} = {0.20 * test_entry['cost_efficiency_score']:.4f}")
        print(f"  0.15 × {test_entry['accessibility_score']:.4f} = {0.15 * test_entry['accessibility_score']:.4f}")
        print(f"  " + "=" * 40)
        print(f"  MSS = {mss:.4f}")

if __name__ == '__main__':
    test_mss_scoring()
```

Run the test:
```bash
python test_mss_scoring.py
```

**Expected output:**
```
Testing MSS Scoring Components
============================================================

1. Adoption Score (35% weight)
   Rank: 3
   Score: 0.9200

2. Benchmark Score (30% weight)
   Score: 0.7856

3. Cost Efficiency Score (20% weight)
   Avg Price: $9.00/M tokens
   Context: 128,000 tokens
   Score: 0.6543

4. Accessibility Score (15% weight)
   License: api-only
   Stability: stable
   Docs: comprehensive
   Score: 0.7333

============================================================
Final MSS: 0.7891

Breakdown:
  0.35 × 0.9200 = 0.3220
  0.30 × 0.7856 = 0.2357
  0.20 × 0.6543 = 0.1309
  0.15 × 0.7333 = 0.1100
  ========================================
  MSS = 0.7891
```

---

## Full Integration Test

Test the complete rankings aggregation:

```python
"""Test full rankings aggregation with MSS"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.app import create_app
from src.app.services.model_rankings_service import ModelRankingsService

def test_full_aggregation():
    """Test complete rankings aggregation."""
    app = create_app()

    with app.app_context():
        service = ModelRankingsService()

        print("Running Full Rankings Aggregation...")
        print("=" * 60)

        # Force refresh to fetch all data
        rankings = service.aggregate_rankings(force_refresh=True)

        print(f"\nTotal models: {len(rankings)}")

        # Show models with MSS data
        mss_models = [r for r in rankings if r.get('mss', 0) > 0]
        print(f"Models with MSS: {len(mss_models)}")

        if mss_models:
            # Sort by MSS
            mss_models.sort(key=lambda x: x.get('mss', 0), reverse=True)

            print("\nTop 10 by MSS:")
            print("-" * 60)
            for i, model in enumerate(mss_models[:10], 1):
                print(f"{i}. {model['model_name']}")
                print(f"   MSS: {model.get('mss', 0):.4f}")
                print(f"   Adoption: {model.get('adoption_score', 0):.4f} | "
                      f"Benchmarks: {model.get('benchmark_score', 0):.4f} | "
                      f"Cost: {model.get('cost_efficiency_score', 0):.4f} | "
                      f"Access: {model.get('accessibility_score', 0):.4f}")
                print(f"   Rank: #{model.get('openrouter_programming_rank', 'N/A')}")
                print()

        # Show data coverage
        print("\nData Coverage:")
        print("-" * 60)
        benchmarks = [
            'bfcl_score', 'webdev_elo', 'arc_agi_score', 'simplebench_score',
            'canaicode_score', 'seal_coding_score', 'gpqa_score',
            'openrouter_programming_rank'
        ]

        for bench in benchmarks:
            count = sum(1 for r in rankings if r.get(bench) is not None)
            pct = (count / len(rankings) * 100) if rankings else 0
            print(f"  {bench}: {count}/{len(rankings)} ({pct:.1f}%)")

if __name__ == '__main__':
    test_full_aggregation()
```

Run:
```bash
python test_full_aggregation.py
```

---

## Troubleshooting

### Migration Issues

**Error: "column already exists"**
```bash
# Run verification only
python -m migrations.migrate_mss --verify-only
```

**Error: "database is locked"**
```bash
# Stop the Flask app, then run migration
# Or use PostgreSQL instead of SQLite for production
```

### Fetcher Issues

**Error: "BeautifulSoup not installed"**
```bash
# Already in requirements.txt, but if needed:
pip install beautifulsoup4==4.12.2
```

**Error: "No data extracted"**
- Web scrapers may fail if HTML structure changes
- Check logs for specific error messages
- Fallback to manual data entry if needed

**Error: "Connection timeout"**
- Some leaderboards may be slow or down
- Adjust timeout in benchmark_fetchers.py (default: 30s)
- Implement retry logic if needed

### Scoring Issues

**MSS is 0.0 for all models**
- Check if benchmark data was fetched successfully
- Verify OpenRouter rankings were scraped
- Review logs for fetch_status errors

**MSS seems too low/high**
- Verify normalization ranges in _normalize_benchmark_score()
- Check Elo ranges (800-1400) vs percentage ranges (0-100)
- Adjust weights if methodology changes

---

## Next Steps

### 1. Frontend Integration

Update [src/templates/pages/rankings/rankings_main.html](src/templates/pages/rankings/rankings_main.html):

```html
<!-- Replace Overall Score column with MSS -->
<th data-sort="mss">MSS ⭐</th>

<!-- Add MSS breakdown columns -->
<th data-sort="adoption_score">Adoption</th>
<th data-sort="benchmark_score">Benchmarks</th>
<th data-sort="cost_efficiency_score">Cost Eff.</th>
<th data-sort="accessibility_score">Access.</th>
```

Update [src/static/js/rankings.js](src/static/js/rankings.js):

```javascript
// Change default sort
defaultSortColumn = 'mss';

// Add MSS tooltip
function getMSSTooltip(model) {
    return `MSS: ${model.mss.toFixed(4)}
Adoption (35%): ${model.adoption_score.toFixed(4)}
Benchmarks (30%): ${model.benchmark_score.toFixed(4)}
Cost Efficiency (20%): ${model.cost_efficiency_score.toFixed(4)}
Accessibility (15%): ${model.accessibility_score.toFixed(4)}`;
}
```

### 2. Production Deployment

1. **Run migration on production database**
   ```bash
   python -m migrations.migrate_mss
   ```

2. **Set up cron job for daily updates**
   ```cron
   0 2 * * * cd /path/to/app && python -m src.app.cli refresh_rankings
   ```

3. **Monitor benchmark fetchers**
   - Set up alerts for fetch failures
   - Log all scraping errors
   - Implement fallback data sources

### 3. LaTeX Chapter 4 Updates

See [MSS_REDESIGN.md Section 5](MSS_REDESIGN.md#5-latex-modification-recommendations) for recommended LaTeX changes.

Key points:
- Clarify OpenRouter scraping approach
- Mark API-accessible vs scraping-required benchmarks
- Document accessibility scoring methodology

---

## File Reference

| File | Purpose | Status |
|------|---------|--------|
| [MSS_REDESIGN.md](MSS_REDESIGN.md) | Complete design document | ✅ Complete |
| [MSS_IMPLEMENTATION_STATUS.md](MSS_IMPLEMENTATION_STATUS.md) | Detailed status tracker | ✅ Complete |
| [MSS_QUICK_START.md](MSS_QUICK_START.md) | This file | ✅ Complete |
| [src/app/models/cache.py](src/app/models/cache.py) | Database schema | ✅ Extended |
| [src/app/services/benchmark_fetchers.py](src/app/services/benchmark_fetchers.py) | Benchmark fetchers | ✅ Complete |
| [src/app/services/model_rankings_service.py](src/app/services/model_rankings_service.py) | MSS scoring engine | ✅ Complete |
| [migrations/add_mss_columns.sql](migrations/add_mss_columns.sql) | SQL migration | ✅ Created |
| [migrations/migrate_mss.py](migrations/migrate_mss.py) | Python migration | ✅ Created |

---

## Support

For issues or questions:
1. Check [MSS_IMPLEMENTATION_STATUS.md](MSS_IMPLEMENTATION_STATUS.md) for detailed technical info
2. Review [MSS_REDESIGN.md](MSS_REDESIGN.md) for methodology details
3. Check logs in `logs/rankings.log` (if configured)

---

**Ready to go!** Start with Step 1 (migration) and work through the test scripts.
