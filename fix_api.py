import re

# Read the file
with open('src/app/routes/api/api.py', 'r') as f:
    content = f.read()

# Replace docker_service with docker_manager
content = re.sub(r'from app\.services\.docker_service import DockerService', r'from app.services.docker_manager import DockerManager', content)
content = re.sub(r'DockerService\(\)', r'DockerManager()', content)

# Fix SecurityAnalysis.application relationship
content = re.sub(r'app = result\.application', r'app = result.generated_application if hasattr(result, "generated_application") else None', content)

# Write back
with open('src/app/routes/api/api.py', 'w') as f:
    f.write(content)

print('Additional fixes completed')