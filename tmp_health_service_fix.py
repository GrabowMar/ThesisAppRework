#!/usr/bin/env python3
"""Fix health_service.py to properly check Celery and Analyzers in Docker"""
import os
import re

# Path to health_service.py
HEALTH_SERVICE_PATH = "src/app/services/health_service.py"

def fix_health_service():
    """Fix the health_service.py file to properly check services in Docker"""
    
    if not os.path.exists(HEALTH_SERVICE_PATH):
        print(f"ERROR: {HEALTH_SERVICE_PATH} not found")
        return False
    
    with open(HEALTH_SERVICE_PATH, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Fix 1: Change Celery import to use get_celery()
    old_celery_import = 'from app.extensions import celery  # type: ignore[attr-defined]'
    new_celery_import = 'from app.extensions import get_celery\n            celery = get_celery()'
    
    if old_celery_import in content:
        content = content.replace(old_celery_import, new_celery_import)
        print("✓ Fixed Celery import to use get_celery()")
    elif 'from app.extensions import get_celery' in content:
        print("✓ Celery import already fixed")
    else:
        print("WARNING: Could not find Celery import pattern to fix")
    
    # Fix 2: Fix analyzer check to actually check Docker ports
    old_analyzer_check = '''    def check_analyzer(self, name: str, port: int) -> Dict[str, Any]:
        """
        Checks if an analyzer service is reachable on its port.

        Args:
            name: The name of the analyzer service.
            port: The port number of the analyzer service.

        Returns:
            A dictionary with the status and a message.
        """
        # This is a simplified check. A real implementation would use sockets
        # or a more robust health check endpoint on the service itself.
        # For now, we assume if the app is running, the user is managing these.
        return {"status": "healthy", "message": f"Port {port} reachable"}'''
    
    new_analyzer_check = '''    def check_analyzer(self, name: str, port: int) -> Dict[str, Any]:
        """
        Checks if an analyzer service is reachable on its port.

        Args:
            name: The name of the analyzer service.
            port: The port number of the analyzer service.

        Returns:
            A dictionary with the status and a message.
        """
        import socket
        
        # Determine the correct host based on environment
        # In Docker, services communicate via container names
        in_docker = os.environ.get('IN_DOCKER', '').lower() in ('true', '1', 'yes')
        
        if in_docker:
            # When running inside Docker, use service names from docker-compose
            host = name  # e.g., "static-analyzer"
        else:
            # When running outside Docker, use localhost
            host = 'localhost'
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                return {"status": "healthy", "message": f"Port {port} reachable"}
            else:
                return {"status": "unhealthy", "message": f"Cannot connect to {host}:{port}"}
        except socket.error as e:
            return {"status": "unhealthy", "message": f"Connection failed: {e}"}
        except Exception as e:
            return {"status": "unhealthy", "message": f"Error checking {name}: {e}"}'''
    
    if old_analyzer_check in content:
        content = content.replace(old_analyzer_check, new_analyzer_check)
        print("✓ Fixed analyzer check to use socket connections")
    elif "sock = socket.socket" in content:
        print("✓ Analyzer check already uses socket connections")
    else:
        # Try a more lenient match
        pattern = r'def check_analyzer\(self, name: str, port: int\).*?return \{"status": "healthy", "message": f"Port \{port\} reachable"\}'
        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, new_analyzer_check.strip(), content, flags=re.DOTALL)
            print("✓ Fixed analyzer check to use socket connections (regex match)")
        else:
            print("WARNING: Could not find analyzer check pattern to fix")
    
    # Only write if changes were made
    if content != original_content:
        with open(HEALTH_SERVICE_PATH, 'w') as f:
            f.write(content)
        print(f"✓ Saved changes to {HEALTH_SERVICE_PATH}")
        return True
    else:
        print("No changes needed")
        return True

if __name__ == "__main__":
    os.chdir("/home/ubuntu/ThesisAppRework")
    
    print("=" * 60)
    print("Fixing health_service.py for Docker environment")
    print("=" * 60)
    
    if fix_health_service():
        print("\n✓ Health service fix applied successfully!")
        print("\nNext: Rebuild web container to apply changes")
    else:
        print("\n✗ Failed to apply fix")
        exit(1)
