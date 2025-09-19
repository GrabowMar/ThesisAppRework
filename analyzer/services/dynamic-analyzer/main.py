#!/usr/bin/env python3
"""
Dynamic Analyzer Service - Web Application Security Scanner
==========================================================

Refactored to use BaseWSService with strict tool selection gating.
"""

import asyncio
import json
import os
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional

from analyzer.shared.service_base import BaseWSService


class DynamicAnalyzer(BaseWSService):
    """Dynamic web application security analyzer."""
    
    def __init__(self):
        super().__init__(service_name="dynamic-analyzer", default_port=2002, version="1.0.0")
    
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
        
        # Check for wget
        try:
            result = subprocess.run(['wget', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('wget')
                self.log.debug("wget available")
        except Exception as e:
            self.log.debug(f"wget not available: {e}")
        
        # Check for nmap
        try:
            result = subprocess.run(['nmap', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('nmap')
                self.log.debug("nmap available")
        except Exception as e:
            self.log.debug(f"nmap not available: {e}")
        # Check for OWASP ZAP (Python client import + optional running daemon)
        try:
            __import__('zapv2')  # type: ignore
            tools.append('zap')
            self.log.debug("ZAP client library available")
        except Exception as e:
            self.log.debug(f"ZAP client not available: {e}")
        
        return tools
    
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
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                
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
            self.log.info(f"Dynamic analysis of {model_slug} app {app_number}")
            
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
            
            # Test connectivity for all URLs
            connectivity_results = []
            if selected_set is None or 'curl' in selected_set:
                for url in target_urls:
                    conn_result = await self.test_connectivity(url)
                    connectivity_results.append(conn_result)
                # Mark curl as used if we executed connectivity checks
                if connectivity_results:
                    results['tools_used'].append('curl')
            else:
                self.log.info("Skipping connectivity tests due to tool selection gating (curl not selected)")
            
            results['results']['connectivity'] = connectivity_results
            
            # Find reachable URLs
            reachable_urls = []
            for i, result in enumerate(connectivity_results):
                if result.get('status') == 'success' and result.get('analysis', {}).get('reachable'):
                    reachable_urls.append(target_urls[i])

            # If only ZAP was selected and we skipped connectivity, still attempt ZAP on provided targets
            if (selected_set is not None and 'zap' in selected_set) and not connectivity_results:
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
                    elif 'curl' in (selected_set or set()):
                        # Fallback to basic check
                        port_scan_result = await self._basic_port_check(host, list(ports_to_scan))
                        results['results']['port_scan'] = port_scan_result
                        results['tools_used'] = list(set(results['tools_used'] + ['curl']))

            # Optional OWASP ZAP scan (only if zap available & at least one reachable URL)
            if 'zap' in self.available_tools and reachable_urls and (selected_set is None or 'zap' in selected_set):
                primary_url = reachable_urls[0]
                self.log.info(f"Attempting ZAP scan for {primary_url}")
                zap_result = await self.zap_scan(primary_url)
                results['results']['zap_scan'] = zap_result
                results['tools_used'] = list(set(results['tools_used'] + ['zap']))
            
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
            
            return results
            
        except Exception as e:
            self.log.error(f"Dynamic analysis failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'model_slug': model_slug,
                'app_number': app_number
            }

    async def zap_scan(self, target: str) -> Dict[str, Any]:
        """Run a lightweight OWASP ZAP spider + passive scan using ZAP's HTTP API (async).

        Keeps total time bounded so the manager (default 180s) doesn't time out.
        """
        if 'zap' not in self.available_tools:
            return {'status': 'tool_unavailable', 'tool': 'zap'}

        import aiohttp

        zap_port = os.getenv('ZAP_PORT', '8090')
        zap_host = os.getenv('ZAP_HOST', 'localhost')
        zap_api = os.getenv('ZAP_API_KEY', '')
        base_url = f'http://{zap_host}:{zap_port}'

        def _params(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            p: Dict[str, Any] = {}
            if zap_api:
                p['apikey'] = zap_api
            if extra:
                p.update(extra)
            return p

        timeout = aiohttp.ClientTimeout(total=20)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Quick connectivity check
                async with session.get(f"{base_url}/JSON/core/view/version/", params=_params()) as r:
                    if r.status != 200:
                        return {'status': 'unreachable', 'tool': 'zap', 'message': f'No ZAP daemon at {base_url} (HTTP {r.status})'}
                    try:
                        _ = (await r.json()).get('version')
                    except Exception:
                        return {'status': 'unreachable', 'tool': 'zap', 'message': f'Invalid response from {base_url}'}

                # Start spider (recurse=true)
                async with session.get(f"{base_url}/JSON/spider/action/scan/", params=_params({'url': target, 'recurse': 'true'})) as s:
                    data = await s.json()
                    spider_id = data.get('scan') if s.status == 200 else None
                if spider_id is None:
                    return {'status': 'error', 'tool': 'zap', 'error': f'Failed to start spider: HTTP {s.status}'}

                # Wait for spider to reach 100% (cap at ~45s)
                spider_deadline = __import__('time').time() + 45
                while __import__('time').time() < spider_deadline:
                    async with session.get(f"{base_url}/JSON/spider/view/status/", params=_params({'scanId': spider_id})) as st:
                        try:
                            pct = int((await st.json()).get('status', 0))
                        except Exception:
                            pct = 0
                    if pct >= 100:
                        break
                    await asyncio.sleep(2)

                # Wait briefly for passive scanner to drain (cap at ~30s)
                pscan_deadline = __import__('time').time() + 30
                while __import__('time').time() < pscan_deadline:
                    async with session.get(f"{base_url}/JSON/pscan/view/recordsToScan/", params=_params()) as p:
                        try:
                            remaining = int((await p.json()).get('recordsToScan', 0))
                        except Exception:
                            remaining = 0
                    if remaining == 0:
                        break
                    await asyncio.sleep(2)

                # Skip active scan by default to keep runtime bounded
                active_result: Dict[str, Any] = {'status': 'skipped', 'reason': 'disabled_by_default'}

                # Fetch alerts for the target
                async with session.get(f"{base_url}/JSON/core/view/alerts/", params=_params({'baseurl': target})) as ar:
                    alerts_obj = await ar.json()
                    alerts_list = alerts_obj.get('alerts', []) if isinstance(alerts_obj, dict) else []

            severity_count = {'High': 0, 'Medium': 0, 'Low': 0, 'Informational': 0}
            for a in alerts_list:
                risk = a.get('risk', '')
                if risk in severity_count:
                    severity_count[risk] += 1

            return {
                'status': 'success',
                'tool': 'zap',
                'target': target,
                'alert_counts': severity_count,
                'total_alerts': len(alerts_list),
                'active_scan': active_result,
                'alerts_sample': alerts_list[:25]
            }
        except Exception as e:
            return {'status': 'error', 'tool': 'zap', 'error': str(e)}

    async def _await_condition(self, predicate, timeout: int = 60, sleep: int = 1):
        """Utility: await predicate True or timeout."""
        start = datetime.now()
        while (datetime.now() - start).total_seconds() < timeout:
            try:
                if predicate():
                    return True
            except Exception:
                pass
            await asyncio.sleep(sleep)
        raise asyncio.TimeoutError('Condition wait timed out')
    
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
                await websocket.send(json.dumps(error_response))
            except Exception:
                pass

async def main():
    service = DynamicAnalyzer()
    await service.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
