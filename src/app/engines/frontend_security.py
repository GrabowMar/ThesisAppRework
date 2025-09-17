"""
Frontend Security Analysis Tools
===============================

Implementation of frontend security analysis tools inspired by the attached files.
Includes ESLint, npm audit, JSHint, and other JavaScript/TypeScript security tools.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import (
    BaseAnalysisTool, ToolResult, Finding, ToolStatus, Severity, Confidence,
    find_executable, run_command, normalize_severity,
    analysis_tool
)

logger = __import__('logging').getLogger(__name__)

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
        return {"security", "quality", "javascript", "typescript", "frontend", "static"}
    
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
                # Extract version from output like "v8.57.0"
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
                        status = ToolStatus.ISSUES_FOUND.value.format(count=len(findings))
                    else:
                        status = ToolStatus.SUCCESS.value
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse ESLint JSON output: {e}")
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
                    # Map ESLint severity to our severity
                    eslint_severity = message.get('severity', 1)
                    severity = Severity.HIGH.value if eslint_severity == 2 else Severity.MEDIUM.value
                    
                    rule_id = message.get('ruleId', '')
                    
                    finding = Finding(
                        tool=self.name,
                        severity=severity,
                        confidence=Confidence.HIGH.value,
                        title=message.get('message', '').strip(),
                        description=message.get('message', '').strip(),
                        file_path=rel_path,
                        line_number=message.get('line'),
                        column=message.get('column'),
                        end_line=message.get('endLine'),
                        end_column=message.get('endColumn'),
                        category=rule_id,
                        rule_id=rule_id,
                        tags=['quality', 'javascript'],
                        raw_data=message
                    )
                    
                    # Add security tag for security-related rules
                    if rule_id and any(term in rule_id.lower() for term in ['security', 'xss', 'injection']):
                        finding.tags.append('security')
                    
                    # Add fix suggestion if available
                    fix_info = message.get('fix')
                    if fix_info:
                        finding.fix_suggestion = "ESLint auto-fix available"
                    
                    findings.append(finding)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse ESLint message: {e}")
                    continue
        
        return findings

@analysis_tool
class NpmAuditTool(BaseAnalysisTool):
    """npm audit security vulnerability scanner."""
    
    @property
    def name(self) -> str:
        return "npm-audit"
    
    @property
    def display_name(self) -> str:
        return "npm audit"
    
    @property
    def description(self) -> str:
        return "Security vulnerability scanner for npm packages"
    
    @property
    def tags(self) -> Set[str]:
        return {"security", "javascript", "frontend", "dependencies"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"javascript", "typescript"}
    
    def is_available(self) -> bool:
        """Check if npm is available."""
        return find_executable("npm") is not None
    
    def get_version(self) -> Optional[str]:
        """Get npm version."""
        try:
            returncode, stdout, _ = run_command(["npm", "--version"], timeout=10)
            if returncode == 0:
                return stdout.strip()
        except Exception as e:
            self.logger.debug(f"Failed to get npm version: {e}")
        return None
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run npm audit analysis."""
        start_time = __import__('time').time()
        
        try:
            # Check for package.json
            package_json = target_path / "package.json"
            if not package_json.exists():
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SKIPPED.value,
                    metadata={'reason': 'No package.json found'},
                    duration_seconds=__import__('time').time() - start_time
                )
            
            # Build npm audit command
            command = ["npm", "audit", "--json"]
            
            # Add custom args
            command.extend(self.config.custom_args)
            
            # Run npm audit
            returncode, stdout, stderr = run_command(
                command,
                cwd=target_path,
                timeout=self.config.timeout,
                env=self.config.environment
            )
            
            # Parse results
            findings = []
            status = ToolStatus.SUCCESS.value
            
            # npm audit returns non-zero when vulnerabilities are found
            if stdout:
                try:
                    audit_data = json.loads(stdout) if stdout else {}
                    findings = self._parse_npm_audit_results(audit_data)
                    
                    if findings:
                        status = ToolStatus.ISSUES_FOUND.value.format(count=len(findings))
                    else:
                        status = ToolStatus.SUCCESS.value
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse npm audit JSON output: {e}")
                    status = ToolStatus.ERROR.value
            else:
                if returncode != 0:
                    status = ToolStatus.ERROR.value
                    error_msg = stderr or "npm audit execution failed"
                    return ToolResult(
                        tool_name=self.name,
                        status=status,
                        error=error_msg,
                        duration_seconds=__import__('time').time() - start_time
                    )
                else:
                    status = ToolStatus.SUCCESS.value
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings[:self.config.max_issues],
                output=stdout,
                metadata={
                    'has_package_json': True,
                    'return_code': returncode
                },
                duration_seconds=__import__('time').time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"npm audit analysis failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=__import__('time').time() - start_time
            )
    
    def _parse_npm_audit_results(self, audit_data: Dict[str, Any]) -> List[Finding]:
        """Parse npm audit JSON results into Finding objects."""
        findings = []
        
        # Handle different npm audit output formats
        vulnerabilities = audit_data.get('vulnerabilities', {})
        if not vulnerabilities:
            # Try old format
            advisories = audit_data.get('advisories', {})
            for advisory_id, advisory in advisories.items():
                findings.extend(self._parse_advisory(advisory_id, advisory))
        else:
            # New format
            for package_name, vuln_info in vulnerabilities.items():
                findings.extend(self._parse_vulnerability(package_name, vuln_info))
        
        return findings
    
    def _parse_vulnerability(self, package_name: str, vuln_info: Dict[str, Any]) -> List[Finding]:
        """Parse vulnerability info from new npm audit format."""
        findings = []
        
        try:
            severity = vuln_info.get('severity', 'unknown')
            via = vuln_info.get('via', [])
            
            for item in via:
                if isinstance(item, dict):
                    title = f"Vulnerable package: {package_name}"
                    description = item.get('title', '')
                    
                    finding = Finding(
                        tool=self.name,
                        severity=normalize_severity(severity),
                        confidence=Confidence.HIGH.value,
                        title=title,
                        description=description,
                        file_path="package.json",
                        category="dependency_vulnerability",
                        rule_id=str(item.get('id', '')),
                        references=[item.get('url', '')] if item.get('url') else [],
                        tags=['security', 'javascript', 'dependency'],
                        raw_data=vuln_info
                    )
                    
                    findings.append(finding)
                    
        except Exception as e:
            logger.warning(f"Failed to parse vulnerability for {package_name}: {e}")
        
        return findings
    
    def _parse_advisory(self, advisory_id: str, advisory: Dict[str, Any]) -> List[Finding]:
        """Parse advisory from old npm audit format."""
        findings = []
        
        try:
            title = advisory.get('title', '')
            severity = advisory.get('severity', 'unknown')
            module_name = advisory.get('module_name', 'unknown')
            
            finding = Finding(
                tool=self.name,
                severity=normalize_severity(severity),
                confidence=Confidence.HIGH.value,
                title=f"Vulnerable package: {module_name}",
                description=title,
                file_path="package.json",
                category="dependency_vulnerability", 
                rule_id=advisory_id,
                references=[advisory.get('url', '')] if advisory.get('url') else [],
                tags=['security', 'javascript', 'dependency'],
                raw_data=advisory
            )
            
            findings.append(finding)
            
        except Exception as e:
            logger.warning(f"Failed to parse advisory {advisory_id}: {e}")
        
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
        return {"quality", "javascript", "frontend", "static"}
    
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
                    # JSHint outputs one JSON object per line
                    jshint_results = []
                    for line in stdout.strip().split('\n'):
                        if line.strip():
                            jshint_results.append(json.loads(line))
                    
                    findings = self._parse_jshint_results(jshint_results, target_path)
                    
                    if findings:
                        status = ToolStatus.ISSUES_FOUND.value.format(count=len(findings))
                    else:
                        status = ToolStatus.SUCCESS.value
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSHint JSON output: {e}")
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
                
                error_info = result.get('error', {})
                if not error_info:
                    continue
                
                # Determine severity based on error reason
                reason = error_info.get('reason', '').lower()
                if any(term in reason for term in ['unsafe', 'security', 'dangerous']):
                    severity = Severity.HIGH.value
                elif any(term in reason for term in ['deprecated', 'bad practice']):
                    severity = Severity.MEDIUM.value
                else:
                    severity = Severity.LOW.value
                
                finding = Finding(
                    tool=self.name,
                    severity=severity,
                    confidence=Confidence.MEDIUM.value,
                    title=error_info.get('reason', '').strip(),
                    description=error_info.get('reason', '').strip(),
                    file_path=rel_path,
                    line_number=error_info.get('line'),
                    column=error_info.get('character'),
                    category=error_info.get('code', ''),
                    rule_id=error_info.get('code', ''),
                    tags=['quality', 'javascript'],
                    raw_data=result
                )
                
                findings.append(finding)
                
            except Exception as e:
                self.logger.warning(f"Failed to parse JSHint result: {e}")
                continue
        
        return findings