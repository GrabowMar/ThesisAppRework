#!/usr/bin/env python3
"""Clear all analysis tasks from database."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app import create_app
from app.models import AnalysisTask
from app.extensions import db

app = create_app()

with app.app_context():
    count = AnalysisTask.query.count()
    print(f"Deleting {count} analysis tasks...")
    
    AnalysisTask.query.delete()
    db.session.commit()
    
    print("✅ All analysis tasks deleted")
