#!/usr/bin/env python3
"""
Database Initialization Script for Thesis Research App

This script initializes the database with model capabilities, port configurations,
and sample data for the thesis research application analyzing AI-generated apps.

Data Sources:
- misc/model_capabilities.json: Comprehensive model metadata from OpenRouter API
- misc/models_summary.json: Model summary with provider colors and names
- misc/port_config.json: Port allocation for Docker containers

Usage:
    python init_db.py
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Ensure we're in the right directory and set up paths
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
src_dir = project_root / "src"

# Add source directory to Python path
sys.path.insert(0, str(src_dir))

# Configure logging
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / 'init_db.log')
    ]
)
logger = logging.getLogger(__name__)

def get_project_root():
    """Get the project root directory."""
    return project_root

def load_json_file(file_path):
    """Load and parse a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Successfully loaded {file_path.name} with {len(data) if isinstance(data, (list, dict)) else 'unknown'} items")
        return data
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return None

def create_tables(app):
    """Create all database tables."""
    with app.app_context():
        logger.info("Creating database tables...")
        from extensions import db
        db.create_all()
        logger.info("Database tables created successfully")

def load_model_capabilities(app, misc_dir):
    """Load model capabilities from JSON file."""
    with app.app_context():
        from extensions import db
        from models import ModelCapability
        
        logger.info("Loading model capabilities...")
        
        capabilities_file = misc_dir / "model_capabilities.json"
        capabilities_data = load_json_file(capabilities_file)
        
        if not capabilities_data:
            logger.error("Failed to load model capabilities")
            return
        
        # Extract the models from the JSON structure
        models_data = capabilities_data.get('models', {})
        if not models_data:
            logger.error("No models found in capabilities data")
            return
        
        models_loaded = 0
        for model_id, model_data in models_data.items():
            try:
                # Check if model already exists
                existing = ModelCapability.query.filter_by(
                    model_id=model_data.get('model_id')
                ).first()
                
                if existing:
                    logger.info(f"Model {model_data.get('model_id')} already exists, skipping")
                    continue
                
                # Create new model capability record
                model_capability = ModelCapability(
                    model_id=model_data.get('model_id'),
                    canonical_slug=model_data.get('canonical_slug', model_data.get('model_id')),
                    provider=model_data.get('provider', 'unknown'),
                    model_name=model_data.get('model_name', model_data.get('model_id')),
                    is_free=model_data.get('is_free', False),
                    context_window=model_data.get('context_window', 0),
                    max_output_tokens=model_data.get('max_output_tokens', 0),
                    supports_function_calling=model_data.get('supports_function_calling', False),
                    supports_vision=model_data.get('supports_vision', False),
                    supports_streaming=model_data.get('supports_streaming', True),
                    supports_json_mode=model_data.get('supports_json_mode', False),
                    input_price_per_token=float(model_data.get('pricing', {}).get('prompt', 0)),
                    output_price_per_token=float(model_data.get('pricing', {}).get('completion', 0)),
                    cost_efficiency=model_data.get('performance_metrics', {}).get('cost_efficiency', 0.0),
                    safety_score=model_data.get('quality_metrics', {}).get('safety', 0.0),
                    capabilities_json=json.dumps(model_data.get('capabilities', {})),
                    metadata_json=json.dumps({
                        'description': model_data.get('description', ''),
                        'architecture': model_data.get('architecture', {}),
                        'quality_metrics': model_data.get('quality_metrics', {}),
                        'performance_metrics': model_data.get('performance_metrics', {}),
                        'last_updated': model_data.get('last_updated', '')
                    })
                )
                
                db.session.add(model_capability)
                models_loaded += 1
                
            except Exception as e:
                logger.error(f"Error processing model {model_id}: {e}")
                continue
        
        db.session.commit()
        logger.info(f"Successfully loaded {models_loaded} model capabilities")

def load_port_configurations(app, misc_dir):
    """Load port configurations from JSON file."""
    with app.app_context():
        from extensions import db
        from models import PortConfiguration
        
        logger.info("Loading port configurations...")
        
        port_file = misc_dir / "port_config.json"
        port_data = load_json_file(port_file)
        
        if not port_data:
            logger.error("Failed to load port configurations")
            return
        
        ports_loaded = 0
        for i, port_entry in enumerate(port_data):
            try:
                frontend_port = port_entry.get('frontend_port')
                backend_port = port_entry.get('backend_port')
                
                if not frontend_port or not backend_port:
                    logger.warning(f"Invalid port entry at index {i}: {port_entry}")
                    continue
                
                # Check if port configuration already exists
                existing = PortConfiguration.query.filter_by(
                    frontend_port=frontend_port
                ).first()
                
                if existing:
                    continue
                
                # Create new port configuration
                port_config = PortConfiguration(
                    frontend_port=frontend_port,
                    backend_port=backend_port,
                    is_available=True,
                    metadata_json=json.dumps({
                        'model': port_entry.get('model', ''),
                        'app_number': port_entry.get('app_number', 0),
                        'app_type': port_entry.get('app_type', ''),
                        'source': 'initial_load'
                    })
                )
                
                db.session.add(port_config)
                ports_loaded += 1
                
            except Exception as e:
                logger.error(f"Error processing port entry {i}: {e}")
                continue
        
        db.session.commit()
        logger.info(f"Successfully loaded {ports_loaded} port configurations")

def create_sample_applications(app, misc_dir):
    """Create sample generated applications."""
    with app.app_context():
        from extensions import db
        from models import GeneratedApplication, ModelCapability, AnalysisStatus
        
        logger.info("Creating sample generated applications...")
        
        # Get some models to create apps for
        models = ModelCapability.query.limit(5).all()
        if not models:
            logger.warning("No models found, skipping sample applications")
            return
        
        apps_created = 0
        for model in models:
            for app_num in range(1, 4):  # Create 3 sample apps per model
                try:
                    app_name = f"sample_app_{app_num}"
                    
                    # Check if application already exists
                    existing = GeneratedApplication.query.filter_by(
                        model_id=model.id,
                        app_number=app_num
                    ).first()
                    
                    if existing:
                        continue
                    
                    # Create sample application
                    gen_app = GeneratedApplication(
                        model_id=model.id,
                        app_number=app_num,
                        app_name=app_name,
                        app_type=f"sample_type_{app_num}",
                        generation_status=AnalysisStatus.COMPLETED,
                        frontend_port=9000 + (model.id * 10) + app_num,
                        backend_port=6000 + (model.id * 10) + app_num,
                        has_frontend=True,
                        has_backend=True,
                        docker_status="not_started",
                        file_structure_json=json.dumps({
                            "frontend": ["src/", "package.json", "Dockerfile"],
                            "backend": ["app.py", "requirements.txt", "Dockerfile"],
                            "docker-compose.yml": True
                        }),
                        metadata_json=json.dumps({
                            "description": f"Sample {app_name} generated by {model.model_name}",
                            "created_for_testing": True,
                            "generation_date": datetime.utcnow().isoformat()
                        })
                    )
                    
                    db.session.add(gen_app)
                    apps_created += 1
                    
                except Exception as e:
                    logger.error(f"Error creating sample app for model {model.model_id}, app {app_num}: {e}")
                    continue
        
        db.session.commit()
        logger.info(f"Successfully created {apps_created} sample applications")

def create_sample_analyses(app):
    """Create sample security analyses."""
    with app.app_context():
        from extensions import db
        from models import SecurityAnalysis, GeneratedApplication, AnalysisStatus, SeverityLevel
        
        logger.info("Creating sample security analyses...")
        
        # Get some applications to analyze
        applications = GeneratedApplication.query.limit(3).all()
        if not applications:
            logger.warning("No applications found, skipping sample analyses")
            return
        
        analyses_created = 0
        for gen_app in applications:
            try:
                # Check if analysis already exists
                existing = SecurityAnalysis.query.filter_by(
                    application_id=gen_app.id
                ).first()
                
                if existing:
                    continue
                
                # Create sample analysis
                analysis = SecurityAnalysis(
                    application_id=gen_app.id,
                    analysis_type="comprehensive",
                    status=AnalysisStatus.COMPLETED,
                    tools_used_json=json.dumps({
                        "backend": ["bandit", "safety"],
                        "frontend": ["eslint", "npm_audit"]
                    }),
                    results_json=json.dumps({
                        "issues_found": 3,
                        "high_severity": 1,
                        "medium_severity": 1,
                        "low_severity": 1,
                        "summary": "Sample analysis results for testing"
                    }),
                    issues_json=json.dumps([
                        {
                            "severity": "high",
                            "type": "SQL Injection",
                            "file": "app.py",
                            "line": 42,
                            "description": "Potential SQL injection vulnerability"
                        },
                        {
                            "severity": "medium", 
                            "type": "XSS",
                            "file": "frontend/src/App.js",
                            "line": 15,
                            "description": "Potential XSS vulnerability"
                        }
                    ]),
                    recommendations_json=json.dumps([
                        "Use parameterized queries",
                        "Sanitize user input",
                        "Implement proper authentication"
                    ])
                )
                
                db.session.add(analysis)
                analyses_created += 1
                
            except Exception as e:
                logger.error(f"Error creating sample analysis for app {gen_app.id}: {e}")
                continue
        
        db.session.commit()
        logger.info(f"Successfully created {analyses_created} sample security analyses")

def create_sample_performance_tests(app):
    """Create sample performance tests."""
    with app.app_context():
        from extensions import db
        from models import PerformanceTest, GeneratedApplication, AnalysisStatus
        
        logger.info("Creating sample performance tests...")
        
        # Get some applications to test
        applications = GeneratedApplication.query.limit(2).all()
        if not applications:
            logger.warning("No applications found, skipping sample performance tests")
            return
        
        tests_created = 0
        for gen_app in applications:
            try:
                # Check if test already exists
                existing = PerformanceTest.query.filter_by(
                    application_id=gen_app.id
                ).first()
                
                if existing:
                    continue
                
                # Create sample performance test
                perf_test = PerformanceTest(
                    application_id=gen_app.id,
                    test_type="load_test",
                    status=AnalysisStatus.COMPLETED,
                    concurrent_users=10,
                    duration_seconds=60,
                    target_url=f"http://localhost:{gen_app.frontend_port}",
                    results_json=json.dumps({
                        "total_requests": 1000,
                        "successful_requests": 995,
                        "failed_requests": 5,
                        "average_response_time": 125.5,
                        "max_response_time": 500.2,
                        "min_response_time": 50.1,
                        "requests_per_second": 16.7
                    }),
                    metrics_json=json.dumps({
                        "cpu_usage": [25.5, 30.2, 28.7],
                        "memory_usage": [512, 520, 518],
                        "response_times": [100, 125, 150, 95, 200]
                    })
                )
                
                db.session.add(perf_test)
                tests_created += 1
                
            except Exception as e:
                logger.error(f"Error creating sample performance test for app {gen_app.id}: {e}")
                continue
        
        db.session.commit()
        logger.info(f"Successfully created {tests_created} sample performance tests")

def create_sample_batch_analyses(app):
    """Create sample batch analyses."""
    with app.app_context():
        from extensions import db
        from models import BatchAnalysis, AnalysisStatus
        
        logger.info("Creating sample batch analyses...")
        
        try:
            # Check if batch analysis already exists
            existing = BatchAnalysis.query.first()
            if existing:
                logger.info("Batch analyses already exist, skipping")
                return
            
            # Create sample batch analysis
            batch_analysis = BatchAnalysis(
                batch_name="Sample Security Scan",
                analysis_type="security",
                status=AnalysisStatus.COMPLETED,
                total_applications=5,
                completed_applications=5,
                failed_applications=0,
                configuration_json=json.dumps({
                    "tools": ["bandit", "safety", "eslint"],
                    "severity_threshold": "medium",
                    "include_frontend": True,
                    "include_backend": True
                }),
                results_summary_json=json.dumps({
                    "total_issues": 15,
                    "critical_issues": 2,
                    "high_issues": 5,
                    "medium_issues": 8,
                    "models_analyzed": ["claude-3-sonnet", "gpt-4", "gemini-pro"],
                    "completion_rate": 100.0
                }),
                applications_json=json.dumps([
                    {"app_id": 1, "status": "completed", "issues_found": 3},
                    {"app_id": 2, "status": "completed", "issues_found": 2},
                    {"app_id": 3, "status": "completed", "issues_found": 5}
                ])
            )
            
            db.session.add(batch_analysis)
            db.session.commit()
            logger.info("Successfully created sample batch analysis")
            
        except Exception as e:
            logger.error(f"Error creating sample batch analysis: {e}")

def main():
    """Main initialization function."""
    logger.info("=== Thesis Research App Database Initialization ===")
    
    # Get project directories
    project_root = get_project_root()
    misc_dir = project_root / "misc"
    
    logger.info(f"Project root: {project_root}")
    logger.info(f"Data source directory: {misc_dir}")
    
    # Verify data files exist
    required_files = ["model_capabilities.json", "models_summary.json", "port_config.json"]
    for file_name in required_files:
        file_path = misc_dir / file_name
        if not file_path.exists():
            logger.error(f"Required file not found: {file_path}")
            return False
        logger.info(f"Found required file: {file_path}")
    
    try:
        # Import and create Flask app
        from app import create_app
        logger.info("Creating Flask application...")
        app = create_app()
        
        # Initialize database
        logger.info("Initializing database...")
        
        # Create database tables
        create_tables(app)
        
        # Load data from JSON files
        load_model_capabilities(app, misc_dir)
        load_port_configurations(app, misc_dir)
        create_sample_applications(app, misc_dir)
        
        # Create sample analysis data
        create_sample_analyses(app)
        create_sample_performance_tests(app)
        create_sample_batch_analyses(app)
        
        logger.info("=== Database initialization completed successfully! ===")
        logger.info("You can now run the application with: python app.py")
        
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
