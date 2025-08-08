#!/usr/bin/env python3
"""
Real Model Testing Script for Analyzer Infrastructure
====================================================

This script tests the analyzer infrastructure on real AI-generated models from the misc/models folder.
It retrieves port configurations from the database and tests all analyzer services:
- Static Analyzer: Code quality and security analysis
- Dynamic Analyzer: OWASP ZAP security scanning (for running apps)
- Performance Tester: Load testing with Locust
- AI Analyzer: OpenRouter-powered requirements analysis

Usage:
    python test_real_models.py [options]
    
Examples:
    python test_real_models.py --models anthropic_claude-3.7-sonnet --apps 1,2,3
    python test_real_models.py --analyzers static,dynamic --max-apps 5
    python test_real_models.py --all-models --analyzers ai --parallel 3
"""

import asyncio
import json
import logging
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import sqlite3

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))
sys.path.append(str(Path(__file__).parent))

try:
    import websockets
except ImportError:
    websockets = None
    print("⚠️ websockets library not installed. Install with: pip install websockets")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_real_models.log')
    ]
)
logger = logging.getLogger(__name__)

# Analyzer service configuration
ANALYZER_SERVICES = {
    'static': {
        'port': 2001,
        'name': 'Static Analyzer',
        'description': 'Code quality and security analysis',
        'timeout': 120
    },
    'dynamic': {
        'port': 2002,
        'name': 'Dynamic Analyzer',
        'description': 'OWASP ZAP security scanning',
        'timeout': 300
    },
    'performance': {
        'port': 2003,
        'name': 'Performance Tester',
        'description': 'Load testing with Locust',
        'timeout': 180
    },
    'ai': {
        'port': 2005,
        'name': 'AI Analyzer',
        'description': 'OpenRouter-powered analysis',
        'timeout': 240
    }
}


class DatabaseManager:
    """Manages database connections and queries for model testing."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
    
    def connect(self):
        """Connect to the SQLite database."""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Enable column access by name
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def disconnect(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def get_port_configurations(self, model_name: str = None, app_num: int = None) -> List[Dict[str, Any]]:
        """Get port configurations for models."""
        if not self.connection:
            self.connect()
        
        query = "SELECT * FROM port_configurations"
        params = []
        
        if model_name:
            query += " WHERE model = ?"
            params.append(model_name)
            if app_num:
                query += " AND app_num = ?"
                params.append(app_num)
        
        query += " ORDER BY model, app_num"
        
        try:
            cursor = self.connection.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to query port configurations: {e}")
            return []
    
    def get_model_capabilities(self) -> List[Dict[str, Any]]:
        """Get all model capabilities."""
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.execute(
                "SELECT model_id, canonical_slug, provider, model_name FROM model_capabilities ORDER BY provider, model_name"
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to query model capabilities: {e}")
            return []


class ModelApplicationInfo:
    """Information about a model application for testing."""
    
    def __init__(self, model_name: str, app_number: int, frontend_port: int, backend_port: int, source_path: str):
        self.model_name = model_name
        self.app_number = app_number
        self.frontend_port = frontend_port
        self.backend_port = backend_port
        self.source_path = source_path
        self.frontend_url = f"http://localhost:{frontend_port}"
        self.backend_url = f"http://localhost:{backend_port}"
        
        # Check what files are available
        path = Path(source_path)
        self.has_backend = (path / "backend").exists()
        self.has_frontend = (path / "frontend").exists()
        self.has_docker_compose = (path / "docker-compose.yml").exists()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_name': self.model_name,
            'app_number': self.app_number,
            'frontend_port': self.frontend_port,
            'backend_port': self.backend_port,
            'source_path': self.source_path,
            'frontend_url': self.frontend_url,
            'backend_url': self.backend_url,
            'has_backend': self.has_backend,
            'has_frontend': self.has_frontend,
            'has_docker_compose': self.has_docker_compose
        }
    
    def __str__(self):
        return f"{self.model_name}/app{self.app_number}"


class AnalyzerTestResult:
    """Result of analyzer testing."""
    
    def __init__(self, app_info: ModelApplicationInfo, analyzer_type: str):
        self.app_info = app_info
        self.analyzer_type = analyzer_type
        self.start_time = datetime.now()
        self.end_time = None
        self.success = False
        self.error_message = None
        self.result_data = None
        self.duration_seconds = 0
        self.issues_found = 0
        self.status = "pending"
    
    def mark_success(self, result_data: Dict[str, Any]):
        """Mark test as successful."""
        self.end_time = datetime.now()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.success = True
        self.result_data = result_data
        self.status = "completed"
        
        # Extract issues count if available
        if isinstance(result_data, dict):
            if 'data' in result_data and isinstance(result_data['data'], dict):
                issues = result_data['data'].get('issues', [])
                self.issues_found = len(issues) if isinstance(issues, list) else 0
    
    def mark_failure(self, error_message: str):
        """Mark test as failed."""
        self.end_time = datetime.now()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.success = False
        self.error_message = error_message
        self.status = "failed"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'app_info': self.app_info.to_dict(),
            'analyzer_type': self.analyzer_type,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'success': self.success,
            'error_message': self.error_message,
            'duration_seconds': self.duration_seconds,
            'issues_found': self.issues_found,
            'status': self.status,
            'result_data': self.result_data
        }


class AnalyzerTester:
    """Tests analyzer services on real model applications."""
    
    def __init__(self):
        self.db_manager = None
        self.results: List[AnalyzerTestResult] = []
        
    def initialize(self, db_path: str):
        """Initialize the tester with database connection."""
        self.db_manager = DatabaseManager(db_path)
        self.db_manager.connect()
    
    def get_available_models(self) -> List[str]:
        """Get list of available model names from filesystem."""
        models_dir = Path(__file__).parent.parent / "misc" / "models"
        if not models_dir.exists():
            logger.error(f"Models directory not found: {models_dir}")
            return []
        
        models = []
        for item in models_dir.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                models.append(item.name)
        
        return sorted(models)
    
    def get_model_applications(self, model_names: List[str] = None, app_numbers: List[int] = None, max_apps: int = None) -> List[ModelApplicationInfo]:
        """Get model applications for testing."""
        if model_names is None:
            model_names = self.get_available_models()
        
        applications = []
        models_dir = Path(__file__).parent.parent / "misc" / "models"
        
        for model_name in model_names:
            model_dir = models_dir / model_name
            if not model_dir.exists():
                logger.warning(f"Model directory not found: {model_dir}")
                continue
            
            # Get port configuration for this model
            port_configs = self.db_manager.get_port_configurations(model_name)
            port_map = {pc['app_num']: pc for pc in port_configs}
            
            # Find available apps
            app_dirs = [d for d in model_dir.iterdir() if d.is_dir() and d.name.startswith('app')]
            app_nums = []
            for app_dir in app_dirs:
                try:
                    app_num = int(app_dir.name[3:])  # Extract number from 'appN'
                    if app_numbers is None or app_num in app_numbers:
                        app_nums.append(app_num)
                except ValueError:
                    continue
            
            app_nums.sort()
            if max_apps:
                app_nums = app_nums[:max_apps]
            
            for app_num in app_nums:
                if app_num not in port_map:
                    logger.warning(f"No port configuration found for {model_name}/app{app_num}")
                    continue
                
                port_config = port_map[app_num]
                app_path = model_dir / f"app{app_num}"
                
                app_info = ModelApplicationInfo(
                    model_name=model_name,
                    app_number=app_num,
                    frontend_port=port_config['frontend_port'],
                    backend_port=port_config['backend_port'],
                    source_path=str(app_path)
                )
                
                applications.append(app_info)
                logger.info(f"Found application: {app_info}")
        
        return applications
    
    async def test_analyzer_service(self, app_info: ModelApplicationInfo, analyzer_type: str) -> AnalyzerTestResult:
        """Test a specific analyzer service on an application."""
        result = AnalyzerTestResult(app_info, analyzer_type)
        
        if websockets is None:
            result.mark_failure("websockets library not available")
            return result
        
        analyzer_config = ANALYZER_SERVICES[analyzer_type]
        uri = f"ws://localhost:{analyzer_config['port']}"
        
        try:
            logger.info(f"Testing {analyzer_config['name']} on {app_info}")
            
            async with websockets.connect(uri, open_timeout=10) as websocket:
                # Prepare analysis request based on analyzer type
                if analyzer_type == 'static':
                    request_data = {
                        "analysis_type": "static",
                        "source_path": app_info.source_path,
                        "tools": ["bandit", "pylint", "eslint", "stylelint"]
                    }
                elif analyzer_type == 'dynamic':
                    # Dynamic analysis requires running applications
                    request_data = {
                        "analysis_type": "dynamic",
                        "target_url": app_info.frontend_url,
                        "backend_url": app_info.backend_url,
                        "scan_depth": 2
                    }
                elif analyzer_type == 'performance':
                    request_data = {
                        "analysis_type": "performance",
                        "target_url": app_info.frontend_url,
                        "scenario": "basic_load",
                        "duration": 30,
                        "users": 5
                    }
                elif analyzer_type == 'ai':
                    request_data = {
                        "analysis_type": "ai",
                        "analysis_focus": "code_review",
                        "source_path": app_info.source_path,
                        "model_name": "openai/gpt-4",
                        "max_tokens": 2000,
                        "requirements": [
                            "Application should have proper error handling",
                            "Code should follow security best practices",
                            "Application should be well-documented"
                        ]
                    }
                
                # Send analysis request
                request_message = {
                    "type": "analysis_request",
                    "id": f"test_{analyzer_type}_{app_info.model_name}_app{app_info.app_number}",
                    "timestamp": datetime.now().isoformat(),
                    "data": request_data
                }
                
                await websocket.send(json.dumps(request_message))
                logger.info(f"Sent request to {analyzer_config['name']}")
                
                # Wait for response with progress updates
                timeout = analyzer_config['timeout']
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=30)
                        response_data = json.loads(response)
                        
                        if response_data.get('type') == 'progress_update':
                            progress_data = response_data.get('data', {})
                            progress = progress_data.get('progress', 0)
                            message = progress_data.get('message', '')
                            logger.info(f"{analyzer_config['name']} progress: {progress:.1%} - {message}")
                        
                        elif response_data.get('type') == 'analysis_result':
                            logger.info(f"Received result from {analyzer_config['name']}")
                            result.mark_success(response_data)
                            break
                        
                        elif response_data.get('type') == 'error':
                            error_msg = response_data.get('data', {}).get('message', 'Unknown error')
                            result.mark_failure(f"Service error: {error_msg}")
                            break
                            
                    except asyncio.TimeoutError:
                        continue
                    except json.JSONDecodeError as e:
                        result.mark_failure(f"Invalid JSON response: {e}")
                        break
                
                if result.status == "pending":
                    result.mark_failure("Timeout waiting for analysis result")
                    
        except ConnectionRefusedError:
            result.mark_failure(f"Cannot connect to {analyzer_config['name']} at {uri}")
        except Exception as e:
            result.mark_failure(f"Unexpected error: {str(e)}")
        
        return result
    
    async def test_multiple_applications(self, applications: List[ModelApplicationInfo], analyzer_types: List[str], parallel: int = 1) -> List[AnalyzerTestResult]:
        """Test multiple applications with specified analyzers."""
        all_results = []
        
        # Create test tasks
        tasks = []
        for app_info in applications:
            for analyzer_type in analyzer_types:
                tasks.append((app_info, analyzer_type))
        
        logger.info(f"Starting {len(tasks)} analysis tasks with {parallel} parallel workers")
        
        # Run tests with limited parallelism
        semaphore = asyncio.Semaphore(parallel)
        
        async def run_test_with_semaphore(app_info, analyzer_type):
            async with semaphore:
                return await self.test_analyzer_service(app_info, analyzer_type)
        
        # Execute tests
        test_coroutines = [run_test_with_semaphore(app_info, analyzer_type) for app_info, analyzer_type in tasks]
        results = await asyncio.gather(*test_coroutines, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                app_info, analyzer_type = tasks[i]
                failed_result = AnalyzerTestResult(app_info, analyzer_type)
                failed_result.mark_failure(f"Exception during test: {str(result)}")
                all_results.append(failed_result)
            else:
                all_results.append(result)
        
        self.results.extend(all_results)
        return all_results
    
    def generate_report(self, results: List[AnalyzerTestResult] = None) -> Dict[str, Any]:
        """Generate a comprehensive test report."""
        if results is None:
            results = self.results
        
        # Overall statistics
        total_tests = len(results)
        successful_tests = sum(1 for r in results if r.success)
        failed_tests = total_tests - successful_tests
        
        # Group by analyzer type
        analyzer_stats = {}
        for analyzer_type in ANALYZER_SERVICES.keys():
            analyzer_results = [r for r in results if r.analyzer_type == analyzer_type]
            if analyzer_results:
                successful = sum(1 for r in analyzer_results if r.success)
                total_issues = sum(r.issues_found for r in analyzer_results if r.success)
                avg_duration = sum(r.duration_seconds for r in analyzer_results) / len(analyzer_results)
                
                analyzer_stats[analyzer_type] = {
                    'total_tests': len(analyzer_results),
                    'successful': successful,
                    'failed': len(analyzer_results) - successful,
                    'success_rate': successful / len(analyzer_results) if analyzer_results else 0,
                    'total_issues_found': total_issues,
                    'average_duration': avg_duration
                }
        
        # Group by model
        model_stats = {}
        for result in results:
            model_name = result.app_info.model_name
            if model_name not in model_stats:
                model_stats[model_name] = {'total': 0, 'successful': 0, 'failed': 0, 'issues': 0}
            
            model_stats[model_name]['total'] += 1
            if result.success:
                model_stats[model_name]['successful'] += 1
                model_stats[model_name]['issues'] += result.issues_found
            else:
                model_stats[model_name]['failed'] += 1
        
        # Failed tests details
        failed_results = [r for r in results if not r.success]
        failure_reasons = {}
        for result in failed_results:
            reason = result.error_message or "Unknown error"
            if reason not in failure_reasons:
                failure_reasons[reason] = 0
            failure_reasons[reason] += 1
        
        report = {
            'summary': {
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'failed_tests': failed_tests,
                'success_rate': successful_tests / total_tests if total_tests > 0 else 0,
                'total_models_tested': len(set(r.app_info.model_name for r in results)),
                'total_applications_tested': len(set(f"{r.app_info.model_name}/app{r.app_info.app_number}" for r in results)),
                'total_issues_found': sum(r.issues_found for r in results if r.success)
            },
            'analyzer_statistics': analyzer_stats,
            'model_statistics': model_stats,
            'failure_analysis': {
                'total_failures': failed_tests,
                'failure_reasons': failure_reasons
            },
            'test_details': [r.to_dict() for r in results],
            'generated_at': datetime.now().isoformat()
        }
        
        return report
    
    def save_report(self, report: Dict[str, Any], filename: str = None):
        """Save test report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analyzer_test_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Test report saved to: {filename}")
        return filename
    
    def print_summary(self, results: List[AnalyzerTestResult] = None):
        """Print a summary of test results."""
        if results is None:
            results = self.results
        
        report = self.generate_report(results)
        summary = report['summary']
        
        print("\n" + "="*80)
        print("ANALYZER INFRASTRUCTURE TEST RESULTS")
        print("="*80)
        
        print("📊 Overall Results:")
        print(f"   Total Tests: {summary['total_tests']}")
        print(f"   Successful: {summary['successful_tests']} ({summary['success_rate']:.1%})")
        print(f"   Failed: {summary['failed_tests']}")
        print(f"   Models Tested: {summary['total_models_tested']}")
        print(f"   Applications Tested: {summary['total_applications_tested']}")
        print(f"   Total Issues Found: {summary['total_issues_found']}")
        
        print("\n🔍 Analyzer Performance:")
        for analyzer_type, stats in report['analyzer_statistics'].items():
            name = ANALYZER_SERVICES[analyzer_type]['name']
            print(f"   {name}:")
            print(f"     Tests: {stats['total_tests']}, Success: {stats['successful']} ({stats['success_rate']:.1%})")
            print(f"     Issues Found: {stats['total_issues_found']}, Avg Duration: {stats['average_duration']:.1f}s")
        
        if report['failure_analysis']['total_failures'] > 0:
            print("\n❌ Failure Analysis:")
            for reason, count in report['failure_analysis']['failure_reasons'].items():
                print(f"   {reason}: {count} failures")
        
        print("\n" + "="*80)


async def main():
    """Main testing function."""
    parser = argparse.ArgumentParser(description="Test analyzer infrastructure on real AI-generated models")
    
    parser.add_argument('--models', type=str, help='Comma-separated list of model names to test')
    parser.add_argument('--apps', type=str, help='Comma-separated list of app numbers to test (e.g., 1,2,3)')
    parser.add_argument('--analyzers', type=str, default='static,dynamic,performance,ai', 
                       help='Comma-separated list of analyzers to test (static,dynamic,performance,ai)')
    parser.add_argument('--max-apps', type=int, help='Maximum number of apps per model to test')
    parser.add_argument('--parallel', type=int, default=2, help='Number of parallel tests')
    parser.add_argument('--db-path', type=str, default='../src/data/thesis_app.db', help='Path to database file')
    parser.add_argument('--output', type=str, help='Output file for detailed report (JSON)')
    parser.add_argument('--all-models', action='store_true', help='Test all available models')
    parser.add_argument('--quick', action='store_true', help='Quick test mode (1 app per model, static analyzer only)')
    
    args = parser.parse_args()
    
    # Quick test mode
    if args.quick:
        args.analyzers = 'static'
        args.max_apps = 1
        args.parallel = 1
    
    # Parse arguments
    models = args.models.split(',') if args.models else None
    app_numbers = [int(x.strip()) for x in args.apps.split(',')] if args.apps else None
    analyzer_types = [x.strip() for x in args.analyzers.split(',')]
    
    # Validate analyzer types
    invalid_analyzers = [a for a in analyzer_types if a not in ANALYZER_SERVICES]
    if invalid_analyzers:
        print(f"❌ Invalid analyzer types: {invalid_analyzers}")
        print(f"Available analyzers: {list(ANALYZER_SERVICES.keys())}")
        return
    
    # Initialize tester
    tester = AnalyzerTester()
    db_path = Path(__file__).parent / args.db_path
    
    if not db_path.exists():
        print(f"❌ Database file not found: {db_path}")
        return
    
    try:
        tester.initialize(str(db_path))
        
        # Get applications to test
        if args.all_models:
            models = None
        
        applications = tester.get_model_applications(models, app_numbers, args.max_apps)
        
        if not applications:
            print("❌ No applications found for testing")
            return
        
        print(f"🚀 Starting tests on {len(applications)} applications with {len(analyzer_types)} analyzers")
        print(f"📋 Analyzers: {', '.join(analyzer_types)}")
        print(f"⚡ Parallel workers: {args.parallel}")
        print(f"🔗 Database: {db_path}")
        
        # Run tests
        start_time = time.time()
        results = await tester.test_multiple_applications(applications, analyzer_types, args.parallel)
        end_time = time.time()
        
        print(f"\n✅ Testing completed in {end_time - start_time:.1f} seconds")
        
        # Generate and display report
        tester.print_summary(results)
        
        # Save detailed report
        report = tester.generate_report(results)
        output_file = args.output or f"analyzer_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        saved_file = tester.save_report(report, output_file)
        
        print(f"\n📄 Detailed report saved to: {saved_file}")
        
        # Exit with appropriate code
        successful_tests = sum(1 for r in results if r.success)
        if successful_tests == len(results):
            print("🎉 All tests passed!")
            sys.exit(0)
        else:
            failed_tests = len(results) - successful_tests
            print(f"⚠️ {failed_tests} tests failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Testing interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Testing failed with error: {e}", exc_info=True)
        print(f"❌ Testing failed: {e}")
        sys.exit(1)
    finally:
        if tester.db_manager:
            tester.db_manager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
