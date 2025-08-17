#!/usr/bin/env python3
"""
Performance Tester Service - Load Testing and Performance Analysis
==================================================================

A containerized performance testing service that performs:
- Load testing with concurrent requests
- Response time analysis
- Throughput measurement
- Resource usage monitoring

Usage:
    docker-compose up performance-tester

The service will start on ws://localhost:2003
"""

import asyncio
import json
import logging
import os
import subprocess
import statistics
from datetime import datetime
from typing import Dict, List, Any, Optional
import websockets
from websockets import connect as ws_connect
from websockets.asyncio.server import serve
import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceTester:
    """Performance testing service for web applications."""
    
    def __init__(self):
        self.service_name = "performance-tester"
        self.version = "1.0.0"
        self.start_time = datetime.now()
        self.available_tools = self._check_available_tools()
    
    def _check_available_tools(self) -> List[str]:
        """Check which performance testing tools are available."""
        tools = []
        
        # Check for curl (basic)
        try:
            result = subprocess.run(['curl', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('curl')
                logger.info("✅ curl available")
        except Exception as e:
            logger.warning(f"❌ curl not available: {e}")
        
        # Check for ab (Apache Bench)
        try:
            result = subprocess.run(['ab', '-V'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('ab')
                logger.info("✅ Apache Bench (ab) available")
        except Exception as e:
            logger.warning(f"❌ Apache Bench not available: {e}")
        
        # Check for wget
        try:
            result = subprocess.run(['wget', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('wget')
                logger.info("✅ wget available")
        except Exception as e:
            logger.warning(f"❌ wget not available: {e}")
        
        # Always available - built-in aiohttp
        tools.append('aiohttp')
        logger.info("✅ aiohttp available (built-in)")
        
        return tools

    async def _progress(self, stage: str, message: str = "", analysis_id: Optional[str] = None, **kwargs):
        """Send a PROGRESS_UPDATE to the gateway if configured."""
        gw = os.getenv('GATEWAY_URL', 'ws://localhost:8765')
        try:
            payload = {
                'type': 'progress_update',
                'correlation_id': analysis_id or kwargs.get('analysis_id') or '',
                'stage': stage,
                'message': message,
                'service': self.service_name,
                'data': {
                    'stage': stage,
                    'message': message,
                    **kwargs
                }
            }
            async with ws_connect(gw, open_timeout=1, close_timeout=1, ping_interval=None) as ws:
                await ws.send(json.dumps(payload))
        except Exception:
            pass
    
    async def measure_response_time(self, url: str, num_requests: int = 10) -> Dict[str, Any]:
        """Measure response times using aiohttp."""
        try:
            logger.info(f"Measuring response time for {url} ({num_requests} requests)")
            await self._progress('measuring', f'Measuring response time: {url}', url=url, requests=num_requests)
            
            response_times = []
            successful_requests = 0
            failed_requests = 0
            status_codes = []
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                for i in range(num_requests):
                    try:
                        start_time = datetime.now()
                        async with session.get(url) as response:
                            await response.read()  # Read the response body
                            end_time = datetime.now()
                            
                            response_time = (end_time - start_time).total_seconds() * 1000  # milliseconds
                            response_times.append(response_time)
                            status_codes.append(response.status)
                            successful_requests += 1
                            
                    except Exception as e:
                        failed_requests += 1
                        logger.debug(f"Request {i+1} failed: {e}")
            
            if response_times:
                await self._progress('measured', f'Response time measured: {url}', url=url,
                                     avg_ms=statistics.mean(response_times))
                return {
                    'status': 'success',
                    'url': url,
                    'total_requests': num_requests,
                    'successful_requests': successful_requests,
                    'failed_requests': failed_requests,
                    'response_times': {
                        'min': min(response_times),
                        'max': max(response_times),
                        'avg': statistics.mean(response_times),
                        'median': statistics.median(response_times),
                        'p95': self._percentile(response_times, 95),
                        'p99': self._percentile(response_times, 99)
                    },
                    'status_codes': list(set(status_codes)),
                    'success_rate': (successful_requests / num_requests) * 100
                }
            else:
                await self._progress('failed', f'No successful requests: {url}', url=url)
                return {
                    'status': 'failed',
                    'url': url,
                    'error': 'No successful requests'
                }
                
        except Exception as e:
            await self._progress('error', f'Error measuring response time: {e}', url=url)
            return {'status': 'error', 'error': str(e)}
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    async def load_test_with_ab(self, url: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform load testing using Apache Bench with custom configuration."""
        try:
            if 'ab' not in self.available_tools:
                return {'status': 'tool_unavailable', 'message': 'Apache Bench not available'}
            
            # Get configuration parameters
            ab_config = config.get('apache_bench', {}) if config else {}
            
            num_requests = ab_config.get('requests', 100)
            concurrency = ab_config.get('concurrency', 10)
            timeout = ab_config.get('timeout', 30)
            timelimit = ab_config.get('timelimit')
            
            logger.info(f"Load testing {url} with ab ({num_requests} requests, {concurrency} concurrent)")
            await self._progress('ab_start', f'AB load test start: {url}', url=url,
                                 requests=num_requests, concurrency=concurrency)
            
            # Build Apache Bench command
            cmd = ['ab']
            
            # Core parameters
            if timelimit:
                cmd.extend(['-t', str(timelimit)])
                logger.info(f"Using time limit: {timelimit}s")
            else:
                cmd.extend(['-n', str(num_requests)])
                
            cmd.extend(['-c', str(concurrency)])
            
            # Advanced configuration
            if ab_config.get('keep_alive'):
                cmd.append('-k')
            
            if ab_config.get('timeout'):
                cmd.extend(['-s', str(timeout)])
            
            if ab_config.get('headers'):
                for header_name, header_value in ab_config['headers'].items():
                    cmd.extend(['-H', f"{header_name}: {header_value}"])
            
            if ab_config.get('cookies'):
                for cookie_name, cookie_value in ab_config['cookies'].items():
                    cmd.extend(['-C', f"{cookie_name}={cookie_value}"])
            
            if ab_config.get('auth'):
                cmd.extend(['-A', ab_config['auth']])
            
            if ab_config.get('method', 'GET').upper() != 'GET':
                cmd.extend(['-m', ab_config['method'].upper()])
            
            if ab_config.get('post_file'):
                cmd.extend(['-p', ab_config['post_file']])
            
            if ab_config.get('put_file'):
                cmd.extend(['-u', ab_config['put_file']])
            
            if ab_config.get('content_type'):
                cmd.extend(['-T', ab_config['content_type']])
            
            if ab_config.get('window_size'):
                cmd.extend(['-b', str(ab_config['window_size'])])
            
            if ab_config.get('verbosity', 1) != 1:
                verbosity = ab_config['verbosity']
                if verbosity == 0:
                    cmd.append('-q')
                elif verbosity >= 2:
                    cmd.extend(['-v', str(verbosity)])
            
            # Output options
            if ab_config.get('csv_output', True):
                csv_file = f'/tmp/ab_results_{hash(url)}.csv'
                cmd.extend(['-e', csv_file])
            
            if ab_config.get('gnuplot_output', False):
                gnuplot_file = f'/tmp/ab_results_{hash(url)}.tsv'
                cmd.extend(['-g', gnuplot_file])
            
            # Add URL
            cmd.append(url)
            
            # Calculate timeout for subprocess
            subprocess_timeout = timeout + 30
            if timelimit:
                subprocess_timeout = timelimit + 30
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=subprocess_timeout)
            
            if result.returncode == 0:
                # Parse ab output
                output_lines = result.stdout.split('\n')
                
                metrics = {}
                for line in output_lines:
                    if 'Requests per second:' in line:
                        metrics['requests_per_second'] = float(line.split(':')[1].split()[0])
                    elif 'Time per request:' in line and 'mean' in line:
                        metrics['time_per_request_mean'] = float(line.split(':')[1].split()[0])
                    elif 'Time per request:' in line and 'concurrent' in line:
                        metrics['time_per_request_concurrent'] = float(line.split(':')[1].split()[0])
                    elif 'Transfer rate:' in line:
                        metrics['transfer_rate_kb_sec'] = float(line.split(':')[1].split()[0])
                    elif 'Failed requests:' in line:
                        metrics['failed_requests'] = int(line.split(':')[1].strip())
                    elif 'Complete requests:' in line:
                        metrics['complete_requests'] = int(line.split(':')[1].strip())
                    elif 'Total transferred:' in line:
                        metrics['total_transferred'] = int(line.split(':')[1].split()[0])
                    elif 'HTML transferred:' in line:
                        metrics['html_transferred'] = int(line.split(':')[1].split()[0])
                
                # Parse connection times
                connection_times = {}
                in_connection_times = False
                for line in output_lines:
                    if 'Connection Times (ms)' in line:
                        in_connection_times = True
                        continue
                    elif in_connection_times and line.strip():
                        if line.startswith('Connect:'):
                            parts = line.split()
                            connection_times['connect'] = {
                                'min': int(parts[1]),
                                'mean': int(parts[2].split('[')[0]),
                                'std_dev': float(parts[2].split('[')[1].split(']')[0]) if '[' in parts[2] else 0,
                                'median': int(parts[3]),
                                'max': int(parts[4])
                            }
                        elif line.startswith('Processing:'):
                            parts = line.split()
                            connection_times['processing'] = {
                                'min': int(parts[1]),
                                'mean': int(parts[2].split('[')[0]),
                                'std_dev': float(parts[2].split('[')[1].split(']')[0]) if '[' in parts[2] else 0,
                                'median': int(parts[3]),
                                'max': int(parts[4])
                            }
                        elif line.startswith('Waiting:'):
                            parts = line.split()
                            connection_times['waiting'] = {
                                'min': int(parts[1]),
                                'mean': int(parts[2].split('[')[0]),
                                'std_dev': float(parts[2].split('[')[1].split(']')[0]) if '[' in parts[2] else 0,
                                'median': int(parts[3]),
                                'max': int(parts[4])
                            }
                        elif line.startswith('Total:'):
                            parts = line.split()
                            connection_times['total'] = {
                                'min': int(parts[1]),
                                'mean': int(parts[2].split('[')[0]),
                                'std_dev': float(parts[2].split('[')[1].split(']')[0]) if '[' in parts[2] else 0,
                                'median': int(parts[3]),
                                'max': int(parts[4])
                            }
                            break
                
                await self._progress('ab_done', f'AB test completed: {url}', url=url,
                                     rps=metrics.get('requests_per_second', 0.0))
                return {
                    'status': 'success',
                    'tool': 'apache_bench',
                    'url': url,
                    'test_parameters': {
                        'total_requests': num_requests,
                        'concurrency': concurrency,
                        'timeout': timeout,
                        'time_limit': timelimit,
                        'keep_alive': ab_config.get('keep_alive', False)
                    },
                    'metrics': metrics,
                    'connection_times': connection_times,
                    'config_used': ab_config
                }
            else:
                await self._progress('ab_error', f'AB test error: {url}', url=url, exit_code=result.returncode)
                return {
                    'status': 'error',
                    'tool': 'apache_bench',
                    'error': result.stderr,
                    'exit_code': result.returncode,
                    'config_used': ab_config
                }
                
        except subprocess.TimeoutExpired:
            await self._progress('timeout', f'AB test timed out: {url}', url=url)
            return {'status': 'timeout', 'tool': 'apache_bench', 'error': 'Load test timed out'}
        except Exception as e:
            await self._progress('error', f'AB test error: {e}', url=url)
            return {'status': 'error', 'tool': 'apache_bench', 'error': str(e)}
    
    async def concurrent_load_test(self, url: str, num_requests: int = 50, concurrency: int = 5) -> Dict[str, Any]:
        """Perform concurrent load testing using aiohttp."""
        try:
            logger.info(f"Concurrent load testing {url} ({num_requests} requests, {concurrency} concurrent)")
            await self._progress('load_start', f'Concurrent load test start: {url}', url=url,
                                 requests=num_requests, concurrency=concurrency)
            
            semaphore = asyncio.Semaphore(concurrency)
            results = []
            
            async def single_request(session: aiohttp.ClientSession, request_id: int):
                async with semaphore:
                    try:
                        start_time = datetime.now()
                        async with session.get(url) as response:
                            content = await response.read()
                            end_time = datetime.now()
                            
                            return {
                                'request_id': request_id,
                                'status_code': response.status,
                                'response_time': (end_time - start_time).total_seconds() * 1000,
                                'content_length': len(content),
                                'success': True
                            }
                    except Exception as e:
                        return {
                            'request_id': request_id,
                            'success': False,
                            'error': str(e)
                        }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                # Create tasks for concurrent requests
                tasks = [single_request(session, i) for i in range(num_requests)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Analyze results
            successful_results = [r for r in results if isinstance(r, dict) and r.get('success')]
            failed_results = [r for r in results if isinstance(r, dict) and not r.get('success')]
            
            if successful_results:
                response_times = [r['response_time'] for r in successful_results]
                status_codes = [r['status_code'] for r in successful_results]
                content_lengths = [r['content_length'] for r in successful_results]
                
                await self._progress('load_done', f'Concurrent load test completed: {url}', url=url,
                                     success=len(successful_results), failed=len(failed_results))
                return {
                    'status': 'success',
                    'tool': 'aiohttp_concurrent',
                    'url': url,
                    'test_parameters': {
                        'total_requests': num_requests,
                        'concurrency': concurrency
                    },
                    'results': {
                        'successful_requests': len(successful_results),
                        'failed_requests': len(failed_results),
                        'success_rate': (len(successful_results) / num_requests) * 100,
                        'response_times': {
                            'min': min(response_times),
                            'max': max(response_times),
                            'avg': statistics.mean(response_times),
                            'median': statistics.median(response_times),
                            'p95': self._percentile(response_times, 95)
                        },
                        'status_codes': list(set(status_codes)),
                        'avg_content_length': statistics.mean(content_lengths) if content_lengths else 0
                    }
                }
            else:
                await self._progress('failed', f'Load test failed: {url}', url=url,
                                     failed=len(failed_results))
                return {
                    'status': 'failed',
                    'url': url,
                    'error': 'No successful requests',
                    'failed_requests': len(failed_results)
                }
                
        except Exception as e:
            await self._progress('error', f'Concurrent load test error: {e}', url=url)
            return {'status': 'error', 'error': str(e)}
    
    async def test_application_performance(self, model_slug: str, app_number: int, target_urls: List[str], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform comprehensive performance testing on application."""
        try:
            logger.info(f"Performance testing {model_slug} app {app_number}")
            
            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'tools_used': self.available_tools.copy(),
                'target_urls': target_urls,
                'results': {}
            }
            
            # Test each URL
            for i, url in enumerate(target_urls):
                url_results = {}
                
                # Basic response time test
                logger.info(f"Testing response times for {url}")
                response_time_result = await self.measure_response_time(url, num_requests=10)
                url_results['response_time'] = response_time_result
                
                # Only do load testing if basic test succeeds
                if response_time_result.get('status') == 'success':
                    # Concurrent load test
                    logger.info(f"Running concurrent load test for {url}")
                    load_test_result = await self.concurrent_load_test(url, num_requests=20, concurrency=3)
                    url_results['load_test'] = load_test_result
                    
                    # Apache Bench test if available
                    if 'ab' in self.available_tools:
                        logger.info(f"Running Apache Bench test for {url}")
                        ab_config = {'apache_bench': {'requests': 50, 'concurrency': 5}}
                        ab_result = await self.load_test_with_ab(url, ab_config)
                        url_results['apache_bench'] = ab_result
                
                results['results'][f'url_{i+1}'] = url_results
            
            # Calculate summary metrics
            summary = {
                'total_urls_tested': len(target_urls),
                'successful_tests': 0,
                'average_response_time': 0,
                'best_performing_url': None,
                'worst_performing_url': None
            }
            
            avg_response_times = []
            url_performance = []
            
            for url_key, url_result in results['results'].items():
                response_time_result = url_result.get('response_time')
                if response_time_result and response_time_result.get('status') == 'success':
                    summary['successful_tests'] += 1
                    avg_rt = response_time_result['response_times']['avg']
                    avg_response_times.append(avg_rt)
                    url_performance.append((url_key, avg_rt))
            
            if avg_response_times:
                summary['average_response_time'] = statistics.mean(avg_response_times)
                
                # Find best and worst performing URLs
                url_performance.sort(key=lambda x: x[1])
                summary['best_performing_url'] = url_performance[0][0]
                summary['worst_performing_url'] = url_performance[-1][0]
            
            results['summary'] = summary
            
            return results
            
        except Exception as e:
            logger.error(f"Performance testing failed: {e}")
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
                
            elif msg_type == "performance_test":
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 1)
                target_urls = message_data.get("target_urls", [])
                config = message_data.get("config", None)
                
                if not target_urls:
                    # Generate default URLs
                    base_port = 6000 + (app_number * 10)
                    target_urls = [
                        f"http://localhost:{base_port}",
                        f"http://localhost:{base_port + 1}"
                    ]
                
                logger.info(f"Starting performance test for {model_slug} app {app_number}")
                analysis_id = message_data.get('id')
                await self._progress('starting', f'Starting performance test {model_slug} app {app_number}',
                                     analysis_id=analysis_id, model_slug=model_slug, app_number=app_number,
                                     targets=len(target_urls))
                if config:
                    logger.info(f"Using custom configuration: {list(config.keys())}")
                
                test_results = await self.test_application_performance(model_slug, app_number, target_urls, config)
                
                response = {
                    "type": "performance_test_result",
                    "status": "success",
                    "service": self.service_name,
                    "analysis": test_results,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(response))
                await self._progress('completed', f'Performance test completed {model_slug} app {app_number}',
                                     analysis_id=analysis_id)
                logger.info(f"Performance test completed for {model_slug} app {app_number}")
                
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
    tester = PerformanceTester()
    client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.info(f"New client connected: {client_addr}")
    
    try:
        async for message in websocket:
            try:
                message_data = json.loads(message)
                await tester.handle_message(websocket, message_data)
            except json.JSONDecodeError:
                logger.error("Invalid JSON message")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {client_addr}")
    except Exception as e:
        logger.error(f"Error with client {client_addr}: {e}")

async def main():
    """Start the performance tester service."""
    host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
    port = int(os.getenv('WEBSOCKET_PORT', 2003))
    
    logger.info(f"Starting Performance Tester service on {host}:{port}")
    
    try:
        async with serve(handle_client, host, port):
            logger.info(f"Performance Tester listening on ws://{host}:{port}")
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
