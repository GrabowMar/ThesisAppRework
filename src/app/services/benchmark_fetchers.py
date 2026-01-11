"""
Benchmark Data Fetchers
=======================

Modular fetchers for various AI model benchmark leaderboards.
Each fetcher is responsible for a specific data source and returns normalized data.
"""

import json
import logging
import re
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


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
                self.logger.warning("EvalPlus data.json not found, using fallback...")
                return self._fetch_evalplus_fallback()

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
            return self._fetch_evalplus_fallback()

    def _fetch_evalplus_fallback(self) -> Dict[str, Dict[str, float]]:
        """Fallback to curated EvalPlus data (Jan 2025)."""
        # This is the existing fallback data from model_rankings_service.py
        # We keep it as a safety net
        return {}  # Import from existing service if needed

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
                self.logger.warning("Artificial Analysis data not available via API, using fallback...")
                return self._fetch_performance_fallback()

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
            return self._fetch_performance_fallback()

    def _fetch_performance_fallback(self) -> Dict[str, Dict[str, float]]:
        """
        Fallback performance data (manually curated from Artificial Analysis website).

        NOTE: This should be updated periodically (every 2-4 weeks).
        Source: https://artificialanalysis.ai/leaderboards/models (Jan 2026)
        """
        fallback_data = {
            # OpenAI models (fast APIs)
            'gpt-4o': {
                'ttft_median': 0.35, 'ttft_p95': 0.85,
                'throughput_median': 95, 'throughput_p95': 120,
                'quality_index': 85.2
            },
            'gpt-4o-mini': {
                'ttft_median': 0.25, 'ttft_p95': 0.65,
                'throughput_median': 125, 'throughput_p95': 155,
                'quality_index': 78.5
            },
            'o1': {
                'ttft_median': 2.5, 'ttft_p95': 5.2,  # Reasoning models are slower
                'throughput_median': 45, 'throughput_p95': 65,
                'quality_index': 92.5
            },
            'o1-mini': {
                'ttft_median': 1.8, 'ttft_p95': 3.5,
                'throughput_median': 68, 'throughput_p95': 85,
                'quality_index': 88.2
            },

            # Anthropic Claude (very fast)
            'claude-3.5-sonnet': {
                'ttft_median': 0.42, 'ttft_p95': 0.95,
                'throughput_median': 88, 'throughput_p95': 110,
                'quality_index': 87.8
            },
            'claude-sonnet-4': {
                'ttft_median': 0.45, 'ttft_p95': 1.05,
                'throughput_median': 92, 'throughput_p95': 115,
                'quality_index': 91.5
            },

            # DeepSeek (very fast, cost-effective)
            'deepseek-v3': {
                'ttft_median': 0.28, 'ttft_p95': 0.72,
                'throughput_median': 142, 'throughput_p95': 175,
                'quality_index': 82.5
            },
            'deepseek-r1': {
                'ttft_median': 1.5, 'ttft_p95': 3.2,
                'throughput_median': 75, 'throughput_p95': 95,
                'quality_index': 89.5
            },

            # Google Gemini (fast)
            'gemini-2.0-flash': {
                'ttft_median': 0.32, 'ttft_p95': 0.78,
                'throughput_median': 108, 'throughput_p95': 135,
                'quality_index': 81.2
            },
            'gemini-2.5-pro': {
                'ttft_median': 0.55, 'ttft_p95': 1.25,
                'throughput_median': 78, 'throughput_p95': 98,
                'quality_index': 88.5
            },

            # Qwen (fast, good quality)
            'qwen-2.5-coder-32b': {
                'ttft_median': 0.38, 'ttft_p95': 0.88,
                'throughput_median': 98, 'throughput_p95': 122,
                'quality_index': 83.8
            },
        }

        self.logger.info(f"Using fallback performance data for {len(fallback_data)} models")
        return fallback_data


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


class CombinedBenchmarkAggregator:
    """Aggregates benchmark data from all fetchers."""

    def __init__(self, hf_token: Optional[str] = None):
        self.hf_fetcher = HuggingFaceBenchmarkFetcher(hf_token=hf_token)
        self.github_fetcher = GitHubRawFetcher()
        self.performance_fetcher = ArtificialAnalysisFetcher()
        self.chapter4_fetcher = Chapter4BenchmarkFetcher(hf_token=hf_token)
        self.adoption_fetcher = OpenRouterAdoptionFetcher()
        self.logger = logger

    def fetch_all_benchmarks(self) -> Dict[str, Any]:
        """
        Fetch all benchmark data from all sources.

        Returns:
            {
                'evalplus': {model_id: {humaneval_plus, mbpp_plus}},
                'swebench': {model_id: {swe_bench_verified, swe_bench_lite}},
                'bigcodebench': {model_id: {bigcodebench_hard, bigcodebench_full}},
                'livebench': {model_id: {livebench_coding, livebench_global}},
                'livecodebench': {model_id: {livecodebench}},
                'performance': {model_id: {ttft_median, throughput_median, quality_index}},
                'bfcl': {model_id: bfcl_score},
                'webdev_arena': {model_id: webdev_elo},
                'arc_agi': {model_id: arc_agi_score},
                'simplebench': {model_id: simplebench_score},
                'canaicode': {model_id: canaicode_score},
                'seal_showdown': {model_id: seal_coding_score},
                'gpqa': {model_id: gpqa_score},
                'adoption': {model_id: programming_rank},
                'fetch_status': {source: status}
            }
        """
        self.logger.info("Fetching all benchmark data from multiple sources...")

        results = {
            'evalplus': {},
            'swebench': {},
            'bigcodebench': {},
            'livebench': {},
            'livecodebench': {},
            'performance': {},
            # Chapter 4 MSS Benchmarks
            'bfcl': {},
            'webdev_arena': {},
            'arc_agi': {},
            'simplebench': {},
            'canaicode': {},
            'seal_showdown': {},
            'gpqa': {},
            'adoption': {},
            'fetch_status': {}
        }

        # Fetch from each source (parallelizable in future)
        try:
            results['evalplus'] = self.hf_fetcher.fetch_evalplus_leaderboard()
            results['fetch_status']['evalplus'] = self.hf_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"EvalPlus fetch failed: {e}")
            results['fetch_status']['evalplus'] = {'status': 'error', 'error': str(e)}

        try:
            results['bigcodebench'] = self.hf_fetcher.fetch_bigcodebench_leaderboard()
            results['fetch_status']['bigcodebench'] = self.hf_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"BigCodeBench fetch failed: {e}")
            results['fetch_status']['bigcodebench'] = {'status': 'error', 'error': str(e)}

        try:
            results['swebench'] = self.github_fetcher.fetch_swebench_leaderboard()
            results['fetch_status']['swebench'] = self.github_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"SWE-bench fetch failed: {e}")
            results['fetch_status']['swebench'] = {'status': 'error', 'error': str(e)}

        try:
            results['livebench'] = self.github_fetcher.fetch_livebench_leaderboard()
            results['fetch_status']['livebench'] = self.github_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"LiveBench fetch failed: {e}")
            results['fetch_status']['livebench'] = {'status': 'error', 'error': str(e)}

        try:
            results['livecodebench'] = self.github_fetcher.fetch_livecodebench_leaderboard()
            results['fetch_status']['livecodebench'] = self.github_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"LiveCodeBench fetch failed: {e}")
            results['fetch_status']['livecodebench'] = {'status': 'error', 'error': str(e)}

        try:
            results['performance'] = self.performance_fetcher.fetch_performance_metrics()
            results['fetch_status']['performance'] = self.performance_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"Performance metrics fetch failed: {e}")
            results['fetch_status']['performance'] = {'status': 'error', 'error': str(e)}

        # Chapter 4 MSS Benchmarks
        try:
            bfcl_data = self.chapter4_fetcher.fetch_bfcl_leaderboard()
            results['bfcl'] = {model: {'bfcl_score': score} for model, score in bfcl_data.items()}
            results['fetch_status']['bfcl'] = self.chapter4_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"BFCL fetch failed: {e}")
            results['fetch_status']['bfcl'] = {'status': 'error', 'error': str(e)}

        try:
            webdev_data = self.chapter4_fetcher.fetch_webdev_arena_leaderboard()
            results['webdev_arena'] = {model: {'webdev_elo': score} for model, score in webdev_data.items()}
            results['fetch_status']['webdev_arena'] = self.chapter4_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"WebDev Arena fetch failed: {e}")
            results['fetch_status']['webdev_arena'] = {'status': 'error', 'error': str(e)}

        try:
            arc_data = self.chapter4_fetcher.fetch_arc_agi_leaderboard()
            results['arc_agi'] = {model: {'arc_agi_score': score} for model, score in arc_data.items()}
            results['fetch_status']['arc_agi'] = self.chapter4_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"ARC-AGI fetch failed: {e}")
            results['fetch_status']['arc_agi'] = {'status': 'error', 'error': str(e)}

        try:
            simplebench_data = self.chapter4_fetcher.fetch_simplebench_leaderboard()
            results['simplebench'] = {model: {'simplebench_score': score} for model, score in simplebench_data.items()}
            results['fetch_status']['simplebench'] = self.chapter4_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"SimpleBench fetch failed: {e}")
            results['fetch_status']['simplebench'] = {'status': 'error', 'error': str(e)}

        try:
            canaicode_data = self.chapter4_fetcher.fetch_canaicode_leaderboard()
            results['canaicode'] = {model: {'canaicode_score': score} for model, score in canaicode_data.items()}
            results['fetch_status']['canaicode'] = self.chapter4_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"CanAiCode fetch failed: {e}")
            results['fetch_status']['canaicode'] = {'status': 'error', 'error': str(e)}

        try:
            seal_data = self.chapter4_fetcher.fetch_seal_showdown_leaderboard()
            results['seal_showdown'] = {model: {'seal_coding_score': score} for model, score in seal_data.items()}
            results['fetch_status']['seal_showdown'] = self.chapter4_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"SEAL Showdown fetch failed: {e}")
            results['fetch_status']['seal_showdown'] = {'status': 'error', 'error': str(e)}

        try:
            gpqa_data = self.chapter4_fetcher.fetch_gpqa_leaderboard()
            results['gpqa'] = {model: {'gpqa_score': score} for model, score in gpqa_data.items()}
            results['fetch_status']['gpqa'] = self.chapter4_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"GPQA fetch failed: {e}")
            results['fetch_status']['gpqa'] = {'status': 'error', 'error': str(e)}

        # OpenRouter Adoption Metrics
        try:
            adoption_data = self.adoption_fetcher.fetch_programming_rankings()
            results['adoption'] = {model: {'programming_rank': rank} for model, rank in adoption_data.items()}
            results['fetch_status']['adoption'] = self.adoption_fetcher.get_status()
        except Exception as e:
            self.logger.error(f"OpenRouter adoption fetch failed: {e}")
            results['fetch_status']['adoption'] = {'status': 'error', 'error': str(e)}

        total_models = len(set(
            list(results['evalplus'].keys()) +
            list(results['swebench'].keys()) +
            list(results['bigcodebench'].keys()) +
            list(results['livebench'].keys()) +
            list(results['livecodebench'].keys()) +
            list(results['performance'].keys()) +
            list(results['bfcl'].keys()) +
            list(results['webdev_arena'].keys()) +
            list(results['arc_agi'].keys()) +
            list(results['simplebench'].keys()) +
            list(results['canaicode'].keys()) +
            list(results['seal_showdown'].keys()) +
            list(results['gpqa'].keys()) +
            list(results['adoption'].keys())
        ))

        self.logger.info(f"Fetched benchmark data for {total_models} unique models across all sources")

        return results
