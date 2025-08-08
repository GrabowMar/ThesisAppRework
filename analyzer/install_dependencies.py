#!/usr/bin/env python3
"""
Install Testing Dependencies
===========================

This script installs the required dependencies for testing the analyzer infrastructure.
"""

import subprocess
import sys

def install_packages():
    """Install required packages for testing."""
    
    packages = [
        "websockets",  # For WebSocket communication with analyzer services
        "asyncio-extras",  # Additional asyncio utilities
        "aiofiles",  # Async file operations
    ]
    
    print("📦 Installing testing dependencies...")
    
    for package in packages:
        try:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            return False
    
    print("\n🎉 All dependencies installed successfully!")
    print("\nNext steps:")
    print("1. Run the quick demo: python quick_test_demo.py")
    print("2. Start analyzer services: python run_all_services.py")
    print("3. Full testing: python test_real_models.py --quick")
    
    return True

if __name__ == "__main__":
    install_packages()
