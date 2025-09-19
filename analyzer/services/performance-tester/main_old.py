#!/usr/bin/env python3
"""
Performance Tester Service - Load Testing and Performance Analysis
==================================================================

Refactored to use BaseWSService with strict tool selection gating.
"""

import asyncio
import json
import os
import subprocess
import statistics
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from analyzer.shared.service_base import BaseWSService
import aiohttp

class PerformanceTester(BaseWSService):
    """Performance testing service for web applications."""
    
    def __init__(self):
        super().__init__(service_name="performance-tester", default_port=2003, version="1.0.0")
    
    def _detect_available_tools(self) -> List[str]:
        """Detect which performance testing tools are available."""
        tools = []
        
        # Check for curl (basic)
        try:
            result = subprocess.run(['curl', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('curl')
                self.log.debug("curl available")
        except Exception as e:
            self.log.debug(f"curl not available: {e}")
        
        # Check for ab (Apache Bench)
        try:
            result = subprocess.run(['ab', '-V'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('ab')
                self.log.debug("Apache Bench (ab) available")
        except Exception as e:
            self.log.debug(f"Apache Bench not available: {e}")
        
        # Check for Artillery
        try:
            result = subprocess.run(['artillery', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('artillery')
                self.log.debug("Artillery available")
        except Exception as e:
            self.log.debug(f"Artillery not available: {e}")
        
        # Check for wget
        try:
            result = subprocess.run(['wget', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('wget')
                self.log.debug("wget available")
        except Exception as e:
            self.log.debug(f"wget not available: {e}")
        
        # Always available - built-in aiohttp
        tools.append('aiohttp')
        self.log.debug("aiohttp available (built-in)")
        # Check for locust python package (import)
        try:
            import importlib  # noqa: F401
            locust_spec = __import__('locust')  # type: ignore
            if locust_spec:
                tools.append('locust')
                self.log.debug("locust available (python package)")
        except Exception as e:
            self.log.debug(f"locust not available: {e}")
        
        return tools
    
    async def measure_response_time(self, url: str, num_requests: int = 10) -> Dict[str, Any]:
        """Measure response times using aiohttp.

        Enhancements:
          * Collect sample errors for diagnostics instead of silent generic failure.
          * Optional fallback: if all requests fail for a localhost URL inside container,
            retry against host.docker.internal (common need when target app runs on host).
            Controlled by PERF_ENABLE_HOST_FALLBACK (default=1) env.
        """
        try:
            self.log.info(f"Measuring response time for {url} ({num_requests} requests)")
            await self.send_progress('measuring', f'Measuring response time: {url}', url=url, requests=num_requests)

            response_times: List[float] = []
            successful_requests = 0
            failed_requests = 0
            status_codes: List[int] = []
            sample_errors: List[str] = []

            # Allow early fallback after a configurable number of consecutive/total failures
            try:
                max_fail_before_fallback_env = os.getenv('PERF_MAX_FAIL_BEFORE_FALLBACK', '0')
                max_fail_before_fallback = int(max_fail_before_fallback_env)
            except ValueError:
                max_fail_before_fallback = 0
            early_fallback_triggered = False

            # Predefine fallback-related vars so they're always bound
            host_is_local = False
            enable_fallback = os.getenv('PERF_ENABLE_HOST_FALLBACK', '1') not in {'0', 'false', 'False'}
            fallback_used = False

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                for i in range(num_requests):
                    try:
                        start_time = datetime.now()
                        async with session.get(url) as response:
                            await response.read()
                            end_time = datetime.now()
                            rt = (end_time - start_time).total_seconds() * 1000
                            response_times.append(rt)
                            status_codes.append(response.status)
                            successful_requests += 1
                    except Exception as e:  # noqa: BLE001
                        failed_requests += 1
                        if len(sample_errors) < 5:
                            sample_errors.append(str(e))
                        self.log.debug(f"Request {i+1} failed: {e}")
                        # Trigger early fallback if threshold reached and we have zero successes so far
                        if (max_fail_before_fallback > 0 and failed_requests >= max_fail_before_fallback
                                and successful_requests == 0):
                            early_fallback_triggered = True
                            self.log.info(
                                f"Early fallback trigger: {failed_requests} consecutive failures for {url}; will attempt host fallback if enabled"
                            )
                            break

                if not response_times:
                    self.log.warning(f"No successful response times recorded for {url}, attempting fallback...")
                    # Attempt localhost -> host.docker.internal fallback if enabled
                    parsed = urlparse(url)
                    host_is_local = parsed.hostname in {'localhost', '127.0.0.1'}
                    if host_is_local and enable_fallback:
                        fallback_url = url.replace('localhost', 'host.docker.internal').replace('127.0.0.1', 'host.docker.internal')
                        self.log.info(f"No successes for {url}; attempting host gateway fallback {fallback_url}")
                        try:
                            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                                for i in range(min(5, num_requests)):
                                    try:
                                        start_time = datetime.now()
                                        async with session.get(fallback_url) as response:
                                            await response.read()
                                            end_time = datetime.now()
                                            rt = (end_time - start_time).total_seconds() * 1000
                                            response_times.append(rt)
                                            status_codes.append(response.status)
                                            successful_requests += 1
                                    except Exception as e:  # noqa: BLE001
                                        failed_requests += 1
                                        if len(sample_errors) < 5:
                                            sample_errors.append(str(e))
                            if response_times:
                                fallback_used = True
                                url = fallback_url  # report successful fallback URL as canonical for metrics
                        except Exception as fe:  # noqa: BLE001
                            if len(sample_errors) < 5:
                                sample_errors.append(f"fallback_error: {fe}")

                if not response_times:
                    await self.send_progress('failed', f'No successful requests: {url}', url=url)
                    return {
                        'status': 'failed',
                        'url': url,
                        'error': 'No successful requests',
                        'sample_errors': sample_errors,
                        'attempted_fallback': host_is_local and enable_fallback,
                        'fallback_succeeded': False
                    }
                else:
                    # Fallback produced successes
                    await self.send_progress('measured', f'Response time measured (fallback): {url}', url=url,
                                         avg_ms=statistics.mean(response_times))
                    return {
                        'status': 'success',
                        'url': url,
                        'total_requests': successful_requests + failed_requests,
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
                        'success_rate': (successful_requests / (successful_requests + failed_requests)) * 100 if (successful_requests + failed_requests) else 0,
                        'sample_errors': sample_errors,
                        'attempted_fallback': True,
                        'fallback_used': fallback_used,
                        'early_fallback_triggered': early_fallback_triggered
                    }

            # Normal success path
            self.log.info(f"Response time test completed successfully: {successful_requests} successful, {failed_requests} failed requests for {url}")
            await self.send_progress('measured', f'Response time measured: {url}', url=url,
                                 avg_ms=statistics.mean(response_times))
            return {
                'status': 'success',
                'url': url,
                'total_requests': successful_requests + failed_requests,
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
                'success_rate': (successful_requests / (successful_requests + failed_requests)) * 100 if (successful_requests + failed_requests) else 0,
                'sample_errors': sample_errors,
                'early_fallback_triggered': early_fallback_triggered
            }

        except Exception as e:  # pragma: no cover
            await self.send_progress('error', f'Error measuring response time: {e}', url=url)
            return {'status': 'error', 'error': str(e), 'url': url}
    
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
            
            self.log.info(f"Load testing {url} with ab ({num_requests} requests, {concurrency} concurrent)")
            await self.send_progress('ab_start', f'AB load test start: {url}', url=url,
                                 requests=num_requests, concurrency=concurrency)
            
            # Build Apache Bench command
            cmd = ['ab']
            
            # Core parameters
            if timelimit:
                cmd.extend(['-t', str(timelimit)])
                self.log.info(f"Using time limit: {timelimit}s")
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
            
            # ab requires a path component; ensure trailing slash so we don't get 'invalid URL'
            ab_url = url if url.endswith('/') or urlparse(url).path else url + '/'
            cmd.append(ab_url)
            
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
                
                await self.send_progress('ab_done', f'AB test completed: {url}', url=url,
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
                await self.send_progress('ab_error', f'AB test error: {url}', url=url, exit_code=result.returncode)
                return {
                    'status': 'error',
                    'tool': 'apache_bench',
                    'error': result.stderr,
                    'exit_code': result.returncode,
                    'config_used': ab_config
                }
                
        except subprocess.TimeoutExpired:
            await self.send_progress('timeout', f'AB test timed out: {url}', url=url)
            return {'status': 'timeout', 'tool': 'apache_bench', 'error': 'Load test timed out'}
        except Exception as e:
            await self.send_progress('error', f'AB test error: {e}', url=url)
            return {'status': 'error', 'tool': 'apache_bench', 'error': str(e)}
    
    async def concurrent_load_test(self, url: str, num_requests: int = 50, concurrency: int = 5) -> Dict[str, Any]:
        """Perform concurrent load testing using aiohttp."""
        try:
            self.log.info(f"Concurrent load testing {url} ({num_requests} requests, {concurrency} concurrent)")
            await self.send_progress('load_start', f'Concurrent load test start: {url}', url=url,
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
                
                await self.send_progress('load_done', f'Concurrent load test completed: {url}', url=url,
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
                await self.send_progress('failed', f'Load test failed: {url}', url=url,
                                     failed=len(failed_results))
                return {
                    'status': 'failed',
                    'url': url,
                    'error': 'No successful requests',
                    'failed_requests': len(failed_results)
                }
                
        except Exception as e:
            await self.send_progress('error', f'Concurrent load test error: {e}', url=url)
            return {'status': 'error', 'error': str(e)}
    
    async def load_test_with_artillery(self, url: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform load testing using Artillery with custom configuration."""
        try:
            if 'artillery' not in self.available_tools:
                return {'status': 'tool_unavailable', 'message': 'Artillery not available'}
            
            # Get configuration parameters
            artillery_config = config.get('artillery', {}) if config else {}
            
            # Artillery configuration
            users = artillery_config.get('users', 100)
            spawn_rate = artillery_config.get('spawn_rate', 10)
            duration = artillery_config.get('duration', 60)
            target = artillery_config.get('target', url)
            
            self.log.info(f"Load testing {url} with Artillery ({users} users, {spawn_rate}/s spawn rate, {duration}s duration)")
            await self.send_progress('artillery_start', f'Artillery load test start: {url}', url=url,
                                 users=users, spawn_rate=spawn_rate, duration=duration)
            
            # Create temporary Artillery config file
            import tempfile
            import yaml
            
            artillery_config_data = {
                'config': {
                    'target': target,
                    'phases': [
                        {
                            'name': artillery_config.get('phase_name', 'Load Test'),
                            'duration': duration,
                            'arrivalRate': spawn_rate,
                            'maxVusers': users
                        }
                    ]
                },
                'scenarios': [
                    {
                        'flow': [
                            {
                                'get': {
                                    'url': artillery_config.get('endpoint', '/')
                                }
                            }
                        ]
                    }
                ]
            }
            
            # Add custom scenarios if provided
            if artillery_config.get('scenarios'):
                artillery_config_data['scenarios'] = artillery_config['scenarios']
            
            # Add processor if provided
            if artillery_config.get('processor'):
                artillery_config_data['config']['processor'] = artillery_config['processor']
            
            # Create temporary config file
            config_file = None
            output_file = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
                    yaml.dump(artillery_config_data, f, indent=2)
                    config_file = f.name
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    output_file = f.name
                
                # Build Artillery command
                cmd = [
                    'artillery', 'run',
                    '--output', output_file,
                    config_file
                ]
                
                # Add additional Artillery options
                if artillery_config.get('quiet'):
                    cmd.append('--quiet')
                
                if artillery_config.get('overrides'):
                    for key, value in artillery_config['overrides'].items():
                        cmd.extend(['--overrides', f'{key}={value}'])
                
                self.log.info(f"Running Artillery: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 120)
                
                if result.returncode == 0:
                    # Parse Artillery JSON output
                    artillery_results = {}
                    try:
                        with open(output_file, 'r') as f:
                            artillery_data = json.load(f)
                            
                        # Extract metrics from Artillery output
                        aggregate = artillery_data.get('aggregate', {})
                        
                        artillery_results = {
                            'scenarios_created': aggregate.get('scenariosCreated', 0),
                            'scenarios_completed': aggregate.get('scenariosCompleted', 0),
                            'requests_completed': aggregate.get('requestsCompleted', 0),
                            'latency': {
                                'min': aggregate.get('latency', {}).get('min', 0),
                                'max': aggregate.get('latency', {}).get('max', 0),
                                'median': aggregate.get('latency', {}).get('median', 0),
                                'p95': aggregate.get('latency', {}).get('p95', 0),
                                'p99': aggregate.get('latency', {}).get('p99', 0)
                            },
                            'rps': {
                                'count': aggregate.get('rps', {}).get('count', 0),
                                'mean': aggregate.get('rps', {}).get('mean', 0)
                            },
                            'scenario_duration': {
                                'min': aggregate.get('scenarioDuration', {}).get('min', 0),
                                'max': aggregate.get('scenarioDuration', {}).get('max', 0),
                                'median': aggregate.get('scenarioDuration', {}).get('median', 0),
                                'p95': aggregate.get('scenarioDuration', {}).get('p95', 0),
                                'p99': aggregate.get('scenarioDuration', {}).get('p99', 0)
                            },
                            'errors': aggregate.get('errors', {}),
                            'codes': aggregate.get('codes', {})
                        }
                        
                    except Exception as parse_error:
                        self.log.warning(f"Could not parse Artillery output: {parse_error}")
                        artillery_results = {'raw_output': result.stdout}
                    
                    await self.send_progress('artillery_done', f'Artillery test completed: {url}', url=url,
                                         rps=artillery_results.get('rps', {}).get('mean', 0))
                    return {
                        'status': 'success',
                        'tool': 'artillery',
                        'url': url,
                        'test_parameters': {
                            'users': users,
                            'spawn_rate': spawn_rate,
                            'duration': duration,
                            'target': target
                        },
                        'results': artillery_results,
                        'config_used': artillery_config
                    }
                else:
                    await self.send_progress('artillery_error', f'Artillery test error: {url}', url=url, exit_code=result.returncode)
                    return {
                        'status': 'error',
                        'tool': 'artillery',
                        'error': result.stderr or result.stdout,
                        'exit_code': result.returncode,
                        'config_used': artillery_config
                    }
            
            finally:
                # Cleanup temporary files
                try:
                    if config_file and os.path.exists(config_file):
                        os.unlink(config_file)
                    if output_file and os.path.exists(output_file):
                        os.unlink(output_file)
                except Exception:
                    pass
                    
        except subprocess.TimeoutExpired:
            await self.send_progress('timeout', f'Artillery test timed out: {url}', url=url)
            return {'status': 'timeout', 'tool': 'artillery', 'error': 'Load test timed out'}
        except Exception as e:
            await self.send_progress('error', f'Artillery test error: {e}', url=url)
            return {'status': 'error', 'tool': 'artillery', 'error': str(e)}
    
    async def test_application_performance(self, model_slug: str, app_number: int, target_urls: List[str], config: Optional[Dict[str, Any]] = None, selected_tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Perform comprehensive performance testing on application."""
        try:
            self.log.info(f"Performance testing {model_slug} app {app_number}")
            selected_set = {t.lower() for t in selected_tools} if selected_tools else None
            
            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'tools_used': [],
                'target_urls': target_urls,
                'results': {}
            }
            
            # Test each URL
            for i, url in enumerate(target_urls):
                url_results = {}
                
                # Basic response time test
                self.log.info(f"Testing response times for {url}")
                # Always use aiohttp internal method unless explicitly excluded by selection
                if selected_set is None or 'aiohttp' in selected_set:
                    response_time_result = await self.measure_response_time(url, num_requests=10)
                    results['tools_used'] = list(set(results['tools_used'] + ['aiohttp']))
                else:
                    response_time_result = {'status': 'skipped', 'reason': 'aiohttp not selected', 'url': url}
                effective_url = response_time_result.get('url', url)
                url_results['response_time'] = response_time_result
                url_results['effective_url'] = effective_url
                
                # Only do load testing if basic test succeeds (success_rate threshold configurable)
                success_status = response_time_result.get('status') == 'success'
                
                # Be more permissive - if the response time test failed but we got a result, log it and continue anyway
                if not success_status:
                    self.log.warning(f"Response time test returned status: {response_time_result.get('status')}, error: {response_time_result.get('error')}")
                    self.log.info(f"Attempting load tests anyway for {effective_url} (bypassing response time gate)")
                    success_status = True  # Force success to allow load tests
                
                # Coerce success_rate to float defensively
                raw_rate = response_time_result.get('success_rate', 0)
                try:
                    success_rate = float(raw_rate)
                except Exception:
                    success_rate = 0.0
                min_rate_env = os.getenv('PERF_MIN_SUCCESS_RATE', '0')
                try:
                    min_success_rate = float(min_rate_env)
                except ValueError:
                    min_success_rate = 0.0
                if success_status and success_rate >= min_success_rate:
                    # Concurrent load test (use effective URL which may be fallback)
                    self.log.info(f"Running concurrent load test for {effective_url}")
                    if selected_set is None or 'aiohttp' in selected_set:
                        load_test_result = await self.concurrent_load_test(effective_url, num_requests=20, concurrency=3)
                        url_results['load_test'] = load_test_result
                        results['tools_used'] = list(set(results['tools_used'] + ['aiohttp']))
                    
                    # Apache Bench test if available
                    if 'ab' in self.available_tools and (selected_set is None or 'ab' in selected_set):
                        self.log.info(f"Running Apache Bench test for {effective_url}")
                        ab_config = {'apache_bench': {'requests': 50, 'concurrency': 5}}
                        ab_result = await self.load_test_with_ab(effective_url, ab_config)
                        url_results['apache_bench'] = ab_result
                        if ab_result.get('status') == 'success':
                            results['tools_used'] = list(set(results['tools_used'] + ['ab']))
                    
                    # Artillery test if available
                    if 'artillery' in self.available_tools and (selected_set is None or 'artillery' in selected_set):
                        self.log.info(f"Running Artillery test for {effective_url}")
                        artillery_config = {
                            'artillery': {
                                'users': 50,
                                'spawn_rate': 5,
                                'duration': 30,
                                'target': effective_url,
                                'endpoint': '/'
                            }
                        }
                        artillery_result = await self.load_test_with_artillery(effective_url, artillery_config)
                        url_results['artillery'] = artillery_result
                        if artillery_result.get('status') == 'success':
                            results['tools_used'] = list(set(results['tools_used'] + ['artillery']))
                        results['tools_used'] = list(set(results['tools_used'] + ['ab']))

                    # Locust test if available (run only for first URL by default to save time)
                    if 'locust' in self.available_tools and i == 0 and (selected_set is None or 'locust' in selected_set):
                        self.log.info(f"Running Locust test for {effective_url}")
                        locust_cfg = None
                        if config:
                            locust_cfg = config.get('locust') if isinstance(config, dict) else None
                        locust_result = await self.run_locust_test(effective_url, locust_cfg)
                        url_results['locust'] = locust_result
                        results['tools_used'] = list(set(results['tools_used'] + ['locust']))
                else:
                    if not success_status:
                        self.log.info(f"Skipping heavy load tests for {url} due to failed response_time status")
                    else:
                        self.log.info(f"Skipping heavy load tests for {url} due to success_rate {success_rate:.2f}% below threshold {min_success_rate:.2f}%")
                
                results['results'][f'url_{i+1}'] = url_results
            
            # Calculate summary metrics
            summary = {
                'total_urls_tested': len(target_urls),
                'successful_tests': 0,
                'average_response_time': 0,
                'best_performing_url': None,
                'worst_performing_url': None,
                'fallback_attempts': 0,
                'fallback_successes': 0,
                'early_fallback_triggers': 0,
                'urls_with_fallback': []
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
                if response_time_result:
                    if response_time_result.get('attempted_fallback'):
                        summary['fallback_attempts'] += 1
                    if response_time_result.get('fallback_used'):
                        summary['fallback_successes'] += 1
                        summary['urls_with_fallback'].append(url_key)
                    if response_time_result.get('early_fallback_triggered'):
                        summary['early_fallback_triggers'] += 1
            
            if avg_response_times:
                summary['average_response_time'] = statistics.mean(avg_response_times)
                
                # Find best and worst performing URLs
                url_performance.sort(key=lambda x: x[1])
                summary['best_performing_url'] = url_performance[0][0]
                summary['worst_performing_url'] = url_performance[-1][0]
            
            results['summary'] = summary
            
            return results
            
        except Exception as e:
            self.log.error(f"Performance testing failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'model_slug': model_slug,
                'app_number': app_number
            }

    async def run_locust_test(self, url: str, locust_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a short Locust headless load test against the base URL.

        Implementation uses the locust CLI via subprocess to avoid mixing gevent with asyncio loop.
        Generates CSV stats which are parsed for summary metrics.
        """
        if 'locust' not in self.available_tools:
            return {'status': 'tool_unavailable', 'tool': 'locust'}
        try:
            # Auto-generate a minimal locustfile if none present in CWD to avoid CLI error
            default_locustfile = 'locustfile.py'
            if not os.path.exists(default_locustfile):
                try:
                    with open(default_locustfile, 'w', encoding='utf-8') as lf:
                        lf.write(
                            "from locust import HttpUser, task, between\n\n"
                            "class QuickUser(HttpUser):\n"
                            "    wait_time = between(0.5, 1.5)\n\n"
                            "    @task\n"
                            "    def index(self):\n"
                            "        self.client.get('/')\n"
                        )
                    self.log.debug("Auto-generated minimal locustfile.py for test run")
                except Exception as gen_err:  # noqa: BLE001
                    self.log.warning(f"Failed to auto-generate locustfile.py: {gen_err}")
            # Defaults (kept deliberately small for fast feedback)
            users = 15
            spawn_rate = 3
            run_time = '15s'
            host = url.rstrip('/')
            if locust_config:
                users = int(locust_config.get('users', users))
                spawn_rate = float(locust_config.get('spawn_rate', spawn_rate))
                run_time = str(locust_config.get('run_time', run_time))
            csv_prefix = f"/tmp/locust_{abs(hash(url))}"
            cmd = [
                'locust', '--headless',
                '-u', str(users),
                '-r', str(spawn_rate),
                '-t', run_time,
                '-H', host,
                '--only-summary',
                '--csv', csv_prefix
            ]
            await self.send_progress('locust_start', f'Locust test start: {url}', url=url, users=users, spawn_rate=spawn_rate)
            # Derive a timeout (run_time -> seconds)
            timeout_seconds = 60
            try:
                if run_time.endswith('s'):
                    timeout_seconds = int(run_time[:-1]) + 30
                elif run_time.endswith('m'):
                    timeout_seconds = int(run_time[:-1]) * 60 + 30
            except Exception:
                pass
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
            if result.returncode != 0:
                await self.send_progress('locust_error', f'Locust failed: {url}', url=url, exit_code=result.returncode)
                return {'status': 'error', 'tool': 'locust', 'exit_code': result.returncode, 'stderr': result.stderr}
            # Parse CSV stats
            stats_file = f"{csv_prefix}_stats.csv"
            summary = {}
            if os.path.exists(stats_file):
                try:
                    import csv  # noqa: F401
                    with open(stats_file, 'r', encoding='utf-8') as f:
                        lines = f.read().strip().splitlines()
                    if lines:
                        header = [h.strip() for h in lines[0].split(',')]
                        for row_line in lines[1:]:
                            cols = [c.strip() for c in row_line.split(',')]
                            row = dict(zip(header, cols))
                            name = row.get('Name') or row.get('name')
                            if name in ('Aggregated', 'Total', 'None', ''):
                                # Extract metrics of interest
                                rps = row.get('Requests/s') or row.get('Requests/s ')
                                p95 = row.get('95%')
                                avg_rt = row.get('Average Response Time') or row.get('Average Response Time ')
                                failures = row.get('Failures')
                                requests = row.get('Requests')
                                summary = {
                                    'requests_per_second': float(rps) if rps and rps.replace('.', '', 1).isdigit() else None,
                                    'p95_response_time_ms': float(p95) if p95 and p95.replace('.', '', 1).isdigit() else None,
                                    'average_response_time_ms': float(avg_rt) if avg_rt and avg_rt.replace('.', '', 1).isdigit() else None,
                                    'total_requests': int(requests) if requests and requests.isdigit() else None,
                                    'failures': int(failures) if failures and failures.isdigit() else None
                                }
                                break
                except Exception as e:
                    summary['parse_error'] = str(e)
            await self.send_progress('locust_done', f'Locust test completed: {url}', url=url, rps=summary.get('requests_per_second'))
            return {
                'status': 'success',
                'tool': 'locust',
                'url': url,
                'config_used': {
                    'users': users,
                    'spawn_rate': spawn_rate,
                    'run_time': run_time
                },
                'summary': summary,
                'stdout_tail': result.stdout.splitlines()[-5:] if result.stdout else []
            }
        except subprocess.TimeoutExpired:
            await self.send_progress('locust_timeout', f'Locust timeout: {url}', url=url)
            return {'status': 'timeout', 'tool': 'locust', 'url': url}
        except FileNotFoundError:
            # Locust executable not found though package claimed present
            return {'status': 'error', 'tool': 'locust', 'error': 'locust command not found'}
        except Exception as e:
            await self.send_progress('locust_error', f'Locust error: {e}', url=url)
            return {'status': 'error', 'tool': 'locust', 'error': str(e)}
    
    async def handle_message(self, websocket, message_data):
        """Handle incoming WebSocket messages."""
        try:
            msg_type = message_data.get("type", "unknown")
            if msg_type == "performance_test":
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 1)
                # Accept new 'target_urls' list; fall back to legacy single 'target_url'
                target_urls = message_data.get("target_urls")
                if not target_urls:
                    single = message_data.get("target_url")
                    if single:
                        target_urls = [single]
                if not isinstance(target_urls, list):  # defensive normalization
                    target_urls = []
                config = message_data.get("config", None)
                selected_tools = list(self.extract_selected_tools(message_data) or [])
                
                if not target_urls:
                    # Generate default URLs
                    base_port = 6000 + (app_number * 10)
                    target_urls = [
                        f"http://localhost:{base_port}",
                        f"http://localhost:{base_port + 1}"
                    ]
                
                self.log.info(f"Starting performance test for {model_slug} app {app_number}")
                analysis_id = message_data.get('id')
                await self.send_progress('starting', f'Starting performance test {model_slug} app {app_number}',
                                     analysis_id=analysis_id, model_slug=model_slug, app_number=app_number,
                                     targets=len(target_urls))
                if config:
                    self.log.info(f"Using custom configuration: {list(config.keys())}")
                
                test_results = await self.test_application_performance(model_slug, app_number, target_urls, config, selected_tools)
                
                response = {
                    "type": "performance_test_result",
                    "status": "success",
                    "service": self.info.name,
                    "analysis": test_results,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(response))
                await self.send_progress('completed', f'Performance test completed {model_slug} app {app_number}',
                                     analysis_id=analysis_id)
                self.log.info(f"Performance test completed for {model_slug} app {app_number}")
                
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
    service = PerformanceTester()
    await service.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
