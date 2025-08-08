#!/usr/bin/env python3
"""
Comprehensive Test Suite for Analyzer Infrastructure
===================================================

This test suite systematically tests all components of the analyzer infrastructure:

1. Database connectivity and model discovery
2. Service startup and health checks
3. WebSocket communication
4. Individual analyzer services
5. Integration testing with real models
6. Error handling and edge cases

Usage:
    python test_suite.py [--verbose] [--quick] [--service SERVICE]

Examples:
    python test_suite.py                           # Run all tests
    python test_suite.py --quick                   # Run only essential tests
    python test_suite.py --service static          # Test only static analyzer
    python test_suite.py --verbose                 # Detailed output
"""

import asyncio
import json
import logging
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import sqlite3

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))
sys.path.append(str(Path(__file__).parent))

try:
    import websockets
    import psutil
except ImportError as e:
    print(f"❌ Missing required packages: {e}")
    print("Install with: python install_dependencies.py")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_suite.log')
    ]
)
logger = logging.getLogger(__name__)

class TestResult:
    """Container for test results."""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.success = False
        self.error_message = ""
        self.execution_time = 0.0
        self.details = {}
        self.start_time = time.time()
    
    def complete(self, success: bool, error_message: str = "", details: Dict = None):
        """Mark test as complete."""
        self.success = success
        self.error_message = error_message
        self.execution_time = time.time() - self.start_time
        self.details = details or {}
    
    def __str__(self):
        status = "✅ PASS" if self.success else "❌ FAIL"
        return f"{status} {self.test_name} ({self.execution_time:.2f}s)"

class DatabaseTester:
    """Tests database connectivity and model discovery."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def test_database_connection(self) -> TestResult:
        """Test basic database connectivity."""
        result = TestResult("Database Connection")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                expected_tables = ['model_capabilities', 'port_configurations', 'generated_applications']
                found_tables = [table[0] for table in tables]
                
                missing_tables = [t for t in expected_tables if t not in found_tables]
                
                if missing_tables:
                    result.complete(False, f"Missing tables: {missing_tables}")
                else:
                    result.complete(True, details={"tables": found_tables})
                    
        except Exception as e:
            result.complete(False, f"Database connection failed: {e}")
        
        return result
    
    def test_model_discovery(self) -> TestResult:
        """Test model discovery from database."""
        result = TestResult("Model Discovery")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Count models
                cursor.execute("SELECT COUNT(*) FROM model_capabilities")
                model_count = cursor.fetchone()[0]
                
                # Count port configurations
                cursor.execute("SELECT COUNT(*) FROM port_configurations")
                port_count = cursor.fetchone()[0]
                
                # Count generated applications
                cursor.execute("SELECT COUNT(*) FROM generated_applications")
                app_count = cursor.fetchone()[0]
                
                if model_count == 0:
                    result.complete(False, "No models found in database")
                elif port_count == 0:
                    result.complete(False, "No port configurations found")
                elif app_count == 0:
                    result.complete(False, "No generated applications found")
                else:
                    result.complete(True, details={
                        "models": model_count,
                        "ports": port_count,
                        "apps": app_count
                    })
                    
        except Exception as e:
            result.complete(False, f"Model discovery failed: {e}")
        
        return result

class ServiceTester:
    """Tests analyzer service functionality."""
    
    def __init__(self):
        self.services = {
            'static': {'port': 2001, 'name': 'Static Analyzer'},
            'dynamic': {'port': 2002, 'name': 'Dynamic Analyzer'},
            'performance': {'port': 2003, 'name': 'Performance Tester'},
            'security': {'port': 2004, 'name': 'Security Analyzer'},
            'ai': {'port': 2005, 'name': 'AI Analyzer'}
        }
    
    def test_service_availability(self, service_name: str) -> TestResult:
        """Test if a service is available on its expected port."""
        result = TestResult(f"Service Availability - {service_name}")
        
        if service_name not in self.services:
            result.complete(False, f"Unknown service: {service_name}")
            return result
        
        service = self.services[service_name]
        port = service['port']
        
        try:
            # Check if port is in use
            port_in_use = False
            for conn in psutil.net_connections():
                if conn.laddr.port == port:
                    port_in_use = True
                    break
            
            if port_in_use:
                result.complete(True, details={"port": port, "status": "running"})
            else:
                result.complete(False, f"Service not running on port {port}")
                
        except Exception as e:
            result.complete(False, f"Port check failed: {e}")
        
        return result
    
    async def test_websocket_connection(self, service_name: str) -> TestResult:
        """Test WebSocket connection to a service."""
        result = TestResult(f"WebSocket Connection - {service_name}")
        
        if service_name not in self.services:
            result.complete(False, f"Unknown service: {service_name}")
            return result
        
        service = self.services[service_name]
        uri = f"ws://localhost:{service['port']}"
        
        try:
            async with websockets.connect(uri, open_timeout=5) as websocket:
                # Send a ping message
                ping_message = {"type": "ping", "timestamp": time.time()}
                await websocket.send(json.dumps(ping_message))
                
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                response_data = json.loads(response)
                
                if response_data.get("type") == "pong":
                    result.complete(True, details={"response": response_data})
                else:
                    result.complete(False, f"Unexpected response: {response_data}")
                    
        except ConnectionRefusedError:
            result.complete(False, "Connection refused - service not running")
        except asyncio.TimeoutError:
            result.complete(False, "Connection timeout")
        except Exception as e:
            result.complete(False, f"WebSocket connection failed: {e}")
        
        return result
    
    async def test_service_health(self, service_name: str) -> TestResult:
        """Test service health endpoint."""
        result = TestResult(f"Service Health - {service_name}")
        
        if service_name not in self.services:
            result.complete(False, f"Unknown service: {service_name}")
            return result
        
        service = self.services[service_name]
        uri = f"ws://localhost:{service['port']}"
        
        try:
            async with websockets.connect(uri, open_timeout=5) as websocket:
                # Send health check request
                health_request = {
                    "type": "health_check",
                    "timestamp": time.time()
                }
                await websocket.send(json.dumps(health_request))
                
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                response_data = json.loads(response)
                
                if response_data.get("status") == "healthy":
                    result.complete(True, details={"health": response_data})
                else:
                    result.complete(False, f"Service unhealthy: {response_data}")
                    
        except Exception as e:
            result.complete(False, f"Health check failed: {e}")
        
        return result

class IntegrationTester:
    """Tests integration with real models."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_test_model(self) -> Optional[Dict]:
        """Get a test model for integration testing."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get first available model with port configuration
                cursor.execute("""
                    SELECT DISTINCT mc.model_slug, mc.provider, mc.model_name
                    FROM model_capabilities mc
                    JOIN port_configurations pc ON mc.model_slug = pc.model_slug
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if row:
                    return {
                        "model_slug": row[0],
                        "provider": row[1],
                        "model_name": row[2]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to get test model: {e}")
            return None
    
    async def test_model_analysis(self, service_name: str) -> TestResult:
        """Test analyzing a real model with a service."""
        result = TestResult(f"Model Analysis - {service_name}")
        
        # Get test model
        test_model = self.get_test_model()
        if not test_model:
            result.complete(False, "No test model available")
            return result
        
        service_tester = ServiceTester()
        service = service_tester.services.get(service_name)
        if not service:
            result.complete(False, f"Unknown service: {service_name}")
            return result
        
        uri = f"ws://localhost:{service['port']}"
        
        try:
            async with websockets.connect(uri, open_timeout=5) as websocket:
                # Send analysis request
                analysis_request = {
                    "type": "analyze",
                    "model_slug": test_model["model_slug"],
                    "app_number": 1,
                    "timestamp": time.time()
                }
                await websocket.send(json.dumps(analysis_request))
                
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=30)
                response_data = json.loads(response)
                
                if response_data.get("status") == "success":
                    result.complete(True, details={
                        "model": test_model,
                        "analysis": response_data
                    })
                else:
                    result.complete(False, f"Analysis failed: {response_data}")
                    
        except Exception as e:
            result.complete(False, f"Model analysis failed: {e}")
        
        return result

class TestSuite:
    """Main test suite orchestrator."""
    
    def __init__(self, db_path: str = None, verbose: bool = False):
        self.db_path = db_path or str(Path(__file__).parent.parent / "src" / "data" / "thesis_app.db")
        self.verbose = verbose
        self.results = []
        
        self.database_tester = DatabaseTester(self.db_path)
        self.service_tester = ServiceTester()
        self.integration_tester = IntegrationTester(self.db_path)
    
    def log_result(self, result: TestResult):
        """Log and store a test result."""
        self.results.append(result)
        
        if self.verbose or not result.success:
            print(result)
            if result.error_message:
                print(f"   Error: {result.error_message}")
            if result.details and self.verbose:
                print(f"   Details: {json.dumps(result.details, indent=2)}")
        else:
            print(f"✅ {result.test_name}")
    
    def run_database_tests(self):
        """Run all database tests."""
        print("\n🔍 Testing Database Connectivity...")
        
        result = self.database_tester.test_database_connection()
        self.log_result(result)
        
        if result.success:
            result = self.database_tester.test_model_discovery()
            self.log_result(result)
    
    def run_service_tests(self, service_name: str = None):
        """Run service availability tests."""
        print("\n🔍 Testing Service Availability...")
        
        services_to_test = [service_name] if service_name else list(self.service_tester.services.keys())
        
        for service in services_to_test:
            result = self.service_tester.test_service_availability(service)
            self.log_result(result)
    
    async def run_websocket_tests(self, service_name: str = None):
        """Run WebSocket connection tests."""
        print("\n🔍 Testing WebSocket Connections...")
        
        services_to_test = [service_name] if service_name else list(self.service_tester.services.keys())
        
        for service in services_to_test:
            result = await self.service_tester.test_websocket_connection(service)
            self.log_result(result)
    
    async def run_health_tests(self, service_name: str = None):
        """Run service health tests."""
        print("\n🔍 Testing Service Health...")
        
        services_to_test = [service_name] if service_name else list(self.service_tester.services.keys())
        
        for service in services_to_test:
            result = await self.service_tester.test_service_health(service)
            self.log_result(result)
    
    async def run_integration_tests(self, service_name: str = None):
        """Run integration tests with real models."""
        print("\n🔍 Testing Model Analysis Integration...")
        
        services_to_test = [service_name] if service_name else ['static']  # Start with static analyzer
        
        for service in services_to_test:
            result = await self.integration_tester.test_model_analysis(service)
            self.log_result(result)
    
    async def run_all_tests(self, quick: bool = False, service_name: str = None):
        """Run the complete test suite."""
        print("🧪 Starting Analyzer Infrastructure Test Suite")
        print("=" * 50)
        
        start_time = time.time()
        
        # Database tests (always run)
        self.run_database_tests()
        
        # Service tests
        self.run_service_tests(service_name)
        
        if not quick:
            # WebSocket tests
            await self.run_websocket_tests(service_name)
            
            # Health tests
            await self.run_health_tests(service_name)
            
            # Integration tests
            await self.run_integration_tests(service_name)
        
        # Generate summary
        self.generate_summary(time.time() - start_time)
    
    def generate_summary(self, total_time: float):
        """Generate test summary."""
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        print(f"Total Time: {total_time:.2f}s")
        
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.results:
                if not result.success:
                    print(f"  • {result.test_name}: {result.error_message}")
        
        # Save detailed results
        self.save_results()
        
        print("\nDetailed results saved to: test_suite_results.json")
        
        if failed_tests == 0:
            print("\n🎉 All tests passed! Analyzer infrastructure is ready.")
        else:
            print(f"\n⚠️ {failed_tests} tests failed. Please check the issues above.")
    
    def save_results(self):
        """Save test results to JSON file."""
        results_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": len(self.results),
                "passed": sum(1 for r in self.results if r.success),
                "failed": sum(1 for r in self.results if not r.success)
            },
            "tests": [
                {
                    "name": r.test_name,
                    "success": r.success,
                    "execution_time": r.execution_time,
                    "error_message": r.error_message,
                    "details": r.details
                }
                for r in self.results
            ]
        }
        
        with open("test_suite_results.json", "w") as f:
            json.dump(results_data, f, indent=2)

async def main():
    parser = argparse.ArgumentParser(description="Analyzer Infrastructure Test Suite")
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--quick', '-q', action='store_true', help='Run only essential tests')
    parser.add_argument('--service', help='Test only specified service')
    parser.add_argument('--db', help='Database path (optional)')
    
    args = parser.parse_args()
    
    test_suite = TestSuite(db_path=args.db, verbose=args.verbose)
    
    try:
        await test_suite.run_all_tests(quick=args.quick, service_name=args.service)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")

if __name__ == "__main__":
    asyncio.run(main())
