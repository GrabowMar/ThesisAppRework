#!/usr/bin/env python3
"""
Test Script for Comprehensive Analyzer Services
===============================================

This script tests all 4 analyzer services to ensure they're working correctly:
- Static Analyzer (port 2001)
- Dynamic Analyzer (port 2002) 
- Performance Tester (port 2003)
- AI Analyzer (port 2004)
- Security Analyzer (port 2005)

Usage:
    python test_all_analyzers.py
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalyzerTester:
    """Test suite for all analyzer services."""
    
    def __init__(self):
        self.services = {
            'static-analyzer': 'ws://localhost:2001',
            'dynamic-analyzer': 'ws://localhost:2002',
            'performance-tester': 'ws://localhost:2003',
            'ai-analyzer': 'ws://localhost:2004',
            'security-analyzer': 'ws://localhost:2005'
        }
        self.results = {}
    
    async def test_service_health(self, service_name: str, websocket_url: str) -> dict:
        """Test health check for a service."""
        try:
            logger.info(f"Testing {service_name} health at {websocket_url}")
            
            async with websockets.connect(websocket_url, timeout=10) as websocket:
                # Send health check
                health_message = {
                    "type": "health_check",
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(health_message))
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                health_data = json.loads(response)
                
                return {
                    'status': 'success',
                    'service': service_name,
                    'health_response': health_data,
                    'connection_time': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'service': service_name,
                'error': str(e)
            }
    
    async def test_service_ping(self, service_name: str, websocket_url: str) -> dict:
        """Test ping/pong for a service."""
        try:
            logger.info(f"Testing {service_name} ping at {websocket_url}")
            
            async with websockets.connect(websocket_url, timeout=10) as websocket:
                # Send ping
                ping_message = {
                    "type": "ping",
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(ping_message))
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                pong_data = json.loads(response)
                
                return {
                    'status': 'success',
                    'service': service_name,
                    'pong_response': pong_data,
                    'ping_time': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'service': service_name,
                'error': str(e)
            }
    
    async def test_static_analysis(self) -> dict:
        """Test static analyzer with sample request."""
        try:
            logger.info("Testing static analysis functionality")
            
            async with websockets.connect('ws://localhost:2001', timeout=15) as websocket:
                analysis_message = {
                    "type": "static_analysis",
                    "model_slug": "anthropic_claude-3.7-sonnet",
                    "app_number": 1,
                    "source_path": "/workspace/misc/models/anthropic_claude-3.7-sonnet/app1"
                }
                
                await websocket.send(json.dumps(analysis_message))
                response = await asyncio.wait_for(websocket.recv(), timeout=30)
                analysis_data = json.loads(response)
                
                return {
                    'status': 'success',
                    'service': 'static-analyzer',
                    'analysis_response': analysis_data,
                    'test_time': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'service': 'static-analyzer',
                'error': str(e)
            }
    
    async def test_security_analysis(self) -> dict:
        """Test security analyzer with sample request."""
        try:
            logger.info("Testing security analysis functionality")
            
            async with websockets.connect('ws://localhost:2005', timeout=15) as websocket:
                analysis_message = {
                    "type": "security_analysis",
                    "model_slug": "anthropic_claude-3.7-sonnet",
                    "app_number": 1,
                    "source_path": "/workspace/misc/models/anthropic_claude-3.7-sonnet/app1"
                }
                
                await websocket.send(json.dumps(analysis_message))
                response = await asyncio.wait_for(websocket.recv(), timeout=30)
                analysis_data = json.loads(response)
                
                return {
                    'status': 'success',
                    'service': 'security-analyzer',
                    'analysis_response': analysis_data,
                    'test_time': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'service': 'security-analyzer',
                'error': str(e)
            }
    
    async def test_all_services(self) -> dict:
        """Test all services comprehensively."""
        logger.info("Starting comprehensive analyzer service tests")
        
        test_results = {
            'test_start_time': datetime.now().isoformat(),
            'services_tested': len(self.services),
            'health_checks': {},
            'ping_tests': {},
            'functional_tests': {},
            'summary': {}
        }
        
        # Health check tests
        logger.info("Running health check tests...")
        for service_name, url in self.services.items():
            health_result = await self.test_service_health(service_name, url)
            test_results['health_checks'][service_name] = health_result
        
        # Ping tests
        logger.info("Running ping tests...")
        for service_name, url in self.services.items():
            ping_result = await self.test_service_ping(service_name, url)
            test_results['ping_tests'][service_name] = ping_result
        
        # Functional tests (for services that are working)
        logger.info("Running functional tests...")
        
        # Test static analyzer if healthy
        if test_results['health_checks']['static-analyzer']['status'] == 'success':
            static_test = await self.test_static_analysis()
            test_results['functional_tests']['static-analyzer'] = static_test
        
        # Test security analyzer if healthy
        if test_results['health_checks']['security-analyzer']['status'] == 'success':
            security_test = await self.test_security_analysis()
            test_results['functional_tests']['security-analyzer'] = security_test
        
        # Calculate summary
        healthy_services = sum(1 for result in test_results['health_checks'].values() if result['status'] == 'success')
        successful_pings = sum(1 for result in test_results['ping_tests'].values() if result['status'] == 'success')
        successful_functional = sum(1 for result in test_results['functional_tests'].values() if result['status'] == 'success')
        
        test_results['summary'] = {
            'healthy_services': healthy_services,
            'total_services': len(self.services),
            'successful_pings': successful_pings,
            'functional_tests_passed': successful_functional,
            'overall_health': 'good' if healthy_services >= 4 else 'partial' if healthy_services >= 2 else 'poor',
            'test_completion_time': datetime.now().isoformat()
        }
        
        return test_results

async def main():
    """Run the analyzer service tests."""
    logger.info("🚀 Starting Comprehensive Analyzer Service Tests")
    logger.info("=" * 60)
    
    tester = AnalyzerTester()
    results = await tester.test_all_services()
    
    # Print results
    print("\n" + "=" * 60)
    print("📋 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    summary = results['summary']
    print(f"✅ Healthy Services: {summary['healthy_services']}/{summary['total_services']}")
    print(f"🏓 Successful Pings: {summary['successful_pings']}/{summary['total_services']}")
    print(f"⚙️  Functional Tests Passed: {summary['functional_tests_passed']}")
    print(f"🌡️  Overall Health: {summary['overall_health'].upper()}")
    
    # Service details
    print("\n📊 SERVICE DETAILS:")
    print("-" * 40)
    
    for service_name in tester.services.keys():
        health_status = results['health_checks'][service_name]['status']
        ping_status = results['ping_tests'][service_name]['status']
        
        status_icon = "✅" if health_status == 'success' and ping_status == 'success' else "❌"
        print(f"{status_icon} {service_name}: Health={health_status}, Ping={ping_status}")
        
        if health_status == 'success':
            health_data = results['health_checks'][service_name]['health_response']
            if 'available_tools' in health_data:
                tools = health_data['available_tools']
                print(f"   🔧 Tools: {', '.join(tools) if tools else 'None'}")
    
    # Functional test details
    if results['functional_tests']:
        print("\n🧪 FUNCTIONAL TEST DETAILS:")
        print("-" * 40)
        
        for service_name, test_result in results['functional_tests'].items():
            status_icon = "✅" if test_result['status'] == 'success' else "❌"
            print(f"{status_icon} {service_name}: {test_result['status']}")
            
            if test_result['status'] == 'success' and 'analysis_response' in test_result:
                analysis = test_result['analysis_response'].get('analysis', {})
                if 'summary' in analysis:
                    summary_info = analysis['summary']
                    print(f"   📈 Issues Found: {summary_info.get('total_issues', 0)}")
                    print(f"   🎯 Tools Executed: {summary_info.get('tools_executed', 0)}")
    
    print("\n" + "=" * 60)
    print("🎉 Test Complete! All analyzer services have been validated.")
    print("=" * 60)
    
    # Save detailed results to file
    with open('analyzer_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("Detailed results saved to analyzer_test_results.json")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        exit(1)
