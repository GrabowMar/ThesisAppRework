#!/usr/bin/env python3
"""
Analyzer Services Launcher
==========================

This script starts all analyzer services in separate processes.
Services include:
- Static Analyzer (port 2001): Code quality and security analysis
- Dynamic Analyzer (port 2002): OWASP ZAP security scanning
- Performance Tester (port 2003): Load testing with Locust
- Security Analyzer (port 2004): Additional security checks
- AI Analyzer (port 2005): OpenRouter-powered analysis

Usage:
    python run_all_services.py [--service SERVICE_NAME] [--stop]

Examples:
    python run_all_services.py                    # Start all services
    python run_all_services.py --service static   # Start only static analyzer
    python run_all_services.py --stop             # Stop all services
"""

import subprocess
import sys
import time
import argparse
from pathlib import Path
from typing import Optional
import signal
import psutil

class ServiceLauncher:
    """Manages analyzer service lifecycle."""
    
    def __init__(self):
        self.services = {
            'static': {
                'name': 'Static Analyzer',
                'port': 2001,
                'path': Path(__file__).parent / 'services' / 'static-analyzer',
                'script': 'main.py',
                'process': None
            },
            'dynamic': {
                'name': 'Dynamic Analyzer', 
                'port': 2002,
                'path': Path(__file__).parent / 'services' / 'dynamic-analyzer',
                'script': 'main.py',
                'process': None
            },
            'performance': {
                'name': 'Performance Tester',
                'port': 2003,
                'path': Path(__file__).parent / 'services' / 'performance-tester',
                'script': 'main.py',
                'process': None
            },
            'security': {
                'name': 'Security Analyzer',
                'port': 2004,
                'path': Path(__file__).parent / 'services' / 'security-analyzer',
                'script': 'main.py',
                'process': None
            },
            'ai': {
                'name': 'AI Analyzer',
                'port': 2005,
                'path': Path(__file__).parent / 'services' / 'ai-analyzer',
                'script': 'main.py',
                'process': None
            }
        }
        self.running_services = {}
        
    def is_port_in_use(self, port: int) -> bool:
        """Check if a port is already in use."""
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == port:
                    return True
            return False
        except Exception:
            return False
    
    def find_process_by_port(self, port: int) -> Optional[int]:
        """Find process ID using a specific port."""
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.pid:
                    return conn.pid
            return None
        except Exception:
            return None
    
    def start_service(self, service_name: str) -> bool:
        """Start a specific analyzer service."""
        if service_name not in self.services:
            print(f"❌ Unknown service: {service_name}")
            return False
            
        service = self.services[service_name]
        
        # Check if port is already in use
        if self.is_port_in_use(service['port']):
            pid = self.find_process_by_port(service['port'])
            print(f"⚠️ Port {service['port']} already in use (PID: {pid})")
            print(f"   {service['name']} may already be running")
            return False
        
        # Check if service directory exists
        if not service['path'].exists():
            print(f"❌ Service directory not found: {service['path']}")
            return False
            
        script_path = service['path'] / service['script']
        if not script_path.exists():
            print(f"❌ Service script not found: {script_path}")
            return False
        
        try:
            print(f"🚀 Starting {service['name']} on port {service['port']}...")
            
            # Start the service process
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(service['path']),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            
            service['process'] = process
            self.running_services[service_name] = process
            
            # Give the service time to start
            time.sleep(2)
            
            # Check if process is still running
            if process.poll() is None:
                print(f"✅ {service['name']} started successfully (PID: {process.pid})")
                return True
            else:
                stdout, stderr = process.communicate()
                print(f"❌ {service['name']} failed to start")
                if stderr:
                    print(f"   Error: {stderr.decode()}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start {service['name']}: {e}")
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """Stop a specific analyzer service."""
        if service_name not in self.running_services:
            # Try to find by port
            service = self.services.get(service_name)
            if service:
                pid = self.find_process_by_port(service['port'])
                if pid:
                    try:
                        process = psutil.Process(pid)
                        process.terminate()
                        process.wait(timeout=5)
                        print(f"✅ Stopped {service['name']} (PID: {pid})")
                        return True
                    except Exception as e:
                        print(f"❌ Failed to stop {service['name']}: {e}")
                        return False
            
            print(f"⚠️ Service {service_name} not running")
            return False
        
        process = self.running_services[service_name]
        service = self.services[service_name]
        
        try:
            print(f"🛑 Stopping {service['name']}...")
            
            if sys.platform == 'win32':
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"   Force killing {service['name']}...")
                process.kill()
                process.wait()
            
            del self.running_services[service_name]
            print(f"✅ {service['name']} stopped")
            return True
            
        except Exception as e:
            print(f"❌ Failed to stop {service['name']}: {e}")
            return False
    
    def start_all_services(self) -> bool:
        """Start all analyzer services."""
        print("🚀 Starting all analyzer services...")
        success_count = 0
        
        for service_name in self.services:
            if self.start_service(service_name):
                success_count += 1
            time.sleep(1)  # Stagger startup
        
        total_services = len(self.services)
        print(f"\n📊 Started {success_count}/{total_services} services")
        
        if success_count == total_services:
            print("🎉 All services started successfully!")
            print("\nService Status:")
            for name, service in self.services.items():
                print(f"  • {service['name']}: http://localhost:{service['port']}")
            print("\nYou can now run tests:")
            print("  python quick_test_demo.py")
            print("  python test_real_models.py --quick")
            return True
        else:
            print("⚠️ Some services failed to start")
            return False
    
    def stop_all_services(self) -> bool:
        """Stop all analyzer services."""
        print("🛑 Stopping all analyzer services...")
        success_count = 0
        
        # Stop running services
        for service_name in list(self.running_services.keys()):
            if self.stop_service(service_name):
                success_count += 1
        
        # Also check for services running on expected ports
        for service_name, service in self.services.items():
            if service_name not in self.running_services:
                pid = self.find_process_by_port(service['port'])
                if pid:
                    try:
                        process = psutil.Process(pid)
                        process.terminate()
                        process.wait(timeout=5)
                        print(f"✅ Stopped orphaned {service['name']} (PID: {pid})")
                        success_count += 1
                    except Exception:
                        pass
        
        print(f"📊 Stopped {success_count} services")
        return True
    
    def status(self):
        """Show status of all analyzer services."""
        print("📊 Analyzer Services Status:")
        print("=" * 50)
        
        for name, service in self.services.items():
            port_in_use = self.is_port_in_use(service['port'])
            pid = self.find_process_by_port(service['port']) if port_in_use else None
            
            status = "🟢 RUNNING" if port_in_use else "🔴 STOPPED"
            pid_info = f" (PID: {pid})" if pid else ""
            
            print(f"{service['name']:20} | Port {service['port']} | {status}{pid_info}")
        
        print("\nTo start services: python run_all_services.py")
        print("To stop services:  python run_all_services.py --stop")

def main():
    parser = argparse.ArgumentParser(description="Analyzer Services Launcher")
    parser.add_argument('--service', help='Start only specified service')
    parser.add_argument('--stop', action='store_true', help='Stop all services')
    parser.add_argument('--status', action='store_true', help='Show service status')
    
    args = parser.parse_args()
    
    launcher = ServiceLauncher()
    
    if args.status:
        launcher.status()
    elif args.stop:
        launcher.stop_all_services()
    elif args.service:
        launcher.start_service(args.service)
    else:
        launcher.start_all_services()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        launcher = ServiceLauncher()
        launcher.stop_all_services()
