#!/usr/bin/env python3
"""
Setup Script for Analyzer Infrastructure
========================================

Quick setup and testing script for the new WebSocket-based analyzer infrastructure.
"""
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, cwd=None, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)
    
    return result


def setup_infrastructure():
    """Set up the analyzer infrastructure."""
    print("=" * 60)
    print("Setting up Analyzer Infrastructure")
    print("=" * 60)
    
    analyzer_dir = Path(__file__).parent
    
    # Check if Docker is available
    try:
        run_command(["docker", "--version"])
        run_command(["docker", "compose", "--version"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: Docker or Docker Compose not found!")
        print("Please install Docker Desktop and try again.")
        return False
    
    # Build and start services
    print("\n1. Building Docker images...")
    try:
        run_command(["docker", "compose", "build"], cwd=analyzer_dir)
    except subprocess.CalledProcessError:
        print("ERROR: Failed to build Docker images!")
        return False
    
    print("\n2. Starting services...")
    try:
        run_command(["docker", "compose", "up", "-d"], cwd=analyzer_dir)
    except subprocess.CalledProcessError:
        print("ERROR: Failed to start services!")
        return False
    
    print("\n3. Waiting for services to start...")
    time.sleep(10)
    
    # Check service status
    print("\n4. Checking service status...")
    try:
        result = run_command(["docker", "compose", "ps"], cwd=analyzer_dir)
        print(result.stdout)
    except subprocess.CalledProcessError:
        print("WARNING: Failed to check service status")
    
    print("\n✅ Infrastructure setup completed!")
    print("\nServices should be available at:")
    print("  - WebSocket Gateway: ws://localhost:8765")
    print("  - Prometheus: http://localhost:9090")
    print("  - Grafana: http://localhost:3000 (admin/admin)")
    
    return True


def test_infrastructure():
    """Test the analyzer infrastructure."""
    print("\n" + "=" * 60)
    print("Testing Analyzer Infrastructure")
    print("=" * 60)
    
    analyzer_dir = Path(__file__).parent
    
    print("\n1. Running test client...")
    try:
        run_command([sys.executable, "test_client.py"], cwd=analyzer_dir)
        print("✅ Test completed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Test failed!")
        return False


def create_test_data():
    """Create test data for analysis."""
    print("\n" + "=" * 60)
    print("Creating Test Data")
    print("=" * 60)
    
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
    print(f"  - {test_file.name}: Python file with security issues")
    print(f"  - {req_file.name}: Requirements with vulnerable dependencies")


def show_logs():
    """Show service logs."""
    print("\n" + "=" * 60)
    print("Service Logs")
    print("=" * 60)
    
    analyzer_dir = Path(__file__).parent
    
    try:
        run_command(["docker", "compose", "logs", "--tail=50"], cwd=analyzer_dir)
    except subprocess.CalledProcessError:
        print("Failed to show logs")


def cleanup():
    """Clean up the infrastructure."""
    print("\n" + "=" * 60)
    print("Cleaning up Infrastructure")
    print("=" * 60)
    
    analyzer_dir = Path(__file__).parent
    
    try:
        run_command(["docker", "compose", "down", "-v"], cwd=analyzer_dir)
        print("✅ Infrastructure cleaned up!")
    except subprocess.CalledProcessError:
        print("❌ Failed to clean up infrastructure")


def main():
    """Main setup script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyzer Infrastructure Setup")
    parser.add_argument("action", choices=["setup", "test", "logs", "cleanup", "all"], 
                       help="Action to perform")
    
    args = parser.parse_args()
    
    if args.action == "setup":
        create_test_data()
        setup_infrastructure()
    elif args.action == "test":
        test_infrastructure()
    elif args.action == "logs":
        show_logs()
    elif args.action == "cleanup":
        cleanup()
    elif args.action == "all":
        create_test_data()
        if setup_infrastructure():
            time.sleep(5)  # Give services time to start
            test_infrastructure()


if __name__ == "__main__":
    main()
