"""
Test Docker functionality from core_services
"""
import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core_services import DockerManager, create_logger_for_component

def test_docker_manager():
    """Test DockerManager functionality."""
    print("Testing DockerManager...")
    
    # Create Docker manager
    docker_manager = DockerManager()
    
    if not docker_manager.client:
        print("❌ Docker client not available")
        return False
    
    print("✅ Docker client created successfully")
    
    # Test container status check
    test_container = "test_nonexistent_container"
    status = docker_manager.get_container_status(test_container)
    print(f"Test container status: {status.to_dict()}")
    
    # Test build functionality (with a real model/app that exists)
    model = "anthropic_claude-3.7-sonnet"
    app_num = 1
    
    # Build path to compose file
    project_root = Path(__file__).parent
    models_base_dir = project_root / "misc" / "models"
    compose_path = models_base_dir / model / f"app{app_num}" / "docker-compose.yml"
    
    print(f"Checking compose file: {compose_path}")
    if compose_path.exists():
        print("✅ Compose file exists")
        
        # Test build containers
        print(f"Testing build for {model}/app{app_num}...")
        try:
            result = docker_manager.build_containers(str(compose_path), model, app_num)
            if result.get('success'):
                print(f"✅ Build successful: {result.get('message')}")
            else:
                print(f"❌ Build failed: {result.get('error')}")
        except Exception as e:
            print(f"❌ Build exception: {e}")
    else:
        print(f"❌ Compose file not found: {compose_path}")
    
    return True

if __name__ == "__main__":
    test_docker_manager()
