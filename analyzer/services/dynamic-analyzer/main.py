#!/usr/bin/env python3
"""
Dynamic Analyzer Service - Web Application Security Scanner
==========================================================

Integrates OWASP ZAP for real security scanning along with connectivity
testing and port scanning capabilities.
"""

import asyncio
import json
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from analyzer.shared.service_base import BaseWSService
from analyzer.shared.tool_logger import ToolExecutionLogger
from sarif_parsers import parse_tool_output_to_sarif, build_sarif_document
from zap_scanner import ZAPScanner


class DynamicAnalyzer(BaseWSService):
    """Dynamic web application security analyzer with OWASP ZAP integration."""
    
    def __init__(self):
        super().__init__(service_name="dynamic-analyzer", default_port=2002, version="2.0.0")
        self._tool_runs: Dict[str, Dict[str, Any]] = {}
        self.zap_scanner: Optional[ZAPScanner] = None
        self._zap_started = False
        # Initialize tool execution logger for comprehensive output logging
        self.tool_logger = ToolExecutionLogger(self.log)

    def _record(self, tool: str, cmd: List[str], proc: subprocess.CompletedProcess, start: float):
        duration = time.time() - start
        
        # Use ToolExecutionLogger for comprehensive logging
        exec_record = self.tool_logger.log_command_complete(
            tool, cmd, proc, duration
        )
        
        entry = self._tool_runs.setdefault(tool, {
            'tool': tool,
            'status': 'success',
            'executed': True,
            'total_issues': 0,
            'commands': [],
            'duration_seconds': 0.0
        })
        if proc.returncode != 0 and entry['status'] == 'success':
            entry['status'] = 'error'
        entry['commands'].append({
            'cmd': cmd,
            'exit_code': proc.returncode,
            'duration': duration,
            'stdout': (proc.stdout or '')[:6000],
            'stderr': (proc.stderr or '')[:3000]
        })
        entry['duration_seconds'] += duration

    def _exec(self, tool: str, cmd: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
        # Log command start
        self.tool_logger.log_command_start(tool, cmd)
        
        start = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        self._record(tool, cmd, proc, start)
        return proc
    
    def _ensure_zap_started(self) -> bool:
        """Connect to the already-running ZAP daemon."""
        if self._zap_started and self.zap_scanner and self.zap_scanner.zap:
            return True
        
        try:
            self.log.info("Connecting to OWASP ZAP daemon...")
            self.zap_scanner = ZAPScanner()
            
            # ZAP is already running as a background service in the container
            # Just connect to it
            if self.zap_scanner.connect_to_zap():
                self._zap_started = True
                self.log.info("OWASP ZAP ready for scanning")
                return True
            else:
                self.log.error("Failed to connect to ZAP daemon")
                return False
        except Exception as e:
            self.log.error(f"Error connecting to ZAP: {e}")
            return False
    
    def _detect_available_tools(self) -> List[str]:
        """Detect which dynamic analysis tools are available."""
        tools = []
        
        # Check for curl
        try:
            result = subprocess.run(['curl', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('curl')
                self.log.debug("curl available")
        except Exception as e:
            self.log.debug(f"curl not available: {e}")
        
        # Check for nmap
        try:
            result = subprocess.run(['nmap', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('nmap')
                self.log.debug("nmap available")
        except Exception as e:
            self.log.debug(f"nmap not available: {e}")
        
        # ZAP is always "available" (will be started on demand)
        tools.append('zap')
        self.log.debug("OWASP ZAP available")
        
        return tools

    async def run_zap_scan(self, url: str, scan_type: str = 'baseline') -> Dict[str, Any]:
        """
        Run OWASP ZAP security scan on target URL.
        
        Args:
            url: Target URL to scan
            scan_type: Type of scan ('quick', 'baseline', 'full')
            
        Returns:
            ZAP scan results with alerts
        """
        try:
            # Ensure ZAP is running
            if not self._ensure_zap_started():
                return {
                    'status': 'error',
                    'error': 'Failed to start ZAP daemon',
                    'url': url
                }
            
            self.log.info(f"Running OWASP ZAP {scan_type} scan on {url}")
            
            # Run appropriate scan type
            if scan_type == 'full':
                # Thorough spider + Active scan
                self.log.info("Running full scan: thorough spider + active scan")
                spider_result = await asyncio.to_thread(
                    self.zap_scanner.spider_scan, url, max_depth=5, max_duration=180
                )
                scan_result = await asyncio.to_thread(
                    self.zap_scanner.active_scan, url, max_duration=300
                )
            elif scan_type == 'baseline':
                # Thorough spider + Passive scan (default for regular apps)
                self.log.info("Running baseline scan: thorough spider + passive scan with ZAP defaults")
                scan_result = await asyncio.to_thread(
                    self.zap_scanner.quick_scan, url, scan_type='baseline'
                )
            else:  # quick
                # Passive scan only
                self.log.info("Running quick scan: passive scan only")
                scan_result = await asyncio.to_thread(
                    self.zap_scanner.quick_scan, url, scan_type='quick'
                )
            
            if scan_result.get('status') == 'success':
                # Get alerts grouped by risk
                alerts_by_risk = await asyncio.to_thread(
                    self.zap_scanner.get_alerts_by_risk, url
                )
                
                total_alerts = sum(len(alerts) for alerts in alerts_by_risk.values())
                
                self.log.info(f"ZAP scan completed. Found {total_alerts} alerts "
                            f"(High: {len(alerts_by_risk['High'])}, "
                            f"Medium: {len(alerts_by_risk['Medium'])}, "
                            f"Low: {len(alerts_by_risk['Low'])})")
                
                return {
                    'status': 'success',
                    'url': url,
                    'scan_type': scan_type,
                    'total_alerts': total_alerts,
                    'alerts_by_risk': alerts_by_risk,
                    'all_alerts': scan_result.get('alerts', [])
                }
            else:
                return scan_result
                
        except Exception as e:
            self.log.error(f"ZAP scan failed for {url}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'url': url
            }
            result = self._exec('curl', cmd, timeout=15)
            
            if result.returncode != 0 and 'SSL' in result.stderr:
                vulnerabilities.append({
                    'type': 'SSL/TLS Configuration Issue',
                    'severity': 'medium',
                    'description': 'SSL/TLS connection failed or insecure configuration detected',
                    'recommendation': 'Review SSL/TLS configuration and ensure proper certificates'
                })
            
        except Exception as e:
            self.log.warning(f"SSL security check failed: {e}")
        
        return {'vulnerabilities': vulnerabilities}
    
    async def _check_security_headers(self, url: str) -> Dict[str, Any]:
        """Check for missing security headers."""
        vulnerabilities = []
        
        try:
            cmd = ['curl', '-I', '--max-time', '10', url]
            result = self._exec('curl', cmd, timeout=15)
            
            if result.returncode == 0:
                headers = result.stdout.lower()
                
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
                        vulnerabilities.append({
                            'type': f'Missing Security Header: {header}',
                            'severity': 'medium',
                            'description': description,
                            'recommendation': f'Add {header} header to improve security'
                        })
            
        except Exception as e:
            self.log.warning(f"Security headers check failed: {e}")
        
        return {'vulnerabilities': vulnerabilities}
    
    async def _check_common_vulnerabilities(self, url: str) -> Dict[str, Any]:
        """Check for common web vulnerabilities."""
        vulnerabilities = []
        
        try:
            # Check for common admin paths
            admin_paths = ['/admin', '/administrator', '/wp-admin', '/login', '/phpmyadmin']
            
            for path in admin_paths:
                test_url = url.rstrip('/') + path
                cmd = ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', '5', test_url]
                result = self._exec('curl', cmd, timeout=10)
                
                if result.returncode == 0 and result.stdout.strip() in ['200', '301', '302']:
                    vulnerabilities.append({
                        'type': f'Exposed Admin Path: {path}',
                        'severity': 'low',
                        'description': f'Admin path {path} is accessible and may expose sensitive functionality',
                        'recommendation': 'Restrict access to admin paths or implement proper authentication'
                    })
            
            # Check for directory listing
            cmd = ['curl', '-s', '--max-time', '5', url]
            result = self._exec('curl', cmd, timeout=10)
            
            if result.returncode == 0 and 'index of' in result.stdout.lower():
                vulnerabilities.append({
                    'type': 'Directory Listing Enabled',
                    'severity': 'medium',
                    'description': 'Directory listing is enabled, which may expose sensitive files',
                    'recommendation': 'Disable directory listing on the web server'
                })
            
        except Exception as e:
            self.log.warning(f"Common vulnerabilities check failed: {e}")
        
        return {'vulnerabilities': vulnerabilities}
    
    async def _check_information_disclosure(self, url: str) -> Dict[str, Any]:
        """Check for information disclosure issues."""
        vulnerabilities = []
        
        try:
            # Check server header for version information
            cmd = ['curl', '-I', '--max-time', '10', url]
            result = self._exec('curl', cmd, timeout=15)
            
            if result.returncode == 0:
                import re
                server_match = re.search(r'server:\s*([^\r\n]+)', result.stdout, re.IGNORECASE)
                if server_match:
                    server_header = server_match.group(1)
                    # Check if version information is disclosed
                    if re.search(r'\d+\.\d+', server_header):
                        vulnerabilities.append({
                            'type': 'Server Version Information Disclosure',
                            'severity': 'low',
                            'description': f'Server header discloses version information: {server_header}',
                            'recommendation': 'Configure server to not disclose version information'
                        })
                
                # Check for PHP version disclosure
                php_match = re.search(r'x-powered-by:\s*([^\r\n]+)', result.stdout, re.IGNORECASE)
                if php_match:
                    powered_by = php_match.group(1)
                    vulnerabilities.append({
                        'type': 'Technology Stack Information Disclosure',
                        'severity': 'low',
                        'description': f'X-Powered-By header discloses technology information: {powered_by}',
                        'recommendation': 'Configure server to not disclose technology stack information'
                    })
            
        except Exception as e:
            self.log.warning(f"Information disclosure check failed: {e}")
        
        return {'vulnerabilities': vulnerabilities}
    
    async def test_connectivity(self, url: str) -> Dict[str, Any]:
        """Test connectivity and basic response analysis."""
        try:
            if 'curl' not in self.available_tools:
                return {'status': 'tool_unavailable', 'message': 'curl not available'}
            
            self.log.info(f"Testing connectivity to {url}")
            
            # Basic connectivity test
            cmd = ['curl', '-I', '--connect-timeout', '10', '--max-time', '30', url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
            
            analysis = {
                'url': url,
                'reachable': result.returncode == 0,
                'curl_exit_code': result.returncode
            }
            
            if result.returncode == 0:
                headers = result.stdout.split('\n')
                status_line = headers[0] if headers else ''
                
                # Extract status code
                status_code = None
                if 'HTTP/' in status_line:
                    parts = status_line.split()
                    if len(parts) >= 2:
                        try:
                            status_code = int(parts[1])
                        except ValueError:
                            pass
                
                # Analyze headers for security
                security_headers = {
                    'x-frame-options': False,
                    'x-content-type-options': False,
                    'strict-transport-security': False,
                    'content-security-policy': False,
                    'x-xss-protection': False
                }
                
                for header in headers:
                    header_lower = header.lower()
                    for sec_header in security_headers:
                        if sec_header in header_lower:
                            security_headers[sec_header] = True
                
                analysis.update({
                    'status_code': status_code,
                    'status_line': status_line.strip(),
                    'security_headers': security_headers,
                    'security_score': sum(security_headers.values()),
                    'total_security_headers': len(security_headers)
                })
            else:
                analysis['error'] = result.stderr.strip()
            
            return {'status': 'success', 'analysis': analysis}
            
        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'analysis': {'url': url, 'reachable': False, 'error': 'Connection timeout'}
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def scan_common_vulnerabilities(self, url: str) -> Dict[str, Any]:
        """Scan for common web vulnerabilities."""
        try:
            vulnerabilities = []
            
            # Test for common paths
            common_paths = [
                '/admin', '/login', '/wp-admin', '/phpmyadmin',
                '/.git', '/.env', '/config', '/backup'
            ]
            
            accessible_paths = []
            
            if 'curl' in self.available_tools:
                for path in common_paths:
                    test_url = url.rstrip('/') + path
                    try:
                        cmd = ['curl', '-I', '--connect-timeout', '5', '--max-time', '10', test_url]
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                        
                        if result.returncode == 0 and result.stdout:
                            status_line = result.stdout.split('\n')[0]
                            if '200' in status_line or '301' in status_line or '302' in status_line:
                                accessible_paths.append({
                                    'path': path,
                                    'url': test_url,
                                    'status': status_line.strip()
                                })
                    except Exception:
                        continue
            
            # Check for exposed files
            if accessible_paths:
                vulnerabilities.append({
                    'type': 'exposed_paths',
                    'severity': 'medium',
                    'description': 'Potentially sensitive paths are accessible',
                    'paths': accessible_paths
                })
            
            return {
                'status': 'success',
                'vulnerabilities': vulnerabilities,
                'total_vulnerabilities': len(vulnerabilities)
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def port_scan(self, host: str, ports: List[int]) -> Dict[str, Any]:
        """Perform basic port scanning."""
        try:
            if 'nmap' not in self.available_tools:
                # Fallback to basic connectivity test
                return await self._basic_port_check(host, ports)
            
            self.log.info(f"Port scanning {host}")
            
            port_list = ','.join(map(str, ports))
            cmd = ['nmap', '-p', port_list, '--open', '-T4', host]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                open_ports = []
                lines = result.stdout.split('\n')
                
                for line in lines:
                    if '/tcp' in line and 'open' in line:
                        parts = line.split()
                        if parts:
                            port_info = parts[0]
                            port_num = port_info.split('/')[0]
                            try:
                                open_ports.append(int(port_num))
                            except ValueError:
                                pass
                
                return {
                    'status': 'success',
                    'host': host,
                    'scanned_ports': ports,
                    'open_ports': open_ports,
                    'total_open': len(open_ports)
                }
            else:
                return {'status': 'error', 'error': result.stderr}
                
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'error': 'Port scan timed out'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _basic_port_check(self, host: str, ports: List[int]) -> Dict[str, Any]:
        """Basic port connectivity check without nmap."""
        open_ports = []
        
        for port in ports:
            try:
                # Use netcat or similar if available
                cmd = ['curl', '--connect-timeout', '2', f'http://{host}:{port}']
                result = self._exec('curl', cmd, timeout=5)
                
                # If curl doesn't immediately fail, port might be open
                if result.returncode != 7:  # 7 = couldn't connect
                    open_ports.append(port)
                    
            except Exception:
                continue
        
        return {
            'status': 'success',
            'host': host,
            'scanned_ports': ports,
            'open_ports': open_ports,
            'total_open': len(open_ports),
            'method': 'basic_check'
        }
    
    async def analyze_running_app(self, model_slug: str, app_number: int, target_urls: List[str], selected_tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Perform comprehensive dynamic analysis on running application."""
        try:
            self.log.info("═" * 80)
            self.log.info(f"🌐 DYNAMIC ANALYSIS: {model_slug} app {app_number}")
            self.log.info(f"   🎯 Targets: {', '.join(target_urls)}")
            self.log.info("═" * 80)
            
            # Normalize tool selection to lowercase set
            selected_set = {t.lower() for t in selected_tools} if selected_tools else None

            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'tools_used': [],
                'target_urls': target_urls,
                'results': {}
            }

            # Collect per-tool raw execution details (stdout/stderr/commands)
            # Reset tool run state
            self._tool_runs = {}
            tool_runs: Dict[str, Dict[str, Any]] = self._tool_runs

            def record_tool_command(tool: str, cmd: List[str], proc: subprocess.CompletedProcess, start_ts: float):
                """Record a single command invocation under tool_runs."""
                duration = time.time() - start_ts
                entry = tool_runs.setdefault(tool, {
                    'tool': tool,
                    'status': 'success',
                    'executed': True,
                    'total_issues': 0,
                    'commands': []
                })
                # Update status if command failed
                if proc.returncode != 0 and entry.get('status') == 'success':
                    entry['status'] = 'error'
                entry['commands'].append({
                    'cmd': cmd,
                    'exit_code': proc.returncode,
                    'duration': duration,
                    'stdout': (proc.stdout or '')[:8000],
                    'stderr': (proc.stderr or '')[:4000]
                })
                # Track cumulative duration
                entry['duration_seconds'] = entry.get('duration_seconds', 0.0) + duration
            
            # Test connectivity for all URLs
            connectivity_results = []
            tool_summary: Dict[str, Dict[str, Any]] = {}
            
            self.log.info("═" * 80)
            self.log.info("🔌 CONNECTIVITY TEST PHASE")
            self.log.info("═" * 80)
            
            if selected_set is None or 'curl' in selected_set:
                for url in target_urls:
                    # Wrap connectivity curl usage capturing raw output
                    conn_result = await self.test_connectivity(url)
                    connectivity_results.append(conn_result)
                # Mark curl as used if we executed connectivity checks
                if connectivity_results:
                    results['tools_used'].append('curl')
                
                # Determine status and error
                curl_status = 'success' if any(r.get('status') == 'success' for r in connectivity_results) else 'error'
                curl_error = None
                if curl_status == 'error' and connectivity_results:
                     # Pick the first error
                     curl_error = connectivity_results[0].get('error') or connectivity_results[0].get('analysis', {}).get('error')

                tool_summary['curl'] = {
                    'tool': 'curl',
                    'status': curl_status,
                    'executed': True if connectivity_results else False,
                    'total_issues': 1 if curl_status == 'error' else 0,
                    'error': curl_error
                }
            else:
                self.log.info("Skipping connectivity tests due to tool selection gating (curl not selected)")
            
            results['results']['connectivity'] = connectivity_results
            
            # Find reachable URLs
            reachable_urls = []
            for i, result in enumerate(connectivity_results):
                if result.get('status') == 'success' and result.get('analysis', {}).get('reachable'):
                    reachable_urls.append(target_urls[i])

            # If we skipped connectivity checks, attempt vulnerability scanning on provided targets
            if not connectivity_results and target_urls:
                reachable_urls = list(target_urls)
            
            # Vulnerability scanning on reachable URLs
            if reachable_urls and (selected_set is None or 'curl' in selected_set):
                vuln_results = []
                for url in reachable_urls[:2]:  # Limit to first 2 URLs
                    vuln_result = await self.scan_common_vulnerabilities(url)
                    vuln_result['url'] = url
                    vuln_results.append(vuln_result)
                
                results['results']['vulnerability_scan'] = vuln_results
                results['tools_used'] = list(set(results['tools_used'] + ['curl']))
                # Treat findings count as issues for curl tool
                issue_count = sum(v.get('total_vulnerabilities', 0) for v in vuln_results if isinstance(v, dict))
                tool_summary['curl']['total_issues'] = issue_count
            
            # Port scanning
            if target_urls:
                # Extract hosts and ports from URLs
                hosts_to_scan = set()
                ports_to_scan = set()
                
                for url in target_urls:
                    try:
                        if '://' in url:
                            host_part = url.split('://')[1].split('/')[0]
                            if ':' in host_part:
                                host, port = host_part.split(':')
                                hosts_to_scan.add(host)
                                ports_to_scan.add(int(port))
                            else:
                                hosts_to_scan.add(host_part)
                    except Exception:
                        continue
                
                # Add common ports
                ports_to_scan.update([80, 443, 8080, 3000, 5000, 8000])
                
                if hosts_to_scan and ports_to_scan:
                    host = list(hosts_to_scan)[0]  # Scan first host
                    # Tool gating: prefer nmap; otherwise allow basic curl-based check if curl selected
                    if selected_set is None or 'nmap' in selected_set:
                        port_scan_result = await self.port_scan(host, list(ports_to_scan))
                        results['results']['port_scan'] = port_scan_result
                        results['tools_used'] = list(set(results['tools_used'] + ['nmap']))
                        
                        nmap_status = port_scan_result.get('status','error')
                        tool_summary['nmap'] = {
                            'tool': 'nmap',
                            'status': nmap_status,
                            'executed': True,
                            'total_issues': 1 if nmap_status == 'error' else 0,
                            'error': port_scan_result.get('error')
                        }
                    elif 'curl' in (selected_set or set()):
                        # Fallback to basic check
                        port_scan_result = await self._basic_port_check(host, list(ports_to_scan))
                        results['results']['port_scan'] = port_scan_result
                        results['tools_used'] = list(set(results['tools_used'] + ['curl']))
                        # augment curl summary
                        tool_summary.setdefault('curl', {'tool':'curl','status':'success','executed':True,'total_issues':0})

            # OWASP ZAP security scanning - real implementation
            if (selected_set is None or 'zap' in selected_set):
                self.log.info("═" * 80)
                self.log.info("🔒 OWASP ZAP SECURITY SCAN PHASE")
                self.log.info("═" * 80)
                
                # Use reachable URLs if available, otherwise use all target URLs for ZAP
                zap_target_urls = reachable_urls if reachable_urls else target_urls
                if zap_target_urls:
                    zap_results = []
                    for url in zap_target_urls[:2]:  # Limit to first 2 URLs
                        # Run baseline scan (spider + passive)
                        zap_result = await self.run_zap_scan(url, scan_type='baseline')
                        zap_results.append(zap_result)
                    
                    results['results']['zap_security_scan'] = zap_results
                    results['tools_used'] = list(set(results['tools_used'] + ['zap']))
                    
                    zap_status = 'success' if any(r.get('status') == 'success' for r in zap_results) else 'error'
                    zap_error = None
                    if zap_status == 'error' and zap_results:
                        zap_error = zap_results[0].get('error')

                    tool_summary['zap'] = {
                        'tool': 'zap',
                        'status': zap_status,
                        'executed': True,
                        'total_issues': sum(z.get('total_alerts', 0) for z in zap_results) + (1 if zap_status == 'error' else 0),
                        'error': zap_error
                    }
                    
                    # Generate SARIF output for ZAP results
                    zap_sarif_runs = []
                    for zap_result in zap_results:
                        if zap_result.get('status') == 'success':
                            # ZAP alerts are already in ZAP format
                            all_alerts = zap_result.get('all_alerts', [])
                            sarif_input = {'alerts': all_alerts}
                            
                            sarif_run = parse_tool_output_to_sarif('zap', sarif_input)
                            if sarif_run:
                                zap_sarif_runs.append(sarif_run)
                                self.log.debug(f"Generated SARIF output for ZAP scan of {zap_result.get('url')}")
                    
                    if zap_sarif_runs:
                        results['sarif_export'] = build_sarif_document(zap_sarif_runs)
                        self.log.info(f"Generated SARIF document with {len(zap_sarif_runs)} ZAP runs")
                else:
                    tool_summary['zap'] = {'tool':'zap','status':'skipped','executed':False,'total_issues':0}
            else:
                if 'zap' in (selected_set or set()):
                    tool_summary['zap'] = {'tool':'zap','status':'not_available','executed':False,'total_issues':0}

            # Mark unavailable tools explicitly if selected but missing
            for candidate in ['curl','nmap','zap']:
                if selected_set and candidate in selected_set and candidate not in tool_summary:
                    tool_summary[candidate] = {'tool': candidate, 'status': 'not_available', 'executed': False, 'total_issues': 0}

            # Merge summary issue counts into tool_runs baseline entries
            for tname, summary in tool_summary.items():
                tr = tool_runs.setdefault(tname, {
                    'tool': tname,
                    'status': summary.get('status','success'),
                    'executed': summary.get('executed', True),
                    'total_issues': summary.get('total_issues', 0),
                    'commands': []
                })
                # Keep the worst status if conflicts
                if tr.get('status') == 'success' and summary.get('status') != 'success':
                    tr['status'] = summary.get('status')
                tr['total_issues'] = summary.get('total_issues', tr.get('total_issues', 0))
                if summary.get('error'):
                    tr['error'] = summary.get('error')

            # Attach detailed tool runs inside results for aggregator discovery
            if tool_runs:
                results['results']['tool_runs'] = tool_runs
            results['tool_results'] = tool_summary
            
            # Focus on basic network tools: curl, wget, nmap, and ZAP-style security scanning
            # Advanced security scanning would require additional specialized tools
            
            # Calculate summary
            total_vulnerabilities = 0
            reachable_count = len(reachable_urls)
            
            if 'vulnerability_scan' in results['results']:
                for vuln_result in results['results']['vulnerability_scan']:
                    if vuln_result.get('status') == 'success':
                        total_vulnerabilities += vuln_result.get('total_vulnerabilities', 0)
            
            results['summary'] = {
                'total_urls_tested': len(target_urls),
                'reachable_urls': reachable_count,
                'vulnerabilities_found': total_vulnerabilities,
                'analysis_status': 'completed'
            }
            
            # Log completion summary
            self.log.info("═" * 80)
            self.log.info(f"✅ DYNAMIC ANALYSIS COMPLETE")
            self.log.info(f"   🎯 URLs Tested: {len(target_urls)}")
            self.log.info(f"   ✅ Reachable: {reachable_count}")
            self.log.info(f"   ⚠️  Vulnerabilities: {total_vulnerabilities}")
            self.log.info("═" * 80)
            
            return results
            
        except Exception as e:
            self.log.error(f"Dynamic analysis failed: {e}")
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
            if msg_type == "dynamic_analyze":
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 1)
                target_urls = message_data.get("target_urls", [])
                # Tool selection normalized
                selected_tools = list(self.extract_selected_tools(message_data) or [])

                if not target_urls:
                    # Generate default URLs based on app number
                    base_port = 6000 + (app_number * 10)
                    target_urls = [
                        f"http://localhost:{base_port}",
                        f"http://localhost:{base_port + 1}"
                    ]
                    self.log.info(f"No target_urls supplied; using default heuristic ports {target_urls}")
                else:
                    self.log.info(f"Received explicit target_urls: {target_urls}")

                self.log.info(f"Starting dynamic analysis for {model_slug} app {app_number}")
                await self.send_progress('starting', f"Starting dynamic analysis for {model_slug} app {app_number}",
                                         model_slug=model_slug, app_number=app_number)

                analysis_results = await self.analyze_running_app(model_slug, app_number, target_urls, selected_tools)

                response = {
                    "type": "dynamic_analysis_result",
                    "status": "success",
                    "service": self.info.name,
                    "analysis": analysis_results,
                    "timestamp": datetime.now().isoformat()
                }

                await websocket.send(json.dumps(response))
                self.log.info(f"Dynamic analysis completed for {model_slug} app {app_number}")
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
                await websocket.send(json.dumps(response))
            except Exception:
                pass
    
    async def cleanup(self):
        """Cleanup resources when service stops."""
        # ZAP runs persistently in the container, no need to stop it
        if self.zap_scanner:
            self.log.info("Disconnecting from OWASP ZAP daemon...")
            self.zap_scanner.zap = None

async def main():
    service = DynamicAnalyzer()
    try:
        await service.run()
    finally:
        await service.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
