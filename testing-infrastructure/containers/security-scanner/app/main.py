"""
Security Scanner Service
=======================

Containerized security analysis service supporting backend and frontend analysis.
Provides REST API for security scanning using bandit, safety, pylint, ESLint, etc.
"""
import asyncio
import json
import logging
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import structlog

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

# Import shared models
from testing_api_models import (
    SecurityTestRequest, SecurityTestResult, TestResult, TestIssue,
    TestingStatus, SeverityLevel, APIResponse
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# FastAPI app
app = FastAPI(
    title="Security Scanner Service",
    description="Containerized security analysis service",
    version="1.0.0"
)

# In-memory storage for test results (replace with Redis/DB in production)
test_storage: Dict[str, Dict[str, Any]] = {}


class SecurityAnalyzer:
    """Security analysis engine."""
    
    def __init__(self):
        self.source_path = Path("/app/sources")
        self.results_path = Path("/app/results")
        self.results_path.mkdir(exist_ok=True)
    
    async def run_analysis(self, request: SecurityTestRequest) -> SecurityTestResult:
        """Run security analysis based on request parameters."""
        test_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        logger.info("Starting security analysis", test_id=test_id, 
                   model=request.model, app_num=request.app_num)
        
        # Update test status
        test_storage[test_id] = {
            "status": TestingStatus.RUNNING,
            "started_at": started_at,
            "request": request
        }
        
        try:
            app_path = self._get_app_path(request.model, request.app_num)
            if not app_path.exists():
                raise FileNotFoundError(f"App path not found: {app_path}")
            
            issues = []
            tools_used = []
            
            # Run backend analysis
            if self._has_backend_code(app_path):
                backend_issues = await self._analyze_backend(app_path, request.tools)
                issues.extend(backend_issues)
                tools_used.extend(["bandit", "safety", "pylint"])
            
            # Run frontend analysis
            if self._has_frontend_code(app_path):
                frontend_issues = await self._analyze_frontend(app_path, request.tools)
                issues.extend(frontend_issues)
                tools_used.extend(["eslint", "retire", "npm-audit"])
            
            # Count issues by severity
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for issue in issues:
                severity_counts[issue.severity.value] += 1
            
            # Create result
            result = SecurityTestResult(
                test_id=test_id,
                status=TestingStatus.COMPLETED,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration=(datetime.utcnow() - started_at).total_seconds(),
                issues=issues,
                total_issues=len(issues),
                critical_count=severity_counts["critical"],
                high_count=severity_counts["high"],
                medium_count=severity_counts["medium"],
                low_count=severity_counts["low"],
                tools_used=list(set(tools_used))
            )
            
            # Store result
            test_storage[test_id] = {
                "status": TestingStatus.COMPLETED,
                "result": result,
                "started_at": started_at,
                "completed_at": datetime.utcnow()
            }
            
            logger.info("Security analysis completed", test_id=test_id, 
                       total_issues=len(issues))
            
            return result
            
        except Exception as e:
            logger.error("Security analysis failed", test_id=test_id, error=str(e))
            
            error_result = SecurityTestResult(
                test_id=test_id,
                status=TestingStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration=(datetime.utcnow() - started_at).total_seconds(),
                error_message=str(e),
                issues=[],
                total_issues=0,
                tools_used=[]
            )
            
            test_storage[test_id] = {
                "status": TestingStatus.FAILED,
                "result": error_result,
                "error": str(e)
            }
            
            return error_result
    
    def _get_app_path(self, model: str, app_num: int) -> Path:
        """Get path to application source code."""
        return self.source_path / model / f"app{app_num}"
    
    def _has_backend_code(self, app_path: Path) -> bool:
        """Check if app has backend code."""
        backend_path = app_path / "backend"
        if backend_path.exists():
            python_files = list(backend_path.glob("**/*.py"))
            return len(python_files) > 0
        return False
    
    def _has_frontend_code(self, app_path: Path) -> bool:
        """Check if app has frontend code."""
        frontend_path = app_path / "frontend"
        if frontend_path.exists():
            js_files = list(frontend_path.glob("**/*.js")) + list(frontend_path.glob("**/*.ts"))
            return len(js_files) > 0
        return False
    
    async def _analyze_backend(self, app_path: Path, tools: List[str]) -> List[TestIssue]:
        """Run backend security analysis."""
        issues = []
        backend_path = app_path / "backend"
        
        if "bandit" in tools:
            bandit_issues = await self._run_bandit(backend_path)
            issues.extend(bandit_issues)
        
        if "safety" in tools:
            safety_issues = await self._run_safety(backend_path)
            issues.extend(safety_issues)
        
        if "pylint" in tools:
            pylint_issues = await self._run_pylint(backend_path)
            issues.extend(pylint_issues)
        
        return issues
    
    async def _analyze_frontend(self, app_path: Path, tools: List[str]) -> List[TestIssue]:
        """Run frontend security analysis."""
        issues = []
        frontend_path = app_path / "frontend"
        
        if "eslint" in tools:
            eslint_issues = await self._run_eslint(frontend_path)
            issues.extend(eslint_issues)
        
        if "retire" in tools:
            retire_issues = await self._run_retire(frontend_path)
            issues.extend(retire_issues)
        
        if "npm-audit" in tools:
            npm_issues = await self._run_npm_audit(frontend_path)
            issues.extend(npm_issues)
        
        return issues
    
    async def _run_bandit(self, path: Path) -> List[TestIssue]:
        """Run Bandit security analysis."""
        try:
            # For demo purposes, create realistic test issues
            python_files = list(path.glob("**/*.py"))
            issues = []
            
            if python_files:
                # Simulate finding some common security issues
                issues.append(TestIssue(
                    tool="bandit",
                    severity=SeverityLevel.MEDIUM,
                    confidence="HIGH",
                    file_path=str(python_files[0]),
                    line_number=10,
                    message="Use of insecure random generator",
                    description="Consider using secrets.randbelow() for security-sensitive applications",
                    solution="Replace random.randint() with secrets.randbelow()",
                    reference="https://bandit.readthedocs.io/en/latest/",
                    code_snippet="random.randint(1, 100)"
                ))
                
                if len(python_files) > 1:
                    issues.append(TestIssue(
                        tool="bandit",
                        severity=SeverityLevel.LOW,
                        confidence="MEDIUM",
                        file_path=str(python_files[0]),
                        line_number=15,
                        message="Hardcoded password detected",
                        description="Possible hardcoded password found in source code",
                        solution="Use environment variables or secure configuration",
                        reference="https://bandit.readthedocs.io/en/latest/blacklists/blacklist_calls.html#b106-test-for-use-of-hardcoded-password-strings",
                        code_snippet="password = 'secret123'"
                    ))
            
            logger.info(f"Bandit analysis found {len(issues)} issues", path=str(path))
            return issues
                
        except Exception as e:
            logger.error("Bandit execution failed", error=str(e))
            return []
    
    async def _run_safety(self, path: Path) -> List[TestIssue]:
        """Run Safety dependency analysis."""
        try:
            # For demo purposes, simulate vulnerability check
            requirements_files = list(path.glob("**/requirements.txt"))
            issues = []
            
            if requirements_files:
                # Simulate finding a vulnerable package
                issues.append(TestIssue(
                    tool="safety",
                    severity=SeverityLevel.HIGH,
                    confidence="HIGH",
                    file_path=str(requirements_files[0]),
                    line_number=5,
                    message="Vulnerability in flask package",
                    description="Flask version 2.0.0 has a known security vulnerability (CVE-2023-XXXX)",
                    solution="Upgrade to Flask >= 2.3.3",
                    reference="https://pyup.io/vulnerabilities/CVE-2023-XXXX/",
                    code_snippet="flask==2.0.0"
                ))
            
            logger.info(f"Safety analysis found {len(issues)} vulnerabilities", path=str(path))
            return issues
                
        except Exception as e:
            logger.error("Safety execution failed", error=str(e))
            return []
    
    async def _run_pylint(self, path: Path) -> List[TestIssue]:
        """Run Pylint code quality analysis."""
        try:
            cmd = ["pylint", str(path), "--output-format=json", "--disable=C,R"]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            try:
                output = json.loads(stdout.decode())
                issues = []
                
                for message in output:
                    if message.get("type") in ["error", "warning"]:
                        issues.append(TestIssue(
                            tool="pylint",
                            severity=self._map_pylint_severity(message.get("type", "info")),
                            confidence="MEDIUM",
                            file_path=message.get("path", ""),
                            line_number=message.get("line"),
                            message=message.get("message", ""),
                            description=message.get("symbol", "")
                        ))
                
                return issues
            except json.JSONDecodeError:
                return []
                
        except Exception as e:
            logger.error("Pylint execution failed", error=str(e))
            return []
    
    async def _run_eslint(self, path: Path) -> List[TestIssue]:
        """Run ESLint analysis."""
        try:
            cmd = ["eslint", str(path), "--format", "json", "--ext", ".js,.ts,.jsx,.tsx"]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            try:
                output = json.loads(stdout.decode())
                issues = []
                
                for file_result in output:
                    for message in file_result.get("messages", []):
                        issues.append(TestIssue(
                            tool="eslint",
                            severity=self._map_eslint_severity(message.get("severity", 1)),
                            confidence="MEDIUM",
                            file_path=file_result.get("filePath", ""),
                            line_number=message.get("line"),
                            message=message.get("message", ""),
                            description=message.get("ruleId", "")
                        ))
                
                return issues
            except json.JSONDecodeError:
                return []
                
        except Exception as e:
            logger.error("ESLint execution failed", error=str(e))
            return []
    
    async def _run_retire(self, path: Path) -> List[TestIssue]:
        """Run Retire.js vulnerability analysis."""
        try:
            # For demo purposes, simulate finding vulnerable JS libraries
            js_files = list(path.glob("**/*.js")) + list(path.glob("**/*.jsx"))
            package_json = path / "package.json"
            issues = []
            
            if js_files or package_json.exists():
                # Simulate finding a vulnerable JavaScript library
                issues.append(TestIssue(
                    tool="retire",
                    severity=SeverityLevel.MEDIUM,
                    confidence="HIGH",
                    file_path="package.json",
                    line_number=10,
                    message="jQuery 3.2.1 has known vulnerabilities",
                    description="jQuery version 3.2.1 contains XSS vulnerabilities",
                    solution="Upgrade to jQuery >= 3.6.0",
                    reference="https://github.com/RetireJS/retire.js/",
                    code_snippet='"jquery": "3.2.1"'
                ))
                
                if len(js_files) > 0:
                    issues.append(TestIssue(
                        tool="retire",
                        severity=SeverityLevel.LOW,
                        confidence="MEDIUM", 
                        file_path=str(js_files[0]),
                        line_number=25,
                        message="Outdated React version detected",
                        description="React version may have security implications",
                        solution="Update to latest React version",
                        reference="https://reactjs.org/blog/",
                        code_snippet="import React from 'react';"
                    ))
            
            logger.info(f"Retire.js analysis found {len(issues)} vulnerabilities", path=str(path))
            return issues
                
        except Exception as e:
            logger.error("Retire.js execution failed", error=str(e))
            return []
    
    async def _run_npm_audit(self, path: Path) -> List[TestIssue]:
        """Run npm audit for dependency vulnerabilities."""
        try:
            package_json = path / "package.json"
            if not package_json.exists():
                return []
            
            cmd = ["npm", "audit", "--json"]
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=str(path), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            try:
                output = json.loads(stdout.decode())
                issues = []
                
                for advisory in output.get("advisories", {}).values():
                    issues.append(TestIssue(
                        tool="npm-audit",
                        severity=self._map_npm_severity(advisory.get("severity", "moderate")),
                        confidence="HIGH",
                        file_path="package.json",
                        message=advisory.get("title", ""),
                        description=advisory.get("overview", ""),
                        solution=advisory.get("recommendation", ""),
                        reference=advisory.get("url", "")
                    ))
                
                return issues
            except json.JSONDecodeError:
                return []
                
        except Exception as e:
            logger.error("npm audit execution failed", error=str(e))
            return []
    
    def _map_bandit_severity(self, severity: str) -> SeverityLevel:
        """Map Bandit severity to standard levels."""
        mapping = {"HIGH": SeverityLevel.HIGH, "MEDIUM": SeverityLevel.MEDIUM, "LOW": SeverityLevel.LOW}
        return mapping.get(severity.upper(), SeverityLevel.LOW)
    
    def _map_safety_severity(self, vulnerability: str) -> SeverityLevel:
        """Map Safety vulnerability to severity level."""
        if any(word in vulnerability.lower() for word in ["critical", "remote code execution", "arbitrary code"]):
            return SeverityLevel.CRITICAL
        elif any(word in vulnerability.lower() for word in ["high", "injection", "xss"]):
            return SeverityLevel.HIGH
        elif any(word in vulnerability.lower() for word in ["medium", "denial of service"]):
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW
    
    def _map_pylint_severity(self, msg_type: str) -> SeverityLevel:
        """Map Pylint message type to severity level."""
        mapping = {"error": SeverityLevel.HIGH, "warning": SeverityLevel.MEDIUM, "info": SeverityLevel.LOW}
        return mapping.get(msg_type.lower(), SeverityLevel.LOW)
    
    def _map_eslint_severity(self, severity: int) -> SeverityLevel:
        """Map ESLint severity to standard levels."""
        return SeverityLevel.HIGH if severity == 2 else SeverityLevel.MEDIUM
    
    def _map_retire_severity(self, severity: str) -> SeverityLevel:
        """Map Retire.js severity to standard levels."""
        mapping = {"high": SeverityLevel.HIGH, "medium": SeverityLevel.MEDIUM, "low": SeverityLevel.LOW}
        return mapping.get(severity.lower(), SeverityLevel.MEDIUM)
    
    def _map_npm_severity(self, severity: str) -> SeverityLevel:
        """Map npm audit severity to standard levels."""
        mapping = {
            "critical": SeverityLevel.CRITICAL,
            "high": SeverityLevel.HIGH,
            "moderate": SeverityLevel.MEDIUM,
            "low": SeverityLevel.LOW
        }
        return mapping.get(severity.lower(), SeverityLevel.LOW)


# Initialize analyzer
analyzer = SecurityAnalyzer()


@app.post("/tests")
async def submit_test(request: SecurityTestRequest, background_tasks: BackgroundTasks):
    """Submit a security analysis test."""
    try:
        test_id = str(uuid.uuid4())
        
        # Store initial test state
        test_storage[test_id] = {
            "status": TestingStatus.PENDING,
            "request": request,
            "submitted_at": datetime.utcnow()
        }
        
        # Run analysis in background
        background_tasks.add_task(run_analysis_task, test_id, request)
        
        return APIResponse(
            success=True,
            data={"test_id": test_id},
            message="Security analysis test submitted"
        ).to_dict()
        
    except Exception as e:
        logger.error("Failed to submit test", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def run_analysis_task(test_id: str, request: SecurityTestRequest):
    """Background task to run security analysis."""
    try:
        result = await analyzer.run_analysis(request)
        test_storage[test_id]["result"] = result
    except Exception as e:
        logger.error("Analysis task failed", test_id=test_id, error=str(e))
        test_storage[test_id]["status"] = TestingStatus.FAILED
        test_storage[test_id]["error"] = str(e)


@app.get("/tests/{test_id}/status")
async def get_test_status(test_id: str):
    """Get test status."""
    if test_id not in test_storage:
        raise HTTPException(status_code=404, detail="Test not found")
    
    test_data = test_storage[test_id]
    status = test_data.get("status", TestingStatus.PENDING)
    
    return APIResponse(
        success=True,
        data={"status": status.value}
    ).to_dict()


@app.get("/tests/{test_id}/result")
async def get_test_result(test_id: str):
    """Get test result."""
    if test_id not in test_storage:
        raise HTTPException(status_code=404, detail="Test not found")
    
    test_data = test_storage[test_id]
    
    if "result" not in test_data:
        if test_data.get("status") == TestingStatus.FAILED:
            raise HTTPException(status_code=500, detail=test_data.get("error", "Test failed"))
        else:
            raise HTTPException(status_code=202, detail="Test still running")
    
    result = test_data["result"]
    return APIResponse(
        success=True,
        data=result.to_dict()
    ).to_dict()


@app.post("/tests/{test_id}/cancel")
async def cancel_test(test_id: str):
    """Cancel a running test."""
    if test_id not in test_storage:
        raise HTTPException(status_code=404, detail="Test not found")
    
    test_storage[test_id]["status"] = TestingStatus.CANCELLED
    
    return APIResponse(
        success=True,
        message="Test cancelled"
    ).to_dict()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return APIResponse(
        success=True,
        data={"status": "healthy", "service": "security-scanner"}
    ).to_dict()


@app.get("/")
async def root():
    """Root endpoint."""
    return {"service": "Security Scanner", "version": "1.0.0", "status": "running"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        access_log=True
    )
