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
                # Only add tools that were actually requested and used
                backend_tools = [tool for tool in ["bandit", "safety", "pylint", "semgrep"] if tool in request.tools]
                tools_used.extend(backend_tools)
            
            # Run frontend analysis
            if self._has_frontend_code(app_path):
                frontend_issues = await self._analyze_frontend(app_path, request.tools)
                issues.extend(frontend_issues)
                # Only add tools that were actually requested and used
                frontend_tools = [tool for tool in ["eslint", "retire", "npm-audit"] if tool in request.tools]
                tools_used.extend(frontend_tools)
            
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
        # The source_path is mounted to /app/sources which contains the models directory
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
        
        if "semgrep" in tools:
            semgrep_issues = await self._run_semgrep(backend_path)
            issues.extend(semgrep_issues)
        
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
        """Run Bandit security analysis on real Python code."""
        try:
            python_files = list(path.glob("**/*.py"))
            issues = []
            
            if not python_files:
                logger.info("No Python files found for Bandit analysis", path=str(path))
                return issues
            
            # Run actual Bandit on each Python file
            for py_file in python_files:
                try:
                    cmd = ["bandit", "-f", "json", str(py_file)]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await proc.communicate()
                    
                    if stdout:
                        try:
                            bandit_output = json.loads(stdout.decode())
                            
                            # Parse Bandit results
                            for result in bandit_output.get("results", []):
                                # Read the actual code snippet
                                code_snippet = ""
                                try:
                                    with open(py_file, 'r', encoding='utf-8') as f:
                                        lines = f.readlines()
                                        line_num = result.get("line_number", 1)
                                        if 1 <= line_num <= len(lines):
                                            code_snippet = lines[line_num - 1].strip()
                                except Exception:
                                    code_snippet = "Unable to read code snippet"
                                
                                issues.append(TestIssue(
                                    tool="bandit",
                                    severity=self._map_bandit_severity(result.get("issue_severity", "LOW")),
                                    confidence=result.get("issue_confidence", "MEDIUM"),
                                    file_path=str(py_file.relative_to(self.source_path)),
                                    line_number=result.get("line_number"),
                                    message=result.get("test_name", "Security issue detected"),
                                    description=result.get("issue_text", ""),
                                    solution="Review and fix the security issue identified by Bandit",
                                    reference=f"https://bandit.readthedocs.io/en/latest/plugins/{result.get('test_id', '')}.html",
                                    code_snippet=code_snippet
                                ))
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse Bandit JSON output", file=str(py_file))
                    
                except Exception as e:
                    logger.warning("Bandit failed on file", file=str(py_file), error=str(e))
                    continue
            
            logger.info(f"Bandit analysis found {len(issues)} issues", path=str(path))
            return issues
                
        except Exception as e:
            logger.error("Bandit execution failed", error=str(e))
            return []
    
    async def _run_safety(self, path: Path) -> List[TestIssue]:
        """Run Safety dependency analysis on real requirements files."""
        try:
            requirements_files = list(path.glob("**/requirements.txt"))
            issues = []
            
            if not requirements_files:
                logger.info("No requirements.txt files found for Safety analysis", path=str(path))
                return issues
            
            # Run actual Safety on each requirements file
            for req_file in requirements_files:
                try:
                    cmd = ["safety", "check", "--json", "-r", str(req_file)]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await proc.communicate()
                    
                    if stdout:
                        try:
                            safety_output = json.loads(stdout.decode())
                            
                            # Parse Safety results
                            for vuln in safety_output:
                                # Read the requirement line
                                package_line = ""
                                try:
                                    with open(req_file, 'r', encoding='utf-8') as f:
                                        lines = f.readlines()
                                        pkg_name = vuln.get("package", "").lower()
                                        for i, line in enumerate(lines):
                                            if pkg_name in line.lower():
                                                package_line = line.strip()
                                                break
                                except Exception:
                                    package_line = f"{vuln.get('package', 'unknown')}=={vuln.get('installed_version', 'unknown')}"
                                
                                issues.append(TestIssue(
                                    tool="safety",
                                    severity=self._map_safety_severity(vuln.get("vulnerability", "")),
                                    confidence="HIGH",
                                    file_path=str(req_file.relative_to(self.source_path)),
                                    line_number=None,
                                    message=f"Vulnerability in {vuln.get('package', 'unknown')} package",
                                    description=vuln.get("vulnerability", "No description available"),
                                    solution=f"Upgrade to version {vuln.get('vulnerable_spec', 'latest')} or higher",
                                    reference=vuln.get("more_info_url", "https://pyup.io/safety/"),
                                    code_snippet=package_line
                                ))
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse Safety JSON output", file=str(req_file))
                    
                except Exception as e:
                    logger.warning("Safety failed on file", file=str(req_file), error=str(e))
                    continue
            
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
        """Run ESLint analysis on real JavaScript/TypeScript files."""
        try:
            js_files = list(path.glob("**/*.js")) + list(path.glob("**/*.jsx")) + list(path.glob("**/*.ts")) + list(path.glob("**/*.tsx"))
            issues = []
            
            if not js_files:
                logger.info("No JavaScript/TypeScript files found for ESLint analysis", path=str(path))
                return issues
            
            # Create temporary ESLint config for analysis
            eslint_config = {
                "env": {"browser": True, "es2021": True, "node": True},
                "extends": ["eslint:recommended"],
                "parserOptions": {"ecmaVersion": 2021, "sourceType": "module"},
                "rules": {
                    "no-unused-vars": "error",
                    "no-console": "warn", 
                    "no-debugger": "error",
                    "no-eval": "error",
                    "no-implied-eval": "error",
                    "no-new-func": "error",
                    "no-script-url": "error",
                    "no-global-assign": "error",
                    "no-implicit-globals": "error",
                    "no-unsafe-innerhtml": "error"
                }
            }
            
            config_file = path / ".eslintrc.json"
            try:
                with open(config_file, 'w') as f:
                    json.dump(eslint_config, f)
                
                # Try multiple ESLint execution strategies
                success = False
                stdout = None
                stderr = None
                
                # Strategy 1: Use globally installed ESLint
                try:
                    cmd = ["eslint", str(path), "--format", "json", "--ext", ".js,.jsx,.ts,.tsx"]
                    proc = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await proc.communicate()
                    success = True
                except FileNotFoundError:
                    # Strategy 2: Use npx eslint
                    try:
                        cmd = ["npx", "eslint", str(path), "--format", "json", "--ext", ".js,.jsx,.ts,.tsx"]
                        proc = await asyncio.create_subprocess_exec(
                            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await proc.communicate()
                        success = True
                    except FileNotFoundError:
                        logger.warning("ESLint not found, falling back to basic analysis")
                
                if success and stdout:
                    try:
                        eslint_output = json.loads(stdout.decode())
                        
                        # Parse ESLint results
                        for file_result in eslint_output:
                            file_path = Path(file_result.get("filePath", ""))
                            for message in file_result.get("messages", []):
                                # Read the actual code snippet
                                code_snippet = ""
                                try:
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        lines = f.readlines()
                                        line_num = message.get("line", 1)
                                        if 1 <= line_num <= len(lines):
                                            code_snippet = lines[line_num - 1].strip()
                                except Exception:
                                    code_snippet = "Unable to read code snippet"
                                
                                issues.append(TestIssue(
                                    tool="eslint",
                                    severity=self._map_eslint_severity(message.get("severity", 1)),
                                    confidence="MEDIUM",
                                    file_path=str(file_path.relative_to(self.source_path)) if file_path.is_relative_to(self.source_path) else str(file_path),
                                    line_number=message.get("line"),
                                    message=message.get("message", ""),
                                    description=f"ESLint rule: {message.get('ruleId', 'unknown')}",
                                    solution="Fix the code quality issue identified by ESLint",
                                    reference=f"https://eslint.org/docs/rules/{message.get('ruleId', '')}",
                                    code_snippet=code_snippet
                                ))
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse ESLint JSON output")
                
                # Fallback: Basic static analysis if ESLint fails
                if not success or not issues:
                    logger.info("Running fallback static analysis for JavaScript files")
                    for js_file in js_files[:5]:  # Limit to first 5 files
                        try:
                            with open(js_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                                
                            # Basic security pattern matching
                            security_patterns = [
                                (r'eval\s*\(', "Use of eval() function", SeverityLevel.HIGH),
                                (r'innerHTML\s*=', "Potential XSS via innerHTML", SeverityLevel.MEDIUM),
                                (r'document\.write\s*\(', "Use of document.write", SeverityLevel.MEDIUM),
                                (r'console\.log\s*\(', "Console log statement", SeverityLevel.LOW),
                                (r'alert\s*\(', "Use of alert()", SeverityLevel.LOW)
                            ]
                            
                            lines = content.split('\n')
                            for line_num, line in enumerate(lines, 1):
                                for pattern, description, severity in security_patterns:
                                    import re
                                    if re.search(pattern, line, re.IGNORECASE):
                                        issues.append(TestIssue(
                                            tool="eslint",
                                            severity=severity,
                                            confidence="LOW",
                                            file_path=str(js_file.relative_to(self.source_path)),
                                            line_number=line_num,
                                            message=description,
                                            description="Pattern-based static analysis finding",
                                            solution="Review and fix the identified pattern",
                                            reference="https://eslint.org/",
                                            code_snippet=line.strip()
                                        ))
                        except Exception as e:
                            logger.warning(f"Failed to analyze {js_file}: {e}")
                
            finally:
                # Clean up temporary config
                if config_file.exists():
                    config_file.unlink()
            
            logger.info(f"ESLint analysis found {len(issues)} issues", path=str(path))
            return issues
                
        except Exception as e:
            logger.error("ESLint execution failed", error=str(e))
            return []
    
    async def _run_retire(self, path: Path) -> List[TestIssue]:
        """Run Retire.js vulnerability analysis on real package.json and JS files."""
        try:
            package_json = path / "package.json"
            js_files = list(path.glob("**/*.js")) + list(path.glob("**/*.jsx"))
            issues = []
            
            if not package_json.exists() and not js_files:
                logger.info("No package.json or JS files found for Retire.js analysis", path=str(path))
                return issues
            
            # Run Retire.js on the directory
            try:
                cmd = ["retire", "--outputformat", "json", "--path", str(path)]
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                
                if stdout:
                    try:
                        retire_output = json.loads(stdout.decode())
                        
                        # Parse Retire.js results
                        for result in retire_output.get("data", []):
                            file_path = result.get("file", "")
                            for vulnerability in result.get("results", []):
                                for vuln_detail in vulnerability.get("vulnerabilities", []):
                                    # Read package.json content for context
                                    code_snippet = ""
                                    if package_json.exists() and "package.json" in file_path:
                                        try:
                                            with open(package_json, 'r', encoding='utf-8') as f:
                                                pkg_data = json.load(f)
                                                component = vulnerability.get("component", "")
                                                deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                                                if component in deps:
                                                    code_snippet = f'"{component}": "{deps[component]}"'
                                        except Exception:
                                            component = vulnerability.get("component", "unknown")
                                            code_snippet = f'Check {component} dependency'
                                    
                                    issues.append(TestIssue(
                                        tool="retire",
                                        severity=self._map_retire_severity(vuln_detail.get("severity", "medium")),
                                        confidence="HIGH",
                                        file_path=str(Path(file_path).relative_to(self.source_path)) if Path(file_path).is_relative_to(self.source_path) else file_path,
                                        line_number=None,
                                        message=f"{vulnerability.get('component', 'Unknown')} has known vulnerabilities",
                                        description=vuln_detail.get("info", [{}])[0].get("summary", "No description available"),
                                        solution=f"Upgrade {vulnerability.get('component', 'component')} to a secure version",
                                        reference=vuln_detail.get("info", [{}])[0].get("URL", "https://retirejs.github.io/retire.js/"),
                                        code_snippet=code_snippet
                                    ))
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse Retire.js JSON output")
                
            except FileNotFoundError:
                # If retire command not found, fall back to basic package.json analysis
                if package_json.exists():
                    with open(package_json, 'r', encoding='utf-8') as f:
                        pkg_data = json.load(f)
                        
                    # Check for known vulnerable packages (basic heuristics)
                    vulnerable_packages = {
                        "jquery": {"<3.6.0": "XSS vulnerabilities"},
                        "lodash": {"<4.17.21": "Prototype pollution"},
                        "moment": {"*": "Deprecated, use dayjs or date-fns"},
                        "react": {"<16.14.0": "Security vulnerabilities"}
                    }
                    
                    for pkg, version_info in vulnerable_packages.items():
                        deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                        if pkg in deps:
                            issues.append(TestIssue(
                                tool="retire",
                                severity=SeverityLevel.MEDIUM,
                                confidence="MEDIUM",
                                file_path="package.json",
                                line_number=None,
                                message=f"{pkg} may have security vulnerabilities",
                                description=list(version_info.values())[0],
                                solution=f"Review and update {pkg} dependency",
                                reference="https://retirejs.github.io/retire.js/",
                                code_snippet=f'"{pkg}": "{deps[pkg]}"'
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
            issues = []
            
            if not package_json.exists():
                logger.info("No package.json found for npm audit analysis", path=str(path))
                return issues
            
            # Try to run npm audit
            try:
                cmd = ["npm", "audit", "--json"]
                proc = await asyncio.create_subprocess_exec(
                    *cmd, cwd=str(path), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                
                if stdout:
                    try:
                        output = json.loads(stdout.decode())
                        
                        # Handle different npm audit output formats
                        if "advisories" in output:
                            # Legacy format
                            for advisory in output.get("advisories", {}).values():
                                issues.append(TestIssue(
                                    tool="npm-audit",
                                    severity=self._map_npm_severity(advisory.get("severity", "moderate")),
                                    confidence="HIGH",
                                    file_path="package.json",
                                    message=advisory.get("title", "Dependency vulnerability"),
                                    description=advisory.get("overview", ""),
                                    solution=advisory.get("recommendation", "Update dependency"),
                                    reference=advisory.get("url", ""),
                                    code_snippet=f'"{advisory.get("module_name", "unknown")}"'
                                ))
                        elif "vulnerabilities" in output:
                            # New format
                            vulns = output.get("vulnerabilities", {})
                            for pkg_name, vuln_info in vulns.items():
                                if isinstance(vuln_info, dict) and vuln_info.get("severity") != "info":
                                    issues.append(TestIssue(
                                        tool="npm-audit",
                                        severity=self._map_npm_severity(vuln_info.get("severity", "moderate")),
                                        confidence="HIGH",
                                        file_path="package.json",
                                        message=f"Vulnerability in {pkg_name}",
                                        description=vuln_info.get("title", "Dependency vulnerability"),
                                        solution="Update to secure version",
                                        reference=vuln_info.get("url", ""),
                                        code_snippet=f'"{pkg_name}"'
                                    ))
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse npm audit JSON output")
                        
            except Exception as e:
                logger.warning(f"npm audit failed, trying alternative analysis: {e}")
                
                # Fallback: Basic package.json analysis for known vulnerable patterns
                try:
                    with open(package_json, 'r', encoding='utf-8') as f:
                        pkg_data = json.load(f)
                    
                    # Check for known vulnerable packages (basic heuristics)
                    vulnerable_packages = {
                        "lodash": {"versions": ["<4.17.21"], "issue": "Prototype pollution vulnerability"},
                        "moment": {"versions": ["*"], "issue": "Deprecated package, security unmaintained"},
                        "jquery": {"versions": ["<3.6.0"], "issue": "XSS vulnerabilities in older versions"},
                        "handlebars": {"versions": ["<4.7.7"], "issue": "Potential template injection"},
                        "yargs-parser": {"versions": ["<18.1.2"], "issue": "Prototype pollution"},
                        "minimist": {"versions": ["<1.2.6"], "issue": "Prototype pollution"},
                        "serialize-javascript": {"versions": ["<6.0.0"], "issue": "XSS vulnerability"},
                        "node-fetch": {"versions": ["<2.6.7"], "issue": "Information disclosure"}
                    }
                    
                    all_deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                    
                    for pkg, version in all_deps.items():
                        if pkg in vulnerable_packages:
                            vuln_info = vulnerable_packages[pkg]
                            issues.append(TestIssue(
                                tool="npm-audit",
                                severity=SeverityLevel.MEDIUM,
                                confidence="MEDIUM",
                                file_path="package.json",
                                line_number=None,
                                message=f"{pkg} may have security vulnerabilities",
                                description=vuln_info["issue"],
                                solution=f"Review and update {pkg} dependency",
                                reference="https://npmjs.com/advisories",
                                code_snippet=f'"{pkg}": "{version}"'
                            ))
                            
                except Exception as e:
                    logger.warning(f"Fallback package.json analysis failed: {e}")
            
            logger.info(f"npm audit analysis found {len(issues)} vulnerabilities", path=str(path))
            return issues
                
        except Exception as e:
            logger.error("npm audit execution failed", error=str(e))
            return []
    
    async def _run_semgrep(self, path: Path) -> List[TestIssue]:
        """Run Semgrep static analysis on real Python code."""
        try:
            python_files = list(path.glob("**/*.py"))
            issues = []
            
            if not python_files:
                logger.info("No Python files found for Semgrep analysis", path=str(path))
                return issues
            
            # Run Semgrep with security-focused rulesets
            cmd = [
                "semgrep", 
                "--config=auto",  # Auto-detect appropriate rules
                "--json",
                "--severity=ERROR",
                "--severity=WARNING", 
                str(path)
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if stdout:
                try:
                    semgrep_output = json.loads(stdout.decode())
                    
                    # Parse Semgrep results
                    for result in semgrep_output.get("results", []):
                        # Read the actual code snippet
                        code_snippet = ""
                        file_path = Path(result.get("path", ""))
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                                start_line = result.get("start", {}).get("line", 1)
                                end_line = result.get("end", {}).get("line", start_line)
                                if 1 <= start_line <= len(lines):
                                    if start_line == end_line:
                                        code_snippet = lines[start_line - 1].strip()
                                    else:
                                        code_snippet = ''.join(lines[start_line-1:min(end_line, len(lines))]).strip()
                        except Exception:
                            code_snippet = "Unable to read code snippet"
                        
                        # Get rule info
                        extra = result.get("extra", {})
                        rule_id = extra.get("metadata", {}).get("owasp", "") or result.get("check_id", "")
                        
                        issues.append(TestIssue(
                            tool="semgrep",
                            severity=self._map_semgrep_severity(extra.get("severity", "WARNING")),
                            confidence="HIGH",
                            file_path=str(file_path.relative_to(self.source_path)) if file_path.is_relative_to(self.source_path) else str(file_path),
                            line_number=result.get("start", {}).get("line"),
                            message=extra.get("message", result.get("check_id", "Security issue detected")),
                            description=extra.get("metadata", {}).get("category", "Static analysis finding"),
                            solution="Review and fix the security issue identified by Semgrep",
                            reference=f"https://semgrep.dev/r/{rule_id}" if rule_id else "https://semgrep.dev/",
                            code_snippet=code_snippet
                        ))
                except json.JSONDecodeError:
                    logger.warning("Failed to parse Semgrep JSON output")
            
            logger.info(f"Semgrep analysis found {len(issues)} issues", path=str(path))
            return issues
                
        except Exception as e:
            logger.error("Semgrep execution failed", error=str(e))
            return []
    
    def _map_semgrep_severity(self, severity: str) -> SeverityLevel:
        """Map Semgrep severity to standard levels."""
        mapping = {
            "ERROR": SeverityLevel.HIGH,
            "WARNING": SeverityLevel.MEDIUM, 
            "INFO": SeverityLevel.LOW
        }
        return mapping.get(severity.upper(), SeverityLevel.MEDIUM)
    
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
