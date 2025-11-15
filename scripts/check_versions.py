import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from app import create_app
from app.models import GeneratedApplication
from sqlalchemy import func

app = create_app()
with app.app_context():
    total = GeneratedApplication.query.count()
    print(f"Total apps: {total}")
    
    apps = GeneratedApplication.query.limit(10).all()
    print(f"\nFirst 10 apps:")
    for a in apps:
        print(f"  - {a.model_slug} app{a.app_number} v{a.version} ({a.template_slug or 'default'})")
    
    from app.extensions import db
    version_counts = db.session.query(
        GeneratedApplication.model_slug,
        GeneratedApplication.app_number,
        func.count(GeneratedApplication.id)
    ).group_by(
        GeneratedApplication.model_slug,
        GeneratedApplication.app_number
    ).having(
        func.count(GeneratedApplication.id) > 1
    ).all()
    
    print(f"\nApps with multiple versions: {len(version_counts)}")
    for m, n, c in version_counts:
        print(f"  - {m} app{n}: {c} versions")
