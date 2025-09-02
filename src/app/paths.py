"""Centralized path constants for template/scaffolding directories.

All code should import from here instead of hardcoding paths.
"""
from __future__ import annotations
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../src/app -> project root
SRC_DIR = PROJECT_ROOT / 'src'
MISC_DIR = SRC_DIR / 'misc'

# Unified directories (no nested duplicates)
CODE_TEMPLATES_DIR = MISC_DIR / 'code_templates'
APP_TEMPLATES_DIR = MISC_DIR / 'app_templates'

# Future extension: profiles, histories, etc.
PROFILES_DIR = MISC_DIR / 'profiles'
HISTORY_DIR = MISC_DIR / '.history'

__all__ = [
    'PROJECT_ROOT', 'SRC_DIR', 'MISC_DIR', 'CODE_TEMPLATES_DIR', 'APP_TEMPLATES_DIR', 'PROFILES_DIR', 'HISTORY_DIR'
]
