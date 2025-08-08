#!/usr/bin/env python3
"""
Static Analyzer Service - Simple WebSocket Server
================================================

A simple static analysis service that responds to health checks and ping messages.
This service listens on port 8001 and can be extended to perform actual static analysis.

Usage:
    python main.py

The service will start on ws://localhost:8001
"""

import asyncio
import json
import logging
import os
from datetime import datetime
import websockets
from websockets.asyncio.server import serve

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StaticAnalyzer:
    """Simple static analyzer service."""
    
    def __init__(self):
        self.service_name = "static-analyzer"
        self.version = "1.0.0"
        self.start_time = datetime.now()
    
    async def handle_message(self, websocket, message_data):
        """Handle incoming messages."""
        try:
            msg_type = message_data.get("type", "unknown")
            
            if msg_type == "ping":
                # Respond to ping with pong
                response = {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                    "service": self.service_name
                }
                await websocket.send(json.dumps(response))
                logger.info("Responded to ping")
                
            elif msg_type == "health_check":
                # Health check response
                uptime = (datetime.now() - self.start_time).total_seconds()
                response = {
                    "type": "health_response",
                    "status": "healthy",
                    "service": self.service_name,
                    "version": self.version,
                    "uptime": uptime,
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response))
                logger.info("Responded to health check")
                
            elif msg_type == "analyze":
                # Simple analysis response
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 0)
                
                # Simulate analysis
                await asyncio.sleep(1)  # Simulate processing time
                
                response = {
                    "type": "analysis_result",
                    "status": "success",
                    "model_slug": model_slug,
                    "app_number": app_number,
                    "service": self.service_name,
                    "results": {
                        "total_files": 10,
                        "issues_found": 3,
                        "severity_breakdown": {
                            "high": 1,
                            "medium": 1,
                            "low": 1
                        }
                    },
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response))
                logger.info(f"Completed analysis for {model_slug} app {app_number}")
                
            else:
                # Unknown message type
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
                pass  # Connection might be closed

async def handle_client(websocket):
    """Handle client connections."""
    analyzer = StaticAnalyzer()
    client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.info(f"New client connected: {client_addr}")
    
    try:
        async for message in websocket:
            try:
                # Parse JSON message
                message_data = json.loads(message)
                logger.debug(f"Received message: {message_data}")
                
                # Handle the message
                await analyzer.handle_message(websocket, message_data)
                
            except json.JSONDecodeError:
                logger.error("Received invalid JSON message")
                error_response = {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "service": analyzer.service_name
                }
                await websocket.send(json.dumps(error_response))
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {client_addr}")
    except Exception as e:
        logger.error(f"Unexpected error with client {client_addr}: {e}")

async def main():
    """Start the static analyzer service."""
    host = os.getenv('WEBSOCKET_HOST', 'localhost')
    port = int(os.getenv('WEBSOCKET_PORT', 8001))
    
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
        """
        Categorize files by type for targeted analysis.
        """
        file_types = {
            'python': [],
            'javascript': [],
            'typescript': [],
            'css': [],
            'html': []
        }
        
        # File extension mappings
        extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.css': 'css',
            '.scss': 'css',
            '.sass': 'css',
            '.less': 'css',
            '.html': 'html',
            '.htm': 'html',
            '.vue': 'javascript'  # Vue files contain JS
        }
        
        # Walk through all files
        for file_path in source_path.rglob('*'):
            if file_path.is_file() and not self._should_ignore_file(file_path):
                ext = file_path.suffix.lower()
                if ext in extensions:
                    file_types[extensions[ext]].append(file_path)
        
        return file_types
    
    def _should_ignore_file(self, file_path: Path) -> bool:
        """
        Check if file should be ignored during analysis.
        """
        ignore_patterns = [
            'node_modules', '.git', '__pycache__', '.pytest_cache',
            'venv', '.venv', 'env', '.env', 'build', 'dist',
            '.min.js', '.min.css', 'vendor'
        ]
        
        path_str = str(file_path).lower()
        return any(pattern in path_str for pattern in ignore_patterns)
    
    async def _analyze_file_type(self, file_type: str, files: List[Path], source_path: Path) -> Dict[str, List[Dict]]:
        """
        Analyze files of a specific type using appropriate tools.
        """
        results = {
            'security_issues': [],
            'quality_issues': [],
            'dependency_issues': [],
            'type_issues': [],
            'style_issues': []
        }
        
        if file_type == 'python':
            results.update(await self._analyze_python_files(files, source_path))
        elif file_type in ['javascript', 'typescript']:
            results.update(await self._analyze_js_ts_files(files, source_path, file_type))
        elif file_type == 'css':
            results.update(await self._analyze_css_files(files, source_path))
        elif file_type == 'html':
            results.update(await self._analyze_html_files(files, source_path))
        
        return results
    
    async def _analyze_python_files(self, files: List[Path], source_path: Path) -> Dict[str, List[Dict]]:
        """
        Analyze Python files for security and quality issues.
        """
        results = {
            'security_issues': [],
            'quality_issues': [],
            'dependency_issues': [],
            'type_issues': []
        }
        
        # Run Bandit for security analysis
        try:
            bandit_result = subprocess.run([
                'bandit', '-r', str(source_path), '-f', 'json'
            ], capture_output=True, text=True)
            
            if bandit_result.stdout:
                bandit_data = json.loads(bandit_result.stdout)
                for issue in bandit_data.get('results', []):
                    results['security_issues'].append({
                        'tool': 'bandit',
                        'severity': issue.get('issue_severity', 'UNKNOWN'),
                        'confidence': issue.get('issue_confidence', 'UNKNOWN'),
                        'file': issue.get('filename', ''),
                        'line': issue.get('line_number', 0),
                        'message': issue.get('issue_text', ''),
                        'rule_id': issue.get('test_id', ''),
                        'category': 'security'
                    })
        except Exception as e:
            logger.warning(f"Bandit analysis failed: {str(e)}")
        
        # Run Pylint for code quality
        try:
            for file_path in files:
                pylint_result = subprocess.run([
                    'pylint', str(file_path), '--output-format=json'
                ], capture_output=True, text=True)
                
                if pylint_result.stdout:
                    try:
                        pylint_data = json.loads(pylint_result.stdout)
                        for issue in pylint_data:
                            results['quality_issues'].append({
                                'tool': 'pylint',
                                'severity': issue.get('type', 'info'),
                                'file': issue.get('path', ''),
                                'line': issue.get('line', 0),
                                'column': issue.get('column', 0),
                                'message': issue.get('message', ''),
                                'rule_id': issue.get('message-id', ''),
                                'category': 'quality'
                            })
                    except json.JSONDecodeError:
                        pass  # Pylint sometimes outputs non-JSON
        except Exception as e:
            logger.warning(f"Pylint analysis failed: {str(e)}")
        
        # Run Safety for dependency vulnerability check
        try:
            # Look for requirements files
            req_files = list(source_path.glob('**/requirements*.txt'))
            req_files.extend(source_path.glob('**/Pipfile'))
            
            for req_file in req_files:
                safety_result = subprocess.run([
                    'safety', 'check', '--file', str(req_file), '--json'
                ], capture_output=True, text=True)
                
                if safety_result.stdout:
                    try:
                        safety_data = json.loads(safety_result.stdout)
                        for vuln in safety_data:
                            results['dependency_issues'].append({
                                'tool': 'safety',
                                'severity': 'HIGH',
                                'package': vuln.get('package_name', ''),
                                'version': vuln.get('installed_version', ''),
                                'vulnerability': vuln.get('vulnerability_id', ''),
                                'message': vuln.get('advisory', ''),
                                'category': 'dependency'
                            })
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.warning(f"Safety analysis failed: {str(e)}")
        
        return results
    
    async def _analyze_js_ts_files(self, files: List[Path], source_path: Path, file_type: str) -> Dict[str, List[Dict]]:
        """
        Analyze JavaScript/TypeScript files using ESLint.
        """
        results = {
            'security_issues': [],
            'quality_issues': [],
            'style_issues': []
        }
        
        try:
            # Create ESLint config for security
            eslint_config = {
                "env": {"browser": True, "node": True, "es2021": True},
                "extends": ["eslint:recommended"],
                "plugins": ["security"],
                "rules": {
                    "security/detect-object-injection": "error",
                    "security/detect-non-literal-fs-filename": "error",
                    "security/detect-unsafe-regex": "error",
                    "security/detect-buffer-noassert": "error",
                    "security/detect-child-process": "error",
                    "security/detect-disable-mustache-escape": "error",
                    "security/detect-eval-with-expression": "error",
                    "security/detect-no-csrf-before-method-override": "error",
                    "security/detect-non-literal-regexp": "error",
                    "security/detect-non-literal-require": "error",
                    "security/detect-possible-timing-attacks": "error",
                    "security/detect-pseudoRandomBytes": "error"
                }
            }
            
            if file_type == 'typescript':
                eslint_config["parser"] = "@typescript-eslint/parser"
                eslint_config["plugins"].append("@typescript-eslint")
            
            # Write config file
            config_path = source_path / '.eslintrc.json'
            config_path.write_text(json.dumps(eslint_config, indent=2))
            
            # Run ESLint
            for file_path in files:
                eslint_result = subprocess.run([
                    'npx', 'eslint', str(file_path), '--format', 'json'
                ], capture_output=True, text=True)
                
                if eslint_result.stdout:
                    try:
                        eslint_data = json.loads(eslint_result.stdout)
                        for file_result in eslint_data:
                            for message in file_result.get('messages', []):
                                issue_data = {
                                    'tool': 'eslint',
                                    'severity': message.get('severity', 1),
                                    'file': file_result.get('filePath', ''),
                                    'line': message.get('line', 0),
                                    'column': message.get('column', 0),
                                    'message': message.get('message', ''),
                                    'rule_id': message.get('ruleId', ''),
                                }
                                
                                # Categorize by rule type
                                rule_id = message.get('ruleId', '')
                                if 'security/' in rule_id:
                                    issue_data['category'] = 'security'
                                    results['security_issues'].append(issue_data)
                                else:
                                    issue_data['category'] = 'quality'
                                    results['quality_issues'].append(issue_data)
                    except json.JSONDecodeError:
                        pass
                        
        except Exception as e:
            logger.warning(f"ESLint analysis failed: {str(e)}")
        
        return results
    
    async def _analyze_css_files(self, files: List[Path], source_path: Path) -> Dict[str, List[Dict]]:
        """
        Analyze CSS files using Stylelint.
        """
        results = {'style_issues': []}
        
        try:
            for file_path in files:
                stylelint_result = subprocess.run([
                    'npx', 'stylelint', str(file_path), '--formatter', 'json'
                ], capture_output=True, text=True)
                
                if stylelint_result.stdout:
                    try:
                        stylelint_data = json.loads(stylelint_result.stdout)
                        for file_result in stylelint_data:
                            for warning in file_result.get('warnings', []):
                                results['style_issues'].append({
                                    'tool': 'stylelint',
                                    'severity': warning.get('severity', 'warning'),
                                    'file': file_result.get('source', ''),
                                    'line': warning.get('line', 0),
                                    'column': warning.get('column', 0),
                                    'message': warning.get('text', ''),
                                    'rule_id': warning.get('rule', ''),
                                    'category': 'style'
                                })
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.warning(f"Stylelint analysis failed: {str(e)}")
        
        return results
    
    async def _analyze_html_files(self, files: List[Path], source_path: Path) -> Dict[str, List[Dict]]:
        """
        Analyze HTML files for basic issues.
        """
        results = {'quality_issues': []}
        
        # Basic HTML validation - could be extended with htmlhint or similar
        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8')
                
                # Check for common security issues
                if '<script>' in content and 'eval(' in content:
                    results['quality_issues'].append({
                        'tool': 'html-analyzer',
                        'severity': 'HIGH',
                        'file': str(file_path),
                        'message': 'Potential XSS risk: eval() usage in script tag',
                        'category': 'security'
                    })
                
                if 'javascript:' in content:
                    results['quality_issues'].append({
                        'tool': 'html-analyzer',
                        'severity': 'MEDIUM',
                        'file': str(file_path),
                        'message': 'Potential XSS risk: javascript: protocol usage',
                        'category': 'security'
                    })
                    
            except Exception as e:
                logger.warning(f"HTML analysis failed for {file_path}: {str(e)}")
        
        return results
    
    def _generate_summary(self, results: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """
        Generate analysis summary with counts and severity breakdown.
        """
        summary = {
            'total_issues': 0,
            'by_category': {},
            'by_severity': {},
            'top_issues': []
        }
        
        # Count issues by category and severity
        for category, issues in results.items():
            if isinstance(issues, list):
                count = len(issues)
                summary['total_issues'] += count
                summary['by_category'][category] = count
                
                # Count by severity
                for issue in issues:
                    severity = str(issue.get('severity', 'UNKNOWN')).upper()
                    summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
        
        # Get top issues (by severity)
        all_issues = []
        for category, issues in results.items():
            if isinstance(issues, list):
                all_issues.extend(issues)
        
        # Sort by severity (HIGH > MEDIUM > LOW)
        severity_order = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'ERROR': 3, 'WARNING': 2, 'INFO': 1}
        all_issues.sort(
            key=lambda x: severity_order.get(str(x.get('severity', '')).upper(), 0),
            reverse=True
        )
        
        summary['top_issues'] = all_issues[:10]  # Top 10 issues
        
        return summary
    
    async def _send_progress(self, websocket, request_id: str, message: str, percentage: int):
        """Send progress update to client."""
        try:
            progress = ProgressUpdate(
                request_id=request_id,
                message=message,
                percentage=percentage
            )
            
            ws_message = WebSocketMessage(
                type=MessageType.PROGRESS_UPDATE,
                data=asdict(progress)
            )
            
            await websocket.send(json.dumps(asdict(ws_message)))
        except Exception as e:
            logger.error(f"Failed to send progress: {str(e)}")


async def handle_client(websocket, path):
    """Handle incoming WebSocket connections."""
    analyzer = StaticAnalyzer()
    logger.info(f"New client connected: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            try:
                # Parse incoming message
                data = json.loads(message)
                ws_message = WebSocketMessage(**data)
                
                if ws_message.type == MessageType.STATIC_ANALYSIS_REQUEST:
                    # Parse analysis request
                    request = StaticAnalysisRequest(**ws_message.data)
                    
                    # Perform analysis
                    result = await analyzer.analyze(request, websocket)
                    
                    # Send result back
                    response = WebSocketMessage(
                        type=MessageType.ANALYSIS_RESULT,
                        data=asdict(result)
                    )
                    
                    await websocket.send(json.dumps(asdict(response)))
                
                elif ws_message.type == MessageType.HEALTH_CHECK:
                    # Respond to health check
                    response = WebSocketMessage(
                        type=MessageType.HEALTH_RESPONSE,
                        data={'status': 'healthy', 'service': 'static-analyzer'}
                    )
                    await websocket.send(json.dumps(asdict(response)))
                    
            except json.JSONDecodeError:
                logger.error("Received invalid JSON message")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
