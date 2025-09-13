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

from analyzer.shared.service_base import BaseWSService


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

    def _detect_available_tools(self) -> List[str]:
        tools: List[str] = []
        for tool in ['bandit', 'pylint', 'mypy', 'eslint', 'stylelint']:
            try:
                result = subprocess.run([tool, '--version'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    tools.append(tool)
                    self.log.debug(f"{tool} available")
            except Exception as e:
                self.log.debug(f"{tool} not available: {e}")
        return tools
    
    def _generate_pylintrc(self, config: Dict[str, Any]) -> str:
        """Generate .pylintrc configuration file content."""
        rcfile_content = f"""[MAIN]
jobs={config.get('jobs', 0)}
load-plugins={','.join(config.get('load_plugins', []))}

[MESSAGES CONTROL]
disable={','.join(config.get('disable', ['missing-docstring', 'too-few-public-methods']))}
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
        
        # Bandit security analysis
        if (
            'bandit' in self.available_tools
            and (selected_tools is None or 'bandit' in selected_tools)
            and bandit_config.get('enabled', True)
        ):
            try:
                # Build exclude list
                exclude_dirs = bandit_config.get('exclude_dirs') or self.default_ignores
                exclude_arg = ','.join(str(source_path / d) for d in exclude_dirs)
                cmd = ['bandit', '-r', str(source_path), '-x', exclude_arg]
                
                # Apply configuration
                if bandit_config.get('format'):
                    cmd.extend(['-f', bandit_config['format']])
                else:
                    cmd.extend(['-f', 'json'])
                
                if bandit_config.get('skips'):
                    cmd.extend(['--skip', ','.join(bandit_config['skips'])])
                else:
                    cmd.extend(['--skip', 'B101'])  # Default skip
                
                if bandit_config.get('tests'):
                    cmd.extend(['--tests', ','.join(bandit_config['tests'])])
                
                if bandit_config.get('severity_level'):
                    severity_map = {'low': 'l', 'medium': 'm', 'high': 'h'}
                    if bandit_config['severity_level'] in severity_map:
                        cmd.extend(['-l', severity_map[bandit_config['severity_level']]])
                
                if bandit_config.get('confidence_level'):
                    confidence_map = {'low': 'l', 'medium': 'm', 'high': 'h'}
                    if bandit_config['confidence_level'] in confidence_map:
                        cmd.extend(['-i', confidence_map[bandit_config['confidence_level']]])
                
                if bandit_config.get('context_lines'):
                    cmd.extend(['--msg-template', 
                              '{abspath}:{line}: {test_id}[bandit]: {severity}: {msg}'])
                
                # Create temporary config file if needed
                config_file = None
                if bandit_config.get('exclude_dirs') or bandit_config.get('baseline_file'):
                    import tempfile
                    import yaml
                    
                    config_data = {}
                    if bandit_config.get('exclude_dirs'):
                        config_data['exclude_dirs'] = bandit_config['exclude_dirs']
                    if bandit_config.get('tests'):
                        config_data['tests'] = bandit_config['tests']
                    if bandit_config.get('skips'):
                        config_data['skips'] = bandit_config['skips']
                    
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                        yaml.dump(config_data, f)
                        config_file = f.name
                        cmd.extend(['-c', config_file])
                
                self.log.info(f"Running Bandit: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                # Cleanup temporary config file
                if config_file:
                    try:
                        os.unlink(config_file)
                    except Exception:
                        pass
                
                if result.stdout:
                    bandit_data = json.loads(result.stdout)
                    results['bandit'] = {
                        'tool': 'bandit',
                        'executed': True,
                        'status': 'success',
                        'issues': bandit_data.get('results', []),
                        'total_issues': len(bandit_data.get('results', [])),
                        'metrics': bandit_data.get('metrics', {}),
                        'config_used': bandit_config
                    }
                else:
                    results['bandit'] = {
                        'tool': 'bandit', 
                        'executed': True,
                        'status': 'no_issues', 
                        'total_issues': 0,
                        'config_used': bandit_config
                    }
            except Exception as e:
                self.log.error(f"Bandit analysis failed: {e}")
                results['bandit'] = {'tool': 'bandit', 'executed': True, 'status': 'error', 'error': str(e)}
        
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
                
                # Select files to analyze (limit to prevent timeout)
                max_files = pylint_config.get('max_files', 10)
                files_to_check = python_files[:max_files]
                
                cmd = ['pylint', '--rcfile', pylintrc_file] + [str(f) for f in files_to_check]
                
                if pylint_config.get('errors_only'):
                    cmd.append('--errors-only')
                
                if pylint_config.get('jobs'):
                    cmd.extend(['-j', str(pylint_config['jobs'])])
                
                self.log.info(f"Running Pylint: {' '.join(cmd[:5])}... ({len(files_to_check)} files)")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                # Cleanup temporary rcfile
                try:
                    os.unlink(pylintrc_file)
                except Exception:
                    pass
                
                if result.stdout:
                    try:
                        pylint_data = json.loads(result.stdout)
                        results['pylint'] = {
                            'tool': 'pylint',
                            'executed': True,
                            'status': 'success',
                            'issues': pylint_data,
                            'total_issues': len(pylint_data),
                            'files_analyzed': len(files_to_check),
                            'config_used': pylint_config
                        }
                    except json.JSONDecodeError:
                        # Pylint might not output JSON, parse text output
                        results['pylint'] = {
                            'tool': 'pylint',
                            'executed': True,
                            'status': 'completed',
                            'message': 'Analysis completed',
                            'output': result.stdout[:1000],  # Truncate output
                            'files_analyzed': len(files_to_check),
                            'config_used': pylint_config
                        }
                else:
                    results['pylint'] = {
                        'tool': 'pylint', 
                        'executed': True,
                        'status': 'no_issues', 
                        'total_issues': 0,
                        'files_analyzed': len(files_to_check),
                        'config_used': pylint_config
                    }
            except Exception as e:
                self.log.error(f"Pylint analysis failed: {e}")
                results['pylint'] = {'tool': 'pylint', 'executed': True, 'status': 'error', 'error': str(e)}
        
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
        
        # ESLint analysis
        if (
            'eslint' in self.available_tools
            and (selected_tools is None or 'eslint' in selected_tools)
            and eslint_config.get('enabled', True)
        ):
            try:
                # Create custom ESLint config
                eslint_config_data = {
                    "extends": eslint_config.get('extends', ["eslint:recommended"]),
                    "env": eslint_config.get('env', {"browser": True, "es2021": True, "node": True}),
                    "parserOptions": eslint_config.get('parser_options', {
                        "ecmaVersion": 2021,
                        "sourceType": "module",
                        "ecmaFeatures": {"jsx": True}
                    }),
                    "rules": eslint_config.get('rules', {
                        "no-eval": "error",
                        "no-implied-eval": "error",
                        "no-new-func": "error",
                        "no-script-url": "error",
                        "no-alert": "warn",
                        "no-console": "warn",
                        "no-debugger": "error",
                        "no-unused-vars": "warn"
                    }),
                    "globals": eslint_config.get('globals', {}),
                    "plugins": eslint_config.get('plugins', []),
                    "settings": eslint_config.get('settings', {})
                }
                
                # Add ignore patterns (defaults + user-provided)
                ignore_patterns = set(eslint_config.get('ignore_patterns', []))
                ignore_patterns.update(self.default_ignores)
                if ignore_patterns:
                    eslint_config_data['ignorePatterns'] = sorted(ignore_patterns)
                
                # Create temporary ESLint config file to avoid writing into read-only source mounts
                import tempfile
                config_file = None
                try:
                    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.eslintrc.json', delete=False)
                    with tmp as f:
                        json.dump(eslint_config_data, f, indent=2)
                        config_file = f.name
                except Exception as e:
                    self.log.error(f"Failed to create temporary ESLint config: {e}")
                    config_file = None
                
                # Build ESLint command
                cmd = ['eslint', '--format', eslint_config.get('format', 'json')]
                if config_file:
                    cmd.extend(['--config', config_file])
                
                if eslint_config.get('fix'):
                    cmd.append('--fix')
                
                if eslint_config.get('max_warnings') is not None:
                    cmd.extend(['--max-warnings', str(eslint_config['max_warnings'])])
                
                if eslint_config.get('output_file'):
                    cmd.extend(['--output-file', eslint_config['output_file']])
                
                # Add files or directory
                if len(js_files) <= 20:  # If manageable number of files
                    cmd.extend([str(f) for f in js_files])
                else:
                    cmd.append(str(source_path))
                
                self.log.info(f"Running ESLint: {' '.join(cmd[:5])}...")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                
                if result.stdout:
                    try:
                        eslint_data = json.loads(result.stdout)
                        total_issues = sum(len(file_result.get('messages', [])) for file_result in eslint_data)
                        
                        # Calculate severity breakdown
                        severity_counts = {'error': 0, 'warning': 0}
                        for file_result in eslint_data:
                            for message in file_result.get('messages', []):
                                severity = 'error' if message.get('severity') == 2 else 'warning'
                                severity_counts[severity] += 1
                        
                        results['eslint'] = {
                            'tool': 'eslint',
                            'executed': True,
                            'status': 'success',
                            'results': eslint_data,
                            'total_issues': total_issues,
                            'severity_breakdown': severity_counts,
                            'files_analyzed': len([f for f in eslint_data if f.get('messages')]),
                            'config_used': eslint_config
                        }
                    except json.JSONDecodeError:
                        results['eslint'] = {
                            'tool': 'eslint', 
                            'executed': True,
                            'status': 'completed', 
                            'message': 'Analysis completed',
                            'output': result.stdout[:500],
                            'config_used': eslint_config
                        }
                else:
                    results['eslint'] = {
                        'tool': 'eslint', 
                        'executed': True,
                        'status': 'no_issues', 
                        'total_issues': 0,
                        'config_used': eslint_config
                    }
                
                # Cleanup temporary config
                try:
                    if config_file:
                        os.unlink(config_file)
                except Exception:
                    pass
                    
            except Exception as e:
                self.log.error(f"ESLint analysis failed: {e}")
                results['eslint'] = {'tool': 'eslint', 'executed': True, 'status': 'error', 'error': str(e)}
        
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
            try:
                # stylelint supports ignore patterns through .stylelintignore; here we pass globs limited to non-ignored dirs
                cmd = ['stylelint', '--formatter', 'json']
                if css_files:
                    cmd.extend([str(p) for p in css_files])
                else:
                    cmd.append(str(source_path / '**/*.css'))
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.stdout:
                    try:
                        stylelint_data = json.loads(result.stdout)
                        total_issues = sum(len(file_result.get('warnings', [])) for file_result in stylelint_data)
                        results['stylelint'] = {
                            'tool': 'stylelint',
                            'executed': True,
                            'status': 'success',
                            'results': stylelint_data,
                            'total_issues': total_issues
                        }
                    except json.JSONDecodeError:
                        results['stylelint'] = {'tool': 'stylelint', 'executed': True, 'status': 'completed'}
                else:
                    results['stylelint'] = {'tool': 'stylelint', 'executed': True, 'status': 'no_issues', 'total_issues': 0}
                    
            except Exception as e:
                results['stylelint'] = {'tool': 'stylelint', 'executed': True, 'status': 'error', 'error': str(e)}
        
        return results
    
    async def analyze_project_structure(self, source_path: Path) -> Dict[str, Any]:
        """Analyze overall project structure and files."""
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
            
            return {
                'status': 'success',
                'file_counts': file_counts,
                'security_files': security_files,
                'total_files': sum(file_counts.values())
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    # Use BaseWSService.send_progress instead of local progress helper

    async def analyze_model_code(self, model_slug: str, app_number: int, config: Optional[Dict[str, Any]] = None, analysis_id: Optional[str] = None, selected_tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Perform comprehensive static analysis on AI model code with custom configuration."""
        try:
            model_path = Path('/app/sources') / model_slug / f'app{app_number}'
            
            if not model_path.exists():
                return {
                    'status': 'error',
                    'error': f'Model path not found: {model_path}'
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
                if isinstance(js_res, dict) and 'eslint' in js_res and isinstance(js_res['eslint'], dict):
                    count += int(js_res['eslint'].get('total_issues', 0))
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
            results['results']['structure'] = await self.analyze_project_structure(model_path)
            
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
                
                await websocket.send(json.dumps(response))
                self.log.info(f"Static analysis completed for {model_slug} app {app_number}")
                
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
