import os
import sys
import logging
from app import create_app
from app.extensions import db
from app.models.pipeline import PipelineExecution

# Ensure app context
sys.path.insert(0, "/app/src")
sys.path.insert(0, "/app")

os.environ["FLASK_ENV"] = "development"

app = create_app()

with app.app_context():
    # Find the pending pipeline
    # We look for the one we just created (status='pending')
    pipeline = PipelineExecution.query.filter_by(status='pending').order_by(PipelineExecution.created_at.desc()).first()
    
    if pipeline:
        print(f"Found pending pipeline: {pipeline.pipeline_id}")
        pipeline.start()
        db.session.commit()
        print(f"Pipeline started! Status: {pipeline.status}")
    else:
        print("No pending pipeline found.")
