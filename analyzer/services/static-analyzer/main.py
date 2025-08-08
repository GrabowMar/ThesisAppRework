"""
Static Analysis Service - Frontend & Backend Security/Quality Analysis
Analyzes Python, JavaScript, TypeScript, HTML, CSS files for security vulnerabilities and code quality issues.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import websockets
from pathlib import Path
from typing import Dict, List, Any, Optional
import shutil
from dataclasses import asdict
from datetime import datetime
import uuid

# Add parent directory to path for shared imports
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.protocol import (
    WebSocketMessage, MessageType, SecurityAnalysisRequest, 
    AnalysisResult, ProgressUpdate, AnalysisStatus, AnalysisType,
    AnalysisIssue, SeverityLevel, create_request_from_dict
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StaticAnalyzer:
    """Comprehensive static analysis for frontend and backend code."""
    
    def __init__(self):
        self.tools = {
            'python': ['bandit', 'pylint', 'safety', 'mypy'],
            'javascript': ['eslint'],
            'typescript': ['eslint'],
            'css': ['stylelint'],
            'html': ['htmlhint']
        }
        
    async def analyze(self, request: SecurityAnalysisRequest, websocket) -> AnalysisResult:
        """
        Perform comprehensive static analysis on the provided code/files.
        """
        analysis_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        logger.info(f"Starting static analysis for {request.source_path}")
        
        # Send initial progress
        await self._send_progress(websocket, analysis_id, "Initializing static analysis", 0.0)
        
        issues = []
        
        try:
            # Create temporary directory for analysis
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download/copy source code
                await self._send_progress(websocket, analysis_id, "Preparing source code", 0.1)
                source_path = await self._prepare_source_code(request, temp_dir)
                
                if not source_path:
                    raise Exception("Failed to prepare source code for analysis")
                
                # Analyze different file types
                file_types = self._categorize_files(source_path)
                total_steps = len(file_types) * 2  # 2 steps per file type
                current_step = 0
                
                for file_type, files in file_types.items():
                    if not files:
                        continue
                        
                    current_step += 1
                    progress = 0.2 + (current_step / total_steps) * 0.6
                    await self._send_progress(
                        websocket, analysis_id, 
                        f"Analyzing {file_type} files", progress
                    )
                    
                    # Run analysis for this file type
                    type_issues = await self._analyze_file_type(file_type, files, source_path)
                    issues.extend(type_issues)
                
                # Generate summary
                await self._send_progress(websocket, analysis_id, "Generating summary", 0.85)
                summary = self._generate_summary(issues)
                
                # Final progress
                await self._send_progress(websocket, analysis_id, "Analysis complete", 1.0)
                
                return AnalysisResult(
                    analysis_id=analysis_id,
                    status=AnalysisStatus.COMPLETED,
                    analysis_type=request.analysis_type,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                    duration=(datetime.utcnow() - started_at).total_seconds(),
                    issues=issues,
                    summary=summary,
                    metadata={
                        'analyzer': 'static-analyzer',
                        'files_analyzed': sum(len(files) for files in file_types.values()),
                        'tools_used': request.tools
                    }
                )
                
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")
            await self._send_progress(websocket, analysis_id, f"Analysis failed: {str(e)}", 1.0)
            
            return AnalysisResult(
                analysis_id=analysis_id,
                status=AnalysisStatus.FAILED,
                analysis_type=request.analysis_type,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration=(datetime.utcnow() - started_at).total_seconds(),
                issues=[],
                summary={},
                metadata={'analyzer': 'static-analyzer'},
                error_message=str(e)
            )
    
    async def _prepare_source_code(self, request: SecurityAnalysisRequest, temp_dir: str) -> Optional[Path]:
        """
        Prepare source code for analysis from various sources.
        """
        try:
            source_path = Path(temp_dir) / "source"
            source_path.mkdir(exist_ok=True)
            
            # Check if we have a local path (e.g., misc/models/*)
            if Path(request.source_path).exists():
                shutil.copytree(request.source_path, source_path, dirs_exist_ok=True)
                return source_path
            
            # Check if we have inline code samples
            if hasattr(request, 'options') and 'code_samples' in request.options:
                for filename, content in request.options['code_samples'].items():
                    file_path = source_path / filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content)
                return source_path
            
            # Default: try to download from git if it's a repository
            if request.source_path.endswith('.git'):
                result = subprocess.run([
                    'git', 'clone', request.source_path, str(source_path)
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    return source_path
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to prepare source code: {str(e)}")
            return None
    
    def _categorize_files(self, source_path: Path) -> Dict[str, List[Path]]:
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
    
    async def _analyze_file_type(self, file_type: str, files: List[Path], source_path: Path) -> List[AnalysisIssue]:
        """
        Analyze files of a specific type using appropriate tools.
        """
        issues = []
        
        if file_type == 'python':
            issues.extend(await self._analyze_python_files(files, source_path))
        elif file_type in ['javascript', 'typescript']:
            issues.extend(await self._analyze_js_ts_files(files, source_path, file_type))
        elif file_type == 'css':
            issues.extend(await self._analyze_css_files(files, source_path))
        elif file_type == 'html':
            issues.extend(await self._analyze_html_files(files, source_path))
        
        return issues
    
    async def _analyze_python_files(self, files: List[Path], source_path: Path) -> List[AnalysisIssue]:
        """
        Analyze Python files for security and quality issues.
        """
        issues = []
        
        # Run Bandit for security analysis
        try:
            bandit_result = subprocess.run([
                'bandit', '-r', str(source_path), '-f', 'json'
            ], capture_output=True, text=True)
            
            if bandit_result.stdout:
                bandit_data = json.loads(bandit_result.stdout)
                for issue in bandit_data.get('results', []):
                    severity_map = {
                        'LOW': SeverityLevel.LOW,
                        'MEDIUM': SeverityLevel.MEDIUM,
                        'HIGH': SeverityLevel.HIGH
                    }
                    
                    issues.append(AnalysisIssue(
                        tool='bandit',
                        severity=severity_map.get(issue.get('issue_severity', 'LOW'), SeverityLevel.LOW),
                        confidence=issue.get('issue_confidence', 'UNKNOWN'),
                        file_path=issue.get('filename', ''),
                        line_number=issue.get('line_number', 0),
                        message=issue.get('issue_text', ''),
                        rule_id=issue.get('test_id', ''),
                        code_snippet=issue.get('code', '')
                    ))
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
                            severity_map = {
                                'error': SeverityLevel.HIGH,
                                'warning': SeverityLevel.MEDIUM,
                                'refactor': SeverityLevel.LOW,
                                'convention': SeverityLevel.LOW,
                                'info': SeverityLevel.INFO
                            }
                            
                            issues.append(AnalysisIssue(
                                tool='pylint',
                                severity=severity_map.get(issue.get('type', 'info'), SeverityLevel.INFO),
                                confidence='HIGH',
                                file_path=issue.get('path', ''),
                                line_number=issue.get('line', 0),
                                column=issue.get('column', 0),
                                message=issue.get('message', ''),
                                rule_id=issue.get('message-id', '')
                            ))
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
                            issues.append(AnalysisIssue(
                                tool='safety',
                                severity=SeverityLevel.HIGH,
                                confidence='HIGH',
                                file_path=str(req_file),
                                message=f"Vulnerable package: {vuln.get('package_name', '')} "
                                       f"version {vuln.get('installed_version', '')}",
                                description=vuln.get('advisory', ''),
                                rule_id=vuln.get('vulnerability_id', '')
                            ))
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.warning(f"Safety analysis failed: {str(e)}")
        
        return issues
    
    async def _analyze_js_ts_files(self, files: List[Path], source_path: Path, file_type: str) -> List[AnalysisIssue]:
        """
        Analyze JavaScript/TypeScript files using ESLint.
        """
        issues = []
        
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
                                severity_map = {
                                    1: SeverityLevel.MEDIUM,  # Warning
                                    2: SeverityLevel.HIGH     # Error
                                }
                                
                                rule_id = message.get('ruleId', '')
                                severity = SeverityLevel.HIGH if 'security/' in rule_id else SeverityLevel.MEDIUM
                                
                                issues.append(AnalysisIssue(
                                    tool='eslint',
                                    severity=severity,
                                    confidence='HIGH',
                                    file_path=file_result.get('filePath', ''),
                                    line_number=message.get('line', 0),
                                    column=message.get('column', 0),
                                    message=message.get('message', ''),
                                    rule_id=rule_id
                                ))
                    except json.JSONDecodeError:
                        pass
                        
        except Exception as e:
            logger.warning(f"ESLint analysis failed: {str(e)}")
        
        return issues
    
    async def _analyze_css_files(self, files: List[Path], source_path: Path) -> List[AnalysisIssue]:
        """
        Analyze CSS files using Stylelint.
        """
        issues = []
        
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
                                severity_map = {
                                    'error': SeverityLevel.HIGH,
                                    'warning': SeverityLevel.MEDIUM
                                }
                                
                                issues.append(AnalysisIssue(
                                    tool='stylelint',
                                    severity=severity_map.get(warning.get('severity', 'warning'), SeverityLevel.MEDIUM),
                                    confidence='MEDIUM',
                                    file_path=file_result.get('source', ''),
                                    line_number=warning.get('line', 0),
                                    column=warning.get('column', 0),
                                    message=warning.get('text', ''),
                                    rule_id=warning.get('rule', '')
                                ))
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.warning(f"Stylelint analysis failed: {str(e)}")
        
        return issues
    
    async def _analyze_html_files(self, files: List[Path], source_path: Path) -> List[AnalysisIssue]:
        """
        Analyze HTML files for basic issues.
        """
        issues = []
        
        # Basic HTML validation - could be extended with htmlhint or similar
        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8')
                
                # Check for common security issues
                if '<script>' in content and 'eval(' in content:
                    issues.append(AnalysisIssue(
                        tool='html-analyzer',
                        severity=SeverityLevel.HIGH,
                        confidence='MEDIUM',
                        file_path=str(file_path),
                        message='Potential XSS risk: eval() usage in script tag',
                        rule_id='xss-eval-usage'
                    ))
                
                if 'javascript:' in content:
                    issues.append(AnalysisIssue(
                        tool='html-analyzer',
                        severity=SeverityLevel.MEDIUM,
                        confidence='MEDIUM',
                        file_path=str(file_path),
                        message='Potential XSS risk: javascript: protocol usage',
                        rule_id='xss-javascript-protocol'
                    ))
                    
            except Exception as e:
                logger.warning(f"HTML analysis failed for {file_path}: {str(e)}")
        
        return issues
    
    def _generate_summary(self, issues: List[AnalysisIssue]) -> Dict[str, Any]:
        """
        Generate analysis summary with counts and severity breakdown.
        """
        summary = {
            'total_issues': len(issues),
            'by_severity': {},
            'by_tool': {},
            'top_issues': []
        }
        
        # Count by severity and tool
        for issue in issues:
            severity = issue.severity.value
            tool = issue.tool
            
            summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
            summary['by_tool'][tool] = summary['by_tool'].get(tool, 0) + 1
        
        # Get top issues (by severity)
        severity_order = {
            SeverityLevel.CRITICAL: 5,
            SeverityLevel.HIGH: 4,
            SeverityLevel.MEDIUM: 3,
            SeverityLevel.LOW: 2,
            SeverityLevel.INFO: 1
        }
        
        sorted_issues = sorted(
            issues,
            key=lambda x: severity_order.get(x.severity, 0),
            reverse=True
        )
        
        summary['top_issues'] = [issue.to_dict() for issue in sorted_issues[:10]]
        
        return summary
    
    async def _send_progress(self, websocket, analysis_id: str, message: str, progress: float):
        """Send progress update to client."""
        try:
            progress_update = ProgressUpdate(
                analysis_id=analysis_id,
                stage="analyzing",
                progress=progress,
                message=message
            )
            
            ws_message = WebSocketMessage(
                type=MessageType.PROGRESS_UPDATE,
                data=progress_update.to_dict()
            )
            
            await websocket.send(ws_message.to_json())
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
                ws_message = WebSocketMessage.from_json(message)
                
                if ws_message.type == MessageType.ANALYSIS_REQUEST:
                    # Parse analysis request
                    request = create_request_from_dict(ws_message.data)
                    
                    # Only handle security analysis requests
                    if isinstance(request, SecurityAnalysisRequest):
                        # Perform analysis
                        result = await analyzer.analyze(request, websocket)
                        
                        # Send result back
                        response = WebSocketMessage(
                            type=MessageType.ANALYSIS_RESULT,
                            data=result.to_dict(),
                            correlation_id=ws_message.id
                        )
                        
                        await websocket.send(response.to_json())
                    else:
                        # Not a security analysis request
                        error_msg = WebSocketMessage(
                            type=MessageType.ERROR,
                            data={
                                'code': 'UNSUPPORTED_REQUEST',
                                'message': 'This service only handles security analysis requests'
                            },
                            correlation_id=ws_message.id
                        )
                        await websocket.send(error_msg.to_json())
                
                elif ws_message.type == MessageType.HEARTBEAT:
                    # Respond to heartbeat
                    response = WebSocketMessage(
                        type=MessageType.HEARTBEAT,
                        data={'status': 'healthy', 'service': 'static-analyzer'}
                    )
                    await websocket.send(response.to_json())
                    
            except json.JSONDecodeError:
                logger.error("Received invalid JSON message")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")


def main():
    """Start the static analyzer service."""
    host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
    port = int(os.getenv('WEBSOCKET_PORT', 8001))
    
    logger.info(f"Starting Static Analyzer service on {host}:{port}")
    
    start_server = websockets.serve(handle_client, host, port)
    
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
    
    def _categorize_files(self, source_path: Path) -> Dict[str, List[Path]]:
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


def main():
    """Start the static analyzer service."""
    host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
    port = int(os.getenv('WEBSOCKET_PORT', 8001))
    
    logger.info(f"Starting Static Analyzer service on {host}:{port}")
    
    start_server = websockets.serve(handle_client, host, port)
    
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
