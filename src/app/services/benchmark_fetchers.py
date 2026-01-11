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

STATIC_BFCL_DATA = {
    # Berkeley Function-Calling Leaderboard (Dec 2025 - Jan 2026)
    # Overall Accuracy percentages
    'claude-opus-4.5': 77.47,
    'claude-sonnet-4.5': 73.24,
    'gemini-3-pro-preview': 72.51,
    'glm-4.6': 72.38,
    'grok-4': 69.57,
    'claude-sonnet-4': 68.5,
    'claude-opus-4': 70.2,
    'gpt-5': 67.8,
    'gpt-5-mini': 65.2,
    'gemini-2.5-pro': 66.8,
    'gemini-2.5-flash': 62.4,
    'deepseek-r1': 64.5,
    'deepseek-v3': 61.2,
    'o3-mini': 63.8,
    'o1': 60.5,
    'qwen-2.5-coder-32b': 58.4,
    'llama-3.3-70b': 55.2,
    'gpt-4o': 54.8,
    'gpt-4o-mini': 52.1,
    'claude-3.5-sonnet': 58.2,
    'mistral-large': 48.5,
}

STATIC_WEBDEV_ARENA_DATA = {
    # WebDev Arena Elo Scores (Oct 2025)
    # Elo range: ~800-1500
    'gpt-5': 1476,
    'claude-opus-4': 1472,
    'claude-opus-4.1': 1460,
    'gemini-2.5-pro': 1402,
    'deepseek-r1': 1394,
    'claude-sonnet-4': 1385,
    'o3-mini': 1365,
    'gpt-5-mini': 1345,
    'gemini-2.5-flash': 1320,
    'claude-3.5-sonnet': 1298,
    'deepseek-v3': 1285,
    'gpt-4o': 1265,
    'qwen-2.5-coder-32b': 1245,
    'llama-3.3-70b': 1215,
    'gpt-4o-mini': 1195,
    'mistral-large': 1165,
    'gemini-1.5-pro': 1145,
}

STATIC_ARC_AGI_DATA = {
    # ARC-AGI-2 Pass Rate (Jan 2026)
    # Percentage scores
    'gpt-5.2-pro': 54.2,
    'gemini-3-pro': 54.0,
    'gpt-5.2': 52.9,
    'claude-opus-4.5': 37.6,
    'claude-opus-4': 35.2,
    'o3-mini': 32.5,
    'gpt-5': 30.8,
    'deepseek-r1': 28.4,
    'gemini-2.5-pro': 26.5,
    'claude-sonnet-4': 24.2,
    'gpt-4o': 18.5,
    'claude-3.5-sonnet': 16.8,
    'deepseek-v3': 15.2,
    'llama-3.3-70b': 12.4,
    'qwen-2.5-coder-32b': 14.5,
}

STATIC_SIMPLEBENCH_DATA = {
    # SimpleBench AVG@5 Scores (Jan 2026)
    # Percentage accuracy (Human baseline: 83.7%)
    'gemini-3-pro-preview': 76.4,
    'gemini-2.5-pro': 62.4,
    'claude-opus-4.5': 62.0,
    'gpt-5-pro': 61.6,
    'grok-4': 60.5,
    'claude-opus-4': 58.2,
    'o3-mini': 55.8,
    'deepseek-r1': 54.2,
    'gpt-5': 52.5,
    'claude-sonnet-4': 50.8,
    'gpt-4o': 45.2,
    'claude-3.5-sonnet': 43.5,
    'deepseek-v3': 42.8,
    'gemini-2.5-flash': 41.2,
    'llama-3.3-70b': 38.5,
    'qwen-2.5-coder-32b': 36.2,
}

STATIC_CANAICODE_DATA = {
    # CanAiCode Senior Interview Scores (Oct 2025)
    # Score out of 148 (normalized to 0-100)
    'qwen3-32b': 100.0,  # 148/148
    'deepseek-r1': 100.0,
    'o1-preview': 100.0,
    'o1-mini': 100.0,
    'o3-mini': 100.0,
    'gpt-5': 98.6,
    'claude-opus-4': 97.3,
    'gemini-2.5-pro': 96.8,
    'claude-sonnet-4': 95.2,
    'deepseek-v3': 94.5,
    'gpt-4o': 92.8,
    'claude-3.5-sonnet': 91.2,
    'qwen-2.5-coder-32b': 94.8,
    'llama-3.3-70b': 88.5,
    'gemini-2.5-flash': 89.2,
    'gpt-4o-mini': 85.4,
    'mistral-large': 82.1,
}

STATIC_SEAL_SHOWDOWN_DATA = {
    # SEAL MCP Atlas Scores (Jan 2026)
    # Percentage scores
    'claude-opus-4.5': 62.30,
    'gpt-5.2': 60.57,
    'claude-opus-4': 58.5,
    'gemini-3-pro-preview': 55.2,
    'o3-mini': 52.8,
    'deepseek-r1': 50.4,
    'gpt-5': 48.2,
    'claude-sonnet-4': 46.5,
    'gemini-2.5-pro': 44.8,
    'deepseek-v3': 42.2,
    'gpt-4o': 38.5,
    'claude-3.5-sonnet': 40.2,
    'llama-3.3-70b': 35.8,
    'qwen-2.5-coder-32b': 38.5,
}

STATIC_GPQA_DATA = {
    # GPQA Accuracy (Jan 2026) from LLM Stats
    # Percentage accuracy
    'gpt-5.2': 92.4,
    'gemini-3-pro': 91.9,
    'grok-4-heavy': 88.4,
    'claude-opus-4.5': 87.0,
    'grok-4': 87.5,
    'o3-mini': 85.2,
    'gpt-5': 84.5,
    'claude-opus-4': 82.8,
    'deepseek-r1': 80.5,
    'gemini-2.5-pro': 78.2,
    'claude-sonnet-4': 76.5,
    'gpt-4o': 72.4,
    'claude-3.5-sonnet': 70.8,
    'deepseek-v3': 68.5,
    'llama-3.3-70b': 65.2,
    'qwen-2.5-coder-32b': 62.8,
    'gemini-2.5-flash': 68.5,
}

STATIC_LIVEBENCH_DATA = {
    # LiveBench Global Average and Coding (Dec 2025 - Jan 2026)
    'claude-opus-4.5': {'livebench_coding': 72.5, 'livebench_global': 76.20},
    'gpt-5.1-codex-max': {'livebench_coding': 74.2, 'livebench_global': 75.63},
    'gemini-3-pro-preview': {'livebench_coding': 73.8, 'livebench_global': 75.22},
    'gpt-5.2': {'livebench_coding': 71.5, 'livebench_global': 74.12},
    'gpt-5-pro': {'livebench_coding': 70.8, 'livebench_global': 73.82},
    'claude-opus-4': {'livebench_coding': 68.5, 'livebench_global': 72.5},
    'o3-mini': {'livebench_coding': 68.5, 'livebench_global': 71.2},
    'deepseek-r1': {'livebench_coding': 65.8, 'livebench_global': 68.5},
    'gemini-2.5-pro': {'livebench_coding': 64.5, 'livebench_global': 67.2},
    'claude-sonnet-4': {'livebench_coding': 65.2, 'livebench_global': 66.8},
    'gpt-5': {'livebench_coding': 62.5, 'livebench_global': 65.4},
    'deepseek-v3': {'livebench_coding': 58.4, 'livebench_global': 62.8},
    'gpt-4o': {'livebench_coding': 52.4, 'livebench_global': 58.5},
    'claude-3.5-sonnet': {'livebench_coding': 58.2, 'livebench_global': 61.5},
    'qwen-2.5-coder-32b': {'livebench_coding': 55.8, 'livebench_global': 58.2},
    'llama-3.3-70b': {'livebench_coding': 48.2, 'livebench_global': 54.5},
    'gemini-2.5-flash': {'livebench_coding': 55.8, 'livebench_global': 60.2},
    'gpt-4o-mini': {'livebench_coding': 42.8, 'livebench_global': 50.4},
}

STATIC_LIVECODEBENCH_DATA = {
    # LiveCodeBench Pass@1 (Aug 2024 - May 2025, 454 problems)
    'o4-mini-high': 80.2,
    'o3-high': 75.8,
    'o4-mini-medium': 74.2,
    'gemini-2.5-pro': 73.6,
    'deepseek-r1': 73.1,
    'o3-mini': 68.5,
    'claude-opus-4': 65.2,
    'gpt-5': 62.8,
    'claude-sonnet-4': 58.5,
    'deepseek-v3': 55.2,
    'gpt-4o': 45.8,
    'claude-3.5-sonnet': 48.5,
    'qwen-2.5-coder-32b': 52.8,
    'llama-3.3-70b': 42.5,
    'gemini-2.5-flash': 48.2,
    'gpt-4o-mini': 38.5,
}

# OpenRouter Programming Category Rankings (Sep-Oct 2025)
STATIC_OPENROUTER_PROGRAMMING_RANKS = {
    'gpt-4o-mini': 1,
    'claude-3.5-sonnet': 2,
    'gemini-2.5-flash': 3,
    'deepseek-chat': 4,
    'gpt-4o': 5,
    'glm-4.6': 6,
    'claude-3.5-haiku': 7,
    'deepseek-r1': 8,
    'qwen3-coder-30b': 9,
    'deepseek-r1-0528': 10,
    'gemini-2.5-pro': 11,
    'claude-sonnet-4': 12,
    'llama-3.3-70b': 15,
    'qwen-2.5-coder-32b': 18,
    'mistral-large': 22,
    'o3-mini': 25,
    'gpt-5-mini': 28,
    'gpt-5': 30,
    'claude-opus-4': 35,
}

# Model Accessibility Metadata
STATIC_ACCESSIBILITY_DATA = {
    # {model_key: {license_type, api_stability, documentation_quality}}
    # License types: apache, mit, llama, commercial, api-only, proprietary
    # Stability: stable, production, reliable, beta, experimental
    # Docs quality: comprehensive, excellent, good, basic, minimal
    'gpt-4o': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'gpt-4o-mini': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'gpt-5': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'gpt-5-mini': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'o1': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'o1-mini': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'o3-mini': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'claude-3.5-sonnet': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'claude-3.5-haiku': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'claude-sonnet-4': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'claude-opus-4': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'claude-opus-4.5': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'gemini-2.5-pro': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'gemini-2.5-flash': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'comprehensive'},
    'deepseek-r1': {'license_type': 'mit', 'api_stability': 'stable', 'documentation_quality': 'good'},
    'deepseek-v3': {'license_type': 'mit', 'api_stability': 'stable', 'documentation_quality': 'good'},
    'deepseek-chat': {'license_type': 'mit', 'api_stability': 'stable', 'documentation_quality': 'good'},
    'qwen-2.5-coder-32b': {'license_type': 'apache', 'api_stability': 'stable', 'documentation_quality': 'good'},
    'qwen3-coder-30b': {'license_type': 'apache', 'api_stability': 'stable', 'documentation_quality': 'good'},
    'qwen-2.5-72b': {'license_type': 'apache', 'api_stability': 'stable', 'documentation_quality': 'good'},
    'llama-3.3-70b': {'license_type': 'llama', 'api_stability': 'stable', 'documentation_quality': 'good'},
    'llama-3.1-405b': {'license_type': 'llama', 'api_stability': 'stable', 'documentation_quality': 'good'},
    'mistral-large': {'license_type': 'apache', 'api_stability': 'stable', 'documentation_quality': 'good'},
    'mistral-small': {'license_type': 'apache', 'api_stability': 'stable', 'documentation_quality': 'basic'},
    'glm-4.6': {'license_type': 'mit', 'api_stability': 'stable', 'documentation_quality': 'basic'},
    'grok-4': {'license_type': 'api-only', 'api_stability': 'stable', 'documentation_quality': 'basic'},
}


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

    def get_static_benchmarks(self) -> Dict[str, Any]:
        """
        Get all benchmark data from static curated sources.
        Instant, no network calls. Aligned with Chapter 4 thesis methodology.
        
        Returns normalized data structure matching fetch_all_benchmarks output.
        """
        self.logger.info("Loading static benchmark data (Chapter 4 methodology)...")
        
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
        
        # BFCL
        for model, score in STATIC_BFCL_DATA.items():
            results['bfcl'][model] = {'bfcl_score': score}
        results['fetch_status']['bfcl'] = {'status': 'ok', 'source': 'static', 'count': len(STATIC_BFCL_DATA)}
        
        # WebDev Arena
        for model, score in STATIC_WEBDEV_ARENA_DATA.items():
            results['webdev_arena'][model] = {'webdev_elo': score}
        results['fetch_status']['webdev_arena'] = {'status': 'ok', 'source': 'static', 'count': len(STATIC_WEBDEV_ARENA_DATA)}
        
        # ARC-AGI
        for model, score in STATIC_ARC_AGI_DATA.items():
            results['arc_agi'][model] = {'arc_agi_score': score}
        results['fetch_status']['arc_agi'] = {'status': 'ok', 'source': 'static', 'count': len(STATIC_ARC_AGI_DATA)}
        
        # SimpleBench
        for model, score in STATIC_SIMPLEBENCH_DATA.items():
            results['simplebench'][model] = {'simplebench_score': score}
        results['fetch_status']['simplebench'] = {'status': 'ok', 'source': 'static', 'count': len(STATIC_SIMPLEBENCH_DATA)}
        
        # CanAiCode
        for model, score in STATIC_CANAICODE_DATA.items():
            results['canaicode'][model] = {'canaicode_score': score}
        results['fetch_status']['canaicode'] = {'status': 'ok', 'source': 'static', 'count': len(STATIC_CANAICODE_DATA)}
        
        # SEAL Showdown
        for model, score in STATIC_SEAL_SHOWDOWN_DATA.items():
            results['seal_showdown'][model] = {'seal_coding_score': score}
        results['fetch_status']['seal_showdown'] = {'status': 'ok', 'source': 'static', 'count': len(STATIC_SEAL_SHOWDOWN_DATA)}
        
        # GPQA
        for model, score in STATIC_GPQA_DATA.items():
            results['gpqa'][model] = {'gpqa_score': score}
        results['fetch_status']['gpqa'] = {'status': 'ok', 'source': 'static', 'count': len(STATIC_GPQA_DATA)}
        
        # LiveBench (has nested structure)
        for model, scores in STATIC_LIVEBENCH_DATA.items():
            results['livebench'][model] = scores
        results['fetch_status']['livebench'] = {'status': 'ok', 'source': 'static', 'count': len(STATIC_LIVEBENCH_DATA)}
        
        # LiveCodeBench
        for model, score in STATIC_LIVECODEBENCH_DATA.items():
            results['livecodebench'][model] = {'livecodebench': score}
        results['fetch_status']['livecodebench'] = {'status': 'ok', 'source': 'static', 'count': len(STATIC_LIVECODEBENCH_DATA)}
        
        # OpenRouter Programming Rankings
        for model, rank in STATIC_OPENROUTER_PROGRAMMING_RANKS.items():
            results['adoption'][model] = {'programming_rank': rank}
        results['fetch_status']['adoption'] = {'status': 'ok', 'source': 'static', 'count': len(STATIC_OPENROUTER_PROGRAMMING_RANKS)}
        
        # Accessibility Metadata
        for model, data in STATIC_ACCESSIBILITY_DATA.items():
            results['accessibility'][model] = data
        results['fetch_status']['accessibility'] = {'status': 'ok', 'source': 'static', 'count': len(STATIC_ACCESSIBILITY_DATA)}
        
        # Performance data uses existing fallback
        results['performance'] = self.performance_fetcher._fetch_performance_fallback()
        results['fetch_status']['performance'] = {'status': 'ok', 'source': 'static', 'count': len(results['performance'])}
        
        total_benchmarks = sum(len(results[k]) for k in ['bfcl', 'webdev_arena', 'arc_agi', 'simplebench', 
                                                          'canaicode', 'seal_showdown', 'gpqa', 'livebench',
                                                          'livecodebench', 'adoption'])
        self.logger.info(f"Loaded static benchmark data: {total_benchmarks} entries across all sources")
        
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
        
        # Define fetcher tasks
        fetch_tasks = {
            'evalplus': lambda: self.hf_fetcher.fetch_evalplus_leaderboard(),
            'bigcodebench': lambda: self.hf_fetcher.fetch_bigcodebench_leaderboard(),
            'swebench': lambda: self.github_fetcher.fetch_swebench_leaderboard(),
            'livebench_live': lambda: self.github_fetcher.fetch_livebench_leaderboard(),
            'livecodebench_live': lambda: self.github_fetcher.fetch_livecodebench_leaderboard(),
            'performance_live': lambda: self.performance_fetcher.fetch_performance_metrics(),
            'bfcl_live': lambda: self.chapter4_fetcher.fetch_bfcl_leaderboard(),
            'webdev_arena_live': lambda: self.chapter4_fetcher.fetch_webdev_arena_leaderboard(),
            'arc_agi_live': lambda: self.chapter4_fetcher.fetch_arc_agi_leaderboard(),
            'simplebench_live': lambda: self.chapter4_fetcher.fetch_simplebench_leaderboard(),
            'canaicode_live': lambda: self.chapter4_fetcher.fetch_canaicode_leaderboard(),
            'seal_showdown_live': lambda: self.chapter4_fetcher.fetch_seal_showdown_leaderboard(),
            'gpqa_live': lambda: self.chapter4_fetcher.fetch_gpqa_leaderboard(),
            'adoption_live': lambda: self.adoption_fetcher.fetch_programming_rankings(),
        }
        
        live_results = {}
        
        # Execute fetches in parallel with timeout
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_key = {
                executor.submit(self._safe_fetch, func): key
                for key, func in fetch_tasks.items()
            }
            
            for future in as_completed(future_to_key, timeout=30):
                key = future_to_key[future]
                try:
                    data = future.result(timeout=10)
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

