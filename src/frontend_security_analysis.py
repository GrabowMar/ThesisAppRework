"""
Frontend Security Analysis Module
=================================

Comprehensive security analysis for frontend code using multiple tools:
- npm audit: Vulnerability scanner for Node.js dependencies
- ESLint: JavaScript/TypeScript linter with security rules
- JSHint: JavaScript code quality checker
- Snyk: Advanced vulnerability and security scanner
"""

import concurrent.futures
import json
import os
import platform
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from contextlib import contextmanager, suppress
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import List, Optional, Tuple, Dict, Any, Union, Callable

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
                        file_name: str = ".frontend_security_results.json", **kwargs) -> Path:
            raise ImportError("JsonResultsManager should be imported from utils module")
        def load_results(self, model: str, app_num: int, 
                        file_name: str = ".frontend_security_results.json", **kwargs) -> Optional[Any]:
            raise ImportError("JsonResultsManager should be imported from utils module")

# Initialize logger
logger = create_logger_for_component('frontend_security')

# Constants
TOOL_TIMEOUT = 45
IS_WINDOWS = platform.system() == "Windows"
SEVERITY_MAP = {"critical": "HIGH", "high": "HIGH", "moderate": "MEDIUM", "medium": "MEDIUM", "low": "LOW", "info": "LOW"}
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
CONFIDENCE_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

# Tool definitions
TOOLS = {
    "npm-audit": {"cmd": "npm", "timeout": TOOL_TIMEOUT},
    "eslint": {"cmd": "npx", "timeout": TOOL_TIMEOUT},
    "jshint": {"cmd": "npx", "timeout": TOOL_TIMEOUT, "max_files": 30},
    "snyk": {"cmd": "snyk", "timeout": 90}
}

FRONTEND_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html", ".css")
JS_EXTENSIONS = (".js", ".jsx")
EXCLUDED_DIRS = {"node_modules", ".git", "dist", "build", "coverage", "vendor", "bower_components"}


class ToolStatus(str, Enum):
    SUCCESS = "✅ No issues found"
    ISSUES_FOUND = "⚠️ Found {count} issues"
    ERROR = "❌ Error"
    AUTH_REQUIRED = "❌ Authentication required"
    NOT_FOUND = "❌ Command not found"
    NO_FILES = "❌ No files to analyze"
    SKIPPED = "⚪ Skipped"


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


def validate_path_security(base_path: Path, target_path: Path) -> bool:
    """Validate that target_path is within base_path."""
    try:
        return target_path.resolve().is_relative_to(base_path.resolve())
    except (OSError, ValueError):
        return False


@dataclass
class SecurityIssue:
    """Security issue found in frontend code."""
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
    def from_dict(cls, data: Dict[str, Any]) -> 'SecurityIssue':
        return cls(**data)


class FrontendSecurityAnalyzer:
    """Analyzes frontend code for security issues using various tools."""

    def __init__(self, base_path: Union[str, Path]):
        self.base_path = Path(base_path).resolve()
        self.results_manager = JsonResultsManager(base_path=self.base_path, module_name="frontend_security")
        self.analysis_lock = Lock()
        
        # Check tool availability
        self.available_tools = {name: bool(get_executable_path(config["cmd"])) for name, config in TOOLS.items()}
        logger.info(f"Available tools: {[k for k, v in self.available_tools.items() if v]}")

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

    def _determine_status(self, tool_name: str, issues: List[SecurityIssue], output: str) -> str:
        """Determine tool execution status."""
        output_lower = output.lower()
        
        if "authenticate" in output_lower or "auth token" in output_lower:
            return ToolStatus.AUTH_REQUIRED.value
        
        if any(err in output_lower for err in ["error", "failed", "exception"]) and not issues:
            return ToolStatus.ERROR.value
            
        return ToolStatus.ISSUES_FOUND.value.format(count=len(issues)) if issues else ToolStatus.SUCCESS.value

    def _find_app_path(self, model: str, app_num: int) -> Optional[Path]:
        """Find application directory path."""
        workspace_root = self.base_path.parent
        base_app_dir = workspace_root / "models" / model / f"app{app_num}"

        if not base_app_dir.is_dir():
            base_app_dir = self.base_path / "models" / model / f"app{app_num}"
            if not base_app_dir.is_dir():
                return None

        if not validate_path_security(self.base_path.parent, base_app_dir):
            logger.error(f"Security violation: {base_app_dir}")
            return None

        # Check for frontend directories
        frontend_markers = ["package.json", "vite.config.js", "webpack.config.js", "angular.json"]
        for subdir in ["frontend", "client", "web", "."]:
            candidate = base_app_dir / subdir
            if candidate.is_dir() and any((candidate / marker).exists() for marker in frontend_markers):
                return candidate.resolve()
        
        return base_app_dir

    def _check_source_files(self, directory: Path, extensions: Tuple[str, ...] = FRONTEND_EXTENSIONS) -> Tuple[bool, List[str]]:
        """Check for source files in directory."""
        if not directory.is_dir():
            return False, []

        files = []
        try:
            for root, dirs, filenames in os.walk(directory, topdown=True):
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
                for filename in filenames:
                    if filename.endswith(extensions):
                        file_path = Path(root) / filename
                        if validate_path_security(directory, file_path):
                            files.append(str(file_path))
        except (OSError, PermissionError) as e:
            logger.error(f"Error checking files in {directory}: {e}")
            return False, []

        return len(files) > 0, files

    def _run_tool(self, tool_name: str, command: List[str], working_dir: Path, 
                  parser: Optional[Callable[[str], List['SecurityIssue']]], timeout: int = TOOL_TIMEOUT) -> Tuple[List['SecurityIssue'], str]:
        """Run a security tool and parse output."""
        issues = []
        
        executable = get_executable_path(command[0])
        if not executable:
            return issues, f"{tool_name} command not found"

        full_command = [executable] + command[1:]
        logger.info(f"Running {tool_name}: {' '.join(full_command)}")

        try:
            proc = subprocess.run(
                full_command,
                cwd=str(working_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                encoding='utf-8',
                errors='replace'
            )
            
            output = f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            
            if proc.stdout and parser:
                try:
                    issues = parser(proc.stdout)
                except Exception as e:
                    logger.error(f"Failed to parse {tool_name} output: {e}")
                    output += f"\nPARSING_ERROR: {e}"

        except subprocess.TimeoutExpired:
            output = f"{tool_name} timed out after {timeout} seconds"
        except (FileNotFoundError, OSError) as e:
            output = f"{tool_name} execution error: {e}"

        return issues, output

    # Tool-specific parsers
    def _parse_npm_audit(self, stdout: str) -> List[SecurityIssue]:
        """Parse npm audit JSON output."""
        issues = []
        data = safe_json_loads(stdout.strip())
        if not data:
            return issues

        # Handle both dict and list cases
        if isinstance(data, dict):
            vulnerabilities = data.get("vulnerabilities", data.get("advisories", {}))
            items = vulnerabilities.items() if isinstance(vulnerabilities, dict) else []
        elif isinstance(data, list):
            items = []
            for entry in data:
                if isinstance(entry, dict):
                    items.extend(entry.get("vulnerabilities", {}).items())
        else:
            items = []

        for key, vuln in items:
            if not isinstance(vuln, dict):
                continue
            severity = SEVERITY_MAP.get(vuln.get("severity", "info").lower(), "LOW")
            name = vuln.get("name", key)
            title = vuln.get("title", "N/A")
            # Handle nested via structure
            via = vuln.get("via", [])
            if isinstance(via, list) and via and isinstance(via[0], dict):
                title = via[0].get("title", title)
            fix_available = vuln.get("fixAvailable")
            fix_text = "Fix available via npm audit fix" if fix_available else "Review advisory"
            issues.append(SecurityIssue(
                filename="package-lock.json",
                line_number=0,
                issue_text=f"{title} (Package: {name})",
                severity=severity,
                confidence="HIGH",
                issue_type=f"dependency_vuln_{name}",
                line_range=[0],
                code=f"{name}",
                tool="npm-audit",
                fix_suggestion=fix_text
            ))
        return issues

    def _parse_eslint(self, stdout: str) -> List[SecurityIssue]:
        """Parse ESLint JSON output."""
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
                    
                rule_id = msg.get("ruleId", "unknown")
                message = msg.get("message", "Unknown issue")
                severity_val = msg.get("severity", 1)
                is_fatal = msg.get("fatal", False)
                
                # Determine severity
                severity = "HIGH" if severity_val >= 2 or is_fatal else "MEDIUM"
                if any(pattern in f"{rule_id} {message}".lower() for pattern in security_patterns):
                    severity = "HIGH"
                
                issues.append(SecurityIssue(
                    filename=str(file_path),
                    line_number=msg.get("line", 0),
                    issue_text=f"[{rule_id}] {message}",
                    severity=severity,
                    confidence="HIGH" if is_fatal else "MEDIUM",
                    issue_type=rule_id,
                    line_range=[msg.get("line", 0)],
                    code=msg.get("source", "N/A"),
                    tool="eslint",
                    fix_suggestion=msg.get("fix", {}).get("text")
                ))
        
        return issues

    def _parse_jshint(self, stdout: str) -> List[SecurityIssue]:
        """Parse JSHint XML output."""
        issues = []
        try:
            root = ET.fromstring(stdout.strip())
        except ET.ParseError:
            return issues

        security_codes = {"W054", "W061"}
        security_keywords = {"eval", "function(", "settimeout", "innerhtml"}
        
        for file_elem in root.findall("file"):
            file_path = Path(file_elem.get("name", "unknown"))
            for error in file_elem.findall("error"):
                line = int(error.get("line", 0))
                message = error.get("message", "Unknown issue")
                code = error.get("code", "")
                
                is_security = (code in security_codes or 
                             any(kw in message.lower() for kw in security_keywords))
                
                severity = "HIGH" if code.startswith('E') or is_security else "MEDIUM"
                
                issues.append(SecurityIssue(
                    filename=str(file_path),
                    line_number=line,
                    issue_text=f"[{code}] {message}",
                    severity=severity,
                    confidence="HIGH" if code in security_codes else "MEDIUM",
                    issue_type=f"jshint_{code}",
                    line_range=[line],
                    code="N/A",
                    tool="jshint",
                    fix_suggestion="Review code for security implications" if is_security else None
                ))
        
        return issues

    def _parse_snyk(self, stdout: str) -> List[SecurityIssue]:
        """Parse Snyk JSON output."""
        issues = []
        data = safe_json_loads(stdout.strip())
        if not data:
            return issues

        # Extract vulnerabilities from various data structures
        vulnerabilities = []
        if isinstance(data, dict):
            vulnerabilities = data.get("vulnerabilities", [])
        elif isinstance(data, list):
            for project in data:
                if isinstance(project, dict):
                    vulnerabilities.extend(project.get("vulnerabilities", []))
        
        for vuln in vulnerabilities:
            if not isinstance(vuln, dict):
                continue
                
            severity = SEVERITY_MAP.get(vuln.get("severity", "low"), "LOW")
            package_name = vuln.get("packageName", "N/A")
            title = vuln.get("title", "N/A")
            vuln_id = vuln.get("id", "N/A")
            
            fix_text = ("Upgrade available" if vuln.get("isUpgradable") 
                       else "Patch available" if vuln.get("isPatchable") 
                       else "Review Snyk report")
            
            issues.append(SecurityIssue(
                filename="dependency_tree",
                line_number=0,
                issue_text=f"{title} ({package_name}) - {vuln_id}",
                severity=severity,
                confidence="HIGH",
                issue_type=f"snyk_vuln_{vuln_id}",
                line_range=[0],
                code=package_name,
                tool="snyk",
                fix_suggestion=fix_text
            ))
        
        return issues

    # Tool runners
    def _run_npm_audit(self, app_path: Path) -> Tuple[List[SecurityIssue], Dict[str, str], str]:
        """Run npm audit."""
        if not (app_path / "package.json").exists():
            return [], {"npm-audit": ToolStatus.NO_FILES.value}, "No package.json found"
        
        # Generate package-lock.json if missing
        if not (app_path / "package-lock.json").exists():
            self._run_tool("npm-install", ["npm", "install", "--package-lock-only"], app_path, None, 120)
        
        issues, output = self._run_tool("npm-audit", ["npm", "audit", "--json"], app_path, self._parse_npm_audit)
        status = self._determine_status("npm-audit", issues, output)
        return issues, {"npm-audit": status}, output

    def _run_eslint(self, app_path: Path) -> Tuple[List[SecurityIssue], Dict[str, str], str]:
        """Run ESLint."""
        has_files, _ = self._check_source_files(app_path)
        if not has_files:
            return [], {"eslint": ToolStatus.NO_FILES.value}, "No frontend files found"

        scan_dir = "src" if (app_path / "src").is_dir() else "."
        args = ["npx", "eslint", "--ext", ".js,.jsx,.ts,.tsx,.vue", "--format", "json", "--quiet", scan_dir]

        # Check for existing config
        eslint_configs = [".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml", "eslint.config.js"]
        has_config = any((app_path / config).exists() for config in eslint_configs)

        if not has_config:
            # Use ESLint 9.x flat config format
            config = [
                {
                    "languageOptions": {
                        "ecmaVersion": "latest",
                        "sourceType": "module",
                        "globals": {
                            "window": "readonly",
                            "document": "readonly",
                            "console": "readonly",
                            "process": "readonly",
                            "Buffer": "readonly",
                            "global": "readonly"
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
            # Use eslint.config.js for ESLint 9.x flat config compatibility
            with self._temp_config(config, "eslint.config.js", is_js=True) as temp_config:
                args.insert(2, "--config")
                args.insert(3, str(temp_config))
                issues, output = self._run_tool("eslint", args, app_path, self._parse_eslint)
        else:
            issues, output = self._run_tool("eslint", args, app_path, self._parse_eslint)

        status = self._determine_status("eslint", issues, output)
        return issues, {"eslint": status}, output

    def _run_jshint(self, app_path: Path) -> Tuple[List[SecurityIssue], Dict[str, str], str]:
        """Run JSHint."""
        has_files, files = self._check_source_files(app_path, JS_EXTENSIONS)
        if not has_files:
            return [], {"jshint": ToolStatus.NO_FILES.value}, "No JS files found"

        max_files = TOOLS["jshint"].get("max_files", 30)
        files_to_scan = [str(Path(f).relative_to(app_path)) for f in files[:max_files]]
        
        args = ["npx", "jshint", "--reporter=checkstyle"] + files_to_scan
        
        if not (app_path / ".jshintrc").exists():
            config = {
                "esversion": 9,
                "browser": True,
                "node": True,
                "strict": "implied",
                "undef": True,
                "unused": "vars",
                "evil": True,
                "maxerr": 100
            }
            with self._temp_config(config, ".jshintrc") as temp_config:
                args.insert(2, "--config")
                args.insert(3, str(temp_config))
                issues, output = self._run_tool("jshint", args, app_path, self._parse_jshint)
        else:
            issues, output = self._run_tool("jshint", args, app_path, self._parse_jshint)
        
        status = self._determine_status("jshint", issues, output)
        return issues, {"jshint": status}, output

    def _run_snyk(self, app_path: Path) -> Tuple[List[SecurityIssue], Dict[str, str], str]:
        """Run Snyk."""
        if not (app_path / "package.json").exists():
            return [], {"snyk": ToolStatus.NO_FILES.value}, "No package.json found"

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            temp_file = Path(tmp.name)
        
        try:
            args = ["snyk", "test", f"--json-file-output={temp_file}"]
            _, output = self._run_tool("snyk", args, app_path, None, TOOLS["snyk"]["timeout"])
            
            issues = []
            if temp_file.exists() and temp_file.stat().st_size > 0:
                with open(temp_file, 'r') as f:
                    issues = self._parse_snyk(f.read())
            
            status = self._determine_status("snyk", issues, output)
            return issues, {"snyk": status}, output
        finally:
            with suppress(OSError):
                temp_file.unlink()

    def _sort_issues(self, issues: List[SecurityIssue]) -> List[SecurityIssue]:
        """Sort issues by severity, confidence, filename, line number."""
        return sorted(issues, key=lambda i: (
            SEVERITY_ORDER.get(i.severity, 99),
            CONFIDENCE_ORDER.get(i.confidence, 99),
            i.filename,
            i.line_number
        ))

    def run_security_analysis(self, model: str, app_num: int, use_all_tools: bool = False, 
                            force_rerun: bool = False) -> Tuple[List[SecurityIssue], Dict[str, str], Dict[str, str]]:
        """Run security analysis on specified model and app."""
        with self.analysis_lock:
            logger.info(f"Starting analysis for {model}/app{app_num}")
            
            # Check cache for full scans
            if use_all_tools and not force_rerun:
                cached = self.results_manager.load_results(model, app_num)
                if cached and isinstance(cached, dict):
                    issues = [SecurityIssue.from_dict(item) for item in cached.get("issues", [])]
                    return issues, cached.get("tool_status", {}), cached.get("tool_outputs", {})

            # Find app path
            app_path = self._find_app_path(model, app_num)
            if not app_path:
                error_msg = f"App path not found for {model}/app{app_num}"
                tools = list(TOOLS.keys()) if use_all_tools else ["eslint"]
                return [], {t: ToolStatus.ERROR.value for t in tools}, {t: error_msg for t in tools}

            # Determine tools to run
            tools_to_run = []
            if use_all_tools:
                tools_to_run = [t for t in TOOLS.keys() if self.available_tools.get(t)]
            else:
                if self.available_tools.get("eslint"):
                    tools_to_run = ["eslint"]

            if not tools_to_run:
                return [], {"eslint": ToolStatus.NOT_FOUND.value}, {"eslint": "No tools available"}

            # Run tools
            tool_runners = {
                "npm-audit": self._run_npm_audit,
                "eslint": self._run_eslint,
                "jshint": self._run_jshint,
                "snyk": self._run_snyk
            }

            all_issues = []
            all_status = {}
            all_outputs = {}

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tools_to_run), 4)) as executor:
                future_to_tool = {
                    executor.submit(tool_runners[tool], app_path): tool
                    for tool in tools_to_run if tool in tool_runners
                }

                for future in concurrent.futures.as_completed(future_to_tool):
                    tool = future_to_tool[future]
                    try:
                        issues, status, output = future.result()
                        all_issues.extend(issues)
                        all_status.update(status)
                        all_outputs[tool] = output
                    except Exception as e:
                        logger.exception(f"Tool {tool} failed: {e}")
                        all_status[tool] = ToolStatus.ERROR.value
                        all_outputs[tool] = str(e)

            # Fill in missing statuses
            for tool in TOOLS.keys():
                if tool not in all_status:
                    if not self.available_tools.get(tool):
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

            logger.info(f"Analysis complete: {len(sorted_issues)} issues found")
            return sorted_issues, all_status, all_outputs

    def get_analysis_summary(self, issues: List[SecurityIssue]) -> Dict[str, Any]:
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