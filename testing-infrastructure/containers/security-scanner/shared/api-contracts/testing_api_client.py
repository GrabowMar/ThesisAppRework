"""
Testing API Client
==================

Client for communicating with containerized testing services.
Handles HTTP requests, retries, and response parsing.
"""
import asyncio
import aiohttp
import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import sys

# Add shared contracts to path
sys.path.append(str(Path(__file__).parent.parent / "api-contracts"))
from testing_api_models import (
    TestRequest, TestResult, APIResponse, BatchTestRequest, BatchTestResult,
    SecurityTestRequest, PerformanceTestRequest, ZapTestRequest, AIAnalysisRequest,
    TestingStatus, TestType, create_test_result_from_dict
)


class TestingAPIClient:
    """Client for communicating with containerized testing services."""
    
    def __init__(self, base_url: str = "http://localhost", timeout: int = 300):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        # Service endpoints
        self.endpoints = {
            TestType.SECURITY_BACKEND: f"{base_url}:8001",
            TestType.SECURITY_FRONTEND: f"{base_url}:8001", 
            TestType.SECURITY_ZAP: f"{base_url}:8003",
            TestType.PERFORMANCE: f"{base_url}:8002",
            TestType.AI_ANALYSIS: f"{base_url}:8004",
            "coordinator": f"{base_url}:8005"
        }
    
    async def _make_request(self, method: str, url: str, data: Optional[Dict] = None,
                           timeout: Optional[int] = None) -> Dict[str, Any]:
        """Make HTTP request with error handling and retries."""
        timeout = timeout or self.timeout
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            try:
                if method.upper() == 'GET':
                    async with session.get(url) as response:
                        response.raise_for_status()
                        return await response.json()
                else:
                    async with session.request(method, url, json=data) as response:
                        response.raise_for_status()
                        return await response.json()
                        
            except aiohttp.ClientError as e:
                self.logger.error(f"Request failed: {e}")
                return {"success": False, "error": str(e)}
            except asyncio.TimeoutError:
                self.logger.error(f"Request timeout after {timeout}s")
                return {"success": False, "error": "Request timeout"}
    
    async def submit_test(self, request: TestRequest) -> str:
        """Submit a test request and return test ID."""
        endpoint = self.endpoints.get(request.test_type)
        if not endpoint:
            raise ValueError(f"No endpoint configured for test type: {request.test_type}")
        
        url = f"{endpoint}/tests"
        data = asdict(request)
        
        response = await self._make_request("POST", url, data)
        
        if response.get("success"):
            return response["data"]["test_id"]
        else:
            raise Exception(f"Failed to submit test: {response.get('error')}")
    
    async def get_test_status(self, test_id: str, test_type: TestType) -> TestingStatus:
        """Get the status of a running test."""
        endpoint = self.endpoints.get(test_type)
        url = f"{endpoint}/tests/{test_id}/status"
        
        response = await self._make_request("GET", url)
        
        if response.get("success"):
            return TestingStatus(response["data"]["status"])
        else:
            return TestingStatus.FAILED
    
    async def get_test_result(self, test_id: str, test_type: TestType) -> Optional[TestResult]:
        """Get the result of a completed test."""
        endpoint = self.endpoints.get(test_type)
        url = f"{endpoint}/tests/{test_id}/result"
        
        response = await self._make_request("GET", url)
        
        if response.get("success"):
            return create_test_result_from_dict(response["data"])
        else:
            return None
    
    async def cancel_test(self, test_id: str, test_type: TestType) -> bool:
        """Cancel a running test."""
        endpoint = self.endpoints.get(test_type)
        url = f"{endpoint}/tests/{test_id}/cancel"
        
        response = await self._make_request("POST", url)
        return response.get("success", False)
    
    async def run_security_analysis(self, model: str, app_num: int, 
                                   tools: List[str] = None) -> TestResult:
        """Run security analysis and wait for completion."""
        request = SecurityTestRequest(
            model=model,
            app_num=app_num,
            test_type=TestType.SECURITY_BACKEND,
            tools=tools or ["bandit", "safety", "pylint"]
        )
        
        test_id = await self.submit_test(request)
        return await self._wait_for_completion(test_id, request.test_type)
    
    async def run_performance_test(self, model: str, app_num: int, 
                                  target_url: str, users: int = 10) -> TestResult:
        """Run performance test and wait for completion."""
        request = PerformanceTestRequest(
            model=model,
            app_num=app_num,
            test_type=TestType.PERFORMANCE,
            users=users,
            target_url=target_url
        )
        
        test_id = await self.submit_test(request)
        return await self._wait_for_completion(test_id, request.test_type)
    
    async def run_zap_scan(self, model: str, app_num: int, 
                          target_url: str, scan_type: str = "spider") -> TestResult:
        """Run ZAP security scan and wait for completion."""
        request = ZapTestRequest(
            model=model,
            app_num=app_num,
            test_type=TestType.SECURITY_ZAP,
            target_url=target_url,
            scan_type=scan_type
        )
        
        test_id = await self.submit_test(request)
        return await self._wait_for_completion(test_id, request.test_type)
    
    async def run_ai_analysis(self, model: str, app_num: int, 
                             requirements: List[str]) -> TestResult:
        """Run AI-powered code analysis and wait for completion."""
        request = AIAnalysisRequest(
            model=model,
            app_num=app_num,
            test_type=TestType.AI_ANALYSIS,
            requirements=requirements
        )
        
        test_id = await self.submit_test(request)
        return await self._wait_for_completion(test_id, request.test_type)
    
    async def submit_batch_test(self, batch_request: BatchTestRequest) -> str:
        """Submit a batch test request."""
        url = f"{self.endpoints['coordinator']}/batch"
        data = asdict(batch_request)
        
        response = await self._make_request("POST", url, data)
        
        if response.get("success"):
            return response["data"]["batch_id"]
        else:
            raise Exception(f"Failed to submit batch test: {response.get('error')}")
    
    async def get_batch_status(self, batch_id: str) -> BatchTestResult:
        """Get the status of a batch test."""
        url = f"{self.endpoints['coordinator']}/batch/{batch_id}"
        
        response = await self._make_request("GET", url)
        
        if response.get("success"):
            data = response["data"]
            return BatchTestResult(
                batch_id=data["batch_id"],
                status=TestingStatus(data["status"]),
                total_tests=data["total_tests"],
                completed_tests=data["completed_tests"],
                failed_tests=data["failed_tests"],
                results=[create_test_result_from_dict(r) for r in data.get("results", [])],
                started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
                completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            )
        else:
            raise Exception(f"Failed to get batch status: {response.get('error')}")
    
    async def _wait_for_completion(self, test_id: str, test_type: TestType, 
                                  poll_interval: int = 5) -> TestResult:
        """Wait for test completion and return result."""
        while True:
            status = await self.get_test_status(test_id, test_type)
            
            if status in [TestingStatus.COMPLETED, TestingStatus.FAILED, TestingStatus.CANCELLED]:
                result = await self.get_test_result(test_id, test_type)
                if result:
                    return result
                else:
                    raise Exception(f"Failed to get result for test {test_id}")
            
            await asyncio.sleep(poll_interval)
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all testing services."""
        health_status = {}
        
        for service_name, endpoint in self.endpoints.items():
            try:
                url = f"{endpoint}/health"
                response = await self._make_request("GET", url, timeout=10)
                health_status[service_name] = response.get("success", False)
            except:
                health_status[service_name] = False
        
        return health_status


# Synchronous wrapper for non-async contexts
class SyncTestingAPIClient:
    """Synchronous wrapper for TestingAPIClient."""
    
    def __init__(self, base_url: str = "http://localhost", timeout: int = 300):
        self.async_client = TestingAPIClient(base_url, timeout)
        self.logger = logging.getLogger(__name__)
    
    def _run_async(self, coro):
        """Run async coroutine in sync context."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)
    
    def submit_test(self, request: TestRequest) -> str:
        """Submit a test request and return test ID."""
        return self._run_async(self.async_client.submit_test(request))
    
    def get_test_status(self, test_id: str, test_type: TestType) -> TestingStatus:
        """Get the status of a running test."""
        return self._run_async(self.async_client.get_test_status(test_id, test_type))
    
    def get_test_result(self, test_id: str, test_type: TestType) -> Optional[TestResult]:
        """Get the result of a completed test."""
        return self._run_async(self.async_client.get_test_result(test_id, test_type))
    
    def cancel_test(self, test_id: str, test_type: TestType) -> bool:
        """Cancel a running test."""
        return self._run_async(self.async_client.cancel_test(test_id, test_type))
    
    def run_security_analysis(self, model: str, app_num: int, 
                             tools: List[str] = None) -> TestResult:
        """Run security analysis and wait for completion."""
        return self._run_async(
            self.async_client.run_security_analysis(model, app_num, tools)
        )
    
    def run_performance_test(self, model: str, app_num: int, 
                            target_url: str, users: int = 10) -> TestResult:
        """Run performance test and wait for completion."""
        return self._run_async(
            self.async_client.run_performance_test(model, app_num, target_url, users)
        )
    
    def run_zap_scan(self, model: str, app_num: int, 
                    target_url: str, scan_type: str = "spider") -> TestResult:
        """Run ZAP security scan and wait for completion."""
        return self._run_async(
            self.async_client.run_zap_scan(model, app_num, target_url, scan_type)
        )
    
    def run_ai_analysis(self, model: str, app_num: int, 
                       requirements: List[str]) -> TestResult:
        """Run AI-powered code analysis and wait for completion."""
        return self._run_async(
            self.async_client.run_ai_analysis(model, app_num, requirements)
        )
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all testing services."""
        return self._run_async(self.async_client.health_check())
