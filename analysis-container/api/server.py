"""
Analysis Container API Server
============================

FastAPI server that provides analysis services for the thesis research platform.
Runs inside a containerized environment with all analysis tools pre-installed.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from .analyzers import (
    SecurityAnalyzer,
    PerformanceAnalyzer, 
    CodeQualityAnalyzer,
    ContainerAnalyzer
)
from .models import AnalysisRequest, AnalysisResult, AnalysisStatus, ToolType
from .utils import setup_logging, create_workspace, cleanup_workspace

# Setup logging
logger = setup_logging()

# Initialize FastAPI app
app = FastAPI(
    title="Analysis Container API",
    description="Containerized analysis services for thesis research platform",
    version="1.0.0"
)

# Global analyzer instances
analyzers = {
    'security': SecurityAnalyzer(),
    'performance': PerformanceAnalyzer(),
    'code_quality': CodeQualityAnalyzer(),
    'container': ContainerAnalyzer()
}

# In-memory job tracking (in production, use Redis or database)
active_jobs: Dict[str, Dict[str, Any]] = {}

class AnalysisJobRequest(BaseModel):
    """Request model for analysis jobs."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_app_path: str
    analysis_types: List[str]
    tools: List[str] = Field(default_factory=list)
    options: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=1, le=10)

class AnalysisJobStatus(BaseModel):
    """Response model for job status."""
    job_id: str
    status: str
    progress: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    results: Optional[Dict[str, Any]]
    errors: List[str] = Field(default_factory=list)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "analyzers": list(analyzers.keys()),
        "active_jobs": len(active_jobs)
    }

@app.get("/tools")
async def list_available_tools():
    """List all available analysis tools."""
    tools = {}
    for analyzer_type, analyzer in analyzers.items():
        tools[analyzer_type] = analyzer.get_available_tools()
    
    return {
        "tools": tools,
        "total_tools": sum(len(t) for t in tools.values())
    }

@app.post("/analyze", response_model=AnalysisJobStatus)
async def start_analysis(request: AnalysisJobRequest, background_tasks: BackgroundTasks):
    """Start a new analysis job."""
    job_id = request.job_id
    
    # Validate request
    if not Path(request.target_app_path).exists():
        raise HTTPException(status_code=400, detail="Target application path does not exist")
    
    # Initialize job tracking
    active_jobs[job_id] = {
        "status": "pending",
        "progress": 0.0,
        "started_at": None,
        "completed_at": None,
        "results": None,
        "errors": [],
        "request": request.dict()
    }
    
    # Start analysis in background
    background_tasks.add_task(run_analysis_job, job_id, request)
    
    return AnalysisJobStatus(
        job_id=job_id,
        status="pending",
        progress=0.0,
        started_at=None,
        completed_at=None,
        results=None
    )

@app.get("/jobs/{job_id}", response_model=AnalysisJobStatus)
async def get_job_status(job_id: str):
    """Get status of an analysis job."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = active_jobs[job_id]
    
    return AnalysisJobStatus(
        job_id=job_id,
        status=job_data["status"],
        progress=job_data["progress"],
        started_at=job_data["started_at"],
        completed_at=job_data["completed_at"],
        results=job_data["results"],
        errors=job_data["errors"]
    )

@app.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel an analysis job."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = active_jobs[job_id]
    
    if job_data["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")
    
    # Mark as cancelled
    job_data["status"] = "cancelled"
    job_data["completed_at"] = datetime.utcnow()
    
    return {"message": f"Job {job_id} cancelled"}

@app.get("/jobs")
async def list_jobs():
    """List all jobs."""
    return {
        "jobs": [
            {
                "job_id": job_id,
                "status": data["status"],
                "progress": data["progress"],
                "started_at": data["started_at"],
                "completed_at": data["completed_at"]
            }
            for job_id, data in active_jobs.items()
        ],
        "total": len(active_jobs)
    }

async def run_analysis_job(job_id: str, request: AnalysisJobRequest):
    """Run analysis job in background."""
    try:
        # Update status
        active_jobs[job_id]["status"] = "running"
        active_jobs[job_id]["started_at"] = datetime.utcnow()
        
        logger.info(f"Starting analysis job {job_id}")
        
        # Create workspace
        workspace_path = create_workspace(job_id)
        
        # Copy target application to workspace
        import shutil
        target_path = workspace_path / "target_app"
        shutil.copytree(request.target_app_path, target_path)
        
        results = {}
        total_analyzers = len(request.analysis_types)
        completed_analyzers = 0
        
        # Run each requested analyzer
        for analysis_type in request.analysis_types:
            if analysis_type not in analyzers:
                logger.warning(f"Unknown analysis type: {analysis_type}")
                continue
            
            try:
                logger.info(f"Running {analysis_type} analysis")
                
                analyzer = analyzers[analysis_type]
                analyzer_results = await analyzer.analyze(
                    target_path=str(target_path),
                    tools=request.tools,
                    options=request.options
                )
                
                results[analysis_type] = analyzer_results
                completed_analyzers += 1
                
                # Update progress
                progress = (completed_analyzers / total_analyzers) * 100
                active_jobs[job_id]["progress"] = progress
                
                logger.info(f"Completed {analysis_type} analysis ({progress:.1f}%)")
                
            except Exception as e:
                logger.error(f"Failed to run {analysis_type} analysis: {str(e)}")
                active_jobs[job_id]["errors"].append(f"{analysis_type}: {str(e)}")
                results[analysis_type] = {"error": str(e)}
        
        # Update final status
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["completed_at"] = datetime.utcnow()
        active_jobs[job_id]["results"] = results
        active_jobs[job_id]["progress"] = 100.0
        
        logger.info(f"Analysis job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Analysis job {job_id} failed: {str(e)}")
        
        # Update error status
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["completed_at"] = datetime.utcnow()
        active_jobs[job_id]["errors"].append(str(e))
        
    finally:
        # Cleanup workspace
        try:
            cleanup_workspace(job_id)
        except Exception as e:
            logger.warning(f"Failed to cleanup workspace: {str(e)}")

if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
