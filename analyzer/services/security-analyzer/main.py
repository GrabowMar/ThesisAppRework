#!/usr/bin/env python3
"""
Security Analyzer Service - Containerized Security Tools
========================================================

A containerized security analysis service that runs:
- Bandit (Python security linter)
- Safety (Python dependency vulnerability checker)
- Pylint (Python code quality analyzer)

This service runs inside a Docker container with all tools pre-installed.
Usage:
    docker-compose up security-analyzer

The service will start on ws://localhost:2005
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

class SecurityAnalyzer:
    """Containerized security analyzer using real security tools."""
    
    def __init__(self):
        self.service_name = "security-analyzer"
        self.version = "1.0.0"
        self.start_time = datetime.now()
        self.available_tools = self._check_available_tools()
    
    def _check_available_tools(self) -> List[str]:
        """Check which security tools are available in the container."""
        tools = []
        
        # Check for Bandit
        try:
            result = subprocess.run(['bandit', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('bandit')
                logger.info(f"✅ Bandit available: {result.stdout.strip()}")
        except Exception as e:
            logger.warning(f"❌ Bandit not available: {e}")
        
        # Check for Safety
        try:
            result = subprocess.run(['safety', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('safety')
                logger.info(f"✅ Safety available: {result.stdout.strip()}")
        except Exception as e:
            logger.warning(f"❌ Safety not available: {e}")
        
        # Check for Pylint
        try:
            result = subprocess.run(['pylint', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('pylint')
                logger.info(f"✅ Pylint available: {result.stdout.strip()}")
        except Exception as e:
            logger.warning(f"❌ Pylint not available: {e}")
        
        return tools
    
    async def run_bandit_analysis(self, source_path: Path) -> Dict[str, Any]:
        """Run Bandit security analysis on Python code."""
        try:
            # Run Bandit with JSON output
            cmd = [
                'bandit', 
                '-r', str(source_path),
                '-f', 'json',
                '--skip', 'B101',  # Skip assert used tests
                '--severity-level', 'low'
            ]
            
            logger.info(f"Running Bandit: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.stdout:
                bandit_data = json.loads(result.stdout)
                return {
                    'tool': 'bandit',
                    'status': 'success',
                    'results': bandit_data.get('results', []),
                    'metrics': bandit_data.get('metrics', {}),
                    'total_issues': len(bandit_data.get('results', [])),
                    'severity_breakdown': self._analyze_bandit_severity(bandit_data.get('results', []))
                }
            else:
                return {
                    'tool': 'bandit',
                    'status': 'no_issues',
                    'results': [],
                    'total_issues': 0,
                    'severity_breakdown': {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Bandit JSON output: {e}")
            return {'tool': 'bandit', 'status': 'error', 'error': f'JSON parse error: {str(e)}'}
        except subprocess.TimeoutExpired:
            logger.error("Bandit analysis timed out")
            return {'tool': 'bandit', 'status': 'error', 'error': 'Analysis timed out'}
        except Exception as e:
            logger.error(f"Bandit analysis failed: {e}")
            return {'tool': 'bandit', 'status': 'error', 'error': str(e)}
    
    def _analyze_bandit_severity(self, results: List[Dict]) -> Dict[str, int]:
        """Analyze severity distribution of Bandit results."""
        severity_count = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for issue in results:
            severity = issue.get('issue_severity', 'MEDIUM').upper()
            if severity in severity_count:
                severity_count[severity] += 1
        return severity_count
    
    async def run_safety_check(self, source_path: Path) -> Dict[str, Any]:
        """Run Safety vulnerability check on requirements."""
        try:
            # Look for requirements files
            req_files = list(source_path.rglob('requirements*.txt'))
            req_files.extend(list(source_path.rglob('Pipfile')))
            req_files.extend(list(source_path.rglob('pyproject.toml')))
            
            if not req_files:
                return {
                    'tool': 'safety',
                    'status': 'no_requirements',
                    'message': 'No requirements files found',
                    'vulnerabilities': []
                }
            
            all_vulnerabilities = []
            for req_file in req_files[:3]:  # Limit to 3 files
                try:
                    cmd = ['safety', 'check', '--json', '--file', str(req_file)]
                    logger.info(f"Running Safety on {req_file.name}: {' '.join(cmd)}")
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.stdout:
                        safety_data = json.loads(result.stdout)
                        vulns = safety_data if isinstance(safety_data, list) else []
                        all_vulnerabilities.extend(vulns)
                        
                except Exception as e:
                    logger.warning(f"Safety check failed for {req_file}: {e}")
                    continue
            
            return {
                'tool': 'safety',
                'status': 'success',
                'vulnerabilities': all_vulnerabilities,
                'total_vulnerabilities': len(all_vulnerabilities),
                'files_checked': [f.name for f in req_files[:3]]
            }
            
        except Exception as e:
            logger.error(f"Safety check failed: {e}")
            return {'tool': 'safety', 'status': 'error', 'error': str(e)}
    
    async def run_pylint_analysis(self, source_path: Path) -> Dict[str, Any]:
        """Run Pylint code quality analysis on Python files."""
        try:
            # Find Python files
            python_files = list(source_path.rglob('*.py'))
            if not python_files:
                return {
                    'tool': 'pylint',
                    'status': 'no_python_files',
                    'message': 'No Python files found'
                }
            
            # Limit to first 10 files to avoid timeout
            files_to_check = python_files[:10]
            
            cmd = ['pylint', '--output-format=json', '--reports=no'] + [str(f) for f in files_to_check]
            logger.info(f"Running Pylint on {len(files_to_check)} files")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            # Pylint returns non-zero even for warnings, so check stdout
            if result.stdout:
                try:
                    pylint_data = json.loads(result.stdout)
                    return {
                        'tool': 'pylint',
                        'status': 'success',
                        'issues': pylint_data,
                        'total_issues': len(pylint_data),
                        'files_analyzed': len(files_to_check),
                        'issue_types': self._analyze_pylint_types(pylint_data)
                    }
                except json.JSONDecodeError:
                    # Sometimes pylint output isn't valid JSON
                    return {
                        'tool': 'pylint',
                        'status': 'completed',
                        'message': 'Analysis completed but output format unexpected',
                        'raw_output': result.stdout[:1000]  # First 1000 chars
                    }
            else:
                return {
                    'tool': 'pylint',
                    'status': 'no_issues',
                    'message': 'No issues found',
                    'files_analyzed': len(files_to_check)
                }
                
        except subprocess.TimeoutExpired:
            logger.error("Pylint analysis timed out")
            return {'tool': 'pylint', 'status': 'error', 'error': 'Analysis timed out'}
        except Exception as e:
            logger.error(f"Pylint analysis failed: {e}")
            return {'tool': 'pylint', 'status': 'error', 'error': str(e)}
    
    def _analyze_pylint_types(self, issues: List[Dict]) -> Dict[str, int]:
        """Analyze issue types from Pylint results."""
        type_count = {'error': 0, 'warning': 0, 'refactor': 0, 'convention': 0}
        for issue in issues:
            issue_type = issue.get('type', 'warning').lower()
            if issue_type in type_count:
                type_count[issue_type] += 1
        return type_count
    
    async def analyze_model_code(self, model_slug: str, app_number: int) -> Dict[str, Any]:
        """Analyze code from a specific AI model app."""
        try:
            # Construct path to model code
            model_path = Path('/app/sources') / model_slug / f'app{app_number}'
            
            if not model_path.exists():
                return {
                    'status': 'error',
                    'error': f'Model path not found: {model_path}',
                    'tools_attempted': []
                }
            
            logger.info(f"Analyzing {model_slug} app {app_number} at {model_path}")
            
            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'tools_used': self.available_tools.copy(),
                'results': {}
            }
            
            # Run each available tool
            if 'bandit' in self.available_tools:
                logger.info("Running Bandit analysis...")
                results['results']['bandit'] = await self.run_bandit_analysis(model_path)
            
            if 'safety' in self.available_tools:
                logger.info("Running Safety check...")
                results['results']['safety'] = await self.run_safety_check(model_path)
            
            if 'pylint' in self.available_tools:
                logger.info("Running Pylint analysis...")
                results['results']['pylint'] = await self.run_pylint_analysis(model_path)
            
            # Calculate summary
            total_issues = 0
            tools_run = 0
            for tool_result in results['results'].values():
                if tool_result.get('status') == 'success':
                    tools_run += 1
                    total_issues += tool_result.get('total_issues', 0)
                    total_issues += tool_result.get('total_vulnerabilities', 0)
            
            results['summary'] = {
                'total_issues_found': total_issues,
                'tools_run_successfully': tools_run,
                'analysis_status': 'completed'
            }
            
            return results
            
        except Exception as e:
            logger.error(f"Model analysis failed: {e}")
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
                logger.info(f"Health check - Tools available: {self.available_tools}")
                
            elif msg_type == "security_analyze":
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 1)
                
                logger.info(f"Starting security analysis for {model_slug} app {app_number}")
                
                # Run the analysis
                analysis_results = await self.analyze_model_code(model_slug, app_number)
                
                response = {
                    "type": "security_analysis_result",
                    "status": "success",
                    "service": self.service_name,
                    "analysis": analysis_results,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(response))
                logger.info(f"Security analysis completed for {model_slug} app {app_number}")
                
            else:
                response = {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                    "service": self.service_name
                }
                await websocket.send(json.dumps(response))
                logger.warning(f"Unknown message type: {msg_type}")
                
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
    analyzer = SecurityAnalyzer()
    client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.info(f"New client connected: {client_addr}")
    
    try:
        async for message in websocket:
            try:
                message_data = json.loads(message)
                logger.debug(f"Received message: {message_data}")
                await analyzer.handle_message(websocket, message_data)
                
            except json.JSONDecodeError:
                logger.error("Received invalid JSON message")
                error_response = {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "service": analyzer.service_name
                }
                await websocket.send(json.dumps(error_response))
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {client_addr}")
    except Exception as e:
        logger.error(f"Unexpected error with client {client_addr}: {e}")

async def main():
    """Start the security analyzer service."""
    host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
    port = int(os.getenv('WEBSOCKET_PORT', 2005))
    
    logger.info(f"Starting Security Analyzer service on {host}:{port}")
    
    try:
        async with serve(handle_client, host, port):
            logger.info(f"Security Analyzer listening on ws://{host}:{port}")
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
