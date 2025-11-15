"""Test path resolution with both flat and template-based structures."""
import pytest
from pathlib import Path
import sys
import tempfile
import shutil

sys.path.insert(0, 'src')

from app.utils.helpers import get_app_directory


class TestAppDirectoryResolution:
    """Test get_app_directory() with various directory structures."""
    
    def test_template_based_structure(self):
        """Test path resolution finds apps in template subdirectories."""
        # This tests the actual filesystem structure we have
        model = 'anthropic_claude-4.5-haiku-20251001'
        
        # app1 is in api_url_shortener template
        app1_path = get_app_directory(model, 1)
        assert app1_path.exists(), f"app1 not found at {app1_path}"
        assert 'api_url_shortener' in str(app1_path), "app1 should be in api_url_shortener template"
        
        # app2 is in api_weather_display template
        app2_path = get_app_directory(model, 2)
        assert app2_path.exists(), f"app2 not found at {app2_path}"
        assert 'api_weather_display' in str(app2_path), "app2 should be in api_weather_display template"
        
        # app3 is in auth_user_login template
        app3_path = get_app_directory(model, 3)
        assert app3_path.exists(), f"app3 not found at {app3_path}"
        assert 'auth_user_login' in str(app3_path), "app3 should be in auth_user_login template"
    
    def test_compose_files_exist(self):
        """Verify docker-compose.yml files exist in resolved paths."""
        model = 'anthropic_claude-4.5-haiku-20251001'
        
        for app_num in [1, 2, 3]:
            app_path = get_app_directory(model, app_num)
            compose_file = app_path / 'docker-compose.yml'
            assert compose_file.exists(), f"docker-compose.yml not found in app{app_num} at {compose_file}"
    
    def test_backward_compatibility_flat_structure(self, tmp_path):
        """Test that flat structure (model/appN) still works."""
        # Create a temporary flat structure
        from app.utils.helpers import GENERATED_APPS_DIR
        
        test_model = 'test_flat_model'
        flat_app_dir = GENERATED_APPS_DIR / test_model / 'app1'
        
        # Create the directory if it doesn't exist
        if not flat_app_dir.exists():
            flat_app_dir.mkdir(parents=True, exist_ok=True)
            created = True
        else:
            created = False
        
        try:
            # Should find flat structure
            resolved = get_app_directory(test_model, 1)
            assert resolved == flat_app_dir, f"Should resolve to flat structure: {flat_app_dir}"
            assert resolved.exists(), "Flat structure directory should exist"
        finally:
            # Clean up if we created it
            if created and flat_app_dir.exists():
                shutil.rmtree(flat_app_dir.parent)
    
    def test_docker_manager_integration(self):
        """Test Docker manager uses updated path resolution."""
        from app.services.docker_manager import DockerManager
        
        docker_mgr = DockerManager()
        model = 'anthropic_claude-4.5-haiku-20251001'
        
        # Verify Docker manager finds compose files in template dirs
        for app_num in [1, 2, 3]:
            compose_path = docker_mgr._get_compose_path(model, app_num)
            assert compose_path.exists(), f"Docker manager should find compose file for app{app_num}"
            assert compose_path.name == 'docker-compose.yml', "Should resolve to docker-compose.yml"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
