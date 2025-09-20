"""
Static Analysis Tools
====================

Static analysis tools that run in the static-analyzer container.
Includes security, quality, and linting tools for various languages.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import (
    BaseAnalysisTool, ToolResult, Finding, ToolStatus, Severity, Confidence,
    find_executable, run_command, normalize_severity, normalize_confidence,
    analysis_tool
)

logger = __import__('logging').getLogger(__name__)

@analysis_tool
class BanditTool(BaseAnalysisTool):
    """Bandit Python security linter."""
    
    @property
    def name(self) -> str:
        return "bandit"
    
    @property
    def display_name(self) -> str:
        return "Bandit"
    
    @property
    def description(self) -> str:
        return "Security vulnerability scanner for Python code"
    
    @property
    def tags(self) -> Set[str]:
        return {"security", "python", "static"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"python"}
    
    def is_available(self) -> bool:
        """Check if bandit is available."""
        return find_executable("bandit") is not None
    
    def get_version(self) -> Optional[str]:
        """Get bandit version."""
        try:
            returncode, stdout, _ = run_command(["bandit", "--version"], timeout=10)
            if returncode == 0:
                match = re.search(r'bandit\s+(\d+\.\d+\.\d+)', stdout)
                if match:
                    return match.group(1)
        except Exception as e:
            self.logger.debug(f"Failed to get bandit version: {e}")
        return None
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run bandit analysis."""
        start_time = __import__('time').time()
        
        try:
            # Check if there are Python files to analyze
            python_files = list(target_path.rglob('*.py'))
            if not python_files:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SKIPPED.value,
                    metadata={'reason': 'No Python files found'},
                    duration_seconds=__import__('time').time() - start_time
                )
            
            # Build bandit command
            command = [
                "bandit",
                "-r", str(target_path),
                "-f", "json",
                "--severity-level", "low",
                "--confidence-level", "low"
            ]
            
            # Add exclude patterns if configured
            if self.config.exclude_patterns:
                for pattern in self.config.exclude_patterns:
                    command.extend(["-x", pattern])
            
            # Add custom args
            command.extend(self.config.custom_args)
            
            # Run bandit
            returncode, stdout, stderr = run_command(
                command,
                cwd=target_path,
                timeout=self.config.timeout,
                env=self.config.environment
            )
            
            # Parse results
            findings = []
            status = ToolStatus.SUCCESS.value
            
            if returncode == 0 or (returncode == 1 and stdout):
                # Bandit returns 1 when issues are found
                try:
                    bandit_data = json.loads(stdout) if stdout else {}
                    findings = self._parse_bandit_results(bandit_data, target_path)
                    
                    if findings:
                        status = ToolStatus.ISSUES_FOUND.value
                    else:
                        status = ToolStatus.SUCCESS.value
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse bandit JSON output: {e}")
                    status = ToolStatus.ERROR.value
                    
            else:
                status = ToolStatus.ERROR.value
                error_msg = stderr or "Bandit execution failed"
                return ToolResult(
                    tool_name=self.name,
                    status=status,
                    error=error_msg,
                    output=stdout,
                    duration_seconds=__import__('time').time() - start_time
                )
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings[:self.config.max_issues],
                output=stdout,
                metadata={
                    'python_files_scanned': len(python_files),
                    'return_code': returncode
                },
                duration_seconds=__import__('time').time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"Bandit analysis failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=__import__('time').time() - start_time
            )
    
    def _parse_bandit_results(self, bandit_data: Dict[str, Any], base_path: Path) -> List[Finding]:
        """Parse bandit JSON results into Finding objects."""
        findings = []
        
        for result in bandit_data.get('results', []):
            try:
                # Extract file path relative to base
                file_path = result.get('filename', '')
                try:
                    rel_path = str(Path(file_path).relative_to(base_path))
                except ValueError:
                    rel_path = file_path
                
                finding = Finding(
                    tool=self.name,
                    severity=normalize_severity(result.get('issue_severity')),
                    confidence=normalize_confidence(result.get('issue_confidence')),
                    title=result.get('issue_text', '').strip(),
                    description=result.get('issue_text', '').strip(),
                    file_path=rel_path,
                    line_number=result.get('line_number'),
                    category=result.get('test_name', ''),
                    rule_id=result.get('test_id', ''),
                    references=[result.get('more_info', '')] if result.get('more_info') else [],
                    tags=['security', 'python', 'static'],
                    raw_data=result
                )
                
                # Add CWE information if available
                cwe_info = result.get('issue_cwe', {})
                if cwe_info and isinstance(cwe_info, dict):
                    cwe_id = cwe_info.get('id')
                    if cwe_id:
                        finding.references.append(f"CWE-{cwe_id}")
                
                findings.append(finding)
                
            except Exception as e:
                self.logger.warning(f"Failed to parse bandit result: {e}")
                continue
        
        return findings

@analysis_tool
class SafetyTool(BaseAnalysisTool):
    """Safety Python dependency vulnerability scanner."""
    
    @property
    def name(self) -> str:
        return "safety"
    
    @property
    def display_name(self) -> str:
        return "Safety"
    
    @property
    def description(self) -> str:
        return "Vulnerability scanner for Python dependencies"
    
    @property
    def tags(self) -> Set[str]:
        return {"security", "python", "dependencies", "static"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"python"}
    
    def is_available(self) -> bool:
        """Check if safety is available."""
        return find_executable("safety") is not None
    
    def get_version(self) -> Optional[str]:
        """Get safety version."""
        try:
            returncode, stdout, _ = run_command(["safety", "--version"], timeout=10)
            if returncode == 0:
                match = re.search(r'(\d+\.\d+\.\d+)', stdout)
                if match:
                    return match.group(1)
        except Exception as e:
            self.logger.debug(f"Failed to get safety version: {e}")
        return None
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run safety analysis."""
        start_time = __import__('time').time()
        
        try:
            # Look for requirements files
            req_files = []
            for pattern in ['requirements*.txt', 'Pipfile', 'pyproject.toml', 'setup.py']:
                req_files.extend(target_path.glob(pattern))
            
            if not req_files:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SKIPPED.value,
                    metadata={'reason': 'No dependency files found'},
                    duration_seconds=__import__('time').time() - start_time
                )
            
            # Build safety command
            command = ["safety", "check", "--json"]
            
            # Add custom args
            command.extend(self.config.custom_args)
            
            # Run safety
            returncode, stdout, stderr = run_command(
                command,
                cwd=target_path,
                timeout=self.config.timeout,
                env=self.config.environment
            )
            
            # Parse results
            findings = []
            status = ToolStatus.SUCCESS.value
            
            if returncode == 0:
                # No vulnerabilities found
                status = ToolStatus.SUCCESS.value
            elif returncode == 255 and stdout:
                # Vulnerabilities found
                try:
                    safety_data = json.loads(stdout) if stdout else []
                    findings = self._parse_safety_results(safety_data)
                    
                    if findings:
                        status = ToolStatus.ISSUES_FOUND.value
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse safety JSON output: {e}")
                    status = ToolStatus.ERROR.value
            else:
                status = ToolStatus.ERROR.value
                error_msg = stderr or "Safety execution failed"
                return ToolResult(
                    tool_name=self.name,
                    status=status,
                    error=error_msg,
                    output=stdout,
                    duration_seconds=__import__('time').time() - start_time
                )
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings[:self.config.max_issues],
                output=stdout,
                metadata={
                    'dependency_files_found': len(req_files),
                    'return_code': returncode
                },
                duration_seconds=__import__('time').time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"Safety analysis failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=__import__('time').time() - start_time
            )
    
    def _parse_safety_results(self, safety_data: List[Dict[str, Any]]) -> List[Finding]:
        """Parse safety JSON results into Finding objects."""
        findings = []
        
        for result in safety_data:
            try:
                package_name = result.get('package', 'unknown')
                
                finding = Finding(
                    tool=self.name,
                    severity=normalize_severity(result.get('severity', 'medium')),
                    confidence=Confidence.HIGH.value,
                    title=f"Vulnerable package: {package_name}",
                    description=result.get('advisory', ''),
                    file_path="requirements.txt",  # Generic, as specific file depends on project structure
                    category="dependency_vulnerability",
                    rule_id=result.get('id', ''),
                    references=[
                        result.get('more_info_url', ''),
                        f"CVE: {result.get('cve', 'N/A')}"
                    ],
                    tags=['security', 'python', 'dependency', 'static'],
                    raw_data=result
                )
                
                findings.append(finding)
                
            except Exception as e:
                self.logger.warning(f"Failed to parse safety result: {e}")
                continue
        
        return findings

@analysis_tool
class PylintTool(BaseAnalysisTool):
    """Pylint Python code quality and security linter."""
    
    @property
    def name(self) -> str:
        return "pylint"
    
    @property
    def display_name(self) -> str:
        return "Pylint"
    
    @property
    def description(self) -> str:
        return "Python code quality and security analysis"
    
    @property
    def tags(self) -> Set[str]:
        return {"quality", "security", "python", "static"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"python"}
    
    def is_available(self) -> bool:
        """Check if pylint is available."""
        return find_executable("pylint") is not None
    
    def get_version(self) -> Optional[str]:
        """Get pylint version."""
        try:
            returncode, stdout, _ = run_command(["pylint", "--version"], timeout=10)
            if returncode == 0:
                match = re.search(r'pylint\s+(\d+\.\d+\.\d+)', stdout)
                if match:
                    return match.group(1)
        except Exception as e:
            self.logger.debug(f"Failed to get pylint version: {e}")
        return None
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run pylint analysis."""
        start_time = __import__('time').time()
        
        try:
            # Find Python files (limit to prevent timeouts)
            python_files = list(target_path.rglob('*.py'))
            if not python_files:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SKIPPED.value,
                    metadata={'reason': 'No Python files found'},
                    duration_seconds=__import__('time').time() - start_time
                )
            
            # Limit number of files to prevent timeouts
            max_files = 10
            if len(python_files) > max_files:
                python_files = python_files[:max_files]
            
            # Build pylint command
            command = [
                "pylint",
                "--output-format=json",
                "--reports=no",
                "--score=no"
            ]
            
            # Add file paths
            for file_path in python_files:
                command.append(str(file_path))
            
            # Add custom args
            command.extend(self.config.custom_args)
            
            # Run pylint
            returncode, stdout, stderr = run_command(
                command,
                cwd=target_path,
                timeout=self.config.timeout,
                env=self.config.environment
            )
            
            # Parse results (pylint returns non-zero for issues)
            findings = []
            status = ToolStatus.SUCCESS.value
            
            if stdout:
                try:
                    pylint_data = json.loads(stdout) if stdout else []
                    findings = self._parse_pylint_results(pylint_data, target_path)
                    
                    if findings:
                        status = ToolStatus.ISSUES_FOUND.value
                    else:
                        status = ToolStatus.SUCCESS.value
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse pylint JSON output: {e}")
                    status = ToolStatus.ERROR.value
            else:
                status = ToolStatus.SUCCESS.value
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings[:self.config.max_issues],
                output=stdout,
                metadata={
                    'python_files_analyzed': len(python_files),
                    'return_code': returncode
                },
                duration_seconds=__import__('time').time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"Pylint analysis failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=__import__('time').time() - start_time
            )
    
    def _parse_pylint_results(self, pylint_data: List[Dict[str, Any]], base_path: Path) -> List[Finding]:
        """Parse pylint JSON results into Finding objects."""
        findings = []
        
        for result in pylint_data:
            try:
                file_path = result.get('path', '')
                try:
                    rel_path = str(Path(file_path).relative_to(base_path))
                except ValueError:
                    rel_path = file_path
                
                finding = Finding(
                    tool=self.name,
                    severity=normalize_severity(result.get('type')),
                    confidence=Confidence.HIGH.value,
                    title=result.get('message', ''),
                    description=result.get('message', ''),
                    file_path=rel_path,
                    line_number=result.get('line'),
                    column=result.get('column'),
                    category=result.get('message-id', ''),
                    rule_id=result.get('symbol', ''),
                    tags=['quality', 'python', 'static'],
                    raw_data=result
                )
                
                findings.append(finding)
                
            except Exception as e:
                self.logger.warning(f"Failed to parse pylint result: {e}")
                continue
        
        return findings

@analysis_tool
class EslintTool(BaseAnalysisTool):
    """ESLint JavaScript/TypeScript security and quality linter."""
    
    @property
    def name(self) -> str:
        return "eslint"
    
    @property
    def display_name(self) -> str:
        return "ESLint"
    
    @property
    def description(self) -> str:
        return "JavaScript/TypeScript linter with security rules"
    
    @property
    def tags(self) -> Set[str]:
        return {"security", "quality", "javascript", "typescript", "static"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"javascript", "typescript", "jsx", "tsx"}
    
    def is_available(self) -> bool:
        """Check if eslint is available."""
        return find_executable("eslint") is not None
    
    def get_version(self) -> Optional[str]:
        """Get eslint version."""
        try:
            returncode, stdout, _ = run_command(["eslint", "--version"], timeout=10)
            if returncode == 0:
                match = re.search(r'v(\d+\.\d+\.\d+)', stdout)
                if match:
                    return match.group(1)
        except Exception as e:
            self.logger.debug(f"Failed to get eslint version: {e}")
        return None
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run ESLint analysis."""
        start_time = __import__('time').time()
        
        try:
            # Check for JavaScript/TypeScript files
            js_patterns = ['*.js', '*.jsx', '*.ts', '*.tsx', '*.vue']
            js_files = []
            for pattern in js_patterns:
                js_files.extend(target_path.rglob(pattern))
            
            if not js_files:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SKIPPED.value,
                    metadata={'reason': 'No JavaScript/TypeScript files found'},
                    duration_seconds=__import__('time').time() - start_time
                )
            
            # Build eslint command
            command = [
                "eslint",
                str(target_path),
                "--format", "json",
                "--ext", ".js,.jsx,.ts,.tsx,.vue"
            ]
            
            # Add ignore patterns
            for pattern in self.config.exclude_patterns:
                command.extend(["--ignore-pattern", pattern])
            
            # Add custom args
            command.extend(self.config.custom_args)
            
            # Run eslint
            returncode, stdout, stderr = run_command(
                command,
                cwd=target_path,
                timeout=self.config.timeout,
                env=self.config.environment
            )
            
            # Parse results
            findings = []
            status = ToolStatus.SUCCESS.value
            
            # ESLint returns 1 when issues are found, 0 when clean
            if returncode == 0 or (returncode == 1 and stdout):
                try:
                    eslint_data = json.loads(stdout) if stdout else []
                    findings = self._parse_eslint_results(eslint_data, target_path)
                    
                    if findings:
                        status = ToolStatus.ISSUES_FOUND.value
                    else:
                        status = ToolStatus.SUCCESS.value
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse eslint JSON output: {e}")
                    status = ToolStatus.ERROR.value
            else:
                status = ToolStatus.ERROR.value
                error_msg = stderr or "ESLint execution failed"
                return ToolResult(
                    tool_name=self.name,
                    status=status,
                    error=error_msg,
                    output=stdout,
                    duration_seconds=__import__('time').time() - start_time
                )
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings[:self.config.max_issues],
                output=stdout,
                metadata={
                    'js_files_scanned': len(js_files),
                    'return_code': returncode
                },
                duration_seconds=__import__('time').time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"ESLint analysis failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=__import__('time').time() - start_time
            )
    
    def _parse_eslint_results(self, eslint_data: List[Dict[str, Any]], base_path: Path) -> List[Finding]:
        """Parse ESLint JSON results into Finding objects."""
        findings = []
        
        for file_result in eslint_data:
            file_path = file_result.get('filePath', '')
            try:
                rel_path = str(Path(file_path).relative_to(base_path))
            except ValueError:
                rel_path = file_path
            
            for message in file_result.get('messages', []):
                try:
                    severity = message.get('severity', 1)
                    rule_id = message.get('ruleId', '')
                    
                    finding = Finding(
                        tool=self.name,
                        severity=normalize_severity(severity),
                        confidence=Confidence.HIGH.value,
                        title=message.get('message', ''),
                        description=message.get('message', ''),
                        file_path=rel_path,
                        line_number=message.get('line'),
                        column=message.get('column'),
                        end_line=message.get('endLine'),
                        end_column=message.get('endColumn'),
                        category="eslint",
                        rule_id=rule_id,
                        references=[f"https://eslint.org/docs/rules/{rule_id}"] if rule_id else [],
                        tags=['quality', 'javascript', 'static'],
                        raw_data=message
                    )
                    
                    findings.append(finding)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse eslint message: {e}")
                    continue
        
        return findings

@analysis_tool
class JshintTool(BaseAnalysisTool):
    """JSHint JavaScript code quality tool."""
    
    @property
    def name(self) -> str:
        return "jshint"
    
    @property
    def display_name(self) -> str:
        return "JSHint"
    
    @property
    def description(self) -> str:
        return "JavaScript code quality and potential error detection"
    
    @property
    def tags(self) -> Set[str]:
        return {"quality", "javascript", "static"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"javascript"}
    
    def is_available(self) -> bool:
        """Check if jshint is available."""
        return find_executable("jshint") is not None
    
    def get_version(self) -> Optional[str]:
        """Get jshint version."""
        try:
            returncode, stdout, _ = run_command(["jshint", "--version"], timeout=10)
            if returncode == 0:
                match = re.search(r'(\d+\.\d+\.\d+)', stdout)
                if match:
                    return match.group(1)
        except Exception as e:
            self.logger.debug(f"Failed to get jshint version: {e}")
        return None
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run JSHint analysis."""
        start_time = __import__('time').time()
        
        try:
            # Find JavaScript files
            js_files = list(target_path.rglob('*.js'))
            if not js_files:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SKIPPED.value,
                    metadata={'reason': 'No JavaScript files found'},
                    duration_seconds=__import__('time').time() - start_time
                )
            
            # Build jshint command
            command = ["jshint", "--reporter", "json"]
            
            # Add file paths (limit to prevent timeouts)
            max_files = 20
            if len(js_files) > max_files:
                js_files = js_files[:max_files]
            
            for js_file in js_files:
                command.append(str(js_file))
            
            # Add custom args
            command.extend(self.config.custom_args)
            
            # Run jshint
            returncode, stdout, stderr = run_command(
                command,
                cwd=target_path,
                timeout=self.config.timeout,
                env=self.config.environment
            )
            
            # Parse results
            findings = []
            status = ToolStatus.SUCCESS.value
            
            if stdout:
                try:
                    jshint_results = json.loads(stdout) if stdout else []
                    findings = self._parse_jshint_results(jshint_results, target_path)
                    
                    if findings:
                        status = ToolStatus.ISSUES_FOUND.value
                    else:
                        status = ToolStatus.SUCCESS.value
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse jshint JSON output: {e}")
                    status = ToolStatus.ERROR.value
            else:
                status = ToolStatus.SUCCESS.value
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings[:self.config.max_issues],
                output=stdout,
                metadata={
                    'js_files_analyzed': len(js_files),
                    'return_code': returncode
                },
                duration_seconds=__import__('time').time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"JSHint analysis failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=__import__('time').time() - start_time
            )
    
    def _parse_jshint_results(self, jshint_results: List[Dict[str, Any]], base_path: Path) -> List[Finding]:
        """Parse JSHint JSON results into Finding objects."""
        findings = []
        
        for result in jshint_results:
            try:
                file_path = result.get('file', '')
                try:
                    rel_path = str(Path(file_path).relative_to(base_path))
                except ValueError:
                    rel_path = file_path
                
                error = result.get('error', {})
                if not error:
                    continue
                
                finding = Finding(
                    tool=self.name,
                    severity=normalize_severity("warning"),
                    confidence=Confidence.MEDIUM.value,
                    title=error.get('reason', ''),
                    description=error.get('reason', ''),
                    file_path=rel_path,
                    line_number=error.get('line'),
                    column=error.get('character'),
                    category="jshint",
                    rule_id=error.get('code', ''),
                    tags=['quality', 'javascript', 'static'],
                    raw_data=result
                )
                
                findings.append(finding)
                
            except Exception as e:
                self.logger.warning(f"Failed to parse jshint result: {e}")
                continue
        
        return findings