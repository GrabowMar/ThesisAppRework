"""
Backend Security Analysis Module
===============================

Comprehensive security analysis for backend code using multiple tools:
- Bandit: Security linter for Python
- Safety: Vulnerability checker for dependencies
- Pylint: Code quality and security patterns
- Vulture: Dead code detection
"""

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple, Any, Union

from logging_service import create_logger_for_component

# Import JsonResultsManager with fallback
try:
    from utils import JsonResultsManager
except ImportError:
    # This fallback shouldn't be needed anymore, but kept for safety
    class JsonResultsManager:
        """Fallback JsonResultsManager implementation - should not be used."""
        def __init__(self, base_path: Path, module_name: str):
            raise ImportError("JsonResultsManager should be imported from utils module")
        def save_results(self, model: str, app_num: int, results: Any, 
                        file_name: str = ".backend_security_results.json", **kwargs) -> Path:
            raise ImportError("JsonResultsManager should be imported from utils module")
        def load_results(self, model: str, app_num: int, 
                        file_name: str = ".backend_security_results.json", **kwargs) -> Optional[Any]:
            raise ImportError("JsonResultsManager should be imported from utils module")

# Initialize logger
logger = create_logger_for_component('backend_security')

# Constants
TOOL_TIMEOUT = 30
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
CONFIDENCE_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

# Tool configurations
TOOLS = {
    "bandit": {"cmd": [sys.executable, "-m", "bandit"], "requires_files": True},
    "safety": {"cmd": [sys.executable, "-m", "safety"], "requires_files": False},
    "pylint": {"cmd": [sys.executable, "-m", "pylint"], "requires_files": True},
    "vulture": {"cmd": [sys.executable, "-m", "vulture"], "requires_files": True}
}


class ToolStatus(str, Enum):
    SUCCESS = "✅ No issues found"
    ISSUES_FOUND = "ℹ️ Found {count} issues"
    ERROR = "❌ Error"
    NOT_FOUND = "❌ Command not found"
    NO_FILES = "⚪ No Python files"
    SKIPPED = "⚪ Skipped"


def validate_path_security(base_path: Path, target_path: Path) -> bool:
    """Validate that target_path is within base_path."""
    try:
        target_path.resolve().relative_to(base_path.resolve())
        return True
    except (OSError, ValueError):
        return False


@dataclass
class BackendSecurityIssue:
    """Security issue found in backend code."""
    filename: str
    line_number: int
    issue_text: str
    severity: str
    confidence: str
    issue_type: str
    line_range: List[int]
    code: str
    tool: str
    fix_suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackendSecurityIssue':
        return cls(**data)


class BackendSecurityAnalyzer:
    """Analyzes backend code for security issues using various tools."""

    def __init__(self, base_path: Union[str, Path]):
        self.base_path = Path(base_path).resolve()
        self.results_manager = JsonResultsManager(base_path=self.base_path, module_name="backend_security")
        self.analysis_lock = Lock()
        
        # Check tool availability
        self.available_tools = {name: self._check_tool_availability(name) for name in TOOLS.keys()}
        logger.info(f"Available tools: {[k for k, v in self.available_tools.items() if v]}")

    def _check_tool_availability(self, tool_name: str) -> bool:
        """Check if a tool is available."""
        try:
            if tool_name == "safety":
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "show", "safety"],
                    capture_output=True, timeout=5, check=False
                )
                return result.returncode == 0
            else:
                result = subprocess.run(
                    [sys.executable, "-c", f"import {tool_name}"],
                    capture_output=True, timeout=5, check=False
                )
                return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            return False

    def _find_app_path(self, model: str, app_num: int) -> Optional[Path]:
        """Find application backend directory path."""
        workspace_root = self.base_path.parent
        candidates = [
            workspace_root / "models" / model / f"app{app_num}" / "backend",
            self.base_path / "models" / model / f"app{app_num}" / "backend",
            self.base_path / model / f"app{app_num}" / "backend",
        ]
        
        for candidate in candidates:
            if candidate.is_dir() and validate_path_security(workspace_root, candidate):
                return candidate
        
        return None

    def _check_source_files(self, directory: Path) -> Tuple[bool, List[str]]:
        """Check for Python source files in directory."""
        if not directory.is_dir():
            return False, []

        try:
            files = []
            for file_path in directory.rglob('*.py'):
                if validate_path_security(directory, file_path):
                    files.append(str(file_path))
            return bool(files), files
        except (OSError, PermissionError):
            return False, []

    def _make_relative_path(self, file_path: str, base_dir: Path) -> str:
        """Convert absolute path to relative path."""
        try:
            path_obj = Path(file_path)
            if path_obj.is_absolute():
                return str(path_obj.relative_to(base_dir.resolve()))
            return file_path
        except (OSError, ValueError):
            return file_path

    def _run_tool(self, tool_name: str, command: List[str], parser: callable, 
                  working_dir: Optional[Path] = None, input_data: Optional[str] = None) -> Tuple[List[BackendSecurityIssue], str, str]:
        """Run a security tool and parse output."""
        issues = []
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=TOOL_TIMEOUT,
                check=False,
                cwd=str(working_dir or self.base_path),
                input=input_data,
                encoding='utf-8',
                errors='replace'
            )
            
            output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            
            if result.stdout and parser:
                try:
                    issues = parser(result.stdout)
                except Exception as e:
                    logger.error(f"Failed to parse {tool_name} output: {e}")
                    output += f"\nPARSING_ERROR: {e}"
            
            status = (ToolStatus.ISSUES_FOUND.value.format(count=len(issues)) if issues 
                     else ToolStatus.SUCCESS.value)
            
            if result.returncode != 0 and not result.stdout:
                status = ToolStatus.ERROR.value

        except subprocess.TimeoutExpired:
            output = f"{tool_name} timed out after {TOOL_TIMEOUT} seconds"
            status = ToolStatus.ERROR.value
        except (FileNotFoundError, OSError) as e:
            output = f"{tool_name} execution error: {e}"
            status = ToolStatus.NOT_FOUND.value

        return issues, output, status

    # Tool parsers
    def _parse_bandit(self, output: str) -> List[BackendSecurityIssue]:
        """Parse Bandit JSON output."""
        try:
            data = json.loads(output)
            issues = []
            
            for issue_data in data.get("results", []):
                issues.append(BackendSecurityIssue(
                    filename=self._make_relative_path(issue_data["filename"], self.base_path),
                    line_number=issue_data["line_number"],
                    issue_text=issue_data["issue_text"],
                    severity=issue_data["issue_severity"].upper(),
                    confidence=issue_data["issue_confidence"].upper(),
                    issue_type=issue_data["test_name"],
                    line_range=issue_data["line_range"],
                    code=issue_data.get("code", "N/A"),
                    tool="Bandit",
                    fix_suggestion=issue_data.get("more_info")
                ))
            
            return issues
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Bandit parsing error: {e}")
            return []

    def _parse_safety(self, output: str) -> List[BackendSecurityIssue]:
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
                issues.append(BackendSecurityIssue(
                    filename="dependencies",
                    line_number=0,
                    issue_text=f"Vulnerable dependency: {package} ({version}). ID: {vuln_id}",
                    severity=severity.upper(),
                    confidence="HIGH",
                    issue_type=f"safety_{vuln_id}",
                    line_range=[0],
                    code=f"{package}=={version}",
                    tool="Safety",
                    fix_suggestion=f"Update {package} to a secure version"
                ))
        
        # Unpinned dependencies
        unpinned_pattern = re.compile(r"Warning: unpinned requirement '([\w\-\[\]]+)'")
        for match in unpinned_pattern.finditer(output):
            package = match.group(1)
            issues.append(BackendSecurityIssue(
                filename="requirements.txt",
                line_number=0,
                issue_text=f"Unpinned dependency: {package}",
                severity="MEDIUM",
                confidence="MEDIUM",
                issue_type="unpinned_dependency",
                line_range=[0],
                code=package,
                tool="Safety",
                fix_suggestion=f"Pin {package} to a specific version"
            ))
        
        return issues

    def _parse_pylint(self, output: str) -> List[BackendSecurityIssue]:
        """Parse Pylint JSON output."""
        try:
            # Extract JSON from output
            json_start = output.find('[')
            if json_start == -1:
                return []
            
            data = json.loads(output[json_start:])
            issues = []
            severity_map = {"F": "HIGH", "E": "HIGH", "W": "MEDIUM", "R": "LOW", "C": "LOW"}
            
            for issue_data in data:
                issues.append(BackendSecurityIssue(
                    filename=self._make_relative_path(issue_data["path"], self.base_path),
                    line_number=issue_data["line"],
                    issue_text=f"[{issue_data['symbol']}] {issue_data['message']}",
                    severity=severity_map.get(issue_data["type"], "LOW"),
                    confidence="MEDIUM",
                    issue_type=f"pylint_{issue_data['symbol']}",
                    line_range=[issue_data["line"]],
                    code="N/A",
                    tool="Pylint",
                    fix_suggestion=None
                ))
            
            return issues
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Pylint parsing error: {e}")
            return []

    def _parse_vulture(self, output: str) -> List[BackendSecurityIssue]:
        """Parse Vulture output."""
        issues = []
        pattern = re.compile(r"^(.*?):(\d+):\s*(.*?) \((\d+)% confidence\)")
        
        for line in output.splitlines():
            match = pattern.match(line)
            if match:
                file_path, line_num, desc, conf = match.groups()
                confidence = "HIGH" if int(conf) >= 80 else "MEDIUM" if int(conf) >= 50 else "LOW"
                
                issues.append(BackendSecurityIssue(
                    filename=self._make_relative_path(file_path, self.base_path),
                    line_number=int(line_num),
                    issue_text=f"Dead Code: {desc.strip()}",
                    severity="LOW",
                    confidence=confidence,
                    issue_type="dead_code",
                    line_range=[int(line_num)],
                    code="N/A",
                    tool="Vulture",
                    fix_suggestion="Remove unused code"
                ))
        
        return issues

    # Tool runners
    def _run_bandit(self, app_path: Path) -> Tuple[List[BackendSecurityIssue], str, str]:
        """Run Bandit analysis."""
        if not self.available_tools["bandit"]:
            return [], "Bandit not available", ToolStatus.NOT_FOUND.value
        
        command = TOOLS["bandit"]["cmd"] + ["-r", ".", "-f", "json", "-ll", "-ii"]
        return self._run_tool("bandit", command, self._parse_bandit, working_dir=app_path)

    def _run_safety(self, app_path: Path) -> Tuple[List[BackendSecurityIssue], str, str]:
        """Run Safety analysis."""
        if not self.available_tools["safety"]:
            return [], "Safety not available", ToolStatus.NOT_FOUND.value
        
        requirements_file = app_path / "requirements.txt"
        if not requirements_file.exists():
            return [], "No requirements.txt found", ToolStatus.NO_FILES.value
        
        try:
            with open(requirements_file, 'r') as f:
                content = f.read()
        except IOError as e:
            return [], f"Error reading requirements.txt: {e}", ToolStatus.ERROR.value
        
        command = TOOLS["safety"]["cmd"] + ["check", "--stdin"]
        return self._run_tool("safety", command, self._parse_safety, working_dir=app_path, input_data=content)

    def _run_pylint(self, app_path: Path) -> Tuple[List[BackendSecurityIssue], str, str]:
        """Run Pylint analysis."""
        if not self.available_tools["pylint"]:
            return [], "Pylint not available", ToolStatus.NOT_FOUND.value
        
        has_files, source_files = self._check_source_files(app_path)
        if not has_files:
            return [], "No Python files found", ToolStatus.NO_FILES.value
        
        # Use relative paths
        rel_files = [str(Path(f).relative_to(app_path)) for f in source_files]
        command = TOOLS["pylint"]["cmd"] + ["--output-format=json", "--exit-zero"] + rel_files
        return self._run_tool("pylint", command, self._parse_pylint, working_dir=app_path)

    def _run_vulture(self, app_path: Path) -> Tuple[List[BackendSecurityIssue], str, str]:
        """Run Vulture analysis."""
        if not self.available_tools["vulture"]:
            return [], "Vulture not available", ToolStatus.NOT_FOUND.value
        
        command = TOOLS["vulture"]["cmd"] + [".", "--min-confidence", "50"]
        return self._run_tool("vulture", command, self._parse_vulture, working_dir=app_path)

    def _sort_issues(self, issues: List[BackendSecurityIssue]) -> List[BackendSecurityIssue]:
        """Sort issues by severity, confidence, filename, line number."""
        return sorted(issues, key=lambda i: (
            SEVERITY_ORDER.get(i.severity, 99),
            CONFIDENCE_ORDER.get(i.confidence, 99),
            i.filename,
            i.line_number
        ))

    def run_security_analysis(self, model: str, app_num: int, use_all_tools: bool = False, 
                            force_rerun: bool = False) -> Tuple[List[BackendSecurityIssue], Dict[str, str], Dict[str, str]]:
        """Run security analysis on specified model and app."""
        with self.analysis_lock:
            logger.info(f"Starting backend analysis for {model}/app{app_num}")
            
            # Check cache for full scans
            if use_all_tools and not force_rerun:
                cached = self.results_manager.load_results(model, app_num)
                if cached and isinstance(cached, dict):
                    issues = [BackendSecurityIssue.from_dict(item) for item in cached.get("issues", [])]
                    return issues, cached.get("tool_status", {}), cached.get("tool_outputs", {})

            # Find app path
            app_path = self._find_app_path(model, app_num)
            if not app_path:
                error_msg = f"Backend path not found for {model}/app{app_num}"
                tools = list(TOOLS.keys()) if use_all_tools else ["bandit"]
                return [], {t: ToolStatus.ERROR.value for t in tools}, {t: error_msg for t in tools}

            # Check for Python files
            has_files, _ = self._check_source_files(app_path)
            
            # Determine tools to run
            tools_to_run = []
            if use_all_tools:
                tools_to_run = list(TOOLS.keys())
            else:
                tools_to_run = ["bandit"]  # Default tool

            # Filter based on file requirements
            if not has_files:
                tools_to_run = [t for t in tools_to_run if not TOOLS[t]["requires_files"]]
                if not tools_to_run:
                    return [], {"bandit": ToolStatus.NO_FILES.value}, {"bandit": "No Python files found"}

            # Run tools
            tool_runners = {
                "bandit": self._run_bandit,
                "safety": self._run_safety,
                "pylint": self._run_pylint,
                "vulture": self._run_vulture
            }

            all_issues = []
            all_status = {}
            all_outputs = {}

            with ThreadPoolExecutor(max_workers=min(len(tools_to_run), 4)) as executor:
                future_to_tool = {
                    executor.submit(tool_runners[tool], app_path): tool
                    for tool in tools_to_run if tool in tool_runners
                }

                for future in as_completed(future_to_tool):
                    tool = future_to_tool[future]
                    try:
                        issues, output, status = future.result()
                        all_issues.extend(issues)
                        all_status[tool] = status
                        all_outputs[tool] = output
                    except Exception as e:
                        logger.exception(f"Tool {tool} failed: {e}")
                        all_status[tool] = ToolStatus.ERROR.value
                        all_outputs[tool] = str(e)

            # Fill in missing statuses
            for tool in TOOLS.keys():
                if tool not in all_status:
                    if not self.available_tools[tool]:
                        all_status[tool] = ToolStatus.NOT_FOUND.value
                        all_outputs[tool] = f"{tool} not available"
                    elif tool not in tools_to_run:
                        all_status[tool] = ToolStatus.SKIPPED.value
                        all_outputs[tool] = "Not selected"

            sorted_issues = self._sort_issues(all_issues)

            # Save results for full scans
            if use_all_tools:
                results = {
                    "issues": [issue.to_dict() for issue in sorted_issues],
                    "tool_status": all_status,
                    "tool_outputs": all_outputs,
                    "timestamp": datetime.now().isoformat()
                }
                self.results_manager.save_results(model, app_num, results)

            logger.info(f"Backend analysis complete: {len(sorted_issues)} issues found")
            return sorted_issues, all_status, all_outputs

    def get_analysis_summary(self, issues: List[BackendSecurityIssue]) -> Dict[str, Any]:
        """Generate analysis summary."""
        summary = {
            "total_issues": len(issues),
            "severity_counts": {sev: 0 for sev in SEVERITY_ORDER},
            "files_affected": len({issue.filename for issue in issues}),
            "tool_counts": {},
            "timestamp": datetime.now().isoformat()
        }

        for issue in issues:
            summary["severity_counts"][issue.severity] = summary["severity_counts"].get(issue.severity, 0) + 1
            summary["tool_counts"][issue.tool] = summary["tool_counts"].get(issue.tool, 0) + 1

        return summary