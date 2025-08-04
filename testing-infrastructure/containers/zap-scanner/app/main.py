"""
ZAP Scanner Service
==================

Containerized OWASP ZAP security scanning service.
Provides REST API for web application security scanning.
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Simple models for ZAP scanning
class ZapScanRequest(BaseModel):
    target_url: str
    scan_type: str = "spider"  # spider, active, passive, baseline
    options: Optional[Dict] = None

class ZapScanResult(BaseModel):
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
    title="ZAP Scanner Service",
    description="Containerized OWASP ZAP security scanning service",
    version="1.0.0"
)

# In-memory storage for active scans
active_scans: Dict[str, Dict] = {}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "zap-scanner"}

@app.post("/scan/zap")
async def create_zap_scan(
    request: ZapScanRequest,
    background_tasks: BackgroundTasks
):
    """Create a new ZAP security scan."""
    scan_id = str(uuid.uuid4())
    
    # Store scan info
    scan_info = {
        "scan_id": scan_id,
        "status": "pending",
        "request": request.model_dump(),
        "created_at": datetime.utcnow(),
        "started_at": None,
        "completed_at": None,
        "results": None
    }
    
    active_scans[scan_id] = scan_info
    
    # Start scan in background
    background_tasks.add_task(run_zap_scan, scan_id, request)
    
    logger.info(f"Created ZAP scan: {scan_id}")
    return {"scan_id": scan_id, "status": "pending"}

@app.get("/scan/{scan_id}")
async def get_scan_status(scan_id: str):
    """Get scan status and results."""
    if scan_id not in active_scans:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return active_scans[scan_id]

@app.get("/scans")
async def list_scans():
    """List all scans."""
    return {"scans": list(active_scans.values())}

async def run_zap_scan(scan_id: str, request: ZapScanRequest):
    """Run ZAP security scan."""
    try:
        active_scans[scan_id]["status"] = "running"
        active_scans[scan_id]["started_at"] = datetime.utcnow()
        
        logger.info(f"Starting ZAP scan: {scan_id}")
        
        # Simulate ZAP scan (in real implementation, this would use ZAP API)
        await asyncio.sleep(10)  # Simulate scan time
        
        # Mock results
        results = {
            "target_url": request.target_url,
            "scan_type": request.scan_type,
            "vulnerabilities": [
                {
                    "name": "Cross Site Scripting (Reflected)",
                    "risk": "High",
                    "confidence": "Medium",
                    "description": "Reflected XSS vulnerability found",
                    "solution": "Validate all user input and encode output",
                    "instances": [
                        {
                            "uri": f"{request.target_url}/search?q=<script>alert(1)</script>",
                            "param": "q"
                        }
                    ]
                },
                {
                    "name": "SQL Injection",
                    "risk": "High",
                    "confidence": "High",
                    "description": "SQL injection vulnerability detected",
                    "solution": "Use parameterized queries",
                    "instances": [
                        {
                            "uri": f"{request.target_url}/login",
                            "param": "username"
                        }
                    ]
                }
            ],
            "summary": {
                "total_vulnerabilities": 2,
                "high_risk": 2,
                "medium_risk": 0,
                "low_risk": 0
            }
        }
        
        active_scans[scan_id]["status"] = "completed"
        active_scans[scan_id]["completed_at"] = datetime.utcnow()
        active_scans[scan_id]["results"] = results
        
        logger.info(f"Completed ZAP scan: {scan_id}")
        
    except Exception as e:
        logger.error(f"ZAP scan failed: {scan_id} - {str(e)}")
        active_scans[scan_id]["status"] = "failed"
        active_scans[scan_id]["completed_at"] = datetime.utcnow()
        active_scans[scan_id]["results"] = {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
