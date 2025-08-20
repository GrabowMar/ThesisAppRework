#!/usr/bin/env python3
"""
Dynamic Analyzer Service - Web Application Security Scanner
==========================================================

A containerized dynamic security analysis service that performs:
- Connectivity testing
- Basic vulnerability scanning
- Response analysis

Usage:
    docker-compose up dynamic-analyzer

The service will start on ws://localhost:2002
"""

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime
from typing import Dict, List, Any
import websockets
from websockets.asyncio.server import serve

level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
level = getattr(logging, level_str, logging.INFO)
logging.basicConfig(level=level)
logger = logging.getLogger(__name__)
logger.setLevel(level)
try:
    logging.getLogger("websockets.server").setLevel(logging.CRITICAL)
    logging.getLogger("websockets.http").setLevel(logging.CRITICAL)
    logging.getLogger("websockets.http11").setLevel(logging.CRITICAL)
except Exception:
    pass

class DynamicAnalyzer:
    """Dynamic web application security analyzer."""
    
    def __init__(self):
        self.service_name = "dynamic-analyzer"
        self.version = "1.0.0"
        self.start_time = datetime.now()
        self.available_tools = self._check_available_tools()
    
    def _check_available_tools(self) -> List[str]:
        """Check which dynamic analysis tools are available."""
        tools = []
        
        # Check for curl
        try:
            result = subprocess.run(['curl', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('curl')
                logger.debug("curl available")
        except Exception as e:
            logger.debug(f"curl not available: {e}")
        
        # Check for wget
        try:
            result = subprocess.run(['wget', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('wget')
                logger.debug("wget available")
        except Exception as e:
            logger.debug(f"wget not available: {e}")
        
        # Check for nmap
        try:
            result = subprocess.run(['nmap', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('nmap')
                logger.debug("nmap available")
        except Exception as e:
            logger.debug(f"nmap not available: {e}")
        
        return tools
    
    async def test_connectivity(self, url: str) -> Dict[str, Any]:
        """Test connectivity and basic response analysis."""
        try:
            if 'curl' not in self.available_tools:
                return {'status': 'tool_unavailable', 'message': 'curl not available'}
            
            logger.info(f"Testing connectivity to {url}")
            
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
            
            logger.info(f"Port scanning {host}")
            
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
    
    async def analyze_running_app(self, model_slug: str, app_number: int, target_urls: List[str]) -> Dict[str, Any]:
        """Perform comprehensive dynamic analysis on running application."""
        try:
            logger.info(f"Dynamic analysis of {model_slug} app {app_number}")
            
            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'tools_used': self.available_tools.copy(),
                'target_urls': target_urls,
                'results': {}
            }
            
            # Test connectivity for all URLs
            connectivity_results = []
            for url in target_urls:
                conn_result = await self.test_connectivity(url)
                connectivity_results.append(conn_result)
            
            results['results']['connectivity'] = connectivity_results
            
            # Find reachable URLs
            reachable_urls = []
            for i, result in enumerate(connectivity_results):
                if result.get('status') == 'success' and result.get('analysis', {}).get('reachable'):
                    reachable_urls.append(target_urls[i])
            
            # Vulnerability scanning on reachable URLs
            if reachable_urls:
                vuln_results = []
                for url in reachable_urls[:2]:  # Limit to first 2 URLs
                    vuln_result = await self.scan_common_vulnerabilities(url)
                    vuln_result['url'] = url
                    vuln_results.append(vuln_result)
                
                results['results']['vulnerability_scan'] = vuln_results
            
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
                    port_scan_result = await self.port_scan(host, list(ports_to_scan))
                    results['results']['port_scan'] = port_scan_result
            
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
            logger.error(f"Dynamic analysis failed: {e}")
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
                
            elif msg_type == "dynamic_analyze":
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 1)
                target_urls = message_data.get("target_urls", [])
                
                if not target_urls:
                    # Generate default URLs based on app number
                    base_port = 6000 + (app_number * 10)
                    target_urls = [
                        f"http://localhost:{base_port}",
                        f"http://localhost:{base_port + 1}"
                    ]
                
                logger.info(f"Starting dynamic analysis for {model_slug} app {app_number}")
                
                analysis_results = await self.analyze_running_app(model_slug, app_number, target_urls)
                
                response = {
                    "type": "dynamic_analysis_result",
                    "status": "success",
                    "service": self.service_name,
                    "analysis": analysis_results,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(response))
                logger.info(f"Dynamic analysis completed for {model_slug} app {app_number}")
                
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
    analyzer = DynamicAnalyzer()
    client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.debug(f"New client connected: {client_addr}")
    
    try:
        async for message in websocket:
            try:
                message_data = json.loads(message)
                await analyzer.handle_message(websocket, message_data)
            except json.JSONDecodeError:
                logger.error("Invalid JSON message")
                
    except websockets.exceptions.ConnectionClosed:
        logger.debug(f"Client disconnected: {client_addr}")
    except Exception as e:
        logger.error(f"Error with client {client_addr}: {e}")

async def main():
    """Start the dynamic analyzer service."""
    host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
    port = int(os.getenv('WEBSOCKET_PORT', 2002))
    
    logger.info(f"Starting Dynamic Analyzer service on {host}:{port}")
    
    try:
        async with serve(handle_client, host, port):
            logger.info(f"Dynamic Analyzer listening on ws://{host}:{port}")
            logger.info("Service ready to accept connections")
            await asyncio.Future()
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
