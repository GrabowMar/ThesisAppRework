"""Validate app6 backend code"""
import ast
from pathlib import Path

app6_backend = Path('generated/apps/openai_gpt-4o-mini/app6/backend/app.py')

if not app6_backend.exists():
    print(f"❌ File not found: {app6_backend}")
    exit(1)

content = app6_backend.read_text(encoding='utf-8')

# Check syntax
try:
    ast.parse(content)
    print("✓ Python syntax: VALID")
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    exit(1)

# Check structure
lines = content.splitlines()
print(f"✓ File size: {len(content)} bytes")
print(f"✓ Lines: {len(lines)}")

# Check for critical components
checks = {
    'TodoPriority class defined': 'class TodoPriority' in content,
    'Helper Classes section': '# --- Helper Classes ---' in content,
    'Uses TodoPriority.medium': 'TodoPriority.medium' in content,
    'Uses Enum(TodoPriority)': 'Enum(TodoPriority)' in content,
    'db instance': 'db = SQLAlchemy()' in content,
    'setup_app function': 'def setup_app' in content,
    'Todo model': 'class Todo(db.Model)' in content,
}

print("\nComponent checks:")
for name, result in checks.items():
    status = "✓" if result else "❌"
    print(f"{status} {name}")

# Count routes
route_count = content.count('@app.route')
print(f"\n✓ Routes: {route_count}")

# Show enum definition
if 'class TodoPriority' in content:
    print("\nEnum definition:")
    in_enum = False
    for line in lines:
        if 'class TodoPriority' in line:
            in_enum = True
        if in_enum:
            print(f"  {line}")
            if line.strip() and not line.strip().startswith(('class', 'low', 'medium', 'high')):
                break
            if line.strip().startswith('high'):
                break

print("\n✅ App6 validation complete!")
