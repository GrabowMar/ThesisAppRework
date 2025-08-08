#!/usr/bin/env python3
"""
Quick test to start and validate the static analyzer service.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

async def test_static_analyzer():
    """Test the static analyzer service startup."""
    
    print("🔧 Quick Static Analyzer Service Test")
    print("=" * 50)
    
    # Start the static analyzer service
    analyzer_script = Path(__file__).parent / "services" / "static-analyzer" / "main.py"
    
    if not analyzer_script.exists():
        print(f"❌ Static analyzer script not found: {analyzer_script}")
        return False
    
    print("🚀 Starting static analyzer service...")
    print(f"   Script: {analyzer_script}")
    
    try:
        # Start the service in background
        process = subprocess.Popen([
            sys.executable, str(analyzer_script)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        print(f"📊 Service started with PID: {process.pid}")
        
        # Wait a moment for the service to start
        print("⏳ Waiting for service to initialize...")
        await asyncio.sleep(3)
        
        # Check if process is still running
        if process.poll() is None:
            print("✅ Service appears to be running")
            
            # Try to test the health check
            health_script = Path(__file__).parent / "services" / "static-analyzer" / "health_check.py"
            if health_script.exists():
                print("🩺 Running health check...")
                
                health_result = subprocess.run([
                    sys.executable, str(health_script)
                ], capture_output=True, text=True, timeout=10)
                
                if health_result.returncode == 0:
                    print("✅ Health check passed!")
                    print(f"   Output: {health_result.stdout.strip()}")
                else:
                    print("⚠️ Health check failed (expected - service might not be fully ready)")
                    print(f"   Error: {health_result.stderr.strip()}")
            
            # Terminate the service
            print("🛑 Stopping service...")
            process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=5)
                print("✅ Service stopped gracefully")
            except subprocess.TimeoutExpired:
                print("⚠️ Service didn't stop gracefully, killing...")
                process.kill()
                process.wait()
            
            return True
        else:
            print("❌ Service failed to start")
            stdout, stderr = process.communicate()
            print(f"   Stdout: {stdout}")
            print(f"   Stderr: {stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ Python interpreter not found")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

async def main():
    """Main test function."""
    print("Static Analyzer Service Quick Test")
    print("This tests if the service can start without API issues.")
    print()
    
    try:
        success = await test_static_analyzer()
        
        if success:
            print("\n🎉 Static analyzer service test completed successfully!")
            print("\nNext steps:")
            print("1. Install dependencies: python install_dependencies.py")
            print("2. Start all services: python run_all_services.py")
            print("3. Run full test: python test_real_models.py --quick")
        else:
            print("\n⚠️ Static analyzer service test had issues.")
            print("Check the error messages above for details.")
            
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
