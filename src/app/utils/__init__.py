"""Utility package init."""
"""
Utilities Package

This package contains utility functions and helper classes used throughout
the application for common tasks like validation, formatting, and data processing.
Also includes shared analysis utilities for SARIF handling, tool normalization,
and unified result building.
"""

from .helpers import (
    safe_json_loads,
    safe_json_dumps,
    format_datetime,
    parse_model_slug,
    get_app_directory,
    check_app_exists,
    get_docker_project_name,
    calculate_percentage,
    truncate_text,
    validate_model_slug,
    validate_app_number,
    sanitize_filename,
    deep_merge_dicts,
    extract_error_message,
    is_valid_url,
    format_file_size,
    create_error_response,
    create_success_response,
    retry_operation,
    Timer
)

from .validators import (
    validate_model_slug as validate_model_slug_detailed,
    validate_app_number as validate_app_number_detailed,
    validate_analysis_types,
    validate_batch_config,
    validate_app_range,
    validate_security_tools,
    validate_performance_config,
    validate_file_path,
    validate_url,
    sanitize_input
)

# Shared analysis utilities
from .sarif_utils import (
    extract_sarif_to_files,
    strip_sarif_rules,
    extract_issues_from_sarif,
    load_sarif_from_reference,
    hydrate_tool_with_sarif,
    estimate_sarif_size,
    is_ruff_sarif,
    remap_ruff_sarif_severity,
    SARIFExtractionResult
)

from .tool_normalization import (
    SEVERITY_LEVELS,
    SEVERITY_MAP,
    normalize_severity,
    compare_severity,
    get_severity_breakdown,
    normalize_tool_status,
    is_success_status,
    collect_normalized_tools,
    aggregate_findings_from_services,
    categorize_services,
    determine_overall_status
)

from .result_builder import (
    SCHEMA_VERSION,
    SCHEMA_NAME,
    UnifiedResultBuilder,
    build_result_from_services,
    save_result_to_filesystem,
    build_universal_format,
    load_result_file,
    get_result_summary
)

__all__ = [
    # Helper functions
    'safe_json_loads',
    'safe_json_dumps',
    'format_datetime',
    'parse_model_slug',
    'get_app_directory',
    'check_app_exists',
    'get_docker_project_name',
    'calculate_percentage',
    'truncate_text',
    'validate_model_slug',
    'validate_app_number',
    'sanitize_filename',
    'deep_merge_dicts',
    'extract_error_message',
    'is_valid_url',
    'format_file_size',
    'create_error_response',
    'create_success_response',
    'retry_operation',
    'Timer',
    
    # Validation functions
    'validate_model_slug_detailed',
    'validate_app_number_detailed',
    'validate_analysis_types',
    'validate_batch_config',
    'validate_app_range',
    'validate_security_tools',
    'validate_performance_config',
    'validate_file_path',
    'validate_url',
    'sanitize_input',
    
    # SARIF utilities
    'extract_sarif_to_files',
    'strip_sarif_rules',
    'extract_issues_from_sarif',
    'load_sarif_from_reference',
    'hydrate_tool_with_sarif',
    'estimate_sarif_size',
    'is_ruff_sarif',
    'remap_ruff_sarif_severity',
    'SARIFExtractionResult',
    
    # Tool normalization
    'SEVERITY_LEVELS',
    'SEVERITY_MAP',
    'normalize_severity',
    'compare_severity',
    'get_severity_breakdown',
    'normalize_tool_status',
    'is_success_status',
    'collect_normalized_tools',
    'aggregate_findings_from_services',
    'categorize_services',
    'determine_overall_status',
    
    # Result builder
    'SCHEMA_VERSION',
    'SCHEMA_NAME',
    'UnifiedResultBuilder',
    'build_result_from_services',
    'save_result_to_filesystem',
    'build_universal_format',
    'load_result_file',
    'get_result_summary'
]
