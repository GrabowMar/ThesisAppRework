"""
Benchmark Data Fetchers
=======================

Modular fetchers for various AI model benchmark leaderboards.
Each fetcher is responsible for a specific data source and returns normalized data.

Chapter 4 MSS Methodology (from thesis):
- MSS = 0.35×Adoption + 0.30×Benchmarks + 0.20×CostEfficiency + 0.15×Accessibility
- Benchmarks: BFCL, WebDev Arena, LiveBench, LiveCodeBench, ARC-AGI, SimpleBench,
              CanAiCode, SEAL Showdown, GPQA

Data sources are curated from public leaderboards (Jan 2026) with fallback data
to ensure fast page loads. Live fetching available on-demand via refresh button.
"""

import json
import logging
import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# CURATED STATIC DATA - Chapter 4 Benchmarks (Updated Jan 2026)
# =============================================================================
# Sources: BFCL (gorilla.cs.berkeley.edu), WebDev Arena (lmarena.ai),
#          LiveBench (livebench.ai), ARC-AGI (arcprize.org), SimpleBench,
#          CanAiCode, SEAL Leaderboards (scale.com), LLM Stats (llm-stats.com)
# =============================================================================

# Static data removed to enforce fail-fast behavior and prevent stale/mock data usage.


class BenchmarkFetcher:
    """Base class for benchmark fetchers."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.logger = logger
        self._last_fetch_time = None
        self._last_error = None

    def fetch(self) -> Dict[str, Dict[str, float]]:
        """Fetch benchmark data. Must be implemented by subclasses."""
        raise NotImplementedError

    def get_status(self) -> Dict[str, Any]:
        """Get fetcher status."""
        return {
            'last_fetch': self._last_fetch_time.isoformat() if self._last_fetch_time else None,
            'last_error': self._last_error,
            'status': 'ok' if self._last_error is None else 'error'
        }


class HuggingFaceBenchmarkFetcher(BenchmarkFetcher):
    """Fetcher for HuggingFace-hosted benchmark datasets."""

    def __init__(self, hf_token: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.hf_token = hf_token
        self.base_url = "https://huggingface.co"

    def fetch_evalplus_leaderboard(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch EvalPlus (HumanEval+ and MBPP+) leaderboard.

        Returns dict: {model_id: {'humaneval_plus': score, 'mbpp_plus': score}}
        """
        try:
            self.logger.info("Fetching EvalPlus leaderboard from HuggingFace...")

            # EvalPlus leaderboard is available as a Space or dataset
            # Try fetching from the leaderboard page's data endpoint
            url = "https://huggingface.co/spaces/evalplus/leaderboard/resolve/main/data.json"

            headers = {'Accept': 'application/json'}
            if self.hf_token:
                headers['Authorization'] = f'Bearer {self.hf_token}'

            response = requests.get(url, headers=headers, timeout=self.timeout)

            if response.status_code == 404:
                # Fallback: scrape from leaderboard HTML or use alternative endpoint
                self.logger.warning("EvalPlus data.json not found")
                return {}

            response.raise_for_status()
            data = response.json()

            results = {}
            # Parse the data structure (format varies by leaderboard)
            # Typically: [{model: str, humaneval_plus: float, mbpp_plus: float}, ...]
            for entry in data:
                model_id = entry.get('model', '')
                if model_id:
                    results[model_id.lower()] = {
                        'humaneval_plus': entry.get('humaneval_plus') or entry.get('humaneval+'),
                        'mbpp_plus': entry.get('mbpp_plus') or entry.get('mbpp+')
                    }

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None
            self.logger.info(f"Fetched EvalPlus data for {len(results)} models")
            return results

        except Exception as e:
            self.logger.error(f"Error fetching EvalPlus leaderboard: {e}")
            self._last_error = str(e)
            return {}

    # _fetch_evalplus_fallback removed

    def fetch_bigcodebench_leaderboard(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch BigCodeBench leaderboard from HuggingFace Space.

        Returns dict: {model_id: {'bigcodebench_hard': score, 'bigcodebench_full': score}}
        """
        try:
            self.logger.info("Fetching BigCodeBench leaderboard...")

            # BigCodeBench leaderboard data endpoint
            url = "https://huggingface.co/spaces/bigcode/bigcodebench-leaderboard/resolve/main/data.json"

            headers = {'Accept': 'application/json'}
            if self.hf_token:
                headers['Authorization'] = f'Bearer {self.hf_token}'

            response = requests.get(url, headers=headers, timeout=self.timeout)

            if response.status_code == 404:
                self.logger.warning("BigCodeBench data.json not found, using GitHub fallback...")
                return self._fetch_bigcodebench_github()

            response.raise_for_status()
            data = response.json()

            results = {}
            for entry in data:
                model_id = entry.get('model', '')
                if model_id:
                    results[model_id.lower()] = {
                        'bigcodebench_hard': entry.get('hard') or entry.get('bigcodebench_hard'),
                        'bigcodebench_full': entry.get('full') or entry.get('bigcodebench_full')
                    }

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None
            self.logger.info(f"Fetched BigCodeBench data for {len(results)} models")
            return results

        except Exception as e:
            self.logger.error(f"Error fetching BigCodeBench leaderboard: {e}")
            self._last_error = str(e)
            return {}

    def _fetch_bigcodebench_github(self) -> Dict[str, Dict[str, float]]:
        """Fallback to GitHub raw JSON."""
        try:
            url = "https://raw.githubusercontent.com/bigcode-project/bigcodebench/main/leaderboard/data.json"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            results = {}
            for entry in data.get('leaderboard', []):
                model_id = entry.get('model', '')
                if model_id:
                    results[model_id.lower()] = {
                        'bigcodebench_hard': entry.get('hard'),
                        'bigcodebench_full': entry.get('full')
                    }

            return results
        except Exception as e:
            self.logger.error(f"BigCodeBench GitHub fallback failed: {e}")
            return {}


class GitHubRawFetcher(BenchmarkFetcher):
    """Fetcher for benchmark data hosted as raw JSON on GitHub."""

    def fetch_swebench_leaderboard(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch SWE-bench leaderboard from GitHub.

        Returns dict: {model_id: {'swe_bench_verified': score, 'swe_bench_lite': score}}
        """
        try:
            self.logger.info("Fetching SWE-bench leaderboard from GitHub...")

            url = "https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/main/data/leaderboards.json"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            results = {}

            # SWE-bench JSON structure: {leaderboards: [{name, results: [{model, score}]}]}
            for leaderboard in data.get('leaderboards', []):
                lb_name = leaderboard.get('name', '').lower()

                for entry in leaderboard.get('results', []):
                    model_id = entry.get('model', '') or entry.get('name', '')
                    score = entry.get('resolved', 0) or entry.get('score', 0)

                    if model_id:
                        model_key = model_id.lower()
                        if model_key not in results:
                            results[model_key] = {}

                        # Map leaderboard name to our field
                        if 'verified' in lb_name:
                            results[model_key]['swe_bench_verified'] = score
                        elif 'lite' in lb_name:
                            results[model_key]['swe_bench_lite'] = score

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None
            self.logger.info(f"Fetched SWE-bench data for {len(results)} models")
            return results

        except Exception as e:
            self.logger.error(f"Error fetching SWE-bench leaderboard: {e}")
            self._last_error = str(e)
            return {}

    def fetch_livebench_leaderboard(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch LiveBench coding category from GitHub/HuggingFace.

        Returns dict: {model_id: {'livebench_coding': score, 'livebench_global': score}}
        """
        try:
            self.logger.info("Fetching LiveBench leaderboard...")

            # LiveBench releases results as HuggingFace dataset
            url = "https://huggingface.co/datasets/livebench/leaderboard/resolve/main/data.json"
            response = requests.get(url, timeout=self.timeout)

            if response.status_code == 404:
                # Try GitHub fallback
                url = "https://raw.githubusercontent.com/LiveBench/LiveBench/main/leaderboard/data.json"
                response = requests.get(url, timeout=self.timeout)

            response.raise_for_status()
            data = response.json()

            results = {}
            for entry in data:
                model_id = entry.get('model', '')
                if model_id:
                    results[model_id.lower()] = {
                        'livebench_coding': entry.get('coding') or entry.get('code_generation'),
                        'livebench_global': entry.get('average') or entry.get('overall')
                    }

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None
            self.logger.info(f"Fetched LiveBench data for {len(results)} models")
            return results

        except Exception as e:
            self.logger.error(f"Error fetching LiveBench leaderboard: {e}")
            self._last_error = str(e)
            return {}

    def fetch_livecodebench_leaderboard(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch LiveCodeBench (competitive programming) leaderboard.

        Returns dict: {model_id: {'livecodebench': score}}
        """
        try:
            self.logger.info("Fetching LiveCodeBench leaderboard...")

            url = "https://raw.githubusercontent.com/LiveBench/LiveCodeBench/main/leaderboard/pass_at_1.json"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            results = {}
            for model_id, score in data.items():
                if isinstance(score, (int, float)):
                    results[model_id.lower()] = {'livecodebench': score}

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None
            self.logger.info(f"Fetched LiveCodeBench data for {len(results)} models")
            return results

        except Exception as e:
            self.logger.error(f"Error fetching LiveCodeBench leaderboard: {e}")
            self._last_error = str(e)
            return {}


class ArtificialAnalysisFetcher(BenchmarkFetcher):
    """Fetcher for performance metrics from Artificial Analysis."""

    def fetch_performance_metrics(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch performance metrics (TTFT, throughput, quality) from Artificial Analysis.

        NOTE: Artificial Analysis doesn't have a public API. Options:
        1. Use HuggingFace Space: https://huggingface.co/spaces/ArtificialAnalysis/LLM-Performance-Leaderboard
        2. Web scraping (brittle, not recommended)
        3. Manual data updates (current approach)

        Returns dict: {model_id: {'ttft_median': float, 'throughput_median': float, 'quality_index': float}}
        """
        try:
            self.logger.info("Fetching Artificial Analysis performance metrics...")

            # Try HuggingFace Space data endpoint
            url = "https://huggingface.co/spaces/ArtificialAnalysis/LLM-Performance-Leaderboard/resolve/main/data/leaderboard.json"

            headers = {'Accept': 'application/json'}
            response = requests.get(url, headers=headers, timeout=self.timeout)

            if response.status_code == 404:
                self.logger.warning("Artificial Analysis data not available via API")
                return {}

            response.raise_for_status()
            data = response.json()

            results = {}
            for entry in data:
                model_id = entry.get('model', '')
                if model_id:
                    results[model_id.lower()] = {
                        'ttft_median': entry.get('ttft_median') or entry.get('median_ttft'),
                        'ttft_p95': entry.get('ttft_p95'),
                        'throughput_median': entry.get('throughput_median') or entry.get('median_output_tps'),
                        'throughput_p95': entry.get('throughput_p95'),
                        'total_latency_median': entry.get('total_latency_median'),
                        'quality_index': entry.get('quality_index') or entry.get('intelligence_index')
                    }

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None
            self.logger.info(f"Fetched performance data for {len(results)} models")
            return results

        except Exception as e:
            self.logger.error(f"Error fetching Artificial Analysis metrics: {e}")
            self._last_error = str(e)
            return {}

    # _fetch_performance_fallback removed


class Chapter4BenchmarkFetcher(BenchmarkFetcher):
    """Fetcher for Chapter 4 MSS-specific benchmarks."""

    def __init__(self, hf_token: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.hf_token = hf_token

    def fetch_bfcl_leaderboard(self) -> Dict[str, float]:
        """
        Fetch BFCL (Berkeley Function Calling Leaderboard) scores.

        Source: HuggingFace dataset gorilla-llm/Berkeley-Function-Calling-Leaderboard
        Returns: {model_id: overall_accuracy_percentage}
        """
        try:
            self.logger.info("Fetching BFCL leaderboard...")

            # Try HuggingFace dataset API first
            url = "https://huggingface.co/datasets/gorilla-llm/Berkeley-Function-Calling-Leaderboard/resolve/main/data/leaderboard.json"

            headers = {'Accept': 'application/json'}
            if self.hf_token:
                headers['Authorization'] = f'Bearer {self.hf_token}'

            response = requests.get(url, headers=headers, timeout=self.timeout)

            if response.status_code == 404:
                # Try alternative endpoint
                url = "https://gorilla.cs.berkeley.edu/leaderboard_data.json"
                response = requests.get(url, timeout=self.timeout)

            response.raise_for_status()
            data = response.json()

            results = {}
            # Parse leaderboard data (format: {model: str, overall_accuracy: float})
            if isinstance(data, list):
                for entry in data:
                    model_id = entry.get('model_name') or entry.get('model', '')
                    score = entry.get('overall_accuracy') or entry.get('accuracy')
                    if model_id and score is not None:
                        results[model_id.lower()] = float(score)
            elif isinstance(data, dict):
                for model_id, model_data in data.items():
                    if isinstance(model_data, dict):
                        score = model_data.get('overall_accuracy') or model_data.get('accuracy')
                        if score is not None:
                            results[model_id.lower()] = float(score)

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None
            self.logger.info(f"Fetched BFCL data for {len(results)} models")
            return results

        except Exception as e:
            self.logger.error(f"Error fetching BFCL leaderboard: {e}")
            self._last_error = str(e)
            return {}

    def fetch_webdev_arena_leaderboard(self) -> Dict[str, float]:
        """
        Fetch WebDev Arena Elo scores via web scraping.

        Source: https://lmarena.ai/leaderboard/webdev
        Returns: {model_id: elo_score}
        """
        try:
            from bs4 import BeautifulSoup

            self.logger.info("Fetching WebDev Arena leaderboard...")

            url = "https://lmarena.ai/leaderboard/webdev"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Try to find leaderboard data in script tags (often embedded as JSON)
            results = {}
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'leaderboard' in script.string.lower():
                    # Try to extract JSON data
                    try:
                        # Look for patterns like: var leaderboardData = {...}
                        match = re.search(r'leaderboard.*?=\s*(\[.*?\]|\{.*?\})', script.string, re.DOTALL)
                        if match:
                            json_str = match.group(1)
                            data = json.loads(json_str)
                            if isinstance(data, list):
                                for entry in data:
                                    model_id = entry.get('model_name') or entry.get('model', '')
                                    score = entry.get('rating') or entry.get('elo') or entry.get('score')
                                    if model_id and score:
                                        results[model_id.lower()] = float(score)
                    except json.JSONDecodeError:
                        pass

            if not results:
                self.logger.warning("Could not extract WebDev Arena data from HTML")

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched WebDev Arena data for {len(results)} models")
            return results

        except ImportError:
            self.logger.error("BeautifulSoup not installed. Run: pip install beautifulsoup4")
            self._last_error = "BeautifulSoup not installed"
            return {}
        except Exception as e:
            self.logger.error(f"Error fetching WebDev Arena leaderboard: {e}")
            self._last_error = str(e)
            return {}

    def fetch_arc_agi_leaderboard(self) -> Dict[str, float]:
        """
        Fetch ARC-AGI scores from LLM Stats aggregator.

        Source: https://llm-stats.com/benchmarks/arc-agi
        Returns: {model_id: pass_rate_percentage}
        """
        try:
            from bs4 import BeautifulSoup

            self.logger.info("Fetching ARC-AGI leaderboard...")

            url = "https://llm-stats.com/benchmarks/arc-agi"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            results = {}
            # Look for embedded JSON data or table data
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'arc' in script.string.lower():
                    try:
                        match = re.search(r'data\s*=\s*(\[.*?\]|\{.*?\})', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            if isinstance(data, list):
                                for entry in data:
                                    model_id = entry.get('model') or entry.get('model_name', '')
                                    score = entry.get('score') or entry.get('pass_rate')
                                    if model_id and score is not None:
                                        results[model_id.lower()] = float(score)
                    except json.JSONDecodeError:
                        pass

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched ARC-AGI data for {len(results)} models")
            return results

        except ImportError:
            self.logger.error("BeautifulSoup not installed")
            self._last_error = "BeautifulSoup not installed"
            return {}
        except Exception as e:
            self.logger.error(f"Error fetching ARC-AGI leaderboard: {e}")
            self._last_error = str(e)
            return {}

    def fetch_simplebench_leaderboard(self) -> Dict[str, float]:
        """
        Fetch SimpleBench scores via web scraping.

        Source: https://simple-bench.com/
        Returns: {model_id: accuracy_percentage}
        """
        try:
            from bs4 import BeautifulSoup

            self.logger.info("Fetching SimpleBench leaderboard...")

            url = "https://simple-bench.com/"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            results = {}
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'simplebench' in script.string.lower():
                    try:
                        match = re.search(r'(?:leaderboard|results|data)\s*=\s*(\[.*?\]|\{.*?\})', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            if isinstance(data, list):
                                for entry in data:
                                    model_id = entry.get('model') or entry.get('name', '')
                                    score = entry.get('accuracy') or entry.get('score')
                                    if model_id and score is not None:
                                        results[model_id.lower()] = float(score)
                    except json.JSONDecodeError:
                        pass

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched SimpleBench data for {len(results)} models")
            return results

        except ImportError:
            self.logger.error("BeautifulSoup not installed")
            self._last_error = "BeautifulSoup not installed"
            return {}
        except Exception as e:
            self.logger.error(f"Error fetching SimpleBench leaderboard: {e}")
            self._last_error = str(e)
            return {}

    def fetch_canaicode_leaderboard(self) -> Dict[str, float]:
        """
        Fetch CanAiCode scores from HuggingFace Space.

        Source: https://huggingface.co/spaces/mike-ravkine/can-ai-code-results
        Returns: {model_id: pass_rate_percentage}
        """
        try:
            self.logger.info("Fetching CanAiCode leaderboard...")

            # Try direct API endpoint for HuggingFace Space
            url = "https://huggingface.co/spaces/mike-ravkine/can-ai-code-results/resolve/main/results.json"

            headers = {'Accept': 'application/json'}
            if self.hf_token:
                headers['Authorization'] = f'Bearer {self.hf_token}'

            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()

            results = {}
            if isinstance(data, list):
                for entry in data:
                    model_id = entry.get('model') or entry.get('name', '')
                    score = entry.get('pass_rate') or entry.get('score') or entry.get('accuracy')
                    if model_id and score is not None:
                        results[model_id.lower()] = float(score)
            elif isinstance(data, dict):
                for model_id, model_data in data.items():
                    if isinstance(model_data, dict):
                        score = model_data.get('pass_rate') or model_data.get('score')
                        if score is not None:
                            results[model_id.lower()] = float(score)

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None
            self.logger.info(f"Fetched CanAiCode data for {len(results)} models")
            return results

        except Exception as e:
            self.logger.error(f"Error fetching CanAiCode leaderboard: {e}")
            self._last_error = str(e)
            return {}

    def fetch_seal_showdown_leaderboard(self) -> Dict[str, float]:
        """
        Fetch SEAL Showdown coding scores via web scraping.

        Source: https://scale.com/leaderboard/coding
        Returns: {model_id: bradley_terry_score}
        """
        try:
            from bs4 import BeautifulSoup

            self.logger.info("Fetching SEAL Showdown coding leaderboard...")

            url = "https://scale.com/leaderboard/coding"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            results = {}
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and ('leaderboard' in script.string.lower() or 'coding' in script.string.lower()):
                    try:
                        match = re.search(r'(?:leaderboard|models|data)\s*=\s*(\[.*?\]|\{.*?\})', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            if isinstance(data, list):
                                for entry in data:
                                    model_id = entry.get('model') or entry.get('name', '')
                                    score = entry.get('rating') or entry.get('score') or entry.get('bt_score')
                                    if model_id and score is not None:
                                        results[model_id.lower()] = float(score)
                    except json.JSONDecodeError:
                        pass

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched SEAL Showdown data for {len(results)} models")
            return results

        except ImportError:
            self.logger.error("BeautifulSoup not installed")
            self._last_error = "BeautifulSoup not installed"
            return {}
        except Exception as e:
            self.logger.error(f"Error fetching SEAL Showdown leaderboard: {e}")
            self._last_error = str(e)
            return {}

    def fetch_gpqa_leaderboard(self) -> Dict[str, float]:
        """
        Fetch GPQA scores from LLM Stats aggregator.

        Source: https://llm-stats.com/benchmarks/gpqa
        Returns: {model_id: accuracy_percentage}
        """
        try:
            from bs4 import BeautifulSoup

            self.logger.info("Fetching GPQA leaderboard...")

            url = "https://llm-stats.com/benchmarks/gpqa"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            results = {}
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'gpqa' in script.string.lower():
                    try:
                        match = re.search(r'data\s*=\s*(\[.*?\]|\{.*?\})', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            if isinstance(data, list):
                                for entry in data:
                                    model_id = entry.get('model') or entry.get('model_name', '')
                                    score = entry.get('score') or entry.get('accuracy')
                                    if model_id and score is not None:
                                        results[model_id.lower()] = float(score)
                    except json.JSONDecodeError:
                        pass

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched GPQA data for {len(results)} models")
            return results

        except ImportError:
            self.logger.error("BeautifulSoup not installed")
            self._last_error = "BeautifulSoup not installed"
            return {}
        except Exception as e:
            self.logger.error(f"Error fetching GPQA leaderboard: {e}")
            self._last_error = str(e)
            return {}


class OpenRouterAdoptionFetcher(BenchmarkFetcher):
    """Fetcher for OpenRouter model popularity/adoption metrics."""

    def fetch_programming_rankings(self) -> Dict[str, int]:
        """
        Fetch model rankings from OpenRouter programming category.

        Source: https://openrouter.ai/rankings/programming
        Returns: {model_id: rank_position}
        """
        try:
            from bs4 import BeautifulSoup

            self.logger.info("Fetching OpenRouter programming rankings...")

            url = "https://openrouter.ai/rankings/programming"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            results = {}
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'ranking' in script.string.lower():
                    try:
                        # Look for rankings data structure
                        match = re.search(r'(?:rankings|models|leaderboard)\s*=\s*(\[.*?\])', script.string, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            for i, entry in enumerate(data, 1):
                                model_id = entry.get('id') or entry.get('model_id') or entry.get('name', '')
                                if model_id:
                                    results[model_id.lower()] = i
                    except json.JSONDecodeError:
                        pass

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched OpenRouter rankings for {len(results)} models")
            return results

        except ImportError:
            self.logger.error("BeautifulSoup not installed")
            self._last_error = "BeautifulSoup not installed"
            return {}
        except Exception as e:
            self.logger.error(f"Error fetching OpenRouter rankings: {e}")
            self._last_error = str(e)
            return {}


class FirecrawlBenchmarkFetcher(BenchmarkFetcher):
    """
    Fetcher that uses Firecrawl to scrape JS-rendered leaderboard pages.

    Firecrawl handles JavaScript rendering and returns clean markdown,
    which is far more reliable than BeautifulSoup regex parsing for
    modern React/Next.js leaderboard sites.
    """

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or os.getenv('FIRECRAWL_API_KEY')
        self._client = None

    def _get_client(self):
        """Lazy-init Firecrawl client."""
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("FIRECRAWL_API_KEY not configured")
            from firecrawl import FirecrawlApp
            self._client = FirecrawlApp(api_key=self.api_key)
        return self._client

    def _scrape_markdown(self, url: str) -> str:
        """Scrape a URL and return its markdown content."""
        client = self._get_client()
        result = client.scrape(
            url,
            formats=['markdown'],
            only_main_content=True,
            timeout=self.timeout * 1000,  # Firecrawl uses milliseconds
        )
        return result.markdown or ''

    @staticmethod
    def _parse_markdown_table(markdown: str) -> List[Dict[str, str]]:
        """Parse ALL markdown tables and return combined rows."""
        lines = markdown.strip().split('\n')
        all_rows: List[Dict[str, str]] = []
        headers: List[str] = []
        in_table = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('|') and '|' in stripped[1:]:
                cells = [c.strip() for c in stripped.split('|')[1:-1]]
                if not cells:
                    continue
                # Separator row
                if all(set(c) <= {'-', ':', ' '} for c in cells):
                    continue
                # Skip empty header rows (e.g. |  |  |  |)
                if all(c.strip() == '' for c in cells):
                    continue
                # Strip bold markers from header candidates
                clean_cells = [c.strip('*').strip() for c in cells]
                if not in_table:
                    headers = clean_cells
                    in_table = True
                    continue
                if len(cells) == len(headers):
                    all_rows.append(dict(zip(headers, cells)))
            else:
                if in_table:
                    in_table = False
                    headers = []
        return all_rows

    @staticmethod
    def _extract_model_name_from_md(cell: str) -> str:
        """Extract clean model name from markdown cell (may contain links)."""
        # Skip image links ![alt](url), find regular [text](url)
        # Pattern: find [text] that is NOT preceded by !
        matches = re.findall(r'(?<!!)\[([^\]]+)\]\([^\)]+\)', cell)
        if matches:
            # Return first non-image link text, strip "New" suffix
            name = matches[0].strip()
            name = re.sub(r'\s*New$', '', name)
            return name
        # Fallback: any [text]
        match = re.search(r'\[([^\]]+)\]', cell)
        if match:
            return match.group(1).strip()
        # Remove <br> tags and return cleaned text
        return re.sub(r'<br\s*/?>', ' ', cell).strip()

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        """Extract a numeric value from text like '92.4%' or '1234'."""
        text = text.strip().rstrip('%')
        match = re.search(r'[-+]?\d+\.?\d*', text)
        if match:
            return float(match.group())
        return None

    def fetch_openrouter_programming_rankings(self) -> Dict[str, int]:
        """
        Fetch model rankings from OpenRouter programming category via Firecrawl.

        Returns: {model_id: rank_position}
        """
        try:
            self.logger.info("Fetching OpenRouter programming rankings via Firecrawl...")
            md = self._scrape_markdown("https://openrouter.ai/rankings/programming")

            results = {}
            # Pattern: numbered list items with model links
            # e.g. "1.\n...\n[Gemini 3 Flash Preview](https://openrouter.ai/google/gemini-3-flash-preview)"
            pattern = r'(\d+)\.\s*(?:!\[.*?\]\(.*?\)\s*)*\[([^\]]+)\]\(https://openrouter\.ai/([^)]+)\)'
            for match in re.finditer(pattern, md):
                rank = int(match.group(1))
                model_id = match.group(3).strip()
                if model_id and '/' in model_id:
                    results[model_id.lower()] = rank

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched OpenRouter rankings for {len(results)} models via Firecrawl")
            return results

        except Exception as e:
            self.logger.error(f"Firecrawl: Error fetching OpenRouter rankings: {e}")
            self._last_error = str(e)
            return {}

    def fetch_livecodebench_leaderboard(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch LiveCodeBench leaderboard via Firecrawl.

        Returns: {model_name: {'livecodebench': pass_at_1_score}}
        """
        try:
            self.logger.info("Fetching LiveCodeBench leaderboard via Firecrawl...")
            md = self._scrape_markdown("https://livecodebench.github.io/leaderboard.html")

            results = {}
            rows = self._parse_markdown_table(md)
            for row in rows:
                model_raw = row.get('Model', '')
                pass1_raw = row.get('Pass@1', '')
                model_name = self._extract_model_name_from_md(model_raw)
                score = self._extract_number(pass1_raw)
                if model_name and score is not None:
                    results[model_name.lower()] = {'livecodebench': score}

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched LiveCodeBench data for {len(results)} models via Firecrawl")
            return results

        except Exception as e:
            self.logger.error(f"Firecrawl: Error fetching LiveCodeBench: {e}")
            self._last_error = str(e)
            return {}

    def fetch_livebench_leaderboard(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch LiveBench leaderboard via Firecrawl.

        Returns: {model_name: {'livebench_coding': score, 'livebench_global': score}}
        """
        try:
            self.logger.info("Fetching LiveBench leaderboard via Firecrawl...")
            md = self._scrape_markdown("https://livebench.ai/#/")

            results = {}
            rows = self._parse_markdown_table(md)
            for row in rows:
                model_raw = row.get('Model', '')
                coding_raw = row.get('Coding Average', '')
                global_raw = row.get('Global Average', '')
                model_name = self._extract_model_name_from_md(model_raw)
                coding = self._extract_number(coding_raw)
                global_avg = self._extract_number(global_raw)
                if model_name and (coding is not None or global_avg is not None):
                    entry = {}
                    if coding is not None:
                        entry['livebench_coding'] = coding
                    if global_avg is not None:
                        entry['livebench_global'] = global_avg
                    results[model_name.lower()] = entry

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched LiveBench data for {len(results)} models via Firecrawl")
            return results

        except Exception as e:
            self.logger.error(f"Firecrawl: Error fetching LiveBench: {e}")
            self._last_error = str(e)
            return {}

    def fetch_simplebench_leaderboard(self) -> Dict[str, float]:
        """
        Fetch SimpleBench leaderboard via Firecrawl.

        Returns: {model_name: accuracy_percentage}
        """
        try:
            self.logger.info("Fetching SimpleBench leaderboard via Firecrawl...")
            md = self._scrape_markdown("https://simple-bench.com/")

            results = {}
            rows = self._parse_markdown_table(md)
            for row in rows:
                model_raw = row.get('Model', '')
                # Score column name varies: 'Score (AVG@5)', 'Score', 'Accuracy'
                score_raw = ''
                for key in row:
                    if 'score' in key.lower() or 'accuracy' in key.lower():
                        score_raw = row[key]
                        break
                model_name = self._extract_model_name_from_md(model_raw)
                score = self._extract_number(score_raw)
                # Skip non-model rows like "Human Baseline"
                if model_name and score is not None and 'human' not in model_name.lower():
                    results[model_name.lower()] = score

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched SimpleBench data for {len(results)} models via Firecrawl")
            return results

        except Exception as e:
            self.logger.error(f"Firecrawl: Error fetching SimpleBench: {e}")
            self._last_error = str(e)
            return {}

    def fetch_seal_showdown_leaderboard(self) -> Dict[str, float]:
        """
        Fetch SEAL leaderboard coding scores via Firecrawl.

        Uses the MCP Atlas sub-leaderboard (most relevant for coding).
        Falls back to parsing the main SEAL page card preview data.

        Returns: {model_name: pass_rate}
        """
        try:
            self.logger.info("Fetching SEAL leaderboard via Firecrawl...")
            md = self._scrape_markdown("https://scale.com/leaderboard/mcp_atlas")

            results = {}
            rows = self._parse_markdown_table(md)
            for row in rows:
                model_raw = row.get('Model', '') or row.get('Name', '')
                score_raw = (row.get('Pass Rate', '')
                             or row.get('Score', '')
                             or row.get('Overall', ''))
                if not score_raw:
                    for key in row:
                        kl = key.lower()
                        if any(t in kl for t in ['pass', 'score', 'rate',
                                                  'elo', 'bt']):
                            score_raw = row[key]
                            break
                model_name = self._extract_model_name_from_md(model_raw)
                score = self._extract_number(score_raw)
                if model_name and score is not None:
                    results[model_name.lower()] = score

            # Fallback: parse card-style data from main page
            if not results:
                self.logger.info("Trying main SEAL page fallback...")
                md = self._scrape_markdown("https://scale.com/leaderboard")
                # Pattern: rank\n\nmodel_name\n\nscore±error
                import re
                blocks = re.findall(
                    r'(\d+)\s*\\\\?\n\\\\?\n\s*([\w\-\.\s]+?)\s*\\\\?\n\\\\?\n\s*([\d.]+)±',
                    md
                )
                for rank, model, score in blocks:
                    model = model.strip().rstrip('*').strip()
                    if model and model.upper() != 'NEW':
                        results[model.lower()] = float(score)

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched SEAL data for {len(results)} models via Firecrawl")
            return results

        except Exception as e:
            self.logger.error(f"Firecrawl: Error fetching SEAL Showdown: {e}")
            self._last_error = str(e)
            return {}

    def fetch_bfcl_leaderboard(self) -> Dict[str, float]:
        """
        Fetch BFCL (Berkeley Function Calling Leaderboard) via Firecrawl.

        Returns: {model_name: overall_accuracy_percentage}
        """
        try:
            self.logger.info("Fetching BFCL leaderboard via Firecrawl...")
            md = self._scrape_markdown("https://gorilla.cs.berkeley.edu/leaderboard.html")

            results = {}
            # BFCL table has duplicate column names, so parse by position
            for line in md.split('\n'):
                line = line.strip()
                if not line.startswith('|'):
                    continue
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if len(cells) < 3:
                    continue
                # Skip header/separator rows
                if cells[0].startswith('Rank') or cells[0].startswith('---'):
                    continue
                if all(set(c) <= {'-', ':', ' '} for c in cells):
                    continue
                # cells[0]=Rank, cells[1]=Overall Acc, cells[2]=Model
                model_name = self._extract_model_name_from_md(cells[2])
                score = self._extract_number(cells[1])
                if model_name and score is not None:
                    results[model_name.lower()] = score

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched BFCL data for {len(results)} models via Firecrawl")
            return results

        except Exception as e:
            self.logger.error(f"Firecrawl: Error fetching BFCL: {e}")
            self._last_error = str(e)
            return {}

    def fetch_webdev_arena_leaderboard(self) -> Dict[str, float]:
        """
        Fetch Arena (formerly LM Arena) Code leaderboard Elo scores via Firecrawl.

        Returns: {model_name: elo_score}
        """
        try:
            self.logger.info("Fetching Arena Code leaderboard via Firecrawl...")
            md = self._scrape_markdown("https://arena.ai/leaderboard")

            results = {}
            # Arena page uses escaped pipes \\| in embedded tables
            # Find Code section and parse its table
            in_code_section = False
            for line in md.split('\n'):
                if '**Code**' in line:
                    in_code_section = True
                    continue
                if in_code_section and ('**' in line and 'Code' not in line
                                        and 'View' not in line):
                    break  # Next section
                if not in_code_section:
                    continue
                # Parse rows: | rank | model_link | score | votes |
                # May use \\| instead of |
                cleaned = line.replace('\\|', '|').strip()
                if not cleaned.startswith('|'):
                    continue
                cells = [c.strip() for c in cleaned.split('|')[1:-1]]
                if len(cells) < 3:
                    continue
                if cells[0].startswith('Rank') or cells[0].startswith('---'):
                    continue
                if all(set(c) <= {'-', ':', ' '} for c in cells):
                    continue
                model_name = self._extract_model_name_from_md(cells[1])
                score = self._extract_number(cells[2])
                if model_name and score is not None:
                    results[model_name.lower()] = score

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched Arena Code data for {len(results)} models via Firecrawl")
            return results

        except Exception as e:
            self.logger.error(f"Firecrawl: Error fetching Arena Code leaderboard: {e}")
            self._last_error = str(e)
            return {}

    def fetch_arc_agi_leaderboard(self) -> Dict[str, float]:
        """
        Fetch ARC-AGI scores via Firecrawl.

        Returns: {model_name: pass_rate_percentage}
        """
        try:
            self.logger.info("Fetching ARC-AGI leaderboard via Firecrawl...")
            md = self._scrape_markdown("https://arcprize.org/leaderboard")

            results = {}
            rows = self._parse_markdown_table(md)
            for row in rows:
                # Column headers: "AI System", "Author", "System Type",
                # "ARC-AGI-1", "ARC-AGI-2", "Cost/Task", "Code / Paper"
                model_raw = (row.get('AI System', '') or row.get('Model', '')
                             or row.get('Name', ''))
                # Prefer ARC-AGI-1 score
                score_raw = row.get('ARC-AGI-1', '')
                if not score_raw:
                    for key in row:
                        kl = key.lower()
                        if 'arc' in kl or 'score' in kl or 'accuracy' in kl:
                            score_raw = row[key]
                            break
                # Skip non-AI entries
                if 'human' in model_raw.lower():
                    continue
                model_name = self._extract_model_name_from_md(model_raw)
                score = self._extract_number(score_raw)
                if model_name and score is not None:
                    results[model_name.lower()] = score

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched ARC-AGI data for {len(results)} models via Firecrawl")
            return results

        except Exception as e:
            self.logger.error(f"Firecrawl: Error fetching ARC-AGI: {e}")
            self._last_error = str(e)
            return {}

    def fetch_gpqa_leaderboard(self) -> Dict[str, float]:
        """
        Fetch GPQA scores via Firecrawl.

        Returns: {model_name: accuracy_percentage}
        """
        try:
            self.logger.info("Fetching GPQA leaderboard via Firecrawl...")
            md = self._scrape_markdown("https://llm-stats.com/benchmarks/gpqa")

            results = {}
            rows = self._parse_markdown_table(md)
            for row in rows:
                model_raw = row.get('Model', '') or row.get('Name', '')
                score_raw = ''
                for key in row:
                    kl = key.lower()
                    if any(t in kl for t in ['score', 'accuracy', 'gpqa', '%']):
                        score_raw = row[key]
                        break
                model_name = self._extract_model_name_from_md(model_raw)
                score = self._extract_number(score_raw)
                if model_name and score is not None:
                    results[model_name.lower()] = score

            self._last_fetch_time = datetime.utcnow()
            self._last_error = None if results else "No data extracted"
            self.logger.info(f"Fetched GPQA data for {len(results)} models via Firecrawl")
            return results

        except Exception as e:
            self.logger.error(f"Firecrawl: Error fetching GPQA: {e}")
            self._last_error = str(e)
            return {}

    def fetch_canaicode_leaderboard(self) -> Dict[str, float]:
        """
        Fetch CanAiCode scores via Firecrawl.

        Note: The HuggingFace Space uses Gradio which doesn't render
        data into static HTML. This fetcher tries the direct space URL
        but may return empty results — fallback data in
        model_rankings_service.py will be used instead.

        Returns: {model_name: pass_rate_percentage}
        """
        try:
            self.logger.info("Fetching CanAiCode leaderboard via Firecrawl...")
            # Try direct Gradio space URL (renders better than HF wrapper)
            md = self._scrape_markdown(
                "https://mike-ravkine-can-ai-code-results.hf.space/"
            )

            results = {}
            rows = self._parse_markdown_table(md)
            for row in rows:
                model_raw = row.get('Model', '') or row.get('Name', '')
                score_raw = ''
                for key in row:
                    kl = key.lower()
                    if any(t in kl for t in ['pass', 'score', 'rate',
                                              'accuracy', '%']):
                        score_raw = row[key]
                        break
                model_name = self._extract_model_name_from_md(model_raw)
                score = self._extract_number(score_raw)
                if model_name and score is not None:
                    results[model_name.lower()] = score

            self._last_fetch_time = datetime.utcnow()
            if not results:
                self._last_error = ("CanAiCode Gradio space doesn't expose "
                                    "static data — using fallback")
                self.logger.warning(self._last_error)
            else:
                self._last_error = None
            self.logger.info(f"Fetched CanAiCode data for {len(results)} models via Firecrawl")
            return results

        except Exception as e:
            self.logger.error(f"Firecrawl: Error fetching CanAiCode: {e}")
            self._last_error = str(e)
            return {}


class CombinedBenchmarkAggregator:
    """
    Aggregates benchmark data from all fetchers.
    
    By default uses static curated data for fast page loads.
    Live fetching available on-demand via fetch_live parameter.
    """

    def __init__(self, hf_token: Optional[str] = None):
        self.hf_token = hf_token
        self.hf_fetcher = HuggingFaceBenchmarkFetcher(hf_token=hf_token)
        self.github_fetcher = GitHubRawFetcher()
        self.performance_fetcher = ArtificialAnalysisFetcher()
        self.chapter4_fetcher = Chapter4BenchmarkFetcher(hf_token=hf_token)
        self.adoption_fetcher = OpenRouterAdoptionFetcher()
        self.logger = logger
        self._last_live_fetch_time = None

        # Firecrawl-powered fetcher for JS-rendered leaderboard pages
        firecrawl_key = os.getenv('FIRECRAWL_API_KEY')
        self._firecrawl_available = bool(firecrawl_key)
        if self._firecrawl_available:
            self.firecrawl_fetcher = FirecrawlBenchmarkFetcher(api_key=firecrawl_key)
            self.logger.info("Firecrawl fetcher initialized for live benchmark scraping")
        else:
            self.firecrawl_fetcher = None
            self.logger.warning("FIRECRAWL_API_KEY not set — falling back to BS4 scrapers")

    def get_static_benchmarks(self) -> Dict[str, Any]:
        """
        Get all benchmark data from static curated sources.
        
        NOTE: Static data has been removed to enforce fail-fast behavior.
        This method now returns an empty structure.
        """
        self.logger.info("Loading static benchmark data (empty/removed)...")
        
        results = {
            'evalplus': {},
            'swebench': {},
            'bigcodebench': {},
            'livebench': {},
            'livecodebench': {},
            'performance': {},
            'bfcl': {},
            'webdev_arena': {},
            'arc_agi': {},
            'simplebench': {},
            'canaicode': {},
            'seal_showdown': {},
            'gpqa': {},
            'adoption': {},
            'accessibility': {},
            'fetch_status': {},
            'data_source': 'static',
            'data_date': 'Jan 2026'
        }
        
        # Static data removed - ensuring empty results
        for key in results.keys():
            if key not in ['fetch_status', 'data_source', 'data_date']:
                results['fetch_status'][key] = {'status': 'ok', 'source': 'static', 'count': 0}
        
        return results

    def fetch_all_benchmarks(self, fetch_live: bool = False) -> Dict[str, Any]:
        """
        Fetch all benchmark data.
        
        Args:
            fetch_live: If True, attempt live fetching from external APIs (slower).
                       If False (default), use static curated data (instant).
        
        Returns:
            Dict with benchmark data from all sources
        """
        if not fetch_live:
            return self.get_static_benchmarks()
        
        return self._fetch_live_parallel()

    def _fetch_live_parallel(self) -> Dict[str, Any]:
        """
        Fetch all benchmark data from live sources in parallel.
        Falls back to static data for any failed sources.
        """
        self.logger.info("Fetching live benchmark data from external sources (parallel)...")
        
        # Start with static data as fallback
        results = self.get_static_benchmarks()
        results['data_source'] = 'live'
        results['data_date'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        
        # Define fetcher tasks — use Firecrawl for JS-rendered pages when available
        fc = self.firecrawl_fetcher
        use_fc = self._firecrawl_available and fc is not None

        fetch_tasks = {
            'evalplus': lambda: self.hf_fetcher.fetch_evalplus_leaderboard(),
            'bigcodebench': lambda: self.hf_fetcher.fetch_bigcodebench_leaderboard(),
            'swebench': lambda: self.github_fetcher.fetch_swebench_leaderboard(),
            'performance_live': lambda: self.performance_fetcher.fetch_performance_metrics(),
            # Firecrawl-powered fetchers for JS-rendered leaderboards (with BS4 fallback)
            'livebench_live': (lambda: fc.fetch_livebench_leaderboard()) if use_fc
                else (lambda: self.github_fetcher.fetch_livebench_leaderboard()),
            'livecodebench_live': (lambda: fc.fetch_livecodebench_leaderboard()) if use_fc
                else (lambda: self.github_fetcher.fetch_livecodebench_leaderboard()),
            'bfcl_live': (lambda: fc.fetch_bfcl_leaderboard()) if use_fc
                else (lambda: self.chapter4_fetcher.fetch_bfcl_leaderboard()),
            'webdev_arena_live': (lambda: fc.fetch_webdev_arena_leaderboard()) if use_fc
                else (lambda: self.chapter4_fetcher.fetch_webdev_arena_leaderboard()),
            'arc_agi_live': (lambda: fc.fetch_arc_agi_leaderboard()) if use_fc
                else (lambda: self.chapter4_fetcher.fetch_arc_agi_leaderboard()),
            'simplebench_live': (lambda: fc.fetch_simplebench_leaderboard()) if use_fc
                else (lambda: self.chapter4_fetcher.fetch_simplebench_leaderboard()),
            'canaicode_live': (lambda: fc.fetch_canaicode_leaderboard()) if use_fc
                else (lambda: self.chapter4_fetcher.fetch_canaicode_leaderboard()),
            'seal_showdown_live': (lambda: fc.fetch_seal_showdown_leaderboard()) if use_fc
                else (lambda: self.chapter4_fetcher.fetch_seal_showdown_leaderboard()),
            'gpqa_live': (lambda: fc.fetch_gpqa_leaderboard()) if use_fc
                else (lambda: self.chapter4_fetcher.fetch_gpqa_leaderboard()),
            'adoption_live': (lambda: fc.fetch_openrouter_programming_rankings()) if use_fc
                else (lambda: self.adoption_fetcher.fetch_programming_rankings()),
        }
        
        live_results = {}
        
        # Execute fetches in parallel with timeout
        # Firecrawl scrapes take longer (~10-20s each), so increase timeouts
        pool_timeout = 90 if use_fc else 30
        result_timeout = 45 if use_fc else 10
        max_workers = 4 if use_fc else 8  # Firecrawl rate limits

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_key = {
                executor.submit(self._safe_fetch, func): key
                for key, func in fetch_tasks.items()
            }
            
            for future in as_completed(future_to_key, timeout=pool_timeout):
                key = future_to_key[future]
                try:
                    data = future.result(timeout=result_timeout)
                    if data:
                        live_results[key] = data
                        self.logger.info(f"Live fetch succeeded: {key} ({len(data)} items)")
                except Exception as e:
                    self.logger.warning(f"Live fetch failed for {key}: {e}")
        
        # Merge live results into static data (live takes precedence if non-empty)
        self._merge_live_results(results, live_results)
        
        self._last_live_fetch_time = datetime.utcnow()
        return results

    def _safe_fetch(self, fetch_func: Callable) -> Any:
        """Safely execute a fetch function with error handling."""
        try:
            return fetch_func()
        except Exception as e:
            self.logger.warning(f"Fetch error: {e}")
            return None

    def _merge_live_results(self, results: Dict[str, Any], live_data: Dict[str, Any]) -> None:
        """Merge live fetched data into results, updating status."""
        # Map live keys to result keys
        key_mapping = {
            'evalplus': 'evalplus',
            'bigcodebench': 'bigcodebench', 
            'swebench': 'swebench',
            'livebench_live': 'livebench',
            'livecodebench_live': 'livecodebench',
            'performance_live': 'performance',
            'bfcl_live': 'bfcl',
            'webdev_arena_live': 'webdev_arena',
            'arc_agi_live': 'arc_agi',
            'simplebench_live': 'simplebench',
            'canaicode_live': 'canaicode',
            'seal_showdown_live': 'seal_showdown',
            'gpqa_live': 'gpqa',
            'adoption_live': 'adoption',
        }
        
        for live_key, result_key in key_mapping.items():
            if live_key in live_data and live_data[live_key]:
                data = live_data[live_key]
                
                # Convert flat score dicts to nested format for Chapter 4 benchmarks
                if result_key in ['bfcl', 'webdev_arena', 'arc_agi', 'simplebench', 
                                  'canaicode', 'seal_showdown', 'gpqa']:
                    score_key = {
                        'bfcl': 'bfcl_score',
                        'webdev_arena': 'webdev_elo',
                        'arc_agi': 'arc_agi_score',
                        'simplebench': 'simplebench_score',
                        'canaicode': 'canaicode_score',
                        'seal_showdown': 'seal_coding_score',
                        'gpqa': 'gpqa_score',
                    }.get(result_key, 'score')
                    
                    if isinstance(next(iter(data.values()), None), (int, float)):
                        data = {model: {score_key: score} for model, score in data.items()}
                
                if result_key == 'adoption':
                    data = {model: {'programming_rank': rank} for model, rank in data.items()}
                
                if result_key == 'livecodebench':
                    if isinstance(next(iter(data.values()), None), (int, float)):
                        data = {model: {'livecodebench': score} for model, score in data.items()}
                
                # Merge into results (live data takes precedence)
                results[result_key].update(data)
                results['fetch_status'][result_key] = {
                    'status': 'ok',
                    'source': 'live',
                    'count': len(data)
                }

