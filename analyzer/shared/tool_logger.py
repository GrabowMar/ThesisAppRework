"""
Tool Execution Logger - Shared Logging Utility for Analyzer Services
====================================================================

Provides standardized, structured logging for tool execution across all analyzer services.
Captures command execution details, outputs, exit codes, and durations for debugging and transparency.

Usage:
    from analyzer.shared.tool_logger import ToolExecutionLogger
    
    logger = ToolExecutionLogger(service_logger)
    
    # Before execution
    logger.log_command_start('bandit', cmd)
    
    # After execution
    exec_record = logger.log_command_complete('bandit', cmd, result, duration)
    
    # Log tool output (DEBUG level with truncation)
    logger.log_tool_output('bandit', result.stdout, result.stderr)
"""

import logging
import time
from typing import Dict, List, Any, Optional
import subprocess


class ToolExecutionLogger:
    """Structured logger for tool execution with comprehensive output capture."""
    
    # Output size limits (bytes) for DEBUG logging
    DEFAULT_STDOUT_LIMIT = 2048  # 2KB for stdout excerpt
    DEFAULT_STDERR_LIMIT = 1024  # 1KB for stderr excerpt
    
    # Output size limits for structured storage (in execution records)
    STORAGE_STDOUT_LIMIT = 8192  # 8KB for storage
    STORAGE_STDERR_LIMIT = 4096  # 4KB for storage
    
    def __init__(self, logger: logging.Logger, verbose: bool = None):
        """
        Initialize tool execution logger.
        
        Args:
            logger: Parent service logger
            verbose: Enable verbose output logging. If None, reads from VERBOSE_TOOL_LOGGING env var
        """
        self.logger = logger
        
        # Check environment variable for verbose logging
        if verbose is None:
            import os
            verbose = os.getenv('VERBOSE_TOOL_LOGGING', 'false').lower() in ('true', '1', 'yes')
        
        self.verbose = verbose
        
        if self.verbose:
            self.logger.info("[TOOL-LOGGER] Verbose tool output logging ENABLED")
    
    def log_command_start(self, tool: str, cmd: List[str], context: Optional[Dict[str, Any]] = None):
        """
        Log the start of a tool execution.
        
        Args:
            tool: Tool name (e.g., 'bandit', 'eslint', 'curl')
            cmd: Command array to execute
            context: Optional context dict (e.g., {'file': 'app.py', 'target': 'backend'})
        """
        # Sanitize command for logging (redact sensitive data)
        safe_cmd = self._sanitize_command(cmd)
        cmd_str = ' '.join(safe_cmd)
        
        # Format context as key=value pairs
        context_str = ""
        if context:
            context_parts = [f"{k}={v}" for k, v in context.items()]
            context_str = f" │ {' │ '.join(context_parts)}"
        
        # Visually appealing format with box drawing characters
        self.logger.info(f"╭─ 🔧 TOOL: {tool.upper()}")
        self.logger.info(f"│  ▶ {cmd_str}{context_str}")
        self.logger.info(f"╰─ ⏳ Starting...")
    
    def log_command_complete(
        self,
        tool: str,
        cmd: List[str],
        result: subprocess.CompletedProcess,
        duration: float,
        context: Optional[Dict[str, Any]] = None,
        is_success: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Log the completion of a tool execution and return structured execution record.
        
        Args:
            tool: Tool name
            cmd: Command array that was executed
            result: subprocess.CompletedProcess result
            duration: Execution duration in seconds
            context: Optional context dict
            is_success: Optional flag to override success determination (for tools with custom exit codes)
            
        Returns:
            Structured execution record dict with cmd, exit_code, duration, outputs
        """
        stdout_size = len(result.stdout) if result.stdout else 0
        stderr_size = len(result.stderr) if result.stderr else 0
        
        # Format output sizes in human-readable form
        def format_size(size_bytes):
            if size_bytes < 1024:
                return f"{size_bytes}B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes/1024:.1f}KB"
            else:
                return f"{size_bytes/(1024*1024):.1f}MB"
        
        # Determine status symbol and color indicator
        # Use is_success override if provided, otherwise default to exit code 0
        if is_success is not None:
            success = is_success
        else:
            success = (result.returncode == 0)
        
        if success:
            status_icon = "✅"
            status_text = "SUCCESS" if result.returncode == 0 else f"SUCCESS (exit={result.returncode})"
        else:
            status_icon = "❌"
            status_text = f"FAILED (exit={result.returncode})"
        
        # Log summary at INFO level with visual structure
        self.logger.info(f"╭─ {status_icon} TOOL: {tool.upper()}")
        self.logger.info(f"│  ⏱️  Duration: {duration:.2f}s")
        self.logger.info(f"│  📊 Output: {format_size(stdout_size)} stdout, {format_size(stderr_size)} stderr")
        self.logger.info(f"╰─ {status_text}")
        
        # Log outputs at DEBUG level if verbose mode enabled
        if self.verbose:
            self.log_tool_output(tool, result.stdout, result.stderr)
        
        # Create structured execution record for storage
        exec_record = self.create_execution_record(
            tool=tool,
            cmd=cmd,
            exit_code=result.returncode,
            duration=duration,
            stdout=result.stdout,
            stderr=result.stderr,
            context=context
        )
        
        return exec_record
    
    def log_tool_output(
        self,
        tool: str,
        stdout: Optional[str],
        stderr: Optional[str],
        truncate: bool = True
    ):
        """
        Log tool stdout/stderr at DEBUG level.
        
        Args:
            tool: Tool name
            stdout: Tool stdout output
            stderr: Tool stderr output
            truncate: Whether to truncate outputs to limits (default: True)
        """
        if not (stdout or stderr):
            return
        
        # Truncate if requested
        stdout_limit = self.DEFAULT_STDOUT_LIMIT if truncate else None
        stderr_limit = self.DEFAULT_STDERR_LIMIT if truncate else None
        
        if stdout:
            stdout_excerpt = self._truncate_text(stdout, stdout_limit)
            truncated_marker = " [TRUNCATED]" if truncate and len(stdout) > self.DEFAULT_STDOUT_LIMIT else ""
            self.logger.debug(f"╭─ 📄 {tool.upper()} STDOUT ({len(stdout)}B{truncated_marker})")
            for line in stdout_excerpt.split('\n')[:50]:  # Limit to 50 lines
                if line.strip():
                    self.logger.debug(f"│  {line}")
            self.logger.debug(f"╰─ END STDOUT")
        
        if stderr:
            stderr_excerpt = self._truncate_text(stderr, stderr_limit)
            truncated_marker = " [TRUNCATED]" if truncate and len(stderr) > self.DEFAULT_STDERR_LIMIT else ""
            self.logger.debug(f"╭─ ⚠️  {tool.upper()} STDERR ({len(stderr)}B{truncated_marker})")
            for line in stderr_excerpt.split('\n')[:50]:  # Limit to 50 lines
                if line.strip():
                    self.logger.debug(f"│  {line}")
            self.logger.debug(f"╰─ END STDERR")
    
    def create_execution_record(
        self,
        tool: str,
        cmd: List[str],
        exit_code: int,
        duration: float,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a structured execution record for storage/aggregation.
        
        Args:
            tool: Tool name
            cmd: Command array
            exit_code: Process exit code
            duration: Execution duration in seconds
            stdout: Tool stdout (will be truncated for storage)
            stderr: Tool stderr (will be truncated for storage)
            context: Optional context dict
            
        Returns:
            Structured dict with execution details
        """
        # Sanitize command for storage
        safe_cmd = self._sanitize_command(cmd)
        
        # Truncate outputs for storage (more generous limits than logging)
        truncated_stdout = self._truncate_text(stdout, self.STORAGE_STDOUT_LIMIT) if stdout else ""
        truncated_stderr = self._truncate_text(stderr, self.STORAGE_STDERR_LIMIT) if stderr else ""
        
        record = {
            'tool': tool,
            'cmd': safe_cmd,
            'exit_code': exit_code,
            'duration': round(duration, 3),
            'stdout': truncated_stdout,
            'stderr': truncated_stderr,
            'stdout_size': len(stdout) if stdout else 0,
            'stderr_size': len(stderr) if stderr else 0,
        }
        
        if context:
            record['context'] = context
        
        return record
    
    def log_parser_start(self, tool: str, input_size: int, input_type: str = 'json'):
        """
        Log the start of output parsing.
        
        Args:
            tool: Tool name
            input_size: Size of input data in bytes
            input_type: Type of input ('json', 'text', 'sarif', etc.)
        """
        def format_size(size_bytes):
            if size_bytes < 1024:
                return f"{size_bytes}B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes/1024:.1f}KB"
            else:
                return f"{size_bytes/(1024*1024):.1f}MB"
        
        self.logger.debug(f"╭─ 🔍 PARSER: {tool.upper()}")
        self.logger.debug(f"│  📥 Parsing {format_size(input_size)} of {input_type} output")
    
    def log_parser_complete(
        self,
        tool: str,
        issue_count: int,
        severity_breakdown: Optional[Dict[str, int]] = None,
        warnings: Optional[List[str]] = None
    ):
        """
        Log the completion of output parsing.
        
        Args:
            tool: Tool name
            issue_count: Number of issues extracted
            severity_breakdown: Optional dict of severity counts (e.g., {'high': 3, 'medium': 7})
            warnings: Optional list of parsing warnings
        """
        # Format severity breakdown with emojis
        severity_str = ""
        if severity_breakdown:
            severity_icons = {
                'critical': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢',
                'info': 'ℹ️'
            }
            severity_parts = []
            for sev, count in severity_breakdown.items():
                if count > 0:
                    icon = severity_icons.get(sev.lower(), '•')
                    severity_parts.append(f"{icon} {sev}={count}")
            if severity_parts:
                severity_str = f"\n│  📊 {' │ '.join(severity_parts)}"
        
        self.logger.debug(f"│  ✅ Extracted {issue_count} issue{'s' if issue_count != 1 else ''}{severity_str}")
        self.logger.debug(f"╰─ PARSING COMPLETE")
        
        if warnings:
            for warning in warnings:
                self.logger.warning(f"⚠️  PARSER WARNING [{tool.upper()}]: {warning}")
    
    def log_parser_error(self, tool: str, error: Exception, input_excerpt: Optional[str] = None):
        """
        Log a parser error with context.
        
        Args:
            tool: Tool name
            error: Exception that occurred
            input_excerpt: Optional excerpt of input that failed to parse
        """
        self.logger.error(f"╭─ ❌ PARSER ERROR: {tool.upper()}")
        self.logger.error(f"│  {type(error).__name__}: {str(error)}")
        
        if input_excerpt:
            truncated_input = self._truncate_text(input_excerpt, 200)
            self.logger.error(f"│  📄 Input excerpt: {truncated_input}")
        
        self.logger.error(f"╰─ PARSING FAILED")
    
    # Private helper methods
    
    def _sanitize_command(self, cmd: List[str]) -> List[str]:
        """
        Sanitize command array to redact sensitive data.
        
        Redacts:
        - API keys (patterns like 'sk-...', 'Bearer ...', etc.)
        - Tokens
        - Passwords
        
        Args:
            cmd: Original command array
            
        Returns:
            Sanitized command array
        """
        import re
        
        # Patterns to redact
        sensitive_patterns = [
            (r'sk-[a-zA-Z0-9]{32,}', 'sk-***REDACTED***'),  # API keys
            (r'Bearer [a-zA-Z0-9._-]{20,}', 'Bearer ***REDACTED***'),  # Bearer tokens
            (r'--api-key[= ]([^ ]+)', '--api-key=***REDACTED***'),  # --api-key flag
            (r'--token[= ]([^ ]+)', '--token=***REDACTED***'),  # --token flag
            (r'--password[= ]([^ ]+)', '--password=***REDACTED***'),  # --password flag
        ]
        
        sanitized = []
        for part in cmd:
            sanitized_part = str(part)
            for pattern, replacement in sensitive_patterns:
                sanitized_part = re.sub(pattern, replacement, sanitized_part)
            sanitized.append(sanitized_part)
        
        return sanitized
    
    def _truncate_text(self, text: Optional[str], limit: Optional[int]) -> str:
        """
        Truncate text to specified limit with ellipsis.
        
        Args:
            text: Text to truncate
            limit: Character limit (None = no truncation)
            
        Returns:
            Truncated text
        """
        if not text:
            return ""
        
        if limit is None or len(text) <= limit:
            return text
        
        # Truncate and add marker
        return text[:limit] + "\n... [TRUNCATED]"
