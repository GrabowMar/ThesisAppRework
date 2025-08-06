#!/usr/bin/env python3

import sys
sys.path.append('src')

from extensions import db
from app import create_app
from models import GeneratedApplication

app = create_app()
with app.app_context():
    print("Checking applications in database...")
    
    # Get count of total applications
    total_count = db.session.query(GeneratedApplication).count()
    print(f"Total applications in database: {total_count}")
    
    # Get first 10 applications with basic info only
    apps = db.session.query(
        GeneratedApplication.id, 
        GeneratedApplication.model_slug, 
        GeneratedApplication.app_number
    ).limit(10).all()
    
    print(f"First 10 applications:")
    for app in apps:
        print(f"  ID: {app[0]}, Model: {app[1]}, App: {app[2]}")
    
    # Check if any have docker-compose files
    from pathlib import Path
    misc_models_dir = Path("misc/models")
    apps_with_docker = 0
    
    for app in apps:
        app_dir = misc_models_dir / app[1] / f"app{app[2]}"
        docker_compose_path = app_dir / "docker-compose.yml"
        if docker_compose_path.exists():
            apps_with_docker += 1
            print(f"  ✓ {app[1]}/app{app[2]} has docker-compose.yml")
        else:
            print(f"  ✗ {app[1]}/app{app[2]} missing docker-compose.yml")
    
    print(f"Applications with docker-compose files: {apps_with_docker}")
