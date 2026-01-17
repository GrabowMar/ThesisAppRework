"""
Centralized Logging Configuration
=================================

Provides a unified logging setup for the entire application with proper
log levels, formatting, and rotation to reduce spam and improve readability.
"""

import os
import sys
import logging
import warnings
import re
from pathlib import Path
from typing import Dict, Optional
from logging.handlers import RotatingFileHandler
from datetime import datetime
from collections import defaultdict

# Color coding dependencies
try:
    from colorama import init, Fore, Style  # type: ignore
    init(autoreset=True)
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    # Fallback color constants
    class Fore:
        RED = BLUE = GREEN = YELLOW = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""

# NOTE: We intentionally avoid monkey-patching LogRecord.getMessage.
# Malformed printf-style logs are normalized via a lightweight LogRecordFactory
# installed during setup; developer guidance: prefer f-strings or supply all
# printf args. See _install_safe_record_factory.

# Custom Logger class ensuring malformed printf-style messages are sanitized
_original_logger_class = logging.getLoggerClass()

class ThesisLogger(_original_logger_class):  # type: ignore[misc]
    def makeRecord(self, *args, **kwargs):  # pragma: no cover - behavior tested indirectly
        record = super().makeRecord(*args, **kwargs)
        # Lightweight early probe; if we fail here a later SafeLogRecord.getMessage
        # still provides a final safety net. This double layer guards against
        # third-party factories swapping ours out after setup.
        if record.args:
            try:
                _ = record.msg % record.args  # probe only
            except TypeError:
                try:
                    raw_msg = str(record.msg)
                except Exception:
                    raw_msg = '<unprintable log message>'
                record.msg = raw_msg
                record.args = ()
                setattr(record, "_malformed_format", True)
        return record

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):  # type: ignore[override]
        # Pre-sanitize before delegating to avoid malformed args propagating.
        if args:
            try:
                # Probe formatting (discard result)
                msg % args  # type: ignore[operator]
            except TypeError:
                try:
                    msg = str(msg)
                except Exception:
                    msg = '<unprintable log message>'
                args = ()
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel)  # pragma: no cover

# Install logger class early (idempotent)
if not isinstance(logging.getLoggerClass(), ThesisLogger):  # pragma: no cover
    logging.setLoggerClass(ThesisLogger)


def _safe_get_message(record: logging.LogRecord) -> str:
    """Safely retrieve a log record's message without raising formatting errors.

    Normalizes the record in-place if a formatting TypeError occurs so that
    downstream filters/formatters do not repeatedly trigger the same error.
    """
    try:
        # NOTE: Always use this helper instead of record.getMessage() directly
        # inside filters/formatters to avoid re-raising TypeError when a log
        # call used printf-style formatting with mismatched / missing args.
        return record.getMessage()
    except TypeError:
        # Fallback to raw msg; clear args so future getMessage calls succeed
        try:
            raw_msg = str(record.msg)
        except Exception:  # pragma: no cover - extreme edge
            raw_msg = '<unprintable log message>'
        record.msg = raw_msg
        record.args = ()
        # Mark record so filters know this originated from malformed printf-style usage
        setattr(record, "_malformed_format", True)
        # Emit a one-time stderr hint (not via logging to avoid recursion)
        if not getattr(_safe_get_message, "_warned", False):  # type: ignore[attr-defined]
            try:
                sys.stderr.write("[logging] Normalized malformed log format (future occurrences suppressed)\n")
            except Exception:  # pragma: no cover
                pass
            setattr(_safe_get_message, "_warned", True)  # type: ignore[attr-defined]
        return raw_msg


class _SafeLogRecord(logging.LogRecord):  # pragma: no cover - exercised indirectly via logging
    """LogRecord subclass whose getMessage never raises on bad printf formatting."""
    def getMessage(self):  # type: ignore[override]
        msg = str(self.msg)
        if self.args:
            try:
                msg = msg % self.args
            except TypeError:
                # Normalize: keep original template, drop args so future calls safe
                self.args = ()
                setattr(self, "_malformed_format", True)
            except Exception:
                # Extremely defensive; return best-effort string
                self.args = ()
        return msg


def _install_safe_record_factory():
    """Install idempotent factory producing _SafeLogRecord instances.

    This guarantees pytest's caplog (which calls record.getMessage) will never
    trigger a TypeError for malformed printf-style usage. We retain earlier
    probes in ThesisLogger for defense-in-depth but rely on the subclass for
    definitive safety.
    """
    if getattr(logging, "_thesis_safe_record_factory_v3", False):
        return
    orig_factory = logging.getLogRecordFactory()

    def factory(*args, **kwargs):  # pragma: no cover
        record = orig_factory(*args, **kwargs)
        # Re-wrap into _SafeLogRecord preserving attributes (cannot just cast; recreate)
        safe = _SafeLogRecord(
            record.name, record.levelno, record.pathname, record.lineno,
            record.msg, record.args, record.exc_info, record.funcName,
            record.__dict__.get('sinfo')
        )
        # Preserve stack_info if present (attribute; not constructor arg)
        if hasattr(record, 'stack_info'):
            try:
                safe.stack_info = record.stack_info  # type: ignore[attr-defined]
            except Exception:
                pass
        # Copy any custom attributes already set
        for k, v in record.__dict__.items():
            if k not in safe.__dict__:
                try:
                    setattr(safe, k, v)
                except Exception:
                    pass
        return safe

    logging.setLogRecordFactory(factory)
    setattr(logging, "_thesis_safe_record_factory_v3", True)


class MalformedFormatSanitizerFilter(logging.Filter):
    """Filter attached to root logger to defensively sanitize any malformed
    printf-style logging records prior to handler formatting. Non-invasive and
    idempotent; complements the safe record factory for environments that
    might swap factories after our setup (e.g., test harnesses)."""
    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover
        if getattr(record, "_malformed_format", False):
            return True
        if record.args:
            try:
                _ = record.msg % record.args
            except TypeError:
                try:
                    raw_msg = str(record.msg)
                except Exception:
                    raw_msg = '<unprintable log message>'
                record.msg = raw_msg
                record.args = ()
                setattr(record, "_malformed_format", True)
        return True


class StackTraceFilter(logging.Filter):
    """Filter to compress and group stack traces."""
    
    def __init__(self, name: str = ""):
        super().__init__(name)
        self._last_stack_traces: Dict[str, datetime] = {}
        self._stack_count: Dict[str, int] = defaultdict(int)
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and compress stack traces."""
        if record.exc_info or record.stack_info:
            # Create a hash of the stack trace
            stack_key = self._get_stack_key(record)
            current_time = datetime.now()
            
            # Count occurrences
            self._stack_count[stack_key] += 1
            
            # Only show stack trace every 5 minutes for the same error
            if stack_key in self._last_stack_traces:
                last_time = self._last_stack_traces[stack_key]
                if (current_time - last_time).seconds < 300:
                    # Replace with summary message
                    count = self._stack_count[stack_key]
                    # Use safe retrieval; reset args so future formatting is safe
                    record.msg = f"{_safe_get_message(record)} (repeated {count}x - stack trace suppressed)"
                    record.args = ()
                    record.exc_info = None
                    record.stack_info = None
                    return True
            
            self._last_stack_traces[stack_key] = current_time
        
        return True
    
    def _get_stack_key(self, record: logging.LogRecord) -> str:
        """Create a key to identify similar stack traces (defensive)."""
        if record.exc_info:
            exc_type = record.exc_info[0].__name__ if record.exc_info[0] else "Unknown"
            exc_msg = str(record.exc_info[1])[:100] if record.exc_info[1] else ""
            return f"{exc_type}:{exc_msg}"
        message = _safe_get_message(record)
        return f"stack:{message[:50]}"


class WerkzeugEndpointFilter(logging.Filter):
    """Filter to suppress high-frequency werkzeug request logs.
    
    Suppresses logging for:
    - Health check endpoint (/api/health)
    - Pipeline status polling (/automation/api/pipeline/*/status)
    - Fragment status (/automation/fragments/status)
    - Static files (css, js, images, fonts)
    - Favicon requests
    - Socket.IO polling
    
    These endpoints are called frequently and create excessive noise.
    """
    
    # Endpoints to suppress (substring matches)
    _suppressed_endpoints = (
        'GET /api/health ',
        '/status HTTP',
        '/detailed-status HTTP',
        '/fragments/status HTTP',
        'GET /static/',
        'GET /favicon',
        '/socket.io/',
        '?polling',
    )
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out high-frequency polling endpoints."""
        message = _safe_get_message(record)
        
        # Check if this is a request log for a suppressed endpoint
        for endpoint in self._suppressed_endpoints:
            if endpoint in message:
                return False
        
        return True


class SecurityScannerProbeFilter(logging.Filter):
    """Filter to suppress security scanner probe 404s from web app logs.
    
    Security scanners (like OWASP ZAP) probe for common admin paths, vulnerability
    endpoints, and technology-specific files. These generate many 404s that clutter
    the web app logs.
    
    This filter:
    - Detects scanner probe patterns (admin paths, .asp/.aspx/.php files, etc.)
    - Suppresses individual probe logs
    - Emits periodic summary notices
    """
    
    # Common scanner probe patterns (lowercase for matching)
    _scanner_patterns = (
        # Admin panels
        '/admin', '/administrator', '/wp-admin', '/phpmyadmin',
        '/siteadmin', '/controlpanel', '/cpanel', '/webadmin',
        '/memberadmin', '/moderator', '/manager',
        # Legacy file extensions (ASP, ASPX, PHP probes)
        '.asp', '.aspx', '.php', '.cgi', '.pl', '.cfm', '.jsp',
        # Common vulnerability paths
        '/login', '/signin', '/user', '/account',
        '/upload', '/backup', '/config', '.bak', '.old', '.sql',
        # CMS paths
        '/wordpress', '/joomla', '/drupal', '/magento',
        # Misc scanner patterns  
        '/shell', '/cmd', '/exec', '/phpinfo',
    )
    
    # Track suppressed probes for periodic summary
    _probe_count = 0
    _last_summary_time = None
    _summary_interval = 60  # seconds between summaries
    
    def __init__(self, name: str = ""):
        super().__init__(name)
        SecurityScannerProbeFilter._last_summary_time = datetime.now()
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter security scanner probe requests."""
        message = _safe_get_message(record).lower()
        
        # Only filter 404 responses that match scanner patterns
        if '404' not in message:
            return True
        
        # Check if this looks like a scanner probe
        is_probe = False
        for pattern in self._scanner_patterns:
            if pattern in message:
                is_probe = True
                break
        
        # Also detect HEAD requests (common scanner technique)
        if 'head /' in message:
            is_probe = True
        
        if is_probe:
            SecurityScannerProbeFilter._probe_count += 1
            
            # Emit periodic summary
            now = datetime.now()
            if SecurityScannerProbeFilter._last_summary_time:
                elapsed = (now - SecurityScannerProbeFilter._last_summary_time).total_seconds()
                if elapsed >= self._summary_interval and SecurityScannerProbeFilter._probe_count > 0:
                    # Log summary and reset counter
                    count = SecurityScannerProbeFilter._probe_count
                    SecurityScannerProbeFilter._probe_count = 0
                    SecurityScannerProbeFilter._last_summary_time = now
                    # Modify the record to show summary instead of individual probe
                    record.msg = f"[SCANNER] Suppressed {count} security scanner probe 404s (see dynamic-analyzer logs for details)"
                    record.args = ()
                    record.levelno = logging.DEBUG
                    return True
            
            # Suppress individual probe logs
            return False
        
        return True


class LogGrouper:
    """Groups similar log messages to reduce spam."""
    
    def __init__(self, group_window: int = 60):
        self.group_window = group_window  # seconds
        self.message_groups: Dict[str, Dict] = {}
        
    def should_log_message(self, record: logging.LogRecord) -> tuple[bool, Optional[str]]:
        """Determine if message should be logged or grouped."""
        message_pattern = self._get_message_pattern(record)
        current_time = datetime.now()
        
        if message_pattern in self.message_groups:
            group = self.message_groups[message_pattern]
            group['count'] += 1
            group['last_seen'] = current_time
            
            # If it's been less than group_window seconds, suppress
            if (current_time - group['first_seen']).seconds < self.group_window:
                return False, None
            else:
                # Time to summarize
                # Build summary defensively
                summary = f"[GROUPED] {_safe_get_message(record)} (repeated {group['count']}x in {self.group_window}s)"
                # Reset the group
                del self.message_groups[message_pattern]
                return True, summary
        else:
            # New message pattern
            self.message_groups[message_pattern] = {
                'count': 1,
                'first_seen': current_time,
                'last_seen': current_time,
                'record': record
            }
            return True, None
    
    def _get_message_pattern(self, record: logging.LogRecord) -> str:
        """Extract pattern from log message for grouping (defensive)."""
        message = _safe_get_message(record)
        
        # Patterns for common repetitive messages
        patterns = [
            r'Scheduler: Sending due task [\w-]+ \([\w.]+\)',
            r'Task [\w.]+\[[\w-]+\] received',
            r'Task [\w.]+\[[\w-]+\] succeeded',
            r'Connected to redis://[\w.:/@]+',
            r'consumer: Cannot connect to redis://[\w.:/@]+',
            r'broker_connection_retry.*',
        ]
        
        for pattern in patterns:
            if re.search(pattern, message):
                return pattern
        
        # Fallback: use first 50 chars
        return message[:50]


class SmartLogFilter(logging.Filter):
    """Advanced filter combining multiple filtering strategies."""
    
    def __init__(self, name: str = ""):
        super().__init__(name)
        self.stack_filter = StackTraceFilter()
        self.grouper = LogGrouper()
        self._suppressed_patterns = {
            # Celery deprecation warnings
            r'CPendingDeprecationWarning.*broker_connection_retry',
            r'.*Monkey-patching ssl after ssl.*',
            r'.*The broker_connection_retry configuration setting.*',
            # Redis connection spam  
            r'Connection closed by server\.',
            r'Error \d+ connecting to localhost:\d+\.',
            r'Redis is loading the dataset in memory\.',
            # High-frequency polling endpoints (suppress completely)
            r'GET /api/health HTTP',
            r'GET /automation/api/pipeline/[^/]+/status HTTP',
            r'GET /automation/api/pipeline/[^/]+/detailed-status HTTP',
            r'GET /automation/fragments/status HTTP',
            # Pipeline executor debug spam
            r'\[PIPELINE:[^:]+:DEBUG\]',
            r'\[[a-z0-9_]+:DEBUG\]',  # All DEBUG context prefixes
            # Security scanner probe patterns (404s for admin paths, .asp/.aspx files)
            r'HEAD /.*\.(asp|aspx|php|cgi|jsp|cfm)\s',
            r'HEAD /(admin|administrator|wp-admin|phpmyadmin|login|cpanel)',
            r'POST /\d+ HTTP',  # Random numeric POST probes
            # Static file requests (reduce noise)
            r'GET /static/.*\.(css|js|png|jpg|jpeg|gif|ico|woff|woff2|ttf|svg) HTTP',
            r'"GET /static/.*" 200',
            r'"GET /static/.*" 304',
            # Werkzeug request logging patterns for common non-essential requests
            r'127\.0\.0\.1 - - \[.*\] "GET /static/',
            r'127\.0\.0\.1 - - \[.*\] "GET /favicon',
            r'127\.0\.0\.1 - - \[.*\] "GET /api/health',
            # Socket.IO/WebSocket noise
            r'socket\.io.*polling',
            r'GET /socket\.io/.*polling',
        }
        
        self._rate_limited_messages = {}
        self._rate_limit_window = 300  # 5 minutes
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Apply comprehensive filtering."""
        # Defensive: record.msg may contain formatting placeholders with mismatched args.
        message = _safe_get_message(record)

        # Always allow malformed format records (we want visibility + tests rely on presence)
        if getattr(record, "_malformed_format", False):
            return True
        
        # 1. Suppress known spam patterns
        for pattern in self._suppressed_patterns:
            if re.search(pattern, message):
                return False
        
        # 2. Apply stack trace filtering
        if not self.stack_filter.filter(record):
            return False
        
        # 3. Apply grouping
        should_log, grouped_message = self.grouper.should_log_message(record)
        if not should_log:
            return False
        elif grouped_message:
            record.msg = grouped_message
        
        # 4. Rate limit specific message types
        if self._is_rate_limited_message(record):
            return self._should_allow_rate_limited(record)
            
        return True
    
    def _is_rate_limited_message(self, record: logging.LogRecord) -> bool:
        """Check if message should be rate limited."""
        message = _safe_get_message(record).lower()
        rate_limited_keywords = [
            'scheduler: sending due task',
            'mingle: searching for neighbors',
            'mingle: all alone',
            'background saving',
        ]
        return any(keyword in message for keyword in rate_limited_keywords)
    
    def _should_allow_rate_limited(self, record: logging.LogRecord) -> bool:
        """Rate limit repetitive messages."""
        # Use safe message retrieval to avoid TypeError
        message_key = f"{record.name}:{_safe_get_message(record)[:50]}"
        current_time = datetime.now().timestamp()

        if message_key in self._rate_limited_messages:
            last_time = self._rate_limited_messages[message_key]
            if current_time - last_time < self._rate_limit_window:
                return False

        self._rate_limited_messages[message_key] = current_time
        return True


class ColoredSmartFormatter(logging.Formatter):
    """Enhanced formatter with color coding and smart contextual information."""
    
    def __init__(self, include_function: bool = False, use_colors: bool = True):
        self.include_function = include_function
        self.use_colors = use_colors and COLORS_AVAILABLE
        super().__init__()
        
        # Define color schemes for different log levels
        self.level_colors = {
            logging.DEBUG: Fore.CYAN,
            logging.INFO: Fore.GREEN,
            logging.WARNING: Fore.YELLOW,
            logging.ERROR: Fore.RED,
            logging.CRITICAL: Fore.RED + Style.BRIGHT
        }
        
        # Define color schemes for different services
        self.service_colors = {
            'factory': Fore.BLUE,
            'task_service': Fore.MAGENTA,
            'analyzer': Fore.CYAN,
            'celery': Fore.YELLOW,
            'redis': Fore.RED,
            'websocket': Fore.GREEN,
            'security': Fore.MAGENTA,
        }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with color coding and smart contextual information."""
        # Base format with defensive message retrieval
        timestamp = self.formatTime(record, '%H:%M:%S')
        level = record.levelname
        name = self._clean_logger_name(record.name)
        # Always retrieve the message defensively (normalizes mismatched args)
        message = _safe_get_message(record)
        
        # Apply colors if enabled
        if self.use_colors:
            level_color = self.level_colors.get(record.levelno, "")
            service_color = self._get_service_color(name)
            
            # Color the level
            colored_level = f"{level_color}{level:8}{Style.RESET_ALL}"
            
            # Color the service name
            colored_name = f"{service_color}{name:20}{Style.RESET_ALL}"
            
            # Add special formatting for grouped messages
            if message.startswith('[GROUPED]'):
                message = f"{Fore.BLUE}{Style.BRIGHT}{message}{Style.RESET_ALL}"
            elif 'repeated' in message and 'stack trace suppressed' in message:
                message = f"{Fore.YELLOW}{message}{Style.RESET_ALL}"
        else:
            colored_level = f"{level:8}"
            colored_name = f"{name:20}"
        
        # Add function info for errors and warnings in development
        if self.include_function and record.levelno >= logging.WARNING:
            location = f"{record.funcName}:{record.lineno}"
            if self.use_colors:
                location = f"{Fore.WHITE}{Style.DIM}[{location}]{Style.RESET_ALL}"
            else:
                location = f"[{location}]"
            return f"[{timestamp}] {colored_level} {colored_name} {location} {message}"
        else:
            return f"[{timestamp}] {colored_level} {colored_name} {message}"
    
    def _clean_logger_name(self, name: str) -> str:
        """Clean and shorten logger names for readability."""
        # Shorten common long names
        replacements = {
            'ThesisApp.': '',
            'app.services.': 'svc.',
            'app.routes.': 'route.',
            'app.utils.': 'util.',
            'analyzer.services.': 'analyzer.',
            'analyzer.websocket_gateway': 'analyzer.ws',
            'celery.worker.': 'celery.',
            'celery.app.': 'celery.',
        }
        
        for old, new in replacements.items():
            if name.startswith(old):
                name = new + name[len(old):]
                break
        
        # Truncate if still too long
        if len(name) > 20:
            name = name[:17] + "..."
            
        return name
    
    def _get_service_color(self, service_name: str) -> str:
        """Get color for service based on name patterns."""
        if not self.use_colors:
            return ""
            
        name_lower = service_name.lower()
        for service, color in self.service_colors.items():
            if service in name_lower:
                return color
        
        # Default color for unknown services
        return Fore.WHITE


class LoggingConfig:
    """Centralized logging configuration for the application."""
    
    def __init__(self, app_name: str = "ThesisApp"):
        self.app_name = app_name
        self.log_dir = Path(__file__).parent.parent.parent.parent / "logs"
        self.log_dir.mkdir(exist_ok=True)
        
        # Get log level from environment
        self.log_level = self._get_log_level()
        self.is_development = os.environ.get('FLASK_ENV', 'development') == 'development'
        
        # Configure Python warnings
        self._configure_warnings()
    
    def setup_logging(self) -> logging.Logger:
        """Setup centralized logging configuration."""
        
        # Get root logger. IMPORTANT: Do NOT blindly clear all handlers because
        # pytest's caplog installs a capturing handler before tests run. If we
        # clear it, tests that assert on log content (e.g. malformed format
        # normalization) will see empty results. Instead only remove handlers
        # we previously attached (marked with _thesis_app flag). This makes
        # setup idempotent while remaining test-friendly.
        root_logger = logging.getLogger()
        preserved_handlers = []
        for h in list(root_logger.handlers):
            if getattr(h, "_thesis_app", False):
                root_logger.removeHandler(h)
            else:
                preserved_handlers.append(h)
        root_logger.setLevel(self.log_level)
        # Ensure a root safety filter is present exactly once
        # Install safe record factory (idempotent)
        _install_safe_record_factory()
        # Attach sanitizer filter once
        if not any(isinstance(f, MalformedFormatSanitizerFilter) for f in root_logger.filters):
            root_logger.addFilter(MalformedFormatSanitizerFilter())

        # Previous v1/v2 factories replaced by subclass-based factory v3 above.
        
        # Create formatters
        console_formatter = ColoredSmartFormatter(
            include_function=self.is_development,
            use_colors=True
        )
        file_formatter = ColoredSmartFormatter(
            include_function=True,
            use_colors=False  # No colors in log files
        )
        
        # Custom filter to inject request_id if available
        class RequestIdFilter(logging.Filter):  # pragma: no cover - contextual
            def filter(self, record: logging.LogRecord) -> bool:
                try:
                    from flask import g  # type: ignore
                    rid = getattr(g, 'request_id', None)
                    if rid and not hasattr(record, 'request_id'):
                        record.request_id = rid  # type: ignore[attr-defined]
                except Exception:
                    pass
                return True

        req_filter = RequestIdFilter()

        # Setup console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(SmartLogFilter())
        console_handler.addFilter(req_filter)
        console_handler._thesis_app = True  # type: ignore[attr-defined]
        
        # Setup file handler with rotation
        log_file = self.log_dir / "app.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(req_filter)
        file_handler._thesis_app = True  # type: ignore[attr-defined]
        
        # Add handlers to root logger
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        
        # Configure specific loggers
        self._configure_specific_loggers()
        
        # Get application logger
        app_logger = logging.getLogger(self.app_name)
        # Ensure we are using ThesisLogger (tests may have created earlier instance)
        if not isinstance(app_logger, ThesisLogger):  # pragma: no cover - exercised in tests
            try:
                logging.Logger.manager.loggerDict.pop(self.app_name, None)  # type: ignore[attr-defined]
            except Exception:
                pass
            app_logger = logging.getLogger(self.app_name)

        # Attach sanitizer filter directly to app logger so its Logger.filter
        # executes prior to handler formatting (root-level filters do NOT run
        # for child loggers before formatting).
        if not any(isinstance(f, MalformedFormatSanitizerFilter) for f in app_logger.filters):
            app_logger.addFilter(MalformedFormatSanitizerFilter())

        # Final safety: wrap current factory so every created record is sanitized
        # even if earlier mechanisms were bypassed by third-parties.
        if not getattr(logging, "_thesis_final_factory", False):
            base_factory = logging.getLogRecordFactory()
            def _final_factory(*a, **kw):  # pragma: no cover - indirect
                rec = base_factory(*a, **kw)
                if rec.args:
                    try:
                        rec.msg % rec.args  # type: ignore[operator]
                    except TypeError:
                        try:
                            rec.msg = str(rec.msg)
                        except Exception:
                            rec.msg = '<unprintable log message>'
                        rec.args = ()
                        setattr(rec, '_malformed_format', True)
                return rec
            logging.setLogRecordFactory(_final_factory)
            setattr(logging, "_thesis_final_factory", True)
        app_logger.info(f"Logging configured - Level: {logging.getLevelName(self.log_level)}")
        
        return app_logger
    
    def _get_log_level(self) -> int:
        """Get log level from environment or default."""
        level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
        return getattr(logging, level_str, logging.INFO)
    
    def _configure_warnings(self):
        """Configure Python warnings to reduce noise."""
        
        # Filter out common warnings that create spam
        warnings.filterwarnings('ignore', category=DeprecationWarning, module='celery')
        warnings.filterwarnings('ignore', message='.*broker_connection_retry.*')
        warnings.filterwarnings('ignore', message='.*CPendingDeprecationWarning.*')

        # Suppress known upcoming websockets deprecations (until library upgrade)
        warnings.filterwarnings('ignore', category=DeprecationWarning, message=r'websockets\.legacy.*')
        warnings.filterwarnings('ignore', category=DeprecationWarning, message=r'websockets\.exceptions\.InvalidStatusCode.*')
        warnings.filterwarnings('ignore', category=DeprecationWarning, message=r'websockets\.WebSocketServerProtocol.*')

        # Redirect warnings to logging
        logging.captureWarnings(True)
        
        # Reduce warnings logger level
        warnings_logger = logging.getLogger('py.warnings')
        warnings_logger.setLevel(logging.ERROR)
    
    def _configure_specific_loggers(self):
        """Configure specific loggers to reduce spam."""
        
        # Celery loggers - reduce verbosity
        celery_loggers = [
            'celery.worker.strategy',
            'celery.worker.consumer',
            'celery.worker.heartbeat',
            'celery.worker.control',
            'celery.app.trace',
            'celery.task',
            'celery.beat',
        ]
        
        for logger_name in celery_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.WARNING)
        
        # Flask and Werkzeug - reduce verbosity in production
        if not self.is_development:
            logging.getLogger('werkzeug').setLevel(logging.WARNING)
            logging.getLogger('flask.app').setLevel(logging.WARNING)
        
        # SQLAlchemy - reduce verbosity
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
        
        # WebSocket and analyzer services
        logging.getLogger('analyzer.websocket_gateway').setLevel(logging.INFO)
        logging.getLogger('app.services.analyzer_integration').setLevel(logging.INFO)
        
        # Add filters to werkzeug to suppress high-frequency polling and scanner probes
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.addFilter(WerkzeugEndpointFilter())
        werkzeug_logger.addFilter(SecurityScannerProbeFilter())
    
    def create_service_logger(self, service_name: str) -> logging.Logger:
        """Create a logger for a specific service."""
        logger_name = f"{self.app_name}.{service_name}"
        return logging.getLogger(logger_name)
    
    def cleanup_old_logs(self, days_to_keep: int = 7):
        """Clean up old log files."""
        if not self.log_dir.exists():
            return
            
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 3600)
        
        for log_file in self.log_dir.glob("*.log*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
            except Exception:
                pass  # Ignore errors during cleanup


# Global instance
_logging_config = None


def get_logging_config() -> LoggingConfig:
    """Get the global logging configuration instance."""
    global _logging_config
    if _logging_config is None:
        _logging_config = LoggingConfig()
    return _logging_config


def setup_application_logging() -> logging.Logger:
    """Setup application logging - call this once at startup."""
    config = get_logging_config()
    return config.setup_logging()


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(f"ThesisApp.{name}")


def reduce_monitoring_spam():
    """Apply additional filters to reduce monitoring-related spam."""
    
    # Add filters to existing handlers
    # (Currently a placeholder - real filters may be added later.)
    for handler in logging.getLogger().handlers:
        pass
