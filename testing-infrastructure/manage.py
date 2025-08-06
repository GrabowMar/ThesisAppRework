#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testing Infrastructure Management Script
========================================

Script to manage the containerized testing infrastructure.
Provides commands to build, deploy, monitor, and manage testing containers.
"""
import argparse
import json
import subprocess
import sys
import time
import os
from pathlib import Path
from typing import Dict, List, Optional

# Set UTF-8 encoding for Windows compatibility
if sys.platform.startswith('win'):
    import io
    # Set stdout and stderr to use UTF-8 encoding
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    else:
        # Fallback for older Python versions
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    # Set console code page to UTF-8 on Windows
    try:
        os.system('chcp 65001 >nul 2>&1')
    except Exception:
        pass

# Safe print function that handles encoding issues on Windows
def safe_print(message: str) -> None:
    """Print message with fallback for encoding issues."""
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback: replace problematic characters with ASCII equivalents
        safe_message = message.encode('ascii', 'replace').decode('ascii')
        print(safe_message)

# Import local testing models
try:
    from local_testing_models import LocalTestingAPIClient, TestType, TestingStatus, ServiceHealth
    SyncTestingAPIClient = LocalTestingAPIClient  # Use local client as replacement
except ImportError:
    print("Warning: Testing API client not available. Some features may be limited.")
    SyncTestingAPIClient = None
    TestType = None
    TestingStatus = None
    ServiceHealth = None


class TestingInfrastructureManager:
    """Manager for containerized testing infrastructure."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.compose_file = base_path / "docker-compose.yml"
        self.client = SyncTestingAPIClient() if SyncTestingAPIClient else None
    
    def build_containers(self, rebuild: bool = False) -> bool:
        """Build all testing containers."""
        safe_print("[BUILD] Building testing containers...")
        
        cmd = ["docker-compose", "-f", str(self.compose_file), "build"]
        if rebuild:
            cmd.append("--no-cache")
        
        try:
            result = subprocess.run(cmd, cwd=self.base_path, capture_output=True, text=True)
            if result.returncode == 0:
                safe_print("[SUCCESS] All containers built successfully")
                return True
            else:
                safe_print(f"[ERROR] Build failed: {result.stderr}")
                return False
        except Exception as e:
            safe_print(f"[ERROR] Build error: {e}")
            return False
    
    def start_services(self, services: Optional[List[str]] = None) -> bool:
        """Start testing services."""
        safe_print("[START] Starting testing services...")
        
        cmd = ["docker-compose", "-f", str(self.compose_file), "up", "-d"]
        if services:
            cmd.extend(services)
        
        try:
            result = subprocess.run(cmd, cwd=self.base_path, capture_output=True, text=True)
            if result.returncode == 0:
                safe_print("[SUCCESS] Services started successfully")
                
                # Wait for services to be ready
                safe_print("[INFO] Waiting for services to be ready...")
                time.sleep(10)
                
                # Check health
                health = self.check_health()
                healthy_services = sum(1 for h in health.values() if h)
                total_services = len(health)
                
                if healthy_services == total_services:
                    safe_print("[SUCCESS] All services are healthy")
                    return True
                elif healthy_services >= total_services * 0.75:  # At least 75% healthy
                    safe_print(f"[WARNING] Most services are healthy ({healthy_services}/{total_services})")
                    return True
                else:
                    safe_print(f"[ERROR] Too many services are unhealthy: {health}")
                    return False
            else:
                safe_print(f"[ERROR] Start failed: {result.stderr}")
                return False
        except Exception as e:
            safe_print(f"[ERROR] Start error: {e}")
            return False
    
    def stop_services(self, services: Optional[List[str]] = None) -> bool:
        """Stop testing services."""
        safe_print("[STOP] Stopping testing services...")
        
        cmd = ["docker-compose", "-f", str(self.compose_file), "down"]
        if services:
            # For individual services, use stop instead of down
            cmd = ["docker-compose", "-f", str(self.compose_file), "stop"] + services
        
        try:
            result = subprocess.run(cmd, cwd=self.base_path, capture_output=True, text=True)
            if result.returncode == 0:
                safe_print("[SUCCESS] Services stopped successfully")
                return True
            else:
                safe_print(f"[ERROR] Stop failed: {result.stderr}")
                return False
        except Exception as e:
            safe_print(f"[ERROR] Stop error: {e}")
            return False
    
    def restart_services(self, services: Optional[List[str]] = None) -> bool:
        """Restart testing services."""
        safe_print("[RESTART] Restarting testing services...")
        
        cmd = ["docker-compose", "-f", str(self.compose_file), "restart"]
        if services:
            cmd.extend(services)
        
        try:
            result = subprocess.run(cmd, cwd=self.base_path, capture_output=True, text=True)
            if result.returncode == 0:
                safe_print("[SUCCESS] Services restarted successfully")
                return True
            else:
                safe_print(f"[ERROR] Restart failed: {result.stderr}")
                return False
        except Exception as e:
            safe_print(f"[ERROR] Restart error: {e}")
            return False
    
    def check_health(self) -> Dict[str, bool]:
        """Check health of all testing services."""
        safe_print("[HEALTH] Checking service health...")
        
        try:
            if not self.client:
                # Fallback: check container status if client is not available
                print("[WARNING] Testing API client not available, checking container status instead")
                status = self.get_status()
                health = {}
                for service, state in status.items():
                    healthy = state == "running"
                    health[service] = healthy
                    status_text = "[OK]" if healthy else "[FAIL]"
                    print(f"  {status_text} {service}: {'Healthy' if healthy else 'Unhealthy'}")
                return health
            
            health = self.client.health_check()
            
            # Print health status
            for service, healthy in health.items():
                status = "[OK]" if healthy else "[FAIL]"
                print(f"  {status} {service}: {'Healthy' if healthy else 'Unhealthy'}")
            
            return health
        except Exception as e:
            print(f"[ERROR] Health check failed: {e}")
            return {}

    def view_logs(self, service: Optional[str] = None, follow: bool = False) -> None:
        """View logs from testing services."""
        cmd = ["docker-compose", "-f", str(self.compose_file), "logs"]
        if follow:
            cmd.append("-f")
        if service:
            cmd.append(service)
        
        try:
            subprocess.run(cmd, cwd=self.base_path)
        except KeyboardInterrupt:
            print("\n[LOG] Log viewing stopped")

    def get_status(self) -> Dict[str, str]:
        """Get status of all containers."""
        print("[STATUS] Getting container status...")
        
        try:
            result = subprocess.run(
                ["docker-compose", "-f", str(self.compose_file), "ps", "--format", "json"],
                cwd=self.base_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # docker-compose ps --format json returns one JSON object per line, not an array
                containers = []
                if result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        line = line.strip()
                        if line and not line.startswith('time='):  # Skip warning lines
                            try:
                                container = json.loads(line)
                                containers.append(container)
                            except json.JSONDecodeError:
                                # Skip malformed lines
                                continue
                
                status = {}
                for container in containers:
                    name = container.get("Service", "unknown")
                    state = container.get("State", "unknown")
                    status[name] = state
                    
                    # Print status
                    status_icon = "[RUN]" if state == "running" else "[EXIT]" if state == "exited" else "[WAIT]"
                    print(f"  {status_icon} {name}: {state}")
                
                return status
            else:
                print(f"[ERROR] Status check failed: {result.stderr}")
                return {}
        except Exception as e:
            print(f"[ERROR] Status error: {e}")
            return {}
    
    def run_test_suite(self) -> bool:
        """Run comprehensive test suite against containerized services."""
        print("[TEST] Running test suite...")
        
        # Check if services are running
        health = self.check_health()
        if not all(health.values()):
            print("[ERROR] Not all services are healthy. Cannot run tests.")
            return False
        
        # Run security analysis test
        print("  [SECURITY] Testing security analysis...")
        try:
            result = self.client.run_security_analysis("test_model", 1, ["bandit", "safety"])
            if result.status.value == "completed":
                print("    [SUCCESS] Security analysis test passed")
            else:
                print(f"    [ERROR] Security analysis test failed: {result.status}")
                return False
        except Exception as e:
            print(f"    [ERROR] Security analysis test error: {e}")
            return False
        
        # Run performance test
        print("  [PERFORMANCE] Testing performance analysis...")
        try:
            result = self.client.run_performance_test("test_model", 1, "http://localhost:3000", 5)
            if result.status.value == "completed":
                print("    [SUCCESS] Performance test passed")
            else:
                print(f"    [ERROR] Performance test failed: {result.status}")
                return False
        except Exception as e:
            print(f"    [ERROR] Performance test error: {e}")
            return False
        
        # Run ZAP scan test
        print("  [ZAP] Testing ZAP scan...")
        try:
            result = self.client.run_zap_scan("test_model", 1, "http://localhost:3000", "spider")
            if result.status.value == "completed":
                print("    [SUCCESS] ZAP scan test passed")
            else:
                print(f"    [ERROR] ZAP scan test failed: {result.status}")
                return False
        except Exception as e:
            print(f"    [ERROR] ZAP scan test error: {e}")
            return False
        
        print("[SUCCESS] All tests passed!")
        return True
    
    def clean_up(self, volumes: bool = False) -> bool:
        """Clean up containers and optionally volumes."""
        print("[CLEANUP] Cleaning up testing infrastructure...")
        
        cmd = ["docker-compose", "-f", str(self.compose_file), "down"]
        if volumes:
            cmd.extend(["-v", "--remove-orphans"])
        
        try:
            result = subprocess.run(cmd, cwd=self.base_path, capture_output=True, text=True)
            if result.returncode == 0:
                print("[SUCCESS] Cleanup completed successfully")
                
                if volumes:
                    print("[CLEANUP] Volumes removed")
                
                return True
            else:
                print(f"[ERROR] Cleanup failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"[ERROR] Cleanup error: {e}")
            return False
    
    def update_containers(self) -> bool:
        """Update all containers to latest versions."""
        print("[UPDATE] Updating containers...")
        
        # Pull latest images
        try:
            result = subprocess.run(
                ["docker-compose", "-f", str(self.compose_file), "pull"],
                cwd=self.base_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"[ERROR] Pull failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"[ERROR] Pull error: {e}")
            return False
        
        # Rebuild and restart
        if not self.build_containers(rebuild=True):
            return False
        
        if not self.restart_services():
            return False
        
        print("[SUCCESS] Containers updated successfully")
        return True


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="Manage containerized testing infrastructure")
    
    # Get script directory
    script_dir = Path(__file__).parent
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Build command
    build_parser = subparsers.add_parser("build", help="Build testing containers")
    build_parser.add_argument("--rebuild", action="store_true", help="Rebuild without cache")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start testing services")
    start_parser.add_argument("services", nargs="*", help="Specific services to start")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop testing services")
    stop_parser.add_argument("services", nargs="*", help="Specific services to stop")
    
    # Restart command
    restart_parser = subparsers.add_parser("restart", help="Restart testing services")
    restart_parser.add_argument("services", nargs="*", help="Specific services to restart")
    
    # Health command
    subparsers.add_parser("health", help="Check service health")
    
    # Status command
    subparsers.add_parser("status", help="Get container status")
    
    # Logs command
    logs_parser = subparsers.add_parser("logs", help="View service logs")
    logs_parser.add_argument("service", nargs="?", help="Specific service to view")
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow log output")
    
    # Test command
    subparsers.add_parser("test", help="Run test suite")
    
    # Clean command
    clean_parser = subparsers.add_parser("clean", help="Clean up containers")
    clean_parser.add_argument("--volumes", action="store_true", help="Remove volumes too")
    
    # Update command
    subparsers.add_parser("update", help="Update containers to latest versions")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = TestingInfrastructureManager(script_dir)
    
    try:
        if args.command == "build":
            success = manager.build_containers(args.rebuild)
        elif args.command == "start":
            success = manager.start_services(args.services or None)
        elif args.command == "stop":
            success = manager.stop_services(args.services or None)
        elif args.command == "restart":
            success = manager.restart_services(args.services or None)
        elif args.command == "health":
            manager.check_health()
            success = True
        elif args.command == "status":
            manager.get_status()
            success = True
        elif args.command == "logs":
            manager.view_logs(args.service, args.follow)
            success = True
        elif args.command == "test":
            success = manager.run_test_suite()
        elif args.command == "clean":
            success = manager.clean_up(args.volumes)
        elif args.command == "update":
            success = manager.update_containers()
        else:
            print(f"[ERROR] Unknown command: {args.command}")
            success = False
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n[CANCEL] Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
