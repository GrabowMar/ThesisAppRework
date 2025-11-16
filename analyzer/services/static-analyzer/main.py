#!/usr/bin/env python3
"""
Static Analyzer Service - Comprehensive Code Quality Analysis
============================================================

Modular static analysis service with strict tool selection gating.
Runs per-language analyzers and reports results with accurate tools_used.
"""

import asyncio
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

# Import shared path resolution utility
from analyzer.shared.path_utils import resolve_app_source_path

from analyzer.shared.service_base import BaseWSService
from parsers import parse_tool_output
from sarif_parsers import parse_tool_output_to_sarif, build_sarif_document, get_available_sarif_parsers


class StaticAnalyzer(BaseWSService):
    """Comprehensive static analyzer for multiple languages."""

    def __init__(self):
        super().__init__(service_name="static-analyzer", default_port=2001, version="1.0.0")
        # Default ignore patterns for heavy/noisy directories
        self.default_ignores = [
            'node_modules', 'dist', 'build', '.next', '.nuxt', '.cache',
            '.venv', 'venv', '__pycache__', '.git', '.tox', '.mypy_cache',
            'coverage', 'site-packages'
        ]

    async def _run_tool(self, cmd: List[str], tool_name: str, config: Optional[Dict] = None, timeout: int = 120, success_exit_codes: List[int] = [0], skip_parser: bool = False) -> Dict[str, Any]:
        """
        Run a tool and capture its output, parsing with tool-specific parsers.
        
        Args:
            cmd: Command to execute
            tool_name: Name of the tool for parser selection
            config: Configuration dict to include in parsed output
            timeout: Command timeout in seconds
            success_exit_codes: List of exit codes considered successful
            skip_parser: If True, return raw output without parsing (for SARIF tools)
            
        Returns:
            Standardized result dictionary with parsed issues
        """
        self.log.info(f"Running {tool_name}: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode not in success_exit_codes:
                error_message = f"{tool_name} exited with {result.returncode}. Stderr: {result.stderr[:500]}"
                self.log.error(error_message)
                return {'tool': tool_name, 'executed': True, 'status': 'error', 'error': error_message, 'exit_code': result.returncode}

            if not result.stdout:
                return {'tool': tool_name, 'executed': True, 'status': 'success', 'issues': [], 'total_issues': 0, 'issue_count': 0}

            # Skip parser for SARIF tools - they handle output themselves
            if skip_parser:
                return {'tool': tool_name, 'executed': True, 'status': 'success', 'output': result.stdout, 'issue_count': 0}

            try:
                raw_output = json.loads(result.stdout)
                # Use tool-specific parser to standardize output
                parsed_result = parse_tool_output(tool_name, raw_output, config)
                
                # Generate SARIF representation if supported
                sarif_run = parse_tool_output_to_sarif(tool_name, raw_output, config)
                if sarif_run:
                    parsed_result['sarif'] = sarif_run
                    self.log.debug(f"Generated SARIF output for {tool_name}")
                
                return parsed_result
            except json.JSONDecodeError as e:
                # Handle tools that output text or newline-delimited JSON (mypy, vulture)
                # Pass raw text to parser which handles format detection
                try:
                    parsed_result = parse_tool_output(tool_name, result.stdout, config)
                    if parsed_result.get('status') in ('success', 'no_issues', 'completed'):
                        # Parser successfully handled the output
                        # Ensure issue_count is present for uniform status display
                        if 'issue_count' not in parsed_result:
                            parsed_result['issue_count'] = parsed_result.get('total_issues', len(parsed_result.get('issues', [])))
                        return parsed_result
                except Exception as parse_err:
                    self.log.warning(f"{tool_name} parser failed: {parse_err}")
                
                # Final fallback: treat as text output
                self.log.warning(f"{tool_name} produced non-JSON output: {e}")
                sarif_run = parse_tool_output_to_sarif(tool_name, result.stdout, config)
                fallback_result = {'tool': tool_name, 'executed': True, 'status': 'success', 'output': result.stdout[:1000], 'issue_count': 0}
                if sarif_run:
                    fallback_result['sarif'] = sarif_run
                    self.log.debug(f"Generated SARIF output for text-based {tool_name}")
                return fallback_result

        except FileNotFoundError:
            self.log.error(f"{tool_name} not found. Is it installed and in PATH?")
            return {'tool': tool_name, 'executed': False, 'status': 'error', 'error': f'{tool_name} not found'}
        except subprocess.TimeoutExpired:
            self.log.error(f"{tool_name} timed out after {timeout} seconds.")
            return {'tool': tool_name, 'executed': True, 'status': 'error', 'error': 'Timeout expired'}
        except Exception as e:
            self.log.error(f"An unexpected error occurred with {tool_name}: {e}")
            return {'tool': tool_name, 'executed': True, 'status': 'error', 'error': str(e)}

    def _detect_available_tools(self) -> List[str]:
        tools: List[str] = []
        # Check Python tools
        for tool in ['bandit', 'pylint', 'mypy', 'semgrep', 'snyk', 'safety', 'pip-audit', 'vulture', 'ruff']:
            try:
                result = subprocess.run([tool, '--version'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    tools.append(tool)
                    self.log.debug(f"{tool} available")
            except Exception as e:
                self.log.debug(f"{tool} not available: {e}")
        
        # Check Node.js tools
        for tool in ['eslint', 'npm-audit', 'stylelint']:
            try:
                # npm-audit is a subcommand, check npm itself
                check_cmd = ['npm', '--version'] if tool == 'npm-audit' else [tool, '--version']
                result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    tools.append(tool)
                    self.log.debug(f"{tool} available")
            except Exception as e:
                self.log.debug(f"{tool} not available: {e}")
        
        return tools
    
    def _generate_pylintrc(self, config: Dict[str, Any]) -> str:
        """Generate .pylintrc configuration file content."""
        # Default disabled checks to avoid fatal errors on generated code
        default_disabled = [
            'missing-docstring', 'too-few-public-methods', 'import-error',
            'no-member', 'no-name-in-module', 'unused-import', 'wrong-import-order',
            'ungrouped-imports', 'wrong-import-position', 'invalid-name'
        ]
        rcfile_content = f"""[MAIN]
jobs={config.get('jobs', 0)}
load-plugins={','.join(config.get('load_plugins', []))}

[MESSAGES CONTROL]
disable={','.join(config.get('disable', default_disabled))}
enable={','.join(config.get('enable', []))}

[REPORTS]
output-format={config.get('output_format', 'json')}
reports={'yes' if config.get('reports', False) else 'no'}
score={'yes' if config.get('score', True) else 'no'}

[FORMAT]
max-line-length={config.get('max_line_length', 100)}
max-module-lines={config.get('max_module_lines', 1000)}

[DESIGN]
max-args=5
max-attributes=7
max-bool-expr=5
max-branches=12
max-locals=15
max-parents=7
max-public-methods=20
max-returns=6
max-statements=50
min-public-methods=2

[BASIC]
good-names={','.join(config.get('good_names', ['i', 'j', 'k', 'ex', 'Run', '_', 'id', 'pk']))}
bad-names={','.join(config.get('bad_names', ['foo', 'bar', 'baz', 'toto', 'tutu', 'tata']))}

[REFACTORING]
max-nested-blocks={config.get('max_nested_blocks', 5)}
"""
        return rcfile_content
    
    def _pylint_severity_to_sarif(self, pylint_type: str) -> str:
        """Convert pylint message type to SARIF level."""
        mapping = {
            'fatal': 'error',
            'error': 'error',
            'warning': 'warning',
            'convention': 'note',
            'refactor': 'note',
            'information': 'note'
        }
        return mapping.get(pylint_type.lower(), 'warning')
    
    async def analyze_python_files(self, source_path: Path, config: Optional[Dict[str, Any]] = None, selected_tools: Optional[Set[str]] = None) -> Dict[str, Any]:
        """Run Python static analysis tools with custom configuration.

        Only executes tools included in selected_tools when provided.
        """
        # Avoid traversing huge directories
        def _iter_py_files(base: Path):
            for p in base.rglob('*.py'):
                # Skip if any ignore directory is in its parents
                if any(part in self.default_ignores for part in p.parts):
                    continue
                yield p

        python_files = list(_iter_py_files(source_path))
        if not python_files:
            return {'status': 'no_files', 'message': 'No Python files found'}
        
        results: Dict[str, Any] = {}
        
        # Get configuration settings
        bandit_config = config.get('bandit', {}) if config else {}
        pylint_config = config.get('pylint', {}) if config else {}
        mypy_config = config.get('mypy', {}) if config else {}
        safety_config = config.get('safety', {}) if config else {}
        vulture_config = config.get('vulture', {}) if config else {}
        semgrep_config = config.get('semgrep', {}) if config else {}
        
        # Bandit security analysis with SARIF output
        if (
            'bandit' in self.available_tools
            and (selected_tools is None or 'bandit' in selected_tools)
            and bandit_config.get('enabled', True)
        ):
            # Build exclude list
            exclude_dirs = bandit_config.get('exclude_dirs') or self.default_ignores
            exclude_arg = ','.join(str(source_path / d) for d in exclude_dirs)
            # Use native SARIF format output
            cmd = ['bandit', '-r', str(source_path), '-x', exclude_arg, '-f', 'sarif', '-o', '/tmp/bandit_output.sarif']
            
            if bandit_config.get('skips'):
                cmd.extend(['--skip', ','.join(bandit_config['skips'])])
            else:
                cmd.extend(['--skip', 'B101'])

            # Run and read SARIF output
            result = await self._run_tool(cmd, 'bandit', config=bandit_config, success_exit_codes=[0, 1], skip_parser=True)
            if result.get('status') != 'error':
                try:
                    with open('/tmp/bandit_output.sarif', 'r') as f:
                        sarif_data = json.load(f)
                        result['sarif'] = sarif_data
                        result['format'] = 'sarif'
                        # Extract issue count from SARIF
                        total_issues = 0
                        if 'runs' in sarif_data:
                            for run in sarif_data['runs']:
                                total_issues += len(run.get('results', []))
                        result['total_issues'] = total_issues
                except Exception as e:
                    self.log.warning(f"Could not read bandit SARIF output: {e}")
            results['bandit'] = result
        
        # Pylint code quality
        if (
            'pylint' in self.available_tools
            and (selected_tools is None or 'pylint' in selected_tools)
            and pylint_config.get('enabled', True)
            and python_files
        ):
            try:
                # Create temporary pylintrc file
                pylintrc_content = self._generate_pylintrc(pylint_config)
                
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.pylintrc', delete=False) as f:
                    f.write(pylintrc_content)
                    pylintrc_file = f.name
                
                max_files = pylint_config.get('max_files', 10)
                files_to_check = python_files[:max_files]
                
                cmd = ['pylint', '--rcfile', pylintrc_file, '--output-format=json'] + [str(f) for f in files_to_check]
                
                # Pylint uses bitflags: 1=fatal, 2=error, 4=warning, 8=refactor, 16=convention, 32=usage error
                result = await self._run_tool(cmd, 'pylint', config=pylint_config, 
                                                        success_exit_codes=[0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32])
                
                # Convert JSON to SARIF format manually
                if result.get('status') != 'error' and 'output' in result:
                    try:
                        pylint_issues = json.loads(result['output'])
                        
                        # Create SARIF structure
                        sarif_data = {
                            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
                            "version": "2.1.0",
                            "runs": [{
                                "tool": {
                                    "driver": {
                                        "name": "pylint",
                                        "informationUri": "https://pylint.pycqa.org/",
                                        "version": "latest"
                                    }
                                },
                                "results": [
                                    {
                                        "ruleId": issue.get('message-id', issue.get('symbol', 'unknown')),
                                        "level": self._pylint_severity_to_sarif(issue.get('type', 'warning')),
                                        "message": {"text": issue.get('message', '')},
                                        "locations": [{
                                            "physicalLocation": {
                                                "artifactLocation": {"uri": issue.get('path', '')},
                                                "region": {
                                                    "startLine": issue.get('line', 0),
                                                    "startColumn": issue.get('column', 0)
                                                }
                                            }
                                        }]
                                    }
                                    for issue in pylint_issues
                                ]
                            }]
                        }
                        
                        result['sarif'] = sarif_data
                        result['format'] = 'sarif'
                    except Exception as e:
                        self.log.warning(f"Could not convert pylint output to SARIF: {e}")
                
                results['pylint'] = result
                os.unlink(pylintrc_file)

            except Exception as e:
                self.log.error(f"Pylint analysis failed: {e}")
                results['pylint'] = {'tool': 'pylint', 'executed': True, 'status': 'error', 'error': str(e)}

        # Semgrep multi-language security analysis with SARIF output
        if (
            'semgrep' in self.available_tools
            and (selected_tools is None or 'semgrep' in selected_tools)
            and semgrep_config.get('enabled', True)
        ):
            # Use SARIF format for better standardization
            cmd = ['semgrep', 'scan', '--sarif', '--config=auto', str(source_path)]
            result = await self._run_tool(cmd, 'semgrep', config=semgrep_config, skip_parser=True)
            if result.get('status') != 'error' and 'output' in result:
                try:
                    sarif_data = json.loads(result['output'])
                    result['sarif'] = sarif_data
                    result['format'] = 'sarif'
                    # Extract issue count
                    total_issues = 0
                    if 'runs' in sarif_data:
                        for run in sarif_data['runs']:
                            total_issues += len(run.get('results', []))
                    result['total_issues'] = total_issues
                except Exception as e:
                    self.log.warning(f"Could not parse semgrep SARIF output: {e}")
            results['semgrep'] = result

        # Mypy type checking
        if (
            'mypy' in self.available_tools
            and (selected_tools is None or 'mypy' in selected_tools)
            and mypy_config.get('enabled', True)
            and python_files
        ):
            # Use mypy with JSON output to stdout (newline-delimited JSON)
            cmd = ['mypy', '--output', 'json', '--show-error-codes', '--no-error-summary', 
                   '--ignore-missing-imports', '--no-incremental', '--cache-dir', '/tmp/mypy_cache']
            max_files = mypy_config.get('max_files', 10)
            files_to_check = python_files[:max_files]
            cmd.extend([str(f) for f in files_to_check])

            # MyPy with JSON format (exit codes: 0=no issues, 1=issues found, 2=fatal error)
            # Parser now handles newline-delimited JSON natively
            results['mypy'] = await self._run_tool(cmd, 'mypy', config=mypy_config, success_exit_codes=[0, 1])

        # Safety dependency vulnerability scanning
        if (
            'safety' in self.available_tools
            and (selected_tools is None or 'safety' in selected_tools)
            and safety_config.get('enabled', True)
        ):
            # Check multiple common locations for requirements files
            requirements_locations = [
                source_path / 'requirements.txt',
                source_path / 'backend' / 'requirements.txt',
                source_path / 'api' / 'requirements.txt',
                source_path / 'server' / 'requirements.txt',
            ]
            
            requirements_file = None
            for location in requirements_locations:
                if location.exists() and location.is_file():
                    requirements_file = location
                    self.log.info(f"Found requirements file at: {location.relative_to(source_path)}")
                    break
            
            if not requirements_file:
                self.log.info("Skipping Safety - no requirements.txt found in common locations")
                results['safety'] = {
                    'tool': 'safety',
                    'executed': False,
                    'status': 'skipped',
                    'message': 'No requirements.txt file found',
                    'total_issues': 0
                }
            else:
                try:
                    cmd = ['safety', 'scan', '--output', 'json', '--file', str(requirements_file)]
                    # Parser handles all output formatting
                    results['safety'] = await self._run_tool(cmd, 'safety', config=safety_config, success_exit_codes=[0, 1, 64])
                except Exception as e:
                    self.log.warning(f"Safety scan failed: {e}")
                    results['safety'] = {
                        'tool': 'safety',
                        'executed': True,
                        'status': 'error',
                        'error': f'Safety execution error: {str(e)}',
                        'total_issues': 0
                    }
        
        # pip-audit as fallback CVE scanner (doesn't require authentication)
        if requirements_file and requirements_file.exists():
            pip_audit_config = config.get('pip-audit', {}) if config else {}
            if (
                'pip-audit' in self.available_tools
                and (selected_tools is None or 'pip-audit' in selected_tools)
                and pip_audit_config.get('enabled', True)
            ):
                try:
                    self.log.info(f"Running pip-audit on: {requirements_file}")
                    cmd = ['pip-audit', '--format', 'json', '--requirement', str(requirements_file)]
                    
                    pip_audit_result = await self._run_tool(cmd, 'pip-audit', config=pip_audit_config, success_exit_codes=[0, 1], skip_parser=True)
                    
                    if pip_audit_result.get('status') != 'error' and 'output' in pip_audit_result:
                        try:
                            audit_data = json.loads(pip_audit_result['output'])
                            vulnerabilities = audit_data.get('vulnerabilities', [])
                            
                            results['pip-audit'] = {
                                'tool': 'pip-audit',
                                'executed': True,
                                'status': 'success',
                                'vulnerabilities': vulnerabilities,
                                'total_issues': len(vulnerabilities),
                                'issue_count': len(vulnerabilities),
                                'format': 'json'
                            }
                            self.log.info(f"pip-audit found {len(vulnerabilities)} CVEs")
                        except Exception as e:
                            self.log.warning(f"Could not parse pip-audit output: {e}")
                            results['pip-audit'] = pip_audit_result
                    else:
                        results['pip-audit'] = pip_audit_result
                        
                except Exception as e:
                    self.log.warning(f"pip-audit scan failed: {e}")
                    results['pip-audit'] = {
                        'tool': 'pip-audit',
                        'executed': True,
                        'status': 'error',
                        'error': f'pip-audit execution error: {str(e)}',
                        'total_issues': 0
                    }

        # Vulture dead code detection
        if (
            'vulture' in self.available_tools
            and (selected_tools is None or 'vulture' in selected_tools)
            and vulture_config.get('enabled', True)
            and python_files
        ):
            cmd = ['vulture', str(source_path)]
            if vulture_config.get('min_confidence'):
                cmd.extend(['--min-confidence', str(vulture_config['min_confidence'])])

            # Vulture returns: 0=no issues, 1=dead code found, 3=syntax errors in checked files
            # All are valid outcomes for analysis purposes
            # Note: Vulture outputs text, not JSON, so we parse it manually
            vulture_result = await self._run_tool(cmd, 'vulture', success_exit_codes=[0, 1, 3])

            if vulture_result.get('status') == 'error':
                results['vulture'] = vulture_result
            elif vulture_result.get('status') == 'completed':
                # Vulture returned text output (expected behavior)
                dead_code_findings = []
                if 'output' in vulture_result:
                    for line in vulture_result['output'].splitlines():
                        if ':' in line and ('unused' in line.lower() or 'unreachable' in line.lower()):
                            parts = line.split(':', 2)
                            if len(parts) >= 3:
                                dead_code_findings.append({
                                    'filename': parts[0],
                                    'line': int(parts[1]) if parts[1].isdigit() else 0,
                                    'message': parts[2].strip()
                                })
                
                results['vulture'] = {
                    'tool': 'vulture',
                    'executed': True,
                    'status': 'success',
                    'results': dead_code_findings,
                    'total_issues': len(dead_code_findings),
                    'issue_count': len(dead_code_findings),
                    'config_used': vulture_config
                }
            else:
                # No output case
                results['vulture'] = {
                    'tool': 'vulture',
                    'executed': True,
                    'status': 'success',
                    'results': [],
                    'total_issues': 0,
                    'issue_count': 0,
                    'config_used': vulture_config
                }
        
        # Ruff - Fast Python linter with SARIF support (replaces flake8)
        ruff_config = config.get('ruff', {}) if config else {}
        if (
            'ruff' in self.available_tools
            and (selected_tools is None or 'ruff' in selected_tools or 'flake8' in (selected_tools or set()))
            and ruff_config.get('enabled', True)
            and python_files
        ):
            # Ruff supports SARIF output natively via --output-format=sarif
            # Use /tmp for cache to avoid permission issues
            cmd = ['ruff', 'check', '--output-format=sarif', '--cache-dir', '/tmp/ruff_cache', str(source_path)]
            result = await self._run_tool(cmd, 'ruff', config=ruff_config, success_exit_codes=[0, 1], skip_parser=True)
            if result.get('status') != 'error' and 'output' in result:
                try:
                    sarif_data = json.loads(result['output'])
                    result['sarif'] = sarif_data
                    result['format'] = 'sarif'
                    # Extract issue count
                    total_issues = 0
                    if 'runs' in sarif_data:
                        for run in sarif_data['runs']:
                            total_issues += len(run.get('results', []))
                    result['total_issues'] = total_issues
                except Exception as e:
                    self.log.warning(f"Could not parse ruff SARIF output: {e}")
            results['ruff'] = result
            # Also add as 'flake8' for backward compatibility
            if 'flake8' in (selected_tools or set()):
                results['flake8'] = result
        

        
        # Summarize per-tool status for Python analyzers (always generate)
        # Use underscore prefix to signal this is internal metadata, not a tool result
        try:
            summary = {}
            for name in ['bandit', 'pylint', 'semgrep', 'mypy', 'safety', 'vulture', 'ruff', 'flake8']:
                t = results.get(name)
                if isinstance(t, dict):
                    try:
                        summary[name] = {
                            'executed': bool(t.get('executed', False)),
                            'status': t.get('status', 'unknown'),
                            'total_issues': int(t.get('total_issues', 0)),
                            'error': t.get('error') if 'error' in t else None,
                            'format': t.get('format', 'json')  # Track output format (sarif/json)
                        }
                    except Exception as e:
                        self.log.error(f"Error creating _metadata for {name}: {e}")
                        summary[name] = {
                            'executed': False,
                            'status': 'error',
                            'total_issues': 0,
                            'error': f'Failed to create status: {str(e)}',
                            'format': 'unknown'
                        }
                else:
                    # Tool not in results - mark as not executed
                    summary[name] = {
                        'executed': False,
                        'status': 'not_run',
                        'total_issues': 0,
                        'error': None,
                        'format': None
                    }
            # Store as _metadata (underscore prefix signals internal use)
            results['_metadata'] = summary
        except Exception as e:
            self.log.error(f"Error creating _metadata summary: {e}")
            # Fallback minimal status
            results['_metadata'] = {'error': str(e)}

        return results
    
    async def analyze_javascript_files(self, source_path: Path, config: Optional[Dict[str, Any]] = None, selected_tools: Optional[Set[str]] = None) -> Dict[str, Any]:
        """Run JavaScript/TypeScript static analysis with custom configuration.

        Only executes tools included in selected_tools when provided.
        """
        js_files = []
        for pattern in ['*.js', '*.jsx', '*.ts', '*.tsx', '*.vue']:
            for p in source_path.rglob(pattern):
                if any(part in self.default_ignores for part in p.parts):
                    continue
                js_files.append(p)
        
        if not js_files:
            return {'status': 'no_files', 'message': 'No JavaScript/TypeScript files found'}
        
        results: Dict[str, Any] = {}
        eslint_config = config.get('eslint', {}) if config else {}
        jshint_config = config.get('jshint', {}) if config else {}
        snyk_config = config.get('snyk', {}) if config else {}
        
        # ESLint analysis
        if (
            'eslint' in self.available_tools
            and (selected_tools is None or 'eslint' in selected_tools)
            and eslint_config.get('enabled', True)
        ):
            try:
                # Use ESLint with Microsoft SARIF formatter
                # ESLint will use .eslintrc.json config file if present
                cmd = ['eslint', '--format', '@microsoft/eslint-formatter-sarif']
                
                if len(js_files) <= 20:
                    cmd.extend([str(f) for f in js_files])
                else:
                    cmd.append(str(source_path))

                result = await self._run_tool(cmd, 'eslint', config=eslint_config, success_exit_codes=[0, 1, 2], skip_parser=True)
                if result.get('status') != 'error' and 'output' in result:
                    try:
                        sarif_data = json.loads(result['output'])
                        result['sarif'] = sarif_data
                        result['format'] = 'sarif'
                        # Extract issue count
                        total_issues = 0
                        if 'runs' in sarif_data:
                            for run in sarif_data['runs']:
                                total_issues += len(run.get('results', []))
                        result['total_issues'] = total_issues
                    except Exception as e:
                        self.log.warning(f"Could not parse eslint SARIF output: {e}")
                results['eslint'] = result
            except Exception as e:
                self.log.error(f"ESLint analysis failed: {e}")
                results['eslint'] = {'tool': 'eslint', 'executed': True, 'status': 'error', 'error': str(e)}

        # npm audit for JavaScript dependency vulnerabilities
        # Search for package.json in the source directory and subdirectories (e.g., frontend/)
        package_json_files = list(source_path.rglob('package.json'))
        # Filter out node_modules
        package_json_files = [pj for pj in package_json_files if 'node_modules' not in pj.parts]
        
        for package_json in package_json_files:
            npm_audit_config = config.get('npm-audit', {}) if config else {}
            if (
                'npm-audit' in self.available_tools
                and (selected_tools is None or 'npm-audit' in selected_tools)
                and npm_audit_config.get('enabled', True)
            ):
                try:
                    self.log.info(f"Running npm audit on: {package_json.parent}")
                    # npm audit must be run in the directory containing package.json
                    cmd = ['npm', 'audit', '--json']
                    
                    # Change to package.json directory for npm audit
                    original_cwd = Path.cwd()
                    try:
                        import os
                        os.chdir(package_json.parent)
                        
                        npm_audit_result = await self._run_tool(cmd, 'npm-audit', config=npm_audit_config, success_exit_codes=[0, 1], skip_parser=True)
                        
                        if npm_audit_result.get('status') != 'error' and 'output' in npm_audit_result:
                            try:
                                audit_data = json.loads(npm_audit_result['output'])
                                vulnerabilities = audit_data.get('vulnerabilities', {})
                                
                                # Count total CVEs
                                total_cves = sum(1 for v in vulnerabilities.values() if isinstance(v, dict))
                                
                                results['npm-audit'] = {
                                    'tool': 'npm-audit',
                                    'executed': True,
                                    'status': 'success',
                                    'vulnerabilities': vulnerabilities,
                                    'total_issues': total_cves,
                                    'issue_count': total_cves,
                                    'format': 'json'
                                }
                                self.log.info(f"npm audit found {total_cves} CVEs")
                            except Exception as e:
                                self.log.warning(f"Could not parse npm audit output: {e}")
                                results['npm-audit'] = npm_audit_result
                        else:
                            results['npm-audit'] = npm_audit_result
                    finally:
                        os.chdir(original_cwd)
                        
                except Exception as e:
                    self.log.warning(f"npm audit scan failed: {e}")
                    results['npm-audit'] = {
                        'tool': 'npm-audit',
                        'executed': True,
                        'status': 'error',
                        'error': f'npm audit execution error: {str(e)}',
                        'total_issues': 0
                    }

        # Snyk Code vulnerability analysis
        if (
            'snyk' in self.available_tools
            and (selected_tools is None or 'snyk' in selected_tools)
            and snyk_config.get('enabled', True)
        ):
            cmd = ['snyk', 'code', 'test', '--json', str(source_path)]
            
            snyk_result = await self._run_tool(cmd, 'snyk', success_exit_codes=[0, 1])

            if snyk_result.get('status') == 'error':
                error_msg = snyk_result.get('error', '').lower()
                # Check for authentication or not configured errors
                if 'authenticate' in error_msg or 'auth' in error_msg or 'token' in error_msg or snyk_result.get('exit_code') == 2:
                    results['snyk'] = {'tool': 'snyk', 'executed': False, 'status': 'skipped', 'message': 'Snyk authentication required (use SNYK_TOKEN env variable)'}
                else:
                    results['snyk'] = snyk_result
            else:
                total_issues = 0
                if 'runs' in snyk_result:
                    for run in snyk_result['runs']:
                        total_issues += len(run.get('results', []))
                elif 'vulnerabilities' in snyk_result:
                    total_issues = len(snyk_result['vulnerabilities'])
                
                results['snyk'] = {
                    'tool': 'snyk',
                    'executed': True,
                    'status': 'success',
                    'results': snyk_result,
                    'total_issues': total_issues,
                    'issue_count': total_issues,
                    'config_used': snyk_config
                }

        # Summarize per-tool status for JS analyzers
        # Use underscore prefix to signal this is internal metadata, not a tool result
        try:
            summary = {}
            for name in ['eslint', 'jshint', 'snyk']:
                t = results.get(name)
                if isinstance(t, dict):
                    summary[name] = {
                        'executed': bool(t.get('executed')),
                        'status': t.get('status'),
                        'total_issues': int(t.get('total_issues', 0)),
                        'error': t.get('error') if 'error' in t else None,
                    }
            if summary:
                results['_metadata'] = summary
        except Exception:
            pass

        return results
    
    async def analyze_css_files(self, source_path: Path, config: Optional[Dict[str, Any]] = None, selected_tools: Optional[Set[str]] = None) -> Dict[str, Any]:
        """Run CSS static analysis. Only executes tools included in selected_tools when provided."""
        css_files = []
        for pattern in ['*.css', '*.scss', '*.sass', '*.less']:
            for p in source_path.rglob(pattern):
                if any(part in self.default_ignores for part in p.parts):
                    continue
                css_files.append(p)
        
        if not css_files:
            return {'status': 'no_files', 'message': 'No CSS files found'}
        
        results: Dict[str, Any] = {}
        
        # Stylelint analysis
        stylelint_cfg = (config or {}).get('stylelint', {})
        if (
            'stylelint' in self.available_tools
            and (selected_tools is None or 'stylelint' in selected_tools)
            and stylelint_cfg.get('enabled', True)
        ):
            # Create a basic stylelint config to avoid configuration errors
            import tempfile
            stylelint_config = {
                "extends": "stylelint-config-standard",
                "rules": {}
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.stylelintrc.json', delete=False) as f:
                json.dump(stylelint_config, f, indent=2)
                config_file = f.name
            
            cmd = ['stylelint', '--config', config_file, '--formatter', 'json']
            if css_files:
                cmd.extend([str(p) for p in css_files])
            else:
                cmd.append(str(source_path / '**/*.css'))

            stylelint_result = await self._run_tool(cmd, 'stylelint', success_exit_codes=[0, 1, 2, 78])  # 78 = config error
            
            os.unlink(config_file)

            if stylelint_result.get('status') == 'error':
                results['stylelint'] = stylelint_result
            else:
                stylelint_data = stylelint_result if isinstance(stylelint_result, list) else []
                total_issues = sum(len(file_result.get('warnings', [])) if isinstance(file_result, dict) else 0 for file_result in stylelint_data)
                results['stylelint'] = {
                    'tool': 'stylelint',
                    'executed': True,
                    'status': 'success',
                    'results': stylelint_data,
                    'total_issues': total_issues,
                    'issue_count': total_issues
                }
        
        return results
    
    async def analyze_project_structure(self, source_path: Path) -> Dict[str, Any]:
        """Analyze overall project structure and files.
        
        Returns metadata about the project, not tool results.
        This is wrapped under 'project_metadata' to avoid confusion with tools.
        """
        try:
            file_counts = {
                'python': len(list(source_path.rglob('*.py'))),
                'javascript': len(list(source_path.rglob('*.js'))) + len(list(source_path.rglob('*.jsx'))),
                'typescript': len(list(source_path.rglob('*.ts'))) + len(list(source_path.rglob('*.tsx'))),
                'css': len(list(source_path.rglob('*.css'))),
                'html': len(list(source_path.rglob('*.html'))),
                'json': len(list(source_path.rglob('*.json'))),
                'dockerfile': len(list(source_path.rglob('Dockerfile*'))),
                'docker_compose': len(list(source_path.rglob('docker-compose*.yml')))
            }
            
            # Check for common security files
            security_files = {
                'requirements_txt': (source_path / 'requirements.txt').exists(),
                'package_json': (source_path / 'package.json').exists(),
                'dockerfile': len(list(source_path.rglob('Dockerfile*'))) > 0,
                'gitignore': (source_path / '.gitignore').exists()
            }
            
            # Wrap in _project_metadata to prevent parsing as tools
            return {
                'status': 'success',
                '_project_metadata': {
                    'file_counts': file_counts,
                    'security_files': security_files,
                    'total_files': sum(file_counts.values())
                }
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    # Use BaseWSService.send_progress instead of local progress helper

    async def analyze_model_code(self, model_slug: str, app_number: int, config: Optional[Dict[str, Any]] = None, analysis_id: Optional[str] = None, selected_tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Perform comprehensive static analysis on AI model code with custom configuration."""
        try:
            # Resolve path supporting both flat and template-based structures
            model_path = resolve_app_source_path(model_slug, app_number)
            
            if model_path is None or not model_path.exists():
                return {
                    'status': 'error',
                    'error': f'Model path not found for {model_slug} app{app_number} (checked flat and template structures)'
                }
            
            self.log.info(f"Static analysis of {model_slug} app {app_number}")
            await self.send_progress('starting', f"Starting static analysis for {model_slug} app {app_number}", analysis_id=analysis_id,
                                 model_slug=model_slug, app_number=app_number)
            
            # Normalize selected tools to a lowercase set for comparisons
            selected_set: Optional[set] = None
            if selected_tools:
                try:
                    selected_set = {t.lower() for t in selected_tools}
                except Exception:
                    selected_set = None

            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'tools_used': [],  # will be populated based on executed tools
                'configuration_applied': config is not None,
                'results': {}
            }
            
            # Run analysis for different file types with configuration
            self.log.info("Analyzing Python files...")
            await self.send_progress('scanning_python', 'Scanning Python files', analysis_id=analysis_id)
            py_res = await self.analyze_python_files(model_path, config, selected_set)
            results['results']['python'] = py_res
            try:
                count = 0
                if isinstance(py_res, dict):
                    if 'bandit' in py_res and isinstance(py_res['bandit'], dict):
                        count += int(py_res['bandit'].get('total_issues', 0))
                    if 'pylint' in py_res and isinstance(py_res['pylint'], dict):
                        count += int(py_res['pylint'].get('total_issues', 0))
                    if 'semgrep' in py_res and isinstance(py_res['semgrep'], dict):
                        count += int(py_res['semgrep'].get('total_issues', 0))
                    if 'mypy' in py_res and isinstance(py_res['mypy'], dict):
                        count += int(py_res['mypy'].get('total_issues', 0))
                    if 'safety' in py_res and isinstance(py_res['safety'], dict):
                        count += int(py_res['safety'].get('total_issues', 0))
                    if 'vulture' in py_res and isinstance(py_res['vulture'], dict):
                        count += int(py_res['vulture'].get('total_issues', 0))
                await self.send_progress('python_completed', f"Python analysis complete ({count} findings)", analysis_id=analysis_id,
                                     issues_found=count)
            except Exception:
                pass
            
            self.log.info("Analyzing JavaScript files...")
            await self.send_progress('scanning_js', 'Scanning JavaScript/TypeScript files', analysis_id=analysis_id)
            js_res = await self.analyze_javascript_files(model_path, config, selected_set)
            results['results']['javascript'] = js_res
            try:
                count = 0
                if isinstance(js_res, dict):
                    if 'eslint' in js_res and isinstance(js_res['eslint'], dict):
                        count += int(js_res['eslint'].get('total_issues', 0))
                    if 'jshint' in js_res and isinstance(js_res['jshint'], dict):
                        count += int(js_res['jshint'].get('total_issues', 0))
                    if 'snyk' in js_res and isinstance(js_res['snyk'], dict):
                        count += int(js_res['snyk'].get('total_issues', 0))
                await self.send_progress('js_completed', f"JS/TS analysis complete ({count} findings)", analysis_id=analysis_id,
                                     issues_found=count)
            except Exception:
                pass
            
            self.log.info("Analyzing CSS files...")
            await self.send_progress('scanning_css', 'Scanning CSS files', analysis_id=analysis_id)
            css_res = await self.analyze_css_files(model_path, config, selected_set)
            results['results']['css'] = css_res
            
            self.log.info("Analyzing project structure...")
            await self.send_progress('analyzing_structure', 'Analyzing project structure', analysis_id=analysis_id)
            structure_result = await self.analyze_project_structure(model_path)
            # Extract _project_metadata to top level to avoid treating it as a tool
            if structure_result.get('_project_metadata'):
                results['_project_metadata'] = structure_result['_project_metadata']
            results['results']['structure'] = {'status': structure_result.get('status', 'unknown')}
            
            # Calculate enhanced summary and derive tools_used strictly from executed tools
            total_issues = 0
            tools_run = 0
            severity_breakdown = {'error': 0, 'warning': 0, 'info': 0}
            used_tools: List[str] = []
            
            for lang_results in results['results'].values():
                if isinstance(lang_results, dict):
                    for tool_name, tool_result in lang_results.items():
                        if not isinstance(tool_result, dict):
                            continue
                        # Only count as executed if tool result explicitly marks executed True
                        if tool_result.get('executed') and tool_name not in used_tools:
                            used_tools.append(tool_name)
                        if isinstance(tool_result, dict) and tool_result.get('status') == 'success':
                            tools_run += 1
                            total_issues += tool_result.get('total_issues', 0)
                            
                            # Aggregate severity breakdown if available
                            if 'severity_breakdown' in tool_result:
                                for severity, count in tool_result['severity_breakdown'].items():
                                    severity_breakdown[severity] = severity_breakdown.get(severity, 0) + count
            
            results['summary'] = {
                'total_issues_found': total_issues,
                'tools_run_successfully': tools_run,
                'severity_breakdown': severity_breakdown,
                'analysis_status': 'completed',
                'configuration_preset': config.get('preset_name', 'custom') if config else 'default'
            }
            results['tools_used'] = used_tools
            
            # Collect SARIF runs and build SARIF document if any tools generated SARIF
            sarif_runs = []
            for lang_results in results['results'].values():
                if isinstance(lang_results, dict):
                    for tool_result in lang_results.values():
                        if isinstance(tool_result, dict) and 'sarif' in tool_result:
                            sarif_runs.append(tool_result['sarif'])
            
            if sarif_runs:
                results['sarif_export'] = build_sarif_document(sarif_runs)
                self.log.info(f"Generated SARIF document with {len(sarif_runs)} tool runs")
            
            await self.send_progress('reporting', 'Compiling report', analysis_id=analysis_id,
                                 total_issues=total_issues, tools_run=tools_run)
            await self.send_progress('completed', 'Static analysis completed', analysis_id=analysis_id,
                                 total_issues=total_issues)
            
            return results
            
        except Exception as e:
            self.log.error(f"Static analysis failed: {e}")
            await self.send_progress('failed', f"Static analysis failed: {e}", analysis_id=analysis_id)
            return {
                'status': 'error',
                'error': str(e),
                'model_slug': model_slug,
                'app_number': app_number
            }
    
    async def handle_message(self, websocket, message_data):
        """Handle incoming WebSocket messages."""
        try:
            msg_type = message_data.get("type", "unknown")
            
            if msg_type == "static_analyze":
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 1)
                config = message_data.get("config", None)
                analysis_id = message_data.get("id")
                # Tool selection normalized
                tools = list(self.extract_selected_tools(message_data) or [])
                
                self.log.info(f"Starting static analysis for {model_slug} app {app_number}")
                if config:
                    self.log.info(f"Using custom configuration: {list(config.keys())}")
                
                analysis_results = await self.analyze_model_code(
                    model_slug, app_number, config, analysis_id=analysis_id, selected_tools=tools
                )
                
                response = {
                    "type": "static_analysis_result",
                    "status": "success",
                    "service": self.info.name,
                    "analysis": analysis_results,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Retry logic for WebSocket send (handle connection issues)
                max_retries = 3
                retry_delay = 1
                
                for attempt in range(max_retries):
                    try:
                        response_json = json.dumps(response)
                        await websocket.send(response_json)
                        self.log.info(f"Static analysis completed for {model_slug} app {app_number}")
                        break  # Success - exit retry loop
                    except TypeError as e:
                        self.log.error(f"Failed to serialize response: {e}")
                        # Send error response instead
                        error_response = {
                            "type": "static_analysis_result",
                            "status": "error",
                            "service": self.info.name,
                            "error": f"Serialization error: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        }
                        await websocket.send(json.dumps(error_response))
                        break  # Don't retry serialization errors
                    except Exception as send_err:
                        if attempt < max_retries - 1:
                            self.log.warning(f"WebSocket send failed (attempt {attempt + 1}/{max_retries}): {send_err}. Retrying...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            self.log.error(f"WebSocket send failed after {max_retries} attempts: {send_err}")
                            raise
                
            else:
                response = {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                    "service": self.info.name
                }
                await websocket.send(json.dumps(response))
                
        except Exception as e:
            self.log.error(f"Error handling message: {e}")
            error_response = {
                "type": "error",
                "message": f"Internal error: {str(e)}",
                "service": self.info.name
            }
            try:
                await websocket.send(json.dumps(error_response))
            except Exception:
                pass

async def main():
    service = StaticAnalyzer()
    await service.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
