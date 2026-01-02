"""
SARIF Utilities
===============

Shared utilities for SARIF file handling, extraction, and parsing.
Consolidates duplicate SARIF logic from analyzer_manager.py and task_execution_service.py.

This module provides:
- SARIF extraction from service results to separate files
- SARIF rule stripping to reduce file size
- Issue extraction from SARIF format
- Severity normalization for SARIF results
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ==============================================================================
# SARIF EXTRACTION
# ==============================================================================

def extract_sarif_to_files(
    services: Dict[str, Any],
    sarif_dir: Path,
    extraction_threshold_kb: int = 500
) -> Dict[str, Any]:
    """Extract SARIF data from service results to separate files.
    
    Returns a copy of services with SARIF data replaced by file references.
    Handles:
    - analysis.sarif_export (large SARIF aggregation)
    - analysis.tool_results.{tool}.sarif (dynamic/performance)
    - analysis.results.{category}.{tool}.sarif (static/security)
    - Large 'output' fields (>500KB)
    
    Args:
        services: Service results dict with structure {service_name: {analysis: {...}}}
        sarif_dir: Directory to write SARIF files to
        extraction_threshold_kb: Only extract output fields larger than this (KB)
        
    Returns:
        Copy of services with SARIF data replaced by file references
    """
    sarif_dir.mkdir(parents=True, exist_ok=True)
    services_copy = {}
    
    for service_name, service_data in services.items():
        if not isinstance(service_data, dict):
            services_copy[service_name] = service_data
            continue
        
        service_copy = dict(service_data)
        analysis = service_copy.get('analysis', {})
        
        if not isinstance(analysis, dict):
            services_copy[service_name] = service_copy
            continue
        
        analysis_copy = dict(analysis)
        
        # Handle sarif_export at analysis level (large SARIF aggregation)
        if 'sarif_export' in analysis_copy and isinstance(analysis_copy['sarif_export'], dict):
            sarif_export = analysis_copy['sarif_export']
            if 'sarif_file' not in sarif_export:  # Not already a reference
                sarif_json = json.dumps(sarif_export, default=str)
                size_kb = len(sarif_json.encode('utf-8')) / 1024
                
                if size_kb > extraction_threshold_kb:
                    filename = f"{service_name}_sarif_export.sarif.json"
                    file_path = sarif_dir / filename
                    
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(sarif_export, f, indent=2)
                        analysis_copy['sarif_export'] = {
                            'sarif_file': f"sarif/{filename}",
                            'extracted_size_kb': round(size_kb, 2),
                            'extracted_at': datetime.now(timezone.utc).isoformat()
                        }
                        logger.info(f"Extracted sarif_export for {service_name} ({size_kb:.1f}KB)")
                    except Exception as e:
                        logger.warning(f"Failed to extract sarif_export for {service_name}: {e}")
        
        # Handle tool_results (dynamic, performance analyzers)
        if 'tool_results' in analysis_copy and isinstance(analysis_copy['tool_results'], dict):
            tool_results_copy = {}
            for tool_name, tool_data in analysis_copy['tool_results'].items():
                if not isinstance(tool_data, dict):
                    tool_results_copy[tool_name] = tool_data
                    continue
                
                tool_copy = dict(tool_data)
                _extract_tool_sarif(tool_copy, tool_name, service_name, sarif_dir)
                _extract_large_output(tool_copy, tool_name, service_name, sarif_dir, extraction_threshold_kb)
                tool_results_copy[tool_name] = tool_copy
            
            analysis_copy['tool_results'] = tool_results_copy
        
        # Handle nested results structure (static, security analyzers)
        if 'results' in analysis_copy and isinstance(analysis_copy['results'], dict):
            results_copy = {}
            for category, category_data in analysis_copy['results'].items():
                if not isinstance(category_data, dict):
                    results_copy[category] = category_data
                    continue
                
                category_copy = {}
                for tool_name, tool_data in category_data.items():
                    if not isinstance(tool_data, dict):
                        category_copy[tool_name] = tool_data
                        continue
                    
                    tool_copy = dict(tool_data)
                    prefix = f"{service_name}_{category}"
                    _extract_tool_sarif(tool_copy, tool_name, prefix, sarif_dir)
                    _extract_large_output(tool_copy, tool_name, prefix, sarif_dir, extraction_threshold_kb)
                    category_copy[tool_name] = tool_copy
                
                results_copy[category] = category_copy
            
            analysis_copy['results'] = results_copy
        
        service_copy['analysis'] = analysis_copy
        services_copy[service_name] = service_copy
    
    return services_copy


def _extract_tool_sarif(
    tool_data: Dict[str, Any],
    tool_name: str,
    prefix: str,
    sarif_dir: Path
) -> None:
    """Extract SARIF from a single tool entry to a separate file.
    
    Modifies tool_data in place, replacing 'sarif' with 'sarif_file' reference.
    """
    sarif_data = tool_data.get('sarif')
    if not sarif_data or not isinstance(sarif_data, dict):
        return
    
    # Don't re-extract if already a reference
    if 'sarif_file' in sarif_data:
        return
    
    # Apply Ruff severity normalization before saving
    if is_ruff_sarif(tool_name, sarif_data):
        remap_ruff_sarif_severity(sarif_data)
    
    # Strip bulky rules to reduce file size
    stripped_sarif = strip_sarif_rules(sarif_data)
    
    safe_tool = tool_name.replace('/', '_').replace('\\', '_')
    filename = f"{prefix}_{safe_tool}.sarif.json"
    file_path = sarif_dir / filename
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(stripped_sarif, f, indent=2)
        
        tool_data['sarif'] = {
            'sarif_file': f"sarif/{filename}",
            'extracted_at': datetime.now(timezone.utc).isoformat()
        }
        logger.debug(f"Extracted SARIF for {tool_name} to {filename}")
    except Exception as e:
        logger.warning(f"Failed to extract SARIF for {tool_name}: {e}")


def _extract_large_output(
    tool_data: Dict[str, Any],
    tool_name: str,
    prefix: str,
    sarif_dir: Path,
    threshold_kb: int = 500
) -> None:
    """Extract large 'output' fields from tool entries to separate files.
    
    Modifies tool_data in place, replacing 'output' with 'output_file' reference.
    """
    output_data = tool_data.get('output')
    if not output_data:
        return
    
    # Don't re-extract if already a reference
    if isinstance(output_data, dict) and 'output_file' in output_data:
        return
    
    output_json = json.dumps(output_data, default=str) if not isinstance(output_data, str) else output_data
    size_kb = len(output_json.encode('utf-8')) / 1024
    
    if size_kb <= threshold_kb:
        return
    
    safe_tool = tool_name.replace('/', '_').replace('\\', '_')
    filename = f"{prefix}_{safe_tool}_output.json"
    file_path = sarif_dir / filename
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            if isinstance(output_data, str):
                f.write(output_data)
            else:
                json.dump(output_data, f, indent=2, default=str)
        
        tool_data['output'] = {
            'output_file': f"sarif/{filename}",
            'extracted_size_kb': round(size_kb, 2)
        }
        logger.debug(f"Extracted output for {tool_name} ({size_kb:.1f}KB)")
    except Exception as e:
        logger.warning(f"Failed to extract output for {tool_name}: {e}")


def strip_sarif_rules(sarif_data: Dict[str, Any]) -> Dict[str, Any]:
    """Strip bulky rule definitions from SARIF to reduce file size.
    
    SARIF 'tool.driver.rules' contains full rule catalog with lengthy descriptions.
    We preserve only: id, name, shortDescription (truncated to 200 chars).
    
    Args:
        sarif_data: Original SARIF document
        
    Returns:
        Copy of SARIF with stripped rules
    """
    if not isinstance(sarif_data, dict):
        return sarif_data
    
    # Make a deep-ish copy for the runs section
    result = dict(sarif_data)
    runs = sarif_data.get('runs', [])
    if not runs:
        return result
    
    result['runs'] = []
    for run in runs:
        if not isinstance(run, dict):
            result['runs'].append(run)
            continue
        
        run_copy = dict(run)
        tool = run.get('tool', {})
        if not isinstance(tool, dict):
            result['runs'].append(run_copy)
            continue
        
        tool_copy = dict(tool)
        driver = tool.get('driver', {})
        if not isinstance(driver, dict):
            run_copy['tool'] = tool_copy
            result['runs'].append(run_copy)
            continue
        
        driver_copy = dict(driver)
        rules = driver.get('rules', [])
        
        if rules:
            slim_rules = []
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                slim_rule = {'id': rule.get('id', '')}
                if rule.get('name'):
                    slim_rule['name'] = rule['name']
                if rule.get('shortDescription'):
                    short_desc = rule['shortDescription']
                    if isinstance(short_desc, dict) and 'text' in short_desc:
                        text = short_desc['text']
                        if len(text) > 200:
                            text = text[:200] + '...'
                        slim_rule['shortDescription'] = {'text': text}
                slim_rules.append(slim_rule)
            driver_copy['rules'] = slim_rules
        
        tool_copy['driver'] = driver_copy
        run_copy['tool'] = tool_copy
        result['runs'].append(run_copy)
    
    return result


# ==============================================================================
# SARIF PARSING / ISSUE EXTRACTION
# ==============================================================================

def extract_issues_from_sarif(sarif_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract issues/findings from SARIF format into normalized structure.
    
    Args:
        sarif_data: SARIF document (dict with 'runs' key)
        
    Returns:
        List of normalized issue dicts with keys:
        - severity: 'high', 'medium', 'low', 'info'
        - message: Human-readable description
        - file: File path
        - line: Line number
        - rule_id: Rule identifier
        - tool: Tool name (extracted from SARIF)
    """
    issues = []
    
    if not isinstance(sarif_data, dict):
        return issues
    
    runs = sarif_data.get('runs', [])
    if not isinstance(runs, list):
        return issues
    
    for run in runs:
        if not isinstance(run, dict):
            continue
        
        # Get tool name
        tool_name = (
            run.get('tool', {})
            .get('driver', {})
            .get('name', 'unknown')
        )
        
        results = run.get('results', [])
        if not isinstance(results, list):
            continue
        
        for result in results:
            if not isinstance(result, dict):
                continue
            
            # Extract location info
            locations = result.get('locations', [])
            file_path = ''
            line_number = 0
            
            if locations and isinstance(locations, list):
                loc = locations[0] if locations else {}
                if isinstance(loc, dict):
                    phys = loc.get('physicalLocation', {})
                    if isinstance(phys, dict):
                        artifact = phys.get('artifactLocation', {})
                        if isinstance(artifact, dict):
                            file_path = artifact.get('uri', '')
                            # Clean up container paths
                            file_path = file_path.replace('/app/sources/', '')
                        
                        region = phys.get('region', {})
                        if isinstance(region, dict):
                            line_number = region.get('startLine', 0)
            
            # Extract message
            message_obj = result.get('message', {})
            if isinstance(message_obj, dict):
                message = message_obj.get('text', '')
            elif isinstance(message_obj, str):
                message = message_obj
            else:
                message = ''
            
            # Extract severity from level
            level = result.get('level', 'warning')
            severity = _sarif_level_to_severity(level, result)
            
            issue = {
                'severity': severity,
                'message': message,
                'file': file_path,
                'line': line_number,
                'rule_id': result.get('ruleId', ''),
                'tool': tool_name
            }
            issues.append(issue)
    
    return issues


def _sarif_level_to_severity(level: str, result: Dict[str, Any]) -> str:
    """Convert SARIF level to normalized severity.
    
    SARIF levels: error, warning, note, none
    Our severities: high, medium, low, info
    
    Also checks result.properties['problem.severity'] for tool-specific overrides.
    """
    # Check for tool-specific severity in properties
    props = result.get('properties', {})
    if isinstance(props, dict):
        custom_sev = props.get('problem.severity')
        if custom_sev:
            custom_lower = str(custom_sev).lower()
            if custom_lower in ('critical', 'high'):
                return 'high'
            elif custom_lower in ('medium', 'warning'):
                return 'medium'
            elif custom_lower in ('low', 'info', 'note'):
                return 'low'
    
    # Map SARIF level to severity
    level_lower = str(level).lower()
    if level_lower in ('error', 'fatal'):
        return 'high'
    elif level_lower in ('warning', 'warn'):
        return 'medium'
    elif level_lower in ('note', 'info', 'none'):
        return 'low'
    
    return 'medium'  # Default


# ==============================================================================
# RUFF-SPECIFIC SARIF HANDLING
# ==============================================================================

def is_ruff_sarif(tool_name: str, sarif_data: Dict[str, Any]) -> bool:
    """Check if SARIF document is from Ruff linter."""
    if str(tool_name).lower() == 'ruff':
        return True
    
    runs = sarif_data.get('runs')
    if not isinstance(runs, list):
        return False
    
    for run in runs:
        if not isinstance(run, dict):
            continue
        driver_name = (
            run.get('tool', {})
            .get('driver', {})
            .get('name', '')
        )
        if isinstance(driver_name, str) and 'ruff' in driver_name.lower():
            return True
    
    return False


def remap_ruff_sarif_severity(sarif_data: Dict[str, Any]) -> None:
    """Remap Ruff SARIF severity levels to more accurate values.
    
    Ruff marks most findings as 'error' but many are actually style issues.
    This normalizes based on rule ID prefixes.
    
    Modifies sarif_data in place.
    """
    def _get_ruff_severity(rule_id: str) -> tuple:
        """Map Ruff rule ID to (level, severity_category)."""
        # Whitespace rules -> note/low
        if rule_id in ['W291', 'W292', 'W293', 'W503', 'W504', 'W605']:
            return ('note', 'low')
        
        # Import ordering -> warning/medium
        if rule_id.startswith('I') or rule_id in ['E401', 'E402']:
            return ('warning', 'medium')
        
        # Security rules
        if rule_id.startswith('S'):
            # High-risk security (hardcoded secrets, etc.)
            if rule_id in ['S104', 'S105', 'S106', 'S107', 'S108', 'S311', 'S324']:
                return ('error', 'high')
            return ('warning', 'medium')
        
        # Syntax errors -> high
        if rule_id in ['E999', 'F821', 'F822', 'F823']:
            return ('error', 'high')
        
        # Unused imports/variables -> medium
        if rule_id in ['F401', 'F403', 'F405', 'F841']:
            return ('warning', 'medium')
        
        # Complexity rules
        if rule_id.startswith('C') or rule_id in ['E501']:
            return ('warning', 'medium')
        
        # Comparison rules
        if rule_id.startswith('E7'):
            if rule_id in ['E711', 'E712', 'E721']:
                return ('warning', 'medium')
            return ('warning', 'low')
        
        # Other E rules -> medium
        if rule_id.startswith('E'):
            return ('warning', 'medium')
        
        return ('warning', 'low')
    
    runs = sarif_data.get('runs')
    if not isinstance(runs, list):
        return
    
    for run in runs:
        if not isinstance(run, dict):
            continue
        results = run.get('results')
        if not isinstance(results, list):
            continue
        
        for result in results:
            if not isinstance(result, dict):
                continue
            
            rule_id = result.get('ruleId')
            if not isinstance(rule_id, str) or not rule_id:
                continue
            
            level, severity_category = _get_ruff_severity(rule_id)
            result['level'] = level
            
            # Store severity category in properties
            props = result.get('properties')
            if not isinstance(props, dict):
                props = {}
                result['properties'] = props
            props['problem.severity'] = severity_category


# ==============================================================================
# SARIF LOADING / HYDRATION
# ==============================================================================

def load_sarif_from_reference(
    sarif_ref: Any,
    task_dir: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Load SARIF data from a reference (file path or inline dict).
    
    Args:
        sarif_ref: Either:
            - Inline SARIF dict (with 'runs' key)
            - Reference dict with 'sarif_file' key
            - String file path
        task_dir: Base directory for resolving relative paths
        
    Returns:
        SARIF dict or None if not found/invalid
    """
    if not sarif_ref:
        return None
    
    # Case 1: Inline SARIF document
    if isinstance(sarif_ref, dict) and isinstance(sarif_ref.get('runs'), list):
        return sarif_ref
    
    # Case 2: Reference dict with file path
    sarif_file = None
    if isinstance(sarif_ref, dict):
        sarif_file = (
            sarif_ref.get('sarif_file') or
            sarif_ref.get('path') or
            sarif_ref.get('file')
        )
    elif isinstance(sarif_ref, str):
        sarif_file = sarif_ref
    
    if not sarif_file or not task_dir:
        return None
    
    # Resolve and load file
    sarif_path = Path(sarif_file)
    if not sarif_path.is_absolute():
        sarif_path = (task_dir / sarif_path).resolve()
    
    # Security: ensure path is within task_dir
    try:
        sarif_path.relative_to(task_dir.resolve())
    except ValueError:
        logger.warning(f"Security: SARIF path {sarif_file} escapes task directory")
        return None
    
    if not sarif_path.exists():
        logger.debug(f"SARIF file not found: {sarif_path}")
        return None
    
    try:
        with open(sarif_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load SARIF from {sarif_path}: {e}")
        return None


def hydrate_tool_with_sarif(
    tool_data: Dict[str, Any],
    tool_name: str,
    task_dir: Optional[Path] = None
) -> None:
    """Hydrate tool data with issues extracted from SARIF if missing.
    
    Modifies tool_data in place:
    - Adds 'issues' list extracted from SARIF
    - Adds 'total_issues' count
    - Adds 'severity_breakdown' dict
    
    Args:
        tool_data: Tool result dict (may contain 'sarif' reference)
        tool_name: Name of tool (for Ruff detection)
        task_dir: Directory for resolving SARIF file references
    """
    if not isinstance(tool_data, dict):
        return
    
    # Skip if issues already present
    issues = tool_data.get('issues', [])
    if issues and len(issues) > 0:
        return
    
    sarif_ref = tool_data.get('sarif')
    if not sarif_ref:
        return
    
    sarif_data = load_sarif_from_reference(sarif_ref, task_dir)
    if not sarif_data:
        return
    
    # Apply Ruff severity normalization
    if is_ruff_sarif(tool_name, sarif_data):
        remap_ruff_sarif_severity(sarif_data)
    
    extracted_issues = extract_issues_from_sarif(sarif_data)
    if not extracted_issues:
        return
    
    tool_data['issues'] = extracted_issues
    tool_data['total_issues'] = len(extracted_issues)
    
    # Compute severity breakdown
    breakdown = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    for issue in extracted_issues:
        sev = str(issue.get('severity', 'info')).lower()
        if sev in breakdown:
            breakdown[sev] += 1
        else:
            breakdown['info'] += 1
    
    tool_data['severity_breakdown'] = breakdown
    logger.debug(f"Hydrated {len(extracted_issues)} issues for {tool_name} from SARIF")


# ==============================================================================
# SARIF SIZE ESTIMATION
# ==============================================================================

def estimate_sarif_size(sarif_data: Any) -> float:
    """Estimate the size of SARIF data in KB.
    
    Args:
        sarif_data: SARIF data (dict, str, or other JSON-serializable)
        
    Returns:
        Estimated size in KB
    """
    if sarif_data is None:
        return 0.0
    
    try:
        if isinstance(sarif_data, str):
            return len(sarif_data.encode('utf-8')) / 1024
        else:
            json_str = json.dumps(sarif_data, default=str)
            return len(json_str.encode('utf-8')) / 1024
    except Exception:
        return 0.0


# ==============================================================================
# SARIF EXTRACTION RESULT
# ==============================================================================

class SARIFExtractionResult:
    """Result container for SARIF extraction operations.
    
    Provides structured information about SARIF extraction including:
    - Number of files extracted
    - Total size of extracted files
    - Individual file paths and sizes
    - Any errors encountered
    """
    
    def __init__(self):
        self.files_extracted: int = 0
        self.total_size_kb: float = 0.0
        self.file_details: List[Dict[str, Any]] = []
        self.errors: List[str] = []
    
    def add_file(self, filename: str, size_kb: float, tool_name: str = None):
        """Record an extracted file."""
        self.files_extracted += 1
        self.total_size_kb += size_kb
        self.file_details.append({
            'filename': filename,
            'size_kb': round(size_kb, 2),
            'tool': tool_name
        })
    
    def add_error(self, error: str):
        """Record an extraction error."""
        self.errors.append(error)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'files_extracted': self.files_extracted,
            'total_size_kb': round(self.total_size_kb, 2),
            'file_details': self.file_details,
            'errors': self.errors,
            'success': len(self.errors) == 0
        }
    
    def __repr__(self):
        return f"SARIFExtractionResult(files={self.files_extracted}, size_kb={self.total_size_kb:.2f})"
