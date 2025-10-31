#!/usr/bin/env python3
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
from zapv2 import ZAPv2

logger = logging.getLogger(__name__)


class ZAPScanner:
    """OWASP ZAP security scanner wrapper."""
    
    def __init__(self, zap_path: str = '/zap/ZAP_2.15.0', api_key: Optional[str] = None):
        """
        Initialize ZAP scanner.
        
        Args:
            zap_path: Path to ZAP installation directory
            api_key: ZAP API key (auto-generated if None)
        """
        self.zap_path = zap_path
        self.api_key = api_key or 'changeme-zap-api-key'
        self.zap_port = 8090
        self.zap_process = None
        self.zap = None
        # Use a dedicated home directory to avoid conflicts
        self.zap_home = '/tmp/zap_home'
    
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
    
    def spider_scan(self, url: str, max_depth: int = 2, max_duration: int = 60) -> Dict[str, Any]:
        """
        Run ZAP spider scan on target URL.
        
        Args:
            url: Target URL to spider
            max_depth: Maximum spider depth
            max_duration: Maximum scan duration in seconds
            
        Returns:
            Spider scan results
        """
        try:
            logger.info(f"Starting spider scan on {url}")
            
            # Start the spider (note: ZAP API uses 'maxchildren' and no 'maxduration' in some versions)
            scan_id = self.zap.spider.scan(url, maxchildren=max_depth)
            
            # Wait for spider to complete
            start_time = time.time()
            while int(self.zap.spider.status(scan_id)) < 100:
                if time.time() - start_time > max_duration:
                    logger.warning(f"Spider scan timeout after {max_duration}s")
                    self.zap.spider.stop(scan_id)
                    break
                time.sleep(2)
            
            # Get spider results
            urls_found = self.zap.spider.results(scan_id)
            
            logger.info(f"Spider scan completed. Found {len(urls_found)} URLs")
            
            return {
                'status': 'success',
                'scan_id': scan_id,
                'urls_found': len(urls_found),
                'urls': urls_found[:100]  # Limit to first 100
            }
            
        except Exception as e:
            logger.error(f"Spider scan failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
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
        Run a quick ZAP scan (baseline or quick).
        
        Args:
            url: Target URL to scan
            scan_type: 'baseline' or 'quick' scan
            
        Returns:
            Scan results with alerts
        """
        try:
            logger.info(f"Starting {scan_type} scan on {url}")
            
            # Access the URL
            self.zap.urlopen(url)
            time.sleep(2)
            
            if scan_type == 'baseline':
                # Spider + Passive scan
                spider_result = self.spider_scan(url, max_depth=1, max_duration=30)
                time.sleep(5)  # Let passive scanner analyze
                alerts = self.zap.core.alerts(baseurl=url)
            else:
                # Just passive scan
                alerts = self.zap.core.alerts(baseurl=url)
            
            logger.info(f"{scan_type.capitalize()} scan completed. Found {len(alerts)} alerts")
            
            return {
                'status': 'success',
                'scan_type': scan_type,
                'total_alerts': len(alerts),
                'alerts': alerts,
                'url': url
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
