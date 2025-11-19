#!/usr/bin/env python3
"""
Performance Tester Service - Simplified and Robust Load Testing
==============================================================

A complete rewrite focused on actually working rather than complex error handling.
Based on proven patterns from performance_analysis.py and Docker best practices.
"""

import os
import json
import asyncio
import aiohttp
import subprocess
import statistics
import time
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from analyzer.shared.service_base import BaseWSService
from analyzer.shared.tool_logger import ToolExecutionLogger

class PerformanceTester(BaseWSService):
    """Simplified, robust performance testing service."""
    
    def __init__(self):
        super().__init__(service_name="performance-tester", default_port=2003, version="2.0.0")
        self.test_output_dir = Path("/tmp/performance_tests")
        self.test_output_dir.mkdir(exist_ok=True)
        # Initialize tool execution logger for comprehensive output logging
        self.tool_logger = ToolExecutionLogger(self.log)
    
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
                self.log.debug("Apache Bench available")
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
        
        # Check for locust python package
        try:
            import importlib.util
            if importlib.util.find_spec('locust') is not None:
                tools.append('locust')
                self.log.debug("Locust available")
            else:
                self.log.debug("Locust not available")
        except Exception as e:
            self.log.debug(f"Locust check failed: {e}")
        
        # Always available - built-in aiohttp
        tools.append('aiohttp')
        self.log.debug("aiohttp available (built-in)")
        
        return tools
    
    async def simple_response_check(self, url: str, num_requests: int = 3) -> Dict[str, Any]:
        """Simple response check - just verify the app is reachable."""
        try:
            self.log.info(f"Quick response check for {url}")
            await self.send_progress('checking', f'Checking connectivity: {url}', url=url)

            # Try multiple hostnames for Docker networking  
            test_urls = [url]
            parsed = urlparse(url)
            if parsed.hostname in ['localhost', '127.0.0.1']:
                # Add host.docker.internal alternative
                alt_url = url.replace(parsed.netloc, f"host.docker.internal:{parsed.port}")
                test_urls.append(alt_url)
            
            successful_url = None
            last_error = None
            
            for test_url in test_urls:
                try:
                    # Use shorter timeout for faster failure detection
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                        async with session.get(test_url) as response:
                            if response.status < 500:  # Accept anything that's not a server error
                                successful_url = test_url
                                self.log.info(f"✓ Successfully connected to {test_url} (status: {response.status})")
                                break
                except Exception as e:
                    last_error = str(e)
                    self.log.debug(f"Failed to connect to {test_url}: {e}")
                    continue
            
            if successful_url:
                await self.send_progress('connected', f'Connected to: {successful_url}')
                return {
                    'status': 'success',
                    'original_url': url,
                    'working_url': successful_url,
                    'message': f'Successfully connected to {successful_url}'
                }
            else:
                await self.send_progress('failed', f'Could not connect to {url}')
                return {
                    'status': 'error',
                    'original_url': url,
                    'error': f'Could not connect to any variant of {url}. Last error: {last_error}'
                }

        except Exception as e:
            await self.send_progress('error', f'Response check error: {e}')
            return {'status': 'error', 'original_url': url, 'error': str(e)}
    
    async def run_apache_bench_test(self, url: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run Apache Bench load test."""
        if 'ab' not in self.available_tools:
            return {'status': 'not_available', 'tool': 'ab', 'executed': False, 'error': 'Apache Bench not available'}
        
        try:
            # Get configuration
            ab_config = config.get('apache_bench', {}) if config else {}
            requests = ab_config.get('requests', 20)  # Reduced from 100 for faster tests
            concurrency = ab_config.get('concurrency', 5)  # Reduced from 10 for faster tests
            
            # Apache Bench requires a path component - ensure URL has trailing slash
            ab_url = url.rstrip('/') + '/'
            
            self.log.info(f"Running Apache Bench: {requests} requests, {concurrency} concurrent on {ab_url}")
            await self.send_progress('ab_start', f'Apache Bench starting: {ab_url}', 
                                   requests=requests, concurrency=concurrency)
            
            # Build command
            cmd = ['ab', '-n', str(requests), '-c', str(concurrency), '-g', 'ab_results.tsv', ab_url]
            
            # Log command start
            self.tool_logger.log_command_start('ab', cmd, context={'requests': requests, 'concurrency': concurrency})
            
            # Run test with shorter timeout for faster tests (was 600s)
            start_ts = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45, cwd=str(self.test_output_dir))
            duration = time.time() - start_ts
            
            # Log command completion
            exec_record = self.tool_logger.log_command_complete('ab', cmd, result, duration)
            
            if result.returncode == 0:
                # Parse results from stdout
                output = result.stdout
                
                # Extract key metrics using simple parsing
                metrics = self._parse_ab_output(output)
                metrics.update({
                    'status': 'success',
                    'tool': 'ab',
                    'executed': True,
                    'total_issues': 0,
                    'url': ab_url,
                    'configuration': {'requests': requests, 'concurrency': concurrency},
                    'raw': {
                        'command': cmd,
                        'stdout': output[:12000],
                        'stderr': (result.stderr or '')[:4000],
                        'exit_code': result.returncode,
                        'duration': duration
                    }
                })
                
                await self.send_progress('ab_complete', f'Apache Bench completed: {ab_url}', 
                                       rps=metrics.get('requests_per_second', 0))
                return metrics
            else:
                error_msg = result.stderr or "Apache Bench failed"
                self.log.error(f"Apache Bench failed: {error_msg}")
                return {'status': 'error', 'tool': 'ab', 'executed': True, 'error': error_msg, 'url': ab_url, 'raw': {
                    'command': cmd,
                    'stdout': (result.stdout or '')[:8000],
                    'stderr': (result.stderr or '')[:4000],
                    'exit_code': result.returncode,
                    'duration': duration
                }}
                
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'tool': 'ab', 'executed': True, 'error': 'Test timed out', 'url': url}
        except Exception as e:
            return {'status': 'error', 'tool': 'ab', 'executed': True, 'error': str(e), 'url': url}
    
    def _parse_ab_output(self, output: str) -> Dict[str, Any]:
        """Parse Apache Bench output for key metrics."""
        metrics = {}
        
        for line in output.split('\n'):
            line = line.strip()
            
            if 'Requests per second:' in line:
                try:
                    rps = float(line.split(':')[1].split('[')[0].strip())
                    metrics['requests_per_second'] = rps
                except (ValueError, IndexError):
                    pass
            
            elif 'Time per request:' in line and '[ms]' in line:
                try:
                    time_per_req = float(line.split(':')[1].split('[')[0].strip())
                    metrics['avg_response_time'] = time_per_req
                except (ValueError, IndexError):
                    pass
            
            elif 'Complete requests:' in line:
                try:
                    completed = int(line.split(':')[1].strip())
                    metrics['completed_requests'] = completed
                except (ValueError, IndexError):
                    pass
            
            elif 'Failed requests:' in line:
                try:
                    failed = int(line.split(':')[1].strip())
                    metrics['failed_requests'] = failed
                except (ValueError, IndexError):
                    pass
        
        return metrics
    
    async def run_locust_test(self, url: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run Locust load test using CLI."""
        if 'locust' not in self.available_tools:
            return {'status': 'not_available', 'tool': 'locust', 'executed': False, 'error': 'Locust not available'}
        
        try:
            # Get configuration
            locust_config = config.get('locust', {}) if config else {}
            users = locust_config.get('users', 10)  # Reduced from 50 for faster tests
            spawn_rate = locust_config.get('spawn_rate', 2)
            run_time = locust_config.get('run_time', '15s')  # Reduced from 30s for faster tests
            
            self.log.info(f"Running Locust: {users} users, {spawn_rate}/s spawn rate, {run_time} duration on {url}")
            await self.send_progress('locust_start', f'Locust starting: {url}', 
                                   users=users, spawn_rate=spawn_rate, duration=run_time)
            
            # Create simple locustfile
            locustfile_path = self.test_output_dir / "simple_locustfile.py"
            locustfile_content = f'''
from locust import HttpUser, task, between

class SimpleUser(HttpUser):
    host = "{url}"
    wait_time = between(1, 2)
    
    @task
    def load_test(self):
        self.client.get("/")
'''
            locustfile_path.write_text(locustfile_content)
            
            # Build command
            csv_prefix = str(self.test_output_dir / "locust_stats")
            cmd = [
                'locust',
                '-f', str(locustfile_path),
                '--headless',
                '--users', str(users),
                '--spawn-rate', str(spawn_rate),
                '--run-time', str(run_time),
                '--host', url,
                '--csv', csv_prefix
            ]
            
            # Run test with shorter timeout for faster tests (was 900s)
            start_ts = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(self.test_output_dir))
            duration = time.time() - start_ts
            
            if result.returncode == 0:
                # Parse CSV results
                metrics = self._parse_locust_csv(csv_prefix)
                metrics.update({
                    'status': 'success',
                    'tool': 'locust',
                    'executed': True,
                    'total_issues': 0,
                    'url': url,
                    'configuration': {'users': users, 'spawn_rate': spawn_rate, 'run_time': run_time},
                    'raw': {
                        'command': cmd,
                        'stdout': (result.stdout or '')[:8000],
                        'stderr': (result.stderr or '')[:4000],
                        'exit_code': result.returncode,
                        'duration': duration
                    }
                })
                
                await self.send_progress('locust_complete', f'Locust completed: {url}', 
                                       rps=metrics.get('requests_per_second', 0))
                return metrics
            else:
                error_msg = result.stderr or "Locust failed"
                self.log.error(f"Locust failed: {error_msg}")
                return {'status': 'error', 'tool': 'locust', 'executed': True, 'error': error_msg, 'url': url, 'raw': {
                    'command': cmd,
                    'stdout': (result.stdout or '')[:4000],
                    'stderr': (result.stderr or '')[:4000],
                    'exit_code': result.returncode,
                    'duration': duration
                }}
                
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'tool': 'locust', 'executed': True, 'error': 'Test timed out', 'url': url}
        except Exception as e:
            return {'status': 'error', 'tool': 'locust', 'executed': True, 'error': str(e), 'url': url}
    
    def _parse_locust_csv(self, csv_prefix: str) -> Dict[str, Any]:
        """Parse Locust CSV results for key metrics."""
        metrics = {}
        
        try:
            stats_file = f"{csv_prefix}_stats.csv"
            if os.path.exists(stats_file):
                with open(stats_file, 'r') as f:
                    lines = f.readlines()
                    if len(lines) > 1:  # Skip header
                        # Parse aggregated stats (last line is usually "Aggregated")
                        for line in reversed(lines[1:]):
                            parts = line.strip().split(',')
                            if len(parts) >= 10 and ('Aggregated' in parts[1] or parts[1] == '"Aggregated"'):
                                # Extract metrics from aggregated row
                                metrics['requests'] = int(parts[2]) if parts[2].isdigit() else 0
                                metrics['failures'] = int(parts[3]) if parts[3].isdigit() else 0
                                metrics['avg_response_time'] = float(parts[4]) if parts[4].replace('.','').isdigit() else 0
                                metrics['min_response_time'] = float(parts[5]) if parts[5].replace('.','').isdigit() else 0
                                metrics['max_response_time'] = float(parts[6]) if parts[6].replace('.','').isdigit() else 0
                                metrics['requests_per_second'] = float(parts[9]) if parts[9].replace('.','').isdigit() else 0
                                break
        except Exception as e:
            self.log.warning(f"Could not parse Locust CSV: {e}")
        
        return metrics
    
    async def run_artillery_test(self, url: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run Artillery load test."""
        if 'artillery' not in self.available_tools:
            return {'status': 'not_available', 'tool': 'artillery', 'executed': False, 'error': 'Artillery not available'}
        
        try:
            # Get configuration
            artillery_config = config.get('artillery', {}) if config else {}
            duration = artillery_config.get('duration', 30)
            arrival_rate = artillery_config.get('arrival_rate', 5)
            
            self.log.info(f"Running Artillery: {duration}s duration, {arrival_rate} arrivals/sec on {url}")
            await self.send_progress('artillery_start', f'Artillery starting: {url}', 
                                   duration=duration, arrival_rate=arrival_rate)
            
            # Create Artillery YAML config
            artillery_config_path = self.test_output_dir / "artillery_config.yml"
            artillery_config_content = f'''config:
  target: "{url}"
  phases:
    - duration: {duration}
      arrivalRate: {arrival_rate}
      name: "Load test"
  http:
    timeout: 30
scenarios:
  - name: "Simple load test"
    flow:
      - get:
          url: "/"
'''
            artillery_config_path.write_text(artillery_config_content)
            
            # Build command with JSON output
            output_json = str(self.test_output_dir / "artillery_report.json")
            cmd = ['artillery', 'run', '--output', output_json, str(artillery_config_path)]
            
            # Run test with shorter timeout for faster tests (was 600s)
            start_ts = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(self.test_output_dir))
            duration_actual = time.time() - start_ts
            
            if result.returncode == 0:
                # Parse JSON results
                metrics = self._parse_artillery_json(output_json)
                metrics.update({
                    'status': 'success',
                    'tool': 'artillery',
                    'executed': True,
                    'total_issues': 0,
                    'url': url,
                    'configuration': {'duration': duration, 'arrival_rate': arrival_rate},
                    'raw': {
                        'command': cmd,
                        'stdout': (result.stdout or '')[:8000],
                        'stderr': (result.stderr or '')[:4000],
                        'exit_code': result.returncode,
                        'duration': duration_actual
                    }
                })
                
                await self.send_progress('artillery_complete', f'Artillery completed: {url}', 
                                       rps=metrics.get('requests_per_second', 0))
                return metrics
            else:
                error_msg = result.stderr or "Artillery failed"
                self.log.error(f"Artillery failed: {error_msg}")
                return {'status': 'error', 'tool': 'artillery', 'executed': True, 'error': error_msg, 'url': url, 'raw': {
                    'command': cmd,
                    'stdout': (result.stdout or '')[:4000],
                    'stderr': (result.stderr or '')[:4000],
                    'exit_code': result.returncode,
                    'duration': duration_actual
                }}
                
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'tool': 'artillery', 'executed': True, 'error': 'Test timed out', 'url': url}
        except Exception as e:
            return {'status': 'error', 'tool': 'artillery', 'executed': True, 'error': str(e), 'url': url}
    
    def _parse_artillery_json(self, json_path: str) -> Dict[str, Any]:
        """Parse Artillery JSON results for key metrics."""
        metrics = {}
        
        try:
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    
                    # Extract aggregate stats
                    aggregate = data.get('aggregate', {})
                    
                    # Request metrics
                    counters = aggregate.get('counters', {})
                    metrics['requests'] = counters.get('http.requests', 0)
                    metrics['responses'] = counters.get('http.responses', 0)
                    metrics['codes'] = {
                        '2xx': counters.get('http.codes.200', 0) + counters.get('http.codes.201', 0),
                        '3xx': counters.get('http.codes.301', 0) + counters.get('http.codes.302', 0),
                        '4xx': counters.get('http.codes.400', 0) + counters.get('http.codes.404', 0),
                        '5xx': counters.get('http.codes.500', 0) + counters.get('http.codes.502', 0)
                    }
                    
                    # Latency metrics
                    latency = aggregate.get('latency', {})
                    metrics['avg_response_time'] = latency.get('mean', 0) / 1000  # Convert to ms
                    metrics['min_response_time'] = latency.get('min', 0) / 1000
                    metrics['max_response_time'] = latency.get('max', 0) / 1000
                    metrics['p50_response_time'] = latency.get('median', 0) / 1000
                    metrics['p95_response_time'] = latency.get('p95', 0) / 1000
                    metrics['p99_response_time'] = latency.get('p99', 0) / 1000
                    
                    # Rate metrics
                    rates = aggregate.get('rates', {})
                    metrics['requests_per_second'] = rates.get('http.request_rate', 0)
                    
                    # Error metrics
                    metrics['errors'] = counters.get('errors.total', 0)
                    
        except Exception as e:
            self.log.warning(f"Could not parse Artillery JSON: {e}")
        
        return metrics
    
    async def run_aiohttp_load_test(self, url: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run simple concurrent load test using aiohttp."""
        try:
            # Get configuration
            aiohttp_config = config.get('aiohttp', {}) if config else {}
            requests = aiohttp_config.get('requests', 20)  # Reduced from 50 for faster tests
            concurrency = aiohttp_config.get('concurrency', 3)  # Reduced from 5 for faster tests
            # Debug override: allow quick test via env PERF_DEBUG=1 to slash workload
            if os.getenv('PERF_DEBUG','0') in ('1','true','True'):
                requests = min(requests, 10)
                concurrency = min(concurrency, 2)
            
            self.log.info(f"Running aiohttp load test: {requests} requests, {concurrency} concurrent on {url}")
            await self.send_progress('aiohttp_start', f'aiohttp load test starting: {url}', 
                                   requests=requests, concurrency=concurrency)
            
            semaphore = asyncio.Semaphore(concurrency)
            response_times = []
            status_codes = []
            errors = []
            
            async def single_request(session: aiohttp.ClientSession):
                async with semaphore:
                    try:
                        start_time = datetime.now()
                        async with session.get(url) as response:
                            await response.read()
                            end_time = datetime.now()
                            response_time = (end_time - start_time).total_seconds() * 1000
                            response_times.append(response_time)
                            status_codes.append(response.status)
                            return True
                    except Exception as e:
                        errors.append(str(e))
                        return False
            
            start_ts = time.time()
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:  # Reduced from 120s
                tasks = [single_request(session) for _ in range(requests)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            duration = time.time() - start_ts
            
            # Calculate metrics
            successful_requests = sum(1 for r in results if r is True)
            failed_requests = len(results) - successful_requests
            
            metrics = {
                'status': 'success',
                'tool': 'aiohttp',
                'executed': True,
                'total_issues': 0,
                'url': url,
                'requests': requests,
                'successful_requests': successful_requests,
                'failed_requests': failed_requests,
                'success_rate': (successful_requests / requests) * 100 if requests > 0 else 0,
                'configuration': {'requests': requests, 'concurrency': concurrency},
                'raw': {
                    'duration': duration,
                    'requests_attempted': requests,
                    'errors': errors[:20]
                }
            }
            
            if response_times:
                metrics.update({
                    'avg_response_time': statistics.mean(response_times),
                    'min_response_time': min(response_times),
                    'max_response_time': max(response_times),
                    'median_response_time': statistics.median(response_times)
                })
            
            await self.send_progress('aiohttp_complete', f'aiohttp load test completed: {url}', 
                                   success_rate=metrics['success_rate'])
            return metrics
            
        except Exception as e:
            return {'status': 'error', 'tool': 'aiohttp', 'executed': True, 'error': str(e), 'url': url}
    
    async def test_application_performance(self, model_slug: str, app_number: int, target_urls: List[str], 
                                         config: Optional[Dict[str, Any]] = None, 
                                         selected_tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Perform comprehensive performance testing on application."""
        try:
            self.log.info("═" * 80)
            self.log.info(f"⚡ PERFORMANCE TESTING: {model_slug} app {app_number}")
            self.log.info(f"   🎯 Targets: {', '.join(target_urls)}")
            self.log.info(f"   🔧 Selected Tools: {', '.join(selected_tools) if selected_tools else 'all available'}")
            self.log.info("═" * 80)
            
            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'tools_used': [],
                'target_urls': target_urls,
                'results': {}
            }
            tool_runs: Dict[str, Dict[str, Any]] = {}
            
            # Determine which tools to run
            available_tools = {'locust', 'ab', 'aiohttp', 'artillery'} & set(self.available_tools)
            if selected_tools:
                # Map tool names
                tool_mapping = {
                    'locust-performance': 'locust',
                    'ab-load-test': 'ab', 
                    'aiohttp-load': 'aiohttp',
                    'artillery-load': 'artillery'
                }
                requested_tools = {tool_mapping.get(tool, tool) for tool in selected_tools}
                tools_to_run = available_tools & requested_tools
            else:
                tools_to_run = available_tools
            
            self.log.info("═" * 80)
            self.log.info("🔌 CONNECTIVITY & LOAD TESTING PHASE")
            self.log.info("═" * 80)
            self.log.info(f"   🔧 Available Tools: {list(tools_to_run)}")
            
            # Test each URL
            tool_summary: Dict[str, Dict[str, Any]] = {}
            for url in target_urls:
                self.log.info(f"\n━━━ Testing URL: {url} ━━━")
                url_results = {}
                
                # 1. Quick connectivity check
                connectivity = await self.simple_response_check(url)
                url_results['connectivity'] = connectivity

                force_run = False
                if connectivity['status'] != 'success':
                    # Fallback: still attempt aiohttp synthetic test (may reveal transient issues)
                    self.log.warning(f"Connectivity failed for {url}; attempting forced aiohttp test anyway")
                    force_run = True
                
                # Use the working URL from connectivity check
                working_url = connectivity.get('working_url') or url
                
                # 2. Run selected tools
                if 'aiohttp' in tools_to_run and (connectivity['status'] == 'success' or force_run):
                    self.log.info(f"Running aiohttp test on {working_url}")
                    aiohttp_result = await self.run_aiohttp_load_test(working_url, config)
                    url_results['aiohttp'] = aiohttp_result
                    tool_summary['aiohttp'] = {k: aiohttp_result.get(k) for k in ('status','tool','executed','total_issues') if k in aiohttp_result}
                    if aiohttp_result.get('status') == 'success':
                        results['tools_used'].append('aiohttp')
                    tool_runs['aiohttp'] = aiohttp_result
                elif 'aiohttp' in tools_to_run and 'aiohttp' not in url_results:
                    # Synthetic failure record so downstream always sees a tool entry
                    synth = {
                        'status': 'error',
                        'tool': 'aiohttp',
                        'executed': False,
                        'total_issues': 0,
                        'url': working_url,
                        'error': connectivity.get('error', 'unreachable'),
                        'raw': {
                            'duration': 0.0,
                            'requests_attempted': 0,
                            'errors': [connectivity.get('error', 'unreachable')]
                        }
                    }
                    url_results['aiohttp'] = synth
                    tool_summary['aiohttp'] = {k: synth.get(k) for k in ('status','tool','executed','total_issues')}
                    tool_runs['aiohttp'] = synth
                
                if 'ab' in tools_to_run and connectivity['status'] == 'success':
                    self.log.info(f"Running Apache Bench test on {working_url}")
                    ab_result = await self.run_apache_bench_test(working_url, config)
                    url_results['ab'] = ab_result
                    tool_summary['ab'] = {k: ab_result.get(k) for k in ('status','tool','executed','total_issues') if k in ab_result}
                    if ab_result.get('status') == 'success':
                        results['tools_used'].append('ab')
                    tool_runs['ab'] = ab_result
                
                if 'locust' in tools_to_run and connectivity['status'] == 'success':
                    self.log.info(f"Running Locust test on {working_url}")
                    locust_result = await self.run_locust_test(working_url, config)
                    url_results['locust'] = locust_result
                    tool_summary['locust'] = {k: locust_result.get(k) for k in ('status','tool','executed','total_issues') if k in locust_result}
                    if locust_result.get('status') == 'success':
                        results['tools_used'].append('locust')
                    tool_runs['locust'] = locust_result
                
                if 'artillery' in tools_to_run and connectivity['status'] == 'success':
                    self.log.info(f"Running Artillery test on {working_url}")
                    artillery_result = await self.run_artillery_test(working_url, config)
                    url_results['artillery'] = artillery_result
                    tool_summary['artillery'] = {k: artillery_result.get(k) for k in ('status','tool','executed','total_issues') if k in artillery_result}
                    if artillery_result.get('status') == 'success':
                        results['tools_used'].append('artillery')
                    tool_runs['artillery'] = artillery_result
                
                results['results'][url] = url_results
            
            # Remove duplicates from tools_used
            results['tools_used'] = list(set(results['tools_used']))
            
            # Attach summarized tool statuses for easier upstream normalization
            # If we have no tool_summary at all, create a synthetic connectivity entry
            if not tool_summary and target_urls:
                tool_summary['connectivity'] = {
                    'tool': 'connectivity',
                    'status': 'error',
                    'executed': True,
                    'total_issues': 0,
                    'summary': 'No performance tools executed'
                }
                tool_runs.setdefault('connectivity', tool_summary['connectivity'])

            if tool_runs:
                results['results']['tool_runs'] = tool_runs
            results['tool_results'] = tool_summary
            # Provide overall status hint
            results['status'] = 'success' if any(t.get('status') == 'success' for t in tool_summary.values()) else 'partial' if tool_summary else 'error'

            self.log.info(f"Performance testing completed. Tools used: {results['tools_used']}")
            return results
            
        except Exception as e:
            self.log.error(f"Performance testing failed: {e}")
            return {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e),
                'tools_used': []
            }
    
    async def handle_message(self, websocket, message_data):
        """Handle incoming WebSocket messages."""
        try:
            # Accept both legacy and new message types for compatibility
            message_type = message_data.get('type')
            if message_type in ['performance_test', 'performance_analysis']:
                model_slug = message_data.get('model_slug', 'unknown')
                app_number = message_data.get('app_number', 0)
                
                # Handle both target_urls (new format) and target_url (legacy format)
                target_urls = message_data.get('target_urls', [])
                if not isinstance(target_urls, list):
                    target_urls = [target_urls] if target_urls else []
                # Filter out any None entries to satisfy type expectations
                target_urls = [u for u in target_urls if isinstance(u, str) and u]
                if not target_urls and message_data.get('target_url'):
                    target_urls = [message_data.get('target_url')]
                # Final defensive cast
                target_urls = [str(u) for u in target_urls]
                
                # Handle tools field from analyzer_manager
                selected_tools = message_data.get('tools', message_data.get('selected_tools', []))
                
                # Build config from message data
                config = message_data.get('config', {})
                if message_data.get('users'):
                    config.setdefault('locust', {})['users'] = message_data.get('users')
                if message_data.get('duration'):
                    config.setdefault('locust', {})['run_time'] = f"{message_data.get('duration')}s"
                
                self.log.info(f"Received performance test request for {model_slug} app {app_number}")
                self.log.info(f"[PERF-TEST] Target URLs: {target_urls}")
                self.log.info(f"[PERF-TEST] Selected tools: {selected_tools}")
                
                result = await self.test_application_performance(
                    model_slug, app_number, target_urls, config, selected_tools
                )
                
                # Log result summary for debugging
                self.log.info(f"[PERF-RESULT] Status: {result.get('status')}")
                self.log.info(f"[PERF-RESULT] Tools used: {result.get('tools_used')}")
                if 'results' in result and 'tool_runs' in result['results']:
                    self.log.info(f"[PERF-RESULT] Tool runs: {list(result['results']['tool_runs'].keys())}")
                
                # Ensure tool_runs surfaced (some callers rely on this path)
                if 'results' in result and 'tool_runs' not in result['results']:
                    # If individual URL sections exist, aggregate minimal tool list
                    tool_runs = {}
                    for url, url_res in result.get('results', {}).items():
                        if not isinstance(url_res, dict):
                            continue
                        for tool_name in ['aiohttp','ab','locust']:
                            tdata = url_res.get(tool_name)
                            if isinstance(tdata, dict) and tdata.get('tool'):
                                tool_runs[tool_name] = tdata
                    if tool_runs:
                        result['results']['tool_runs'] = tool_runs
                        self.log.info(f"[PERF-RESULT] Aggregated tool_runs: {list(tool_runs.keys())}")

                wrapped = {
                    'type': 'performance_analysis_result',
                    'status': 'success',
                    'service': self.info.name,
                    'analysis': result,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.log.info(f"[PERF-RESPONSE] Sending response with analysis status={result.get('status')}")
                await websocket.send(json.dumps(wrapped))
            
            elif message_type == 'health_check':
                await websocket.send(json.dumps({
                    'type': 'health_response',
                    'status': 'healthy',
                    'service': 'performance-tester',
                    'version': '2.0.0',
                    'available_tools': self.available_tools,
                    'timestamp': datetime.now().isoformat()
                }))
            
            else:
                await websocket.send(json.dumps({
                    'type': 'error',
                    'error': f'Unknown message type: {message_type}'
                }))
                
        except Exception as e:
            self.log.error(f"Error handling message: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'error': str(e)
            }))

async def main():
    service = PerformanceTester()
    await service.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass