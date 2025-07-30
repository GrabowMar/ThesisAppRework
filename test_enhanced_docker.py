#!/usr/bin/env python3
"""Test enhanced DockerManager functionality."""

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core_services import DockerManager

def test_enhanced_functionality():
    """Test the enhanced DockerManager functionality."""
    print("Testing Enhanced DockerManager...")
    
    # Initialize DockerManager
    try:
        docker_manager = DockerManager()
        print("✅ DockerManager initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize DockerManager: {e}")
        return False
    
    # Test Docker availability
    is_available = docker_manager.is_docker_available()
    print(f"✓ Docker available: {is_available}")
    
    if not is_available:
        print("❌ Docker is not available, skipping container tests")
        return False
    
    # Test Docker version
    version = docker_manager.get_docker_version()
    print(f"✓ Docker version: {version}")
    
    # Test safe Docker operation wrapper
    try:
        containers = docker_manager.safe_docker_operation(
            "list_containers", 
            docker_manager.client.containers.list
        )
        print(f"✓ Safe operation - found {len(containers)} containers")
    except Exception as e:
        print(f"⚠️ Safe operation test failed: {e}")
    
    # Test container health check (use a common container name if exists)
    test_container = "test_container"
    health_info = docker_manager.check_container_health(test_container)
    print(f"✓ Container health check: {health_info['status']}")
    
    # Test logs with limit
    logs = docker_manager.get_container_logs_with_limit(test_container, lines=10)
    print(f"✓ Log retrieval test completed (length: {len(logs)} chars)")
    
    print("\n🎉 Enhanced DockerManager tests completed!")
    return True

if __name__ == "__main__":
    test_enhanced_functionality()
