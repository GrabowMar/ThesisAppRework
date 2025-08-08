#!/usr/bin/env python3
"""
Analyzer Infrastructure Setup and Management Script
Helps users setup, test, and manage the containerized analyzer services.
"""

import subprocess
import sys
import time
import json
import asyncio
try:
    import websockets
except ImportError:
    websockets = None
from pathlib import Path

def run_command(command, description, check=True):
    """Run a command and handle errors."""
    print(f"\n🔧 {description}")
    print(f"Command: {command}")
    
    try:
        if isinstance(command, str):
            result = subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
        else:
            result = subprocess.run(command, check=check, capture_output=True, text=True)
        
        if result.stdout:
            print("✅ Output:", result.stdout.strip())
        if result.stderr and check:
            print("⚠️ Stderr:", result.stderr.strip())
        
        return result.returncode == 0
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed with code {e.returncode}")
        if e.stdout:
            print("Output:", e.stdout.strip())
        if e.stderr:
            print("Error:", e.stderr.strip())
        return False

def check_prerequisites():
    """Check if Docker and Docker Compose are available."""
    print("🔍 Checking prerequisites...")
    
    # Check Docker
    if not run_command("docker --version", "Checking Docker", check=False):
        print("❌ Docker is not installed or not running")
        print("Please install Docker Desktop: https://www.docker.com/products/docker-desktop")
        return False
    
    # Check Docker Compose
    if not run_command("docker-compose --version", "Checking Docker Compose", check=False):
        if not run_command("docker compose version", "Checking Docker Compose (new syntax)", check=False):
            print("❌ Docker Compose is not available")
            return False
    
    print("✅ Prerequisites satisfied")
    return True

def setup_environment():
    """Setup environment variables and configuration."""
    print("\n📝 Setting up environment...")
    
    env_file = Path(".env")
    if not env_file.exists():
        print("Creating .env file with default values...")
        env_content = """# Analyzer Infrastructure Environment Variables
OPENROUTER_API_KEY=your_openrouter_api_key_here
LOG_LEVEL=INFO
PYTHONPATH=/app

# Service Configuration
WEBSOCKET_HOST=0.0.0.0
GATEWAY_PORT=8765
STATIC_ANALYZER_PORT=2001
DYNAMIC_ANALYZER_PORT=2002
PERFORMANCE_TESTER_PORT=2003
AI_ANALYZER_PORT=2005

# ZAP Configuration
ZAP_PORT=8090

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
"""
        env_file.write_text(env_content)
        print("✅ Created .env file")
        print("⚠️ Please update OPENROUTER_API_KEY in .env file for AI analysis")
    else:
        print("✅ .env file already exists")
    
    return True

def create_test_data():
    """Create test data for analysis."""
    print("\n📋 Creating test data...")
    
    # Create a simple test Python file with security issues
    test_dir = Path(__file__).parent.parent / "misc" / "models" / "test" / "app1"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a Python file with intentional security issues
    test_file = test_dir / "test_app.py"
    test_content = '''#!/usr/bin/env python3
"""
Test application with intentional security issues for testing.
"""
import os
import subprocess

# Security issue: hardcoded password
PASSWORD = "admin123"

# Security issue: SQL injection vulnerability
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return query

# Security issue: command injection
def run_command(cmd):
    os.system(cmd)

# Security issue: eval usage
def calculate(expression):
    return eval(expression)

# Security issue: weak random
import random
def generate_token():
    return str(random.randint(1000, 9999))

if __name__ == "__main__":
    print("Test application with security issues")
'''
    
    test_file.write_text(test_content)
    
    # Create requirements.txt with vulnerable dependencies
    req_file = test_dir / "requirements.txt"
    req_content = '''# Intentionally vulnerable dependencies for testing
requests==2.25.1
flask==1.1.1
'''
    req_file.write_text(req_content)
    
    print(f"✅ Created test data in {test_dir}")
    return True

def build_services():
    """Build all Docker services."""
    print("\n🏗️ Building analyzer services...")
    
    services = [
        "static-analyzer",
        "dynamic-analyzer", 
        "performance-tester",
        "ai-analyzer"
    ]
    
    for service in services:
        if not run_command(f"docker-compose build {service}", f"Building {service}"):
            print(f"❌ Failed to build {service}")
            return False
    
    print("✅ All services built successfully")
    return True

def start_services():
    """Start all services using Docker Compose."""
    print("\n🚀 Starting analyzer infrastructure...")
    
    if not run_command("docker-compose up -d", "Starting all services"):
        print("❌ Failed to start services")
        return False
    
    print("✅ Services started")
    
    # Wait for services to be ready
    print("⏳ Waiting for services to be ready...")
    time.sleep(30)
    
    return True

def check_service_health():
    """Check health of all services."""
    print("\n🏥 Checking service health...")
    
    services = {
        "static-analyzer": 2001,
        "dynamic-analyzer": 2002,
        "performance-tester": 2003,
        "ai-analyzer": 2005
    }
    
    all_healthy = True
    
    for service, port in services.items():
        print(f"\nChecking {service}...")
        
        # Check if container is running
        run_command(f"docker-compose ps {service}", f"Checking {service} status", check=False)
        
        # Try health check script
        if run_command(f"docker-compose exec -T {service} python health_check.py", 
                      f"Running {service} health check", check=False):
            print(f"✅ {service} is healthy")
        else:
            print(f"⚠️ {service} health check failed")
            all_healthy = False
    
    return all_healthy

async def test_websocket_connectivity():
    """Test WebSocket connectivity to services."""
    if websockets is None:
        print("⚠️ websockets library not available")
        return
        
    print("\n🔌 Testing WebSocket connectivity...")
    
    services = {
        "static-analyzer": 2001,
        "dynamic-analyzer": 2002,
        "performance-tester": 2003,
        "ai-analyzer": 2005
    }
    
    for service, port in services.items():
        try:
            uri = f"ws://localhost:{port}"
            print(f"Testing {service} at {uri}...")
            
            async with websockets.connect(uri, timeout=5) as websocket:
                # Send heartbeat
                heartbeat = {
                    "type": "heartbeat",
                    "data": {"test": "connectivity"},
                    "id": f"test_{service}",
                    "timestamp": "2025-01-27T10:00:00Z"
                }
                
                await websocket.send(json.dumps(heartbeat))
                await asyncio.wait_for(websocket.recv(), timeout=5)
                
                print(f"✅ {service} WebSocket connection successful")
                
        except Exception as e:
            print(f"❌ {service} WebSocket connection failed: {str(e)}")

def test_connectivity():
    """Test connectivity to all services."""
    if websockets is None:
        print("⚠️ websockets library not installed, skipping connectivity test")
        print("Install with: pip install websockets")
        return
    
    try:
        asyncio.run(test_websocket_connectivity())
    except Exception as e:
        print(f"❌ WebSocket testing failed: {str(e)}")

def show_logs():
    """Show logs from all services."""
    print("\n📋 Showing service logs...")
    run_command("docker-compose logs --tail=50", "Getting recent logs", check=False)

def show_status():
    """Show status of all services."""
    print("\n📊 Service Status:")
    run_command("docker-compose ps", "Getting service status", check=False)
    
    print("\n🔍 Container Stats:")
    run_command("docker stats --no-stream", "Getting container stats", check=False)

def stop_services():
    """Stop all services."""
    print("\n🛑 Stopping analyzer services...")
    run_command("docker-compose down", "Stopping services", check=False)

def cleanup():
    """Clean up containers and volumes."""
    print("\n🧹 Cleaning up analyzer infrastructure...")
    run_command("docker-compose down -v", "Stopping and removing volumes", check=False)
    run_command("docker system prune -f", "Cleaning up unused Docker resources", check=False)

def main():
    """Main setup and management script."""
    if len(sys.argv) < 2:
        print("""
🔬 Analyzer Infrastructure Management

Usage: python setup.py <command>

Commands:
  setup     - Full setup (check prerequisites, build, start)
  build     - Build all services  
  start     - Start all services
  stop      - Stop all services
  restart   - Restart all services
  status    - Show service status
  health    - Check service health
  test      - Test WebSocket connectivity
  logs      - Show service logs
  cleanup   - Stop services and clean up volumes
  
Examples:
  python setup.py setup     # Complete setup
  python setup.py status    # Check what's running
  python setup.py logs      # View recent logs
  python setup.py cleanup   # Clean everything
""")
        return
    
    command = sys.argv[1].lower()
    
    if command == "setup":
        print("🚀 Setting up Analyzer Infrastructure")
        if not check_prerequisites():
            sys.exit(1)
        if not setup_environment():
            sys.exit(1)
        if not create_test_data():
            sys.exit(1)
        if not build_services():
            sys.exit(1)
        if not start_services():
            sys.exit(1)
        
        print("\n⏳ Waiting for services to stabilize...")
        time.sleep(10)
        
        check_service_health()
        test_connectivity()
        
        print("\n🎉 Analyzer Infrastructure Setup Complete!")
        print("\nNext steps:")
        print("1. Update OPENROUTER_API_KEY in .env file for AI analysis")
        print("2. Test the services with: python test_client.py")
        print("3. View service status with: python setup.py status")
        print("4. View logs with: python setup.py logs")
        
    elif command == "build":
        build_services()
        
    elif command == "start":
        start_services()
        
    elif command == "stop":
        stop_services()
        
    elif command == "restart":
        stop_services()
        time.sleep(5)
        start_services()
        
    elif command == "status":
        show_status()
        
    elif command == "health":
        check_service_health()
        
    elif command == "test":
        test_connectivity()
        
    elif command == "logs":
        show_logs()
        
    elif command == "cleanup":
        cleanup()
        
    else:
        print(f"❌ Unknown command: {command}")
        print("Run 'python setup.py' to see available commands")

if __name__ == "__main__":
    main()
