#!/usr/bin/env python3
"""
Analyzer Infrastructure Startup Script
======================================

This script helps start and manage the comprehensive analyzer infrastructure.

Usage:
    python start_analyzers.py [command]

Commands:
    start    - Start all analyzer services
    stop     - Stop all analyzer services  
    restart  - Restart all analyzer services
    status   - Show status of all services
    logs     - Show logs from all services
    test     - Run comprehensive tests on all services
"""

import subprocess
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalyzerManager:
    """Manager for analyzer Docker infrastructure."""
    
    def __init__(self):
        self.compose_file = Path("docker-compose.yml")
        self.services = [
            'static-analyzer',
            'dynamic-analyzer', 
            'performance-tester',
            'ai-analyzer',
            'security-analyzer'
        ]
    
    def run_command(self, command: list, capture_output: bool = False) -> tuple:
        """Run a shell command and return result."""
        try:
            logger.info(f"Running: {' '.join(command)}")
            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                cwd=Path(__file__).parent
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return 1, "", str(e)
    
    def start_services(self):
        """Start all analyzer services."""
        logger.info("🚀 Starting analyzer infrastructure...")
        
        # Build and start services
        returncode, stdout, stderr = self.run_command([
            'docker-compose', 'up', '--build', '-d'
        ])
        
        if returncode == 0:
            logger.info("✅ All services started successfully!")
            
            # Wait a moment for services to start
            logger.info("⏳ Waiting for services to initialize...")
            time.sleep(10)
            
            # Show status
            self.show_status()
            
        else:
            logger.error(f"❌ Failed to start services: {stderr}")
            return False
        
        return True
    
    def stop_services(self):
        """Stop all analyzer services."""
        logger.info("🛑 Stopping analyzer infrastructure...")
        
        returncode, stdout, stderr = self.run_command([
            'docker-compose', 'down'
        ])
        
        if returncode == 0:
            logger.info("✅ All services stopped successfully!")
        else:
            logger.error(f"❌ Failed to stop services: {stderr}")
            return False
        
        return True
    
    def restart_services(self):
        """Restart all analyzer services."""
        logger.info("🔄 Restarting analyzer infrastructure...")
        
        self.stop_services()
        time.sleep(2)
        return self.start_services()
    
    def show_status(self):
        """Show status of all services."""
        logger.info("📊 Checking service status...")
        
        returncode, stdout, stderr = self.run_command([
            'docker-compose', 'ps'
        ], capture_output=True)
        
        if returncode == 0:
            print("\n" + "=" * 60)
            print("🐳 DOCKER SERVICES STATUS")
            print("=" * 60)
            print(stdout)
        else:
            logger.error(f"❌ Failed to get status: {stderr}")
        
        # Check if ports are accessible
        print("\n📡 PORT ACCESSIBILITY:")
        print("-" * 40)
        
        import socket
        ports = {
            'static-analyzer': 2001,
            'dynamic-analyzer': 2002,
            'performance-tester': 2003,
            'ai-analyzer': 2004,
            'security-analyzer': 2005
        }
        
        for service, port in ports.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                
                if result == 0:
                    print(f"✅ {service}: localhost:{port} - ACCESSIBLE")
                else:
                    print(f"❌ {service}: localhost:{port} - NOT ACCESSIBLE")
            except Exception as e:
                print(f"❌ {service}: localhost:{port} - ERROR: {e}")
    
    def show_logs(self, service: str = None):
        """Show logs from services."""
        if service:
            logger.info(f"📋 Showing logs for {service}...")
            command = ['docker-compose', 'logs', '-f', '--tail=50', service]
        else:
            logger.info("📋 Showing logs from all services...")
            command = ['docker-compose', 'logs', '-f', '--tail=20']
        
        returncode, stdout, stderr = self.run_command(command)
    
    def run_tests(self):
        """Run comprehensive tests on all services."""
        logger.info("🧪 Running comprehensive analyzer tests...")
        
        # Check if test script exists
        test_script = Path("test_all_analyzers.py")
        if not test_script.exists():
            logger.error("❌ Test script not found!")
            return False
        
        # Run tests
        returncode, stdout, stderr = self.run_command([
            'python', 'test_all_analyzers.py'
        ])
        
        if returncode == 0:
            logger.info("✅ All tests completed!")
        else:
            logger.error(f"❌ Tests failed: {stderr}")
        
        return returncode == 0

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        command = 'start'
    else:
        command = sys.argv[1].lower()
    
    manager = AnalyzerManager()
    
    print("🔬 Analyzer Infrastructure Manager")
    print("=" * 50)
    
    if command == 'start':
        success = manager.start_services()
        if success:
            print("\n🎉 Analyzer infrastructure is ready!")
            print("You can now run tests with: python start_analyzers.py test")
        
    elif command == 'stop':
        manager.stop_services()
        
    elif command == 'restart':
        manager.restart_services()
        
    elif command == 'status':
        manager.show_status()
        
    elif command == 'logs':
        service = sys.argv[2] if len(sys.argv) > 2 else None
        manager.show_logs(service)
        
    elif command == 'test':
        manager.run_tests()
        
    else:
        print(f"❌ Unknown command: {command}")
        print("\nAvailable commands:")
        print("  start    - Start all analyzer services")
        print("  stop     - Stop all analyzer services")
        print("  restart  - Restart all analyzer services")
        print("  status   - Show status of all services")
        print("  logs     - Show logs from all services")
        print("  test     - Run comprehensive tests")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Operation interrupted by user")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)
