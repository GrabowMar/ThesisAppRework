"""
Performance Testing Service
==========================

Containerized performance testing service using Locust.
Provides REST API for load testing and performance analysis.
"""
import asyncio
import json
import logging
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Simple models for performance testing
class PerformanceTestRequest(BaseModel):
    target_url: str
    users: int = 10
    spawn_rate: int = 1
    duration: int = 60
    test_name: Optional[str] = None

class PerformanceTestResult(BaseModel):
    test_id: str
    status: str
    results: Optional[Dict] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Performance Testing Service",
    description="Containerized performance testing service",
    version="1.0.0"
)

# In-memory storage for active tests
active_tests: Dict[str, Dict] = {}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "performance-tester"}

@app.post("/test/performance")
async def create_performance_test(
    request: PerformanceTestRequest,
    background_tasks: BackgroundTasks
):
    """Create a new performance test."""
    test_id = str(uuid.uuid4())
    
    # Store test info
    test_info = {
        "test_id": test_id,
        "status": "pending",
        "request": request.model_dump(),
        "created_at": datetime.utcnow(),
        "started_at": None,
        "completed_at": None,
        "results": None
    }
    
    active_tests[test_id] = test_info
    
    # Start test in background
    background_tasks.add_task(run_performance_test, test_id, request)
    
    logger.info(f"Created performance test: {test_id}")
    return {"test_id": test_id, "status": "pending"}

@app.get("/test/{test_id}")
async def get_test_status(test_id: str):
    """Get test status and results."""
    if test_id not in active_tests:
        raise HTTPException(status_code=404, detail="Test not found")
    
    return active_tests[test_id]

@app.get("/tests")
async def list_tests():
    """List all tests."""
    return {"tests": list(active_tests.values())}

async def run_performance_test(test_id: str, request: PerformanceTestRequest):
    """Run performance test using Locust."""
    try:
        active_tests[test_id]["status"] = "running"
        active_tests[test_id]["started_at"] = datetime.utcnow()
        
        logger.info(f"Starting performance test: {test_id}")
        
        # Create a simple locust file
        locust_file = f"/tmp/locustfile_{test_id}.py"
        locust_content = f'''
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def index_page(self):
        self.client.get("/")
        
    @task
    def about_page(self):
        self.client.get("/about")
'''
        
        with open(locust_file, 'w') as f:
            f.write(locust_content)
        
        # Run locust command
        cmd = [
            "locust",
            "-f", locust_file,
            "--host", request.target_url,
            "--users", str(request.users),
            "--spawn-rate", str(request.spawn_rate),
            "--run-time", f"{request.duration}s",
            "--headless",
            "--only-summary"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=request.duration + 60)
        
        # Parse results
        results = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "summary": "Performance test completed"
        }
        
        active_tests[test_id]["status"] = "completed" if result.returncode == 0 else "failed"
        active_tests[test_id]["completed_at"] = datetime.utcnow()
        active_tests[test_id]["results"] = results
        
        logger.info(f"Completed performance test: {test_id}")
        
    except Exception as e:
        logger.error(f"Performance test failed: {test_id} - {str(e)}")
        active_tests[test_id]["status"] = "failed"
        active_tests[test_id]["completed_at"] = datetime.utcnow()
        active_tests[test_id]["results"] = {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
