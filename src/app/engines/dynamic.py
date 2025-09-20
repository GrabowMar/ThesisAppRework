"""
Dynamic Analysis Tools
=====================

Dynamic analysis tools that run in the dynamic-analyzer container.
Includes network security testing and connectivity analysis tools.
Note: ZAP was removed to reduce complexity - security analysis is handled by static tools.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import (
    BaseAnalysisTool, ToolResult, Finding, ToolStatus, Severity, Confidence,
    find_executable, run_command,
    analysis_tool
)

logger = __import__('logging').getLogger(__name__)

@analysis_tool
class ZapTool(BaseAnalysisTool):
    """OWASP ZAP (Zed Attack Proxy) security scanner integrated in dynamic container."""
    
    @property
    def name(self) -> str:
        return "zap"
    
    @property
    def display_name(self) -> str:
        return "OWASP ZAP"
    
    @property
    def description(self) -> str:
        return "Web application security scanner and penetration testing tool"
    
    @property
    def tags(self) -> Set[str]:
        return {"security", "web", "dynamic", "penetration_testing"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"web", "http", "html", "javascript"}
    
    def is_available(self) -> bool:
        """Check if ZAP functionality is available (via curl for basic security checks)."""
        return find_executable("curl") is not None
    
    def get_version(self) -> Optional[str]:
        """Get ZAP version."""
        try:
            # Check if ZAP daemon is running on standard port
            returncode, stdout, _ = run_command([
                "curl", "-s", "http://localhost:8090/JSON/core/view/version/"
            ], timeout=5)
            if returncode == 0 and stdout:
                data = json.loads(stdout)
                return data.get('version', 'unknown')
        except Exception as e:
            self.logger.debug(f"Failed to get ZAP version: {e}")
        return None
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run ZAP-style security analysis using curl and basic security checks."""
        start_time = time.time()
        
        try:
            # Get target URL from kwargs
            target_url = kwargs.get('target_url', 'http://localhost:5000')
            
            # Perform basic security scans using curl (ZAP-style)
            findings = []
            
            # 1. SSL/TLS Security Check
            ssl_findings = self._check_ssl_security(target_url)
            findings.extend(ssl_findings)
            
            # 2. HTTP Headers Security Check
            header_findings = self._check_security_headers(target_url)
            findings.extend(header_findings)
            
            # 3. Common Vulnerability Checks
            vuln_findings = self._check_common_vulnerabilities(target_url)
            findings.extend(vuln_findings)
            
            # 4. Information Disclosure Check
            info_findings = self._check_information_disclosure(target_url)
            findings.extend(info_findings)
            
            # Generate report
            report_path = target_path / "zap_style_report.json"
            report_data = {
                'target_url': target_url,
                'scan_type': 'ZAP-style security scan',
                'total_findings': len(findings),
                'timestamp': time.time(),
                'findings': [f.__dict__ for f in findings]
            }
            
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2)
            
            status = ToolStatus.SUCCESS.value
            if findings:
                status = ToolStatus.ISSUES_FOUND.value
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings[:self.config.max_issues],
                metadata={
                    'target_url': target_url,
                    'scan_type': 'ZAP-style security scan',
                    'report_path': str(report_path),
                    'checks_performed': ['ssl_security', 'security_headers', 'common_vulnerabilities', 'information_disclosure']
                },
                duration_seconds=time.time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"ZAP-style analysis failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=time.time() - start_time
            )
    
    def _check_ssl_security(self, target_url: str) -> List[Finding]:
        """Check SSL/TLS security configuration."""
        findings = []
        
        try:
            # Test SSL configuration
            cmd = ["curl", "-I", "--ssl-reqd", "--max-time", "10", target_url]
            returncode, stdout, stderr = run_command(cmd, timeout=15)
            
            if returncode != 0 and "SSL" in stderr:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    title="SSL/TLS Configuration Issue",
                    description="SSL/TLS connection failed or insecure configuration detected",
                    file_path=target_url,
                    category="ssl_security",
                    rule_id="ssl_001",
                    tags=['security', 'ssl', 'tls']
                ))
            
        except Exception as e:
            self.logger.warning(f"SSL security check failed: {e}")
        
        return findings
    
    def _check_security_headers(self, target_url: str) -> List[Finding]:
        """Check for missing security headers."""
        findings = []
        
        try:
            cmd = ["curl", "-I", "--max-time", "10", target_url]
            returncode, stdout, _ = run_command(cmd, timeout=15)
            
            if returncode == 0:
                headers = stdout.lower()
                
                # Check for missing security headers
                security_headers = {
                    'x-content-type-options': 'Missing X-Content-Type-Options header',
                    'x-frame-options': 'Missing X-Frame-Options header',
                    'content-security-policy': 'Missing Content-Security-Policy header',
                    'strict-transport-security': 'Missing Strict-Transport-Security header',
                    'x-xss-protection': 'Missing X-XSS-Protection header'
                }
                
                for header, description in security_headers.items():
                    if header not in headers:
                        findings.append(Finding(
                            tool=self.name,
                            severity=Severity.MEDIUM,
                            confidence=Confidence.HIGH,
                            title=f"Missing Security Header: {header}",
                            description=description,
                            file_path=target_url,
                            category="security_headers",
                            rule_id=f"header_{header.replace('-', '_')}",
                            tags=['security', 'headers']
                        ))
            
        except Exception as e:
            self.logger.warning(f"Security headers check failed: {e}")
        
        return findings
    
    def _check_common_vulnerabilities(self, target_url: str) -> List[Finding]:
        """Check for common web vulnerabilities."""
        findings = []
        
        try:
            # Check for common admin paths
            admin_paths = ['/admin', '/administrator', '/wp-admin', '/login', '/phpmyadmin']
            
            for path in admin_paths:
                test_url = target_url.rstrip('/') + path
                cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5", test_url]
                returncode, stdout, _ = run_command(cmd, timeout=10)
                
                if returncode == 0 and stdout.strip() in ['200', '301', '302']:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.LOW,
                        confidence=Confidence.MEDIUM,
                        title=f"Exposed Admin Path: {path}",
                        description=f"Admin path {path} is accessible and may expose sensitive functionality",
                        file_path=test_url,
                        category="information_disclosure",
                        rule_id="admin_path_exposure",
                        tags=['security', 'information_disclosure']
                    ))
            
            # Check for directory listing
            cmd = ["curl", "-s", "--max-time", "5", target_url]
            returncode, stdout, _ = run_command(cmd, timeout=10)
            
            if returncode == 0 and "index of" in stdout.lower():
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    title="Directory Listing Enabled",
                    description="Directory listing is enabled, which may expose sensitive files",
                    file_path=target_url,
                    category="information_disclosure",
                    rule_id="directory_listing",
                    tags=['security', 'information_disclosure']
                ))
            
        except Exception as e:
            self.logger.warning(f"Common vulnerabilities check failed: {e}")
        
        return findings
    
    def _check_information_disclosure(self, target_url: str) -> List[Finding]:
        """Check for information disclosure issues."""
        findings = []
        
        try:
            # Check server header for version information
            cmd = ["curl", "-I", "--max-time", "10", target_url]
            returncode, stdout, _ = run_command(cmd, timeout=15)
            
            if returncode == 0:
                server_match = re.search(r'server:\s*([^\r\n]+)', stdout, re.IGNORECASE)
                if server_match:
                    server_header = server_match.group(1)
                    # Check if version information is disclosed
                    if re.search(r'\d+\.\d+', server_header):
                        findings.append(Finding(
                            tool=self.name,
                            severity=Severity.LOW,
                            confidence=Confidence.MEDIUM,
                            title="Server Version Information Disclosure",
                            description=f"Server header discloses version information: {server_header}",
                            file_path=target_url,
                            category="information_disclosure",
                            rule_id="server_version_disclosure",
                            tags=['security', 'information_disclosure']
                        ))
                
                # Check for PHP version disclosure
                php_match = re.search(r'x-powered-by:\s*([^\r\n]+)', stdout, re.IGNORECASE)
                if php_match:
                    powered_by = php_match.group(1)
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.LOW,
                        confidence=Confidence.HIGH,
                        title="Technology Stack Information Disclosure",
                        description=f"X-Powered-By header discloses technology information: {powered_by}",
                        file_path=target_url,
                        category="information_disclosure",
                        rule_id="tech_stack_disclosure",
                        tags=['security', 'information_disclosure']
                    ))
            
        except Exception as e:
            self.logger.warning(f"Information disclosure check failed: {e}")
        
        return findings

@analysis_tool
class CurlTool(BaseAnalysisTool):
    """HTTP client tool for basic connectivity and response testing."""
    
    @property
    def name(self) -> str:
        return "curl"
    
    @property
    def display_name(self) -> str:
        return "cURL"
    
    @property
    def description(self) -> str:
        return "HTTP client for testing web endpoints and connectivity"
    
    @property
    def tags(self) -> Set[str]:
        return {"http", "connectivity", "web", "dynamic"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"web", "http"}
    
    def is_available(self) -> bool:
        """Check if curl is available."""
        return find_executable("curl") is not None
    
    def get_version(self) -> Optional[str]:
        """Get curl version."""
        try:
            returncode, stdout, _ = run_command(["curl", "--version"], timeout=10)
            if returncode == 0:
                match = re.search(r'curl\s+(\d+\.\d+\.\d+)', stdout)
                if match:
                    return match.group(1)
        except Exception as e:
            self.logger.debug(f"Failed to get curl version: {e}")
        return None
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run basic HTTP connectivity tests."""
        start_time = time.time()
        
        try:
            # Get target URL from kwargs
            target_url = kwargs.get('target_url', 'http://localhost:5000')
            
            findings = []
            metadata = {}
            
            # Test basic connectivity
            connectivity_result = self._test_connectivity(target_url)
            metadata['connectivity'] = connectivity_result
            
            # Test common endpoints
            endpoint_results = self._test_common_endpoints(target_url)
            metadata['endpoints'] = endpoint_results
            
            # Test security headers
            headers_result = self._test_security_headers(target_url)
            metadata['security_headers'] = headers_result
            
            # Analyze results for findings
            findings.extend(self._analyze_connectivity_results(connectivity_result, target_url))
            findings.extend(self._analyze_headers_results(headers_result, target_url))
            
            status = ToolStatus.SUCCESS.value
            if findings:
                status = ToolStatus.ISSUES_FOUND.value
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings[:self.config.max_issues],
                metadata=metadata,
                duration_seconds=time.time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"cURL analysis failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=time.time() - start_time
            )
    
    def _test_connectivity(self, url: str) -> Dict[str, Any]:
        """Test basic connectivity to URL."""
        try:
            returncode, stdout, stderr = run_command([
                "curl", "-s", "-w", 
                "response_code:%{response_code}\\ntime_total:%{time_total}\\ntime_connect:%{time_connect}",
                "-o", "/dev/null",
                url
            ], timeout=30)
            
            result = {
                'success': returncode == 0,
                'return_code': returncode,
                'stderr': stderr
            }
            
            if returncode == 0:
                # Parse curl output
                for line in stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        try:
                            result[key] = float(value) if '.' in value else int(value)
                        except ValueError:
                            result[key] = value
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_common_endpoints(self, base_url: str) -> Dict[str, Any]:
        """Test common endpoints."""
        endpoints = ['/', '/health', '/api', '/api/health', '/status']
        results = {}
        
        for endpoint in endpoints:
            url = base_url.rstrip('/') + endpoint
            try:
                returncode, _, _ = run_command([
                    "curl", "-s", "-w", "%{response_code}", "-o", "/dev/null", url
                ], timeout=10)
                
                results[endpoint] = {
                    'accessible': returncode == 0,
                    'return_code': returncode
                }
            except Exception as e:
                results[endpoint] = {
                    'accessible': False,
                    'error': str(e)
                }
        
        return results
    
    def _test_security_headers(self, url: str) -> Dict[str, Any]:
        """Test for security headers."""
        try:
            returncode, stdout, _ = run_command([
                "curl", "-s", "-I", url
            ], timeout=15)
            
            headers = {}
            if returncode == 0:
                for line in stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        headers[key.strip().lower()] = value.strip()
            
            # Check for important security headers
            security_headers = {
                'x-frame-options': headers.get('x-frame-options'),
                'x-content-type-options': headers.get('x-content-type-options'),
                'x-xss-protection': headers.get('x-xss-protection'),
                'strict-transport-security': headers.get('strict-transport-security'),
                'content-security-policy': headers.get('content-security-policy'),
                'referrer-policy': headers.get('referrer-policy')
            }
            
            return {
                'all_headers': headers,
                'security_headers': security_headers,
                'success': returncode == 0
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _analyze_connectivity_results(self, result: Dict[str, Any], url: str) -> List[Finding]:
        """Analyze connectivity results for issues."""
        findings = []
        
        if not result.get('success'):
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH.value,
                confidence=Confidence.HIGH.value,
                title="Connectivity failure",
                description=f"Unable to connect to {url}",
                file_path=url,
                category="connectivity",
                rule_id="connectivity_failure",
                tags=['connectivity', 'web', 'dynamic'],
                raw_data=result
            ))
        
        # Check response time
        time_total = result.get('time_total', 0)
        if time_total > 5.0:  # More than 5 seconds
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM.value,
                confidence=Confidence.HIGH.value,
                title="Slow response time",
                description=f"Response time of {time_total:.2f}s exceeds 5s threshold",
                file_path=url,
                category="performance",
                rule_id="slow_response",
                tags=['performance', 'web', 'dynamic'],
                raw_data=result
            ))
        
        return findings
    
    def _analyze_headers_results(self, result: Dict[str, Any], url: str) -> List[Finding]:
        """Analyze security headers for issues."""
        findings = []
        
        if not result.get('success'):
            return findings
        
        security_headers = result.get('security_headers', {})
        
        # Check for missing security headers
        missing_headers = []
        for header, value in security_headers.items():
            if not value:
                missing_headers.append(header)
        
        if missing_headers:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM.value,
                confidence=Confidence.HIGH.value,
                title="Missing security headers",
                description=f"Missing security headers: {', '.join(missing_headers)}",
                file_path=url,
                category="security_headers",
                rule_id="missing_security_headers",
                tags=['security', 'web', 'headers', 'dynamic'],
                raw_data=result
            ))
        
        return findings

@analysis_tool
class NmapTool(BaseAnalysisTool):
    """Network discovery and security auditing tool."""
    
    @property
    def name(self) -> str:
        return "nmap"
    
    @property
    def display_name(self) -> str:
        return "Nmap"
    
    @property
    def description(self) -> str:
        return "Network discovery and security auditing"
    
    @property
    def tags(self) -> Set[str]:
        return {"network", "security", "discovery", "dynamic"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"network", "tcp", "udp"}
    
    def is_available(self) -> bool:
        """Check if nmap is available."""
        return find_executable("nmap") is not None
    
    def get_version(self) -> Optional[str]:
        """Get nmap version."""
        try:
            returncode, stdout, _ = run_command(["nmap", "--version"], timeout=10)
            if returncode == 0:
                match = re.search(r'Nmap\s+(\d+\.\d+)', stdout)
                if match:
                    return match.group(1)
        except Exception as e:
            self.logger.debug(f"Failed to get nmap version: {e}")
        return None
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run basic network scan."""
        start_time = time.time()
        
        try:
            # Get target host from kwargs
            target_host = kwargs.get('target_host', 'localhost')
            
            # Run basic port scan
            command = [
                "nmap", "-sS", "-O", "-sV", 
                "--script=vuln",
                "-oX", str(target_path / "nmap_scan.xml"),
                target_host
            ]
            
            returncode, stdout, stderr = run_command(
                command,
                cwd=target_path,
                timeout=self.config.timeout,
                env=self.config.environment
            )
            
            findings = []
            metadata = {
                'target_host': target_host,
                'return_code': returncode,
                'command': ' '.join(command)
            }
            
            if returncode == 0:
                # Parse nmap output for findings
                findings = self._parse_nmap_output(stdout, target_host)
                status = ToolStatus.SUCCESS.value
                if findings:
                    status = ToolStatus.ISSUES_FOUND.value
            else:
                status = ToolStatus.ERROR.value
                return ToolResult(
                    tool_name=self.name,
                    status=status,
                    error=stderr or "Nmap execution failed",
                    output=stdout,
                    duration_seconds=time.time() - start_time
                )
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings[:self.config.max_issues],
                output=stdout,
                metadata=metadata,
                duration_seconds=time.time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"Nmap analysis failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=time.time() - start_time
            )
    
    def _parse_nmap_output(self, output: str, target_host: str) -> List[Finding]:
        """Parse nmap output for security findings."""
        findings = []
        
        try:
            lines = output.split('\n')
            open_ports = []
            
            for line in lines:
                # Look for open ports
                if '/tcp' in line and 'open' in line:
                    port_info = line.strip()
                    open_ports.append(port_info)
                
                # Look for vulnerability script results
                if '|' in line and ('VULNERABLE' in line or 'CVE' in line):
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.HIGH.value,
                        confidence=Confidence.MEDIUM.value,
                        title="Potential vulnerability detected",
                        description=line.strip(),
                        file_path=target_host,
                        category="network_vulnerability",
                        rule_id="nmap_vuln_script",
                        tags=['security', 'network', 'vulnerability', 'dynamic'],
                        raw_data={'line': line.strip()}
                    ))
            
            # Report open ports as informational findings
            if open_ports:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.INFO.value,
                    confidence=Confidence.HIGH.value,
                    title=f"Open ports detected on {target_host}",
                    description=f"Found {len(open_ports)} open ports: {', '.join(open_ports[:5])}",
                    file_path=target_host,
                    category="network_discovery",
                    rule_id="open_ports",
                    tags=['network', 'discovery', 'dynamic'],
                    raw_data={'ports': open_ports}
                ))
                
        except Exception as e:
            self.logger.warning(f"Failed to parse nmap output: {e}")
        
        return findings