"""Integration test for containerized app generation with port allocation"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_port_allocation_integration():
    """Test that port allocation works with sample generation"""
    from app.services.port_allocation_service import get_port_allocation_service
    from app.extensions import db
    from app.factory import create_app
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        # Get port service
        port_service = get_port_allocation_service()
        
        # Test allocation for a new model/app
        test_model = "test_model_containerization"
        test_app_num = 1
        
        # Allocate ports
        ports = port_service.get_or_allocate_ports(test_model, test_app_num)
        
        print(f"✅ Allocated ports for {test_model}/app{test_app_num}:")
        print(f"   Backend: {ports.backend}")
        print(f"   Frontend: {ports.frontend}")
        
        # Verify ports were allocated
        assert ports.backend > 0
        assert ports.frontend > 0
        assert ports.backend != ports.frontend
        
        # Verify consistency (should return same ports on second call)
        ports2 = port_service.get_or_allocate_ports(test_model, test_app_num)
        assert ports2.backend == ports.backend
        assert ports2.frontend == ports.frontend
        print(f"✅ Port allocation is consistent")
        
        # Test another app
        ports3 = port_service.get_or_allocate_ports(test_model, 2)
        assert ports3.backend != ports.backend
        assert ports3.frontend != ports.frontend
        print(f"✅ Different ports allocated for app2:")
        print(f"   Backend: {ports3.backend}")
        print(f"   Frontend: {ports3.frontend}")
        
        # Clean up test data
        port_service.release_ports(test_model, 1)
        port_service.release_ports(test_model, 2)
        print(f"✅ Cleaned up test data")
        
        print("\n✅ All port allocation integration tests passed!")

def test_scaffolding_files_exist():
    """Test that all scaffolding files exist"""
    scaffolding_dir = Path(__file__).parent.parent / "misc" / "scaffolding" / "react-flask"
    
    required_files = [
        "docker-compose.yml",
        ".env.example",
        "README.md",
        "backend/Dockerfile",
        "backend/.dockerignore",
        "backend/app.py",
        "backend/requirements.txt",
        "frontend/Dockerfile",
        "frontend/.dockerignore",
        "frontend/nginx.conf",
        "frontend/index.html",
        "frontend/package.json",
        "frontend/vite.config.js",
        "frontend/src/App.jsx",
        "frontend/src/App.css",
    ]
    
    missing = []
    for file in required_files:
        file_path = scaffolding_dir / file
        if not file_path.exists():
            missing.append(file)
        else:
            print(f"✅ {file}")
    
    if missing:
        print(f"\n❌ Missing files:")
        for file in missing:
            print(f"   - {file}")
        raise AssertionError(f"Missing {len(missing)} scaffolding files")
    
    print(f"\n✅ All {len(required_files)} scaffolding files exist!")

def test_port_placeholders_in_templates():
    """Test that port placeholders exist in key template files"""
    scaffolding_dir = Path(__file__).parent.parent / "misc" / "scaffolding" / "react-flask"
    
    # Files that should have port placeholders
    files_with_placeholders = {
        "docker-compose.yml": ["{{backend_port", "{{frontend_port"],
        ".env.example": ["{{backend_port", "{{frontend_port"],
        "backend/app.py": ["{{backend_port"],
        "frontend/vite.config.js": ["{{backend_port", "{{frontend_port"],
        "README.md": ["{{backend_port", "{{frontend_port"],
    }
    
    for file, expected_placeholders in files_with_placeholders.items():
        file_path = scaffolding_dir / file
        content = file_path.read_text(encoding='utf-8')
        
        for placeholder in expected_placeholders:
            if placeholder in content:
                print(f"✅ {file} contains {placeholder}")
            else:
                print(f"❌ {file} missing {placeholder}")
                raise AssertionError(f"{file} missing {placeholder}")
    
    print(f"\n✅ All port placeholders found in templates!")

if __name__ == '__main__':
    print("=" * 60)
    print("Testing Scaffolding Files")
    print("=" * 60)
    test_scaffolding_files_exist()
    
    print("\n" + "=" * 60)
    print("Testing Port Placeholders")
    print("=" * 60)
    test_port_placeholders_in_templates()
    
    print("\n" + "=" * 60)
    print("Testing Port Allocation Integration")
    print("=" * 60)
    test_port_allocation_integration()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
