#!/usr/bin/env python3
"""
Full Pipeline Test: Generation -> Analysis
Tests the complete end-to-end workflow
"""

import sys
import os
import time
import json
import asyncio
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from app.extensions import db
from app.models import GeneratedApplication, AnalysisTask, PipelineExecution
from app.constants import AnalysisStatus
from app.services.generation_v2.service import GenerationService
from app.services.analyzer_manager_wrapper import AnalyzerManagerWrapper
from app.engines.container_tool_registry import get_container_tool_registry

def print_status(message, level="INFO"):
    """Print formatted status message"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARNING": "⚠️",
        "PROGRESS": "🔄"
    }
    icon = icons.get(level, "•")
    print(f"[{timestamp}] {icon} {message}")

def wait_with_dots(seconds, message="Waiting"):
    """Wait with animated dots"""
    for i in range(seconds):
        dots = "." * ((i % 3) + 1)
        print(f"\r{message}{dots}   ", end="", flush=True)
        time.sleep(1)
    print()

async def test_generation_async(app, model_id, template_slug):
    """Test app generation (async)"""
    print_status("=" * 70, "INFO")
    print_status("STEP 1: GENERATION", "INFO")
    print_status("=" * 70, "INFO")
    print_status(f"Model: {model_id}", "INFO")
    print_status(f"Template: {template_slug}", "INFO")

    with app.app_context():
        try:
            service = GenerationService()

            print_status("Starting generation...", "PROGRESS")
            result = await service.generate_full_app(
                model_slug=model_id,
                app_num=None,  # Auto-assign app number
                template_slug=template_slug,
                use_auto_fix=False
            )

            if result.get('success'):
                app_num = result.get('app_num')
                print_status(f"Generation completed successfully!", "SUCCESS")
                print_status(f"App number: {app_num}", "INFO")
                print_status(f"App directory: {result.get('app_dir', 'N/A')}", "INFO")
                print_status(f"Backend port: {result.get('backend_port', 'N/A')}", "INFO")
                print_status(f"Frontend port: {result.get('frontend_port', 'N/A')}", "INFO")
                return app_num
            else:
                print_status(f"Generation failed: {result.get('error', 'Unknown error')}", "ERROR")
                return None

        except Exception as e:
            print_status(f"Generation error: {str(e)}", "ERROR")
            import traceback
            traceback.print_exc()
            return None

def test_analysis(app, model_id, app_number):
    """Test analysis on generated app"""
    print_status("=" * 70, "INFO")
    print_status("STEP 2: ANALYSIS", "INFO")
    print_status("=" * 70, "INFO")
    print_status(f"Analyzing app: {model_id}/app{app_number}", "INFO")

    with app.app_context():
        try:
            # Get available tools
            registry = get_container_tool_registry()
            all_tools = registry.get_all_tools()

            # Select a subset of tools for testing
            test_tools = []
            tool_names = ['bandit', 'semgrep', 'eslint', 'locust']

            for tool_name in tool_names:
                if tool_name in all_tools:
                    test_tools.append(all_tools[tool_name])

            if not test_tools:
                print_status("No tools available for analysis", "WARNING")
                return None

            print_status(f"Using tools: {[t.name for t in test_tools]}", "INFO")

            # Create analysis task
            task_id = f"test_analysis_{int(time.time())}"

            # Get a default analyzer configuration
            from app.models import AnalyzerConfiguration
            default_config = AnalyzerConfiguration.query.filter_by(is_default=True).first()
            if not default_config:
                # Create a default config if none exists
                default_config = AnalyzerConfiguration(
                    name="Test Configuration",
                    config_data='{}',
                    is_default=True
                )
                db.session.add(default_config)
                db.session.flush()

            analysis_task = AnalysisTask(
                task_id=task_id,
                task_name=f"Full Pipeline Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                target_model=model_id,
                target_app_number=app_number,
                status=AnalysisStatus.PENDING,
                is_main_task=True,
                analyzer_config_id=default_config.id,
            )

            db.session.add(analysis_task)
            db.session.commit()

            print_status(f"Created analysis task: {task_id}", "SUCCESS")

            # Start analysis
            wrapper = AnalyzerManagerWrapper()

            print_status("Starting comprehensive analysis...", "PROGRESS")
            analysis_task.status = AnalysisStatus.RUNNING
            db.session.commit()

            # Run analysis (this will take some time)
            result = wrapper.run_comprehensive_analysis(
                model_slug=model_id,
                app_number=app_number,
                task_name=task_id,
                tools=[t.name for t in test_tools]
            )

            # Update task status
            if result.get('success'):
                analysis_task.status = AnalysisStatus.COMPLETED
                analysis_task.progress_percentage = 100
                print_status("Analysis completed successfully!", "SUCCESS")

                # Display summary
                summary = result.get('summary', {})
                print_status(f"Total findings: {summary.get('total_findings', 0)}", "INFO")

                services = result.get('services', {})
                for service_name, service_data in services.items():
                    if service_data.get('success'):
                        findings = len(service_data.get('findings', []))
                        print_status(f"  {service_name}: {findings} findings", "INFO")

            else:
                analysis_task.status = AnalysisStatus.FAILED
                analysis_task.error_message = result.get('error', 'Unknown error')
                print_status(f"Analysis failed: {result.get('error', 'Unknown error')}", "ERROR")

            db.session.commit()
            return task_id

        except Exception as e:
            print_status(f"Analysis error: {str(e)}", "ERROR")
            import traceback
            traceback.print_exc()
            return None

def verify_results(app, model_id, app_number, task_id):
    """Verify analysis results are saved"""
    print_status("=" * 70, "INFO")
    print_status("STEP 3: VERIFICATION", "INFO")
    print_status("=" * 70, "INFO")

    with app.app_context():
        try:
            # Check if app exists in DB
            gen_app = GeneratedApplication.query.filter_by(
                model_slug=model_id,
                app_number=app_number
            ).first()

            if gen_app:
                print_status("✓ Generated application found in database", "SUCCESS")
            else:
                print_status("✗ Generated application NOT found in database", "ERROR")

            # Check if analysis task exists
            task = AnalysisTask.query.filter_by(task_id=task_id).first()

            if task:
                print_status(f"✓ Analysis task found: {task.status.value}", "SUCCESS")
                print_status(f"  Progress: {task.progress_percentage}%", "INFO")

                if task.error_message:
                    print_status(f"  Error: {task.error_message}", "WARNING")
            else:
                print_status("✗ Analysis task NOT found in database", "ERROR")

            # Check for result files
            results_dir = f"results/{model_id}/app{app_number}/task_{task_id}"
            if os.path.exists(results_dir):
                files = os.listdir(results_dir)
                print_status(f"✓ Results directory exists with {len(files)} files", "SUCCESS")
                for file in files[:5]:  # Show first 5 files
                    print_status(f"  - {file}", "INFO")
            else:
                print_status("✗ Results directory NOT found", "WARNING")

            return True

        except Exception as e:
            print_status(f"Verification error: {str(e)}", "ERROR")
            return False

async def main_async():
    """Main test execution (async)"""
    print_status("=" * 70, "INFO")
    print_status("FULL PIPELINE TEST: GENERATION -> ANALYSIS", "INFO")
    print_status("=" * 70, "INFO")

    # Configuration
    # Use canonical_slug format (with underscores, not slashes)
    model_id = "arcee-ai_trinity-large-preview"
    template_slug = "crud_todo_list"

    print_status(f"Test configuration:", "INFO")
    print_status(f"  Model: {model_id}", "INFO")
    print_status(f"  Template: {template_slug}", "INFO")
    print()

    # Create Flask app
    app = create_app()

    # Step 1: Generate app
    app_number = await test_generation_async(app, model_id, template_slug)

    if not app_number:
        print_status("Generation failed, aborting test", "ERROR")
        return 1

    print()
    wait_with_dots(3, "Preparing for analysis")

    # Step 2: Run analysis
    task_id = test_analysis(app, model_id, app_number)

    if not task_id:
        print_status("Analysis failed", "ERROR")
        return 1

    print()
    wait_with_dots(2, "Verifying results")

    # Step 3: Verify
    verify_results(app, model_id, app_number, task_id)

    print()
    print_status("=" * 70, "INFO")
    print_status("TEST COMPLETED", "SUCCESS")
    print_status("=" * 70, "INFO")
    print_status(f"Summary:", "INFO")
    print_status(f"  Model: {model_id}", "INFO")
    print_status(f"  App Number: {app_number}", "INFO")
    print_status(f"  Analysis Task: {task_id}", "INFO")
    print_status(f"  Results: results/{model_id}/app{app_number}/task_{task_id}/", "INFO")

    return 0

def main():
    """Sync wrapper for async main"""
    return asyncio.run(main_async())

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_status("Test interrupted by user", "WARNING")
        sys.exit(130)
    except Exception as e:
        print_status(f"Unexpected error: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)
