"""
CLI Tools Analysis Module
========================

Unified interface for all CLI-based code analysis tools including:
- Security analysis (backend and frontend)
- Code quality analysis
- Dependency vulnerability scanning

This module consolidates functionality from:
- backend_security_analysis.py
- frontend_security_analysis.py  
- code_quality_analysis.py
"""

import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from contextlib import contextmanager, suppress
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple, Any, Union, Callable

# Import logging service from core_services module
try:
    from core_services import get_logger as core_get_logger
except ImportError:
    import logging
    def core_get_logger(component: str):
        return logging.getLogger(component)

def get_logger(name: str):
    """Get logger - standardized interface."""
    return core_get_logger(name)

def create_logger_for_component(name: str):
    """Create logger for component - standardized interface."""
    return get_logger(name)

# Import JsonResultsManager with proper compatibility
try:
    from core_services import JsonResultsManager as _CoreJsonResultsManager
    JsonResultsManager = _CoreJsonResultsManager  # type: ignore
except ImportError:
    # Fallback JsonResultsManager implementation for compatibility
    class JsonResultsManager:  # type: ignore
        """Fallback JsonResultsManager implementation."""
        def __init__(self, module_name: str, base_path: Optional[Path] = None):
            self.module_name = module_name
            self.base_path = base_path or Path(__file__).parent.parent / "reports"
            
        def save_results(self, model: str, app_num: int, results: Any, 
                        file_name: Optional[str] = None) -> Path:
            """Save analysis results to JSON file."""
            if file_name is None:
                file_name = f".{self.module_name}_results.json"
            
            results_dir = self.base_path / model / f"app{app_num}"
            results_dir.mkdir(parents=True, exist_ok=True)
            results_path = results_dir / file_name
            
            with open(results_path, "w", encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            
            return results_path
            
        def load_results(self, model: str, app_num: int, 
                        file_name: Optional[str] = None) -> Optional[Any]:
            """Load analysis results from JSON file."""
            if file_name is None:
                file_name = f".{self.module_name}_results.json"
            
            results_path = self.base_path / model / f"app{app_num}" / file_name
            if not results_path.exists():
                return None
                
            try:
                with open(results_path, "r", encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None

# Import database models
try:
    from flask import current_app
    from .models import SecurityAnalysis, GeneratedApplication, AnalysisStatus, SeverityLevel
    from .extensions import db
    DATABASE_INTEGRATION = True
except ImportError:
    try:
        from models import SecurityAnalysis, GeneratedApplication, AnalysisStatus, SeverityLevel
        from extensions import db
        DATABASE_INTEGRATION = True
    except ImportError:
        DATABASE_INTEGRATION = False

# Initialize logger
logger = create_logger_for_component('cli_tools_analysis')

# Constants
TOOL_TIMEOUT = 60
IS_WINDOWS = platform.system() == "Windows"
SEVERITY_ORDER = {"ERROR": 0, "HIGH": 0, "WARNING": 1, "MEDIUM": 1, "INFO": 2, "LOW": 2}
CONFIDENCE_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

# Tool categories
class ToolCategory(str, Enum):
    BACKEND_SECURITY = "backend_security"
    FRONTEND_SECURITY = "frontend_security"
    BACKEND_QUALITY = "backend_quality"
    FRONTEND_QUALITY = "frontend_quality"


class ToolStatus(str, Enum):
    SUCCESS = "✅ No issues found"
    ISSUES_FOUND = "ℹ️ Found {count} issues"
    ERROR = "❌ Error"
    AUTH_REQUIRED = "❌ Authentication required"
    NOT_FOUND = "❌ Command not found"
    NO_FILES = "⚪ No files found"
    SKIPPED = "⚪ Skipped"


@dataclass
class AnalysisIssue:
    """Unified issue structure for all analysis types."""
    filename: str
    line_number: int
    issue_text: str
    severity: str  # ERROR/HIGH, WARNING/MEDIUM, INFO/LOW
    confidence: str
    issue_type: str
    category: str  # security, style, complexity, formatting, documentation, duplication, type, dependency
    rule_id: str
    line_range: List[int]
    code: str
    tool: str
    fix_suggestion: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisIssue':
        return cls(**data)


def validate_path_security(base_path: Path, target_path: Path) -> bool:
    """Validate that target_path is within base_path."""
    try:
        target_path.resolve().relative_to(base_path.resolve())
        return True
    except (OSError, ValueError):
        return False


def get_executable_path(name: str) -> Optional[str]:
    """Find executable path for a command."""
    cmd = f"{name}.cmd" if IS_WINDOWS else name
    path = shutil.which(cmd)
    if not path and IS_WINDOWS:
        path = shutil.which(name)
    return path


def safe_json_loads(data: str) -> Optional[Union[dict, list]]:
    """Safely parse JSON data."""
    if not data:
        return None
    
    data = data[1:] if data.startswith('\ufeff') else data  # Remove BOM
    try:
        return json.loads(data)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.error(f"JSON parsing failed: {e}")
        return None


class BaseAnalyzer(ABC):
    """Base class for all analyzers."""
    
    def __init__(self, base_path: Union[str, Path], category: ToolCategory):
        self.base_path = Path(base_path).resolve()
        self.category = category
        self.results_manager = JsonResultsManager(module_name=category.value, base_path=self.base_path)
        self.analysis_lock = Lock()
        self.available_tools = {}
        
    @abstractmethod
    def get_tool_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Return tool definitions for this analyzer."""
        pass
        
    @abstractmethod
    def run_analysis(self, model: str, app_num: int, use_all_tools: bool = False, 
                    force_rerun: bool = False) -> Tuple[List[Dict], Dict[str, str], Dict[str, str]]:
        """Run analysis on specified model and app."""
        pass
        
    def _check_tool_availability(self, tool_name: str, tool_config: Dict[str, Any]) -> bool:
        """Check if a tool is available."""
        try:
            if tool_config.get("python_module"):
                # Special case for safety - check if package is installed
                if tool_name == "safety":
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "show", "safety"],
                        capture_output=True, timeout=5, check=False
                    )
                    return result.returncode == 0
                else:
                    # For other tools, try to import them directly
                    result = subprocess.run(
                        [sys.executable, "-c", f"import {tool_name}"],
                        capture_output=True, timeout=5, check=False
                    )
                    return result.returncode == 0
            elif tool_config.get("npx_tool"):
                # Check npx availability and the specific tool
                try:
                    # First check if npx is available (need shell=True on Windows)
                    npx_result = subprocess.run(
                        ["npx", "--version"],
                        capture_output=True, timeout=5, check=False, shell=True
                    )
                    if npx_result.returncode != 0:
                        return False
                    
                    # Then check if the specific tool can be found by npx
                    cmd = tool_config.get("cmd", [])
                    tool_cmd = cmd[1] if len(cmd) > 1 else tool_name
                    tool_result = subprocess.run(
                        ["npx", tool_cmd, "--version"],
                        capture_output=True, timeout=10, check=False, shell=True
                    )
                    return tool_result.returncode == 0
                except Exception:
                    return False
            else:
                # Check system command
                cmd = tool_config.get("cmd", [])
                if not cmd:
                    return False
                return bool(get_executable_path(cmd[0]))
        except Exception as e:
            logger.debug(f"Tool {tool_name} availability check failed: {e}")
            return False
            
    def _run_tool(self, tool_name: str, command: List[str], parser_func: Optional[Callable],
                  working_dir: Path, timeout: int = TOOL_TIMEOUT,
                  input_data: Optional[str] = None) -> Tuple[List[AnalysisIssue], str, str]:
        """Run a tool and parse its output."""
        try:
            logger.info(f"🔧 Starting {tool_name} analysis")
            logger.info(f"📁 Working directory: {working_dir}")
            logger.info(f"⚙️  Command: {' '.join(command)}")
            if input_data:
                logger.info(f"📥 Input data length: {len(input_data)} characters")
            
            # Use shell=True for NPX commands on Windows
            use_shell = IS_WINDOWS and len(command) > 0 and (command[0] == "npx" or command[0] == "npm")
            if use_shell:
                logger.info(f"🪟 Using shell mode for Windows NPX command")
            
            start_time = datetime.now()
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                input=input_data,
                encoding='utf-8',
                errors='replace',
                shell=use_shell
            )
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"⏱️  {tool_name} completed in {execution_time:.2f} seconds")
            logger.info(f"🏁 Return code: {result.returncode}")
            
            if result.stdout:
                logger.info(f"📤 STDOUT length: {len(result.stdout)} characters")
                if len(result.stdout) > 1000:
                    logger.info(f"📤 STDOUT preview: {result.stdout[:500]}...")
                else:
                    logger.info(f"📤 STDOUT: {result.stdout}")
            else:
                logger.info(f"📤 No STDOUT output")
                
            if result.stderr:
                logger.info(f"⚠️  STDERR length: {len(result.stderr)} characters")
                if len(result.stderr) > 1000:
                    logger.info(f"⚠️  STDERR preview: {result.stderr[:500]}...")
                else:
                    logger.info(f"⚠️  STDERR: {result.stderr}")
            else:
                logger.info(f"⚠️  No STDERR output")
            
            output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            
            if result.returncode in [0, 1]:  # 0 = no issues, 1 = issues found
                if parser_func:
                    logger.info(f"🔍 Parsing {tool_name} output...")
                    try:
                        issues = parser_func(result.stdout)
                        logger.info(f"✅ Parsed {len(issues)} issues from {tool_name}")
                        for i, issue in enumerate(issues[:5]):  # Log first 5 issues
                            logger.info(f"  Issue {i+1}: {issue.filename}:{issue.line_number} - {issue.severity} - {issue.issue_text[:100]}")
                        if len(issues) > 5:
                            logger.info(f"  ... and {len(issues) - 5} more issues")
                    except Exception as parse_error:
                        logger.error(f"❌ Failed to parse {tool_name} output: {parse_error}")
                        issues = []
                else:
                    issues = []
                    logger.info(f"ℹ️  No parser function provided for {tool_name}")
                
                status = ToolStatus.ISSUES_FOUND.value.format(count=len(issues)) if issues else ToolStatus.SUCCESS.value
                logger.info(f"✅ {tool_name} analysis completed: {status}")
                return issues, status, output
            else:
                logger.error(f"❌ {tool_name} failed with return code {result.returncode}")
                logger.error(f"❌ Error details: {result.stderr}")
                return [], ToolStatus.ERROR.value, output
                
        except subprocess.TimeoutExpired:
            logger.error(f"⏰ {tool_name} timed out after {timeout} seconds")
            return [], ToolStatus.ERROR.value, f"Tool timed out after {timeout} seconds"
        except FileNotFoundError:
            logger.error(f"🚫 {tool_name} command not found")
            return [], ToolStatus.NOT_FOUND.value, "Command not found"
        except Exception as e:
            logger.error(f"💥 Error running {tool_name}: {e}")
            return [], ToolStatus.ERROR.value, str(e)
            
    def _sort_issues(self, issues: List[AnalysisIssue]) -> List[AnalysisIssue]:
        """Sort issues by severity, confidence, filename, line number."""
        return sorted(issues, key=lambda i: (
            SEVERITY_ORDER.get(i.severity, 99),
            CONFIDENCE_ORDER.get(i.confidence, 99),
            i.filename,
            i.line_number
        ))
        
    @contextmanager
    def _temp_config(self, config_content: Union[dict, list], suffix: str, is_js: bool = False):
        """Create temporary configuration file."""
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
                if is_js:
                    if suffix == "eslint.config.js":
                        # ESLint 9.x flat config format
                        f.write('export default ')
                        json.dump(config_content, f, indent=2)
                        f.write(';\n')
                    else:
                        # Traditional JS module format
                        f.write('module.exports = ')
                        json.dump(config_content, f, indent=2)
                        f.write(';\n')
                else:
                    json.dump(config_content, f, indent=2)
                temp_file = Path(f.name)
            yield temp_file
        finally:
            if temp_file and temp_file.exists():
                with suppress(OSError):
                    temp_file.unlink()


class BackendSecurityAnalyzer(BaseAnalyzer):
    """Analyzes backend code for security issues."""
    
    def __init__(self, base_path: Union[str, Path]):
        super().__init__(base_path, ToolCategory.BACKEND_SECURITY)
        self.tools = self.get_tool_definitions()
        
        logger.info(f"🔍 Initializing Backend Security Analyzer")
        logger.info(f"📁 Base path: {base_path}")
        logger.info(f"🔧 Checking availability of {len(self.tools)} backend security tools...")
        
        self.available_tools = {}
        for name, config in self.tools.items():
            logger.info(f"  🔍 Checking {name}...")
            is_available = self._check_tool_availability(name, config)
            self.available_tools[name] = is_available
            status_icon = "✅" if is_available else "❌"
            logger.info(f"    {status_icon} {name}: {'Available' if is_available else 'Not available'}")
            
        available_tools_list = [k for k, v in self.available_tools.items() if v]
        logger.info(f"✅ Backend security tools ready: {len(available_tools_list)}/{len(self.tools)} available")
        logger.info(f"📋 Available tools: {available_tools_list}")
        
    def get_tool_definitions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "bandit": {
                "cmd": [sys.executable, "-m", "bandit"],
                "python_module": True,
                "requires_files": True,
                "timeout": 30
            },
            "safety": {
                "cmd": [sys.executable, "-m", "safety"],
                "python_module": True,
                "requires_files": False,
                "timeout": 30
            },
            "pylint": {
                "cmd": [sys.executable, "-m", "pylint"],
                "python_module": True,
                "requires_files": True,
                "timeout": 45,
                "max_files": 30
            },
            "vulture": {
                "cmd": [sys.executable, "-m", "vulture"],
                "python_module": True,
                "requires_files": True,
                "timeout": 30
            }
        }
        
    def _find_app_path(self, model: str, app_num: int) -> Optional[Path]:
        """Find application backend directory path."""
        workspace_root = self.base_path.parent if self.base_path.name == "src" else self.base_path
        candidates = [
            workspace_root / "misc" / "models" / model / f"app{app_num}" / "backend",
            self.base_path / "misc" / "models" / model / f"app{app_num}" / "backend",
        ]
        
        for candidate in candidates:
            if candidate.is_dir() and validate_path_security(workspace_root, candidate):
                return candidate
        
        return None
        
    def _check_source_files(self, directory: Path) -> Tuple[bool, List[Path]]:
        """Check for Python source files."""
        python_files = []
        for ext in ['.py']:
            python_files.extend(directory.rglob(f"*{ext}"))
        
        # Filter out common directories to ignore
        ignore_dirs = {'.git', '__pycache__', '.pytest_cache', 'venv', 'env', 'node_modules', '.vscode'}
        filtered_files = []
        
        for file_path in python_files:
            if not any(ignore_dir in file_path.parts for ignore_dir in ignore_dirs):
                if validate_path_security(self.base_path, file_path):
                    filtered_files.append(file_path)
        
        return len(filtered_files) > 0, filtered_files
        
    def _parse_bandit(self, output: str) -> List[AnalysisIssue]:
        """Parse Bandit JSON output."""
        try:
            data = json.loads(output)
            issues = []
            
            for issue_data in data.get("results", []):
                issues.append(AnalysisIssue(
                    filename=issue_data["filename"],
                    line_number=issue_data["line_number"],
                    issue_text=issue_data["issue_text"],
                    severity=issue_data["issue_severity"].upper(),
                    confidence=issue_data["issue_confidence"].upper(),
                    issue_type=issue_data["test_name"],
                    category="security",
                    rule_id=issue_data["test_id"],
                    line_range=issue_data["line_range"],
                    code=issue_data.get("code", "N/A"),
                    tool="bandit",
                    fix_suggestion=issue_data.get("more_info")
                ))
            
            return issues
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Bandit parsing error: {e}")
            return []
            
    def _parse_safety(self, output: str) -> List[AnalysisIssue]:
        """Parse Safety output."""
        issues = []
        
        # Vulnerability pattern
        vuln_pattern = re.compile(
            r"([\w\-\[\]]+)\s+([\d.]+)\s+([<>=]+[\d.]+)\s+(High|Medium|Low) Severity\s+ID: (\d+)"
        )
        
        for line in output.splitlines():
            match = vuln_pattern.search(line)
            if match:
                package, version, affected, severity, vuln_id = match.groups()
                issues.append(AnalysisIssue(
                    filename="requirements.txt",
                    line_number=0,
                    issue_text=f"Vulnerable dependency: {package} ({version}). ID: {vuln_id}",
                    severity=severity.upper(),
                    confidence="HIGH",
                    issue_type=f"safety_{vuln_id}",
                    category="dependency",
                    rule_id=vuln_id,
                    line_range=[0],
                    code=f"{package}=={version}",
                    tool="safety",
                    fix_suggestion=f"Update {package} to a secure version"
                ))
        
        return issues
        
    def _parse_pylint(self, output: str) -> List[AnalysisIssue]:
        """Parse Pylint JSON output for security issues."""
        try:
            json_start = output.find('[')
            if json_start == -1:
                return []
                
            data = json.loads(output[json_start:])
            issues = []
            
            severity_map = {"F": "HIGH", "E": "HIGH", "W": "MEDIUM", "R": "LOW", "C": "LOW"}
            
            # Security-related pylint codes
            security_codes = {
                "exec-used", "eval-used", "bad-open-mode", "hardcoded-password",
                "subprocess-popen-preexec-fn", "bad-file-permissions"
            }
            
            for issue_data in data:
                symbol = issue_data["symbol"]
                is_security = symbol in security_codes
                
                if is_security:  # Only include security-related issues
                    issues.append(AnalysisIssue(
                        filename=issue_data["path"],
                        line_number=issue_data["line"],
                        issue_text=f"[{symbol}] {issue_data['message']}",
                        severity=severity_map.get(issue_data["type"], "LOW"),
                        confidence="MEDIUM",
                        issue_type=f"pylint_{symbol}",
                        category="security",
                        rule_id=symbol,
                        line_range=[issue_data["line"]],
                        code="N/A",
                        tool="pylint"
                    ))
            
            return issues
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Pylint parsing error: {e}")
            return []
            
    def _run_bandit(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run Bandit analysis."""
        command = self.tools["bandit"]["cmd"] + ["-r", ".", "-f", "json", "-ll", "-ii"]
        return self._run_tool("bandit", command, self._parse_bandit, working_dir=app_path)
        
    def _run_safety(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run Safety analysis."""
        requirements_file = app_path / "requirements.txt"
        if not requirements_file.exists():
            return [], ToolStatus.NO_FILES.value, "No requirements.txt found"
        
        try:
            with open(requirements_file, 'r') as f:
                content = f.read()
        except IOError as e:
            return [], ToolStatus.ERROR.value, f"Error reading requirements.txt: {e}"
        
        command = self.tools["safety"]["cmd"] + ["check", "--stdin"]
        return self._run_tool("safety", command, self._parse_safety, 
                            working_dir=app_path, input_data=content)
                            
    def run_analysis(self, model: str, app_num: int, use_all_tools: bool = False,
                    force_rerun: bool = False) -> Tuple[List[Dict], Dict[str, str], Dict[str, str]]:
        """Run backend security analysis."""
        with self.analysis_lock:
            logger.info(f"🔒 Starting backend security analysis for {model}/app{app_num}")
            logger.info(f"⚙️  Configuration: use_all_tools={use_all_tools}, force_rerun={force_rerun}")
            
            # Check cache
            if not force_rerun:
                logger.info(f"🔍 Checking for cached results...")
                cached = self.results_manager.load_results(model, app_num, 
                                                         file_name=".backend_security_results.json")
                if cached:
                    logger.info("✅ Using cached backend security results")
                    return (cached.get("issues", []),
                           cached.get("tool_status", {}),
                           cached.get("tool_outputs", {}))
                else:
                    logger.info("ℹ️  No cached results found, running fresh analysis")
                           
            # Find app path
            logger.info(f"📁 Looking for backend path for {model}/app{app_num}")
            app_path = self._find_app_path(model, app_num)
            if not app_path:
                error_msg = f"Backend path not found for {model}/app{app_num}"
                logger.error(f"❌ {error_msg}")
                return [], {"error": error_msg}, {}
            logger.info(f"✅ Found backend path: {app_path}")
                
            # Determine tools to run
            tools_to_run = list(self.tools.keys()) if use_all_tools else ["bandit"]
            logger.info(f"🔧 Tools to run: {tools_to_run}")
            
            # Run tools
            all_issues = []
            tool_status = {}
            tool_outputs = {}
            
            for i, tool_name in enumerate(tools_to_run, 1):
                logger.info(f"🔧 Running tool {i}/{len(tools_to_run)}: {tool_name}")
                
                if not self.available_tools.get(tool_name):
                    status_msg = f"Tool not available"
                    logger.warning(f"⚠️  {tool_name}: {status_msg}")
                    tool_status[tool_name] = ToolStatus.NOT_FOUND.value
                    continue
                    
                logger.info(f"🚀 Executing {tool_name} on {app_path}")
                if tool_name == "bandit":
                    issues, status, output = self._run_bandit(app_path)
                elif tool_name == "safety":
                    issues, status, output = self._run_safety(app_path)
                else:
                    logger.warning(f"⚠️  Unknown tool: {tool_name}")
                    continue
                    
                # Log results
                if status == ToolStatus.SUCCESS.value:
                    issues_count = len(issues)
                    logger.info(f"✅ {tool_name} completed successfully - Found {issues_count} issues")
                else:
                    logger.error(f"❌ {tool_name} failed with status: {status}")
                    
                all_issues.extend(issues)
                tool_status[tool_name] = status
                tool_outputs[tool_name] = output
                
            # Generate final summary
            total_issues = len(all_issues)
            successful_tools = sum(1 for status in tool_status.values() 
                                 if status == ToolStatus.SUCCESS.value)
            failed_tools = len(tool_status) - successful_tools
            
            logger.info(f"🎯 Backend Security Analysis Complete!")
            logger.info(f"📊 Summary: {total_issues} total issues, {successful_tools} tools succeeded, {failed_tools} tools failed")
            
            # Sort and save
            logger.info(f"📋 Sorting and formatting {total_issues} issues...")
            sorted_issues = self._sort_issues(all_issues)
            issues_dict = [issue.to_dict() for issue in sorted_issues]
            
            logger.info(f"💾 Saving results to cache...")
            results = {
                "issues": issues_dict,
                "tool_status": tool_status,
                "tool_outputs": tool_outputs,
                "timestamp": datetime.now().isoformat(),
                "analysis_summary": {
                    "total_issues": total_issues,
                    "tools_run": len(tool_status),
                    "successful_tools": successful_tools,
                    "failed_tools": failed_tools
                }
            }
            
            self.results_manager.save_results(model, app_num, results,
                                            file_name=".backend_security_results.json")
            logger.info(f"✅ Results saved successfully")
                                            
            return issues_dict, tool_status, tool_outputs


class FrontendSecurityAnalyzer(BaseAnalyzer):
    """Analyzes frontend code for security issues."""
    
    def __init__(self, base_path: Union[str, Path]):
        super().__init__(base_path, ToolCategory.FRONTEND_SECURITY)
        self.tools = self.get_tool_definitions()
        
        logger.info(f"🔍 Initializing Frontend Security Analyzer")
        logger.info(f"📁 Base path: {base_path}")
        logger.info(f"🔧 Checking availability of {len(self.tools)} frontend security tools...")
        
        self.available_tools = {}
        for name, config in self.tools.items():
            logger.info(f"  🔍 Checking {name}...")
            is_available = self._check_tool_availability(name, config)
            self.available_tools[name] = is_available
            status_icon = "✅" if is_available else "❌"
            logger.info(f"    {status_icon} {name}: {'Available' if is_available else 'Not available'}")
            
        available_tools_list = [k for k, v in self.available_tools.items() if v]
        logger.info(f"✅ Frontend security tools ready: {len(available_tools_list)}/{len(self.tools)} available")
        logger.info(f"📋 Available tools: {available_tools_list}")
        
    def get_tool_definitions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "eslint": {
                "cmd": ["npx", "eslint"],
                "npx_tool": True,
                "requires_files": True,
                "timeout": 45
            },
            "jshint": {
                "cmd": ["npx", "jshint"],
                "npx_tool": True,
                "requires_files": True,
                "timeout": 45,
                "max_files": 30
            },
            "snyk": {
                "cmd": ["npx", "snyk"],
                "npx_tool": True,
                "requires_files": False,
                "timeout": 90
            },
            "retire": {
                "cmd": ["npx", "retire"],
                "npx_tool": True,
                "requires_files": True,
                "timeout": 60
            }
        }
        
    def _find_app_path(self, model: str, app_num: int) -> Optional[Path]:
        """Find application frontend directory path."""
        workspace_root = self.base_path.parent if self.base_path.name == "src" else self.base_path
        base_app_dir = workspace_root / "misc" / "models" / model / f"app{app_num}"

        if not base_app_dir.is_dir():
            base_app_dir = self.base_path / "misc" / "models" / model / f"app{app_num}"
            if not base_app_dir.is_dir():
                return None

        # Check for frontend directories
        frontend_markers = ["package.json", "vite.config.js", "webpack.config.js"]
        for subdir in ["frontend", "client", "web", "."]:
            candidate = base_app_dir / subdir
            if candidate.is_dir() and any((candidate / marker).exists() for marker in frontend_markers):
                return candidate.resolve()
        
        return base_app_dir
        
    def _parse_eslint(self, stdout: str) -> List[AnalysisIssue]:
        """Parse ESLint JSON output for security issues."""
        issues = []
        data = safe_json_loads(stdout.strip())
        if not isinstance(data, list):
            return issues

        security_patterns = {"security", "inject", "prototype", "csrf", "xss", "sanitize", "unsafe"}
        
        for file_result in data:
            if not isinstance(file_result, dict):
                continue
                
            file_path = Path(file_result.get("filePath", "unknown"))
            for msg in file_result.get("messages", []):
                if not isinstance(msg, dict):
                    continue
                    
                rule_id = msg.get("ruleId", "unknown") or "unknown"
                message = msg.get("message", "Unknown issue") or "Unknown issue"
                
                # Only include security-related issues
                search_text = f"{rule_id} {message}".lower()
                if any(pattern in search_text for pattern in security_patterns):
                    severity = "HIGH" if msg.get("severity", 1) >= 2 else "MEDIUM"
                    
                    issues.append(AnalysisIssue(
                        filename=str(file_path),
                        line_number=msg.get("line", 0),
                        issue_text=f"[{rule_id}] {message}",
                        severity=severity,
                        confidence="HIGH" if msg.get("fatal") else "MEDIUM",
                        issue_type=rule_id,
                        category="security",
                        rule_id=rule_id,
                        line_range=[msg.get("line", 0)],
                        code=msg.get("source", "N/A"),
                        tool="eslint",
                        fix_suggestion=msg.get("fix", {}).get("text") if msg.get("fix") else None
                    ))
        
        return issues
        
    def _parse_retire(self, stdout: str) -> List[AnalysisIssue]:
        """Parse retire.js output for vulnerable JavaScript libraries."""
        issues = []
        lines = stdout.strip().split('\n') if stdout.strip() else []
        
        current_file = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # File path detection
            if line.endswith('.js') or line.endswith('.jsx') or line.endswith('.ts') or line.endswith('.tsx'):
                current_file = line
                continue
                
            # Vulnerability detection patterns
            if 'vulnerability' in line.lower() or 'cve-' in line.lower():
                # Parse vulnerability information
                severity = "HIGH"
                if 'medium' in line.lower():
                    severity = "MEDIUM"
                elif 'low' in line.lower():
                    severity = "LOW"
                    
                # Extract CVE or vulnerability ID
                cve_match = re.search(r'CVE-\d{4}-\d+', line)
                vuln_id = cve_match.group(0) if cve_match else "unknown"
                
                issues.append(AnalysisIssue(
                    filename=current_file or "unknown",
                    line_number=0,
                    issue_text=line,
                    severity=severity,
                    confidence="HIGH",
                    issue_type=f"retire_{vuln_id}",
                    category="dependency",
                    rule_id=vuln_id,
                    line_range=[0],
                    code="N/A",
                    tool="retire",
                    fix_suggestion="Update vulnerable library to a safe version"
                ))
        
        return issues
        
    def _parse_jshint(self, stdout: str) -> List[AnalysisIssue]:
        """Parse JSHint output for JavaScript issues."""
        issues = []
        lines = stdout.strip().split('\n') if stdout.strip() else []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # JSHint format: filename: line x, col y, message (code)
            match = re.match(r'^([^:]+):\s*line\s+(\d+),\s*col\s+(\d+),\s*(.+?)\s*\(([A-Z]\d+)\).*$', line)
            if match:
                filename, line_num, col, message, code = match.groups()
                
                # Determine severity based on JSHint error codes
                severity = "WARNING"
                if code.startswith('E'):
                    severity = "ERROR"
                elif code.startswith('W'):
                    severity = "WARNING"
                    
                # Focus on security-related issues
                security_patterns = ['eval', 'with', 'document.write', 'innerHTML', 'setTimeout', 'setInterval']
                is_security = any(pattern in message.lower() for pattern in security_patterns)
                
                if is_security:
                    issues.append(AnalysisIssue(
                        filename=filename,
                        line_number=int(line_num),
                        issue_text=f"[{code}] {message}",
                        severity=severity,
                        confidence="MEDIUM",
                        issue_type=f"jshint_{code}",
                        category="security",
                        rule_id=code,
                        line_range=[int(line_num)],
                        code="N/A",
                        tool="jshint"
                    ))
        
        return issues
        
    def _parse_snyk(self, stdout: str) -> List[AnalysisIssue]:
        """Parse Snyk output for security vulnerabilities."""
        issues = []
        
        # Try to parse as JSON first
        data = safe_json_loads(stdout.strip())
        if data and isinstance(data, dict):
            vulnerabilities = data.get("vulnerabilities", [])
            for vuln in vulnerabilities:
                if not isinstance(vuln, dict):
                    continue
                    
                severity_map = {"critical": "HIGH", "high": "HIGH", "medium": "MEDIUM", "low": "LOW"}
                severity = severity_map.get(vuln.get("severity", "").lower(), "MEDIUM")
                
                issues.append(AnalysisIssue(
                    filename=vuln.get("from", ["unknown"])[0] if vuln.get("from") else "package.json",
                    line_number=0,
                    issue_text=vuln.get("title", "Unknown vulnerability"),
                    severity=severity,
                    confidence="HIGH",
                    issue_type=f"snyk_{vuln.get('id', 'unknown')}",
                    category="dependency",
                    rule_id=vuln.get("id", "unknown"),
                    line_range=[0],
                    code=vuln.get("packageName", "N/A"),
                    tool="snyk",
                    fix_suggestion=vuln.get("fixedIn", ["Update to latest version"])[0] if vuln.get("fixedIn") else None
                ))
        else:
            # Parse text output
            lines = stdout.strip().split('\n') if stdout.strip() else []
            current_issue = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Look for vulnerability markers
                if line.startswith('✗') and ('High' in line or 'Medium' in line or 'Low' in line):
                    severity = "HIGH" if "High" in line else "MEDIUM" if "Medium" in line else "LOW"
                    
                    # Extract package name and issue
                    package_match = re.search(r'in (.+?) \[', line)
                    package_name = package_match.group(1) if package_match else "unknown"
                    
                    issues.append(AnalysisIssue(
                        filename="package.json",
                        line_number=0,
                        issue_text=line,
                        severity=severity,
                        confidence="HIGH",
                        issue_type=f"snyk_{package_name}",
                        category="dependency",
                        rule_id=f"snyk_{package_name}",
                        line_range=[0],
                        code=package_name,
                        tool="snyk",
                        fix_suggestion="Update to a secure version"
                    ))
        
        return issues
        
    def _run_eslint(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run ESLint with security rules."""
        scan_dir = "src" if (app_path / "src").is_dir() else "."
        args = ["npx", "eslint", "--ext", ".js,.jsx,.ts,.tsx,.vue", "--format", "json", "--quiet", scan_dir]

        # Check for existing config
        eslint_configs = [".eslintrc.js", ".eslintrc.json", "eslint.config.js"]
        has_config = any((app_path / config).exists() for config in eslint_configs)

        if not has_config:
            # Security-focused config
            config = [
                {
                    "languageOptions": {
                        "ecmaVersion": "latest",
                        "sourceType": "module",
                        "globals": {
                            "window": "readonly",
                            "document": "readonly"
                        }
                    },
                    "rules": {
                        "no-eval": "error",
                        "no-implied-eval": "error",
                        "no-script-url": "error",
                        "no-new-func": "error"
                    }
                }
            ]
            with self._temp_config(config, "eslint.config.js", is_js=True) as temp_config:
                args.insert(2, "--config")
                args.insert(3, str(temp_config))
                return self._run_tool("eslint", args, self._parse_eslint, working_dir=app_path)
        else:
            return self._run_tool("eslint", args, self._parse_eslint, working_dir=app_path)
            
    def _run_retire(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run retire.js to detect vulnerable JavaScript libraries."""
        command = ["npx", "retire", "--outputformat", "text", "--path", "."]
        return self._run_tool("retire", command, self._parse_retire, working_dir=app_path)
        
    def _run_jshint(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run JSHint for JavaScript code quality and security issues."""
        # Find JavaScript files to analyze
        scan_patterns = ["src/**/*.js", "src/**/*.jsx", "*.js", "*.jsx"]
        
        # Use a basic JSHint config focused on security
        jshint_config = {
            "esversion": 6,
            "node": True,
            "browser": True,
            "strict": True,
            "evil": False,  # Disallow eval
            "forin": True,  # Require for-in loops to filter
            "noarg": True,  # Prohibit use of arguments.caller and arguments.callee
            "noempty": True,  # Prohibit empty blocks
            "eqeqeq": True,  # Require triple equals
            "boss": False,  # Prohibit assignments in weird places
            "loopfunc": False,  # Prohibit functions in loops
            "expr": False,  # Prohibit expression statements
            "curly": True,  # Require curly braces for blocks
            "supernew": False,  # Prohibit weird constructors
            "undef": True,  # Require all variables to be declared
            "unused": True,  # Prohibit unused variables
        }
        
        scan_dir = "src" if (app_path / "src").is_dir() else "."
        
        with self._temp_config(jshint_config, ".jshintrc", is_js=False) as temp_config:
            command = ["npx", "jshint", "--config", str(temp_config), "--reporter", "unix", scan_dir]
            return self._run_tool("jshint", command, self._parse_jshint, working_dir=app_path)
            
    def _run_snyk(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run Snyk to test for vulnerabilities."""
        if not (app_path / "package.json").exists():
            return [], ToolStatus.NO_FILES.value, "No package.json found"
            
        # Install dependencies if node_modules doesn't exist
        if not (app_path / "node_modules").exists():
            logger.info("Installing dependencies for Snyk analysis...")
            install_result = subprocess.run(
                ["npm", "install"], 
                cwd=app_path, 
                capture_output=True, 
                text=True, 
                timeout=120
            )
            if install_result.returncode != 0:
                return [], ToolStatus.ERROR.value, f"npm install failed: {install_result.stderr}"
        
        # Run Snyk test
        command = ["npx", "snyk", "test", "--json"]
        return self._run_tool("snyk", command, self._parse_snyk, working_dir=app_path)
            
    def run_analysis(self, model: str, app_num: int, use_all_tools: bool = False,
                    force_rerun: bool = False) -> Tuple[List[Dict], Dict[str, str], Dict[str, str]]:
        """Run frontend security analysis."""
        with self.analysis_lock:
            logger.info(f"🌐 Starting frontend security analysis for {model}/app{app_num}")
            logger.info(f"⚙️  Configuration: use_all_tools={use_all_tools}, force_rerun={force_rerun}")
            
            # Check cache
            if not force_rerun:
                logger.info(f"🔍 Checking for cached results...")
                cached = self.results_manager.load_results(model, app_num,
                                                         file_name=".frontend_security_results.json")
                if cached:
                    logger.info("✅ Using cached frontend security results")
                    return (cached.get("issues", []),
                           cached.get("tool_status", {}),
                           cached.get("tool_outputs", {}))
                else:
                    logger.info("ℹ️  No cached results found, running fresh analysis")
                           
            # Find app path
            logger.info(f"📁 Looking for frontend path for {model}/app{app_num}")
            app_path = self._find_app_path(model, app_num)
            if not app_path:
                error_msg = f"Frontend path not found for {model}/app{app_num}"
                logger.error(f"❌ {error_msg}")
                return [], {"error": error_msg}, {}
            logger.info(f"✅ Found frontend path: {app_path}")
                
            # Determine tools to run
            tools_to_run = ["eslint", "retire", "jshint", "snyk"] if use_all_tools else ["eslint", "retire"]
            logger.info(f"🔧 Tools to run: {tools_to_run}")
            
            # Run tools
            all_issues = []
            tool_status = {}
            tool_outputs = {}
            
            for i, tool_name in enumerate(tools_to_run, 1):
                logger.info(f"🔧 Running tool {i}/{len(tools_to_run)}: {tool_name}")
                
                if not self.available_tools.get(tool_name):
                    status_msg = f"Tool not available"
                    logger.warning(f"⚠️  {tool_name}: {status_msg}")
                    tool_status[tool_name] = ToolStatus.NOT_FOUND.value
                    continue
                    
                logger.info(f"🚀 Executing {tool_name} on {app_path}")
                if tool_name == "eslint":
                    issues, status, output = self._run_eslint(app_path)
                elif tool_name == "retire":
                    issues, status, output = self._run_retire(app_path)
                elif tool_name == "jshint":
                    issues, status, output = self._run_jshint(app_path)
                elif tool_name == "snyk":
                    issues, status, output = self._run_snyk(app_path)
                else:
                    logger.warning(f"⚠️  Unknown tool: {tool_name}")
                    continue
                    
                # Log results  
                if status == ToolStatus.SUCCESS.value:
                    issues_count = len(issues)
                    logger.info(f"✅ {tool_name} completed successfully - Found {issues_count} issues")
                else:
                    logger.error(f"❌ {tool_name} failed with status: {status}")
                    
                all_issues.extend(issues)
                tool_status[tool_name] = status
                tool_outputs[tool_name] = output
                
            # Generate final summary
            total_issues = len(all_issues)
            successful_tools = sum(1 for status in tool_status.values() 
                                 if status == ToolStatus.SUCCESS.value)
            failed_tools = len(tool_status) - successful_tools
            
            logger.info(f"🎯 Frontend Security Analysis Complete!")
            logger.info(f"📊 Summary: {total_issues} total issues, {successful_tools} tools succeeded, {failed_tools} tools failed")

            # Sort and save
            logger.info(f"📋 Sorting and formatting {total_issues} issues...")
            sorted_issues = self._sort_issues(all_issues)
            issues_dict = [issue.to_dict() for issue in sorted_issues]

            logger.info(f"💾 Saving results to cache...")
            results = {
                "issues": issues_dict,
                "tool_status": tool_status,
                "tool_outputs": tool_outputs,
                "timestamp": datetime.now().isoformat(),
                "analysis_summary": {
                    "total_issues": total_issues,
                    "tools_run": len(tool_status),
                    "successful_tools": successful_tools,
                    "failed_tools": failed_tools
                }
            }
            
            self.results_manager.save_results(model, app_num, results,
                                            file_name=".frontend_security_results.json")
            logger.info(f"✅ Results saved successfully")
            
            return issues_dict, tool_status, tool_outputs
class BackendQualityAnalyzer(BaseAnalyzer):
    """Analyzes backend code quality."""
    
    def __init__(self, base_path: Union[str, Path]):
        super().__init__(base_path, ToolCategory.BACKEND_QUALITY)
        self.tools = self.get_tool_definitions()
        self.available_tools = {name: self._check_tool_availability(name, config)
                               for name, config in self.tools.items()}
        logger.info(f"Available backend quality tools: {[k for k, v in self.available_tools.items() if v]}")
        
    def get_tool_definitions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "flake8": {
                "cmd": [sys.executable, "-m", "flake8"],
                "python_module": True,
                "requires_files": True,
                "timeout": 60,
                "max_files": 50
            },
            "pylint": {
                "cmd": [sys.executable, "-m", "pylint"],
                "python_module": True,
                "requires_files": True,
                "timeout": 60,
                "max_files": 30
            },
            "radon": {
                "cmd": [sys.executable, "-m", "radon"],
                "python_module": True,
                "requires_files": True,
                "timeout": 60,
                "max_files": 40
            },
            "mypy": {
                "cmd": [sys.executable, "-m", "mypy"],
                "python_module": True,
                "requires_files": True,
                "timeout": 60,
                "max_files": 25
            },
            "pycodestyle": {
                "cmd": [sys.executable, "-m", "pycodestyle"],
                "python_module": True,
                "requires_files": True,
                "timeout": 60,
                "max_files": 50
            },
            "pydocstyle": {
                "cmd": [sys.executable, "-m", "pydocstyle"],
                "python_module": True,
                "requires_files": True,
                "timeout": 60,
                "max_files": 40
            }
        }
        
    def _find_app_path(self, model: str, app_num: int) -> Optional[Path]:
        """Find application backend directory path."""
        workspace_root = self.base_path.parent if self.base_path.name == "src" else self.base_path
        candidates = [
            workspace_root / "misc" / "models" / model / f"app{app_num}" / "backend",
            self.base_path / "misc" / "models" / model / f"app{app_num}" / "backend",
        ]
        
        for candidate in candidates:
            if candidate.is_dir() and validate_path_security(workspace_root, candidate):
                return candidate
        
        return None
        
    def _check_source_files(self, directory: Path) -> Tuple[bool, List[Path]]:
        """Check for Python source files."""
        python_files = []
        for ext in ['.py']:
            python_files.extend(directory.rglob(f"*{ext}"))
        
        # Filter out common directories to ignore
        ignore_dirs = {'.git', '__pycache__', '.pytest_cache', 'venv', 'env', 'node_modules'}
        filtered_files = []
        
        for file_path in python_files:
            if not any(ignore_dir in file_path.parts for ignore_dir in ignore_dirs):
                if validate_path_security(self.base_path, file_path):
                    filtered_files.append(file_path)
        
        return len(filtered_files) > 0, filtered_files
        
    def _parse_flake8(self, output: str) -> List[AnalysisIssue]:
        """Parse Flake8 output."""
        try:
            issues = []
            lines = output.strip().split('\n')
            
            for line in lines:
                if not line.strip():
                    continue
                    
                # Format: filename:line:col: code message
                match = re.match(r'^([^:]+):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$', line)
                if match:
                    filename, line_num, col, code, message = match.groups()
                    
                    # Determine category based on error code
                    category = "style"
                    if code.startswith('E'):
                        severity = "ERROR"
                        if code.startswith('E1') or code.startswith('E9'):
                            category = "formatting"
                    elif code.startswith('W'):
                        severity = "WARNING"
                        category = "style"
                    elif code.startswith('F'):
                        severity = "ERROR"
                        category = "style"
                    else:
                        severity = "INFO"
                    
                    issues.append(AnalysisIssue(
                        filename=filename,
                        line_number=int(line_num),
                        issue_text=message,
                        severity=severity,
                        confidence="HIGH",
                        issue_type=f"flake8_{code}",
                        category=category,
                        rule_id=code,
                        line_range=[int(line_num)],
                        code="N/A",
                        tool="flake8"
                    ))
            
            return issues
        except Exception as e:
            logger.error(f"Flake8 parsing error: {e}")
            return []
            
    def _parse_pylint(self, output: str) -> List[AnalysisIssue]:
        """Parse Pylint JSON output for quality issues."""
        try:
            json_start = output.find('[')
            if json_start == -1:
                return []
                
            data = json.loads(output[json_start:])
            issues = []
            
            # Map pylint categories to our categories
            category_map = {
                'C': 'style',      # Convention
                'R': 'complexity', # Refactor
                'W': 'style',      # Warning
                'E': 'style',      # Error
                'F': 'style',      # Fatal
            }
            
            severity_map = {"F": "ERROR", "E": "ERROR", "W": "WARNING", "R": "WARNING", "C": "INFO"}
            
            for issue_data in data:
                issues.append(AnalysisIssue(
                    filename=issue_data["path"],
                    line_number=issue_data["line"],
                    issue_text=f"[{issue_data['symbol']}] {issue_data['message']}",
                    severity=severity_map.get(issue_data["type"], "INFO"),
                    confidence="MEDIUM",
                    issue_type=f"pylint_{issue_data['symbol']}",
                    category=category_map.get(issue_data["type"], "style"),
                    rule_id=issue_data["symbol"],
                    line_range=[issue_data["line"]],
                    code="N/A",
                    tool="pylint"
                ))
            
            return issues
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Pylint parsing error: {e}")
            return []
            
    def _parse_radon(self, output: str) -> List[AnalysisIssue]:
        """Parse Radon JSON output."""
        try:
            data = json.loads(output)
            issues = []
            
            for filename, functions in data.items():
                for func_data in functions:
                    complexity = func_data.get("complexity", 0)
                    
                    # Only report high complexity (> 10)
                    if complexity > 10:
                        severity = "ERROR" if complexity > 20 else "WARNING" if complexity > 15 else "INFO"
                        
                        issues.append(AnalysisIssue(
                            filename=filename,
                            line_number=func_data.get("lineno", 1),
                            issue_text=f"High cyclomatic complexity ({complexity}) in function '{func_data.get('name', 'unknown')}'",
                            severity=severity,
                            confidence="HIGH",
                            issue_type="radon_complexity",
                            category="complexity",
                            rule_id="CC",
                            line_range=[func_data.get("lineno", 1)],
                            code="N/A",
                            tool="radon",
                            metrics={"cyclomatic": complexity}
                        ))
            
            return issues
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Radon parsing error: {e}")
            return []
            
    def _parse_mypy(self, output: str) -> List[AnalysisIssue]:
        """Parse MyPy output."""
        issues = []
        try:
            for line in output.strip().split('\n'):
                if not line.strip():
                    continue
                    
                # MyPy format: filename:line:column: severity: message
                if ':' in line and any(sev in line for sev in ['error', 'warning', 'note']):
                    parts = line.split(':', 4)
                    if len(parts) >= 4:
                        filename = parts[0]
                        line_num = int(parts[1]) if parts[1].isdigit() else 1
                        severity = "ERROR" if "error" in line.lower() else "WARNING" if "warning" in line.lower() else "INFO"
                        message = parts[-1].strip()
                        
                        issues.append(AnalysisIssue(
                            filename=filename,
                            line_number=line_num,
                            issue_text=message,
                            severity=severity,
                            confidence="HIGH",
                            issue_type="mypy_type",
                            category="type_checking",
                            rule_id="mypy",
                            line_range=[line_num],
                            code="N/A",
                            tool="mypy"
                        ))
        except Exception as e:
            logger.error(f"MyPy parsing error: {e}")
            
        return issues
        
    def _parse_pycodestyle(self, output: str) -> List[AnalysisIssue]:
        """Parse pycodestyle output."""
        issues = []
        try:
            for line in output.strip().split('\n'):
                if not line.strip():
                    continue
                    
                # pycodestyle format: filename:line:column: code message
                if ':' in line:
                    parts = line.split(':', 3)
                    if len(parts) >= 4:
                        filename = parts[0]
                        line_num = int(parts[1]) if parts[1].isdigit() else 1
                        message_part = parts[3].strip()
                        
                        # Extract error code
                        code_match = message_part.split(' ', 1)
                        rule_id = code_match[0] if code_match else "E999"
                        message = code_match[1] if len(code_match) > 1 else message_part
                        
                        # Determine severity based on error code
                        severity = "ERROR" if rule_id.startswith('E') else "WARNING"
                        
                        issues.append(AnalysisIssue(
                            filename=filename,
                            line_number=line_num,
                            issue_text=message,
                            severity=severity,
                            confidence="HIGH",
                            issue_type="pycodestyle_style",
                            category="style",
                            rule_id=rule_id,
                            line_range=[line_num],
                            code="N/A",
                            tool="pycodestyle"
                        ))
        except Exception as e:
            logger.error(f"Pycodestyle parsing error: {e}")
            
        return issues
        
    def _parse_pydocstyle(self, output: str) -> List[AnalysisIssue]:
        """Parse pydocstyle output."""
        issues = []
        try:
            lines = output.strip().split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue
                    
                # pydocstyle format: filename:line: D### message
                if ':' in line and 'D' in line:
                    parts = line.split(':', 2)
                    if len(parts) >= 3:
                        filename = parts[0]
                        line_num = int(parts[1]) if parts[1].isdigit() else 1
                        message_part = parts[2].strip()
                        
                        # Extract error code and message
                        code_match = message_part.split(' ', 1)
                        rule_id = code_match[0] if code_match else "D999"
                        message = code_match[1] if len(code_match) > 1 else message_part
                        
                        issues.append(AnalysisIssue(
                            filename=filename,
                            line_number=line_num,
                            issue_text=message,
                            severity="WARNING",
                            confidence="MEDIUM",
                            issue_type="pydocstyle_doc",
                            category="documentation",
                            rule_id=rule_id,
                            line_range=[line_num],
                            code="N/A",
                            tool="pydocstyle"
                        ))
                i += 1
        except Exception as e:
            logger.error(f"Pydocstyle parsing error: {e}")
            
        return issues
        
    def _run_flake8(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run Flake8 analysis."""
        has_files, source_files = self._check_source_files(app_path)
        if not has_files:
            return [], ToolStatus.NO_FILES.value, "No Python files found"

        max_files = self.tools["flake8"].get("max_files", 50)
        files_to_scan = [str(Path(f).relative_to(app_path)) for f in source_files[:max_files]]
        
        command = self.tools["flake8"]["cmd"] + files_to_scan
        return self._run_tool("flake8", command, self._parse_flake8, working_dir=app_path)
        
    def _run_pylint(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run Pylint analysis."""
        has_files, source_files = self._check_source_files(app_path)
        if not has_files:
            return [], ToolStatus.NO_FILES.value, "No Python files found"

        max_files = self.tools["pylint"].get("max_files", 30)
        files_to_scan = [str(Path(f).relative_to(app_path)) for f in source_files[:max_files]]
        
        command = self.tools["pylint"]["cmd"] + ["--output-format=json", "--exit-zero"] + files_to_scan
        return self._run_tool("pylint", command, self._parse_pylint, working_dir=app_path)
        
    def _run_radon(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run Radon complexity analysis."""
        has_files, source_files = self._check_source_files(app_path)
        if not has_files:
            return [], ToolStatus.NO_FILES.value, "No Python files found"

        max_files = self.tools["radon"].get("max_files", 40)
        files_to_scan = [str(Path(f).relative_to(app_path)) for f in source_files[:max_files]]
        
        command = self.tools["radon"]["cmd"] + ["cc", "--json"] + files_to_scan
        return self._run_tool("radon", command, self._parse_radon, working_dir=app_path)
        
    def _run_mypy(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run MyPy type checking analysis."""
        has_files, source_files = self._check_source_files(app_path)
        if not has_files:
            return [], ToolStatus.NO_FILES.value, "No Python files found"

        max_files = self.tools["mypy"].get("max_files", 25)
        files_to_scan = [str(Path(f).relative_to(app_path)) for f in source_files[:max_files]]
        
        # Simplified mypy command without json report
        command = self.tools["mypy"]["cmd"] + ["--no-error-summary", "--show-error-codes"] + files_to_scan
        return self._run_tool("mypy", command, self._parse_mypy, working_dir=app_path)
        
    def _run_pycodestyle(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run pycodestyle (PEP 8) analysis."""
        has_files, source_files = self._check_source_files(app_path)
        if not has_files:
            return [], ToolStatus.NO_FILES.value, "No Python files found"

        max_files = self.tools["pycodestyle"].get("max_files", 50)
        files_to_scan = [str(Path(f).relative_to(app_path)) for f in source_files[:max_files]]
        
        command = self.tools["pycodestyle"]["cmd"] + files_to_scan
        return self._run_tool("pycodestyle", command, self._parse_pycodestyle, working_dir=app_path)
        
    def _run_pydocstyle(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run pydocstyle documentation analysis."""
        has_files, source_files = self._check_source_files(app_path)
        if not has_files:
            return [], ToolStatus.NO_FILES.value, "No Python files found"

        max_files = self.tools["pydocstyle"].get("max_files", 40)
        files_to_scan = [str(Path(f).relative_to(app_path)) for f in source_files[:max_files]]
        
        command = self.tools["pydocstyle"]["cmd"] + files_to_scan
        return self._run_tool("pydocstyle", command, self._parse_pydocstyle, working_dir=app_path)
        
    def run_analysis(self, model: str, app_num: int, use_all_tools: bool = False,
                    force_rerun: bool = False) -> Tuple[List[Dict], Dict[str, str], Dict[str, str]]:
        """Run backend quality analysis."""
        with self.analysis_lock:
            logger.info(f"🔧 Starting backend quality analysis for {model}/app{app_num}")
            logger.info(f"⚙️  Configuration: use_all_tools={use_all_tools}, force_rerun={force_rerun}")
            
            # Check cache
            if not force_rerun:
                logger.info(f"🔍 Checking for cached results...")
                cached = self.results_manager.load_results(model, app_num,
                                                         file_name=".backend_quality_results.json")
                if cached:
                    logger.info("✅ Using cached backend quality results")
                    return (cached.get("issues", []),
                           cached.get("tool_status", {}),
                           cached.get("tool_outputs", {}))
                else:
                    logger.info("ℹ️  No cached results found, running fresh analysis")
                           
            # Find app path
            logger.info(f"📁 Looking for backend path for {model}/app{app_num}")
            app_path = self._find_app_path(model, app_num)
            if not app_path:
                error_msg = f"Backend path not found for {model}/app{app_num}"
                logger.error(f"❌ {error_msg}")
                return [], {"error": error_msg}, {}
            logger.info(f"✅ Found backend path: {app_path}")
                
            # Determine tools to run
            tools_to_run = list(self.tools.keys()) if use_all_tools else ["flake8"]
            logger.info(f"🔧 Tools to run: {tools_to_run}")
            
            # Run tools
            all_issues = []
            tool_status = {}
            tool_outputs = {}
            
            for i, tool_name in enumerate(tools_to_run, 1):
                logger.info(f"🔧 Running tool {i}/{len(tools_to_run)}: {tool_name}")
                
                if not self.available_tools.get(tool_name):
                    status_msg = f"Tool not available"
                    logger.warning(f"⚠️  {tool_name}: {status_msg}")
                    tool_status[tool_name] = ToolStatus.NOT_FOUND.value
                    continue
                    
                logger.info(f"🚀 Executing {tool_name} on {app_path}")
                if tool_name == "flake8":
                    issues, status, output = self._run_flake8(app_path)
                elif tool_name == "pylint":
                    issues, status, output = self._run_pylint(app_path)
                elif tool_name == "radon":
                    issues, status, output = self._run_radon(app_path)
                elif tool_name == "mypy":
                    issues, status, output = self._run_mypy(app_path)
                elif tool_name == "pycodestyle":
                    issues, status, output = self._run_pycodestyle(app_path)
                elif tool_name == "pydocstyle":
                    issues, status, output = self._run_pydocstyle(app_path)
                else:
                    logger.warning(f"⚠️  Unknown tool: {tool_name}")
                    continue
                    
                # Log results  
                if status == ToolStatus.SUCCESS.value:
                    issues_count = len(issues)
                    logger.info(f"✅ {tool_name} completed successfully - Found {issues_count} issues")
                else:
                    logger.error(f"❌ {tool_name} failed with status: {status}")
                    
                all_issues.extend(issues)
                tool_status[tool_name] = status
                tool_outputs[tool_name] = output
                
            # Generate final summary
            total_issues = len(all_issues)
            successful_tools = sum(1 for status in tool_status.values() 
                                 if status == ToolStatus.SUCCESS.value)
            failed_tools = len(tool_status) - successful_tools
            
            logger.info(f"🎯 Backend Quality Analysis Complete!")
            logger.info(f"📊 Summary: {total_issues} total issues, {successful_tools} tools succeeded, {failed_tools} tools failed")

            # Sort and save
            logger.info(f"📋 Sorting and formatting {total_issues} issues...")
            sorted_issues = self._sort_issues(all_issues)
            issues_dict = [issue.to_dict() for issue in sorted_issues]
            
            logger.info(f"💾 Saving results to cache...")
            results = {
                "issues": issues_dict,
                "tool_status": tool_status,
                "tool_outputs": tool_outputs,
                "timestamp": datetime.now().isoformat(),
                "analysis_summary": {
                    "total_issues": total_issues,
                    "tools_run": len(tool_status),
                    "successful_tools": successful_tools,
                    "failed_tools": failed_tools
                }
            }
            
            self.results_manager.save_results(model, app_num, results,
                                            file_name=".backend_quality_results.json")
            logger.info(f"✅ Results saved successfully")
                                            
            return issues_dict, tool_status, tool_outputs


class FrontendQualityAnalyzer(BaseAnalyzer):
    """Analyzes frontend code quality."""
    
    def __init__(self, base_path: Union[str, Path]):
        super().__init__(base_path, ToolCategory.FRONTEND_QUALITY)
        self.tools = self.get_tool_definitions()
        self.available_tools = {name: self._check_tool_availability(name, config)
                               for name, config in self.tools.items()}
        logger.info(f"Available frontend quality tools: {[k for k, v in self.available_tools.items() if v]}")
        
    def get_tool_definitions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "eslint": {
                "cmd": ["npx", "eslint"],
                "npx_tool": True,
                "requires_files": True,
                "timeout": 60
            },
            "prettier": {
                "cmd": ["npx", "prettier"],
                "npx_tool": True,
                "requires_files": True,
                "timeout": 30
            },
            "jshint": {
                "cmd": ["npx", "jshint"],
                "npx_tool": True,
                "requires_files": True,
                "timeout": 45
            }
        }
        
    def _find_app_path(self, model: str, app_num: int) -> Optional[Path]:
        """Find application frontend directory path."""
        workspace_root = self.base_path.parent if self.base_path.name == "src" else self.base_path
        base_app_dir = workspace_root / "misc" / "models" / model / f"app{app_num}"

        if not base_app_dir.is_dir():
            base_app_dir = self.base_path / "misc" / "models" / model / f"app{app_num}"
            if not base_app_dir.is_dir():
                return None

        # Check for frontend directories
        frontend_markers = ["package.json", "vite.config.js", "webpack.config.js"]
        for subdir in ["frontend", "client", "web", "."]:
            candidate = base_app_dir / subdir
            if candidate.is_dir() and any((candidate / marker).exists() for marker in frontend_markers):
                return candidate.resolve()
        
        return base_app_dir
        
    def _check_source_files(self, directory: Path) -> Tuple[bool, List[Path]]:
        """Check for JavaScript/TypeScript source files."""
        js_extensions = ['.js', '.jsx', '.ts', '.tsx', '.vue']
        js_files = []
        
        for ext in js_extensions:
            js_files.extend(directory.rglob(f"*{ext}"))
        
        # Filter out common directories to ignore
        ignore_dirs = {'.git', 'node_modules', '.vscode', 'dist', 'build'}
        filtered_files = []
        
        for file_path in js_files:
            if not any(ignore_dir in file_path.parts for ignore_dir in ignore_dirs):
                if validate_path_security(self.base_path, file_path):
                    filtered_files.append(file_path)
        
        return len(filtered_files) > 0, filtered_files
        
    def _parse_eslint_quality(self, stdout: str) -> List[AnalysisIssue]:
        """Parse ESLint JSON output for quality issues (not security)."""
        issues = []
        data = safe_json_loads(stdout.strip())
        if not isinstance(data, list):
            return issues

        # Quality-focused patterns (exclude security patterns)
        quality_patterns = {"no-unused-vars", "no-console", "no-debugger", "complexity", "max-len", 
                           "indent", "semi", "quotes", "brace-style", "comma-spacing", "eol-last"}
        
        for file_result in data:
            if not isinstance(file_result, dict):
                continue
                
            file_path = Path(file_result.get("filePath", "unknown"))
            for msg in file_result.get("messages", []):
                if not isinstance(msg, dict):
                    continue
                    
                rule_id = msg.get("ruleId", "unknown") or "unknown"
                message = msg.get("message", "Unknown issue") or "Unknown issue"
                
                # Only include quality-related issues (not security)
                if any(pattern in rule_id for pattern in quality_patterns) or "style" in rule_id.lower():
                    severity = "WARNING" if msg.get("severity", 1) >= 2 else "INFO"
                    
                    # Determine category
                    category = "style"
                    if "complexity" in rule_id:
                        category = "complexity"
                    elif "unused" in rule_id:
                        category = "duplication"
                    elif any(fmt in rule_id for fmt in ["indent", "semi", "quotes", "spacing"]):
                        category = "formatting"
                    
                    issues.append(AnalysisIssue(
                        filename=str(file_path),
                        line_number=msg.get("line", 0),
                        issue_text=f"[{rule_id}] {message}",
                        severity=severity,
                        confidence="HIGH" if msg.get("fatal") else "MEDIUM",
                        issue_type=rule_id,
                        category=category,
                        rule_id=rule_id,
                        line_range=[msg.get("line", 0)],
                        code=msg.get("source", "N/A"),
                        tool="eslint",
                        fix_suggestion=msg.get("fix", {}).get("text") if msg.get("fix") else None
                    ))
        
        return issues
        
    def _parse_prettier(self, stdout: str) -> List[AnalysisIssue]:
        """Parse Prettier output for formatting issues."""
        issues = []
        lines = stdout.strip().split('\n') if stdout.strip() else []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('['):
                continue
                
            # Prettier typically shows files that need formatting
            if line.endswith('.js') or line.endswith('.jsx') or line.endswith('.ts') or line.endswith('.tsx'):
                issues.append(AnalysisIssue(
                    filename=line,
                    line_number=1,
                    issue_text="File needs formatting",
                    severity="INFO",
                    confidence="HIGH",
                    issue_type="prettier_formatting",
                    category="formatting",
                    rule_id="prettier",
                    line_range=[1],
                    code="N/A",
                    tool="prettier",
                    fix_suggestion="Run prettier --write to fix formatting"
                ))
        
        return issues
        
    def _parse_jshint_quality(self, stdout: str) -> List[AnalysisIssue]:
        """Parse JSHint output for quality issues (not security)."""
        issues = []
        lines = stdout.strip().split('\n') if stdout.strip() else []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # JSHint format: filename: line x, col y, message (code)
            match = re.match(r'^([^:]+):\s*line\s+(\d+),\s*col\s+(\d+),\s*(.+?)\s*\(([A-Z]\d+)\).*$', line)
            if match:
                filename, line_num, col, message, code = match.groups()
                
                # Determine severity based on JSHint error codes
                severity = "WARNING"
                if code.startswith('E'):
                    severity = "ERROR"
                elif code.startswith('W'):
                    severity = "WARNING"
                    
                # Focus on quality issues (not security)
                quality_patterns = ['unused', 'undef', 'missing semicolon', 'unexpected', 'expected']
                is_quality = any(pattern in message.lower() for pattern in quality_patterns)
                
                if is_quality:
                    category = "style"
                    if "unused" in message.lower():
                        category = "duplication"
                    elif "semicolon" in message.lower():
                        category = "formatting"
                        
                    issues.append(AnalysisIssue(
                        filename=filename,
                        line_number=int(line_num),
                        issue_text=f"[{code}] {message}",
                        severity=severity,
                        confidence="MEDIUM",
                        issue_type=f"jshint_{code}",
                        category=category,
                        rule_id=code,
                        line_range=[int(line_num)],
                        code="N/A",
                        tool="jshint"
                    ))
        
        return issues
        
    def _run_eslint_quality(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run ESLint for quality analysis (not security)."""
        scan_dir = "src" if (app_path / "src").is_dir() else "."
        
        # Quality-focused ESLint config
        config = [
            {
                "languageOptions": {
                    "ecmaVersion": "latest",
                    "sourceType": "module",
                    "globals": {
                        "window": "readonly",
                        "document": "readonly",
                        "console": "readonly"
                    }
                },
                "rules": {
                    "no-unused-vars": "warn",
                    "no-console": "warn",
                    "no-debugger": "error",
                    "complexity": ["warn", 10],
                    "max-len": ["warn", {"code": 120}],
                    "indent": ["warn", 2],
                    "semi": ["warn", "always"],
                    "quotes": ["warn", "single"],
                    "brace-style": "warn",
                    "comma-spacing": "warn",
                    "eol-last": "warn"
                }
            }
        ]
        
        with self._temp_config(config, "eslint.config.js", is_js=True) as temp_config:
            args = ["npx", "eslint", "--config", str(temp_config), "--ext", ".js,.jsx,.ts,.tsx,.vue", "--format", "json", scan_dir]
            return self._run_tool("eslint", args, self._parse_eslint_quality, working_dir=app_path)
            
    def _run_prettier_check(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run Prettier to check formatting."""
        scan_dir = "src" if (app_path / "src").is_dir() else "."
        command = ["npx", "prettier", "--check", f"{scan_dir}/**/*.{{js,jsx,ts,tsx}}"]
        return self._run_tool("prettier", command, self._parse_prettier, working_dir=app_path)
        
    def _run_jshint_quality(self, app_path: Path) -> Tuple[List[AnalysisIssue], str, str]:
        """Run JSHint for quality analysis."""
        # Quality-focused JSHint config
        jshint_config = {
            "esversion": 6,
            "node": True,
            "browser": True,
            "strict": True,
            "undef": True,  # Report undefined variables
            "unused": True,  # Report unused variables
            "latedef": True,  # Prohibit use before definition
            "nonew": True,  # Prohibit constructors for side-effects
            "trailing": True,  # Prohibit trailing whitespace
            "maxlen": 120,  # Line length limit
            "maxcomplexity": 10,  # Cyclomatic complexity limit
            "maxdepth": 4,  # Maximum nesting depth
            "maxparams": 5,  # Maximum number of parameters
            "maxstatements": 20  # Maximum statements per function
        }
        
        scan_dir = "src" if (app_path / "src").is_dir() else "."
        
        with self._temp_config(jshint_config, ".jshintrc", is_js=False) as temp_config:
            command = ["npx", "jshint", "--config", str(temp_config), "--reporter", "unix", scan_dir]
            return self._run_tool("jshint", command, self._parse_jshint_quality, working_dir=app_path)
            
    def run_analysis(self, model: str, app_num: int, use_all_tools: bool = False,
                    force_rerun: bool = False) -> Tuple[List[Dict], Dict[str, str], Dict[str, str]]:
        """Run frontend quality analysis."""
        with self.analysis_lock:
            logger.info(f"🎨 Starting frontend quality analysis for {model}/app{app_num}")
            logger.info(f"⚙️  Configuration: use_all_tools={use_all_tools}, force_rerun={force_rerun}")
            
            # Check cache
            if not force_rerun:
                logger.info(f"🔍 Checking for cached results...")
                cached = self.results_manager.load_results(model, app_num,
                                                         file_name=".frontend_quality_results.json")
                if cached:
                    logger.info("✅ Using cached frontend quality results")
                    return (cached.get("issues", []),
                           cached.get("tool_status", {}),
                           cached.get("tool_outputs", {}))
                else:
                    logger.info("ℹ️  No cached results found, running fresh analysis")
                           
            # Find app path
            logger.info(f"📁 Looking for frontend path for {model}/app{app_num}")
            app_path = self._find_app_path(model, app_num)
            if not app_path:
                error_msg = f"Frontend path not found for {model}/app{app_num}"
                logger.error(f"❌ {error_msg}")
                return [], {"error": error_msg}, {}
            logger.info(f"✅ Found frontend path: {app_path}")
                
            # Check for source files
            logger.info(f"📄 Checking for JavaScript/TypeScript files...")
            has_files, source_files = self._check_source_files(app_path)
            if not has_files:
                logger.info("ℹ️  No JavaScript/TypeScript files found")
                return [], {"info": "No JavaScript/TypeScript files found"}, {}
            logger.info(f"✅ Found {len(source_files)} JavaScript/TypeScript files")
                
            # Determine tools to run
            tools_to_run = ["eslint", "prettier", "jshint"] if use_all_tools else ["eslint"]
            logger.info(f"🔧 Tools to run: {tools_to_run}")
            
            # Run tools
            all_issues = []
            tool_status = {}
            tool_outputs = {}
            
            for i, tool_name in enumerate(tools_to_run, 1):
                logger.info(f"🔧 Running tool {i}/{len(tools_to_run)}: {tool_name}")
                
                if not self.available_tools.get(tool_name):
                    status_msg = f"Tool not available"
                    logger.warning(f"⚠️  {tool_name}: {status_msg}")
                    tool_status[tool_name] = ToolStatus.NOT_FOUND.value
                    continue
                    
                logger.info(f"🚀 Executing {tool_name} on {app_path}")
                if tool_name == "eslint":
                    issues, status, output = self._run_eslint_quality(app_path)
                elif tool_name == "prettier":
                    issues, status, output = self._run_prettier_check(app_path)
                elif tool_name == "jshint":
                    issues, status, output = self._run_jshint_quality(app_path)
                else:
                    logger.warning(f"⚠️  Unknown tool: {tool_name}")
                    continue
                    
                # Log results  
                if status == ToolStatus.SUCCESS.value:
                    issues_count = len(issues)
                    logger.info(f"✅ {tool_name} completed successfully - Found {issues_count} issues")
                else:
                    logger.error(f"❌ {tool_name} failed with status: {status}")
                    
                all_issues.extend(issues)
                tool_status[tool_name] = status
                tool_outputs[tool_name] = output
                
            # Generate final summary
            total_issues = len(all_issues)
            successful_tools = sum(1 for status in tool_status.values() 
                                 if status == ToolStatus.SUCCESS.value)
            failed_tools = len(tool_status) - successful_tools
            
            logger.info(f"🎯 Frontend Quality Analysis Complete!")
            logger.info(f"📊 Summary: {total_issues} total issues, {successful_tools} tools succeeded, {failed_tools} tools failed")

            # Sort and save
            logger.info(f"📋 Sorting and formatting {total_issues} issues...")
            sorted_issues = self._sort_issues(all_issues)
            issues_dict = [issue.to_dict() for issue in sorted_issues]
            
            logger.info(f"💾 Saving results to cache...")
            results = {
                "issues": issues_dict,
                "tool_status": tool_status,
                "tool_outputs": tool_outputs,
                "timestamp": datetime.now().isoformat(),
                "analysis_summary": {
                    "total_issues": total_issues,
                    "tools_run": len(tool_status),
                    "successful_tools": successful_tools,
                    "failed_tools": failed_tools
                }
            }
            
            self.results_manager.save_results(model, app_num, results,
                                            file_name=".frontend_quality_results.json")
            logger.info(f"✅ Results saved successfully")
                                            
            return issues_dict, tool_status, tool_outputs
                
            # Check for source files
            has_files, source_files = self._check_source_files(app_path)
            if not has_files:
                logger.info("No JavaScript/TypeScript files found")
                return [], {"info": "No JavaScript/TypeScript files found"}, {}
                
            # Basic analysis
            all_issues = []
            tool_status = {"file_check": f"Found {len(source_files)} JavaScript/TypeScript files"}
            tool_outputs = {"file_check": f"Files: {[str(f.relative_to(app_path)) for f in source_files[:10]]}"}
            
            # Add a placeholder issue
            if source_files:
                sample_file = source_files[0]
                all_issues.append(AnalysisIssue(
                    filename=str(sample_file.relative_to(app_path)),
                    line_number=1,
                    issue_text="Frontend quality analysis is working! (This is a test message)",
                    severity="INFO",
                    confidence="HIGH",
                    issue_type="test_issue",
                    category="style",
                    rule_id="TEST001",
                    line_range=[1],
                    code="// Test code",
                    tool="frontend_analyzer"
                ))
                
            # Convert to dict format
            issues_dict = [issue.to_dict() for issue in all_issues]
            
            # Save results
            results = {
                "issues": issues_dict,
                "tool_status": tool_status,
                "tool_outputs": tool_outputs,
                "timestamp": datetime.now().isoformat()
            }
            
            self.results_manager.save_results(model, app_num, results,
                                            file_name=".frontend_quality_results.json")
                                            
            return issues_dict, tool_status, tool_outputs


class UnifiedCLIAnalyzer:
    """Unified interface for all CLI-based analysis tools."""
    
    def __init__(self, base_path: Union[str, Path]):
        self.base_path = Path(base_path).resolve()
        
        # Initialize all analyzers
        self.analyzers = {
            ToolCategory.BACKEND_SECURITY: BackendSecurityAnalyzer(base_path),
            ToolCategory.FRONTEND_SECURITY: FrontendSecurityAnalyzer(base_path),
            ToolCategory.BACKEND_QUALITY: BackendQualityAnalyzer(base_path),
            ToolCategory.FRONTEND_QUALITY: FrontendQualityAnalyzer(base_path)
        }
        
    def get_available_tools(self, category: Optional[ToolCategory] = None) -> Dict[str, List[str]]:
        """Get available tools, optionally filtered by category."""
        if category:
            analyzer = self.analyzers.get(category)
            if analyzer:
                return {category.value: list(analyzer.available_tools.keys())}
            return {}
            
        # Return all available tools
        available = {}
        for cat, analyzer in self.analyzers.items():
            available[cat.value] = list(analyzer.available_tools.keys())
        return available
        
    def run_analysis(self, model: str, app_num: int, 
                    categories: Optional[List[ToolCategory]] = None,
                    use_all_tools: bool = False,
                    force_rerun: bool = False) -> Dict[str, Any]:
        """Run analysis across multiple categories."""
        if not categories:
            categories = list(ToolCategory)
            
        results = {}
        
        for category in categories:
            analyzer = self.analyzers.get(category)
            if not analyzer:
                continue
                
            try:
                issues, tool_status, tool_outputs = analyzer.run_analysis(
                    model, app_num, use_all_tools, force_rerun
                )
                
                results[category.value] = {
                    "issues": issues,
                    "tool_status": tool_status,
                    "tool_outputs": tool_outputs,
                    "summary": self._generate_summary(issues)
                }
            except Exception as e:
                logger.error(f"Analysis failed for {category.value}: {e}")
                results[category.value] = {
                    "error": str(e),
                    "issues": [],
                    "tool_status": {},
                    "tool_outputs": {}
                }
                
        return results
        
    def save_to_database(self, model: str, app_num: int, results: Dict[str, Any]) -> bool:
        """Save analysis results to the database."""
        try:
            # Import database components within Flask context
            from flask import current_app
            try:
                from .models import SecurityAnalysis, GeneratedApplication, AnalysisStatus
                from .extensions import db
            except ImportError:
                from models import SecurityAnalysis, GeneratedApplication, AnalysisStatus
                from extensions import db
            
            # Check if we're in app context
            if not current_app:
                logger.warning("No Flask app context available")
                return False
        except ImportError as e:
            logger.warning(f"Database integration not available: {e}")
            return False
            
        try:
            # Find or create the GeneratedApplication
            app = GeneratedApplication.query.filter_by(model_slug=model, app_number=app_num).first()
            if not app:
                logger.warning(f"GeneratedApplication not found for {model}/app{app_num}")
                return False
            
            # Count issues by severity
            total_issues = 0
            critical_severity = 0
            high_severity = 0
            medium_severity = 0 
            low_severity = 0
            
            for category_data in results.values():
                if isinstance(category_data, dict) and "issues" in category_data:
                    issues = category_data["issues"]
                    total_issues += len(issues)
                    
                    for issue in issues:
                        severity = issue.get("severity", "").upper()
                        if severity in ["CRITICAL"]:
                            critical_severity += 1
                        elif severity in ["HIGH", "ERROR"]:
                            high_severity += 1
                        elif severity in ["MEDIUM", "WARNING"]:
                            medium_severity += 1
                        else:
                            low_severity += 1
            
            # Prepare tool status data
            enabled_tools = {}
            
            for category_name, category_data in results.items():
                if isinstance(category_data, dict) and "tool_status" in category_data:
                    tool_status = category_data["tool_status"]
                    for tool_name, status in tool_status.items():
                        enabled_tools[tool_name] = status not in ["NOT_FOUND", "ERROR"]
            
            # Create or update SecurityAnalysis record
            analysis = SecurityAnalysis.query.filter_by(application_id=app.id).first()
            if not analysis:
                analysis = SecurityAnalysis()
                analysis.application_id = app.id
                db.session.add(analysis)
            
            # Update analysis fields
            analysis.status = AnalysisStatus.COMPLETED
            analysis.total_issues = total_issues
            analysis.critical_severity_count = critical_severity
            analysis.high_severity_count = high_severity
            analysis.medium_severity_count = medium_severity
            analysis.low_severity_count = low_severity
            analysis.completed_at = datetime.utcnow()
            
            if not analysis.started_at:
                analysis.started_at = datetime.utcnow()
            
            # Set tool configuration and results
            analysis.set_enabled_tools(enabled_tools)
            analysis.set_results(results)
            
            db.session.commit()
            logger.info(f"Saved CLI analysis results to database for {model}/app{app_num}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save to database: {e}")
            try:
                db.session.rollback()
            except:
                pass
            return False
    
    def run_full_analysis(self, model: str, app_num: int, 
                         use_all_tools: bool = True,
                         save_to_db: bool = True,
                         force_rerun: bool = False) -> Dict[str, Any]:
        """Run complete analysis with all tools and save to database."""
        logger.info(f"Starting full CLI analysis for {model}/app{app_num} (use_all_tools={use_all_tools})")
        
        # Run analysis across all categories
        results = self.run_analysis(
            model=model,
            app_num=app_num,
            categories=list(ToolCategory),
            use_all_tools=use_all_tools,
            force_rerun=force_rerun
        )
        
        # Add metadata
        results["metadata"] = {
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "app_num": app_num,
            "use_all_tools": use_all_tools,
            "analyzer_version": "1.0.0"
        }
        
        # Save to database if requested
        if save_to_db:
            self.save_to_database(model, app_num, results)
        
        return results
        
    def _generate_summary(self, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate analysis summary."""
        summary = {
            "total_issues": len(issues),
            "severity_counts": {},
            "category_counts": {},
            "tool_counts": {},
            "files_affected": len({issue["filename"] for issue in issues})
        }
        
        for issue in issues:
            severity = issue.get("severity", "UNKNOWN")
            category = issue.get("category", "unknown")
            tool = issue.get("tool", "unknown")
            
            summary["severity_counts"][severity] = summary["severity_counts"].get(severity, 0) + 1
            summary["category_counts"][category] = summary["category_counts"].get(category, 0) + 1
            summary["tool_counts"][tool] = summary["tool_counts"].get(tool, 0) + 1
            
        return summary


# Example usage
if __name__ == "__main__":
    # Initialize the unified analyzer
    analyzer = UnifiedCLIAnalyzer(Path.cwd())
    
    # Check available tools
    print("Available tools:")
    for category, tools in analyzer.get_available_tools().items():
        print(f"  {category}: {tools}")
        
    # Run analysis on a specific model/app
    results = analyzer.run_analysis(
        model="anthropic_claude-3-sonnet",
        app_num=1,
        categories=[ToolCategory.BACKEND_SECURITY, ToolCategory.BACKEND_QUALITY],
        use_all_tools=True
    )
    
    # Print results summary
    for category, result in results.items():
        print(f"\n{category}:")
        print(f"  Total issues: {result['summary']['total_issues']}")
        print(f"  Severity counts: {result['summary']['severity_counts']}")
