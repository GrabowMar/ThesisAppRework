"""
Analysis Container - Analyzer Implementations
=============================================

Concrete implementations of analysis tools in containerized environment.
"""

import asyncio
import json
import logging
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import ToolResult, AnalysisStatus, ToolType
from .utils import load_tool_config

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """Base class for all analyzers."""
    
    def __init__(self, analyzer_type: str):
        self.analyzer_type = analyzer_type
        self.logger = logging.getLogger(f'analyzer.{analyzer_type}')
    
    @abstractmethod
    async def analyze(self, target_path: str, tools: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
        """Run analysis on target path."""
        pass
    
    @abstractmethod
    def get_available_tools(self) -> List[str]:
        """Get list of available tools for this analyzer."""
        pass
    
    async def run_tool(self, tool: ToolType, target_path: str, options: Dict[str, Any]) -> ToolResult:
        """Run a specific tool."""
        import time
        start_time = time.time()
        
        try:
            config = load_tool_config(tool.value)
            result = await self._execute_tool(tool, target_path, {**config, **options})
            
            duration = time.time() - start_time
            
            return ToolResult(
                tool=tool,
                status=AnalysisStatus.COMPLETED,
                duration=duration,
                output=result,
                metrics={"execution_time": duration}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Tool {tool.value} failed: {str(e)}")
            
            return ToolResult(
                tool=tool,
                status=AnalysisStatus.FAILED,
                duration=duration,
                output={},
                errors=[str(e)]
            )
    
    @abstractmethod
    async def _execute_tool(self, tool: ToolType, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Execute specific tool - to be implemented by subclasses."""
        pass


class SecurityAnalyzer(BaseAnalyzer):
    """Security analysis tools."""
    
    def __init__(self):
        super().__init__("security")
    
    def get_available_tools(self) -> List[str]:
        return [
            ToolType.BANDIT.value,
            ToolType.SAFETY.value,
            ToolType.SEMGREP.value,
            ToolType.ESLINT.value,
            ToolType.RETIRE_JS.value,
            ToolType.SNYK.value,
            ToolType.TRUFFLEHOG.value,
            ToolType.ZAP.value
        ]
    
    async def analyze(self, target_path: str, tools: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
        """Run security analysis."""
        results = {}
        
        # Default tools if none specified
        if not tools:
            tools = [ToolType.BANDIT.value, ToolType.SAFETY.value, ToolType.ESLINT.value]
        
        # Filter to security tools only
        security_tools = [t for t in tools if t in self.get_available_tools()]
        
        for tool_name in security_tools:
            try:
                tool = ToolType(tool_name)
                result = await self.run_tool(tool, target_path, options)
                results[tool_name] = result.dict()
            except Exception as e:
                self.logger.error(f"Failed to run {tool_name}: {str(e)}")
                results[tool_name] = {"error": str(e)}
        
        return results
    
    async def _execute_tool(self, tool: ToolType, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security tool."""
        if tool == ToolType.BANDIT:
            return await self._run_bandit(target_path, options)
        elif tool == ToolType.SAFETY:
            return await self._run_safety(target_path, options)
        elif tool == ToolType.SEMGREP:
            return await self._run_semgrep(target_path, options)
        elif tool == ToolType.ESLINT:
            return await self._run_eslint(target_path, options)
        elif tool == ToolType.RETIRE_JS:
            return await self._run_retire_js(target_path, options)
        elif tool == ToolType.SNYK:
            return await self._run_snyk(target_path, options)
        elif tool == ToolType.TRUFFLEHOG:
            return await self._run_trufflehog(target_path, options)
        elif tool == ToolType.ZAP:
            return await self._run_zap(target_path, options)
        else:
            raise ValueError(f"Unknown security tool: {tool}")
    
    async def _run_bandit(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Bandit security analysis."""
        cmd = [
            "bandit", "-r", target_path,
            "-f", "json",
            "-o", "/tmp/bandit_results.json"
        ]
        
        if options.get("skip_tests"):
            cmd.extend(["--skip", "B101"])
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        # Read results file
        try:
            with open("/tmp/bandit_results.json", "r") as f:
                results = json.load(f)
            return results
        except FileNotFoundError:
            return {"error": "Bandit results file not found", "stderr": stderr.decode()}
    
    async def _run_safety(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Safety dependency check."""
        # Look for requirements files
        req_files = list(Path(target_path).rglob("requirements*.txt"))
        req_files.extend(list(Path(target_path).rglob("Pipfile")))
        
        if not req_files:
            return {"error": "No dependency files found"}
        
        results = {}
        
        for req_file in req_files:
            cmd = ["safety", "check", "-r", str(req_file), "--json"]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            try:
                file_results = json.loads(stdout.decode())
                results[str(req_file)] = file_results
            except json.JSONDecodeError:
                results[str(req_file)] = {"error": "Failed to parse Safety output"}
        
        return results
    
    async def _run_semgrep(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Semgrep static analysis."""
        cmd = [
            "semgrep", "--config=auto",
            "--json",
            "--output=/tmp/semgrep_results.json",
            target_path
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        try:
            with open("/tmp/semgrep_results.json", "r") as f:
                results = json.load(f)
            return results
        except FileNotFoundError:
            return {"error": "Semgrep results file not found"}
    
    async def _run_eslint(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run ESLint for frontend security."""
        js_files = list(Path(target_path).rglob("*.js"))
        js_files.extend(list(Path(target_path).rglob("*.jsx")))
        js_files.extend(list(Path(target_path).rglob("*.ts")))
        js_files.extend(list(Path(target_path).rglob("*.tsx")))
        
        if not js_files:
            return {"error": "No JavaScript/TypeScript files found"}
        
        cmd = [
            "eslint",
            "--format", "json",
            "--ext", ".js,.jsx,.ts,.tsx",
            target_path
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        try:
            results = json.loads(stdout.decode())
            return {"results": results}
        except json.JSONDecodeError:
            return {"error": "Failed to parse ESLint output", "stderr": stderr.decode()}
    
    async def _run_retire_js(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Retire.js for JavaScript vulnerabilities."""
        cmd = ["retire", "--outputformat", "json", "--outputpath", "/tmp/retire_results.json", target_path]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        try:
            with open("/tmp/retire_results.json", "r") as f:
                results = json.load(f)
            return results
        except FileNotFoundError:
            return {"error": "Retire.js results file not found"}
    
    async def _run_snyk(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Snyk vulnerability scanning."""
        cmd = ["snyk", "test", "--json", target_path]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        try:
            results = json.loads(stdout.decode())
            return results
        except json.JSONDecodeError:
            return {"error": "Failed to parse Snyk output"}
    
    async def _run_trufflehog(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run TruffleHog for secret detection."""
        cmd = ["trufflehog", "filesystem", "--json", target_path]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        # TruffleHog outputs one JSON per line
        results = []
        for line in stdout.decode().strip().split('\n'):
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        return {"findings": results}
    
    async def _run_zap(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run OWASP ZAP security scan."""
        # This would require a running web application
        # For now, return placeholder
        return {"error": "ZAP scanning requires running web application"}


class PerformanceAnalyzer(BaseAnalyzer):
    """Performance analysis tools."""
    
    def __init__(self):
        super().__init__("performance")
    
    def get_available_tools(self) -> List[str]:
        return [ToolType.LOCUST.value, ToolType.LIGHTHOUSE.value]
    
    async def analyze(self, target_path: str, tools: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
        """Run performance analysis."""
        results = {}
        
        if not tools:
            tools = [ToolType.LOCUST.value]
        
        performance_tools = [t for t in tools if t in self.get_available_tools()]
        
        for tool_name in performance_tools:
            try:
                tool = ToolType(tool_name)
                result = await self.run_tool(tool, target_path, options)
                results[tool_name] = result.dict()
            except Exception as e:
                self.logger.error(f"Failed to run {tool_name}: {str(e)}")
                results[tool_name] = {"error": str(e)}
        
        return results
    
    async def _execute_tool(self, tool: ToolType, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Execute performance tool."""
        if tool == ToolType.LOCUST:
            return await self._run_locust(target_path, options)
        elif tool == ToolType.LIGHTHOUSE:
            return await self._run_lighthouse(target_path, options)
        else:
            raise ValueError(f"Unknown performance tool: {tool}")
    
    async def _run_locust(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Locust performance test."""
        # This requires a running application
        return {"error": "Locust testing requires running web application"}
    
    async def _run_lighthouse(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Lighthouse performance audit."""
        # This requires a running web application
        return {"error": "Lighthouse audit requires running web application"}


class CodeQualityAnalyzer(BaseAnalyzer):
    """Code quality analysis tools."""
    
    def __init__(self):
        super().__init__("code_quality")
    
    def get_available_tools(self) -> List[str]:
        return [
            ToolType.FLAKE8.value,
            ToolType.PYLINT.value,
            ToolType.MYPY.value,
            ToolType.SONARQUBE.value
        ]
    
    async def analyze(self, target_path: str, tools: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
        """Run code quality analysis."""
        results = {}
        
        if not tools:
            tools = [ToolType.FLAKE8.value, ToolType.PYLINT.value]
        
        quality_tools = [t for t in tools if t in self.get_available_tools()]
        
        for tool_name in quality_tools:
            try:
                tool = ToolType(tool_name)
                result = await self.run_tool(tool, target_path, options)
                results[tool_name] = result.dict()
            except Exception as e:
                self.logger.error(f"Failed to run {tool_name}: {str(e)}")
                results[tool_name] = {"error": str(e)}
        
        return results
    
    async def _execute_tool(self, tool: ToolType, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code quality tool."""
        if tool == ToolType.FLAKE8:
            return await self._run_flake8(target_path, options)
        elif tool == ToolType.PYLINT:
            return await self._run_pylint(target_path, options)
        elif tool == ToolType.MYPY:
            return await self._run_mypy(target_path, options)
        elif tool == ToolType.SONARQUBE:
            return await self._run_sonarqube(target_path, options)
        else:
            raise ValueError(f"Unknown code quality tool: {tool}")
    
    async def _run_flake8(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Flake8 code quality check."""
        cmd = ["flake8", "--format=json", target_path]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        # Flake8 doesn't output JSON by default, parse line format
        issues = []
        for line in stdout.decode().strip().split('\n'):
            if line and ':' in line:
                parts = line.split(':', 3)
                if len(parts) >= 4:
                    issues.append({
                        "file": parts[0],
                        "line": parts[1],
                        "column": parts[2],
                        "message": parts[3].strip()
                    })
        
        return {"issues": issues}
    
    async def _run_pylint(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Pylint code quality check."""
        cmd = ["pylint", "--output-format=json", target_path]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        try:
            results = json.loads(stdout.decode())
            return {"issues": results}
        except json.JSONDecodeError:
            return {"error": "Failed to parse Pylint output"}
    
    async def _run_mypy(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run MyPy type checking."""
        cmd = ["mypy", "--no-error-summary", target_path]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        # Parse MyPy output
        issues = []
        for line in stdout.decode().strip().split('\n'):
            if line and ':' in line:
                issues.append({"message": line})
        
        return {"issues": issues}
    
    async def _run_sonarqube(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run SonarQube analysis."""
        return {"error": "SonarQube analysis requires server setup"}


class ContainerAnalyzer(BaseAnalyzer):
    """Container security analysis tools."""
    
    def __init__(self):
        super().__init__("container")
    
    def get_available_tools(self) -> List[str]:
        return [ToolType.DOCKER_SCAN.value, ToolType.TRIVY.value]
    
    async def analyze(self, target_path: str, tools: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
        """Run container analysis."""
        results = {}
        
        if not tools:
            tools = [ToolType.DOCKER_SCAN.value]
        
        container_tools = [t for t in tools if t in self.get_available_tools()]
        
        for tool_name in container_tools:
            try:
                tool = ToolType(tool_name)
                result = await self.run_tool(tool, target_path, options)
                results[tool_name] = result.dict()
            except Exception as e:
                self.logger.error(f"Failed to run {tool_name}: {str(e)}")
                results[tool_name] = {"error": str(e)}
        
        return results
    
    async def _execute_tool(self, tool: ToolType, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Execute container tool."""
        if tool == ToolType.DOCKER_SCAN:
            return await self._run_docker_scan(target_path, options)
        elif tool == ToolType.TRIVY:
            return await self._run_trivy(target_path, options)
        else:
            raise ValueError(f"Unknown container tool: {tool}")
    
    async def _run_docker_scan(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Docker security scan."""
        # Look for Dockerfile
        dockerfiles = list(Path(target_path).rglob("Dockerfile*"))
        
        if not dockerfiles:
            return {"error": "No Dockerfile found"}
        
        results = {}
        for dockerfile in dockerfiles:
            # This would require Docker Desktop with scan enabled
            results[str(dockerfile)] = {"error": "Docker scan requires Docker Desktop"}
        
        return results
    
    async def _run_trivy(self, target_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Trivy vulnerability scanner."""
        return {"error": "Trivy not installed in container"}
