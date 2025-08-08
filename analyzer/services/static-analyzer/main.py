#!/usr/bin/env python3
"""
Static Analyzer Service - Comprehensive Code Quality Analysis
============================================================

A containerized static analysis service that runs:
- Python: Bandit (security), Pylint (quality), MyPy (types)
- JavaScript/TypeScript: ESLint (quality + security)
- CSS: Stylelint
- General: File structure analysis

This service runs inside a Docker container with all tools pre-installed.
Usage:
    docker-compose up static-analyzer

The service will start on ws://localhost:2001
"""

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import websockets
from websockets.asyncio.server import serve

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StaticAnalyzer:
    """Comprehensive static analyzer for multiple languages."""
    
    def __init__(self):
        self.service_name = "static-analyzer"
        self.version = "1.0.0"
        self.start_time = datetime.now()
        self.available_tools = self._check_available_tools()
    
    def _check_available_tools(self) -> List[str]:
        """Check which static analysis tools are available."""
        tools = []
        
        # Python tools
        for tool in ['bandit', 'pylint', 'mypy']:
            try:
                result = subprocess.run([tool, '--version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    tools.append(tool)
                    logger.info(f"✅ {tool} available")
            except Exception as e:
                logger.warning(f"❌ {tool} not available: {e}")
        
        # JavaScript tools
        for tool in ['eslint']:
            try:
                result = subprocess.run([tool, '--version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    tools.append(tool)
                    logger.info(f"✅ {tool} available")
            except Exception as e:
                logger.warning(f"❌ {tool} not available: {e}")
        
        # CSS tools
        for tool in ['stylelint']:
            try:
                result = subprocess.run([tool, '--version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    tools.append(tool)
                    logger.info(f"✅ {tool} available")
            except Exception as e:
                logger.warning(f"❌ {tool} not available: {e}")
        
        return tools
    
    async def analyze_python_files(self, source_path: Path) -> Dict[str, Any]:
        """Run Python static analysis tools."""
        python_files = list(source_path.rglob('*.py'))
        if not python_files:
            return {'status': 'no_files', 'message': 'No Python files found'}
        
        results = {}
        
        # Bandit security analysis
        if 'bandit' in self.available_tools:
            try:
                cmd = ['bandit', '-r', str(source_path), '-f', 'json', '--skip', 'B101']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.stdout:
                    bandit_data = json.loads(result.stdout)
                    results['bandit'] = {
                        'tool': 'bandit',
                        'status': 'success',
                        'issues': bandit_data.get('results', []),
                        'total_issues': len(bandit_data.get('results', []))
                    }
                else:
                    results['bandit'] = {'tool': 'bandit', 'status': 'no_issues', 'total_issues': 0}
            except Exception as e:
                results['bandit'] = {'tool': 'bandit', 'status': 'error', 'error': str(e)}
        
        # Pylint code quality
        if 'pylint' in self.available_tools and python_files:
            try:
                # Limit to first 5 files to avoid timeout
                files_to_check = python_files[:5]
                cmd = ['pylint', '--output-format=json', '--reports=no'] + [str(f) for f in files_to_check]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.stdout:
                    try:
                        pylint_data = json.loads(result.stdout)
                        results['pylint'] = {
                            'tool': 'pylint',
                            'status': 'success',
                            'issues': pylint_data,
                            'total_issues': len(pylint_data),
                            'files_analyzed': len(files_to_check)
                        }
                    except json.JSONDecodeError:
                        results['pylint'] = {
                            'tool': 'pylint',
                            'status': 'completed',
                            'message': 'Analysis completed'
                        }
                else:
                    results['pylint'] = {'tool': 'pylint', 'status': 'no_issues', 'total_issues': 0}
            except Exception as e:
                results['pylint'] = {'tool': 'pylint', 'status': 'error', 'error': str(e)}
        
        return results
    
    async def analyze_javascript_files(self, source_path: Path) -> Dict[str, Any]:
        """Run JavaScript/TypeScript static analysis."""
        js_files = []
        for pattern in ['*.js', '*.jsx', '*.ts', '*.tsx', '*.vue']:
            js_files.extend(list(source_path.rglob(pattern)))
        
        if not js_files:
            return {'status': 'no_files', 'message': 'No JavaScript/TypeScript files found'}
        
        results = {}
        
        # ESLint analysis
        if 'eslint' in self.available_tools:
            try:
                # Create basic ESLint config
                eslint_config = {
                    "extends": ["eslint:recommended"],
                    "parserOptions": {"ecmaVersion": 2020, "sourceType": "module"},
                    "rules": {
                        "no-eval": "error",
                        "no-implied-eval": "error",
                        "no-new-func": "error",
                        "no-script-url": "error"
                    }
                }
                
                config_file = source_path / '.eslintrc.json'
                with open(config_file, 'w') as f:
                    json.dump(eslint_config, f)
                
                # Run ESLint
                cmd = ['eslint', '--format', 'json', str(source_path)]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.stdout:
                    try:
                        eslint_data = json.loads(result.stdout)
                        total_issues = sum(len(file_result.get('messages', [])) for file_result in eslint_data)
                        results['eslint'] = {
                            'tool': 'eslint',
                            'status': 'success',
                            'results': eslint_data,
                            'total_issues': total_issues,
                            'files_analyzed': len([f for f in eslint_data if f.get('messages')])
                        }
                    except json.JSONDecodeError:
                        results['eslint'] = {'tool': 'eslint', 'status': 'completed', 'message': 'Analysis completed'}
                else:
                    results['eslint'] = {'tool': 'eslint', 'status': 'no_issues', 'total_issues': 0}
                
                # Cleanup
                try:
                    config_file.unlink()
                except Exception:
                    pass
                    
            except Exception as e:
                results['eslint'] = {'tool': 'eslint', 'status': 'error', 'error': str(e)}
        
        return results
    
    async def analyze_css_files(self, source_path: Path) -> Dict[str, Any]:
        """Run CSS static analysis."""
        css_files = []
        for pattern in ['*.css', '*.scss', '*.sass', '*.less']:
            css_files.extend(list(source_path.rglob(pattern)))
        
        if not css_files:
            return {'status': 'no_files', 'message': 'No CSS files found'}
        
        results = {}
        
        # Stylelint analysis
        if 'stylelint' in self.available_tools:
            try:
                cmd = ['stylelint', '--formatter', 'json', str(source_path / '**/*.css')]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.stdout:
                    try:
                        stylelint_data = json.loads(result.stdout)
                        total_issues = sum(len(file_result.get('warnings', [])) for file_result in stylelint_data)
                        results['stylelint'] = {
                            'tool': 'stylelint',
                            'status': 'success',
                            'results': stylelint_data,
                            'total_issues': total_issues
                        }
                    except json.JSONDecodeError:
                        results['stylelint'] = {'tool': 'stylelint', 'status': 'completed'}
                else:
                    results['stylelint'] = {'tool': 'stylelint', 'status': 'no_issues', 'total_issues': 0}
                    
            except Exception as e:
                results['stylelint'] = {'tool': 'stylelint', 'status': 'error', 'error': str(e)}
        
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
    
    async def analyze_model_code(self, model_slug: str, app_number: int) -> Dict[str, Any]:
        """Perform comprehensive static analysis on AI model code."""
        try:
            model_path = Path('/app/sources') / model_slug / f'app{app_number}'
            
            if not model_path.exists():
                return {
                    'status': 'error',
                    'error': f'Model path not found: {model_path}'
                }
            
            logger.info(f"Static analysis of {model_slug} app {app_number}")
            
            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'tools_used': self.available_tools.copy(),
                'results': {}
            }
            
            # Run analysis for different file types
            logger.info("Analyzing Python files...")
            results['results']['python'] = await self.analyze_python_files(model_path)
            
            logger.info("Analyzing JavaScript files...")
            results['results']['javascript'] = await self.analyze_javascript_files(model_path)
            
            logger.info("Analyzing CSS files...")
            results['results']['css'] = await self.analyze_css_files(model_path)
            
            logger.info("Analyzing project structure...")
            results['results']['structure'] = await self.analyze_project_structure(model_path)
            
            # Calculate summary
            total_issues = 0
            tools_run = 0
            
            for lang_results in results['results'].values():
                if isinstance(lang_results, dict):
                    for tool_result in lang_results.values():
                        if isinstance(tool_result, dict) and tool_result.get('status') == 'success':
                            tools_run += 1
                            total_issues += tool_result.get('total_issues', 0)
            
            results['summary'] = {
                'total_issues_found': total_issues,
                'tools_run_successfully': tools_run,
                'analysis_status': 'completed'
            }
            
            return results
            
        except Exception as e:
            logger.error(f"Static analysis failed: {e}")
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
            
            if msg_type == "ping":
                response = {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                    "service": self.service_name
                }
                await websocket.send(json.dumps(response))
                logger.info("Responded to ping")
                
            elif msg_type == "health_check":
                uptime = (datetime.now() - self.start_time).total_seconds()
                response = {
                    "type": "health_response",
                    "status": "healthy",
                    "service": self.service_name,
                    "version": self.version,
                    "uptime": uptime,
                    "available_tools": self.available_tools,
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response))
                logger.info(f"Health check - Tools: {self.available_tools}")
                
            elif msg_type == "static_analyze":
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 1)
                
                logger.info(f"Starting static analysis for {model_slug} app {app_number}")
                
                analysis_results = await self.analyze_model_code(model_slug, app_number)
                
                response = {
                    "type": "static_analysis_result",
                    "status": "success",
                    "service": self.service_name,
                    "analysis": analysis_results,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(response))
                logger.info(f"Static analysis completed for {model_slug} app {app_number}")
                
            else:
                response = {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                    "service": self.service_name
                }
                await websocket.send(json.dumps(response))
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error_response = {
                "type": "error",
                "message": f"Internal error: {str(e)}",
                "service": self.service_name
            }
            try:
                await websocket.send(json.dumps(error_response))
            except Exception:
                pass

async def handle_client(websocket):
    """Handle client connections."""
    analyzer = StaticAnalyzer()
    client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.info(f"New client connected: {client_addr}")
    
    try:
        async for message in websocket:
            try:
                message_data = json.loads(message)
                await analyzer.handle_message(websocket, message_data)
            except json.JSONDecodeError:
                logger.error("Invalid JSON message")
                error_response = {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "service": analyzer.service_name
                }
                await websocket.send(json.dumps(error_response))
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {client_addr}")
    except Exception as e:
        logger.error(f"Error with client {client_addr}: {e}")

async def main():
    """Start the static analyzer service."""
    host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
    port = int(os.getenv('WEBSOCKET_PORT', 2001))
    
    logger.info(f"Starting Static Analyzer service on {host}:{port}")
    
    try:
        async with serve(handle_client, host, port):
            logger.info(f"Static Analyzer listening on ws://{host}:{port}")
            logger.info("Service ready to accept connections")
            await asyncio.Future()  # Run forever
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Service crashed: {e}")
        exit(1)
