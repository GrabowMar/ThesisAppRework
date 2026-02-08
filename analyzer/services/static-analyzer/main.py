#!/usr/bin/env python3
"""
Static Analyzer Service - Comprehensive Code Quality Analysis
============================================================

Modular static analysis service with strict tool selection gating.
Runs per-language analyzers and reports results with accurate tools_used.

Configuration files are loaded from analyzer/configs/ folder.
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
from analyzer.shared.tool_logger import ToolExecutionLogger
from parsers import parse_tool_output
from sarif_parsers import parse_tool_output_to_sarif, build_sarif_document, remap_ruff_sarif_severity

# Import configuration loader
try:
    from analyzer.config_loader import get_config_loader
    CONFIG_LOADER_AVAILABLE = True
except ImportError:
    CONFIG_LOADER_AVAILABLE = False


def _extract_sarif_severity(sarif_data: Dict[str, Any]) -> Dict[str, int]:
    """Extract severity breakdown from SARIF data.
    
    Maps SARIF levels: error→high, warning→medium, note→low, none/missing→info.
    Also checks rule-level defaultConfiguration as fallback.
    """
    severity = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    
    # Build rule-level severity lookup from tool.driver.rules
    rule_levels = {}
    for run in sarif_data.get('runs', []):
        driver = run.get('tool', {}).get('driver', {})
        for rule in driver.get('rules', []):
            rule_id = rule.get('id', '')
            default_level = rule.get('defaultConfiguration', {}).get('level', '')
            if rule_id and default_level:
                rule_levels[rule_id] = default_level
        
        for result in run.get('results', []):
            level = result.get('level', '')
            if not level:
                # Fallback to rule-level default
                level = rule_levels.get(result.get('ruleId', ''), 'note')
            
            if level in ('error',):
                severity['high'] += 1
            elif level in ('warning',):
                severity['medium'] += 1
            elif level in ('note',):
                severity['low'] += 1
            else:
                severity['info'] += 1
    
    return {k: v for k, v in severity.items() if v > 0}


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
        # Initialize tool execution logger for comprehensive output logging
        self.tool_logger = ToolExecutionLogger(self.log)

    async def _run_tool(self, cmd: List[str], tool_name: str, config: Optional[Dict] = None, timeout: int = 120, success_exit_codes: List[int] = [0], skip_parser: bool = False, retries: int = 0) -> Dict[str, Any]:
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
        import time
        
        # Log command start
        self.tool_logger.log_command_start(tool_name, cmd)
        
        start_time = time.time()
        try:
            # Use asyncio subprocess to avoid blocking the event loop
            # This allows WebSocket ping/pong to continue during long-running tools
            # Provide DEVNULL as stdin to prevent EOF errors from tools expecting input
            
            for attempt in range(retries + 1):
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdin=asyncio.subprocess.DEVNULL,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    try:
                        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()
                        raise subprocess.TimeoutExpired(cmd, timeout)
                    
                    # If we are here, execution finished. Check return code if it's a known flaky error
                    # But _run_tool mainly checks returncode later.
                    # However, for Sys_error in semgrep (exit code 2 usually), we might want to retry if allowed.
                    
                    # Create a temporary result to check success
                    temp_result_code = proc.returncode
                    
                    # If success or not out of retries, break (we handle error mapping below)
                    # BUT: logical issue - if we want to retry on specific error codes, we need to know them.
                    # For now, we retry on ANY failure if retries > 0, or maybe just exceptions?
                    # The request specifically mentioned Sys_error which often causes non-zero exit.
                    
                    # Let's trust the process: if it returns, we use it. 
                    # Note: We need to handle the case where we WANT to retry on non-success result.
                    
                    if temp_result_code in success_exit_codes:
                        break # Success
                        
                    # If failure and we have retries left
                    if attempt < retries:
                        self.log.warning(f"Tool {tool_name} failed with code {temp_result_code} (attempt {attempt+1}/{retries+1}). Retrying...")
                        await asyncio.sleep(1) # Backoff
                        continue
                        
                except Exception as e:
                    # If unexpected exception (like OS error) and retries left
                    if attempt < retries:
                        self.log.warning(f"Tool {tool_name} raised exception {e} (attempt {attempt+1}/{retries+1}). Retrying...")
                        await asyncio.sleep(1)
                        continue
                    raise e # Re-raise if no retries left

            # Proc and stdout/stderr are from the last attempt


            
            # Create a result object compatible with subprocess.run output
            class SubprocessResult:
                def __init__(self, returncode, stdout, stderr):
                    self.returncode = returncode
                    self.stdout = stdout.decode('utf-8', errors='replace') if stdout else ''
                    self.stderr = stderr.decode('utf-8', errors='replace') if stderr else ''
            
            result = SubprocessResult(proc.returncode, stdout, stderr)
            duration = time.time() - start_time
            
            # Check if this is a successful exit code
            is_success = result.returncode in success_exit_codes
            
            # Log command completion with outputs
            exec_record = self.tool_logger.log_command_complete(
                tool_name, cmd, result, duration, is_success=is_success  # type: ignore[arg-type]
            )
            
            if result.returncode not in success_exit_codes:
                error_message = f"{tool_name} exited with {result.returncode}. Stderr: {result.stderr[:500]}"
                self.log.error(error_message)
                return {'tool': tool_name, 'executed': True, 'status': 'error', 'error': error_message, 'exit_code': result.returncode, 'execution_record': exec_record}

            if not result.stdout:
                return {'tool': tool_name, 'executed': True, 'status': 'success', 'issues': [], 'total_issues': 0, 'issue_count': 0, 'execution_record': exec_record}

            # Skip parser for SARIF tools - they handle output themselves
            if skip_parser:
                return {'tool': tool_name, 'executed': True, 'status': 'success', 'output': result.stdout, 'issue_count': 0, 'execution_record': exec_record}

            try:
                # Log parser start
                self.tool_logger.log_parser_start(tool_name, len(result.stdout), 'json')
                
                raw_output = json.loads(result.stdout)
                # Use tool-specific parser to standardize output
                parsed_result = parse_tool_output(tool_name, raw_output, config)
                
                # Log parser completion
                severity_breakdown = parsed_result.get('severity_breakdown')
                issue_count = parsed_result.get('total_issues', parsed_result.get('issue_count', 0))
                self.tool_logger.log_parser_complete(tool_name, issue_count, severity_breakdown)
                
                # Generate SARIF representation if supported
                sarif_run = parse_tool_output_to_sarif(tool_name, raw_output, config)
                if sarif_run:
                    parsed_result['sarif'] = sarif_run
                    self.log.debug(f"Generated SARIF output for {tool_name}")
                
                # Attach execution record for debugging
                parsed_result['execution_record'] = exec_record
                return parsed_result
            except json.JSONDecodeError as e:
                # Attempt fallback parsing for text/NDJSON tools (mypy) before logging error
                try:
                    self.tool_logger.log_parser_start(tool_name, len(result.stdout), 'text')
                    parsed_result = parse_tool_output(tool_name, result.stdout, config)
                    if parsed_result.get('status') in ('success', 'no_issues', 'completed'):
                        # Parser successfully handled the output
                        # Ensure issue_count is present for uniform status display
                        if 'issue_count' not in parsed_result:
                            parsed_result['issue_count'] = parsed_result.get('total_issues', len(parsed_result.get('issues', [])))
                        # Log successful text parsing
                        issue_count = parsed_result.get('issue_count', 0)
                        self.tool_logger.log_parser_complete(tool_name, issue_count)
                        parsed_result['execution_record'] = exec_record
                        return parsed_result
                    elif tool_name not in ['mypy']:
                        # Only log the original JSON error if fallback didn't return a clear success
                        # and it's not a tool known to output NDJSON/text (like mypy)
                        self.tool_logger.log_parser_error(tool_name, e, result.stdout[:200])

                except Exception as parse_err:
                    # Fallback failed, log both errors
                    self.tool_logger.log_parser_error(tool_name, e, result.stdout[:200])
                    self.tool_logger.log_parser_error(tool_name, parse_err)
                    self.log.warning(f"{tool_name} parser failed: {parse_err}")
                
                # If we're here, fallback failed or returned non-success status
                
                # Final fallback: treat as text output
                self.log.warning(f"{tool_name} produced non-JSON output: {e}")
                sarif_run = parse_tool_output_to_sarif(tool_name, result.stdout, config)
                fallback_result = {'tool': tool_name, 'executed': True, 'status': 'success', 'output': result.stdout[:1000], 'issue_count': 0, 'execution_record': exec_record}
                if sarif_run:
                    fallback_result['sarif'] = sarif_run
                    self.log.debug(f"Generated SARIF output for text-based {tool_name}")
                return fallback_result

        except FileNotFoundError:
            self.log.error(f"{tool_name} not found. Is it installed and in PATH?")
            return {'tool': tool_name, 'executed': False, 'status': 'error', 'error': f'{tool_name} not found'}
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.log.error(f"{tool_name} timed out after {timeout} seconds.")
            self.log.info(f"[TOOL-EXEC] {tool_name}: ✗ TIMEOUT | duration={duration:.2f}s")
            return {'tool': tool_name, 'executed': True, 'status': 'error', 'error': 'Timeout expired', 'duration': duration}
        except Exception as e:
            self.log.error(f"An unexpected error occurred with {tool_name}: {e}")
            return {'tool': tool_name, 'executed': True, 'status': 'error', 'error': str(e)}

    def _detect_available_tools(self) -> List[str]:
        tools: List[str] = []
        self.log.info("Starting tool detection...")
        # Check Python tools
        for tool in ['bandit', 'pylint', 'mypy', 'semgrep', 'snyk', 'safety', 'pip-audit', 'vulture', 'ruff', 'radon', 'detect-secrets']:
            try:
                result = subprocess.run([tool, '--version'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    tools.append(tool)
                    self.log.info(f"{tool} available")
            except Exception as e:
                self.log.info(f"{tool} not available: {e}")
        
        self.log.info("Finished Python tools detection. Starting Node.js tools detection...")
        
        # Check Node.js tools
        for tool in ['eslint', 'npm-audit', 'stylelint', 'html-validator']:
            try:
                self.log.info(f"Checking {tool}...")
                # npm-audit is a subcommand, check npm itself
                check_cmd = ['npm', '--version'] if tool == 'npm-audit' else [tool, '--version']
                result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    tools.append(tool)
                    self.log.info(f"{tool} available")
                else:
                    self.log.warning(f"{tool} check failed with code {result.returncode}: {result.stderr}")
            except Exception as e:
                self.log.warning(f"{tool} not available: {e}")
        
        self.log.info(f"Detected tools: {tools}")
        return tools

    def _strip_sarif_rules(self, sarif_data: Dict[str, Any]) -> Dict[str, Any]:
        """Strip bulky rule definitions from SARIF to reduce file size.
        
        SARIF 'tool.driver.rules' contains full rule catalog (thousands of entries
        with lengthy descriptions). We preserve only minimal rule info needed for
        display: id, name, shortDescription.
        
        This reduces Semgrep output by ~60-80% (85k+ lines -> ~5k lines).
        """
        if not isinstance(sarif_data, dict):
            return sarif_data
            
        runs = sarif_data.get('runs', [])
        for run in runs:
            if not isinstance(run, dict):
                continue
            tool = run.get('tool', {})
            if not isinstance(tool, dict):
                continue
            driver = tool.get('driver', {})
            if not isinstance(driver, dict):
                continue
            
            rules = driver.get('rules', [])
            if rules:
                # Keep only essential fields: id, name, shortDescription
                slim_rules = []
                for rule in rules:
                    if not isinstance(rule, dict):
                        continue
                    slim_rule = {
                        'id': rule.get('id', ''),
                    }
                    if rule.get('name'):
                        slim_rule['name'] = rule['name']
                    if rule.get('shortDescription'):
                        # Keep shortDescription but truncate if very long
                        short_desc = rule['shortDescription']
                        if isinstance(short_desc, dict) and 'text' in short_desc:
                            text = short_desc['text'][:200] if len(short_desc.get('text', '')) > 200 else short_desc['text']
                            slim_rule['shortDescription'] = {'text': text}
                    slim_rules.append(slim_rule)
                driver['rules'] = slim_rules
                self.log.info(f"Stripped SARIF rules: {len(rules)} -> {len(slim_rules)} (kept id/name/shortDesc only)")
        
        return sarif_data
    
    def _detect_python_framework(self, source_path: Path) -> Dict[str, bool]:
        """Detect which Python web frameworks are used in the source code.
        
        Scans Python files and requirements.txt for framework indicators to avoid
        applying irrelevant Semgrep rules (e.g., Django rules on Flask apps).
        
        Returns:
            Dict with framework names as keys and boolean presence as values.
        """
        frameworks = {
            'flask': False,
            'django': False,
            'fastapi': False,
            'tornado': False,
            'bottle': False,
            'pyramid': False,
        }
        
        # Framework detection patterns (imports and common usage)
        patterns = {
            'flask': [
                'from flask import', 'import flask', 
                'Flask(__name__)', '@app.route', 'Flask('
            ],
            'django': [
                'from django', 'import django',
                'INSTALLED_APPS', 'django.conf.settings', 'urlpatterns',
                'from django.db import models', 'django.urls'
            ],
            'fastapi': [
                'from fastapi import', 'import fastapi',
                'FastAPI()', '@app.get', '@app.post'
            ],
            'tornado': [
                'from tornado', 'import tornado',
                'tornado.web', 'tornado.ioloop'
            ],
            'bottle': [
                'from bottle import', 'import bottle',
                'Bottle()', '@route'
            ],
            'pyramid': [
                'from pyramid', 'import pyramid',
                'Configurator()', 'pyramid.config'
            ],
        }
        
        # Check requirements.txt/requirements-*.txt for dependencies
        for req_file in source_path.glob('**/requirements*.txt'):
            try:
                content = req_file.read_text(encoding='utf-8', errors='ignore').lower()
                for framework in frameworks:
                    if framework in content:
                        frameworks[framework] = True
                        self.log.info(f"Detected {framework} in {req_file.name}")
            except Exception as e:
                self.log.debug(f"Could not read {req_file}: {e}")
        
        # Check setup.py/pyproject.toml for dependencies
        for setup_file in ['setup.py', 'pyproject.toml']:
            setup_path = source_path / setup_file
            if setup_path.exists():
                try:
                    content = setup_path.read_text(encoding='utf-8', errors='ignore').lower()
                    for framework in frameworks:
                        if framework in content:
                            frameworks[framework] = True
                            self.log.info(f"Detected {framework} in {setup_file}")
                except Exception as e:
                    self.log.debug(f"Could not read {setup_file}: {e}")
        
        # Scan Python files for imports and usage patterns
        python_files_checked = 0
        max_files_to_check = 20  # Limit for performance
        
        for py_file in source_path.rglob('*.py'):
            if python_files_checked >= max_files_to_check:
                break
            # Skip ignored directories
            if any(part in self.default_ignores for part in py_file.parts):
                continue
            
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                for framework, pattern_list in patterns.items():
                    if not frameworks[framework]:  # Only check if not already detected
                        for pattern in pattern_list:
                            if pattern in content:
                                frameworks[framework] = True
                                self.log.info(f"Detected {framework} in {py_file.name} (pattern: {pattern})")
                                break
                python_files_checked += 1
            except Exception as e:
                self.log.debug(f"Could not read {py_file}: {e}")
        
        detected = [f for f, v in frameworks.items() if v]
        if detected:
            self.log.info(f"Framework detection complete: {', '.join(detected)}")
        else:
            self.log.info("No specific Python web framework detected")
        
        return frameworks
    
    def _filter_semgrep_rulesets(self, rulesets: List[str], frameworks: Dict[str, bool]) -> List[str]:
        """Filter Semgrep rulesets based on detected frameworks.
        
        Removes framework-specific rulesets that don't apply to the project.
        For example, removes p/django rules if only Flask is detected.
        
        Args:
            rulesets: Original list of Semgrep rulesets
            frameworks: Dict of detected frameworks from _detect_python_framework
            
        Returns:
            Filtered list of rulesets appropriate for the project
        """
        # Framework-specific rulesets that should only apply when framework is detected
        framework_rulesets = {
            'p/flask': 'flask',
            'p/django': 'django',
            'p/fastapi': 'fastapi',
        }
        
        # If no frameworks detected, keep all rulesets (conservative)
        any_framework_detected = any(frameworks.values())
        if not any_framework_detected:
            self.log.info("No frameworks detected, keeping all Semgrep rulesets")
            return rulesets
        
        filtered = []
        removed = []
        
        for ruleset in rulesets:
            # Check if this is a framework-specific ruleset
            if ruleset in framework_rulesets:
                required_framework = framework_rulesets[ruleset]
                if frameworks.get(required_framework, False):
                    filtered.append(ruleset)
                else:
                    removed.append(ruleset)
            else:
                # Not framework-specific, keep it
                filtered.append(ruleset)
        
        if removed:
            self.log.info(f"Filtered out Semgrep rulesets (framework not detected): {', '.join(removed)}")
        
        return filtered
    
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
            # Load enhanced configuration from configs/static/bandit.yaml
            if CONFIG_LOADER_AVAILABLE:
                loader = get_config_loader()
                bandit_full_config = loader.load_config('bandit', 'static', bandit_config)
                exclude_dirs = bandit_full_config.get('exclude_dirs', self.default_ignores)
                skips = bandit_full_config.get('skips', ['B101'])
                severity = bandit_full_config.get('severity', 'low')
                confidence = bandit_full_config.get('confidence', 'medium')
            else:
                # Fallback to runtime config or defaults
                exclude_dirs = bandit_config.get('exclude_dirs') or self.default_ignores
                skips = bandit_config.get('skips', ['B101'])
                severity = bandit_config.get('severity', 'low')
                confidence = bandit_config.get('confidence', 'medium')
            
            exclude_arg = ','.join(str(source_path / d) for d in exclude_dirs)
            import uuid
            unique_id = str(uuid.uuid4())
            bandit_output_file = f'/tmp/bandit_output_{unique_id}.sarif'
            
            # Use native SARIF format output
            cmd = ['bandit', '-r', str(source_path), '-x', exclude_arg, '-f', 'sarif', '-o', bandit_output_file]
            
            # Add severity and confidence filters
            if severity and severity != 'all':
                cmd.extend(['--severity-level', severity])
            if confidence and confidence != 'all':
                cmd.extend(['--confidence-level', confidence])
            
            # Add skips
            if skips:
                cmd.extend(['--skip', ','.join(skips)])

            # Run and read SARIF output
            # Run and read SARIF output
            result = await self._run_tool(cmd, 'bandit', config=bandit_config, success_exit_codes=[0, 1], skip_parser=True, timeout=60)
            if result.get('status') != 'error':
                try:
                    if os.path.exists(bandit_output_file):
                        with open(bandit_output_file, 'r') as f:
                            sarif_data = json.load(f)
                            result['sarif'] = sarif_data
                            result['format'] = 'sarif'
                            # Extract issue count from SARIF
                            total_issues = 0
                            if 'runs' in sarif_data:
                                for run in sarif_data['runs']:
                                    total_issues += len(run.get('results', []))
                            result['total_issues'] = total_issues
                            result['issue_count'] = total_issues
                            result['issues'] = []
                            result['severity_breakdown'] = _extract_sarif_severity(sarif_data)
                        
                        # Clean up temp file
                        try:
                            os.unlink(bandit_output_file)
                        except Exception:
                            pass
                    else:
                        self.log.warning(f"Bandit output file not found: {bandit_output_file}")
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
                result = await self._run_tool(cmd, 'pylint', config=pylint_config, timeout=60, 
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
                        result['severity_breakdown'] = _extract_sarif_severity(sarif_data)
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
            # Load enhanced configuration from configs/static/semgrep.yaml
            if CONFIG_LOADER_AVAILABLE:
                loader = get_config_loader()
                semgrep_full_config = loader.load_config('semgrep', 'static', semgrep_config)
                rulesets = semgrep_full_config.get('rulesets', ['p/security-audit', 'p/python', 'p/javascript'])
            else:
                # Fallback: Enhanced default rulesets for comprehensive security scanning
                rulesets = semgrep_config.get('rulesets', [
                    'p/security-audit',    # Comprehensive security audit
                    'p/secrets',           # Secret/credential detection  
                    'p/owasp-top-ten',     # OWASP Top 10 vulnerabilities
                    'p/python',            # Python best practices + security
                    'p/javascript',        # JavaScript security
                    'p/flask',             # Flask-specific security rules
                    'p/react',             # React security patterns
                ])
            
            # Detect Python frameworks and filter rulesets to avoid false positives
            # E.g., don't apply p/django rules to Flask apps
            detected_frameworks = self._detect_python_framework(source_path)
            rulesets = self._filter_semgrep_rulesets(rulesets, detected_frameworks)
            
            # Build command with filtered rulesets
            cmd = ['semgrep', 'scan', '--sarif']
            for ruleset in rulesets:
                cmd.extend(['--config', ruleset])
            cmd.append(str(source_path))
            cmd.append(str(source_path))
            # Semgrep can be slow; use 180s timeout with 1 retry (2 total attempts = 360s max)
            result = await self._run_tool(cmd, 'semgrep', config=semgrep_config, skip_parser=True, retries=1, timeout=90)
            if result.get('status') != 'error' and 'output' in result:
                try:
                    sarif_data = json.loads(result['output'])
                    # CRITICAL: Strip bulky rule definitions to reduce file size by ~60%
                    # Semgrep includes the entire rule catalog (thousands of rules) in tool.driver.rules
                    # We only need the results - rule IDs are sufficient for lookups
                    sarif_data = self._strip_sarif_rules(sarif_data)
                    result['sarif'] = sarif_data
                    result['format'] = 'sarif'
                    # Extract issue count
                    total_issues = 0
                    if 'runs' in sarif_data:
                        for run in sarif_data['runs']:
                            total_issues += len(run.get('results', []))
                    result['total_issues'] = total_issues
                    result['issue_count'] = total_issues  # Match total_issues for consistent display
                    # NOTE: issues[] array intentionally empty - data is in SARIF file
                    result['issues'] = []  # Explicit - full details in SARIF
                    result['severity_breakdown'] = _extract_sarif_severity(sarif_data)
                    # Semgrep: if no severity extracted (levels stripped), treat all as medium (security findings)
                    if not result['severity_breakdown'] and total_issues > 0:
                        result['severity_breakdown'] = {'medium': total_issues}
                except Exception as e:
                    self.log.warning(f"Could not parse semgrep SARIF output: {e}")
            results['semgrep'] = result

        # Mypy type checking with enhanced strict mode
        if (
            'mypy' in self.available_tools
            and (selected_tools is None or 'mypy' in selected_tools)
            and mypy_config.get('enabled', True)
            and python_files
        ):
            # Load enhanced configuration from configs/static/mypy.ini
            if CONFIG_LOADER_AVAILABLE:
                loader = get_config_loader()
                mypy_full_config = loader.load_config('mypy', 'static', mypy_config)
                use_strict = mypy_full_config.get('strict', True)
                warn_unused = mypy_full_config.get('warn_unused_ignores', True)
                warn_redundant = mypy_full_config.get('warn_redundant_casts', True)
                max_files = mypy_full_config.get('max_files', 20)
            else:
                use_strict = mypy_config.get('strict', False)
                warn_unused = mypy_config.get('warn_unused_ignores', True)
                warn_redundant = mypy_config.get('warn_redundant_casts', True)
                max_files = mypy_config.get('max_files', 10)
            
            # Build command with enhanced type checking options
            import uuid
            unique_id_mypy = str(uuid.uuid4())
            mypy_cache_dir = f'/tmp/mypy_cache_{unique_id_mypy}'
            
            cmd = ['mypy', '--output', 'json', '--show-error-codes', '--no-error-summary',
                   '--no-incremental', '--cache-dir', mypy_cache_dir]
            
            # Add strict mode flags
            if use_strict:
                cmd.append('--strict')
            
            # Add warning flags
            if warn_unused:
                cmd.append('--warn-unused-ignores')
            if warn_redundant:
                cmd.append('--warn-redundant-casts')
            
            # Keep ignore-missing-imports for generated code compatibility
            cmd.append('--ignore-missing-imports')
            
            files_to_check = python_files[:max_files]
            cmd.extend([str(f) for f in files_to_check])

            # MyPy with JSON format (exit codes: 0=no issues, 1=issues found, 2=fatal error)
            # Parser now handles newline-delimited JSON natively
            # MyPy with JSON format (exit codes: 0=no issues, 1=issues found, 2=fatal error)
            # Parser now handles newline-delimited JSON natively
            mypy_result = await self._run_tool(cmd, 'mypy', config=mypy_config, success_exit_codes=[0, 1], timeout=60)
            results['mypy'] = mypy_result
            
            # Clean up cache dir
            try:
                import shutil
                if os.path.exists(mypy_cache_dir):
                    shutil.rmtree(mypy_cache_dir, ignore_errors=True)
            except Exception as e:
                self.log.debug(f"Failed to clean up mypy cache: {e}")

        # Find requirements file (used by both safety and pip-audit)
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

        # Safety dependency vulnerability scanning
        # NOTE: Using deprecated 'check' command as 'scan' requires interactive input
        # The check command with -r and --output json works in non-interactive mode
        if (
            'safety' in self.available_tools
            and (selected_tools is None or 'safety' in selected_tools)
            and safety_config.get('enabled', True)
        ):
            
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
                    # Use deprecated check command which works in non-interactive mode
                    # Pipe empty input to avoid EOF errors
                    cmd = ['safety', 'check', '-r', str(requirements_file), '--output', 'json']
                    safety_result = await self._run_tool(cmd, 'safety', config=safety_config, success_exit_codes=[0, 1, 64], skip_parser=True, timeout=60)
                    
                    if safety_result.get('status') != 'error' and 'output' in safety_result:
                        try:
                            # Extract JSON from output (safety adds deprecation warnings before/after)
                            output = safety_result.get('output', '')
                            # Find the JSON block - it starts with '{' and ends with '}'
                            json_start = output.find('{')
                            json_end = output.rfind('}') + 1
                            if json_start >= 0 and json_end > json_start:
                                json_str = output[json_start:json_end]
                                safety_data = json.loads(json_str)
                                
                                vulnerabilities = safety_data.get('vulnerabilities', [])
                                affected_packages = safety_data.get('affected_packages', {})
                                
                                results['safety'] = {
                                    'tool': 'safety',
                                    'executed': True,
                                    'status': 'success',
                                    'vulnerabilities': vulnerabilities,
                                    'affected_packages': affected_packages,
                                    'scanned_packages': safety_data.get('scanned_packages', {}),
                                    'total_issues': len(vulnerabilities),
                                    'issue_count': len(vulnerabilities),
                                    'format': 'json'
                                }
                                # Safety: security vulns, map analyzed_version severity or default to high
                                if vulnerabilities:
                                    safety_sev = {'high': 0, 'medium': 0, 'low': 0}
                                    for v in vulnerabilities:
                                        sev = v.get('severity', {})
                                        if isinstance(sev, dict):
                                            cvss_score = sev.get('cvssv3', {}).get('base_score', 0) if isinstance(sev.get('cvssv3'), dict) else 0
                                            if cvss_score >= 7.0:
                                                safety_sev['high'] += 1
                                            elif cvss_score >= 4.0:
                                                safety_sev['medium'] += 1
                                            else:
                                                safety_sev['low'] += 1
                                        else:
                                            safety_sev['high'] += 1  # default for security vulns
                                    results['safety']['severity_breakdown'] = {k: v for k, v in safety_sev.items() if v > 0}
                                self.log.info(f"Safety found {len(vulnerabilities)} vulnerabilities in {len(affected_packages)} packages")
                            else:
                                self.log.warning("Could not find JSON in Safety output")
                                results['safety'] = safety_result
                        except json.JSONDecodeError as e:
                            self.log.warning(f"Could not parse Safety JSON output: {e}")
                            results['safety'] = safety_result
                    else:
                        results['safety'] = safety_result
                        
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
                    
                    pip_audit_result = await self._run_tool(cmd, 'pip-audit', config=pip_audit_config, success_exit_codes=[0, 1], skip_parser=True, timeout=60)
                    
                    if pip_audit_result.get('status') != 'error' and 'output' in pip_audit_result:
                        try:
                            audit_data = json.loads(pip_audit_result['output'])
                            # pip-audit returns 'dependencies' array with each package having 'vulns' array
                            dependencies = audit_data.get('dependencies', [])
                            
                            # Extract all vulnerabilities from all packages
                            all_vulnerabilities = []
                            for dep in dependencies:
                                pkg_name = dep.get('name', 'unknown')
                                pkg_version = dep.get('version', 'unknown')
                                for vuln in dep.get('vulns', []):
                                    all_vulnerabilities.append({
                                        'package': pkg_name,
                                        'version': pkg_version,
                                        'id': vuln.get('id', 'unknown'),
                                        'description': vuln.get('description', ''),
                                        'fix_versions': vuln.get('fix_versions', []),
                                        'aliases': vuln.get('aliases', [])
                                    })
                            
                            results['pip-audit'] = {
                                'tool': 'pip-audit',
                                'executed': True,
                                'status': 'success',
                                'dependencies': dependencies,
                                'vulnerabilities': all_vulnerabilities,
                                'total_issues': len(all_vulnerabilities),
                                'issue_count': len(all_vulnerabilities),
                                'format': 'json'
                            }
                            # pip-audit: all are security vulns, default to high
                            if all_vulnerabilities:
                                results['pip-audit']['severity_breakdown'] = {'high': len(all_vulnerabilities)}
                            self.log.info(f"pip-audit found {len(all_vulnerabilities)} CVEs")
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
            # Load enhanced configuration from configs/static/vulture.toml
            if CONFIG_LOADER_AVAILABLE:
                loader = get_config_loader()
                vulture_full_config = loader.load_config('vulture', 'static', vulture_config)
                min_confidence = vulture_full_config.get('min_confidence', 80)
                sort_by_size = vulture_full_config.get('sort_by_size', True)
            else:
                min_confidence = vulture_config.get('min_confidence', 80)
                sort_by_size = vulture_config.get('sort_by_size', True)
            
            cmd = ['vulture', str(source_path)]
            cmd.extend(['--min-confidence', str(min_confidence)])
            if sort_by_size:
                cmd.append('--sort-by-size')

            # Vulture returns: 0=no issues, 1=dead code found, 3=syntax errors in checked files
            # All are valid outcomes for analysis purposes
            # Note: Vulture outputs text, not JSON, so we parse it manually with skip_parser=True
            vulture_result = await self._run_tool(cmd, 'vulture', success_exit_codes=[0, 1, 3], skip_parser=True, timeout=60)

            if vulture_result.get('status') == 'error':
                results['vulture'] = vulture_result
            elif vulture_result.get('status') in ('success', 'completed', 'no_issues'):
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
                    'issues': dead_code_findings,
                    'total_issues': len(dead_code_findings),
                    'issue_count': len(dead_code_findings),
                    'config_used': vulture_config
                }
                # Map confidence to severity: 90%+ → medium, else → low
                if dead_code_findings:
                    import re
                    vulture_sev = {'medium': 0, 'low': 0}
                    for f in dead_code_findings:
                        conf_match = re.search(r'(\d+)%\s*confidence', f.get('message', ''))
                        conf = int(conf_match.group(1)) if conf_match else 60
                        if conf >= 90:
                            vulture_sev['medium'] += 1
                        else:
                            vulture_sev['low'] += 1
                    results['vulture']['severity_breakdown'] = {k: v for k, v in vulture_sev.items() if v > 0}
            else:
                # No output case
                results['vulture'] = {
                    'tool': 'vulture',
                    'executed': True,
                    'status': 'success',
                    'issues': [],
                    'total_issues': 0,
                    'issue_count': 0,
                    'config_used': vulture_config
                }
        
        # Ruff - Fast Python linter with SARIF support
        ruff_config = config.get('ruff', {}) if config else {}
        if (
            'ruff' in self.available_tools
            and (selected_tools is None or 'ruff' in selected_tools)
            and ruff_config.get('enabled', True)
            and python_files
        ):
            # Load enhanced configuration from configs/static/ruff.toml
            if CONFIG_LOADER_AVAILABLE:
                loader = get_config_loader()
                ruff_full_config = loader.load_config('ruff', 'static', ruff_config)
                select_rules = ruff_full_config.get('select', ['E', 'F', 'W', 'I', 'S', 'B', 'A', 'C90', 'UP', 'PT', 'RUF'])
                line_length = ruff_full_config.get('line_length', 100)
                target_version = ruff_full_config.get('target-version', 'py310')
            else:
                # Fallback defaults with security rules enabled
                select_rules = ruff_config.get('select', ['E', 'F', 'W', 'I', 'S', 'B', 'A', 'C90', 'UP'])
                line_length = ruff_config.get('line_length', 100)
                target_version = ruff_config.get('target-version', 'py310')
            
            # Build command with enhanced rule selection
            cmd = ['ruff', 'check', '--output-format=sarif', '--cache-dir', '/tmp/ruff_cache']
            
            # Add rule selection
            if select_rules:
                cmd.extend(['--select', ','.join(select_rules)])
            
            # Add line length and target version
            cmd.extend(['--line-length', str(line_length)])
            cmd.extend(['--target-version', target_version])
            
            cmd.append(str(source_path))
            
            result = await self._run_tool(cmd, 'ruff', config=ruff_config, success_exit_codes=[0, 1], skip_parser=True, timeout=60)
            if result.get('status') != 'error' and 'output' in result:
                try:
                    sarif_data = json.loads(result['output'])
                    
                    # Remap severity levels (Ruff marks everything as "error", but whitespace should be low)
                    sarif_data = remap_ruff_sarif_severity(sarif_data)
                    self.log.info("Applied Ruff severity remapping for whitespace and formatting rules")
                    
                    result['sarif'] = sarif_data
                    result['format'] = 'sarif'
                    # Extract issue count
                    total_issues = 0
                    if 'runs' in sarif_data:
                        for run in sarif_data['runs']:
                            total_issues += len(run.get('results', []))
                    result['total_issues'] = total_issues
                    result['issue_count'] = total_issues  # Match total_issues for consistent display
                    # NOTE: issues[] array intentionally empty - data is in SARIF file
                    result['issues'] = []  # Explicit - full details in SARIF
                    result['severity_breakdown'] = _extract_sarif_severity(sarif_data)
                except Exception as e:
                    self.log.warning(f"Could not parse ruff SARIF output: {e}")
            results['ruff'] = result
        
        # Radon complexity analysis - cyclomatic complexity and maintainability index
        radon_config = config.get('radon', {}) if config else {}
        if (
            'radon' in self.available_tools
            and (selected_tools is None or 'radon' in selected_tools)
            and radon_config.get('enabled', True)
            and python_files
        ):
            # Run Cyclomatic Complexity (cc) analysis with average and show all functions
            # -s = show complexity, -a = show average
            min_complexity = radon_config.get('min_complexity', 'B')  # B = medium complexity threshold
            cmd = ['radon', 'cc', str(source_path), '--json', '--average', '--show-complexity', '-nc']
            
            # Exclude test directories
            for ignore_dir in ['node_modules', 'venv', '.venv', '__pycache__', '.git']:
                cmd.extend(['-e', f'*/{ignore_dir}/*'])
            
            result = await self._run_tool(cmd, 'radon', config=radon_config, success_exit_codes=[0], timeout=60)
            
            # Calculate total complexity issues (functions with complexity > C grade)
            if result.get('status') in ('success', 'no_issues') and result.get('issues'):
                complexity_issues = [i for i in result.get('issues', []) if i.get('rank', 'A') in ['D', 'E', 'F']]
                result['total_issues'] = len(complexity_issues)
                result['issue_count'] = len(complexity_issues)
            
            results['radon'] = result

        # Detect-Secrets scan
        secrets_config = config.get('detect-secrets', {}) if config else {}
        if (
            'detect-secrets' in self.available_tools
            and (selected_tools is None or 'detect-secrets' in selected_tools)
            and secrets_config.get('enabled', True)
        ):
            # Scan recursively
            cmd = ['detect-secrets', 'scan', str(source_path)]
            # detect-secrets outputs JSON to stdout
            results['detect-secrets'] = await self._run_tool(cmd, 'detect-secrets', config=secrets_config, success_exit_codes=[0], timeout=60)

        
        # Summarize per-tool status for Python analyzers (always generate)
        # Use underscore prefix to signal this is internal metadata, not a tool result
        try:
            summary = {}
            for name in ['bandit', 'pylint', 'semgrep', 'mypy', 'safety', 'pip-audit', 'vulture', 'ruff', 'radon', 'detect-secrets']:
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

                # Check if target has config, otherwise use default
                has_config = False
                for cfg in ['.eslintrc.js', '.eslintrc.json', '.eslintrc.yaml', '.eslintrc.yml', 'eslint.config.js']:
                     if (source_path / cfg).exists():
                         has_config = True
                         break
                
                if not has_config:
                     # Default config is in the service root (/app/.eslintrc.json in Docker)
                     # Use absolute path to be safe, falling back to CWD if /app doesn't exist (local dev)
                     default_config = Path('/app/.eslintrc.json')
                     if not default_config.exists():
                         default_config = Path.cwd() / '.eslintrc.json'
                     
                     if default_config.exists():
                         cmd.extend(['--config', str(default_config)])
                         self.log.info(f"Using default ESLint config: {default_config}")
                     else:
                         self.log.warning(f"Default ESLint config not found at {default_config}")
                
                if len(js_files) <= 20:
                    cmd.extend([str(f) for f in js_files])
                else:
                    cmd.append(str(source_path))

                result = await self._run_tool(cmd, 'eslint', config=eslint_config, success_exit_codes=[0, 1, 2], skip_parser=True, timeout=60)
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
                        result['issue_count'] = total_issues  # Match total_issues for consistent display
                        # NOTE: issues[] array intentionally left empty - data is in SARIF file
                        result['issues'] = []  # Explicit - full details in SARIF
                        result['severity_breakdown'] = _extract_sarif_severity(sarif_data)
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
                    
                    original_cwd = Path.cwd()
                    temp_dir = None
                    try:
                        import os
                        import shutil
                        import tempfile
                        
                        # Check if package-lock.json exists in source
                        lockfile_path = package_json.parent / 'package-lock.json'
                        
                        if lockfile_path.exists():
                            # Lockfile exists, run audit directly
                            os.chdir(package_json.parent)
                            audit_dir = package_json.parent
                        else:
                            # No lockfile - copy package.json to temp dir and generate lockfile there
                            # (source may be read-only mounted volume)
                            self.log.info(f"No package-lock.json found, generating in temp directory...")
                            temp_dir = tempfile.mkdtemp(prefix='npm_audit_')
                            shutil.copy(package_json, Path(temp_dir) / 'package.json')
                            os.chdir(temp_dir)
                            
                            try:
                                gen_result = subprocess.run(
                                    ['npm', 'i', '--package-lock-only'],
                                    capture_output=True, text=True, timeout=120
                                )
                                if gen_result.returncode != 0:
                                    self.log.warning(f"Failed to generate lockfile: {gen_result.stderr[:200]}")
                                    results['npm-audit'] = {
                                        'tool': 'npm-audit',
                                        'executed': False,
                                        'status': 'skipped',
                                        'message': 'No package-lock.json and failed to generate one',
                                        'error': gen_result.stderr[:500],
                                        'total_issues': 0
                                    }
                                    continue
                                self.log.info("Generated package-lock.json successfully")
                            except Exception as e:
                                self.log.warning(f"Failed to generate lockfile: {e}")
                                results['npm-audit'] = {
                                    'tool': 'npm-audit',
                                    'executed': False,
                                    'status': 'skipped',
                                    'message': f'No package-lock.json and failed to generate: {str(e)}',
                                    'total_issues': 0
                                }
                                continue
                            audit_dir = Path(temp_dir)
                        
                        cmd = ['npm', 'audit', '--json']
                        npm_audit_result = await self._run_tool(cmd, 'npm-audit', config=npm_audit_config, success_exit_codes=[0, 1], skip_parser=True, timeout=60)
                        
                        if npm_audit_result.get('status') != 'error' and 'output' in npm_audit_result:
                            try:
                                audit_data = json.loads(npm_audit_result['output'])
                                
                                # Check for error response (e.g., ENOLOCK)
                                if 'error' in audit_data:
                                    error_info = audit_data['error']
                                    error_code = error_info.get('code', 'UNKNOWN')
                                    error_summary = error_info.get('summary', str(error_info))
                                    self.log.warning(f"npm audit error: {error_code} - {error_summary}")
                                    results['npm-audit'] = {
                                        'tool': 'npm-audit',
                                        'executed': True,
                                        'status': 'error',
                                        'error': f'{error_code}: {error_summary}',
                                        'total_issues': 0
                                    }
                                else:
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
                                        'format': 'json',
                                        'source_dir': str(package_json.parent)
                                    }
                                    # Extract severity from vulnerability objects
                                    npm_severity = {'high': 0, 'medium': 0, 'low': 0, 'info': 0}
                                    for v in vulnerabilities.values():
                                        if isinstance(v, dict):
                                            sev = v.get('severity', 'info').lower()
                                            if sev in ('critical', 'high'):
                                                npm_severity['high'] += 1
                                            elif sev in ('moderate', 'medium'):
                                                npm_severity['medium'] += 1
                                            elif sev == 'low':
                                                npm_severity['low'] += 1
                                            else:
                                                npm_severity['info'] += 1
                                    results['npm-audit']['severity_breakdown'] = {k: v for k, v in npm_severity.items() if v > 0}
                                    self.log.info(f"npm audit found {total_cves} CVEs")
                            except Exception as e:
                                self.log.warning(f"Could not parse npm audit output: {e}")
                                results['npm-audit'] = npm_audit_result
                        else:
                            results['npm-audit'] = npm_audit_result
                    finally:
                        os.chdir(original_cwd)
                        # Clean up temp directory
                        if temp_dir and Path(temp_dir).exists():
                            try:
                                shutil.rmtree(temp_dir)
                            except Exception:
                                pass
                        
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
            
            snyk_result = await self._run_tool(cmd, 'snyk', success_exit_codes=[0, 1], timeout=60)

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
            # Add Tailwind CSS compatible rules to avoid false positives for @tailwind directives
            import tempfile
            stylelint_config = {
                "extends": "stylelint-config-standard",
                "rules": {
                    "at-rule-no-unknown": [True, {
                        "ignoreAtRules": ["tailwind", "apply", "layer", "config", "screen", "responsive", "variants"]
                    }],
                    "function-no-unknown": [True, {
                        "ignoreFunctions": ["theme", "screen"]
                    }]
                }
            }
            
            config_file = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.stylelintrc.json', delete=False) as f:
                    json.dump(stylelint_config, f, indent=2)
                    config_file = f.name
                
                cmd = ['stylelint', '--config', config_file, '--formatter', 'json']
                if css_files:
                    cmd.extend([str(p) for p in css_files])
                else:
                    cmd.append(str(source_path / '**/*.css'))

                # Use _run_tool which now has StylelintParser registered
                # Stylelint exit code 2 means issues found, which is a "success" for the tool
                result = await self._run_tool(cmd, 'stylelint', config=stylelint_cfg, success_exit_codes=[0, 1, 2], timeout=60)
                results['stylelint'] = result
                
            except Exception as e:
                self.log.error(f"Stylelint analysis failed: {e}")
                results['stylelint'] = {'tool': 'stylelint', 'executed': True, 'status': 'error', 'error': str(e)}
            finally:
                if config_file:
                    try:
                        os.unlink(config_file)
                    except Exception:
                        pass
        
        return results
    
    async def analyze_html_files(self, source_path: Path, config: Optional[Dict[str, Any]] = None, selected_tools: Optional[Set[str]] = None) -> Dict[str, Any]:
        """Run HTML static analysis."""
        html_files = []
        for p in source_path.rglob('*.html'):
            if any(part in self.default_ignores for part in p.parts):
                continue
            html_files.append(p)
        
        if not html_files:
            return {'status': 'no_files', 'message': 'No HTML files found'}
        
        results: Dict[str, Any] = {}
        
        # html-validator analysis
        html_config = (config or {}).get('html-validator', {})
        if (
            'html-validator' in self.available_tools
            and (selected_tools is None or 'html-validator' in selected_tools)
            and html_config.get('enabled', True)
        ):
            # html-validator-cli --format=json --verbose file1 file2 ...
            cmd = ['html-validator', '--format=json', '--verbose']
            cmd.extend([str(p) for p in html_files])

            # Use _run_tool with registered HTMLValidatorParser
            # html-validator-cli exit code 1 means issues found
            result = await self._run_tool(cmd, 'html-validator', config=html_config, success_exit_codes=[0, 1], timeout=60)
            results['html-validator'] = result
        
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
            self.log.info("═" * 80)
            self.log.info("🐍 PYTHON ANALYSIS PHASE")
            self.log.info("═" * 80)
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
            
            self.log.info("═" * 80)
            self.log.info("📜 JAVASCRIPT/TYPESCRIPT ANALYSIS PHASE")
            self.log.info("═" * 80)
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
            
            self.log.info("═" * 80)
            self.log.info("🎨 CSS ANALYSIS PHASE")
            self.log.info("═" * 80)
            await self.send_progress('scanning_css', 'Scanning CSS files', analysis_id=analysis_id)
            css_res = await self.analyze_css_files(model_path, config, selected_set)
            results['results']['css'] = css_res

            self.log.info("═" * 80)
            self.log.info("🌐 HTML ANALYSIS PHASE")
            self.log.info("═" * 80)
            await self.send_progress('scanning_html', 'Scanning HTML files', analysis_id=analysis_id)
            html_res = await self.analyze_html_files(model_path, config, selected_set)
            results['results']['html'] = html_res
            
            self.log.info("═" * 80)
            self.log.info("📁 PROJECT STRUCTURE ANALYSIS")
            self.log.info("═" * 80)
            await self.send_progress('analyzing_structure', 'Analyzing project structure', analysis_id=analysis_id)
            structure_result = await self.analyze_project_structure(model_path)
            # Extract _project_metadata to top level to avoid treating it as a tool
            if structure_result.get('_project_metadata'):
                results['_project_metadata'] = structure_result['_project_metadata']
            results['results']['structure'] = {'status': structure_result.get('status', 'unknown')}
            
            # Calculate enhanced summary and derive tools_used strictly from executed tools
            total_issues = 0
            tools_run = 0
            severity_breakdown = {'high': 0, 'medium': 0, 'low': 0, 'error': 0, 'warning': 0, 'info': 0}
            used_tools: List[str] = []
            
            for lang, lang_results in results['results'].items():
                if isinstance(lang_results, dict):
                    # Progress counting for sub-phases
                    issues_in_lang = 0
                    
                    for tool_name, tool_result in lang_results.items():
                        if not isinstance(tool_result, dict):
                            continue
                            
                        # Only count as executed if tool result explicitly marks executed True
                        if tool_result.get('executed') and tool_name not in used_tools:
                            used_tools.append(tool_name)
                            
                        if tool_result.get('status') == 'success':
                            tools_run += 1
                            findings = tool_result.get('total_issues', 0)
                            total_issues += findings
                            issues_in_lang += findings
                            
                            # Aggregate severity breakdown if available
                            if 'severity_breakdown' in tool_result:
                                for severity, count in tool_result['severity_breakdown'].items():
                                    if severity in severity_breakdown:
                                        severity_breakdown[severity] += count
                                    else:
                                        severity_breakdown[severity] = count
            
            # Map 'error' to 'high', 'warning' to 'medium', 'info' to 'low' for visual consistency
            # if tools used different naming conventions
            severity_breakdown['high'] += severity_breakdown.pop('error', 0)
            severity_breakdown['medium'] += severity_breakdown.pop('warning', 0)
            severity_breakdown['low'] += severity_breakdown.pop('info', 0)
            
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
            
            # Log completion summary
            self.log.info("═" * 80)
            self.log.info(f"✅ STATIC ANALYSIS COMPLETE")
            self.log.info(f"   📊 Total Issues: {total_issues}")
            self.log.info(f"   🔧 Tools Run: {tools_run}")
            self.log.info(f"   📝 Tools Used: {', '.join(used_tools) if used_tools else 'none'}")
            self.log.info("═" * 80)
            
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

                # Send initial status to keep connection alive
                try:
                    await websocket.send(json.dumps({
                        'type': 'status_update',
                        'stage': 'started',
                        'message': f"Starting static analysis for {model_slug} app {app_number}",
                        'analysis_id': analysis_id
                    }))
                except Exception as e:
                    self.log.warning(f"Failed to send initial status: {e}")

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
