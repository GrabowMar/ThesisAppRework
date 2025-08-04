#!/usr/bin/env python3
"""
Test script for real model analysis with the updated security scanner
"""
import subprocess
import time
import sys
import os
from pathlib import Path

def run_command(cmd, cwd=None, timeout=None):
    """Run a command and return success status."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            cwd=cwd, 
            capture_output=True, 
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def check_prerequisites():
    """Check if Docker and required tools are available."""
    print("🔍 Checking prerequisites...")
    
    # Check Docker
    success, stdout, stderr = run_command("docker --version")
    if not success:
        print("❌ Docker not found. Please install Docker first.")
        return False
    print(f"✅ {stdout.strip()}")
    
    # Check Docker Compose
    success, stdout, stderr = run_command("docker compose version")
    if not success:
        print("❌ Docker Compose not found.")
        return False
    print(f"✅ {stdout.strip()}")
    
    # Check if models directory exists
    models_dir = Path("../misc/models")
    if not models_dir.exists():
        print(f"❌ Models directory not found: {models_dir.resolve()}")
        return False
    print(f"✅ Models directory found: {models_dir.resolve()}")
    
    # Check if anthropic_claude-3.7-sonnet/app1 exists
    test_app = models_dir / "anthropic_claude-3.7-sonnet" / "app1"
    if not test_app.exists():
        print(f"❌ Test app not found: {test_app}")
        return False
    print(f"✅ Test app found: {test_app}")
    
    return True

def build_security_scanner():
    """Build the security scanner container."""
    print("\n🏗️  Building security scanner container...")
    
    success, stdout, stderr = run_command(
        "docker compose build security-scanner", 
        timeout=300  # 5 minutes
    )
    
    if success:
        print("✅ Security scanner built successfully")
        return True
    else:
        print("❌ Failed to build security scanner:")
        print(f"   stdout: {stdout}")
        print(f"   stderr: {stderr}")
        return False

def start_security_scanner():
    """Start the security scanner service."""
    print("\n🚀 Starting security scanner...")
    
    # Stop any existing containers first
    run_command("docker compose down security-scanner")
    
    success, stdout, stderr = run_command(
        "docker compose up -d security-scanner",
        timeout=60
    )
    
    if success:
        print("✅ Security scanner started")
        
        # Wait for service to be ready
        print("⏳ Waiting for service to be ready...")
        for i in range(30):  # Wait up to 30 seconds
            time.sleep(1)
            success, _, _ = run_command("curl -f http://localhost:8001/health")
            if success:
                print("✅ Security scanner is healthy")
                return True
            if i % 5 == 0:
                print(f"   Still waiting... ({i+1}/30 seconds)")
        
        print("⚠️  Service started but health check failed")
        return False
    else:
        print("❌ Failed to start security scanner:")
        print(f"   stdout: {stdout}")
        print(f"   stderr: {stderr}")
        return False

def test_real_analysis():
    """Test the security analysis on real model code."""
    print("\n🧪 Testing real model analysis...")
    
    # Run the comprehensive test
    success, stdout, stderr = run_command(
        "python comprehensive_test.py",
        timeout=180  # 3 minutes
    )
    
    if success:
        print("✅ Real analysis test completed successfully")
        print("\n📊 Test Output:")
        print(stdout)
        return True
    else:
        print("❌ Real analysis test failed:")
        print(f"   stdout: {stdout}")
        print(f"   stderr: {stderr}")
        return False

def check_container_logs():
    """Check container logs for any issues."""
    print("\n📋 Checking container logs...")
    
    success, stdout, stderr = run_command("docker compose logs security-scanner --tail=50")
    if success:
        print("📄 Recent logs:")
        print(stdout)
    else:
        print("❌ Failed to get logs")

def main():
    """Main test execution."""
    print("🎯 REAL MODEL ANALYSIS TEST SUITE")
    print("=" * 50)
    
    try:
        # Step 1: Check prerequisites
        if not check_prerequisites():
            sys.exit(1)
        
        # Step 2: Build container
        if not build_security_scanner():
            sys.exit(1)
        
        # Step 3: Start service
        if not start_security_scanner():
            check_container_logs()
            sys.exit(1)
        
        # Step 4: Test real analysis
        if not test_real_analysis():
            check_container_logs()
            sys.exit(1)
        
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Security scanner successfully analyzes real model applications")
        print("✅ Actual source code is being processed")
        print("✅ JSON results contain real security findings")
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        run_command("docker compose down security-scanner")

if __name__ == "__main__":
    main()
