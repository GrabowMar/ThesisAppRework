"""
Reports generation module.

Contains specialized report generators for different analysis perspectives.
"""
from .base_generator import BaseReportGenerator
from .loc_utils import count_loc_from_generated_files
from .report_constants import KNOWN_TOOLS, CWE_CATEGORIES
from .report_utils import (
    extract_tools_from_services,
    extract_findings_from_services,
    calculate_scientific_metrics,
    extract_cwe_statistics,
)
from .app_report_generator import AppReportGenerator
from .tool_report_generator import ToolReportGenerator

__all__ = [
    'BaseReportGenerator',
    'AppReportGenerator',
    'ToolReportGenerator',
    'count_loc_from_generated_files',
    'KNOWN_TOOLS',
    'CWE_CATEGORIES',
    'extract_tools_from_services',
    'extract_findings_from_services',
    'calculate_scientific_metrics',
    'extract_cwe_statistics',
]
