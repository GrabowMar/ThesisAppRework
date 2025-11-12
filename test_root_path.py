import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.factory import create_app

app = create_app()
print(f"root_path: {app.root_path}")
print(f"parent: {Path(app.root_path).parent}")
print(f"parent.parent: {Path(app.root_path).parent.parent}")
