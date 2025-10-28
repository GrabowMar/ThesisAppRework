"""Centralized path constants for template/scaffolding directories.

All code should import from here instead of hardcoding paths.
"""
from __future__ import annotations
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../src/app -> project root
SRC_DIR = PROJECT_ROOT / 'src'
# misc/ lives at project root for templates and configs
MISC_DIR = PROJECT_ROOT / 'misc'
REPORTS_DIR = PROJECT_ROOT / 'reports'
RESULTS_DIR = PROJECT_ROOT / 'results'

# Legacy JSON files kept under misc/
PORT_CONFIG_JSON = MISC_DIR / 'port_config.json'
MODELS_SUMMARY_JSON = MISC_DIR / 'models_summary.json'

# V2 Template System (Jinja2-based)
TEMPLATES_V2_DIR = MISC_DIR / 'templates'
SCAFFOLDING_DIR = MISC_DIR / 'scaffolding'
REQUIREMENTS_DIR = MISC_DIR / 'requirements'

# Legacy template directories (deprecated, use V2 system above)
CODE_TEMPLATES_DIR = MISC_DIR / 'code_templates'
APP_TEMPLATES_DIR = MISC_DIR / 'app_templates'

# Future extension: profiles, histories, etc.
PROFILES_DIR = MISC_DIR / 'profiles'
HISTORY_DIR = MISC_DIR / '.history'

# ---------------------------------------------------------------------------
# Unified generated content root (all AI/generated artifacts live here)
# ---------------------------------------------------------------------------
GENERATED_ROOT = PROJECT_ROOT / 'generated'
GENERATED_APPS_DIR = GENERATED_ROOT / 'apps'

# Consolidated top-level folders: raw artifacts + metadata
GENERATED_RAW_API_DIR = GENERATED_ROOT / 'raw'
GENERATED_METADATA_DIR = GENERATED_ROOT / 'metadata'

# Raw output organization (still grouped for clarity inside the raw folder)
GENERATED_RAW_API_RESPONSES_DIR = GENERATED_RAW_API_DIR / 'responses'
GENERATED_RAW_API_PAYLOADS_DIR = GENERATED_RAW_API_DIR / 'payloads'

# Metadata organization: ONLY indices/runs/ for per-run comprehensive metadata
GENERATED_INDICES_DIR = GENERATED_METADATA_DIR / 'indices'

# Legacy metadata paths (kept for backwards compatibility in code, but not created)
GENERATED_MARKDOWN_DIR = GENERATED_METADATA_DIR / 'markdown'
GENERATED_STATS_DIR = GENERATED_METADATA_DIR / 'stats'
GENERATED_STATS_GENERATION_DIR = GENERATED_STATS_DIR / 'generation'
GENERATED_STATS_BATCH_DIR = GENERATED_STATS_DIR / 'batches'
GENERATED_FAILURES_DIR = GENERATED_METADATA_DIR / 'failures'
GENERATED_CAPABILITIES_DIR = GENERATED_METADATA_DIR / 'capabilities'
GENERATED_SUMMARIES_DIR = GENERATED_METADATA_DIR / 'summaries'
GENERATED_CONFIG_DIR = GENERATED_METADATA_DIR / 'config'
GENERATED_LARGE_CONTENT_DIR = GENERATED_METADATA_DIR / 'large_content'
GENERATED_LOGS_DIR = GENERATED_METADATA_DIR / 'logs'
GENERATED_TMP_DIR = GENERATED_METADATA_DIR / 'tmp'

_GENERATED_DIRS = [
    GENERATED_ROOT,
    GENERATED_APPS_DIR,
    GENERATED_RAW_API_DIR,
    GENERATED_RAW_API_RESPONSES_DIR,
    GENERATED_RAW_API_PAYLOADS_DIR,
    GENERATED_METADATA_DIR,
    GENERATED_INDICES_DIR,  # ONLY create indices/, subdirs created on-demand
]

for _p in _GENERATED_DIRS:
    try:
        _p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

__all__ = [
    'PROJECT_ROOT', 'SRC_DIR', 'MISC_DIR', 'REPORTS_DIR', 'RESULTS_DIR', 'PORT_CONFIG_JSON', 'MODELS_SUMMARY_JSON',
    'TEMPLATES_V2_DIR', 'SCAFFOLDING_DIR', 'REQUIREMENTS_DIR',
    'CODE_TEMPLATES_DIR', 'APP_TEMPLATES_DIR', 'PROFILES_DIR', 'HISTORY_DIR',
    'GENERATED_ROOT', 'GENERATED_APPS_DIR', 'GENERATED_RAW_API_DIR', 'GENERATED_METADATA_DIR',
    'GENERATED_RAW_API_RESPONSES_DIR', 'GENERATED_RAW_API_PAYLOADS_DIR', 'GENERATED_MARKDOWN_DIR',
    'GENERATED_STATS_DIR', 'GENERATED_STATS_GENERATION_DIR', 'GENERATED_STATS_BATCH_DIR',
    'GENERATED_FAILURES_DIR', 'GENERATED_CAPABILITIES_DIR', 'GENERATED_SUMMARIES_DIR',
    'GENERATED_CONFIG_DIR', 'GENERATED_LARGE_CONTENT_DIR', 'GENERATED_INDICES_DIR',
    'GENERATED_LOGS_DIR', 'GENERATED_TMP_DIR'
]
