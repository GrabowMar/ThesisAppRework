#!/usr/bin/env python3
# pyright: reportOptionalMemberAccess=false
"""
OWASP ZAP Integration Module
============================

Provides real ZAP scanning capabilities using the ZAP daemon and Python API.
"""

import os
import time
import logging
import subprocess
from typing import Dict, List, Any, Optional
from zapv2 import ZAPv2  # type: ignore[import-not-found]
import urllib3

# Suppress SSL warnings when testing local apps without valid certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Try to import ConfigLoader for enhanced configuration
try:
    import sys
    from pathlib import Path
    # Add parent paths for config_loader
    analyzer_root = Path(__file__).resolve().parent.parent.parent
    if str(analyzer_root) not in sys.path:
        sys.path.insert(0, str(analyzer_root))
    from config_loader import get_config_loader, ConfigLoader
    CONFIG_LOADER_AVAILABLE = True
except ImportError:
    CONFIG_LOADER_AVAILABLE = False


class ZAPScanner:
    """OWASP ZAP security scanner wrapper."""
    
    def __init__(self, zap_path: str = '/zap/ZAP_2.16.1', api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize ZAP scanner.
        
        Args:
            zap_path: Path to ZAP installation directory
            api_key: ZAP API key (auto-generated if None)
            config: Optional runtime configuration overrides
        """
        self.zap_path = zap_path
        self.api_key = api_key or 'changeme-zap-api-key'
        self.zap_port = 8090
        self.zap_process = None
        self.zap = None
        # Use a dedicated home directory to avoid conflicts
        self.zap_home = '/tmp/zap_home'
        
        # Load configuration with ConfigLoader
        self._load_config(config)
    
    def _load_config(self, runtime_config: Optional[Dict[str, Any]] = None):
        """
        Load ZAP configuration from config files with runtime overrides.
        
        Args:
            runtime_config: Optional runtime configuration overrides from analysis wizard
        """
        if CONFIG_LOADER_AVAILABLE:
            loader = get_config_loader()
            self.config = loader.load_config('zap', 'dynamic', runtime_config)
        else:
            # Fallback defaults with enhanced settings
            self.config = {
                'spider': {
                    'max_depth': 10,  # Enhanced from 5
                    'thread_count': 5,
                    'max_duration': 300,
                    'max_children': 0,  # Unlimited
                },
                'passive_scan': {
                    'wait_time': 30,  # Enhanced from 10
                },
                'active_scan': {
                    'enabled': False,  # Off by default for safety
                    'max_duration': 300,
                },
                'ajax_spider': {
                    'enabled': False,  # Disabled by default (avoids browser/Selenium dependency)
                    'max_duration': 60,
                },
                **(runtime_config or {})
            }
        
        # Extract commonly used config values
        spider_config = self.config.get('spider', {})
        self.default_max_depth = spider_config.get('max_depth', 10)
        self.default_thread_count = spider_config.get('thread_count', 5)
        self.default_max_duration = spider_config.get('max_duration', 300)
        self.passive_wait_time = self.config.get('passive_scan', {}).get('wait_time', 30)
        self.ajax_spider_enabled = self.config.get('ajax_spider', {}).get('enabled', False)
        
        logger.info(f"ZAP config loaded: spider_depth={self.default_max_depth}, ajax_spider={self.ajax_spider_enabled}")
    
    def connect_to_zap(self, timeout: int = 10) -> bool:
        """
        Connect to an already-running ZAP daemon.
        
        Args:
            timeout: Maximum time to wait for connection (seconds)
            
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            logger.info(f"Connecting to ZAP daemon on port {self.zap_port}...")
            
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # Try to connect to ZAP API
                    test_zap = ZAPv2(apikey=self.api_key, proxies={
                        'http': f'http://127.0.0.1:{self.zap_port}',
                        'https': f'http://127.0.0.1:{self.zap_port}'
                    })
                    version = test_zap.core.version
                    logger.info(f"Connected to ZAP daemon successfully (version: {version})")
                    self.zap = test_zap
                    return True
                except Exception as e:
                    logger.debug(f"Waiting for ZAP connection... ({e})")
                    time.sleep(1)
            
            logger.error("Failed to connect to ZAP daemon within timeout")
            return False
            
        except Exception as e:
            logger.error(f"Failed to connect to ZAP daemon: {e}")
            return False
        
    def start_zap_daemon(self, timeout: int = 90) -> bool:
        """
        Start ZAP in daemon mode.
        
        Args:
            timeout: Maximum time to wait for ZAP to start (seconds) - default 90s for full initialization
            
        Returns:
            True if ZAP started successfully, False otherwise
        """
        try:
            zap_sh = os.path.join(self.zap_path, 'zap.sh')
            
            if not os.path.exists(zap_sh):
                logger.error(f"ZAP executable not found at {zap_sh}")
                return False
            
            # Start ZAP in daemon mode (headless) with virtual X display
            # Use a dedicated home directory to avoid lock conflicts
            cmd = [
                'xvfb-run',
                '-a',  # Auto select display number
                zap_sh,
                '-daemon',
                '-port', str(self.zap_port),
                '-dir', self.zap_home,  # Dedicated home directory
                '-config', f'api.key={self.api_key}',
                '-config', 'api.addrs.addr.name=.*',
                '-config', 'api.addrs.addr.regex=true',
                '-config', 'ajaxSpider.browserId=htmlunit',
            ]
            
            logger.info(f"Starting ZAP daemon on port {self.zap_port} with xvfb (home: {self.zap_home})...")
            logger.info(f"ZAP command: {' '.join(cmd)}")
            self.zap_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info(f"ZAP process started with PID: {self.zap_process.pid}")
            
            # Give ZAP a moment to start and check if it crashes immediately
            time.sleep(3)
            poll_result = self.zap_process.poll()
            if poll_result is not None:
                logger.error(f"ZAP process exited immediately with code: {poll_result}")
                try:
                    stdout, stderr = self.zap_process.communicate(timeout=1)
                    logger.error(f"ZAP stdout: {stdout[:1000]}")
                    logger.error(f"ZAP stderr: {stderr[:1000]}")
                except Exception as e:
                    logger.error(f"Could not read ZAP output: {e}")
                return False
            
            # Wait for ZAP to be ready
            start_time = time.time()
            attempt = 0
            while time.time() - start_time < timeout:
                attempt += 1
                elapsed = int(time.time() - start_time)
                try:
                    # Try to connect to ZAP API
                    test_zap = ZAPv2(apikey=self.api_key, proxies={
                        'http': f'http://127.0.0.1:{self.zap_port}',
                        'https': f'http://127.0.0.1:{self.zap_port}'
                    })
                    version = test_zap.core.version
                    logger.info(f"ZAP daemon started successfully after {elapsed}s (version: {version})")
                    self.zap = test_zap
                    return True
                except Exception as e:
                    if attempt % 5 == 0:  # Log every 5th attempt
                        logger.info(f"Waiting for ZAP to start... ({elapsed}s elapsed, attempt {attempt})")
                    time.sleep(2)
            
            logger.error("ZAP daemon failed to start within timeout")
            # Capture stdout/stderr from the process if available
            if self.zap_process:
                try:
                    stdout, stderr = self.zap_process.communicate(timeout=1)
                    logger.error(f"ZAP stdout: {stdout[:500]}")
                    logger.error(f"ZAP stderr: {stderr[:500]}")
                except Exception as log_err:
                    logger.warning(f"Could not capture ZAP output: {log_err}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to start ZAP daemon: {e}")
            return False
    
    def stop_zap_daemon(self):
        """Stop the ZAP daemon."""
        try:
            if self.zap:
                logger.info("Shutting down ZAP daemon...")
                self.zap.core.shutdown()
            
            if self.zap_process:
                self.zap_process.terminate()
                self.zap_process.wait(timeout=10)
                logger.info("ZAP daemon stopped")
        except Exception as e:
            logger.warning(f"Error stopping ZAP daemon: {e}")
            if self.zap_process:
                self.zap_process.kill()
    
    def spider_scan(self, url: str, max_depth: Optional[int] = None, max_duration: Optional[int] = None, max_children: int = 0) -> Dict[str, Any]:
        """
        Run ZAP spider scan on target URL with thorough coverage.
        
        Args:
            url: Target URL to spider
            max_depth: Maximum spider depth (default from config: 10)
            max_duration: Maximum scan duration in seconds (default from config: 300s)
            max_children: Maximum number of children to spider (0 = unlimited, ZAP default)
            
        Returns:
            Spider scan results
        """
        try:
            # Use config values as defaults
            actual_max_depth = max_depth if max_depth is not None else self.default_max_depth
            actual_max_duration = max_duration if max_duration is not None else self.default_max_duration
            actual_thread_count = self.default_thread_count
            
            logger.info(f"Starting comprehensive spider scan on {url} (max_depth={actual_max_depth}, max_duration={actual_max_duration}s, threads={actual_thread_count})")
            
            # Configure spider for thorough scanning
            self.zap.spider.set_option_max_depth(actual_max_depth)
            self.zap.spider.set_option_thread_count(actual_thread_count)
            
            # Start the traditional spider
            # maxchildren=0 means no limit (ZAP default behavior)
            scan_id = self.zap.spider.scan(url, maxchildren=max_children, recurse=True, subtreeonly=False)
            logger.info(f"Spider scan started with ID: {scan_id}")
            
            # Wait for spider to complete with progress updates
            start_time = time.time()
            last_progress = 0
            while True:
                progress = int(self.zap.spider.status(scan_id))
                elapsed = int(time.time() - start_time)
                
                # Log progress every 20%
                if progress >= last_progress + 20:
                    logger.info(f"Spider progress: {progress}% (elapsed: {elapsed}s)")
                    last_progress = progress
                
                if progress >= 100:
                    break
                    
                if elapsed > actual_max_duration:
                    logger.warning(f"Spider scan timeout after {actual_max_duration}s (progress: {progress}%)")
                    self.zap.spider.stop(scan_id)
                    break
                    
                time.sleep(3)  # Check every 3 seconds
            
            # Get spider results
            urls_found = self.zap.spider.results(scan_id)
            elapsed_total = int(time.time() - start_time)
            
            logger.info(f"Traditional spider completed in {elapsed_total}s. Found {len(urls_found)} URLs")
            
            # Run AJAX spider if enabled (discovers JavaScript-rendered content)
            ajax_urls = []
            if self.ajax_spider_enabled:
                ajax_result = self._run_ajax_spider(url)
                if ajax_result.get('status') == 'success':
                    ajax_urls = ajax_result.get('urls', [])
                    logger.info(f"AJAX spider discovered {len(ajax_urls)} additional URLs")
            
            # Combine URLs from both spiders
            all_urls = list(set(urls_found + ajax_urls))
            
            logger.info(f"Spider scan completed in {int(time.time() - start_time)}s. Total unique URLs: {len(all_urls)}")
            
            return {
                'status': 'success',
                'scan_id': scan_id,
                'urls_found': len(all_urls),
                'urls': all_urls,
                'traditional_urls': len(urls_found),
                'ajax_urls': len(ajax_urls),
                'duration': int(time.time() - start_time),
                'max_depth': actual_max_depth,
                'config_used': {
                    'max_depth': actual_max_depth,
                    'max_duration': actual_max_duration,
                    'thread_count': actual_thread_count,
                    'ajax_spider_enabled': self.ajax_spider_enabled
                }
            }
            
        except Exception as e:
            logger.error(f"Spider scan failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _run_ajax_spider(self, url: str) -> Dict[str, Any]:
        """
        Run AJAX spider to discover JavaScript-rendered content.
        
        Args:
            url: Target URL to spider
            
        Returns:
            AJAX spider results
        """
        try:
            ajax_config = self.config.get('ajax_spider', {})
            ajax_max_duration = ajax_config.get('max_duration', 60)
            
            logger.info(f"Starting AJAX spider on {url} (max_duration={ajax_max_duration}s)")
            
            # Start AJAX spider
            self.zap.ajaxSpider.scan(url)
            
            # Wait for completion with timeout
            start_time = time.time()
            while self.zap.ajaxSpider.status == 'running':
                elapsed = int(time.time() - start_time)
                if elapsed > ajax_max_duration:
                    logger.warning(f"AJAX spider timeout after {ajax_max_duration}s")
                    self.zap.ajaxSpider.stop()
                    break
                time.sleep(2)
            
            # Get results
            results = self.zap.ajaxSpider.results()
            urls = [r.get('requestHeader', '').split(' ')[1] for r in results if 'requestHeader' in r]
            # Filter out empty strings and duplicates
            urls = list(set(u for u in urls if u and u.startswith('http')))
            
            return {
                'status': 'success',
                'urls': urls,
                'duration': int(time.time() - start_time)
            }
            
        except Exception as e:
            logger.warning(f"AJAX spider failed (non-critical): {e}")
            return {
                'status': 'error',
                'error': str(e),
                'urls': []
            }
    
    def active_scan(self, url: str, max_duration: int = 180) -> Dict[str, Any]:
        """
        Run ZAP active scan (penetration testing) on target URL.
        
        Args:
            url: Target URL to scan
            max_duration: Maximum scan duration in seconds
            
        Returns:
            Active scan results
        """
        try:
            logger.info(f"Starting active scan on {url}")
            
            # Access the URL first
            self.zap.urlopen(url)
            time.sleep(2)
            
            # Start active scan
            scan_id = self.zap.ascan.scan(url)
            
            # Wait for scan to complete
            start_time = time.time()
            while int(self.zap.ascan.status(scan_id)) < 100:
                if time.time() - start_time > max_duration:
                    logger.warning(f"Active scan timeout after {max_duration}s")
                    self.zap.ascan.stop(scan_id)
                    break
                progress = self.zap.ascan.status(scan_id)
                logger.debug(f"Active scan progress: {progress}%")
                time.sleep(5)
            
            # Get alerts
            alerts = self.zap.core.alerts(baseurl=url)
            
            logger.info(f"Active scan completed. Found {len(alerts)} alerts")
            
            return {
                'status': 'success',
                'scan_id': scan_id,
                'total_alerts': len(alerts),
                'alerts': alerts
            }
            
        except Exception as e:
            logger.error(f"Active scan failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def passive_scan(self, url: str, wait_time: int = 10) -> Dict[str, Any]:
        """
        Run ZAP passive scan on target URL.
        
        Args:
            url: Target URL to scan
            wait_time: Time to wait for passive scan to analyze traffic
            
        Returns:
            Passive scan results
        """
        try:
            logger.info(f"Starting passive scan on {url}")
            
            # Access the URL
            self.zap.urlopen(url)
            
            # Wait for passive scanner to analyze
            time.sleep(wait_time)
            
            # Get passive scan alerts
            alerts = self.zap.core.alerts(baseurl=url)
            
            logger.info(f"Passive scan completed. Found {len(alerts)} alerts")
            
            return {
                'status': 'success',
                'total_alerts': len(alerts),
                'alerts': alerts
            }
            
        except Exception as e:
            logger.error(f"Passive scan failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def quick_scan(self, url: str, scan_type: str = 'baseline') -> Dict[str, Any]:
        """
        Run a comprehensive ZAP scan (baseline or quick).
        
        Args:
            url: Target URL to scan
            scan_type: 'baseline' (thorough spider + passive) or 'quick' (passive only)
            
        Returns:
            Scan results with alerts
        """
        try:
            logger.info(f"Starting {scan_type} scan on {url}")
            
            # PRE-SCAN: Validate target is reachable before proceeding
            try:
                import requests
                response = requests.get(url, timeout=10, verify=False)
                logger.info(f"Target {url} is reachable (status: {response.status_code})")
            except requests.exceptions.RequestException as e:
                logger.error(f"Target {url} is unreachable: {e}")
                return {
                    'status': 'error',
                    'error': f'Target unreachable: {str(e)}',
                    'url': url,
                    'scan_type': scan_type,
                    'total_alerts': 0,
                    'alerts': []
                }
            
            # Access the URL to initialize
            self.zap.urlopen(url)
            time.sleep(2)
            
            if scan_type == 'baseline':
                # Thorough spider + Passive scan using config values
                logger.info(f"Running comprehensive spider scan (depth={self.default_max_depth}, duration={self.default_max_duration}s)...")
                spider_result = self.spider_scan(url)  # Uses config defaults
                
                # Validate spider found URLs (indicates target was reachable and scannable)
                urls_found = spider_result.get('urls_found', 0)
                if spider_result.get('status') == 'success':
                    logger.info(f"Spider discovered {urls_found} URLs (traditional: {spider_result.get('traditional_urls', 0)}, AJAX: {spider_result.get('ajax_urls', 0)})")
                    if urls_found == 0:
                        logger.warning(f"Spider scan found 0 URLs for {url} - target may be unreachable or have no discoverable content")
                        return {
                            'status': 'error',
                            'error': 'Spider found no URLs - target appears unreachable or returned no content',
                            'url': url,
                            'scan_type': scan_type,
                            'total_alerts': 0,
                            'alerts': []
                        }
                else:
                    logger.error(f"Spider scan failed: {spider_result.get('error', 'Unknown error')}")
                    return {
                        'status': 'error',
                        'error': f"Spider scan failed: {spider_result.get('error', 'Unknown error')}",
                        'url': url,
                        'scan_type': scan_type,
                        'total_alerts': 0,
                        'alerts': []
                    }
                
                # Wait for passive scanner to analyze all spidered URLs
                logger.info(f"Waiting for passive scan analysis (wait_time={self.passive_wait_time}s)...")
                time.sleep(self.passive_wait_time)  # Use config value
                
                # Wait for passive scan queue to empty
                records_remaining = int(self.zap.pscan.records_to_scan)
                wait_count = 0
                max_wait_iterations = max(30, self.passive_wait_time)  # At least 30 or match wait time
                while records_remaining > 0 and wait_count < max_wait_iterations:
                    logger.debug(f"Passive scan: {records_remaining} records remaining")
                    time.sleep(2)
                    records_remaining = int(self.zap.pscan.records_to_scan)
                    wait_count += 1
                
                alerts = self.zap.core.alerts(baseurl=url)
            else:
                # Quick passive scan only
                time.sleep(5)
                alerts = self.zap.core.alerts(baseurl=url)
            
            logger.info(f"{scan_type.capitalize()} scan completed. Found {len(alerts)} alerts")
            
            return {
                'status': 'success',
                'scan_type': scan_type,
                'total_alerts': len(alerts),
                'alerts': alerts,
                'url': url,
                'config_used': {
                    'max_depth': self.default_max_depth,
                    'max_duration': self.default_max_duration,
                    'passive_wait_time': self.passive_wait_time,
                    'ajax_spider_enabled': self.ajax_spider_enabled
                }
            }
            
        except Exception as e:
            logger.error(f"{scan_type} scan failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'url': url
            }
    
    def get_alerts_by_risk(self, url: str) -> Dict[str, List[Dict]]:
        """
        Get alerts grouped by risk level.
        
        Args:
            url: Target URL filter
            
        Returns:
            Dict with alerts grouped by risk: High, Medium, Low, Informational
        """
        try:
            alerts = self.zap.core.alerts(baseurl=url)
            
            grouped = {
                'High': [],
                'Medium': [],
                'Low': [],
                'Informational': []
            }
            
            for alert in alerts:
                risk = alert.get('risk', 'Informational')
                grouped[risk].append(alert)
            
            return grouped
            
        except Exception as e:
            logger.error(f"Failed to get alerts: {e}")
            return {
                'High': [],
                'Medium': [],
                'Low': [],
                'Informational': []
            }
