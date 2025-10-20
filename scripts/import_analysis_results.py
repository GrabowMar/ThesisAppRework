#!/usr/bin/env python3
"""
Import Analysis Results from JSON files to Database
===================================================

This script reads analysis JSON result files and imports them into the database
so they can be viewed in the web application GUI.

Usage:
    python scripts/import_analysis_results.py
    python scripts/import_analysis_results.py --model google_gemini-2.5-flash
    python scripts/import_analysis_results.py --model x-ai_grok-code-fast-1 --app 1
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dateutil import parser as dateutil_parser

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app import create_app
from app.models import AnalysisTask
from app.extensions import db
from app.constants import AnalysisStatus, JobPriority, AnalysisType
from app.services.analysis_result_store import persist_analysis_payload_by_task_id

def parse_analysis_type_from_filename(filename: str) -> str:
    """Determine analysis type from filename."""
    filename_lower = filename.lower()
    if '_static_' in filename_lower:
        return 'static'
    elif '_dynamic_' in filename_lower:
        return 'dynamic'
    elif '_performance_' in filename_lower:
        return 'performance'
    elif '_ai_' in filename_lower:
        return 'ai'
    else:
        return 'security'  # default

def create_task_from_json(json_path: Path, payload: Dict[str, Any]) -> Optional[str]:
    """Create an AnalysisTask from JSON payload and return task_id."""
    
    # Extract metadata
    metadata = payload.get('metadata', {})
    results = payload.get('results', {})
    task_meta = results.get('task', {})
    
    model_slug = metadata.get('model_slug') or task_meta.get('model_slug', 'unknown')
    app_number = metadata.get('app_number') or task_meta.get('app_number', 0)
    analysis_type_str = metadata.get('analysis_type') or task_meta.get('analysis_type', 'security')
    
    # Parse analysis type
    try:
        if analysis_type_str == 'unified':
            # For unified type, derive from filename
            analysis_type_str = parse_analysis_type_from_filename(json_path.name)
        analysis_type = AnalysisType(analysis_type_str)
    except ValueError:
        analysis_type = AnalysisType.SECURITY
    
    # Create unique task ID from filename to avoid collisions
    # Filename format: model_app#_type_timestamp.json
    filename_base = json_path.stem  # e.g., "google_gemini-2.5-flash_app1_ai_20251020_201427"
    task_id = f"task_{filename_base}"
    
    # Get or create a default analyzer configuration
    from app.models import AnalyzerConfiguration
    analyzer_config = AnalyzerConfiguration.query.filter_by(analyzer_type=analysis_type).first()
    if not analyzer_config:
        # Create a default config if none exists
        analyzer_config = AnalyzerConfiguration()
        analyzer_config.name = f"Default {analysis_type_str.title()}"
        analyzer_config.analyzer_type = analysis_type
        analyzer_config.config_data = "{}"
        db.session.add(analyzer_config)
        db.session.flush()  # Get ID without committing
    
    # Check if task already exists
    existing = AnalysisTask.query.filter_by(task_id=task_id).first()
    if existing:
        print(f"  ⚠️  Task {task_id} already exists, updating...")
        task = existing
    else:
        # Create new task
        task = AnalysisTask()
        task.task_id = task_id
        task.task_name = f"{model_slug} app{app_number} {analysis_type_str} analysis"
        task.analyzer_config_id = analyzer_config.id
        task.analysis_type = analysis_type
        task.target_model = model_slug
        task.target_app_number = app_number
        task.priority = JobPriority.NORMAL
        task.status = AnalysisStatus.COMPLETED
        db.session.add(task)
    
    # Update task metadata - convert timestamps to datetime objects
    started_str = task_meta.get('started_at')
    completed_str = task_meta.get('completed_at')
    
    # Parse ISO format timestamps to datetime objects
    if started_str:
        try:
            task.started_at = datetime.fromisoformat(started_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            task.started_at = datetime.now(timezone.utc)
    else:
        task.started_at = datetime.now(timezone.utc)
    
    if completed_str:
        try:
            task.completed_at = datetime.fromisoformat(completed_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            task.completed_at = datetime.now(timezone.utc)
    else:
        task.completed_at = datetime.now(timezone.utc)
    
    task.progress_percentage = 100.0
    task.status = AnalysisStatus.COMPLETED
    
    # Commit task first
    db.session.commit()
    
    return task.task_id

def import_json_file(json_path: Path) -> bool:
    """Import a single JSON file into the database."""
    try:
        print(f"📄 Processing: {json_path.name}")
        
        # Load JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        
        # Create or update task
        task_id = create_task_from_json(json_path, payload)
        if not task_id:
            print(f"  ❌ Failed to create task")
            return False
        
        # Store the full payload
        success = persist_analysis_payload_by_task_id(task_id, payload)
        
        if success:
            # Get summary info
            summary = payload.get('results', {}).get('summary', {})
            total_findings = summary.get('total_findings', 0)
            tools_executed = summary.get('tools_executed', 0)
            
            print(f"  ✅ Imported as {task_id}")
            print(f"     {total_findings} findings, {tools_executed} tools")
            return True
        else:
            print(f"  ❌ Failed to persist payload")
            return False
            
    except json.JSONDecodeError as e:
        print(f"  ❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description='Import analysis results from JSON to database')
    parser.add_argument('--model', help='Filter by model slug (e.g., google_gemini-2.5-flash)')
    parser.add_argument('--app', type=int, help='Filter by app number')
    parser.add_argument('--type', help='Filter by analysis type (static, dynamic, performance, ai)')
    parser.add_argument('--results-dir', default='results', help='Results directory (default: results)')
    args = parser.parse_args()
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        # Find all JSON files in results directory
        results_dir = Path(args.results_dir)
        if not results_dir.exists():
            print(f"❌ Results directory not found: {results_dir}")
            return 1
        
        json_files = list(results_dir.rglob('*.json'))
        
        # Filter by criteria
        if args.model:
            json_files = [f for f in json_files if args.model in str(f)]
        if args.app:
            json_files = [f for f in json_files if f'app{args.app}' in str(f)]
        if args.type:
            json_files = [f for f in json_files if f'_{args.type}_' in str(f)]
        
        if not json_files:
            print("❌ No JSON files found matching criteria")
            return 1
        
        print(f"\n🔍 Found {len(json_files)} JSON files to import")
        print("=" * 60)
        
        # Import each file
        success_count = 0
        fail_count = 0
        
        for json_path in sorted(json_files):
            if import_json_file(json_path):
                success_count += 1
            else:
                fail_count += 1
        
        print("\n" + "=" * 60)
        print(f"✅ Successfully imported: {success_count}")
        print(f"❌ Failed: {fail_count}")
        print(f"📊 Total processed: {len(json_files)}")
        
        return 0 if fail_count == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
