#!/usr/bin/env python3
"""
Verification Script: Web App Analysis Workflow
===============================================

Mimics the exact workflow used by the Flask web application to validate
that metadata filtering fixes work correctly in production scenarios.

Workflow:
1. Submit analysis task via AnalysisTaskService (same as web UI)
2. Monitor TaskExecutionService background daemon processing
3. Validate results from both database and filesystem
4. Check for metadata contamination in tools map

Usage:
    python scripts/verify_web_app_analysis.py [--model MODEL] [--app APP] [--tools TOOL1,TOOL2]
    
    # Use existing analysis results
    python scripts/verify_web_app_analysis.py --existing task_5b458fafaac2
    
    # Trigger new analysis
    python scripts/verify_web_app_analysis.py --model openai_gpt-4 --app 1 --tools bandit,pylint,safety
"""

import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Set, Optional
from collections import defaultdict

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask, AnalysisStatus
from app.services.task_service import AnalysisTaskService


# Metadata keys that should NOT appear as tools
METADATA_KEYS = {
    'tool_status', '_metadata', 'status', 'file_counts', 'security_files',
    'total_files', 'message', 'error', 'analysis_time', 'model_slug',
    'app_number', 'tools_used', 'configuration_applied', 'results',
    '_project_metadata', 'structure', 'target_model', 'target_app_number',
    'task_id', 'created_at', 'completed_at', 'duration_seconds'
}


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print section header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


class AnalysisVerifier:
    """Verifies analysis workflow matches web app behavior."""
    
    def __init__(self, app):
        self.app = app
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.successes: List[str] = []
    
    def verify_existing_analysis(self, task_id: str) -> Dict[str, Any]:
        """Verify an existing analysis task from database and filesystem."""
        print_header(f"Verifying Existing Analysis: {task_id}")
        
        with self.app.app_context():
            # 1. Load from database
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if not task:
                print_error(f"Task {task_id} not found in database")
                return {'success': False, 'error': 'Task not found'}
            
            print_info(f"Task found in database: {task.task_id}")
            print_info(f"  Status: {task.status.value}")
            print_info(f"  Model: {task.target_model}")
            print_info(f"  App: {task.target_app_number}")
            print_info(f"  Created: {task.created_at}")
            
            # 2. Check filesystem results
            results_dir = Path('results') / task.target_model / f'app{task.target_app_number}' / task_id
            if not results_dir.exists():
                print_error(f"Results directory not found: {results_dir}")
                self.issues.append(f"Missing results directory: {results_dir}")
            else:
                print_success(f"Results directory exists: {results_dir}")
            
            # 3. Load consolidated JSON
            json_files = list(results_dir.glob('*.json'))
            main_json = [f for f in json_files if 'task_' in f.name and 
                        '_static' not in f.name and '_dynamic' not in f.name and
                        '_performance' not in f.name and '_ai' not in f.name]
            
            if not main_json:
                print_error("No consolidated JSON file found")
                self.issues.append("Missing consolidated JSON")
                return {'success': False, 'error': 'No consolidated JSON'}
            
            json_path = main_json[0]
            print_success(f"Found consolidated JSON: {json_path.name}")
            
            with open(json_path, 'r', encoding='utf-8') as f:
                filesystem_data = json.load(f)
            
            # 4. Validate both sources
            validation_results = {
                'database': self._validate_database_results(task),
                'filesystem': self._validate_filesystem_results(filesystem_data),
                'consistency': self._validate_consistency(task, filesystem_data)
            }
            
            # 5. Print summary
            self._print_validation_summary(validation_results)
            
            return {
                'success': len(self.issues) == 0,
                'task_id': task_id,
                'validation': validation_results,
                'issues': self.issues,
                'warnings': self.warnings,
                'successes': self.successes
            }
    
    def submit_new_analysis(self, model_slug: str, app_number: int, 
                           tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Submit new analysis task and monitor execution (web app workflow)."""
        print_header(f"Submitting New Analysis: {model_slug} app{app_number}")
        
        with self.app.app_context():
            # 1. Create task via AnalysisTaskService (same as web UI)
            print_info("Creating analysis task...")
            
            custom_options = {
                'selected_tool_names': tools or [],
                'source': 'verification_script',
                'unified_analysis': True
            }
            
            try:
                task = AnalysisTaskService.create_task(
                    model_slug=model_slug,
                    app_number=app_number,
                    tools=tools,
                    priority=5,  # High priority
                    custom_options=custom_options
                )
                print_success(f"Task created: {task.task_id}")
                print_info(f"  Status: {task.status.value}")
                print_info(f"  Tools: {tools or 'all available'}")
                
            except Exception as e:
                print_error(f"Failed to create task: {e}")
                return {'success': False, 'error': str(e)}
            
            # 2. Monitor TaskExecutionService processing
            print_info("\nWaiting for TaskExecutionService to pick up task...")
            print_info("(Background daemon polls every 2-10 seconds)")
            
            max_wait = 1800  # 30 minutes
            poll_interval = 3
            elapsed = 0
            last_status = task.status
            
            while elapsed < max_wait:
                time.sleep(poll_interval)
                elapsed += poll_interval
                
                # Refresh task from database
                db.session.expire_all()
                task = AnalysisTask.query.filter_by(task_id=task.task_id).first()
                
                if task.status != last_status:
                    print_info(f"  Status changed: {last_status.value} → {task.status.value}")
                    last_status = task.status
                
                if task.status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED, 
                                  AnalysisStatus.CANCELLED):
                    break
                
                # Print progress indicator
                if elapsed % 15 == 0:
                    print(f"  ... waiting ({elapsed}s elapsed, status: {task.status.value})")
            
            # 3. Check final status
            if task.status == AnalysisStatus.COMPLETED:
                print_success(f"Task completed successfully ({elapsed}s)")
            elif task.status == AnalysisStatus.FAILED:
                print_error(f"Task failed: {task.error_message}")
                return {'success': False, 'error': task.error_message, 'task_id': task.task_id}
            else:
                print_warning(f"Task did not complete within {max_wait}s (status: {task.status.value})")
                return {'success': False, 'error': 'Timeout', 'task_id': task.task_id}
            
            # 4. Validate results
            return self.verify_existing_analysis(task.task_id)
    
    def _validate_database_results(self, task: AnalysisTask) -> Dict[str, Any]:
        """Validate task.result_summary JSON from database (informational only)."""
        print_info("\n[Database Validation - Informational]")
        
        validation = {
            'has_result_summary': False,
            'tools_count': 0,
            'metadata_in_tools': [],
            'missing_fields': [],
            'status': 'info'  # Changed to info - DB uses condensed format
        }
        
        # Use get_result_summary() method to parse JSON
        result_summary = task.get_result_summary()
        
        if not result_summary:
            print_warning("Task has no result_summary JSON")
            self.warnings.append("Database: No result_summary")
            return validation
        
        validation['has_result_summary'] = True
        print_success("Task has result_summary JSON")
        
        # Note: Database stores condensed summary, not full results with tools map
        # The web UI loads from filesystem, so that's the primary validation target
        if 'results' in result_summary and 'tools' in result_summary['results']:
            tools = result_summary['results']['tools']
            validation['tools_count'] = len(tools)
            print_success(f"Database: Found {len(tools)} tools")
            
            # Check for metadata contamination
            tool_names_lower = {name.lower() for name in tools.keys()}
            metadata_found = tool_names_lower & METADATA_KEYS
            
            if metadata_found:
                validation['metadata_in_tools'] = list(metadata_found)
                for meta_key in metadata_found:
                    print_error(f"Database: Metadata key found in tools: {meta_key}")
                    self.issues.append(f"Database: Metadata '{meta_key}' in tools map")
            else:
                print_success("Database: No metadata keys in tools map")
                self.successes.append("Database: Clean tools map (no metadata)")
            
            # Check tool structure
            for tool_name, tool_data in tools.items():
                missing = []
                if 'status' not in tool_data:
                    missing.append('status')
                if 'executed' not in tool_data:
                    missing.append('executed')
                if 'total_issues' not in tool_data:
                    missing.append('total_issues')
                
                if missing:
                    validation['missing_fields'].append({tool_name: missing})
                    print_warning(f"Database: Tool '{tool_name}' missing fields: {missing}")
                    self.warnings.append(f"Database: Tool '{tool_name}' incomplete")
        else:
            print_info("Database: Uses condensed summary format (tools map in filesystem only)")
            print_info("  This is expected - web UI loads full results from filesystem")
        
        validation['status'] = 'info'  # Database format is different, not a pass/fail
        return validation
    
    def _validate_filesystem_results(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate consolidated JSON from filesystem."""
        print_info("\n[Filesystem Validation]")
        
        validation = {
            'has_results': False,
            'has_tools': False,
            'tools_count': 0,
            'metadata_in_tools': [],
            'tools_skipped': [],
            'tools_failed': [],
            'missing_fields': [],
            'status': 'unknown'
        }
        
        # Check structure
        if 'results' not in data:
            print_error("Filesystem: No 'results' section")
            self.issues.append("Filesystem: Missing results section")
            return validation
        
        validation['has_results'] = True
        results = data['results']
        
        # Check tools map
        if 'tools' not in results:
            print_error("Filesystem: No 'tools' map in results")
            self.issues.append("Filesystem: Missing tools map")
            return validation
        
        validation['has_tools'] = True
        tools = results['tools']
        validation['tools_count'] = len(tools)
        print_success(f"Filesystem: Found {len(tools)} tools")
        
        # Check for metadata contamination
        tool_names_lower = {name.lower() for name in tools.keys()}
        metadata_found = tool_names_lower & METADATA_KEYS
        
        if metadata_found:
            validation['metadata_in_tools'] = list(metadata_found)
            for meta_key in metadata_found:
                print_error(f"Filesystem: Metadata key found in tools: {meta_key}")
                self.issues.append(f"Filesystem: Metadata '{meta_key}' in tools map")
        else:
            print_success("Filesystem: No metadata keys in tools map")
            self.successes.append("Filesystem: Clean tools map (no metadata)")
        
        # Check summary section
        if 'summary' in results:
            summary = results['summary']
            
            # Check tools_skipped
            tools_skipped = summary.get('tools_skipped', [])
            validation['tools_skipped'] = tools_skipped
            
            if tools_skipped:
                # Check if skipped tools are metadata keys
                skipped_lower = {t.lower() for t in tools_skipped}
                metadata_skipped = skipped_lower & METADATA_KEYS
                
                if metadata_skipped:
                    print_error(f"Filesystem: Metadata in tools_skipped: {metadata_skipped}")
                    self.issues.append(f"Filesystem: Metadata in tools_skipped: {metadata_skipped}")
                else:
                    print_warning(f"Filesystem: {len(tools_skipped)} tools legitimately skipped")
                    self.warnings.append(f"Filesystem: {len(tools_skipped)} tools skipped (legitimate)")
            else:
                print_success("Filesystem: tools_skipped is empty (expected)")
                self.successes.append("Filesystem: Empty tools_skipped array")
            
            # Check tools_failed
            tools_failed = summary.get('tools_failed', [])
            validation['tools_failed'] = tools_failed
            if tools_failed:
                print_warning(f"Filesystem: {len(tools_failed)} tools failed: {tools_failed}")
                self.warnings.append(f"Filesystem: {len(tools_failed)} tools failed")
        
        # Check tool structure
        for tool_name, tool_data in tools.items():
            if not isinstance(tool_data, dict):
                print_error(f"Filesystem: Tool '{tool_name}' is not a dict: {type(tool_data)}")
                self.issues.append(f"Filesystem: Tool '{tool_name}' invalid type")
                continue
            
            missing = []
            if 'status' not in tool_data:
                missing.append('status')
            if 'executed' not in tool_data:
                missing.append('executed')
            if 'total_issues' not in tool_data:
                missing.append('total_issues')
            
            if missing:
                validation['missing_fields'].append({tool_name: missing})
                print_warning(f"Filesystem: Tool '{tool_name}' missing fields: {missing}")
                self.warnings.append(f"Filesystem: Tool '{tool_name}' incomplete")
        
        validation['status'] = 'pass' if not validation['metadata_in_tools'] else 'fail'
        return validation
    
    def _validate_consistency(self, task: AnalysisTask, filesystem_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate filesystem results are clean (database uses different format)."""
        print_info("\n[Consistency Validation]")
        
        validation = {
            'filesystem_clean': False,
            'status': 'unknown'
        }
        
        # Primary check: Filesystem results must be clean
        if 'results' in filesystem_data:
            fs_tools = filesystem_data['results'].get('tools', {})
            fs_tool_names = {name.lower() for name in fs_tools.keys()}
            fs_has_metadata = bool(fs_tool_names & METADATA_KEYS)
            
            if not fs_has_metadata:
                validation['filesystem_clean'] = True
                print_success("✓ Filesystem results are metadata-free (PRIMARY CHECK)")
                self.successes.append("Consistency: Filesystem tools map clean")
            else:
                print_error("✗ Filesystem results contain metadata in tools")
                self.issues.append("Consistency: Filesystem has metadata contamination")
        
        validation['status'] = 'pass' if validation['filesystem_clean'] else 'fail'
        return validation
    
    def _print_validation_summary(self, results: Dict[str, Any]):
        """Print validation summary."""
        print_header("Validation Summary")
        
        # Count results
        total_checks = 0
        passed_checks = 0
        
        for category, result in results.items():
            if isinstance(result, dict) and 'status' in result:
                total_checks += 1
                if result['status'] in ('pass', 'unknown'):
                    passed_checks += 1
        
        # Print statistics
        print(f"\n{Colors.BOLD}Statistics:{Colors.ENDC}")
        print(f"  Total Validations: {total_checks}")
        print(f"  Passed: {passed_checks}")
        print(f"  Issues: {len(self.issues)}")
        print(f"  Warnings: {len(self.warnings)}")
        print(f"  Successes: {len(self.successes)}")
        
        # Print issues
        if self.issues:
            print(f"\n{Colors.FAIL}{Colors.BOLD}Issues Found:{Colors.ENDC}")
            for issue in self.issues:
                print(f"  {Colors.FAIL}✗{Colors.ENDC} {issue}")
        
        # Print warnings
        if self.warnings:
            print(f"\n{Colors.WARNING}{Colors.BOLD}Warnings:{Colors.ENDC}")
            for warning in self.warnings:
                print(f"  {Colors.WARNING}⚠{Colors.ENDC} {warning}")
        
        # Print successes
        if self.successes:
            print(f"\n{Colors.OKGREEN}{Colors.BOLD}Successes:{Colors.ENDC}")
            for success in self.successes[:5]:  # Limit to first 5
                print(f"  {Colors.OKGREEN}✓{Colors.ENDC} {success}")
            if len(self.successes) > 5:
                print(f"  ... and {len(self.successes) - 5} more")
        
        # Final verdict
        print()
        if not self.issues:
            print_success("VERIFICATION PASSED: No metadata contamination detected")
        else:
            print_error("VERIFICATION FAILED: Metadata contamination found")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Verify web app analysis workflow and metadata filtering',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify existing analysis
  python scripts/verify_web_app_analysis.py --existing task_5b458fafaac2
  
  # Submit new analysis with specific tools
  python scripts/verify_web_app_analysis.py --model openai_gpt-4 --app 1 --tools bandit,pylint,safety
  
  # Submit comprehensive analysis (all tools)
  python scripts/verify_web_app_analysis.py --model anthropic_claude-3.7-sonnet --app 1
        """
    )
    
    parser.add_argument('--existing', type=str, metavar='TASK_ID',
                       help='Verify existing analysis task by ID')
    parser.add_argument('--model', type=str, metavar='MODEL_SLUG',
                       help='Model slug for new analysis (e.g., openai_gpt-4)')
    parser.add_argument('--app', type=int, metavar='APP_NUMBER',
                       help='App number for new analysis (e.g., 1)')
    parser.add_argument('--tools', type=str, metavar='TOOL1,TOOL2',
                       help='Comma-separated list of tools (optional, defaults to all)')
    parser.add_argument('--output', type=str, metavar='FILE',
                       help='Save validation report to JSON file')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.existing:
        mode = 'existing'
    elif args.model and args.app:
        mode = 'new'
    else:
        parser.print_help()
        print_error("\nError: Must specify either --existing TASK_ID or --model and --app")
        sys.exit(1)
    
    # Parse tools list
    tools_list = None
    if args.tools:
        tools_list = [t.strip() for t in args.tools.split(',')]
    
    # Create Flask app
    print_info("Initializing Flask application context...")
    app = create_app()
    
    # Create verifier
    verifier = AnalysisVerifier(app)
    
    # Run verification
    if mode == 'existing':
        result = verifier.verify_existing_analysis(args.existing)
    else:
        result = verifier.submit_new_analysis(args.model, args.app, tools_list)
    
    # Save output if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, default=str)
        print_success(f"\nValidation report saved to: {output_path}")
    
    # Exit with appropriate code
    sys.exit(0 if result.get('success', False) else 1)


if __name__ == '__main__':
    main()
