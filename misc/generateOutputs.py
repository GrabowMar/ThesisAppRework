#!/usr/bin/env python3
"""
Combined OpenRouter Code Generator & Extractor

This application provides a GUI for generating and extracting application code using
the OpenRouter API. It supports multiple AI models, template-based generation,
automatic code extraction, and file organization.

Key Features:
- Multi-model code generation with OpenRouter API
- Template-based application scaffolding
- Automatic code block extraction and file organization
- Port configuration management
- Comprehensive logging and statistics
- GUI interface with progress tracking

Version: 2.0 - Improved and refactored
"""

# Standard library imports (alphabetical order)
import hashlib
import json
import logging
import os
import random
import re
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Third-party imports (alphabetical order)
import requests
import tkinter as tk
from dotenv import load_dotenv
from tkinter import filedialog, font, messagebox, scrolledtext, ttk

# Load environment variables at module level
load_dotenv()

# =============================================================================
# Application Constants and Configuration
# =============================================================================

class AppConfig:
    """
    Centralized application configuration containing all constants and settings.
    
    This class serves as a single source of truth for application-wide
    configuration values including UI settings, logging parameters, API
    configuration, and processing limits.
    """
    
    # UI Configuration
    WINDOW_TITLE = "OpenRouter Code Generator & Extractor - Combined"
    WINDOW_SIZE = "1600x900"
    DEFAULT_LOG_FILE = f"combined_app_{datetime.now().strftime('%Y%m%d')}.log"
    MAX_RECENT_FILES = 10
    
    # Logging Configuration
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    
    # Code Processing
    MIN_CODE_BLOCK_SIZE = 20
    
    # API Retry Configuration
    MAX_RETRIES = 2
    RETRY_DELAYS = [10, 30]
    TIMEOUT_FALLBACK = [300, 600]
    EXPONENTIAL_BACKOFF = True
    MAX_BACKOFF_DELAY = 300
    
    # Parallel Processing Configuration
    MAX_PARALLEL_REQUESTS = 3  # Default number of parallel API requests
    MIN_PARALLEL_REQUESTS = 1
    MAX_PARALLEL_REQUESTS_LIMIT = 8  # Hard limit to prevent API abuse
    
    # Files to exclude from port replacement (frozen set for immutability)
    SKIP_PORT_REPLACEMENT = frozenset([
        "package.json", "package-lock.json", "yarn.lock",
        ".env", ".env.example", ".gitignore", "README.md",
        "tsconfig.json", "jsconfig.json", ".eslintrc.js",
        "babel.config.js", ".prettierrc", "requirements.txt"
    ])
    
    # Default API values
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 12000
    DEFAULT_SYSTEM_PROMPT = (
        "You are an expert full-stack developer. Generate comprehensive markdown "
        "documentation with clean, production-ready code. Include detailed explanations, "
        "setup instructions, and all necessary files."
    )

# =============================================================================
# Core Data Classes
# =============================================================================

# =============================================================================
# Core Data Classes
# =============================================================================

@dataclass
class GenerationTask:
    """
    Individual generation task for parallel processing.
    
    Represents a single unit of work for generating either frontend or backend
    code for an application template using a specific AI model.
    
    Attributes:
        template: The application template to generate code for
        model: The AI model identifier to use for generation
        is_frontend: True for frontend generation, False for backend
        task_id: Unique identifier for this task
    """
    template: 'AppTemplate'
    model: str
    is_frontend: bool
    task_id: str
    
    @property
    def task_type(self) -> str:
        """Return human-readable task type."""
        return "frontend" if self.is_frontend else "backend"


@dataclass
class GenerationConfig:
    """
    Configuration settings for code generation operations.
    
    Contains all parameters needed to control how code generation is performed,
    including model settings, token limits, and complexity adjustments.
    
    Attributes:
        models: List of AI model identifiers to use
        temperature: Randomness in generation (0.0 to 1.0)
        max_tokens: Maximum tokens per generation request
        system_prompt: System prompt to guide model behavior
        save_raw_markdown: Whether to save raw markdown responses
        save_json_export: Whether to save JSON export of responses
        auto_adjust_for_complexity: Whether to auto-adjust settings based on app complexity
    """
    models: List[str]
    temperature: float = AppConfig.DEFAULT_TEMPERATURE
    max_tokens: int = AppConfig.DEFAULT_MAX_TOKENS
    system_prompt: str = AppConfig.DEFAULT_SYSTEM_PROMPT
    save_raw_markdown: bool = True
    save_json_export: bool = True
    auto_adjust_for_complexity: bool = True
    
    def get_adjusted_config(
        self, 
        app_name: str, 
        requirements: List[str]
    ) -> 'GenerationConfig':
        """
        Create an adjusted configuration based on application complexity.
        
        Analyzes the application name and requirements to determine complexity
        and adjusts generation parameters accordingly.
        
        Args:
            app_name: Name of the application to generate
            requirements: List of application requirements
            
        Returns:
            New GenerationConfig with adjusted parameters
        """
        if not self.auto_adjust_for_complexity:
            return self
        
        complexity_score = self._assess_app_complexity(app_name, requirements)
        
        adjusted_config = GenerationConfig(
            models=self.models[:],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            system_prompt=self.system_prompt,
            save_raw_markdown=self.save_raw_markdown,
            save_json_export=self.save_json_export,
            auto_adjust_for_complexity=False
        )
        
        # Adjust parameters based on complexity score
        if complexity_score > 0.7:
            # High complexity applications
            adjusted_config.max_tokens = min(16000, int(self.max_tokens * 1.5))
            adjusted_config.temperature = max(0.5, self.temperature - 0.1)
            adjusted_config.system_prompt += (
                " This is a complex application with many features - ensure "
                "comprehensive implementation with detailed error handling."
            )
        elif complexity_score > 0.4:
            # Medium complexity applications
            adjusted_config.max_tokens = min(14000, int(self.max_tokens * 1.2))
            adjusted_config.system_prompt += (
                " Include proper error handling and user feedback."
            )
        
        return adjusted_config
    
    def _assess_app_complexity(
        self, 
        app_name: str, 
        requirements: List[str]
    ) -> float:
        """
        Assess application complexity on a scale from 0.0 to 1.0.
        
        Uses keyword analysis and requirement count to determine
        how complex an application is likely to be.
        
        Args:
            app_name: Name of the application
            requirements: List of application requirements
            
        Returns:
            Complexity score between 0.0 (simple) and 1.0 (very complex)
        """
        score = 0.0
        
        # Keywords that indicate complex applications
        complex_keywords = [
            'management', 'dashboard', 'analytics', 'platform', 'system',
            'enterprise', 'collaboration', 'marketplace', 'social', 'workflow'
        ]
        
        # Score based on complex keywords in app name
        app_name_lower = app_name.lower()
        for keyword in complex_keywords:
            if keyword in app_name_lower:
                score += 0.2
        
        # Score based on requirements if provided
        if requirements:
            complex_features = [
                'authentication', 'database', 'api', 'payment', 'real-time',
                'notification', 'upload', 'search', 'admin', 'analytics'
            ]
            requirements_text = ' '.join(requirements).lower()
            
            # Count complex feature matches
            feature_matches = sum(
                1 for feature in complex_features 
                if feature in requirements_text
            )
            score += min(0.5, feature_matches * 0.05)
            
            # Score based on number of requirements
            score += min(0.3, len(requirements) * 0.02)
        
        return min(1.0, score)  # Cap at 1.0

@dataclass
class AppTemplate:
    """
    Application template with frontend and backend components.
    
    Represents a template for generating both frontend and backend code
    for a specific type of application.
    
    Attributes:
        app_num: Unique application number
        name: Human-readable application name
        frontend_template: Template content for frontend generation
        backend_template: Template content for backend generation
        requirements: List of application requirements/features
        frontend_file: Optional path to frontend template file
        backend_file: Optional path to backend template file
    """
    app_num: int
    name: str
    frontend_template: str
    backend_template: str
    requirements: List[str]
    frontend_file: Optional[Path] = None
    backend_file: Optional[Path] = None


@dataclass
class ModelInfo:
    """
    Information about an AI model.
    
    Contains metadata about an AI model including its capabilities,
    provider information, and usage characteristics.
    
    Attributes:
        raw_slug: Original model identifier from API
        standardized_name: Normalized name for internal use
        provider: Model provider (e.g., openai, anthropic)
        model_family: Model family/series (e.g., gpt-4, claude)
        variant: Model variant (standard, free, etc.)
        is_free: Whether the model is free to use
        capabilities: Set of model capabilities
        description: Human-readable model description
    """
    raw_slug: str
    standardized_name: str
    provider: str
    model_family: str
    variant: str = "standard"
    is_free: bool = False
    capabilities: Set[str] = field(default_factory=set)
    description: str = ""

@dataclass
class CodeBlock:
    """
    Extracted code block with metadata and port management.
    
    Represents a single extracted code block from AI-generated content,
    including information about the code type, ports, and processing status.
    
    Attributes:
        language: Programming language of the code
        code: The actual code content
        file_type: Detected file type (e.g., "backend/app.py")
        model_info: Information about the AI model that generated this code
        app_num: Application number this code belongs to
        message_id: Unique identifier for the source message
        backend_port: Assigned backend port number
        frontend_port: Assigned frontend port number
        detected_backend_ports: Ports detected in backend code
        detected_frontend_ports: Ports detected in frontend code
        line_count: Number of lines in the code (computed)
        checksum: MD5 checksum of the code (computed)
        selected_for_save: Whether this block is selected for saving
        original_code: Original code before port replacements (computed)
        extraction_issues: List of issues found during extraction
        port_replacements: Dictionary of port replacements made
        file_index: Index for handling multiple files of same type
        is_main_component: Whether this is the main JSX component
        html_compatibility_score: JSX-HTML compatibility score
    """
    # Core attributes
    language: str
    code: str
    file_type: Optional[str]
    model_info: ModelInfo
    app_num: int
    message_id: str
    
    # Port management
    backend_port: Optional[int] = None
    frontend_port: Optional[int] = None
    detected_backend_ports: List[int] = field(default_factory=list)
    detected_frontend_ports: List[int] = field(default_factory=list)
    
    # Computed attributes (set in __post_init__)
    line_count: int = field(init=False)
    checksum: str = field(init=False)
    original_code: str = field(init=False)
    
    # Processing metadata
    selected_for_save: bool = True
    extraction_issues: List[str] = field(default_factory=list)
    port_replacements: Dict[str, str] = field(default_factory=dict)
    
    # File handling
    file_index: int = 0  # For handling multiple files of same type
    is_main_component: bool = False  # For JSX components
    html_compatibility_score: float = 0.0  # For JSX-HTML compatibility
    
    def __post_init__(self):
        """Initialize computed fields after object creation."""
        self.line_count = len(self.code.splitlines())
        self.checksum = hashlib.md5(self.code.encode()).hexdigest()[:8]
        self.original_code = self.code
        self._detect_ports_in_code()
    
    def _detect_ports_in_code(self):
        """
        Detect backend and frontend ports mentioned in the code.
        
        Uses regex patterns to find port numbers that are likely to be
        backend ports (5xxx) or frontend ports (3xxx, 8xxx).
        """
        # Backend ports typically in 5000-5999 range
        backend_pattern = r'\b(5\d{3})\b'
        self.detected_backend_ports = sorted(set(
            int(port) for port in re.findall(backend_pattern, self.code)
        ))
        
        # Frontend ports typically in 3000-3999 or 8000-8999 range
        frontend_pattern = r'\b([38]\d{3})\b'
        self.detected_frontend_ports = sorted(set(
            int(port) for port in re.findall(frontend_pattern, self.code)
        ))
    
    def get_replaced_code(self) -> str:
        """
        Get code with detected ports replaced with assigned ports.
        
        Replaces any detected ports in the code with the assigned ports
        for this application, while avoiding replacement in certain file types
        that should not be modified (e.g., package.json, README.md).
        
        Returns:
            Code with port numbers replaced as appropriate
        """
        # Skip port replacement for certain file types
        if (self.file_type and 
            any(skip_pattern in self.file_type 
                for skip_pattern in AppConfig.SKIP_PORT_REPLACEMENT)):
            return self.code
        
        modified_code = self.code
        self.port_replacements.clear()
        
        # Replace backend ports
        if self.backend_port and self.detected_backend_ports:
            for detected_port in self.detected_backend_ports:
                if detected_port != self.backend_port:
                    old_port_str = str(detected_port)
                    new_port_str = str(self.backend_port)
                    port_pattern = r'\b' + old_port_str + r'\b'
                    
                    if re.search(port_pattern, modified_code):
                        modified_code = re.sub(port_pattern, new_port_str, modified_code)
                        self.port_replacements[f"backend_{old_port_str}"] = new_port_str
        
        # Replace frontend ports
        if self.frontend_port and self.detected_frontend_ports:
            for detected_port in self.detected_frontend_ports:
                if detected_port != self.frontend_port:
                    old_port_str = str(detected_port)
                    new_port_str = str(self.frontend_port)
                    port_pattern = r'\b' + old_port_str + r'\b'
                    
                    if re.search(port_pattern, modified_code):
                        modified_code = re.sub(port_pattern, new_port_str, modified_code)
                        self.port_replacements[f"frontend_{old_port_str}"] = new_port_str
        
        return modified_code

@dataclass
class GenerationResult:
    """
    Result of a code generation operation.
    
    Contains the complete results from generating code for a single application,
    including both frontend and backend components, success status, and
    any extracted code blocks.
    
    Attributes:
        app_num: Application number that was generated
        app_name: Human-readable application name
        model: AI model used for generation
        frontend_markdown: Generated frontend markdown content
        backend_markdown: Generated backend markdown content
        requirements: List of application requirements used
        frontend_success: Whether frontend generation succeeded
        backend_success: Whether backend generation succeeded
        timestamp: When the generation was completed
        extracted_blocks: List of code blocks extracted from the results
    """
    app_num: int
    app_name: str
    model: str
    frontend_markdown: str
    backend_markdown: str
    requirements: List[str]
    frontend_success: bool
    backend_success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    extracted_blocks: List[CodeBlock] = field(default_factory=list)


@dataclass
class APICallStats:
    """
    Statistics for API calls made during code generation.
    
    Tracks detailed information about API calls including timing,
    retry attempts, error messages, and response data for debugging
    and performance monitoring.
    
    Attributes:
        model: AI model used for the API call
        app_name: Application name being generated
        call_type: Type of API call (e.g., 'frontend', 'backend')
        attempts: Number of attempts made
        success: Whether the final attempt succeeded
        total_duration: Total time taken for all attempts
        error_messages: List of error messages encountered
        raw_response: Raw API response data
        final_content: Final content received from API
        timestamp: When the API call was made
        retry_delays: List of delays between retry attempts
        timeout_used: Timeout value used for the request
    """
    model: str
    app_name: str
    call_type: str
    attempts: int = 0
    success: bool = False
    total_duration: float = 0.0
    error_messages: List[str] = field(default_factory=list)
    raw_response: Optional[Dict] = None
    final_content: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    retry_delays: List[float] = field(default_factory=list)
    timeout_used: int = 180

# =============================================================================
# Logging Configuration
# =============================================================================

class LoggerSetup:
    """
    Handles logging configuration for the application.
    
    Provides centralized logging setup with file rotation, console output,
    and special handling for Unicode characters and emojis on Windows.
    """
    
    @staticmethod
    def setup() -> logging.Logger:
        """
        Setup application logging with file and console handlers.
        
        Creates a logger with rotating file handler and console handler,
        with special formatting to handle Unicode characters safely on Windows.
        
        Returns:
            Configured logger instance
        """
        logger = logging.getLogger("CombinedApp")
        logger.setLevel(logging.INFO)
        
        # Clear any existing handlers to avoid duplicates
        if logger.hasHandlers():
            logger.handlers.clear()
        
        # Create formatters with safe Unicode handling
        file_formatter = LoggerSetup.SafeFormatter(
            '[%(asctime)s] %(levelname)s [%(funcName)s:%(lineno)d]: %(message)s'
        )
        console_formatter = LoggerSetup.SafeFormatter('[%(levelname)s] %(message)s')
        
        # Setup file handler with rotation
        try:
            file_handler = RotatingFileHandler(
                AppConfig.DEFAULT_LOG_FILE,
                maxBytes=AppConfig.LOG_MAX_BYTES,
                backupCount=AppConfig.LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as error:
            print(f"Warning: Could not create log file: {error}")

        # Setup console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    class SafeFormatter(logging.Formatter):
        """
        Custom formatter that handles Unicode safely for Windows compatibility.
        
        Replaces emoji characters with text equivalents to ensure log messages
        display correctly on all platforms.
        """
        
        # Mapping of emojis to text equivalents
        EMOJI_REPLACEMENTS = {
            '💾': '[SAVE]', '✅': '[OK]', '❌': '[ERROR]',
            '🚀': '[START]', '⏹️': '[STOP]', '📊': '[STATS]',
            '🔄': '[REFRESH]', '📁': '[FOLDER]', '📄': '[FILE]',
            '🤖': '[MODEL]', '⚡': '[FAST]', '🎯': '[TARGET]',
            '⏳': '[WAIT]', '🔍': '[SEARCH]', '📝': '[NOTE]'
        }
        
        def format(self, record):
            """
            Format log record with safe Unicode handling.
            
            Args:
                record: LogRecord to format
                
            Returns:
                Formatted log message with emojis replaced
            """
            formatted_message = super().format(record)
            
            # Replace emojis with text for Windows compatibility
            for emoji, replacement in self.EMOJI_REPLACEMENTS.items():
                formatted_message = formatted_message.replace(emoji, replacement)
            
            return formatted_message


# Initialize global logger
logger = LoggerSetup.setup()

# =============================================================================
# Model Detection and Management
# =============================================================================

class ModelDetector:
    """
    Handles AI model detection, analysis, and standardization.
    
    Provides functionality to parse model identifiers, extract provider
    information, detect capabilities, and create standardized model
    information objects.
    """
    
    @staticmethod
    def standardize_model_name(model_slug: str) -> str:
        """
        Convert model slug to standardized internal name.
        
        Removes the ':free' suffix and converts slashes to underscores
        to create a consistent internal identifier.
        
        Args:
            model_slug: Original model slug from API (e.g., 'openai/gpt-4:free')
            
        Returns:
            Standardized model name (e.g., 'openai_gpt-4')
        """
        clean_slug = model_slug.replace(':free', '')
        return clean_slug.replace('/', '_')
    
    @staticmethod
    def extract_provider(model_slug: str) -> str:
        """
        Extract provider name from model slug.
        
        Extracts the provider portion from a model slug, which is typically
        the part before the first forward slash.
        
        Args:
            model_slug: Model slug (e.g., 'anthropic/claude-3-opus')
            
        Returns:
            Provider name (e.g., 'anthropic') or 'unknown' if not found
        """
        clean_slug = model_slug.replace(':free', '')
        return clean_slug.split('/')[0] if '/' in clean_slug else 'unknown'
    
    @staticmethod
    def detect_model_capabilities(model_info_dict: Dict) -> Set[str]:
        """
        Detect model capabilities from model information dictionary.
        
        Analyzes the model description and metadata to determine what
        capabilities the model has (e.g., reasoning, vision, coding).
        
        Args:
            model_info_dict: Dictionary containing model metadata
            
        Returns:
            Set of capability strings
        """
        capabilities = set()
        
        if not model_info_dict:
            return capabilities
        
        description = (model_info_dict.get('description', '') or '').lower()
        
        # Map of capabilities to their identifying keywords
        capability_keywords = {
            'reasoning': ['reasoning', 'think', 'chain-of-thought'],
            'vision': ['vision', 'image', 'multimodal'],
            'coding': ['code', 'coding', 'programming'],
            'long_context': ['long context', 'extended context', '1m', 'million token']
        }
        
        # Check description for capability keywords
        for capability, keywords in capability_keywords.items():
            if any(keyword in description for keyword in keywords):
                capabilities.add(capability)
        
        # Check for reasoning configuration
        if model_info_dict.get('reasoning_config'):
            capabilities.add('reasoning')
        
        # Check context length for long context capability
        context_length = model_info_dict.get('context_length', 0) or 0
        if context_length > 100000:  # 100k+ tokens considered long context
            capabilities.add('long_context')
        
        return capabilities
    
    @staticmethod
    def analyze_model(character_id: str, character_data: Dict) -> ModelInfo:
        """
        Analyze model information from character data.
        
        Creates a comprehensive ModelInfo object by parsing the character
        data and extracting all relevant model information.
        
        Args:
            character_id: Unique character identifier
            character_data: Dictionary containing character/model data
            
        Returns:
            ModelInfo object with parsed model information
        """
        model_slug = character_data.get('model', 'unknown')
        model_info_dict = character_data.get('modelInfo', {})
        
        # Extract basic information
        standardized_name = ModelDetector.standardize_model_name(model_slug)
        provider = ModelDetector.extract_provider(model_slug)
        capabilities = ModelDetector.detect_model_capabilities(model_info_dict)
        
        # Determine variant and pricing
        variant = "free" if ':free' in model_slug else "standard"
        is_free = ':free' in model_slug
        
        # Extract model family
        model_family = 'unknown'
        if '_' in standardized_name:
            # Extract family from standardized name (e.g., 'gpt-4' from 'openai_gpt-4')
            family_part = standardized_name.split('_')[1].split('-')[0]
            model_family = family_part
        
        return ModelInfo(
            raw_slug=model_slug,
            standardized_name=standardized_name,
            provider=provider,
            model_family=model_family,
            variant=variant,
            is_free=is_free,
            capabilities=capabilities,
            description=model_info_dict.get('description', '')
        )

# =============================================================================
# Port Configuration Management
# =============================================================================

class PortManager:
    """
    Manages port configuration for different models and applications.
    
    Handles loading, caching, and retrieval of port configurations that
    specify which backend and frontend ports should be used for each
    model/application combination.
    
    Attributes:
        config_file: Path to the port configuration JSON file
        port_configs: List of loaded port configuration dictionaries
    """
    
    def __init__(self, config_file: Path):
        """
        Initialize PortManager with configuration file.
        
        Args:
            config_file: Path to the JSON file containing port configurations
        """
        self.config_file = config_file
        self.port_configs: List[Dict] = []
        self._load_port_config()
    
    def _load_port_config(self):
        """
        Load port configuration from the JSON file.
        
        Attempts to read and parse the port configuration file. If the file
        doesn't exist or has parsing errors, initializes with empty configuration.
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as config_file:
                    self.port_configs = json.load(config_file)
                logger.info(f"Loaded {len(self.port_configs)} port configurations")
            else:
                logger.warning(f"Port config file not found: {self.config_file}")
                self.port_configs = []
        except Exception as error:
            logger.error(f"Error loading port config: {error}")
            self.port_configs = []
    
    def get_ports_for_model_app(
        self, 
        model_name: str, 
        app_number: int
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Get backend and frontend ports for a specific model/app combination.
        
        Searches the loaded port configurations to find matching ports
        for the given model and application number.
        
        Args:
            model_name: Name of the AI model
            app_number: Application number
            
        Returns:
            Tuple of (backend_port, frontend_port), with None if not found
        """
        for port_config in self.port_configs:
            if (port_config.get("model_name") == model_name and 
                port_config.get("app_number") == app_number):
                backend_port = port_config.get("backend_port")
                frontend_port = port_config.get("frontend_port")
                return backend_port, frontend_port
        
        logger.warning(
            f"No port config found for {model_name}/app{app_number}"
        )
        return None, None
    
    def reload_configuration(self):
        """
        Reload port configuration from file.
        
        Useful for picking up changes to the configuration file without
        restarting the application.
        """
        self._load_port_config()

# =============================================================================
# File Pattern Matching and Type Detection
# =============================================================================

class FilePatternMatcher:
    """
    Identifies file types and paths from code content and language.
    
    Provides sophisticated pattern matching to determine appropriate file paths
    and types for generated code blocks based on their content and programming
    language.
    """
    
    @staticmethod
    def identify_file_type(code: str, language: str) -> Optional[str]:
        """
        Identify file type from code content and language.
        
        Determines the appropriate file path and type based on code content
        analysis and language detection.
        
        Args:
            code: The source code content to analyze
            language: Programming language identifier
            
        Returns:
            File path/type string or None if not identifiable
        """
        normalized_language = language.lower()
        
        if normalized_language in ['markdown', 'md']:
            return FilePatternMatcher._identify_markdown_file_type(code)
        
        return FilePatternMatcher._identify_direct_code_file_type(code, normalized_language)
    
    @staticmethod
    def _identify_markdown_file_type(code: str) -> Optional[str]:
        """
        Identify file type from markdown content.
        
        Analyzes markdown code blocks to determine what type of file
        the content represents based on code fences and keywords.
        
        Args:
            code: Markdown content to analyze
            
        Returns:
            Identified file type or None
        """
        # Pattern definitions: (code_fence, required_keywords, file_type)
        markdown_patterns = [
            ('```python', ['from flask import', 'import flask', 'app = Flask'], "backend/app.py"),
            ('```jsx', ['import React', 'from "react"', 'useState'], "frontend/src/App.jsx"),
            ('```javascript', ['import React', 'from "react"', 'useState'], "frontend/src/App.jsx"),
            ('```json', ['dependencies', 'scripts'], "frontend/package.json"),
            ('```css', [], "frontend/src/App.css"),
            ('```html', ['id="root"', 'div id="root"'], "frontend/index.html"),
        ]
        
        # Check each pattern
        for code_fence, required_keywords, file_type in markdown_patterns:
            if code_fence in code:
                # If no keywords required, or any keyword found, match this pattern
                if not required_keywords or any(keyword in code for keyword in required_keywords):
                    return file_type
        
        # Special handling for Docker files
        if '```dockerfile' in code.lower():
            if 'python' in code.lower():
                return "backend/Dockerfile"
            elif 'node' in code.lower():
                return "frontend/Dockerfile"
        
        # Docker Compose files
        if (('```yaml' in code or '```yml' in code) and 
            'services:' in code and 'docker' in code.lower()):
            return "docker-compose.yml"
        
        return None
    
    @staticmethod
    def _identify_direct_code_file_type(code: str, language: str) -> Optional[str]:
        """
        Identify file type from direct code content (non-markdown).
        
        Analyzes code directly without markdown formatting to determine
        the appropriate file type and path.
        
        Args:
            code: Direct code content
            language: Programming language
            
        Returns:
            Identified file type or None
        """
        # Pattern mapping: (language, keywords_tuple) -> file_type
        code_file_patterns = {
            ('python', ('from flask import', 'import flask', 'app = Flask')): "backend/app.py",
            ('jsx', ('import React', 'from "react"', 'useState')): "frontend/src/App.jsx",
            ('javascript', ('import React', 'from "react"', 'useState')): "frontend/src/App.jsx",
            ('javascript', ('defineConfig', 'vite')): "frontend/vite.config.js",
            ('css', ()): "frontend/src/App.css",
            ('html', ('id="root"', 'div id="root"')): "frontend/index.html",
        }
        
        # Check each pattern
        for (lang, required_keywords), file_type in code_file_patterns.items():
            if language == lang:
                # If no keywords required, or any keyword found, match this pattern
                if not required_keywords or any(keyword in code for keyword in required_keywords):
                    return file_type
        
        # Special handling for JSON files
        if language == 'json':
            try:
                json_data = json.loads(code)
                if 'dependencies' in json_data or 'scripts' in json_data:
                    return "frontend/package.json"
            except json.JSONDecodeError:
                pass  # Not valid JSON, continue with other checks
        
        # Docker files (direct Dockerfile content)
        if language == 'dockerfile' or 'FROM' in code[:100]:
            if 'python' in code.lower():
                return "backend/Dockerfile"
            elif 'node' in code.lower():
                return "frontend/Dockerfile"
        
        # Docker Compose files
        if (language in ['yaml', 'yml'] and 
            'services:' in code and 'docker' in code.lower()):
            return "docker-compose.yml"
        
        # Requirements files
        if (language in ['text', 'plaintext'] and 
            FilePatternMatcher._is_python_requirements_file(code)):
            return "backend/requirements.txt"
        
        return None
    
    @staticmethod
    def _is_python_requirements_file(code: str) -> bool:
        """
        Check if text content appears to be a Python requirements.txt file.
        
        Analyzes the structure and content to determine if it matches
        the format of a Python requirements file.
        
        Args:
            code: Text content to analyze
            
        Returns:
            True if content appears to be a requirements.txt file
        """
        lines = code.strip().split('\n')
        if not lines:
            return False
        
        # Check first few lines for requirements.txt patterns
        for line in lines[:5]:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            # Check if line matches requirements.txt format
            requirements_pattern = (
                r'^[a-zA-Z0-9\-_]+(?:\[[^\]]+\])?'  # Package name with optional extras
                r'(?:[=<>~!]=?[\d\w\.\-\+]+)?'      # Optional version specifier
                r'(?:\s*#.*)?$'                     # Optional comment
            )
            
            if not re.match(requirements_pattern, line):
                return False
        
        return True
    
    @staticmethod
    def identify_multiple_files(code: str, language: str, existing_files: Optional[List[str]] = None) -> List[Tuple[str, str, int, bool, float]]:
        """Identify multiple files from code content
        Returns: List of (file_type, code_segment, file_index, is_main, html_compatibility_score)
        """
        if existing_files is None:
            existing_files = []
            
        language = language.lower()
        
        if language in ['jsx', 'javascript', 'js']:
            return FilePatternMatcher._identify_jsx_files(code, existing_files)
        elif language == 'python':
            return FilePatternMatcher._identify_python_files(code, existing_files)
        elif language == 'html':
            return FilePatternMatcher._identify_html_files(code, existing_files)
        else:
            # Single file identification for other languages
            file_type = FilePatternMatcher.identify_file_type(code, language)
            if file_type:
                return [(file_type, code, 0, True, 0.0)]
            return []
    
    @staticmethod
    def _identify_jsx_files(code: str, existing_files: List[str]) -> List[Tuple[str, str, int, bool, float]]:
        """Identify multiple JSX files from code content"""
        files = []
        
        # Look for component patterns
        component_pattern = r'(?:export\s+default\s+function\s+(\w+)|function\s+(\w+)\s*\([^)]*\)\s*{[^}]*return\s*\(|const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*{[^}]*return\s*\()'
        components = re.findall(component_pattern, code, re.DOTALL | re.MULTILINE)
        
        # Extract individual components
        if len(components) > 1:
            # Multiple components detected
            for i, comp_match in enumerate(components):
                comp_name = next((name for name in comp_match if name), f"Component{i+1}")
                
                # Extract the component code
                start_pattern = rf'(?:export\s+default\s+)?(?:function\s+{comp_name}|const\s+{comp_name}\s*=)'
                start_match = re.search(start_pattern, code, re.IGNORECASE)
                
                if start_match:
                    start_pos = start_match.start()
                    
                    # Find the end of this component (simple heuristic)
                    brace_count = 0
                    end_pos = len(code)
                    in_component = False
                    
                    for j, char in enumerate(code[start_pos:], start_pos):
                        if char == '{':
                            brace_count += 1
                            in_component = True
                        elif char == '}':
                            brace_count -= 1
                            if in_component and brace_count == 0:
                                end_pos = j + 1
                                break
                    
                    component_code = code[start_pos:end_pos]
                    
                    # Determine if this is the main component
                    is_main = ('export default' in component_code or 
                              comp_name.lower() in ['app', 'main', 'index'] or
                              i == 0)
                    
                    # Calculate HTML compatibility score
                    html_score = FilePatternMatcher._calculate_html_jsx_compatibility_score(component_code)
                    
                    # Determine file name
                    if is_main:
                        file_type = "frontend/src/App.jsx"
                    else:
                        file_type = f"frontend/src/components/{comp_name}.jsx"
                    
                    files.append((file_type, component_code, i, is_main, html_score))
        else:
            # Single component or no clear components
            is_main = 'App' in code or 'export default' in code
            html_score = FilePatternMatcher._calculate_html_jsx_compatibility_score(code)
            file_type = "frontend/src/App.jsx"
            files.append((file_type, code, 0, is_main, html_score))
        
        return files
    
    @staticmethod
    def _identify_python_files(code: str, existing_files: List[str]) -> List[Tuple[str, str, int, bool, float]]:
        """Identify multiple Python files from code content"""
        files = []
        
        # Look for class definitions and function patterns
        class_pattern = r'class\s+(\w+)'
        classes = re.findall(class_pattern, code)
        
        # Check if it's a Flask app
        if ('from flask import' in code or 'import flask' in code or 
            'app = Flask' in code or '@app.route' in code):
            
            # Multiple route handlers could be separate files
            route_patterns = re.findall(r'@app\.route\([\'"][^\'"]*[\'"][^)]*\)\s*def\s+(\w+)', code, re.MULTILINE)
            
            if len(route_patterns) > 3:  # If many routes, consider splitting
                # Keep main app in app.py
                files.append(("backend/app.py", code, 0, True, 0.0))
                
                # Extract route handlers for separate files (optional enhancement)
                for i, route_func in enumerate(route_patterns[3:], 1):
                    # This is a simplified extraction - in practice, you'd want more sophisticated parsing
                    files.append((f"backend/routes/{route_func}.py", f"# Route handler for {route_func}\n# Extract from main app.py", i, False, 0.0))
            else:
                files.append(("backend/app.py", code, 0, True, 0.0))
        
        elif len(classes) > 1:
            # Multiple classes - could be separate files
            for i, class_name in enumerate(classes):
                # Extract class code (simplified)
                class_pattern = rf'class\s+{class_name}[^:]*:.*?(?=class\s+\w+|$)'
                class_match = re.search(class_pattern, code, re.DOTALL)
                
                if class_match:
                    class_code = class_match.group(0)
                    is_main = i == 0 or class_name.lower() in ['main', 'app']
                    file_type = f"backend/{class_name.lower()}.py" if not is_main else "backend/app.py"
                    files.append((file_type, class_code, i, is_main, 0.0))
        else:
            # Single file
            files.append(("backend/app.py", code, 0, True, 0.0))
        
        return files
    
    @staticmethod
    def _identify_html_files(code: str, existing_files: List[str]) -> List[Tuple[str, str, int, bool, float]]:
        """Identify multiple HTML files from code content"""
        files = []
        
        # Check if it's a main index.html or component template
        is_index = ('id="root"' in code or 'div id="root"' in code or 
                   '<title>' in code or '<!DOCTYPE html>' in code)
        
        if is_index:
            files.append(("frontend/index.html", code, 0, True, 1.0))
        else:
            # Could be a template or partial
            files.append(("frontend/templates/template.html", code, 0, False, 0.8))
        
        return files
    
    @staticmethod
    def _calculate_html_jsx_compatibility_score(jsx_code: str) -> float:
        """
        Calculate compatibility score between JSX and HTML structure.
        
        Analyzes JSX code to determine how well it would translate to
        static HTML, useful for rendering compatibility decisions.
        
        Args:
            jsx_code: JSX code content to analyze
            
        Returns:
            Compatibility score from 0.0 to 1.0
        """
        score = 0.0
        
        # Check for common HTML elements (higher score = more HTML-like)
        html_elements = ['div', 'span', 'p', 'h1', 'h2', 'h3', 'button', 'input', 'form']
        jsx_elements_found = sum(
            1 for element in html_elements 
            if f'<{element}' in jsx_code
        )
        score += (jsx_elements_found / len(html_elements)) * 0.4
        
        # Check for React-specific attributes vs HTML attributes
        if 'className=' in jsx_code:
            score += 0.2  # JSX uses className instead of class
        elif 'class=' in jsx_code:
            score += 0.1  # Less optimal for React but more HTML-like
        
        # Check for React patterns (lower score = less HTML compatibility)
        react_patterns = ['useState', 'useEffect', 'props']
        if any(pattern in jsx_code for pattern in react_patterns):
            score += 0.2
        
        # Check for JSX expressions
        if '{' in jsx_code and '}' in jsx_code:
            score += 0.2
        
        return min(score, 1.0)


# =============================================================================
# Code Extraction and Processing
# =============================================================================

class CodeExtractor:
    """
    Extracts and processes code blocks from markdown content.
    
    Handles parsing of AI-generated markdown responses, extraction of code blocks,
    file type identification, port management, and organization of extracted code
    into structured CodeBlock objects.
    
    Attributes:
        port_manager: Manages port configurations for different models
        model_detector: Handles model analysis and standardization
        file_matcher: Identifies file types from code content
        batch_app_number: Current app number for batch processing
        extraction_stats: Statistics about extraction operations
    """
    
    def __init__(self, port_manager: PortManager):
        """
        Initialize CodeExtractor with required dependencies.
        
        Args:
            port_manager: PortManager instance for handling port configurations
        """
        self.port_manager = port_manager
        self.model_detector = ModelDetector()
        self.file_matcher = FilePatternMatcher()
        self.batch_app_number: Optional[int] = None
        self.extraction_stats = self._initialize_extraction_stats()
    
    def _initialize_extraction_stats(self) -> Dict:
        """
        Initialize extraction statistics tracking.
        
        Creates a dictionary to track various metrics about the code
        extraction process including counts by provider, model issues, etc.
        
        Returns:
            Dictionary with initialized statistic counters
        """
        return {
            'total_messages': 0,
            'total_blocks': 0,
            'by_provider': {},
            'by_model': {},
            'models_with_issues': set(),
            'port_replacements': 0
        }
    
    def set_batch_app_number(self, app_number: int):
        """
        Set the current batch application number for processing.
        
        Used during batch processing to associate extracted code blocks
        with the correct application number.
        
        Args:
            app_number: Application number to use for extracted blocks
        """
        self.batch_app_number = app_number
    
    def extract_code_blocks_from_json(
        self, 
        json_data: Dict, 
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[CodeBlock]:
        """
        Extract code blocks from JSON data containing AI responses.
        
        Processes JSON data from AI conversations and extracts all code blocks,
        analyzing them for file types, ports, and other metadata.
        
        Args:
            json_data: Dictionary containing messages and character data
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of extracted and processed CodeBlock objects
        """
        extracted_blocks = []
        messages = json_data.get("messages", {})
        characters = json_data.get("characters", {})
        
        # Reset extraction statistics
        self.extraction_stats = self._initialize_extraction_stats()
        self.extraction_stats['total_messages'] = len(messages)
        
        # Analyze all available models first
        model_analyses = {}
        for character_id, character_data in characters.items():
            model_info = self.model_detector.analyze_model(character_id, character_data)
            model_analyses[character_id] = model_info
            logger.info(f"Analyzed model: {model_info.standardized_name}")
        
        # Process each message for code blocks
        total_messages = len(messages)
        processed_messages = 0
        
        for message_id, message_data in messages.items():
            content = message_data.get("content", "")
            character_id = message_data.get("characterId", "")
            
            # Validate character/model information
            if character_id not in model_analyses:
                logger.warning(f"Unknown character ID: {character_id}")
                continue
            
            model_info = model_analyses[character_id]
            
            # Extract app number from metadata if available
            if ("metadata" in message_data and 
                "app_details" in message_data["metadata"]):
                app_details = message_data["metadata"]["app_details"]
                if "app_num" in app_details:
                    self.batch_app_number = app_details["app_num"]
            
            # Extract code blocks from this message
            message_code_blocks = self._extract_code_blocks(
                content, model_info, message_id
            )
            
            # Apply metadata hints if available
            if ("metadata" in message_data and 
                "app_details" in message_data["metadata"]):
                self._process_metadata_hints(
                    message_code_blocks, 
                    message_data["metadata"]["app_details"]
                )
            
            extracted_blocks.extend(message_code_blocks)
            
            # Update progress
            processed_messages += 1
            if progress_callback:
                progress_callback(processed_messages, total_messages)
        
        # Update final statistics
        self._update_extraction_stats(extracted_blocks)
        
        logger.info(f"Extraction complete: {len(extracted_blocks)} blocks from {len(messages)} messages")
        return extracted_blocks
    
    def _extract_code_blocks(self, content: str, model_info: ModelInfo, message_id: str) -> List[CodeBlock]:
        """Extract code blocks from message content with multiple file support"""
        blocks = []
        app_num = self.batch_app_number if self.batch_app_number is not None else 1
        
        # Pattern for markdown code blocks
        pattern = re.compile(r'```(?:(\w+))?\s*\n(.*?)```', re.DOTALL)
        matches = pattern.finditer(content)
        
        code_blocks_found = []
        for match in matches:
            language = match.group(1) or 'plaintext'
            code = match.group(2).strip()
            
            if len(code) < AppConfig.MIN_CODE_BLOCK_SIZE:
                continue
                
            code_blocks_found.append((language, code))
        
        # If no code blocks, check if entire content is markdown
        if not code_blocks_found and len(content) > AppConfig.MIN_CODE_BLOCK_SIZE and '```' in content:
            code_blocks_found.append(('markdown', content))
        
        # Track existing file types to avoid duplicates
        existing_files = []
        
        # Process each code block with multiple file detection
        for language, code in code_blocks_found:
            cleaned_code, issues = self._clean_code(code, model_info)
            
            # First try multiple file identification
            multiple_files = self.file_matcher.identify_multiple_files(cleaned_code, language, existing_files)
            
            if multiple_files:
                # Multiple files detected
                html_blocks = []  # Store HTML blocks to match with JSX later
                
                for file_type, code_segment, file_index, is_main, html_compatibility in multiple_files:
                    backend_port, frontend_port = self.port_manager.get_ports_for_model_app(
                        model_info.standardized_name, app_num
                    )
                    
                    block = CodeBlock(
                        language=language,
                        code=code_segment,
                        file_type=file_type,
                        model_info=model_info,
                        app_num=app_num,
                        message_id=message_id,
                        backend_port=backend_port,
                        frontend_port=frontend_port,
                        extraction_issues=issues,
                        file_index=file_index,
                        is_main_component=is_main,
                        html_compatibility_score=html_compatibility
                    )
                    
                    blocks.append(block)
                    existing_files.append(file_type)
                    
                    if language == 'html':
                        html_blocks.append(block)
                    
                    logger.info(f"Extracted {file_type} (index: {file_index}, main: {is_main}) from {model_info.standardized_name}")
            else:
                # Single file identification (fallback)
                file_type = self.file_matcher.identify_file_type(cleaned_code, language)
                
                if not file_type:
                    logger.warning(f"Could not identify file type for {language} block from {model_info.standardized_name}")
                    continue
                
                backend_port, frontend_port = self.port_manager.get_ports_for_model_app(
                    model_info.standardized_name, app_num
                )
                
                block = CodeBlock(
                    language=language,
                    code=cleaned_code,
                    file_type=file_type,
                    model_info=model_info,
                    app_num=app_num,
                    message_id=message_id,
                    backend_port=backend_port,
                    frontend_port=frontend_port,
                    extraction_issues=issues,
                    file_index=0,
                    is_main_component=True,
                    html_compatibility_score=0.0
                )
                
                blocks.append(block)
                existing_files.append(file_type)
                logger.info(f"Extracted {file_type} from {model_info.standardized_name}")
        
        # Post-process JSX blocks to determine best main component based on HTML compatibility
        self._optimize_jsx_main_component(blocks)
        
        return blocks
    
    def _optimize_jsx_main_component(self, blocks: List[CodeBlock]):
        """Optimize JSX main component selection based on HTML compatibility and structure"""
        jsx_blocks = [block for block in blocks if block.language.lower() in ['jsx', 'javascript', 'js']]
        html_blocks = [block for block in blocks if block.language.lower() == 'html']
        
        if not jsx_blocks:
            return
        
        # If there are HTML blocks, find the JSX with best HTML compatibility
        if html_blocks:
            html_content = html_blocks[0].code  # Use first HTML block as reference
            
            best_jsx = None
            best_score = -1
            
            for jsx_block in jsx_blocks:
                # Calculate compatibility with HTML structure
                compatibility_score = self._calculate_jsx_html_compatibility(jsx_block.code, html_content)
                jsx_block.html_compatibility_score = compatibility_score
                
                if compatibility_score > best_score:
                    best_score = compatibility_score
                    best_jsx = jsx_block
            
            # Update main component designation
            for jsx_block in jsx_blocks:
                jsx_block.is_main_component = (jsx_block == best_jsx)
                
                # Update file path for main component
                if jsx_block.is_main_component and jsx_block.file_type != "frontend/src/App.jsx":
                    jsx_block.file_type = "frontend/src/App.jsx"
                    
            logger.info(f"Optimized main JSX component based on HTML compatibility (score: {best_score:.2f})")
        
        # If no HTML, prioritize based on React patterns and naming
        else:
            for jsx_block in jsx_blocks:
                # Score based on React patterns
                react_score = 0
                if 'export default' in jsx_block.code:
                    react_score += 3
                if 'App' in jsx_block.code:
                    react_score += 2
                if any(hook in jsx_block.code for hook in ['useState', 'useEffect', 'useContext']):
                    react_score += 2
                if 'import React' in jsx_block.code:
                    react_score += 1
                    
                jsx_block.html_compatibility_score = react_score / 8.0  # Normalize to 0-1
    
    def _calculate_jsx_html_compatibility(self, jsx_code: str, html_code: str) -> float:
        """Calculate how well JSX code matches with HTML structure"""
        score = 0.0
        
        # Extract HTML elements from both
        jsx_elements = set(re.findall(r'<(\w+)', jsx_code))
        html_elements = set(re.findall(r'<(\w+)', html_code))
        
        # Calculate element overlap
        if html_elements:
            common_elements = jsx_elements.intersection(html_elements)
            element_overlap = len(common_elements) / len(html_elements)
            score += element_overlap * 0.4
        
        # Check for id/class patterns
        html_ids = set(re.findall(r'id="([^"]+)"', html_code))
        jsx_ids = set(re.findall(r'id="([^"]+)"', jsx_code))
        
        if html_ids:
            id_overlap = len(jsx_ids.intersection(html_ids)) / len(html_ids)
            score += id_overlap * 0.2
        
        # Check for React root mounting pattern
        if 'root' in html_code and any(pattern in jsx_code for pattern in ['createRoot', 'render', 'ReactDOM']):
            score += 0.3
        
        # Check for similar structure complexity
        jsx_depth = jsx_code.count('<') - jsx_code.count('</')
        html_depth = html_code.count('<') - html_code.count('</')
        
        if html_depth > 0:
            depth_similarity = 1 - abs(jsx_depth - html_depth) / max(jsx_depth, html_depth, 1)
            score += depth_similarity * 0.1
        
        return min(score, 1.0)
    
    def _clean_code(self, code: str, model_info: ModelInfo) -> Tuple[str, List[str]]:
        """Clean extracted code from AI commentary"""
        issues = []
        cleaned = code
        
        commentary_patterns = [
            r'^(?:Here\'s|Here is|This is|I\'ll|Let me).*?:\s*\n',
            r'^(?:```.*?\n)?(?:# )?(?:File:|Filename:).*?\n',
            r'^\s*(?:Note:|TODO:|FIXME:|Important:).*?\n',
        ]
        
        for pattern in commentary_patterns:
            if re.search(pattern, cleaned, re.MULTILINE | re.IGNORECASE):
                cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.IGNORECASE)
                issues.append("Removed AI commentary")
        
        if cleaned.count('...') > 2:
            issues.append("Code appears truncated")
        
        return cleaned, issues
    
    def _process_metadata_hints(self, blocks: List[CodeBlock], app_details: Dict):
        """Process metadata hints for file type identification"""
        if not app_details or "code_type" not in app_details:
            return
        
        code_type = app_details["code_type"]
        
        for block in blocks:
            if block.file_type:
                continue
            
            if code_type == "frontend":
                if block.language.lower() in ["jsx", "javascript", "js"]:
                    block.file_type = "frontend/src/App.jsx"
                elif block.language.lower() == "css":
                    block.file_type = "frontend/src/App.css"
                elif block.language.lower() == "html":
                    block.file_type = "frontend/index.html"
                elif block.language.lower() == "json":
                    block.file_type = "frontend/package.json"
            elif code_type == "backend":
                if block.language.lower() == "python":
                    block.file_type = "backend/app.py"
                elif block.language.lower() in ["text", "plaintext"]:
                    block.file_type = "backend/requirements.txt"
                elif block.language.lower() == "dockerfile":
                    block.file_type = "backend/Dockerfile"
    
    def _update_extraction_stats(self, blocks: List[CodeBlock]):
        """Update extraction statistics"""
        self.extraction_stats['total_blocks'] = len(blocks)
        
        for block in blocks:
            provider = block.model_info.provider
            model = block.model_info.standardized_name
            
            self.extraction_stats['by_provider'][provider] = \
                self.extraction_stats['by_provider'].get(provider, 0) + 1
            self.extraction_stats['by_model'][model] = \
                self.extraction_stats['by_model'].get(model, 0) + 1
            
            if block.extraction_issues:
                self.extraction_stats['models_with_issues'].add(model)
    
    def get_statistics_report(self) -> str:
        """Generate extraction statistics report"""
        stats = self.extraction_stats
        report = "EXTRACTION STATISTICS\n" + "="*50 + "\n\n"
        
        report += f"Total messages processed: {stats['total_messages']}\n"
        report += f"Total code blocks extracted: {stats['total_blocks']}\n"
        
        if stats['total_messages'] > 0:
            success_rate = (stats['total_blocks'] / stats['total_messages'] * 100)
            report += f"Success rate: {success_rate:.1f}%\n\n"
        
        report += "BY PROVIDER:\n"
        for provider, count in sorted(stats['by_provider'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / max(stats['total_blocks'], 1)) * 100
            report += f"  {provider}: {count} blocks ({percentage:.1f}%)\n"
        
        report += "\nBY MODEL:\n"
        for model, count in sorted(stats['by_model'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / max(stats['total_blocks'], 1)) * 100
            report += f"  {model}: {count} blocks ({percentage:.1f}%)\n"
        
        if stats['models_with_issues']:
            report += f"\nMODELS WITH ISSUES ({len(stats['models_with_issues'])}):\n"
            for model in sorted(stats['models_with_issues']):
                report += f"  {model}\n"
        
        return report

# =============================================================================
# File Management
# =============================================================================

class FileManager:
    """Manages file operations for extracted code blocks"""
    
    def __init__(self, models_dir: Path):
        self.models_dir = models_dir
        self.save_stats = self._init_stats()
    
    def _init_stats(self) -> Dict[str, int]:
        """Initialize save statistics"""
        return {
            'files_written': 0,
            'files_failed': 0,
            'port_replacements': 0
        }
    
    def save_code_block(self, block: CodeBlock, force_overwrite: bool = True) -> bool:
        """Save a code block to filesystem with multiple file support"""
        try:
            if not block.file_type:
                logger.warning(f"No file type for block from {block.model_info.standardized_name}")
                return False
            
            # Handle file indexing for multiple files of the same type
            base_file_type = block.file_type
            file_path = (self.models_dir / 
                        block.model_info.standardized_name / 
                        f"app{block.app_num}" / 
                        base_file_type)
            
            # If file_index > 0 and it's not the main component, modify filename
            if block.file_index > 0 and not block.is_main_component:
                file_path = self._generate_indexed_filename(file_path, block.file_index, block)
            
            # Handle special case for JSX components that are not main
            elif (block.language.lower() in ['jsx', 'javascript', 'js'] and 
                  not block.is_main_component and 
                  'components/' not in str(file_path)):
                file_path = self._generate_component_filename(file_path, block)
            
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            final_code = block.get_replaced_code()
            
            # Add compatibility comments for JSX files
            if block.language.lower() in ['jsx', 'javascript', 'js']:
                final_code = self._add_jsx_metadata_comments(final_code, block)
            
            if block.port_replacements:
                self.save_stats['port_replacements'] += len(block.port_replacements)
                logger.info(f"Applied port replacements to {file_path.name}: {block.port_replacements}")
            
            file_path.write_text(final_code, encoding='utf-8')
            
            self.save_stats['files_written'] += 1
            
            # Log additional info for multiple files
            extra_info = ""
            if block.file_index > 0:
                extra_info = f" (index: {block.file_index})"
            if hasattr(block, 'is_main_component') and block.is_main_component:
                extra_info += " [MAIN]"
            if hasattr(block, 'html_compatibility_score') and block.html_compatibility_score > 0:
                extra_info += f" (HTML compat: {block.html_compatibility_score:.2f})"
            
            logger.info(f"Successfully saved: {file_path}{extra_info}")
            return True
            
        except Exception as e:
            self.save_stats['files_failed'] += 1
            logger.error(f"Failed to save {block.file_type}: {e}")
            return False
    
    def _generate_indexed_filename(self, original_path: Path, index: int, block: CodeBlock) -> Path:
        """Generate filename with index for multiple files"""
        stem = original_path.stem
        suffix = original_path.suffix
        parent = original_path.parent
        
        # Extract component name if available
        if block.language.lower() in ['jsx', 'javascript', 'js']:
            # Try to extract component name from code
            comp_match = re.search(r'(?:function\s+(\w+)|const\s+(\w+)\s*=)', block.code)
            if comp_match:
                comp_name = comp_match.group(1) or comp_match.group(2)
                return parent / f"{comp_name}{suffix}"
        
        # Default indexed naming
        return parent / f"{stem}_{index:02d}{suffix}"
    
    def _generate_component_filename(self, original_path: Path, block: CodeBlock) -> Path:
        """Generate component-specific filename for JSX files"""
        # Try to extract component name from code
        comp_match = re.search(r'(?:export\s+default\s+function\s+(\w+)|function\s+(\w+)|const\s+(\w+)\s*=)', block.code)
        
        if comp_match:
            comp_name = next((name for name in comp_match.groups() if name), "Component")
        else:
            comp_name = f"Component{block.file_index:02d}"
        
        # Create components directory structure
        components_dir = original_path.parent / "src" / "components"
        return components_dir / f"{comp_name}.jsx"
    
    def _add_jsx_metadata_comments(self, code: str, block: CodeBlock) -> str:
        """Add metadata comments to JSX files"""
        comments = []
        
        if hasattr(block, 'is_main_component') and block.is_main_component:
            comments.append("// MAIN COMPONENT - Entry point for the application")
        
        if hasattr(block, 'html_compatibility_score') and block.html_compatibility_score > 0:
            comments.append(f"// HTML Compatibility Score: {block.html_compatibility_score:.2f}")
        
        if block.file_index > 0:
            comments.append(f"// File Index: {block.file_index} (Multiple components detected)")
        
        if comments:
            header = "/*\n * Generated by OpenRouter Code Generator\n" + \
                    "\n".join(f" * {comment[3:]}" for comment in comments) + \
                    "\n */\n\n"
            return header + code
        
        return code
    
    def create_project_index(self, blocks: List[CodeBlock], model_name: str, app_num: int) -> bool:
        """Create an index file for the project with file relationships"""
        try:
            model_dir = self.models_dir / model_name / f"app{app_num}"
            index_file = model_dir / "PROJECT_INDEX.md"
            
            # Group blocks by type
            jsx_blocks = [b for b in blocks if b.language.lower() in ['jsx', 'javascript', 'js']]
            python_blocks = [b for b in blocks if b.language.lower() == 'python']
            html_blocks = [b for b in blocks if b.language.lower() == 'html']
            other_blocks = [b for b in blocks if b not in jsx_blocks + python_blocks + html_blocks]
            
            content = f"# Project Index - {model_name} App {app_num}\n\n"
            content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Frontend section
            if jsx_blocks or html_blocks:
                content += "## Frontend Files\n\n"
                
                if html_blocks:
                    for block in html_blocks:
                        content += f"- **{block.file_type}** - Main HTML template\n"
                
                if jsx_blocks:
                    main_jsx = next((b for b in jsx_blocks if b.is_main_component), None)
                    if main_jsx:
                        content += f"- **{main_jsx.file_type}** - Main React component (HTML compatibility: {main_jsx.html_compatibility_score:.2f})\n"
                    
                    for block in jsx_blocks:
                        if not block.is_main_component:
                            content += f"- **{block.file_type}** - Component (compatibility: {block.html_compatibility_score:.2f})\n"
                
                content += "\n"
            
            # Backend section
            if python_blocks:
                content += "## Backend Files\n\n"
                for block in python_blocks:
                    main_indicator = " - Main application" if block.is_main_component else ""
                    content += f"- **{block.file_type}**{main_indicator}\n"
                content += "\n"
            
            # Other files
            if other_blocks:
                content += "## Configuration & Other Files\n\n"
                for block in other_blocks:
                    content += f"- **{block.file_type}** ({block.language})\n"
                content += "\n"
            
            # Compatibility analysis
            if jsx_blocks and html_blocks:
                content += "## HTML-JSX Compatibility Analysis\n\n"
                html_elements = set()
                for html_block in html_blocks:
                    html_elements.update(re.findall(r'<(\w+)', html_block.code))
                
                best_jsx = max(jsx_blocks, key=lambda b: b.html_compatibility_score)
                content += f"Best JSX-HTML match: **{best_jsx.file_type}** (score: {best_jsx.html_compatibility_score:.2f})\n\n"
                
                content += "### HTML Elements Found:\n"
                for elem in sorted(html_elements):
                    content += f"- `{elem}`\n"
                content += "\n"
            
            # Port configuration
            if blocks:
                sample_block = blocks[0]
                if sample_block.backend_port or sample_block.frontend_port:
                    content += "## Port Configuration\n\n"
                    if sample_block.backend_port:
                        content += f"- Backend port: {sample_block.backend_port}\n"
                    if sample_block.frontend_port:
                        content += f"- Frontend port: {sample_block.frontend_port}\n"
                    content += "\n"
            
            # File statistics
            content += "## Statistics\n\n"
            content += f"- Total files: {len(blocks)}\n"
            content += f"- JSX/JS files: {len(jsx_blocks)}\n"
            content += f"- Python files: {len(python_blocks)}\n"
            content += f"- HTML files: {len(html_blocks)}\n"
            content += f"- Other files: {len(other_blocks)}\n"
            
            model_dir.mkdir(parents=True, exist_ok=True)
            index_file.write_text(content, encoding='utf-8')
            
            logger.info(f"Created project index: {index_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create project index: {e}")
            return False
    
    def get_save_statistics(self) -> Dict[str, int]:
        """Get save statistics"""
        return self.save_stats.copy()
    
    def reset_statistics(self):
        """Reset statistics"""
        self.save_stats = self._init_stats()

# =============================================================================
# OpenRouter API Integration
# =============================================================================

class OpenRouterCodeGenerator:
    """Generates markdown documentation using OpenRouter API"""
    
    # Available models - loaded dynamically
    AVAILABLE_MODELS: List[str] = []
    MODEL_CAPABILITIES: Dict[str, Dict[str, Any]] = {}
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[GenerationConfig] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.site_url = os.getenv("OPENROUTER_SITE_URL", "https://app-generator.local")
        self.site_name = os.getenv("OPENROUTER_SITE_NAME", "App Code Generator")
        self.config = config or GenerationConfig(models=[])
        
        if not self.api_key:
            raise ValueError("OpenRouter API key not found. Set OPENROUTER_API_KEY in .env file")
        
        # Load models on initialization
        self.__class__.load_models_from_summary()
        self._initialize_model_capabilities()
    
    @classmethod
    def load_models_from_summary(cls, models_file: Optional[Path] = None) -> bool:
        """Load models from models_summary.json"""
        if models_file is None:
            # Use script directory instead of current working directory
            script_dir = Path(__file__).parent
            models_file = script_dir / "models_summary.json"
        
        try:
            if not models_file.exists():
                logger.warning(f"Models summary file not found: {models_file}")
                cls.AVAILABLE_MODELS = []
                return False
            
            with open(models_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            models = []
            
            for model_info in data.get('models', []):
                name = model_info['name']
                provider = model_info['provider']
                
                # Convert from JSON format (provider_model-name) to OpenRouter format (provider/model-name)
                if '_' in name and name.startswith(f"{provider}_"):
                    # Remove provider prefix and replace first underscore with slash
                    model_part = name[len(f"{provider}_"):]
                    openrouter_name = f"{provider}/{model_part}"
                    models.append(openrouter_name)
                    logger.debug(f"Converted {name} -> {openrouter_name}")
                else:
                    logger.warning(f"Unexpected model format: {name} (provider: {provider})")
            
            if models:
                cls.AVAILABLE_MODELS = sorted(models)
                logger.info(f"Loaded {len(models)} models from {models_file}")
                logger.info(f"Sample models: {models[:3]} ...")
                return True
            else:
                logger.warning("No models found in summary file")
                cls.AVAILABLE_MODELS = []
                return False
                
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            cls.AVAILABLE_MODELS = []
            return False
    
    @classmethod
    def reload_models(cls, models_file: Optional[Path] = None) -> bool:
        """Reload models from summary file"""
        return cls.load_models_from_summary(models_file)
    
    def _initialize_model_capabilities(self):
        """Initialize model capabilities"""
        # Use script directory instead of current working directory
        script_dir = Path(__file__).parent
        capabilities_file = script_dir / "model_capabilities.json"
        
        if capabilities_file.exists():
            try:
                with open(capabilities_file, 'r', encoding='utf-8') as f:
                    self.MODEL_CAPABILITIES = json.load(f)
                logger.info(f"Loaded capabilities for {len(self.MODEL_CAPABILITIES)} models")
            except Exception as e:
                logger.warning(f"Error loading capabilities: {e}")
        
        # Initialize missing models
        for model in self.AVAILABLE_MODELS:
            if model not in self.MODEL_CAPABILITIES:
                self.MODEL_CAPABILITIES[model] = self._get_default_model_capabilities(model)
        
        self._save_model_capabilities()
        
        # Optionally fetch live data to enhance capabilities
        if os.getenv("FETCH_LIVE_MODEL_DATA", "false").lower() == "true":
            logger.info("Fetching live model data is enabled via environment variable")
            self.fetch_live_model_data()
    
    def _get_default_model_capabilities(self, model: str) -> Dict[str, Any]:
        """Get comprehensive default capabilities for a model based on OpenRouter API structure"""
        capabilities = {
            # Basic model information
            "model_id": model,
            "canonical_slug": model.replace('/', '_').replace(':', '_'),
            "provider": model.split('/')[0] if '/' in model else "unknown",
            "model_name": model.split('/')[-1] if '/' in model else model,
            "is_free": ":free" in model,
            "last_updated": datetime.now().isoformat(),
            
            # Context and token limits
            "context_window": 32000,
            "max_output_tokens": 8000,
            "max_completion_tokens": 8000,
            "max_prompt_tokens": 24000,
            
            # API capabilities
            "supports_system_prompt": True,
            "supports_function_calling": False,
            "supports_tool_calling": False,
            "supports_streaming": True,
            "supports_json_mode": False,
            "supports_structured_output": False,
            "supports_reasoning_tokens": False,
            "supports_vision": False,
            "supports_image_input": False,
            "supports_image_output": False,
            "supports_web_search": False,
            "supports_prompt_caching": False,
            
            # Modalities
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            
            # Pricing information (USD per token)
            "pricing": {
                "prompt_tokens": "0.00005" if ":free" not in model else "0",
                "completion_tokens": "0.00015" if ":free" not in model else "0",
                "image_tokens": "0",
                "request_cost": "0",
                "web_search_cost": "0",
                "reasoning_tokens": "0",
                "input_cache_read": "0",
                "input_cache_write": "0"
            },
            
            # Performance metrics
            "performance": {
                "avg_latency_ms": 2000,
                "tokens_per_second": 50,
                "uptime_percentage": 99.5,
                "quality_score": 7.5,
                "speed_score": 7.0,
                "cost_efficiency": 6.0
            },
            
            # Model architecture
            "architecture": {
                "tokenizer": "GPT",
                "instruct_type": "chat",
                "quantization": "unknown",
                "parameter_count": "unknown",
                "training_cutoff": "2024-04"
            },
            
            # Capabilities and features
            "capabilities": {
                "reasoning": False,
                "coding": True,
                "math": True,
                "creative_writing": True,
                "analysis": True,
                "multilingual": True,
                "long_context": False,
                "vision": False,
                "function_calling": False,
                "json_mode": False
            },
            
            # Supported parameters
            "supported_parameters": [
                "temperature", "max_tokens", "top_p", "frequency_penalty", 
                "presence_penalty", "stop", "stream", "seed"
            ],
            
            # Rate limits and restrictions
            "rate_limits": {
                "requests_per_minute": 60,
                "tokens_per_minute": 100000,
                "requests_per_day": 1000
            },
            
            # Provider information
            "provider_info": {
                "moderated_by_openrouter": True,
                "needs_moderation": False,
                "may_log_prompts": True,
                "may_train_on_data": False,
                "privacy_policy_url": "",
                "terms_of_service_url": "",
                "status_page_url": ""
            },
            
            # Quality metrics (0-10 scale)
            "quality_metrics": {
                "helpfulness": 7.5,
                "accuracy": 8.0,
                "coherence": 8.5,
                "creativity": 7.0,
                "instruction_following": 8.0,
                "safety": 9.0
            },
            
            # Usage statistics
            "usage_stats": {
                "popularity_rank": 50,
                "total_requests": 0,
                "success_rate": 98.5,
                "average_rating": 4.2,
                "total_tokens_generated": 0
            }
        }
        
        model_lower = model.lower()
        
        # Model-specific adjustments based on known characteristics
        if "gpt-4" in model_lower:
            capabilities.update({
                "context_window": 128000,
                "max_output_tokens": 16384,
                "max_completion_tokens": 16384,
                "max_prompt_tokens": 111616,
                "supports_vision": "vision" in model_lower or "v" in model_lower,
                "supports_image_input": "vision" in model_lower or "v" in model_lower,
                "supports_function_calling": True,
                "supports_tool_calling": True,
                "supports_json_mode": True,
                "supports_structured_output": True,
                "pricing": {
                    "prompt_tokens": "0.00001" if "mini" in model_lower else "0.000005",
                    "completion_tokens": "0.00003" if "mini" in model_lower else "0.000015",
                    "image_tokens": "0.001275" if "vision" in model_lower else "0",
                    "request_cost": "0",
                    "web_search_cost": "0",
                    "reasoning_tokens": "0",
                    "input_cache_read": "0",
                    "input_cache_write": "0"
                },
                "performance": {
                    "avg_latency_ms": 1500,
                    "tokens_per_second": 80,
                    "uptime_percentage": 99.9,
                    "quality_score": 9.5,
                    "speed_score": 8.5,
                    "cost_efficiency": 8.0
                },
                "capabilities": {
                    "reasoning": True,
                    "coding": True,
                    "math": True,
                    "creative_writing": True,
                    "analysis": True,
                    "multilingual": True,
                    "long_context": True,
                    "vision": "vision" in model_lower or "v" in model_lower,
                    "function_calling": True,
                    "json_mode": True
                },
                "quality_metrics": {
                    "helpfulness": 9.5,
                    "accuracy": 9.2,
                    "coherence": 9.7,
                    "creativity": 8.5,
                    "instruction_following": 9.5,
                    "safety": 9.8
                },
                "supported_parameters": [
                    "temperature", "max_tokens", "top_p", "frequency_penalty", 
                    "presence_penalty", "stop", "stream", "seed", "tools", 
                    "tool_choice", "response_format", "logit_bias", "top_logprobs"
                ]
            })
            if "vision" in model_lower or "v" in model_lower:
                capabilities["input_modalities"] = ["text", "image"]
                capabilities["architecture"]["instruct_type"] = "multimodal_chat"
                
        elif "claude" in model_lower:
            capabilities.update({
                "context_window": 200000,
                "max_output_tokens": 8192,
                "max_completion_tokens": 8192,
                "max_prompt_tokens": 191808,
                "supports_vision": "3.5" in model_lower or "vision" in model_lower,
                "supports_image_input": "3.5" in model_lower or "vision" in model_lower,
                "supports_function_calling": True,
                "supports_tool_calling": True,
                "supports_json_mode": True,
                "supports_prompt_caching": True,
                "pricing": {
                    "prompt_tokens": "0.000003",
                    "completion_tokens": "0.000015",
                    "image_tokens": "0.0048" if "3.5" in model_lower else "0",
                    "request_cost": "0",
                    "web_search_cost": "0",
                    "reasoning_tokens": "0",
                    "input_cache_read": "0.0000003",
                    "input_cache_write": "0.00000375"
                },
                "performance": {
                    "avg_latency_ms": 2000,
                    "tokens_per_second": 75,
                    "uptime_percentage": 99.8,
                    "quality_score": 9.2,
                    "speed_score": 8.0,
                    "cost_efficiency": 9.0
                },
                "capabilities": {
                    "reasoning": True,
                    "coding": True,
                    "math": True,
                    "creative_writing": True,
                    "analysis": True,
                    "multilingual": True,
                    "long_context": True,
                    "vision": "3.5" in model_lower or "vision" in model_lower,
                    "function_calling": True,
                    "json_mode": True
                },
                "architecture": {
                    "tokenizer": "Claude",
                    "instruct_type": "chat",
                    "quantization": "unknown",
                    "parameter_count": "unknown",
                    "training_cutoff": "2024-04"
                },
                "quality_metrics": {
                    "helpfulness": 9.2,
                    "accuracy": 9.0,
                    "coherence": 9.8,
                    "creativity": 9.0,
                    "instruction_following": 9.3,
                    "safety": 9.9
                },
                "provider_info": {
                    "moderated_by_openrouter": False,
                    "needs_moderation": False,
                    "may_log_prompts": False,
                    "may_train_on_data": False,
                    "privacy_policy_url": "https://www.anthropic.com/privacy",
                    "terms_of_service_url": "https://www.anthropic.com/terms",
                    "status_page_url": "https://status.anthropic.com/"
                }
            })
            if "3.5" in model_lower or "vision" in model_lower:
                capabilities["input_modalities"] = ["text", "image"]
                capabilities["architecture"]["instruct_type"] = "multimodal_chat"
                
        elif "gemini" in model_lower:
            capabilities.update({
                "context_window": 1000000 if "pro" in model_lower else 128000,
                "max_output_tokens": 8192,
                "max_completion_tokens": 8192,
                "supports_vision": True,
                "supports_image_input": True,
                "supports_function_calling": True,
                "supports_tool_calling": True,
                "supports_json_mode": True,
                "pricing": {
                    "prompt_tokens": "0.000000125" if "flash" in model_lower else "0.00000125",
                    "completion_tokens": "0.000000375" if "flash" in model_lower else "0.000005",
                    "image_tokens": "0.000265",
                    "request_cost": "0",
                    "web_search_cost": "0",
                    "reasoning_tokens": "0",
                    "input_cache_read": "0",
                    "input_cache_write": "0"
                },
                "performance": {
                    "avg_latency_ms": 1800 if "flash" in model_lower else 2500,
                    "tokens_per_second": 100 if "flash" in model_lower else 60,
                    "uptime_percentage": 99.7,
                    "quality_score": 8.5,
                    "speed_score": 9.0 if "flash" in model_lower else 7.0,
                    "cost_efficiency": 9.5 if "flash" in model_lower else 8.0
                },
                "capabilities": {
                    "reasoning": True,
                    "coding": True,
                    "math": True,
                    "creative_writing": True,
                    "analysis": True,
                    "multilingual": True,
                    "long_context": "pro" in model_lower,
                    "vision": True,
                    "function_calling": True,
                    "json_mode": True
                },
                "input_modalities": ["text", "image"],
                "architecture": {
                    "tokenizer": "Gemini",
                    "instruct_type": "multimodal_chat",
                    "quantization": "unknown",
                    "parameter_count": "unknown",
                    "training_cutoff": "2024-04"
                },
                "quality_metrics": {
                    "helpfulness": 8.5,
                    "accuracy": 8.7,
                    "coherence": 8.8,
                    "creativity": 8.2,
                    "instruction_following": 8.9,
                    "safety": 9.5
                }
            })
            
        elif "deepseek" in model_lower:
            capabilities.update({
                "context_window": 128000 if "r1" in model_lower or "v3" in model_lower else 64000,
                "max_output_tokens": 16000 if "r1" in model_lower or "v3" in model_lower else 8000,
                "max_completion_tokens": 16000 if "r1" in model_lower or "v3" in model_lower else 8000,
                "supports_reasoning_tokens": "r1" in model_lower,
                "pricing": {
                    "prompt_tokens": "0.00000014" if "chat" in model_lower else "0.00000055",
                    "completion_tokens": "0.00000028" if "chat" in model_lower else "0.00000055",
                    "image_tokens": "0",
                    "request_cost": "0",
                    "web_search_cost": "0",
                    "reasoning_tokens": "0.00000055" if "r1" in model_lower else "0",
                    "input_cache_read": "0",
                    "input_cache_write": "0"
                },
                "performance": {
                    "avg_latency_ms": 2200,
                    "tokens_per_second": 70,
                    "uptime_percentage": 99.5,
                    "quality_score": 8.8 if "r1" in model_lower else 8.2,
                    "speed_score": 7.5,
                    "cost_efficiency": 9.8
                },
                "capabilities": {
                    "reasoning": "r1" in model_lower,
                    "coding": True,
                    "math": True,
                    "creative_writing": True,
                    "analysis": True,
                    "multilingual": True,
                    "long_context": "r1" in model_lower or "v3" in model_lower,
                    "vision": False,
                    "function_calling": False,
                    "json_mode": True
                },
                "quality_metrics": {
                    "helpfulness": 8.8 if "r1" in model_lower else 8.0,
                    "accuracy": 9.0 if "r1" in model_lower else 8.2,
                    "coherence": 8.5,
                    "creativity": 7.8,
                    "instruction_following": 8.7,
                    "safety": 8.5
                }
            })
            
        elif "llama" in model_lower:
            capabilities.update({
                "context_window": 131072,
                "max_output_tokens": 8192,
                "max_completion_tokens": 8192,
                "supports_vision": "vision" in model_lower or "llava" in model_lower,
                "supports_image_input": "vision" in model_lower or "llava" in model_lower,
                "supports_function_calling": "3.1" in model_lower or "3.2" in model_lower,
                "supports_tool_calling": "3.1" in model_lower or "3.2" in model_lower,
                "pricing": {
                    "prompt_tokens": "0.00000018" if "8b" in model_lower else "0.00000059",
                    "completion_tokens": "0.00000018" if "8b" in model_lower else "0.00000079",
                    "image_tokens": "0.001135" if "vision" in model_lower else "0",
                    "request_cost": "0",
                    "web_search_cost": "0",
                    "reasoning_tokens": "0",
                    "input_cache_read": "0",
                    "input_cache_write": "0"
                },
                "performance": {
                    "avg_latency_ms": 2000,
                    "tokens_per_second": 85,
                    "uptime_percentage": 99.6,
                    "quality_score": 8.5,
                    "speed_score": 8.5,
                    "cost_efficiency": 9.2
                },
                "capabilities": {
                    "reasoning": True,
                    "coding": True,
                    "math": True,
                    "creative_writing": True,
                    "analysis": True,
                    "multilingual": True,
                    "long_context": True,
                    "vision": "vision" in model_lower or "llava" in model_lower,
                    "function_calling": "3.1" in model_lower or "3.2" in model_lower,
                    "json_mode": True
                },
                "architecture": {
                    "tokenizer": "Llama",
                    "instruct_type": "chat",
                    "quantization": "unknown",
                    "parameter_count": "70B" if "70b" in model_lower else ("8B" if "8b" in model_lower else "unknown"),
                    "training_cutoff": "2024-12"
                }
            })
            if "vision" in model_lower or "llava" in model_lower:
                capabilities["input_modalities"] = ["text", "image"]
                capabilities["architecture"]["instruct_type"] = "multimodal_chat"
        
        return capabilities
    
    def _save_model_capabilities(self):
        """Save model capabilities to file with comprehensive statistics"""
        try:
            # Create a comprehensive capabilities file with metadata
            output = {
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "total_models": len(self.MODEL_CAPABILITIES),
                    "data_source": "OpenRouter API + Static Analysis",
                    "format_version": "2.0",
                    "description": "Comprehensive model capabilities including pricing, performance, and feature support"
                },
                "capabilities_summary": {
                    "providers": {},
                    "total_free_models": 0,
                    "total_vision_models": 0,
                    "total_function_calling_models": 0,
                    "total_reasoning_models": 0,
                    "avg_context_window": 0,
                    "price_ranges": {
                        "cheapest_prompt": {"model": "", "price": float('inf')},
                        "most_expensive_prompt": {"model": "", "price": 0},
                        "cheapest_completion": {"model": "", "price": float('inf')},
                        "most_expensive_completion": {"model": "", "price": 0}
                    }
                },
                "models": self.MODEL_CAPABILITIES
            }
            
            # Calculate summary statistics
            total_context = 0
            for model_id, caps in self.MODEL_CAPABILITIES.items():
                provider = caps.get("provider", "unknown")
                
                # Count by provider
                if provider not in output["capabilities_summary"]["providers"]:
                    output["capabilities_summary"]["providers"][provider] = {
                        "count": 0,
                        "free_models": 0,
                        "vision_models": 0,
                        "function_calling_models": 0
                    }
                
                output["capabilities_summary"]["providers"][provider]["count"] += 1
                
                # Count features
                if caps.get("is_free", False):
                    output["capabilities_summary"]["total_free_models"] += 1
                    output["capabilities_summary"]["providers"][provider]["free_models"] += 1
                
                if caps.get("supports_vision", False):
                    output["capabilities_summary"]["total_vision_models"] += 1
                    output["capabilities_summary"]["providers"][provider]["vision_models"] += 1
                
                if caps.get("supports_function_calling", False):
                    output["capabilities_summary"]["total_function_calling_models"] += 1
                    output["capabilities_summary"]["providers"][provider]["function_calling_models"] += 1
                
                if caps.get("supports_reasoning_tokens", False) or caps.get("capabilities", {}).get("reasoning", False):
                    output["capabilities_summary"]["total_reasoning_models"] += 1
                
                # Context window average
                context = caps.get("context_window", 0)
                total_context += context
                
                # Price tracking
                pricing = caps.get("pricing", {})
                prompt_price = float(pricing.get("prompt_tokens", "0"))
                completion_price = float(pricing.get("completion_tokens", "0"))
                
                if prompt_price > 0:
                    if prompt_price < output["capabilities_summary"]["price_ranges"]["cheapest_prompt"]["price"]:
                        output["capabilities_summary"]["price_ranges"]["cheapest_prompt"] = {
                            "model": model_id, "price": prompt_price
                        }
                    if prompt_price > output["capabilities_summary"]["price_ranges"]["most_expensive_prompt"]["price"]:
                        output["capabilities_summary"]["price_ranges"]["most_expensive_prompt"] = {
                            "model": model_id, "price": prompt_price
                        }
                
                if completion_price > 0:
                    if completion_price < output["capabilities_summary"]["price_ranges"]["cheapest_completion"]["price"]:
                        output["capabilities_summary"]["price_ranges"]["cheapest_completion"] = {
                            "model": model_id, "price": completion_price
                        }
                    if completion_price > output["capabilities_summary"]["price_ranges"]["most_expensive_completion"]["price"]:
                        output["capabilities_summary"]["price_ranges"]["most_expensive_completion"] = {
                            "model": model_id, "price": completion_price
                        }
            
            # Calculate average context window
            if len(self.MODEL_CAPABILITIES) > 0:
                output["capabilities_summary"]["avg_context_window"] = total_context // len(self.MODEL_CAPABILITIES)
            
            # Use script directory instead of current working directory
            script_dir = Path(__file__).parent
            capabilities_file = script_dir / "model_capabilities.json"
            with open(capabilities_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Enhanced model capabilities saved with {len(self.MODEL_CAPABILITIES)} models")
            
        except Exception as e:
            logger.error(f"Error saving model capabilities: {e}")
    
    def fetch_live_model_data(self) -> bool:
        """Fetch live model data from OpenRouter API using focused approach"""
        try:
            logger.info("Fetching live model data for loaded models only...")
            
            # Get currently loaded models (base versions only)
            base_models = {model.replace(":free", "") for model in self.AVAILABLE_MODELS}
            logger.info(f"Checking pricing for {len(base_models)} loaded models")
            
            # Fetch models list from API
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=self.get_headers(),
                timeout=30
            )
            
            if response.status_code == 200:
                models_data = response.json().get("data", [])
                logger.info(f"Fetched {len(models_data)} models from OpenRouter API")
                
                # Create pricing lookup for our loaded models
                api_pricing = {}
                capabilities_updates = 0
                
                for model_data in models_data:
                    model_id = model_data.get("id", "")
                    if not model_id or model_id not in base_models:
                        continue
                        
                    # Store pricing info
                    api_pricing[model_id] = model_data.get("pricing", {})
                    
                    # Update capabilities if we have this model
                    if model_id in self.MODEL_CAPABILITIES:
                        capabilities = self.MODEL_CAPABILITIES[model_id]
                        self._update_capabilities_from_api_data(capabilities, model_data)
                        capabilities_updates += 1
                
                # Determine which loaded models are free
                free_models = set()
                for base_model in base_models:
                    if base_model in api_pricing:
                        pricing = api_pricing[base_model]
                        prompt_cost = float(pricing.get("prompt", "0") or "0")
                        completion_cost = float(pricing.get("completion", "0") or "0")
                        
                        if prompt_cost == 0 and completion_cost == 0:
                            free_models.add(base_model)
                
                # Build refined model list: base models + free versions where applicable
                refined_models = set()
                for base_model in base_models:
                    refined_models.add(base_model)  # Add paid version
                    if base_model in free_models:
                        refined_models.add(f"{base_model}:free")  # Add free version
                
                # Update the available models with focused list
                self.__class__.AVAILABLE_MODELS = sorted(refined_models)
                
                logger.info(f"Updated capabilities for {capabilities_updates} models")
                logger.info(f"Refined model list: {len(base_models)} base models → {len(refined_models)} total ({len(free_models)} free)")
                
                # Save updated capabilities
                self._save_model_capabilities()
                return True
                
            else:
                logger.warning(f"Failed to fetch models: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error fetching live model data: {e}")
            return False
    
    @classmethod
    def get_free_models_dynamically(cls, api_key: Optional[str] = None) -> Set[str]:
        """Get free models by checking pricing dynamically for already loaded models only"""
        try:
            api_key = api_key or os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                logger.warning("No API key available for dynamic free model detection")
                return set()

            headers = {
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://app-generator.local"),
                "X-Title": os.getenv("OPENROUTER_SITE_NAME", "App Code Generator"),
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                models_data = response.json().get("data", [])
                logger.info(f"Fetched {len(models_data)} models from OpenRouter API")
                
                # Create a mapping of model_id -> pricing info
                api_pricing = {}
                api_model_ids = []
                for model_data in models_data:
                    model_id = model_data.get("id", "")
                    if model_id:
                        api_model_ids.append(model_id)
                        pricing = model_data.get("pricing", {})
                        api_pricing[model_id] = pricing
                
                # Only check our already loaded models
                base_models = {model.replace(":free", "") for model in cls.AVAILABLE_MODELS}
                free_models = set()
                
                logger.info(f"Checking {len(base_models)} loaded models against {len(api_pricing)} API models...")
                
                # Show sample comparisons for debugging
                logger.info(f"Sample loaded models: {list(base_models)[:5]}")
                logger.info(f"Sample API model IDs: {api_model_ids[:5]}")
                
                # Check each loaded model against API data
                found_matches = 0
                free_variant_matches = 0
                for base_model in base_models:
                    # First, check the base model
                    model_is_free = False
                    
                    if base_model in api_pricing:
                        found_matches += 1
                        pricing = api_pricing[base_model]
                        prompt_cost = float(pricing.get("prompt", "0") or "0")
                        completion_cost = float(pricing.get("completion", "0") or "0")
                        
                        if prompt_cost == 0 and completion_cost == 0:
                            free_models.add(base_model)
                            logger.info(f"✅ Model {base_model} confirmed as FREE (base version)")
                            model_is_free = True
                        else:
                            logger.info(f"💳 Model {base_model} is PAID (${prompt_cost}/${completion_cost})")
                    else:
                        logger.warning(f"❌ Model {base_model} not found in API data")
                    
                    # If base model is not free, check for :free variant
                    if not model_is_free:
                        free_variant = f"{base_model}:free"
                        if free_variant in api_pricing:
                            free_variant_matches += 1
                            pricing = api_pricing[free_variant]
                            prompt_cost = float(pricing.get("prompt", "0") or "0")
                            completion_cost = float(pricing.get("completion", "0") or "0")
                            
                            if prompt_cost == 0 and completion_cost == 0:
                                free_models.add(base_model)
                                logger.info(f"✅ Model {base_model} confirmed as FREE (:free variant)")
                            else:
                                logger.warning(f"⚠️ Model {free_variant} exists but not free (${prompt_cost}/${completion_cost})")
                        else:
                            # Try to find partial matches for debugging
                            partial_matches = [api_id for api_id in api_model_ids if base_model.split('/')[-1] in api_id and ':free' in api_id]
                            if partial_matches:
                                logger.info(f"   Possible free matches: {partial_matches[:3]}")
                
                logger.info(f"Found {found_matches} exact base matches + {free_variant_matches} free variant matches")
                logger.info(f"Identified {len(free_models)} free models: {list(free_models)}")
                return free_models
            else:
                logger.warning(f"API request failed with status {response.status_code}")
                if response.text:
                    logger.warning(f"API response: {response.text[:200]}")
                return set()
                
        except Exception as e:
            logger.warning(f"Could not fetch free models dynamically: {e}")
            # Fallback: return models with :free suffix from current list
            fallback_free = {model.replace(":free", "") for model in cls.AVAILABLE_MODELS if ":free" in model}
            logger.info(f"Using fallback: {len(fallback_free)} models with :free suffix")
            return fallback_free
    
    def _update_capabilities_from_api_data(self, capabilities: Dict[str, Any], api_data: Dict[str, Any]):
        """Update capabilities with data from OpenRouter API"""
        try:
            # Update basic info
            capabilities["model_name"] = api_data.get("name", capabilities.get("model_name", ""))
            capabilities["canonical_slug"] = api_data.get("canonical_slug", capabilities.get("canonical_slug", ""))
            
            # Update context and limits
            if "context_length" in api_data:
                capabilities["context_window"] = api_data["context_length"]
            
            top_provider = api_data.get("top_provider", {})
            if top_provider:
                if "context_length" in top_provider:
                    capabilities["context_window"] = top_provider["context_length"]
                if "max_completion_tokens" in top_provider:
                    capabilities["max_completion_tokens"] = top_provider["max_completion_tokens"]
                    capabilities["max_output_tokens"] = top_provider["max_completion_tokens"]
                capabilities["provider_info"]["moderated_by_openrouter"] = top_provider.get("is_moderated", True)
            
            # Update pricing
            pricing = api_data.get("pricing", {})
            if pricing:
                capabilities["pricing"].update({
                    "prompt_tokens": pricing.get("prompt", "0"),
                    "completion_tokens": pricing.get("completion", "0"),
                    "image_tokens": pricing.get("image", "0"),
                    "request_cost": pricing.get("request", "0"),
                    "web_search_cost": pricing.get("web_search", "0"),
                    "reasoning_tokens": pricing.get("internal_reasoning", "0"),
                    "input_cache_read": pricing.get("input_cache_read", "0"),
                    "input_cache_write": pricing.get("input_cache_write", "0")
                })
            
            # Update architecture
            architecture = api_data.get("architecture", {})
            if architecture:
                capabilities["architecture"].update({
                    "tokenizer": architecture.get("tokenizer", capabilities["architecture"]["tokenizer"]),
                    "instruct_type": architecture.get("instruct_type", capabilities["architecture"]["instruct_type"])
                })
                
                # Update modalities
                input_modalities = architecture.get("input_modalities", [])
                output_modalities = architecture.get("output_modalities", [])
                
                if input_modalities:
                    capabilities["input_modalities"] = input_modalities
                    capabilities["supports_vision"] = "image" in input_modalities
                    capabilities["supports_image_input"] = "image" in input_modalities
                    capabilities["capabilities"]["vision"] = "image" in input_modalities
                
                if output_modalities:
                    capabilities["output_modalities"] = output_modalities
                    capabilities["supports_image_output"] = "image" in output_modalities
            
            # Update supported parameters
            supported_params = api_data.get("supported_parameters", [])
            if supported_params:
                capabilities["supported_parameters"] = supported_params
                
                # Update capability flags based on supported parameters
                capabilities["supports_function_calling"] = "tools" in supported_params
                capabilities["supports_tool_calling"] = "tools" in supported_params
                capabilities["capabilities"]["function_calling"] = "tools" in supported_params
                capabilities["supports_json_mode"] = "response_format" in supported_params
                capabilities["capabilities"]["json_mode"] = "response_format" in supported_params
            
            # Update description
            description = api_data.get("description", "")
            if description:
                capabilities["description"] = description
                
                # Enhance capabilities based on description
                desc_lower = description.lower()
                if "reasoning" in desc_lower or "think" in desc_lower:
                    capabilities["supports_reasoning_tokens"] = True
                    capabilities["capabilities"]["reasoning"] = True
                
                if "vision" in desc_lower or "multimodal" in desc_lower:
                    capabilities["supports_vision"] = True
                    capabilities["capabilities"]["vision"] = True
            
            # Update last update timestamp
            capabilities["last_updated"] = datetime.now().isoformat()
            capabilities["data_source"] = "OpenRouter API"
            
        except Exception as e:
            logger.warning(f"Error updating capabilities from API data: {e}")
    
    def get_model_capabilities(self, model: str) -> Dict[str, Any]:
        """Get capabilities for a model"""
        return self.MODEL_CAPABILITIES.get(model, self._get_default_model_capabilities(model))
    
    def get_adaptive_config_for_model(self, model: str, base_config: GenerationConfig) -> GenerationConfig:
        """Get configuration adapted for model capabilities"""
        capabilities = self.get_model_capabilities(model)
        
        adapted = GenerationConfig(
            models=base_config.models,
            temperature=base_config.temperature,
            max_tokens=base_config.max_tokens,
            system_prompt=base_config.system_prompt,
            save_raw_markdown=base_config.save_raw_markdown,
            save_json_export=base_config.save_json_export,
            auto_adjust_for_complexity=base_config.auto_adjust_for_complexity
        )
        
        model_max_output = capabilities.get("max_output_tokens", 8000)
        adapted.max_tokens = min(base_config.max_tokens, model_max_output)
        
        if capabilities.get("is_free", False):
            adapted.max_tokens = min(adapted.max_tokens, 8000)
            adapted.temperature = min(base_config.temperature, 0.8)
        
        logger.info(f"Adapted config for {model}: max_tokens={adapted.max_tokens}")
        
        return adapted
    
    @classmethod
    def get_model_info(cls, model_slug: str) -> Dict[str, str]:
        """Get information about a model"""
        info = {
            'provider': 'unknown',
            'model_name': 'unknown',
            'is_free': False,
            'display_name': model_slug
        }
        
        try:
            clean_slug = model_slug.replace(':free', '')
            if '/' in clean_slug:
                provider, model_name = clean_slug.split('/', 1)
                info['provider'] = provider
                info['model_name'] = model_name
                info['is_free'] = ':free' in model_slug
                info['display_name'] = f"{provider.title()} {model_name.replace('-', ' ').title()}"
        except Exception:
            pass
        
        return info
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name
        return headers
    
    def generate_markdown(self, template_content: str, model: str, is_frontend: bool = True, 
                         app_name: str = "", requirements: Optional[List[str]] = None) -> Tuple[Optional[str], bool, Optional[APICallStats]]:
        """Generate markdown documentation using OpenRouter API"""
        
        # Get adjusted configuration
        base_adjusted_config = self.config.get_adjusted_config(app_name, requirements or [])
        model_adapted_config = self.get_adaptive_config_for_model(model, base_adjusted_config)
        
        code_type = "frontend" if is_frontend else "backend"
        requirements_text = "\n".join(f"- {req}" for req in (requirements or []))
        
        prompt = f"""Generate a comprehensive {code_type} implementation for the '{app_name}' application.

**Requirements:**
{requirements_text}

**Template Specification:**
{template_content}

**Instructions:**
1. Return the COMPLETE response in markdown format
2. Include all necessary code blocks with proper syntax highlighting  
3. Add detailed explanations and documentation
4. Include setup instructions, dependencies, and usage examples
5. Structure the response with clear headings and sections
6. Ensure all code is production-ready and follows best practices
7. Add comments in the code for clarity
8. Include error handling and edge cases
9. Make sure the implementation matches ALL requirements

Please generate a comprehensive {code_type} solution based on the above template."""

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": model_adapted_config.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": model_adapted_config.temperature,
            "max_tokens": model_adapted_config.max_tokens
        }
        
        stats = APICallStats(
            model=model,
            app_name=app_name,
            call_type=code_type
        )
        
        start_time = time.time()
        
        for attempt in range(AppConfig.MAX_RETRIES):
            stats.attempts += 1
            attempt_start = time.time()
            
            timeout = AppConfig.TIMEOUT_FALLBACK[attempt] if attempt < len(AppConfig.TIMEOUT_FALLBACK) else AppConfig.TIMEOUT_FALLBACK[-1]
            stats.timeout_used = timeout
            
            try:
                logger.info(f"Generating {code_type} for {app_name} with {model} (attempt {attempt + 1}/{AppConfig.MAX_RETRIES}, timeout: {timeout}s)...")
                
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=self.get_headers(),
                    timeout=timeout
                )
                
                attempt_duration = time.time() - attempt_start
                stats.retry_delays.append(attempt_duration)
                
                # Save raw response
                try:
                    if response.status_code == 200:
                        response_data = response.json()
                        stats.raw_response = response_data
                    else:
                        stats.raw_response = {
                            'status_code': response.status_code,
                            'text': response.text,
                            'headers': dict(response.headers),
                            'reason': response.reason
                        }
                except Exception as json_error:
                    stats.raw_response = {
                        'status_code': response.status_code,
                        'text': response.text[:2000],
                        'headers': dict(response.headers),
                        'json_error': str(json_error)
                    }
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        if content.strip():
                            stats.success = True
                            stats.final_content = content.strip()
                            stats.total_duration = time.time() - start_time
                            
                            self._save_raw_api_data(stats, payload, template_content, requirements)
                            
                            logger.info(f"✅ Successfully generated {code_type} for {app_name} with {model}")
                            return content.strip(), True, stats
                        else:
                            error_msg = f"Empty response from {model}"
                            stats.error_messages.append(error_msg)
                            logger.warning(error_msg)
                    except json.JSONDecodeError as e:
                        error_msg = f"JSON decode error: {str(e)}"
                        stats.error_messages.append(error_msg)
                        logger.error(error_msg)
                elif response.status_code == 429:
                    error_msg = "Rate limit hit (429)"
                    stats.error_messages.append(error_msg)
                    logger.warning(error_msg)
                    
                    if attempt < AppConfig.MAX_RETRIES - 1:
                        rate_limit_delay = min(120 * (attempt + 1), AppConfig.MAX_BACKOFF_DELAY)
                        logger.info(f"⏳ Waiting {rate_limit_delay}s...")
                        time.sleep(rate_limit_delay)
                        continue
                else:
                    error_msg = f"API Error: {response.status_code} - {response.reason}"
                    stats.error_messages.append(error_msg)
                    logger.error(error_msg)
                
            except requests.exceptions.Timeout:
                error_msg = f"Timeout after {timeout}s"
                stats.error_messages.append(error_msg)
                logger.error(error_msg)
                
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {str(e)}"
                stats.error_messages.append(error_msg)
                logger.error(error_msg)
                
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                stats.error_messages.append(error_msg)
                logger.error(error_msg)
            
            if attempt < AppConfig.MAX_RETRIES - 1:
                if AppConfig.EXPONENTIAL_BACKOFF:
                    base_delay = AppConfig.RETRY_DELAYS[min(attempt, len(AppConfig.RETRY_DELAYS) - 1)]
                    exponential_delay = base_delay * (2 ** attempt)
                    jitter = exponential_delay * 0.1 * (0.5 - random.random())
                    retry_delay = min(exponential_delay + jitter, AppConfig.MAX_BACKOFF_DELAY)
                else:
                    retry_delay = AppConfig.RETRY_DELAYS[attempt] if attempt < len(AppConfig.RETRY_DELAYS) else AppConfig.RETRY_DELAYS[-1]
                
                logger.info(f"⏳ Waiting {retry_delay:.1f}s before retry...")
                time.sleep(retry_delay)
        
        stats.total_duration = time.time() - start_time
        stats.success = False
        
        self._save_raw_api_data(stats, payload, template_content, requirements)
        
        logger.error(f"❌ Failed to generate {code_type} for {app_name} with {model}")
        return None, False, stats
    
    def _save_raw_api_data(self, stats: APICallStats, payload: Dict, template_content: str, requirements: Optional[List[str]]):
        """Save raw API call data"""
        try:
            timestamp_str = stats.timestamp.strftime("%Y%m%d_%H%M%S")
            model_safe = stats.model.replace('/', '_').replace(':', '_')

            # Only use api_data subfolders, do not create any in the main folder
            base_dir = Path("api_data")
            raw_outputs_dir = base_dir / "raw_outputs" / timestamp_str[:8] / model_safe
            stats_dir = base_dir / "generation_stats" / timestamp_str[:8] / model_safe
            failed_dir = base_dir / "failed_attempts" / timestamp_str[:8] / model_safe

            if stats.success:
                raw_outputs_dir.mkdir(parents=True, exist_ok=True)
                stats_dir.mkdir(parents=True, exist_ok=True)
            else:
                failed_dir.mkdir(parents=True, exist_ok=True)
                stats_dir.mkdir(parents=True, exist_ok=True)

            call_id = f"{stats.app_name}_{stats.call_type}_{timestamp_str}_{uuid.uuid4().hex[:8]}"

            raw_data = {
                'metadata': {
                    'call_id': call_id,
                    'model': stats.model,
                    'app_name': stats.app_name,
                    'call_type': stats.call_type,
                    'timestamp': stats.timestamp.isoformat(),
                    'success': stats.success,
                    'total_attempts': stats.attempts,
                    'total_duration_seconds': stats.total_duration
                },
                'request': {
                    'payload': payload,
                    'headers': self.get_headers(),
                    'api_url': self.api_url,
                    'template_content': template_content,
                    'requirements': requirements or []
                },
                'response': {
                    'raw_response': stats.raw_response,
                    'final_content': stats.final_content,
                    'content_length': len(stats.final_content) if stats.final_content else 0
                },
                'execution_details': {
                    'attempts': stats.attempts,
                    'timeout_used': stats.timeout_used,
                    'retry_delays': stats.retry_delays,
                    'error_messages': stats.error_messages
                }
            }

            if stats.success:
                raw_file = raw_outputs_dir / f"{call_id}_success.json"
            else:
                raw_file = failed_dir / f"{call_id}_failed.json"

            with open(raw_file, 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, indent=2, ensure_ascii=False)

            # Save statistics summary
            stats_summary = {
                'call_id': call_id,
                'model': stats.model,
                'app_name': stats.app_name,
                'call_type': stats.call_type,
                'timestamp': stats.timestamp.isoformat(),
                'success': stats.success,
                'attempts': stats.attempts,
                'total_duration': round(stats.total_duration, 3),
                'timeout_used': stats.timeout_used,
                'content_generated': bool(stats.final_content),
                'content_length': len(stats.final_content) if stats.final_content else 0,
                'errors_count': len(stats.error_messages),
                'first_error': stats.error_messages[0] if stats.error_messages else None
            }

            stats_file = stats_dir / f"{call_id}_stats.json"
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_summary, f, indent=2, ensure_ascii=False)

            # Update daily summary
            daily_summary_file = stats_dir.parent / f"daily_summary_{timestamp_str[:8]}.json"
            daily_data = []

            if daily_summary_file.exists():
                try:
                    with open(daily_summary_file, 'r', encoding='utf-8') as f:
                        daily_data = json.load(f)
                except Exception:
                    daily_data = []

            daily_data.append(stats_summary)

            with open(daily_summary_file, 'w', encoding='utf-8') as f:
                json.dump(daily_data, f, indent=2, ensure_ascii=False)

            if stats.success:
                logger.info(f"💾 Saved successful generation data: {raw_file}")
            else:
                logger.warning(f"💾 Saved failed generation data: {raw_file}")

        except Exception as e:
            logger.error(f"Failed to save raw API data: {e}")
            # Fallback save
            try:
                fallback_dir = Path("api_data") / "fallback_saves"
                fallback_dir.mkdir(parents=True, exist_ok=True)
                fallback_file = fallback_dir / f"fallback_{int(time.time())}.json"

                fallback_data = {
                    'error_saving': str(e),
                    'model': stats.model,
                    'app_name': stats.app_name,
                    'success': stats.success,
                    'attempts': stats.attempts,
                    'errors': stats.error_messages,
                    'timestamp': stats.timestamp.isoformat()
                }

                with open(fallback_file, 'w', encoding='utf-8') as f:
                    json.dump(fallback_data, f, indent=2)

                logger.info(f"Saved fallback data to {fallback_file}")

            except Exception as fallback_error:
                logger.error(f"Even fallback save failed: {fallback_error}")
    
    def generate_analysis_report(self, date_filter: Optional[str] = None) -> str:
        """Generate analysis report from saved API data"""
        try:
            api_data_dir = Path("api_data")
            if not api_data_dir.exists():
                return "No API data directory found."
            
            stats_dir = api_data_dir / "generation_stats"
            daily_summaries = []
            
            for date_dir in stats_dir.glob("*"):
                if date_dir.is_dir():
                    if date_filter and date_filter not in date_dir.name:
                        continue
                    
                    summary_file = date_dir / f"daily_summary_{date_dir.name}.json"
                    if summary_file.exists():
                        try:
                            with open(summary_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                daily_summaries.extend(data)
                        except Exception as e:
                            logger.warning(f"Could not read {summary_file}: {e}")
            
            if not daily_summaries:
                return "No generation statistics found."
            
            # Analyze data
            total_calls = len(daily_summaries)
            successful_calls = sum(1 for s in daily_summaries if s['success'])
            failed_calls = total_calls - successful_calls
            
            model_stats = {}
            app_stats = {}
            error_patterns = {}
            
            total_tokens = 0
            total_cost = 0.0
            total_duration = 0.0
            
            for call in daily_summaries:
                model = call['model']
                app = call['app_name']
                
                if model not in model_stats:
                    model_stats[model] = {'total': 0, 'success': 0, 'failed': 0, 'avg_attempts': 0, 'total_tokens': 0}
                
                model_stats[model]['total'] += 1
                model_stats[model]['success'] += 1 if call['success'] else 0
                model_stats[model]['failed'] += 1 if not call['success'] else 0
                model_stats[model]['avg_attempts'] += call['attempts']
                model_stats[model]['total_tokens'] += call.get('openrouter_tokens_used', 0)
                
                if app not in app_stats:
                    app_stats[app] = {'total': 0, 'success': 0, 'failed': 0}
                
                app_stats[app]['total'] += 1
                app_stats[app]['success'] += 1 if call['success'] else 0
                app_stats[app]['failed'] += 1 if not call['success'] else 0
                
                if not call['success'] and call.get('first_error'):
                    error_type = call['first_error'].split(':')[0] if ':' in call['first_error'] else call['first_error'][:50]
                    error_patterns[error_type] = error_patterns.get(error_type, 0) + 1
                
                total_tokens += call.get('openrouter_tokens_used', 0)
                total_cost += call.get('openrouter_cost', 0.0)
                total_duration += call.get('total_duration', 0)
            
            # Calculate averages
            for model in model_stats:
                if model_stats[model]['total'] > 0:
                    model_stats[model]['avg_attempts'] /= model_stats[model]['total']
                    model_stats[model]['success_rate'] = (model_stats[model]['success'] / model_stats[model]['total']) * 100
            
            # Generate report
            report = "OPENROUTER API GENERATION ANALYSIS REPORT\n"
            report += "=" * 60 + "\n\n"
            
            report += "📊 OVERVIEW\n"
            report += f"Total API calls: {total_calls}\n"
            report += f"Successful: {successful_calls} ({(successful_calls/total_calls*100):.1f}%)\n"
            report += f"Failed: {failed_calls} ({(failed_calls/total_calls*100):.1f}%)\n"
            report += f"Total tokens used: {total_tokens:,}\n"
            report += f"Total estimated cost: ${total_cost:.4f}\n"
            report += f"Total processing time: {total_duration/60:.1f} minutes\n\n"
            
            report += "🤖 MODEL PERFORMANCE\n"
            report += "-" * 40 + "\n"
            for model, stats in sorted(model_stats.items(), key=lambda x: x[1].get('success_rate', 0), reverse=True):
                report += f"{model}:\n"
                report += f"  Success rate: {stats.get('success_rate', 0):.1f}% ({stats['success']}/{stats['total']})\n"
                report += f"  Avg attempts: {stats['avg_attempts']:.1f}\n"
                report += f"  Tokens used: {stats['total_tokens']:,}\n\n"
            
            report += "📱 APPLICATION PERFORMANCE\n"
            report += "-" * 40 + "\n"
            for app, stats in sorted(app_stats.items(), key=lambda x: x[1]['success'] / max(x[1]['total'], 1), reverse=True):
                success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
                report += f"{app}: {success_rate:.1f}% success ({stats['success']}/{stats['total']})\n"
            
            if error_patterns:
                report += "\n❌ COMMON ERROR PATTERNS\n"
                report += "-" * 40 + "\n"
                for error, count in sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:10]:
                    report += f"{error}: {count} occurrences\n"
            
            # Save report
            report_file = api_data_dir / f"analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"📋 Analysis report saved to {report_file}")
            return report
            
        except Exception as e:
            error_msg = f"Failed to generate analysis report: {e}"
            logger.error(error_msg)
            return error_msg

# =============================================================================
# API Data Management
# =============================================================================

class APIDataManager:
    """Manages API data files"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path("api_data")
    
    def cleanup_old_files(self, days_to_keep: int = 30) -> Dict[str, int]:
        """Clean up old API data files"""
        cleanup_stats = {
            'files_deleted': 0,
            'directories_cleaned': 0,
            'bytes_freed': 0,
            'errors': 0
        }
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            for subdir in ['raw_outputs', 'generation_stats', 'failed_attempts']:
                dir_path = self.base_dir / subdir
                if not dir_path.exists():
                    continue
                
                for date_dir in dir_path.glob("*"):
                    if not date_dir.is_dir():
                        continue
                    
                    try:
                        dir_date = datetime.strptime(date_dir.name, "%Y%m%d")
                        
                        if dir_date < cutoff_date:
                            size_bytes = sum(f.stat().st_size for f in date_dir.rglob('*') if f.is_file())
                            
                            import shutil
                            shutil.rmtree(date_dir)
                            
                            cleanup_stats['directories_cleaned'] += 1
                            cleanup_stats['bytes_freed'] += size_bytes
                            logger.info(f"Deleted old data directory: {date_dir}")
                            
                    except ValueError:
                        continue
                    except Exception as e:
                        cleanup_stats['errors'] += 1
                        logger.error(f"Error deleting {date_dir}: {e}")
            
            logger.info(f"Cleanup completed: {cleanup_stats['directories_cleaned']} directories, "
                       f"{cleanup_stats['bytes_freed'] / 1024 / 1024:.1f}MB freed")
            
        except Exception as e:
            cleanup_stats['errors'] += 1
            logger.error(f"Cleanup failed: {e}")
        
        return cleanup_stats
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get information about stored API data"""
        info = {
            'total_files': 0,
            'total_size_mb': 0.0,
            'by_type': {},
            'oldest_date': None,
            'newest_date': None,
            'models_tracked': set(),
            'apps_tracked': set()
        }
        
        try:
            if not self.base_dir.exists():
                return info
            
            dates_found = set()
            
            for file_path in self.base_dir.rglob('*.json'):
                info['total_files'] += 1
                info['total_size_mb'] += file_path.stat().st_size / 1024 / 1024
                
                parent_type = file_path.parent.parent.name if file_path.parent.parent != self.base_dir else file_path.parent.name
                info['by_type'][parent_type] = info['by_type'].get(parent_type, 0) + 1
                
                for part in file_path.parts:
                    if re.match(r'\d{8}', part):
                        dates_found.add(part)
                
                if info['total_files'] <= 50:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if 'model' in data:
                                info['models_tracked'].add(data['model'])
                            if 'app_name' in data:
                                info['apps_tracked'].add(data['app_name'])
                    except Exception:
                        pass
            
            if dates_found:
                sorted_dates = sorted(dates_found)
                info['oldest_date'] = sorted_dates[0]
                info['newest_date'] = sorted_dates[-1]
            
            info['models_tracked'] = list(info['models_tracked'])
            info['apps_tracked'] = list(info['apps_tracked'])
            
        except Exception as e:
            logger.error(f"Failed to get storage info: {e}")
        
        return info
    
    def create_archive(self, output_file: Optional[Path] = None) -> str:
        """Create archive of all API data"""
        try:
            if output_file is None:
                output_file = Path(f"api_data_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
            
            import zipfile
            
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in self.base_dir.rglob('*'):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(self.base_dir.parent)
                        zipf.write(file_path, relative_path)
            
            size_mb = output_file.stat().st_size / 1024 / 1024
            logger.info(f"Created archive: {output_file} ({size_mb:.1f}MB)")
            return str(output_file)
            
        except Exception as e:
            error_msg = f"Failed to create archive: {e}"
            logger.error(error_msg)
            return error_msg

# =============================================================================
# App Template Loader
# =============================================================================

class AppTemplateLoader:
    """Loads app templates from markdown files"""
    
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
    
    def load_templates(self) -> List[AppTemplate]:
        """Load all app templates from directory"""
        templates = []
        
        md_files = list(self.templates_dir.glob("*.md"))
        
        if not md_files:
            logger.warning(f"No markdown files found in {self.templates_dir}")
            return templates
        
        app_groups = {}
        
        for file in md_files:
            match = re.match(r'app_(\d+)_(frontend|backend)_(.+)\.md', file.name)
            if match:
                app_num = int(match.group(1))
                file_type = match.group(2)
                app_name = match.group(3)
                
                if app_num not in app_groups:
                    app_groups[app_num] = {
                        'name': app_name,
                        'frontend': None,
                        'backend': None
                    }
                
                app_groups[app_num][file_type] = file
        
        for app_num, files in sorted(app_groups.items()):
            if files['frontend'] and files['backend']:
                frontend_content = files['frontend'].read_text(encoding='utf-8')
                backend_content = files['backend'].read_text(encoding='utf-8')
                
                app_name = files['name'].replace('_', ' ').title()
                
                requirements = self._extract_requirements(frontend_content, backend_content)
                
                templates.append(AppTemplate(
                    app_num=app_num,
                    name=app_name,
                    frontend_template=frontend_content,
                    backend_template=backend_content,
                    requirements=requirements,
                    frontend_file=files['frontend'],
                    backend_file=files['backend']
                ))
        
        return templates
    
    def _extract_requirements(self, frontend: str, backend: str) -> List[str]:
        """Extract requirements from template content"""
        requirements = []
        
        patterns = [
            r'##?\s*(?:Features?|Requirements?)[:\s]*\n((?:[-*]\s*.+\n?)+)',
            r'(?:must|should|need to|required to)\s+(.+?)(?:\.|$)',
        ]
        
        for pattern in patterns:
            for content in [frontend, backend]:
                matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                for match in matches:
                    if isinstance(match, str) and match.strip():
                        lines = match.strip().split('\n')
                        for line in lines:
                            cleaned = re.sub(r'^[-*]\s*', '', line).strip()
                            if cleaned and len(cleaned) > 10:
                                requirements.append(cleaned)
        
        if not requirements:
            requirements = [
                "Modern and clean user interface",
                "Production-ready with error handling",
                "Proper routing and navigation",
                "Clean code structure with comments",
                "Comprehensive documentation"
            ]
        
        return list(set(requirements))[:5]

# =============================================================================
# GUI Application
# =============================================================================

class CombinedApp(tk.Tk):
    """Combined application for code generation and extraction"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize components
        self.generator: Optional[OpenRouterCodeGenerator] = None
        self.loader: Optional[AppTemplateLoader] = None
        
        # Initialize file management
        # Use script directory instead of current working directory
        script_dir = Path(__file__).parent
        self.port_config_file = script_dir / "port_config.json"
        self.models_dir = script_dir / "models"
        self.templates_dir = script_dir / "app_templates"
        self.output_dir = script_dir / "generated_conversations"
        # Do not create raw_outputs or generation_stats in main dir
        # self.raw_outputs_dir = current_dir / "raw_outputs"
        # self.generation_stats_dir = current_dir / "generation_stats"
        
        self.port_manager = PortManager(self.port_config_file)
        self.file_manager = FileManager(self.models_dir)
        self.extractor = CodeExtractor(self.port_manager)
        
        # Configuration
        self.config = GenerationConfig(models=[])
        self.templates: List[AppTemplate] = []
        self.generation_results: List[GenerationResult] = []
        
        # Parallel processing configuration
        self.parallel_workers = AppConfig.MAX_PARALLEL_REQUESTS
        
        # State
        self.is_generating: bool = False
        self.generation_queue: Queue = Queue()
        self.generation_thread: Optional[threading.Thread] = None
        
        # Initialize stats
        self.extraction_stats = {
            'total_blocks': 0,
            'saved_blocks': 0,
            'failed_blocks': 0
        }
        
        # UI variables
        self.template_vars = []
        self.model_vars = []
        
        # Model state for toggle system
        self.detected_free_models = set()
        
        # Setup UI
        self._setup_ui()
        
        # Auto-load models on startup
        self._auto_reload_models_on_startup()
        
        # Check initial setup
        self._check_setup()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _on_closing(self):
        """Handle window close event"""
        if self.is_generating:
            response = messagebox.askyesno(
                "Confirm Exit",
                "Generation/extraction is still in progress. Are you sure you want to exit?"
            )
            if response:
                self.is_generating = False
                self.destroy()
                sys.exit(0)
        else:
            self.destroy()
            sys.exit(0)
    
    def _check_setup(self):
        """Check if required files and directories exist"""
        issues = []
        
        # Check API key
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            issues.append("OpenRouter API key not found in environment")
            if hasattr(self, 'api_status_label'):
                self.api_status_label.config(text="API: ❌")
        else:
            if hasattr(self, 'api_status_label'):
                self.api_status_label.config(text="API: ✅")
        
        # Check port config
        if not self.port_config_file.exists():
            issues.append(f"Port configuration not found: {self.port_config_file}")
        else:
            try:
                self.port_manager = PortManager(self.port_config_file)
                self.extractor = CodeExtractor(self.port_manager)
                self.log_message("✅ Port configuration loaded", "success")
            except Exception as e:
                issues.append(f"Error loading port config: {e}")
        
        # Create directories
        for dir_path, name in [
            (self.models_dir, "models"), 
            (self.templates_dir, "templates"),
            (self.output_dir, "output")
        ]:
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True)
                    self.log_message(f"Created {name} directory: {dir_path}", "info")
                except Exception as e:
                    issues.append(f"Could not create {name} directory: {e}")
        
        if self.models_dir.exists():
            self.file_manager = FileManager(self.models_dir)
        
        if issues:
            messagebox.showwarning(
                "Setup Issues",
                "The following issues were found:\n\n" + "\n".join(f"• {issue}" for issue in issues)
            )
    
    def _setup_ui(self):
        """Setup the user interface"""
        self.title(AppConfig.WINDOW_TITLE)
        self.geometry(AppConfig.WINDOW_SIZE)
        self.minsize(1200, 800)
        
        # Configure theme
        self._setup_theme()
        
        # Configure main grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Main container
        main_container = ttk.Frame(self)
        main_container.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=1)
        
        # Create notebook
        self.notebook = ttk.Notebook(main_container, style="Modern.TNotebook")
        self.notebook.grid(row=0, column=0, sticky="nsew")
        
        # Create tabs
        self._create_generation_tab()
        self._create_extraction_tab()
        self._create_results_tab()
        self._create_analytics_tab()
        self._create_settings_tab()
        
        # Status bar
        self._create_status_bar()
        
        # Keyboard shortcuts
        self._setup_keyboard_shortcuts()
    
    def _setup_theme(self):
        """Configure modern theme"""
        style = ttk.Style()
        
        style.configure("Modern.TNotebook", 
                       background="#f0f0f0",
                       tabmargins=[2, 5, 2, 0])
        style.configure("Modern.TNotebook.Tab",
                       padding=[20, 8],
                       font=("Segoe UI", 9, "bold"))
        
        style.configure("Accent.TButton",
                       font=("Segoe UI", 9, "bold"))
        
        style.configure("Success.TButton",
                       font=("Segoe UI", 9, "bold"))
        
        style.configure("Warning.TButton",
                       font=("Segoe UI", 9))
        
        style.configure("Card.TFrame",
                       relief="solid",
                       borderwidth=1)
        
        style.configure("Heading.TLabel",
                       font=("Segoe UI", 11, "bold"))
        
        style.configure("Subheading.TLabel",
                       font=("Segoe UI", 9, "bold"))
        
        style.configure("Info.TLabel",
                       font=("Segoe UI", 8))
    
    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.bind("<Control-g>", lambda e: self._start_generation())
        self.bind("<Control-s>", lambda e: self._stop_generation())
        self.bind("<Control-r>", lambda e: self._reload_models())
        self.bind("<Control-l>", lambda e: self._load_templates())
        self.bind("<F5>", lambda e: self._reload_models())
        self.bind("<Escape>", lambda e: self._stop_generation())
    
    def _create_generation_tab(self):
        """Create generation tab"""
        generation_frame = ttk.Frame(self.notebook)
        self.notebook.add(generation_frame, text="🚀 Generation")
        
        generation_frame.grid_rowconfigure(1, weight=1)
        generation_frame.grid_rowconfigure(2, weight=1)
        generation_frame.grid_columnconfigure(0, weight=1)
        
        # Header
        self._create_generation_header(generation_frame)
        
        # Content
        self._create_generation_content(generation_frame)
        
        # Log
        self._create_log_section(generation_frame)
    
    def _create_generation_header(self, parent):
        """Create generation header"""
        header_frame = ttk.Frame(parent, style="Card.TFrame")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Title
        title_frame = ttk.Frame(header_frame)
        title_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=15, pady=(15, 10))
        
        ttk.Label(title_frame, text="Code Generation", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(title_frame, 
                 text="Generate application code using AI models with customizable templates",
                 style="Info.TLabel").pack(anchor="w", pady=(2, 0))
        
        # Configuration
        config_container = ttk.Frame(header_frame)
        config_container.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 15))
        config_container.grid_columnconfigure(0, weight=1)
        config_container.grid_columnconfigure(1, weight=1)
        
        # Templates card
        templates_card = ttk.LabelFrame(config_container, text="📁 Templates", padding=10)
        templates_card.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        templates_card.grid_columnconfigure(1, weight=1)
        
        ttk.Label(templates_card, text="Directory:").grid(row=0, column=0, sticky="w")
        self.templates_dir_var = tk.StringVar(value=str(self.templates_dir))
        templates_entry = ttk.Entry(templates_card, textvariable=self.templates_dir_var, width=40)
        templates_entry.grid(row=0, column=1, sticky="ew", padx=(10, 5))
        
        ttk.Button(templates_card, text="Browse", command=self._browse_templates_dir, width=8).grid(row=0, column=2)
        ttk.Button(templates_card, text="🔄 Load Templates", 
                  command=self._load_templates, style="Accent.TButton").grid(row=1, column=0, columnspan=3, pady=(10, 0), sticky="ew")
        
        # Output card
        output_card = ttk.LabelFrame(config_container, text="📤 Output", padding=10)
        output_card.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        output_card.grid_columnconfigure(1, weight=1)
        
        ttk.Label(output_card, text="Directory:").grid(row=0, column=0, sticky="w")
        self.output_dir_var = tk.StringVar(value=str(self.output_dir))
        output_entry = ttk.Entry(output_card, textvariable=self.output_dir_var, width=40)
        output_entry.grid(row=0, column=1, sticky="ew", padx=(10, 5))
        
        ttk.Button(output_card, text="Browse", command=self._browse_output_dir, width=8).grid(row=0, column=2)
        ttk.Button(output_card, text="📁 Open Folder", 
                  command=self._open_output_folder).grid(row=1, column=0, columnspan=3, pady=(10, 0), sticky="ew")
    
    def _create_generation_content(self, parent):
        """Create generation content"""
        content_frame = ttk.Frame(parent)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=1)
        
        # Templates section
        templates_section = self._create_templates_section(content_frame)
        templates_section.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        # Models section
        models_section = self._create_models_section(content_frame)
        models_section.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        
        # Control panel
        control_panel = self._create_control_panel(content_frame)
        control_panel.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    
    def _create_templates_section(self, parent):
        """Create templates section"""
        templates_frame = ttk.LabelFrame(parent, text="📋 Application Templates", padding=10)
        templates_frame.grid_rowconfigure(1, weight=1)
        templates_frame.grid_columnconfigure(0, weight=1)
        
        # Header
        templates_header = ttk.Frame(templates_frame)
        templates_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        templates_header.grid_columnconfigure(1, weight=1)
        
        # Selection controls
        select_frame = ttk.Frame(templates_header)
        select_frame.pack(side="left")
        
        ttk.Button(select_frame, text="✓ All", command=self._select_all_templates, 
                  width=8).pack(side="left", padx=(0, 5))
        ttk.Button(select_frame, text="✗ None", command=self._deselect_all_templates,
                  width=8).pack(side="left")
        
        # Info label
        self.templates_info_label = ttk.Label(templates_header, text="No templates loaded", 
                                            style="Info.TLabel")
        self.templates_info_label.pack(side="right")
        
        # Templates list
        list_frame = ttk.Frame(templates_frame)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Canvas for scrolling
        self.templates_canvas = tk.Canvas(list_frame, bg="#ffffff", highlightthickness=0)
        templates_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.templates_canvas.yview)
        self.templates_scrollable_frame = ttk.Frame(self.templates_canvas)
        
        self.templates_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.templates_canvas.configure(scrollregion=self.templates_canvas.bbox("all"))
        )
        
        self.templates_canvas.create_window((0, 0), window=self.templates_scrollable_frame, anchor="nw")
        self.templates_canvas.configure(yscrollcommand=templates_scrollbar.set)
        
        # Bind mouse wheel
        def _on_templates_mousewheel(event):
            self.templates_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.templates_canvas.bind("<MouseWheel>", _on_templates_mousewheel)
        
        self.templates_canvas.grid(row=0, column=0, sticky="nsew")
        templates_scrollbar.grid(row=0, column=1, sticky="ns")
        
        return templates_frame
    
    def _create_models_section(self, parent):
        """Create models section"""
        models_frame = ttk.LabelFrame(parent, text="🤖 AI Models", padding=10)
        models_frame.grid_rowconfigure(2, weight=1)
        models_frame.grid_columnconfigure(0, weight=1)
        
        # Header with model preference controls
        models_header = ttk.Frame(models_frame)
        models_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Model type selection
        type_frame = ttk.Frame(models_header)
        type_frame.pack(side="left", padx=(0, 10))
        
        ttk.Label(type_frame, text="Show:", style="Info.TLabel").pack(side="left", padx=(0, 5))
        
        self.model_type_var = tk.StringVar(value="both")
        ttk.Radiobutton(type_frame, text="Free", variable=self.model_type_var, 
                       value="free", command=self._on_model_type_changed).pack(side="left", padx=(0, 5))
        ttk.Radiobutton(type_frame, text="Paid", variable=self.model_type_var, 
                       value="paid", command=self._on_model_type_changed).pack(side="left", padx=(0, 5))
        ttk.Radiobutton(type_frame, text="Both", variable=self.model_type_var, 
                       value="both", command=self._on_model_type_changed).pack(side="left")
        
        # Refresh button for dynamic detection
        refresh_frame = ttk.Frame(models_header)
        refresh_frame.pack(side="left", padx=(10, 0))
        
        ttk.Button(refresh_frame, text="� Check Free", command=self._detect_free_models,
                  width=12).pack(side="left", padx=(0, 5))
        
        # Selection controls
        select_frame = ttk.Frame(models_header)
        select_frame.pack(side="left", padx=(10, 0))
        
        ttk.Button(select_frame, text="✓ All", command=self._select_all_models, 
                  width=8).pack(side="left", padx=(0, 5))
        ttk.Button(select_frame, text="✗ None", command=self._deselect_all_models,
                  width=8).pack(side="left", padx=(0, 5))
        ttk.Button(select_frame, text="💰 Free", command=self._select_free_models,
                  width=8).pack(side="left")
        
        # Info label
        self.models_info_label = ttk.Label(models_header, text="Loading models...", 
                                         style="Info.TLabel")
        self.models_info_label.pack(side="right")
        
        # Status label for dynamic detection
        self.models_status_info = ttk.Label(models_frame, text="", style="Info.TLabel")
        self.models_status_info.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        
        # Models list
        list_frame = ttk.Frame(models_frame)
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Canvas for scrolling with fixed size constraints
        self.models_canvas = tk.Canvas(list_frame, bg="#ffffff", highlightthickness=0, 
                                      height=200, width=400)  # Set both height and width constraints
        models_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.models_canvas.yview)
        self.models_scrollable_frame = ttk.Frame(self.models_canvas)
        
        # Configure canvas to not resize
        self.models_canvas.grid_propagate(False)
        
        self.models_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.models_canvas.configure(scrollregion=self.models_canvas.bbox("all"))
        )
        
        self.models_canvas.create_window((0, 0), window=self.models_scrollable_frame, anchor="nw")
        self.models_canvas.configure(yscrollcommand=models_scrollbar.set)
        
        # Bind mouse wheel
        def _on_models_mousewheel(event):
            self.models_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.models_canvas.bind("<MouseWheel>", _on_models_mousewheel)
        
        # Bind canvas configure to maintain scrollable frame width
        def _on_canvas_configure(event):
            canvas_width = event.width
            self.models_canvas.itemconfig(self.models_canvas.find_all()[0], width=canvas_width)
        self.models_canvas.bind('<Configure>', _on_canvas_configure)
        
        self.models_canvas.grid(row=0, column=0, sticky="nsew")
        models_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Populate models
        self._populate_models_checkboxes()
        
        return models_frame
    
    def _create_control_panel(self, parent):
        """Create control panel"""
        control_frame = ttk.Frame(parent, style="Card.TFrame")
        control_frame.grid_columnconfigure(1, weight=1)
        
        # Selection summary
        summary_frame = ttk.Frame(control_frame)
        summary_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=15, pady=(15, 10))
        
        self.selection_info = ttk.Label(summary_frame, 
                                      text="Templates: 0 | Models: 0 | Total Requests: 0 | Est. Time: 0m",
                                      style="Subheading.TLabel")
        self.selection_info.pack()
        
        # Progress
        progress_frame = ttk.Frame(control_frame)
        progress_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 10))
        progress_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                          mode='determinate', length=400)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        self.progress_label = ttk.Label(progress_frame, text="Ready", style="Info.TLabel")
        self.progress_label.grid(row=0, column=1)
        
        # Control buttons
        buttons_frame = ttk.Frame(control_frame)
        buttons_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 15))
        
        self.generate_btn = ttk.Button(buttons_frame, text="🚀 Generate & Extract Code", 
                                     command=self._start_generation, style="Accent.TButton",
                                     width=25)
        self.generate_btn.pack(side="left", padx=(0, 10))
        
        ttk.Button(buttons_frame, text="⏹️ Stop", command=self._stop_generation, 
                  style="Warning.TButton", width=10).pack(side="left", padx=(0, 10))
        
        # Quick actions
        quick_frame = ttk.Frame(buttons_frame)
        quick_frame.pack(side="right")
        
        ttk.Button(quick_frame, text="🔄 Reload Models", command=self._reload_models, 
                  width=15).pack(side="left", padx=(0, 5))
        ttk.Button(quick_frame, text="📊 View Stats", command=self._show_generation_stats, 
                  width=12).pack(side="left")
        
        return control_frame
    
    def _create_log_section(self, parent):
        """Create log section"""
        log_frame = ttk.LabelFrame(parent, text="📝 Generation Log", padding=10)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(5, 10))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        # Log controls
        log_controls = ttk.Frame(log_frame)
        log_controls.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Filter options
        filter_frame = ttk.Frame(log_controls)
        filter_frame.pack(side="left")
        
        ttk.Label(filter_frame, text="Filter:").pack(side="left", padx=(0, 5))
        
        self.log_filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.log_filter_var,
                                  values=["All", "Info", "Success", "Warning", "Error"],
                                  state="readonly", width=10)
        filter_combo.pack(side="left", padx=(0, 10))
        filter_combo.bind("<<ComboboxSelected>>", self._filter_log)
        
        # Auto-scroll
        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_frame, text="Auto-scroll", 
                       variable=self.auto_scroll_var).pack(side="left", padx=(10, 0))
        
        # Actions
        actions_frame = ttk.Frame(log_controls)
        actions_frame.pack(side="right")
        
        ttk.Button(actions_frame, text="Clear", command=self._clear_log, 
                  width=8).pack(side="right", padx=(5, 0))
        ttk.Button(actions_frame, text="Save", command=self._save_log, 
                  width=8).pack(side="right")
        
        # Log text
        log_container = ttk.Frame(log_frame)
        log_container.grid(row=1, column=0, sticky="nsew")
        log_container.grid_rowconfigure(0, weight=1)
        log_container.grid_columnconfigure(0, weight=1)
        
        log_font = font.Font(family="Consolas", size=9)
        self.log_text = scrolledtext.ScrolledText(log_container, height=12, wrap=tk.WORD, 
                                                font=log_font, bg="#fafafa")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        
        # Configure tags
        self.log_text.tag_config("info", foreground="#0078d4")
        self.log_text.tag_config("success", foreground="#107c10", font=(log_font.actual()["family"], 9, "bold"))
        self.log_text.tag_config("error", foreground="#d13438", font=(log_font.actual()["family"], 9, "bold"))
        self.log_text.tag_config("warning", foreground="#ff8c00")
        self.log_text.tag_config("timestamp", foreground="#8a8886", font=(log_font.actual()["family"], 8))
    
    def _create_extraction_tab(self):
        """Create enhanced extraction tab with advanced file preview"""
        extraction_frame = ttk.Frame(self.notebook)
        self.notebook.add(extraction_frame, text="📂 Extraction & Files")
        
        extraction_frame.grid_rowconfigure(0, weight=1)
        extraction_frame.grid_columnconfigure(0, weight=1)
        
        # Create main paned window
        main_paned = ttk.PanedWindow(extraction_frame, orient=tk.HORIZONTAL)
        main_paned.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Left panel - File list and info
        left_frame = self._create_extraction_left_panel(main_paned)
        main_paned.add(left_frame, weight=1)
        
        # Right panel - File preview and details
        right_frame = self._create_extraction_right_panel(main_paned)
        main_paned.add(right_frame, weight=2)
        
        # Bottom status bar for extraction info
        self._create_extraction_status_bar(extraction_frame)
    
    def _create_extraction_left_panel(self, parent):
        """Create left panel for extraction tab with file list"""
        left_frame = ttk.Frame(parent)
        
        # Top info section
        info_frame = ttk.LabelFrame(left_frame, text="ℹ️ Extraction Information", padding=5)
        info_frame.pack(fill="x", padx=5, pady=5)
        
        info_text = """Multi-file code extraction with intelligent file detection:
• Automatically detects multiple JSX components and Python files
• Calculates HTML-JSX compatibility scores  
• Creates proper project structure with components/ folders
• Applies port configuration and tracks all changes"""
        
        ttk.Label(info_frame, text=info_text, justify="left", font=("Arial", 9)).pack(anchor="w")
        
        # File list section
        list_frame = ttk.LabelFrame(left_frame, text="📁 Extracted Files", padding=5)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Filter controls
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill="x", pady=(0, 5))
        
        ttk.Label(filter_frame, text="Filter:").pack(side="left")
        self.extraction_filter_var = tk.StringVar()
        self.extraction_filter_var.trace('w', self._apply_extraction_filter)
        ttk.Entry(filter_frame, textvariable=self.extraction_filter_var, width=15).pack(side="left", padx=5)
        
        ttk.Button(filter_frame, text="Clear", command=self._clear_extraction_filter, width=6).pack(side="left", padx=2)
        ttk.Button(filter_frame, text="Refresh", command=self._refresh_extraction_view, width=8).pack(side="right", padx=2)
        
        # File tree
        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill="both", expand=True)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        columns = ("Model", "App", "File", "Type", "Status")
        self.extraction_tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=12)
        
        self.extraction_tree.heading("#0", text="ID")
        self.extraction_tree.column("#0", width=60)
        
        for col in columns:
            self.extraction_tree.heading(col, text=col)
            if col == "Model":
                self.extraction_tree.column(col, width=200)
            elif col == "File":
                self.extraction_tree.column(col, width=180)
            elif col == "Type":
                self.extraction_tree.column(col, width=80)
            else:
                self.extraction_tree.column(col, width=80)
        
        # Scrollbars for tree
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.extraction_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.extraction_tree.xview)
        self.extraction_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.extraction_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        # Bind selection event
        self.extraction_tree.bind('<<TreeviewSelect>>', self._on_extraction_file_select)
        self.extraction_tree.bind('<Double-1>', self._open_file_in_external_editor)
        
        # Selection controls
        selection_frame = ttk.Frame(list_frame)
        selection_frame.pack(fill="x", pady=(5, 0))
        
        ttk.Button(selection_frame, text="Select All", command=self._select_all_extractions, width=10).pack(side="left", padx=2)
        ttk.Button(selection_frame, text="Select None", command=self._select_no_extractions, width=10).pack(side="left", padx=2)
        ttk.Button(selection_frame, text="Save Selected", command=self._save_selected_extractions, width=12).pack(side="right", padx=2)
        
        return left_frame
    
    def _create_extraction_right_panel(self, parent):
        """Create right panel for extraction tab with file preview"""
        right_frame = ttk.Frame(parent)
        
        # Create vertical paned window for details and preview
        right_paned = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Top section - File details
        details_frame = self._create_extraction_details_section(right_paned)
        right_paned.add(details_frame, weight=1)
        
        # Bottom section - Code preview
        preview_frame = self._create_extraction_preview_section(right_paned)
        right_paned.add(preview_frame, weight=2)
        
        return right_frame
    
    def _create_extraction_details_section(self, parent):
        """Create file details section for extraction tab"""
        details_frame = ttk.LabelFrame(parent, text="📋 File Details", padding=5)
        
        # Details grid
        details_grid = ttk.Frame(details_frame)
        details_grid.pack(fill="x", padx=5, pady=5)
        
        # Configure grid columns
        for i in range(4):
            details_grid.grid_columnconfigure(i, weight=1)
        
        # File information
        ttk.Label(details_grid, text="Model:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", padx=5)
        self.extraction_model_var = tk.StringVar()
        ttk.Label(details_grid, textvariable=self.extraction_model_var, font=("Arial", 9)).grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(details_grid, text="Provider:", font=("Arial", 9, "bold")).grid(row=0, column=2, sticky="w", padx=5)
        self.extraction_provider_var = tk.StringVar()
        ttk.Label(details_grid, textvariable=self.extraction_provider_var, font=("Arial", 9)).grid(row=0, column=3, sticky="w", padx=5)
        
        ttk.Label(details_grid, text="File Path:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w", padx=5)
        self.extraction_filepath_var = tk.StringVar()
        ttk.Label(details_grid, textvariable=self.extraction_filepath_var, font=("Arial", 9)).grid(row=1, column=1, columnspan=3, sticky="w", padx=5)
        
        ttk.Label(details_grid, text="Language:", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky="w", padx=5)
        self.extraction_language_var = tk.StringVar()
        ttk.Label(details_grid, textvariable=self.extraction_language_var, font=("Arial", 9)).grid(row=2, column=1, sticky="w", padx=5)
        
        ttk.Label(details_grid, text="File Index:", font=("Arial", 9, "bold")).grid(row=2, column=2, sticky="w", padx=5)
        self.extraction_file_index_var = tk.StringVar()
        ttk.Label(details_grid, textvariable=self.extraction_file_index_var, font=("Arial", 9)).grid(row=2, column=3, sticky="w", padx=5)
        
        # Multi-file information
        multifile_frame = ttk.LabelFrame(details_frame, text="🔗 Multi-File Information", padding=5)
        multifile_frame.pack(fill="x", padx=5, pady=5)
        
        multifile_grid = ttk.Frame(multifile_frame)
        multifile_grid.pack(fill="x")
        
        ttk.Label(multifile_grid, text="Main Component:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", padx=5)
        self.extraction_main_var = tk.StringVar()
        ttk.Label(multifile_grid, textvariable=self.extraction_main_var, font=("Arial", 9)).grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(multifile_grid, text="HTML Compatibility:", font=("Arial", 9, "bold")).grid(row=0, column=2, sticky="w", padx=5)
        self.extraction_compat_var = tk.StringVar()
        ttk.Label(multifile_grid, textvariable=self.extraction_compat_var, font=("Arial", 9)).grid(row=0, column=3, sticky="w", padx=5)
        
        # Port information
        port_frame = ttk.LabelFrame(details_frame, text="🔌 Port Configuration", padding=5)
        port_frame.pack(fill="x", padx=5, pady=5)
        
        port_grid = ttk.Frame(port_frame)
        port_grid.pack(fill="x")
        
        ttk.Label(port_grid, text="Configured Ports:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", padx=5)
        self.extraction_config_ports_var = tk.StringVar()
        ttk.Label(port_grid, textvariable=self.extraction_config_ports_var, font=("Arial", 9)).grid(row=0, column=1, columnspan=3, sticky="w", padx=5)
        
        ttk.Label(port_grid, text="Detected Ports:", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w", padx=5)
        self.extraction_detected_ports_var = tk.StringVar()
        ttk.Label(port_grid, textvariable=self.extraction_detected_ports_var, font=("Arial", 9)).grid(row=1, column=1, columnspan=3, sticky="w", padx=5)
        
        ttk.Label(port_grid, text="Replacements:", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky="w", padx=5)
        self.extraction_replacements_var = tk.StringVar()
        ttk.Label(port_grid, textvariable=self.extraction_replacements_var, font=("Arial", 9)).grid(row=2, column=1, columnspan=3, sticky="w", padx=5)
        
        return details_frame
    
    def _create_extraction_preview_section(self, parent):
        """Create code preview section for extraction tab"""
        preview_frame = ttk.LabelFrame(parent, text="🔍 Code Preview", padding=5)
        
        # Preview toolbar
        toolbar = ttk.Frame(preview_frame)
        toolbar.pack(fill="x", pady=(0, 5))
        
        # View mode controls
        ttk.Button(toolbar, text="📋 Copy Code", command=self._copy_extraction_code, width=12).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🔗 Open File", command=self._open_extraction_file, width=12).pack(side="left", padx=2)
        ttk.Button(toolbar, text="💾 Save As...", command=self._save_extraction_as, width=12).pack(side="left", padx=2)
        
        # View mode radio buttons
        self.extraction_view_mode = tk.StringVar(value="replaced")
        ttk.Radiobutton(toolbar, text="Replaced Code", variable=self.extraction_view_mode, 
                       value="replaced", command=self._update_extraction_preview).pack(side="right", padx=5)
        ttk.Radiobutton(toolbar, text="Original Code", variable=self.extraction_view_mode, 
                       value="original", command=self._update_extraction_preview).pack(side="right", padx=5)
        
        # Code statistics
        self.extraction_code_stats_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self.extraction_code_stats_var, 
                 font=("Arial", 8)).pack(side="right", padx=10)
        
        # Code preview text widget
        self.extraction_preview = scrolledtext.ScrolledText(
            preview_frame, 
            wrap="none", 
            font=("Consolas", 10),
            state="disabled",
            height=20
        )
        self.extraction_preview.pack(fill="both", expand=True)
        
        # Add syntax highlighting tags
        self._setup_extraction_syntax_highlighting()
        
        return preview_frame
    
    def _setup_extraction_syntax_highlighting(self):
        """Setup basic syntax highlighting for the extraction preview"""
        # Configure text widget tags for syntax highlighting
        self.extraction_preview.tag_configure("keyword", foreground="#0066CC", font=("Consolas", 10, "bold"))
        self.extraction_preview.tag_configure("string", foreground="#009900")
        self.extraction_preview.tag_configure("comment", foreground="#808080", font=("Consolas", 10, "italic"))
        self.extraction_preview.tag_configure("function", foreground="#CC6600", font=("Consolas", 10, "bold"))
        self.extraction_preview.tag_configure("number", foreground="#FF6600")
        self.extraction_preview.tag_configure("error", background="#FFE6E6", foreground="#CC0000")
        self.extraction_preview.tag_configure("main_component", background="#E6F3FF", foreground="#0066CC")
        
    def _create_extraction_status_bar(self, parent):
        """Create status bar for extraction tab"""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        # Extraction statistics
        self.extraction_stats_label = ttk.Label(status_frame, text="No extraction data", 
                                              font=("Arial", 9, "bold"))
        self.extraction_stats_label.pack(side="left")
        
        # File count and selection info
        self.extraction_selection_var = tk.StringVar()
        ttk.Label(status_frame, textvariable=self.extraction_selection_var,
                 font=("Arial", 9)).pack(side="right")
    
    # Enhanced Extraction Event Handlers
    def _on_extraction_file_select(self, event):
        """Handle file selection in extraction tree"""
        selection = self.extraction_tree.selection()
        if not selection:
            self._clear_extraction_selection()
            return
        
        item_id = selection[0]
        item_data = self.extraction_tree.item(item_id)
        checksum = item_data["text"].replace("#", "")
        
        # Find the corresponding code block
        selected_block = None
        for result in self.generation_results:
            for block in result.extracted_blocks:
                if block.checksum == checksum:
                    selected_block = block
                    break
            if selected_block:
                break
        
        if selected_block:
            self._display_extraction_file_details(selected_block)
        else:
            self._clear_extraction_selection()
    
    def _display_extraction_file_details(self, block: CodeBlock):
        """Display detailed information about selected file"""
        self.current_extraction_block = block
        
        # Update file details
        self.extraction_model_var.set(block.model_info.standardized_name)
        self.extraction_provider_var.set(f"{block.model_info.provider} ({'Free' if block.model_info.is_free else 'Paid'})")
        self.extraction_filepath_var.set(block.file_type or "Unknown")
        self.extraction_language_var.set(block.language.upper())
        
        # Multi-file information
        file_index_text = f"{block.file_index}" if hasattr(block, 'file_index') else "0"
        if hasattr(block, 'file_index') and block.file_index > 0:
            file_index_text += " (Multi-file)"
        self.extraction_file_index_var.set(file_index_text)
        
        main_status = "Yes" if hasattr(block, 'is_main_component') and block.is_main_component else "No"
        if hasattr(block, 'is_main_component') and block.is_main_component:
            main_status += " ⭐"
        self.extraction_main_var.set(main_status)
        
        compat_score = getattr(block, 'html_compatibility_score', 0.0)
        if compat_score > 0:
            compat_text = f"{compat_score:.2f}"
            if compat_score >= 0.8:
                compat_text += " (Excellent)"
            elif compat_score >= 0.6:
                compat_text += " (Good)"
            elif compat_score >= 0.4:
                compat_text += " (Fair)"
            else:
                compat_text += " (Poor)"
        else:
            compat_text = "N/A"
        self.extraction_compat_var.set(compat_text)
        
        # Port information
        config_ports = []
        if block.backend_port:
            config_ports.append(f"Backend: {block.backend_port}")
        if block.frontend_port:
            config_ports.append(f"Frontend: {block.frontend_port}")
        self.extraction_config_ports_var.set(" | ".join(config_ports) if config_ports else "None")
        
        detected_ports = []
        if block.detected_backend_ports:
            detected_ports.append(f"Backend: {', '.join(map(str, block.detected_backend_ports))}")
        if block.detected_frontend_ports:
            detected_ports.append(f"Frontend: {', '.join(map(str, block.detected_frontend_ports))}")
        self.extraction_detected_ports_var.set(" | ".join(detected_ports) if detected_ports else "None")
        
        if block.port_replacements:
            replacements = [f"{k}→{v}" for k, v in block.port_replacements.items()]
            self.extraction_replacements_var.set(", ".join(replacements))
        else:
            self.extraction_replacements_var.set("None")
        
        # Update preview
        self._update_extraction_preview()
        
        # Update selection info
        self.extraction_selection_var.set(f"Selected: {block.file_type} | {len(block.code)} chars")
    
    def _clear_extraction_selection(self):
        """Clear extraction selection and reset details"""
        self.current_extraction_block = None
        
        # Clear all detail variables
        for var_name in ['extraction_model_var', 'extraction_provider_var', 'extraction_filepath_var',
                        'extraction_language_var', 'extraction_file_index_var', 'extraction_main_var',
                        'extraction_compat_var', 'extraction_config_ports_var', 'extraction_detected_ports_var',
                        'extraction_replacements_var', 'extraction_code_stats_var', 'extraction_selection_var']:
            if hasattr(self, var_name):
                getattr(self, var_name).set("")
        
        # Clear preview
        self.extraction_preview.config(state='normal')
        self.extraction_preview.delete("1.0", tk.END)
        self.extraction_preview.insert("1.0", "Select a file from the list to preview its content...")
        self.extraction_preview.config(state='disabled')
    
    def _update_extraction_preview(self):
        """Update the code preview with syntax highlighting"""
        if not hasattr(self, 'current_extraction_block') or not self.current_extraction_block:
            return
        
        block = self.current_extraction_block
        
        # Get code based on view mode
        if self.extraction_view_mode.get() == "original":
            code = block.original_code if hasattr(block, 'original_code') else block.code
        else:
            code = block.get_replaced_code() if hasattr(block, 'get_replaced_code') else block.code
        
        # Update preview
        self.extraction_preview.config(state='normal')
        self.extraction_preview.delete("1.0", tk.END)
        self.extraction_preview.insert("1.0", code)
        
        # Apply syntax highlighting
        self._apply_syntax_highlighting(code, block.language)
        
        self.extraction_preview.config(state='disabled')
        
        # Update statistics
        lines = len(code.splitlines())
        chars = len(code)
        words = len(code.split())
        self.extraction_code_stats_var.set(f"Lines: {lines} | Chars: {chars} | Words: {words}")
    
    def _apply_syntax_highlighting(self, code: str, language: str):
        """Apply basic syntax highlighting to the preview"""
        language = language.lower()
        
        # Remove existing tags
        for tag in ["keyword", "string", "comment", "function", "number", "error", "main_component"]:
            self.extraction_preview.tag_delete(tag)
        
        lines = code.splitlines()
        
        # Highlight based on language
        if language in ['javascript', 'jsx', 'js']:
            self._highlight_javascript(lines)
        elif language == 'python':
            self._highlight_python(lines)
        elif language == 'html':
            self._highlight_html(lines)
        elif language == 'css':
            self._highlight_css(lines)
        elif language == 'json':
            self._highlight_json(lines)
        
        # Highlight main component indicator if applicable
        if (hasattr(self, 'current_extraction_block') and self.current_extraction_block and 
            hasattr(self.current_extraction_block, 'is_main_component') and 
            self.current_extraction_block.is_main_component):
            # Find export default or main function patterns
            for i, line in enumerate(lines, 1):
                if any(pattern in line for pattern in ['export default', 'function App', 'const App']):
                    start = f"{i}.0"
                    end = f"{i}.end"
                    self.extraction_preview.tag_add("main_component", start, end)
    
    def _highlight_javascript(self, lines):
        """Apply JavaScript/JSX syntax highlighting"""
        js_keywords = ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 
                      'import', 'export', 'from', 'default', 'class', 'extends', 'async', 'await',
                      'useState', 'useEffect', 'useContext', 'React']
        
        for i, line in enumerate(lines, 1):
            # Keywords
            for keyword in js_keywords:
                if keyword in line:
                    start_pos = 0
                    while True:
                        pos = line.find(keyword, start_pos)
                        if pos == -1:
                            break
                        if pos == 0 or not line[pos-1].isalnum():
                            start = f"{i}.{pos}"
                            end = f"{i}.{pos + len(keyword)}"
                            self.extraction_preview.tag_add("keyword", start, end)
                        start_pos = pos + 1
            
            # Strings
            import re
            for match in re.finditer(r'"[^"]*"|\'[^\']*\'|`[^`]*`', line):
                start = f"{i}.{match.start()}"
                end = f"{i}.{match.end()}"
                self.extraction_preview.tag_add("string", start, end)
            
            # Comments
            if '//' in line:
                pos = line.find('//')
                start = f"{i}.{pos}"
                end = f"{i}.end"
                self.extraction_preview.tag_add("comment", start, end)
    
    def _highlight_python(self, lines):
        """Apply Python syntax highlighting"""
        python_keywords = ['def', 'class', 'if', 'elif', 'else', 'for', 'while', 'try', 'except',
                          'import', 'from', 'return', 'yield', 'lambda', 'with', 'as', 'pass',
                          'break', 'continue', 'global', 'nonlocal', 'Flask', 'app', 'route']
        
        for i, line in enumerate(lines, 1):
            # Keywords
            for keyword in python_keywords:
                if keyword in line:
                    start_pos = 0
                    while True:
                        pos = line.find(keyword, start_pos)
                        if pos == -1:
                            break
                        if pos == 0 or not line[pos-1].isalnum():
                            start = f"{i}.{pos}"
                            end = f"{i}.{pos + len(keyword)}"
                            self.extraction_preview.tag_add("keyword", start, end)
                        start_pos = pos + 1
            
            # Strings
            import re
            for match in re.finditer(r'"[^"]*"|\'[^\']*\'|"""[^"]*"""|\'\'\'[^\']*\'\'\'', line):
                start = f"{i}.{match.start()}"
                end = f"{i}.{match.end()}"
                self.extraction_preview.tag_add("string", start, end)
            
            # Comments
            if '#' in line:
                pos = line.find('#')
                start = f"{i}.{pos}"
                end = f"{i}.end"
                self.extraction_preview.tag_add("comment", start, end)
    
    def _highlight_html(self, lines):
        """Apply HTML syntax highlighting"""
        for i, line in enumerate(lines, 1):
            # HTML tags
            import re
            for match in re.finditer(r'<[^>]*>', line):
                start = f"{i}.{match.start()}"
                end = f"{i}.{match.end()}"
                self.extraction_preview.tag_add("keyword", start, end)
            
            # Comments
            if '<!--' in line:
                start_pos = line.find('<!--')
                end_pos = line.find('-->')
                if end_pos != -1:
                    start = f"{i}.{start_pos}"
                    end = f"{i}.{end_pos + 3}"
                    self.extraction_preview.tag_add("comment", start, end)
    
    def _highlight_css(self, lines):
        """Apply CSS syntax highlighting"""
        for i, line in enumerate(lines, 1):
            # CSS properties and selectors
            if ':' in line and not line.strip().startswith('/*'):
                pos = line.find(':')
                start = f"{i}.0"
                end = f"{i}.{pos}"
                self.extraction_preview.tag_add("function", start, end)
    
    def _highlight_json(self, lines):
        """Apply JSON syntax highlighting"""
        for i, line in enumerate(lines, 1):
            # JSON strings
            import re
            for match in re.finditer(r'"[^"]*"', line):
                start = f"{i}.{match.start()}"
                end = f"{i}.{match.end()}"
                self.extraction_preview.tag_add("string", start, end)
    
    # Enhanced Extraction Filter and Selection Methods
    def _apply_extraction_filter(self, *args):
        """Apply filter to extraction tree"""
        filter_text = self.extraction_filter_var.get().lower()
        
        # Clear and repopulate tree
        for item in self.extraction_tree.get_children():
            self.extraction_tree.delete(item)
        
        # Add filtered items
        for result in self.generation_results:
            for block in result.extracted_blocks:
                if self._matches_extraction_filter(block, filter_text):
                    self._add_extraction_to_tree(block, True)  # Assume success for existing blocks
    
    def _matches_extraction_filter(self, block: CodeBlock, filter_text: str) -> bool:
        """Check if block matches filter criteria"""
        if not filter_text:
            return True
        
        searchable_text = " ".join([
            block.model_info.standardized_name.lower(),
            block.file_type.lower() if block.file_type else "",
            block.language.lower(),
            str(block.app_num)
        ])
        
        return filter_text in searchable_text
    
    def _clear_extraction_filter(self):
        """Clear extraction filter"""
        self.extraction_filter_var.set("")
        self._refresh_extraction_view()
    
    def _refresh_extraction_view(self):
        """Refresh the extraction view"""
        # Clear tree
        for item in self.extraction_tree.get_children():
            self.extraction_tree.delete(item)
        
        # Repopulate with all extraction results
        for result in self.generation_results:
            for block in result.extracted_blocks:
                self._add_extraction_to_tree(block, True)  # Assume success for existing blocks
        
        self._update_extraction_stats()
    
    def _select_all_extractions(self):
        """Select all extraction items"""
        for item in self.extraction_tree.get_children():
            self.extraction_tree.selection_add(item)
    
    def _select_no_extractions(self):
        """Clear all extraction selections"""
        self.extraction_tree.selection_remove(*self.extraction_tree.selection())
    
    def _save_selected_extractions(self):
        """Save selected extraction files"""
        selection = self.extraction_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select files to save.")
            return
        
        selected_blocks = []
        for item_id in selection:
            item_data = self.extraction_tree.item(item_id)
            checksum = item_data["text"].replace("#", "")
            
            # Find corresponding block
            for result in self.generation_results:
                for block in result.extracted_blocks:
                    if block.checksum == checksum:
                        selected_blocks.append(block)
                        break
        
        if selected_blocks:
            saved_count = 0
            for block in selected_blocks:
                if self.file_manager and self.file_manager.save_code_block(block):
                    saved_count += 1
            
            messagebox.showinfo("Save Complete", f"Saved {saved_count}/{len(selected_blocks)} files successfully.")
            self._update_extraction_stats()
    
    # Enhanced Extraction Actions
    def _copy_extraction_code(self):
        """Copy current extraction code to clipboard"""
        if not hasattr(self, 'current_extraction_block') or not self.current_extraction_block:
            messagebox.showwarning("No Selection", "Please select a file first.")
            return
        
        code = self.current_extraction_block.get_replaced_code() if hasattr(self.current_extraction_block, 'get_replaced_code') else self.current_extraction_block.code
        
        try:
            self.clipboard_clear()
            self.clipboard_append(code)
            self.update()
            messagebox.showinfo("Copied", "Code copied to clipboard!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy code: {e}")
    
    def _open_extraction_file(self):
        """Open extraction file in default system editor"""
        if not hasattr(self, 'current_extraction_block') or not self.current_extraction_block:
            messagebox.showwarning("No Selection", "Please select a file first.")
            return
        
        block = self.current_extraction_block
        if not block.file_type:
            messagebox.showwarning("No File Path", "File path not available.")
            return
        
        # Construct file path
        model_name = block.model_info.standardized_name
        file_path = self.models_dir / model_name / f"app{block.app_num}" / block.file_type
        
        if file_path.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(file_path))
                elif sys.platform == "darwin":
                    os.system(f"open '{file_path}'")
                else:
                    os.system(f"xdg-open '{file_path}'")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}")
        else:
            messagebox.showwarning("File Not Found", f"File not found: {file_path}")
    
    def _save_extraction_as(self):
        """Save current extraction as a new file"""
        if not hasattr(self, 'current_extraction_block') or not self.current_extraction_block:
            messagebox.showwarning("No Selection", "Please select a file first.")
            return
        
        block = self.current_extraction_block
        
        # Determine file extension
        ext_map = {
            'jsx': '.jsx', 'javascript': '.js', 'js': '.js',
            'python': '.py', 'html': '.html', 'css': '.css',
            'json': '.json', 'markdown': '.md', 'yaml': '.yml'
        }
        
        extension = ext_map.get(block.language.lower(), '.txt')
        
        file_path = filedialog.asksaveasfilename(
            title="Save Extraction As",
            defaultextension=extension,
            initialdir=".",
            filetypes=[
                ("All Files", "*.*"),
                (f"{block.language.upper()} Files", f"*{extension}")
            ]
        )
        
        if file_path:
            try:
                code = block.get_replaced_code() if hasattr(block, 'get_replaced_code') else block.code
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                messagebox.showinfo("Saved", f"File saved to: {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")
    
    def _open_file_in_external_editor(self, event):
        """Open selected file in external editor (double-click handler)"""
        self._open_extraction_file()
    
    def _create_extraction_results_section(self, parent):
        """Create extraction results section"""
        results_frame = ttk.LabelFrame(parent, text="📊 Extraction Results", padding=10)
        results_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)
        
        # Tree
        tree_frame = ttk.Frame(results_frame)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        columns = ("Model", "App", "File", "Ports", "Status")
        self.extraction_tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=15)
        
        self.extraction_tree.heading("#0", text="ID")
        self.extraction_tree.column("#0", width=80)
        
        for col in columns:
            self.extraction_tree.heading(col, text=col)
            if col == "Model":
                self.extraction_tree.column(col, width=250)
            elif col == "File":
                self.extraction_tree.column(col, width=200)
            else:
                self.extraction_tree.column(col, width=100)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.extraction_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.extraction_tree.xview)
        self.extraction_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.extraction_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        # Stats
        self.extraction_stats_label = ttk.Label(results_frame, text="No extraction data", 
                                              font=("Arial", 10, "bold"))
        self.extraction_stats_label.grid(row=1, column=0, pady=(10, 0))
    
    def _create_results_tab(self):
        """Create results tab"""
        results_frame = ttk.Frame(self.notebook)
        self.notebook.add(results_frame, text="📊 Results")
        
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)
        
        # Results tree
        self._create_results_tree(results_frame)
    
    def _create_results_tree(self, parent):
        """Create results tree"""
        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        columns = ("App", "Model", "Frontend", "Backend", "Files", "Time")
        self.results_tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", height=20)
        
        self.results_tree.heading("#0", text="ID")
        self.results_tree.column("#0", width=50)
        
        for col in columns:
            self.results_tree.heading(col, text=col)
            if col == "Model":
                self.results_tree.column(col, width=300)
            elif col == "App":
                self.results_tree.column(col, width=200)
            else:
                self.results_tree.column(col, width=100)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.results_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        # Controls
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=1, column=0, pady=(0, 10))
        
        ttk.Button(control_frame, text="📄 View Markdown", command=self._view_markdown, 
                  width=15).pack(side="left", padx=5)
        ttk.Button(control_frame, text="📁 Open Output", command=self._open_output_folder, 
                  width=15).pack(side="left", padx=5)
        ttk.Button(control_frame, text="🗑️ Clear Results", command=self._clear_results, 
                  width=15).pack(side="left", padx=5)
    
    def _create_analytics_tab(self):
        """Create analytics tab"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text="📊 Analytics")
        
        analytics_frame.grid_rowconfigure(1, weight=1)
        analytics_frame.grid_columnconfigure(0, weight=1)
        
        # Header
        header_frame = ttk.Frame(analytics_frame, style="Card.TFrame")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        title_container = ttk.Frame(header_frame)
        title_container.pack(fill="x", padx=15, pady=15)
        
        ttk.Label(title_container, text="Analytics & Performance Metrics", 
                 style="Heading.TLabel").pack(anchor="w")
        ttk.Label(title_container, text="View detailed statistics about your generation sessions",
                 style="Info.TLabel").pack(anchor="w", pady=(2, 0))
        
        # Content
        content_frame = ttk.Frame(analytics_frame)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        
        # Stats panel
        stats_frame = ttk.LabelFrame(content_frame, text="📈 Session Statistics", padding=15)
        stats_frame.grid(row=0, column=0, sticky="nsew")
        
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=20, wrap=tk.WORD,
                                                   font=("Consolas", 9), bg="#fafafa")
        self.stats_text.pack(fill="both", expand=True)
        self.stats_text.insert("1.0", "No analytics data available yet.\n\nStart a generation session to see statistics.")
        
        # Controls
        controls_frame = ttk.Frame(analytics_frame)
        controls_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        ttk.Button(controls_frame, text="🔄 Refresh Analytics", 
                  command=self._refresh_analytics).pack(side="left", padx=(0, 10))
        ttk.Button(controls_frame, text="📁 Export Report", 
                  command=self._export_analytics_report).pack(side="left", padx=(0, 10))
        ttk.Button(controls_frame, text="🧹 Clear Data", 
                  command=self._clear_analytics_data).pack(side="left", padx=(0, 10))
        
        # Model data controls
        model_controls_frame = ttk.Frame(analytics_frame)
        model_controls_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        ttk.Label(model_controls_frame, text="Model Data:", 
                 style="Info.TLabel").pack(side="left", padx=(0, 10))
        ttk.Button(model_controls_frame, text="🌐 Fetch Live Data", 
                  command=self._fetch_live_model_data).pack(side="left", padx=(0, 5))
        ttk.Button(model_controls_frame, text="📊 View Capabilities", 
                  command=self._view_model_capabilities).pack(side="left", padx=(0, 5))
        ttk.Button(model_controls_frame, text="📄 Open Capabilities File", 
                  command=lambda: (lambda script_dir=Path(__file__).parent: os.startfile(script_dir / "model_capabilities.json") if (script_dir / "model_capabilities.json").exists() 
                          else messagebox.showwarning("Warning", "Model capabilities file not found"))()).pack(side="left")
    
    def _create_settings_tab(self):
        """Create settings tab"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="⚙️ Settings")
        
        settings_frame.grid_columnconfigure(0, weight=1)
        
        # API Settings
        api_frame = ttk.LabelFrame(settings_frame, text="API Configuration", padding=15)
        api_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        api_frame.grid_columnconfigure(1, weight=1)
        
        # Temperature
        ttk.Label(api_frame, text="Temperature:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.temperature_var = tk.DoubleVar(value=AppConfig.DEFAULT_TEMPERATURE)
        temperature_scale = ttk.Scale(api_frame, from_=0.0, to=1.0, variable=self.temperature_var, 
                                    orient="horizontal")
        temperature_scale.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.temperature_label = ttk.Label(api_frame, text=f"{AppConfig.DEFAULT_TEMPERATURE}")
        self.temperature_label.grid(row=0, column=2)
        
        def update_temp_label(value):
            self.temperature_label.config(text=f"{float(value):.1f}")
        temperature_scale.config(command=update_temp_label)
        
        # Max Tokens
        ttk.Label(api_frame, text="Max Tokens:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(10, 0))
        self.max_tokens_var = tk.IntVar(value=AppConfig.DEFAULT_MAX_TOKENS)
        ttk.Spinbox(api_frame, from_=4000, to=32000, increment=2000, 
                   textvariable=self.max_tokens_var, width=15).grid(row=1, column=1, sticky="w", pady=(10, 0))
        
        # Export Settings
        export_frame = ttk.LabelFrame(settings_frame, text="Export Options", padding=15)
        export_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        
        self.save_markdown_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(export_frame, text="Save raw markdown files", 
                       variable=self.save_markdown_var).pack(anchor="w", pady=2)
        
        self.save_json_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(export_frame, text="Save JSON conversation export", 
                       variable=self.save_json_var).pack(anchor="w", pady=2)
        
        self.save_detailed_metadata_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(export_frame, text="Save detailed metadata & summary report", 
                       variable=self.save_detailed_metadata_var).pack(anchor="w", pady=2)
        
        self.create_index_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(export_frame, text="Create index.html for markdown files", 
                       variable=self.create_index_var).pack(anchor="w", pady=2)
        
        self.auto_extract_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(export_frame, text="Auto-extract and save code files", 
                       variable=self.auto_extract_var).pack(anchor="w", pady=2)
        
        # Rate Limiting
        rate_frame = ttk.LabelFrame(settings_frame, text="Rate Limiting", padding=15)
        rate_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        
        ttk.Label(rate_frame, text="Delay between requests (seconds):").pack(anchor="w")
        self.rate_limit_var = tk.IntVar(value=2)
        ttk.Spinbox(rate_frame, from_=1, to=30, textvariable=self.rate_limit_var, 
                   width=10).pack(anchor="w", pady=(5, 0))
        
        # Parallel Processing
        parallel_frame = ttk.LabelFrame(settings_frame, text="Parallel Processing", padding=15)
        parallel_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        
        ttk.Label(parallel_frame, text="Number of parallel workers:").pack(anchor="w")
        self.parallel_workers_var = tk.IntVar(value=self.parallel_workers)
        workers_spinbox = ttk.Spinbox(parallel_frame, 
                                     from_=AppConfig.MIN_PARALLEL_REQUESTS, 
                                     to=AppConfig.MAX_PARALLEL_REQUESTS_LIMIT,
                                     textvariable=self.parallel_workers_var, 
                                     width=10,
                                     command=self._update_parallel_workers)
        workers_spinbox.pack(anchor="w", pady=(5, 0))
        workers_spinbox.bind("<KeyRelease>", lambda e: self._update_parallel_workers())
        
        # Info label for parallel processing
        self.parallel_info_label = ttk.Label(parallel_frame, 
                                           text=f"Current: {self.parallel_workers} workers • Estimated speedup: {min(self.parallel_workers, 4):.1f}x",
                                           foreground="gray")
        self.parallel_info_label.pack(anchor="w", pady=(5, 0))
        
        # Controls
        control_frame = ttk.Frame(settings_frame)
        control_frame.grid(row=4, column=0, pady=20)
        
        ttk.Button(control_frame, text="🔄 Reload Port Config", command=self._reload_port_config, 
                  width=20).pack(side="left", padx=5)
        ttk.Button(control_frame, text="🤖 Reload Models", command=self._reload_models, 
                  width=20).pack(side="left", padx=5)
        ttk.Button(control_frame, text="🌐 Fetch Live Data", command=self._fetch_live_model_data, 
                  width=20).pack(side="left", padx=5)
        ttk.Button(control_frame, text="📊 View Capabilities", command=self._view_model_capabilities, 
                  width=20).pack(side="left", padx=5)
        ttk.Button(control_frame, text="📁 Open Models Folder", command=self._open_models_folder, 
                  width=20).pack(side="left", padx=5)
    
    def _create_status_bar(self):
        """Create status bar"""
        status_container = ttk.Frame(self, style="Card.TFrame")
        status_container.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        status_container.grid_columnconfigure(0, weight=1)
        
        status_frame = ttk.Frame(status_container)
        status_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        status_frame.grid_columnconfigure(0, weight=1)
        
        # Main status
        self.status_var = tk.StringVar(value="Ready - Welcome to OpenRouter Code Generator")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, style="Info.TLabel")
        status_label.grid(row=0, column=0, sticky="w")
        
        # Indicators
        indicators_frame = ttk.Frame(status_frame)
        indicators_frame.grid(row=0, column=1, sticky="e")
        
        self.api_status_label = ttk.Label(indicators_frame, text="API: Checking...", style="Info.TLabel")
        self.api_status_label.pack(side="right", padx=(10, 0))
        
        self.models_status_label = ttk.Label(indicators_frame, text="Models: Loading...", style="Info.TLabel")
        self.models_status_label.pack(side="right", padx=(10, 0))
        
        self.templates_status_label = ttk.Label(indicators_frame, text="Templates: Not loaded", style="Info.TLabel")
        self.templates_status_label.pack(side="right", padx=(10, 0))
    
    # UI Helper Methods
    def _populate_models_checkboxes(self):
        """Populate model checkboxes with individual free/paid toggle capability"""
        all_models = OpenRouterCodeGenerator.AVAILABLE_MODELS
        
        # Filter models based on user selection
        model_type = getattr(self, 'model_type_var', tk.StringVar(value="both")).get()
        
        # Debug logging
        logger.info(f"Populating models: {len(all_models)} total models, filter='{model_type}'")
        
        if model_type == "free":
            models = [m for m in all_models if ":free" in m]
            logger.info(f"Free models found: {len(models)}")
        elif model_type == "paid":
            models = [m for m in all_models if ":free" not in m]
            logger.info(f"Paid models found: {len(models)}")
        else:  # both
            models = all_models
            logger.info(f"All models: {len(models)}")
        
        # Clear existing
        for widget in self.models_scrollable_frame.winfo_children():
            widget.destroy()
        self.model_vars.clear()
        
        # Count free and paid models
        free_count = sum(1 for m in models if ":free" in m)
        paid_count = len(models) - free_count
        
        # Update info
        if not models:
            if model_type == "free":
                status_text = "no free models available - try 'Detect Free'"
                color = "orange"
            elif model_type == "paid":
                status_text = "no paid models available"
                color = "orange"
            else:
                status_text = "no models loaded - check models_summary.json"
                color = "red"
        else:
            filter_info = f"({model_type} only)" if model_type != "both" else ""
            status_text = f"showing {len(models)} models {filter_info}"
            color = "green"
        
        self.models_info_label.config(
            text=f"{len(models)} models (💰{free_count} free, 💳{paid_count} paid) - {status_text}",
            foreground=color
        )
        
        if not models:
            no_models_label = ttk.Label(
                self.models_scrollable_frame, 
                text=f"No {model_type} models available.\n" +
                     ("Try clicking 'Detect Free' to find free models dynamically." if model_type == "free" else
                      "Change filter to 'Both' to see all models."),
                foreground="orange",
                justify="center"
            )
            no_models_label.pack(pady=20)
            return
        
        # Group models by base name for toggle functionality
        model_groups = self._group_models_by_base(models)
        
        for i, (base_model, available_variants) in enumerate(sorted(model_groups.items())):
            var = tk.BooleanVar()
            # Auto-select based on preference
            if model_type == "free" and any(":free" in v for v in available_variants) and i < 3:
                var.set(True)
            elif model_type == "both" and i < 3 and any(":free" in v for v in available_variants):
                var.set(True)
            
            # Determine current model version to display
            preferred_model = self._get_preferred_model_version(base_model, available_variants, model_type)
            self.model_vars.append((var, preferred_model))
            
            # Create model frame with enhanced controls
            self._create_model_row(base_model, available_variants, var, preferred_model)
        
        # Update canvas scroll region after adding widgets
        self.models_scrollable_frame.update_idletasks()
        self.models_canvas.configure(scrollregion=self.models_canvas.bbox("all"))
        
        self._update_selection_info()
    
    def _group_models_by_base(self, models):
        """Group models by their base name (without :free suffix)"""
        groups = {}
        for model in models:
            base_model = model.replace(":free", "")
            if base_model not in groups:
                groups[base_model] = []
            groups[base_model].append(model)
        return groups
    
    def _get_preferred_model_version(self, base_model, available_variants, model_type):
        """Get the preferred model version based on filter and availability"""
        has_free = any(":free" in v for v in available_variants)
        has_paid = any(":free" not in v for v in available_variants)
        
        if model_type == "free" and has_free:
            return f"{base_model}:free"
        elif model_type == "paid" and has_paid:
            return base_model
        elif has_free:  # Default to free if available
            return f"{base_model}:free"
        else:
            return base_model
    
    def _create_model_row(self, base_model, available_variants, var, current_model):
        """Create an enhanced model row with toggle capability"""
        # Main container frame
        main_frame = ttk.Frame(self.models_scrollable_frame)
        main_frame.pack(fill="x", padx=5, pady=2)
        
        # Left side - checkbox and model info
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="x", expand=True)
        
        # Checkbox
        cb = ttk.Checkbutton(left_frame, variable=var, command=self._update_selection_info)
        cb.pack(side="left")
        
        # Model info display
        model_info_frame = ttk.Frame(left_frame)
        model_info_frame.pack(side="left", fill="x", expand=True, padx=(5, 0))
        
        # Provider and model name
        model_info = OpenRouterCodeGenerator.get_model_info(current_model)
        provider = model_info['provider']
        model_name = model_info['model_name']
        is_free = model_info['is_free']
        
        # Model display
        provider_label = ttk.Label(model_info_frame, text=f"{provider}/", foreground="gray", font=("Arial", 9))
        provider_label.pack(side="left")
        
        model_name_label = ttk.Label(model_info_frame, text=model_name, 
                                   foreground="green" if is_free else "blue", 
                                   font=("Arial", 9, "bold" if is_free else "normal"))
        model_name_label.pack(side="left")
        
        # Current version indicator
        version_label = ttk.Label(model_info_frame, 
                                text=" (Free)" if is_free else " (Paid)", 
                                foreground="green" if is_free else "blue", 
                                font=("Arial", 8))
        version_label.pack(side="left")
        
        # Right side - toggle controls (only if both versions exist)
        has_free = any(":free" in v for v in available_variants)
        has_paid = any(":free" not in v for v in available_variants)
        
        if has_free and has_paid:
            # Toggle button container
            toggle_frame = ttk.Frame(main_frame)
            toggle_frame.pack(side="right", padx=(10, 0))
            
            # Toggle button
            toggle_text = "→ 💳" if is_free else "→ 💰"
            toggle_button = ttk.Button(
                toggle_frame, 
                text=toggle_text,
                width=6,
                command=lambda bm=base_model: self._toggle_model_version(bm)
            )
            toggle_button.pack(side="right")
            
            # Availability indicator
            availability_text = "💰💳" if has_free and has_paid else ("💰" if has_free else "💳")
            availability_label = ttk.Label(toggle_frame, text=availability_text, font=("Arial", 8))
            availability_label.pack(side="right", padx=(0, 5))
        elif has_free:
            # Show only available as free
            free_only_frame = ttk.Frame(main_frame)
            free_only_frame.pack(side="right", padx=(10, 0))
            
            ttk.Label(free_only_frame, text="💰 only", foreground="green", font=("Arial", 8)).pack()
        elif has_paid:
            # Show only available as paid
            paid_only_frame = ttk.Frame(main_frame)
            paid_only_frame.pack(side="right", padx=(10, 0))
            
            ttk.Label(paid_only_frame, text="💳 only", foreground="blue", font=("Arial", 8)).pack()
    
    def _toggle_model_version(self, base_model):
        """Toggle between free and paid versions of a model"""
        try:
            # Find the current model entry in model_vars
            for i, (var, current_model) in enumerate(self.model_vars):
                current_base = current_model.replace(":free", "")
                if current_base == base_model:
                    # Determine new version
                    if ":free" in current_model:
                        # Switch to paid version
                        new_model = base_model
                        action = "paid"
                    else:
                        # Switch to free version
                        new_model = f"{base_model}:free"
                        action = "free"
                    
                    # Verify the new version exists
                    if new_model in OpenRouterCodeGenerator.AVAILABLE_MODELS:
                        # Update the model_vars entry
                        self.model_vars[i] = (var, new_model)
                        
                        # Log the change
                        logger.info(f"Toggled {current_model} → {new_model}")
                        
                        # Refresh the UI to show the change
                        self._populate_models_checkboxes()
                        
                        # Show brief status message
                        if hasattr(self, 'models_status_info'):
                            self.models_status_info.config(
                                text=f"Switched to {action} version: {base_model.split('/')[-1]}",
                                foreground="green"
                            )
                            # Clear the message after 3 seconds
                            self.after(3000, lambda: self.models_status_info.config(text=""))
                        
                        return True
                    else:
                        # Model version doesn't exist
                        logger.warning(f"Model version {new_model} not available")
                        if hasattr(self, 'models_status_info'):
                            self.models_status_info.config(
                                text=f"❌ {action.title()} version not available",
                                foreground="red"
                            )
                            self.after(3000, lambda: self.models_status_info.config(text=""))
                        return False
            
            logger.warning(f"Could not find model {base_model} in current selection")
            return False
            
        except Exception as e:
            logger.error(f"Error toggling model version: {e}")
            if hasattr(self, 'models_status_info'):
                self.models_status_info.config(
                    text=f"❌ Toggle failed: {str(e)[:30]}",
                    foreground="red"
                )
                self.after(3000, lambda: self.models_status_info.config(text=""))
            return False
        
        # Update canvas scroll region after adding widgets
        self.models_scrollable_frame.update_idletasks()
        self.models_canvas.configure(scrollregion=self.models_canvas.bbox("all"))
        
        self._update_selection_info()
    
    def _populate_templates_checkboxes(self):
        """Populate template checkboxes"""
        # Clear existing
        for widget in self.templates_scrollable_frame.winfo_children():
            widget.destroy()
        self.template_vars.clear()
        
        if not self.templates:
            self.templates_info_label.config(text="No templates loaded")
            return
        
        # Update info
        total_size = sum(len(t.frontend_template) + len(t.backend_template) for t in self.templates)
        size_mb = total_size / 1024 / 1024
        self.templates_info_label.config(text=f"{len(self.templates)} templates ({size_mb:.1f} MB)")
        
        for i, template in enumerate(self.templates):
            var = tk.BooleanVar()
            var.set(True)  # Select all by default
            
            self.template_vars.append((var, template))
            
            # Create frame
            frame = ttk.Frame(self.templates_scrollable_frame)
            frame.pack(fill="x", padx=5, pady=2)
            
            cb = ttk.Checkbutton(frame, variable=var, command=self._update_selection_info)
            cb.pack(side="left")
            
            # Template info
            info_frame = ttk.Frame(frame)
            info_frame.pack(side="left", fill="x", expand=True)
            
            name_label = ttk.Label(info_frame, text=f"App {template.app_num}: {template.name}", 
                                 font=("Arial", 9, "bold"))
            name_label.pack(anchor="w")
            
            # Size info
            frontend_size = len(template.frontend_template) / 1024
            backend_size = len(template.backend_template) / 1024
            size_label = ttk.Label(info_frame, 
                                 text=f"Frontend: {frontend_size:.1f}KB | Backend: {backend_size:.1f}KB", 
                                 foreground="gray", font=("Arial", 8))
            size_label.pack(anchor="w")
            
            # Requirements
            if template.requirements:
                req_text = " • ".join(template.requirements[:2])
                if len(template.requirements) > 2:
                    req_text += f" • (+{len(template.requirements)-2} more)"
                req_label = ttk.Label(info_frame, text=req_text, foreground="blue", font=("Arial", 8))
                req_label.pack(anchor="w")
        
        self._update_selection_info()
    
    def log_message(self, message: str, tag: Optional[str] = None):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        
        if tag:
            self.log_text.insert(tk.END, full_message, tag)
        else:
            self.log_text.insert(tk.END, full_message)
        
        if self.auto_scroll_var.get():
            self.log_text.see(tk.END)
        self.update_idletasks()
    
    # Event Handlers
    def _browse_templates_dir(self):
        """Browse for templates directory"""
        directory = filedialog.askdirectory(
            title="Select Templates Directory",
            initialdir=self.templates_dir_var.get()
        )
        if directory:
            self.templates_dir_var.set(directory)
            self.templates_dir = Path(directory)
    
    def _browse_output_dir(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(
            title="Select Output Directory",
            initialdir=self.output_dir_var.get()
        )
        if directory:
            self.output_dir_var.set(directory)
            self.output_dir = Path(directory)
    
    def _load_templates(self):
        """Load templates"""
        try:
            self.templates_dir = Path(self.templates_dir_var.get())
            
            if not self.templates_dir.exists():
                self.templates_dir.mkdir(parents=True)
                self.log_message(f"Created templates directory: {self.templates_dir}", "info")
                messagebox.showinfo("Info", f"Created templates directory: {self.templates_dir}\n\nPlease add your template files and reload.")
                return
            
            self.loader = AppTemplateLoader(self.templates_dir)
            self.templates = self.loader.load_templates()
            
            if not self.templates:
                messagebox.showwarning(
                    "No Templates Found",
                    f"No valid template pairs found in {self.templates_dir}\n\n"
                    "Expected file format: app_N_frontend_name.md and app_N_backend_name.md"
                )
                return
            
            self._populate_templates_checkboxes()
            self.log_message(f"✅ Loaded {len(self.templates)} templates", "success")
            self.templates_status_label.config(text=f"Templates: ✅ {len(self.templates)}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {e}")
            self.log_message(f"❌ Error loading templates: {e}", "error")
    
    def _select_all_templates(self):
        """Select all templates"""
        for var, _ in self.template_vars:
            var.set(True)
        self._update_selection_info()
    
    def _deselect_all_templates(self):
        """Deselect all templates"""
        for var, _ in self.template_vars:
            var.set(False)
        self._update_selection_info()
    
    def _select_all_models(self):
        """Select all models"""
        for var, _ in self.model_vars:
            var.set(True)
        self._update_selection_info()
    
    def _deselect_all_models(self):
        """Deselect all models"""
        for var, _ in self.model_vars:
            var.set(False)
        self._update_selection_info()
    
    def _select_free_models(self):
        """Select only free models"""
        for var, model in self.model_vars:
            var.set(":free" in model)
        self._update_selection_info()
    
    def _on_model_type_changed(self):
        """Handle model type selection change"""
        self._populate_models_checkboxes()
    
    def _detect_free_models(self):
        """Dynamically detect which of the loaded models are actually free"""
        def detection_thread():
            try:
                self.after(0, lambda: self.models_status_info.config(text="🔄 Checking loaded models for free pricing..."))
                
                # Get the current number of loaded models for reference
                base_models_count = len({model.replace(":free", "") for model in OpenRouterCodeGenerator.AVAILABLE_MODELS})
                
                self.after(0, lambda: self.log_message(f"🔍 Checking {base_models_count} loaded models against API pricing...", "info"))
                
                # Check which of our loaded models are actually free
                free_models = OpenRouterCodeGenerator.get_free_models_dynamically()
                
                if not free_models:
                    self.after(0, lambda: self.models_status_info.config(
                        text="⚠️ No free models found among loaded models", foreground="orange"))
                    return
                
                # Store the detected free models for the toggle system
                self.detected_free_models = free_models
                
                # Rebuild model list: keep all base models, add :free suffix only to confirmed free ones
                all_models = set()
                base_models = {model.replace(":free", "") for model in OpenRouterCodeGenerator.AVAILABLE_MODELS}
                
                for base_model in base_models:
                    all_models.add(base_model)  # Always add the base (paid) version
                    if base_model in free_models:
                        all_models.add(f"{base_model}:free")  # Add free version only if confirmed
                
                # Update the class variable with the refined list
                OpenRouterCodeGenerator.AVAILABLE_MODELS = sorted(all_models)
                
                final_count = len(OpenRouterCodeGenerator.AVAILABLE_MODELS)
                logger.info(f"Refined model list: {base_models_count} base models → {final_count} total models ({len(free_models)} confirmed free)")
                
                # Update UI on main thread
                self.after(0, lambda count=len(free_models): self._on_free_detection_complete(count))
                    
            except Exception as error:
                logger.error(f"Error checking model pricing: {error}")
                error_msg = f"❌ Pricing check failed: {str(error)[:50]}"
                self.after(0, lambda msg=error_msg: self.models_status_info.config(
                    text=msg, foreground="red"))
        
        # Run in background thread
        threading.Thread(target=detection_thread, daemon=True).start()
    
    def _on_free_detection_complete(self, free_count: int):
        """Handle completion of free model detection"""
        self.models_status_info.config(
            text=f"✅ Found {free_count} free models among loaded models", 
            foreground="green"
        )
        
        # Debug logging
        logger.info(f"Detection complete: {len(OpenRouterCodeGenerator.AVAILABLE_MODELS)} total models in list")
        free_models_in_list = [m for m in OpenRouterCodeGenerator.AVAILABLE_MODELS if ":free" in m]
        logger.info(f"Free models in list: {len(free_models_in_list)}")
        
        # Set the filter to show free models to make them visible
        if hasattr(self, 'model_type_var'):
            self.model_type_var.set("free")
        
        # Force multiple UI updates to ensure refresh
        self.update_idletasks()
        self._populate_models_checkboxes()
        self.update_idletasks()
        
        # Select free models after population
        self._select_free_models()
        
        # Log the result
        total_models = len(OpenRouterCodeGenerator.AVAILABLE_MODELS)
        base_models = len({model.replace(":free", "") for model in OpenRouterCodeGenerator.AVAILABLE_MODELS})
        self.log_message(f"� Pricing check complete: {base_models} loaded models → {free_count} confirmed free", "success")
        self.log_message("💡 Switching to 'Free' filter to show confirmed free models", "info")
    
    def _update_selection_info(self):
        """Update selection information"""
        if not hasattr(self, 'selection_info'):
            return
        
        selected_templates = sum(1 for var, _ in self.template_vars if var.get())
        selected_models = sum(1 for var, _ in self.model_vars if var.get())
        total_requests = selected_templates * selected_models * 2  # frontend + backend
        
        # Calculate estimated time with parallel processing
        rate_limit = self.rate_limit_var.get() if hasattr(self, 'rate_limit_var') else 2
        workers = getattr(self, 'parallel_workers', AppConfig.MAX_PARALLEL_REQUESTS)
        
        # Base time per request
        base_time_per_request = rate_limit + 3  # Rate limit + processing time
        
        # With parallel processing, effective time is reduced
        effective_workers = min(workers, total_requests)  # Can't use more workers than tasks
        parallel_efficiency = 0.8  # Account for coordination overhead
        
        if effective_workers > 1:
            estimated_time = (total_requests * base_time_per_request) / (effective_workers * parallel_efficiency)
        else:
            estimated_time = total_requests * base_time_per_request
        
        minutes = int(estimated_time) // 60
        seconds = int(estimated_time) % 60
        
        # Include parallel info in display
        parallel_info = f" | Workers: {workers}" if workers > 1 else ""
        
        self.selection_info.config(
            text=f"Templates: {selected_templates} | Models: {selected_models} | Requests: {total_requests}{parallel_info} | Est. Time: {minutes}m {seconds}s"
        )
        
        if hasattr(self, 'progress_bar'):
            self.progress_bar.config(maximum=total_requests)
    
    def _update_parallel_workers(self):
        """Update parallel workers setting"""
        try:
            new_value = self.parallel_workers_var.get()
            if AppConfig.MIN_PARALLEL_REQUESTS <= new_value <= AppConfig.MAX_PARALLEL_REQUESTS_LIMIT:
                self.parallel_workers = new_value
                
                # Update info label
                if hasattr(self, 'parallel_info_label'):
                    speedup = min(new_value, 4)  # Realistic speedup estimate
                    self.parallel_info_label.config(
                        text=f"Current: {new_value} workers • Estimated speedup: {speedup:.1f}x"
                    )
                
                # Update selection info to reflect new timing
                self._update_selection_info()
                
                self.log_message(f"⚡ Parallel workers set to {new_value}", "info")
            else:
                # Reset to valid range
                valid_value = max(AppConfig.MIN_PARALLEL_REQUESTS, 
                                min(new_value, AppConfig.MAX_PARALLEL_REQUESTS_LIMIT))
                self.parallel_workers_var.set(valid_value)
                self.parallel_workers = valid_value
                
        except (ValueError, tk.TclError):
            # Reset to current value on invalid input
            self.parallel_workers_var.set(self.parallel_workers)
    
    def _save_log(self):
        """Save log to file"""
        if not self.log_text.get(1.0, tk.END).strip():
            messagebox.showinfo("Info", "Log is empty")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Save Log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                messagebox.showinfo("Success", f"Log saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save log: {e}")
    
    def _clear_log(self):
        """Clear log"""
        self.log_text.delete(1.0, tk.END)
    
    def _filter_log(self, event=None):
        """Filter log entries - placeholder for future implementation"""
        pass
    
    def _show_generation_stats(self):
        """Show generation statistics"""
        if not self.generation_results:
            messagebox.showinfo("No Data", "No generation results available yet.\nRun a generation session first.")
            return
        
        self.notebook.select(3)  # Analytics tab
        self._refresh_analytics()
    
    def _refresh_analytics(self):
        """Refresh analytics data"""
        try:
            if self.generation_results:
                report = self._generate_analytics_report()
                self.stats_text.delete("1.0", tk.END)
                self.stats_text.insert("1.0", report)
            else:
                self.stats_text.delete("1.0", tk.END)
                self.stats_text.insert("1.0", "No analytics data available yet.\n\nStart a generation session to see statistics.")
        except Exception as e:
            logger.error(f"Error refreshing analytics: {e}")
            messagebox.showerror("Error", f"Failed to refresh analytics: {e}")
    
    def _export_analytics_report(self):
        """Export analytics report"""
        if not self.generation_results:
            messagebox.showinfo("No Data", "No data to export.")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Export Analytics Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Markdown files", "*.md"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                report = self._generate_analytics_report()
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(report)
                messagebox.showinfo("Success", f"Analytics report exported to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report: {e}")
    
    def _clear_analytics_data(self):
        """Clear analytics data"""
        if messagebox.askyesno("Confirm", "Clear all analytics data?\n\nThis cannot be undone."):
            self.generation_results.clear()
            self._refresh_analytics()
            messagebox.showinfo("Success", "Analytics data cleared.")
    
    def _generate_analytics_report(self) -> str:
        """Generate analytics report"""
        if not self.generation_results:
            return "No data available."
        
        total_generations = len(self.generation_results)
        successful_generations = sum(1 for r in self.generation_results 
                                   if r.frontend_success and r.backend_success)
        success_rate = (successful_generations / total_generations) * 100
        
        # Model performance
        model_stats = {}
        for result in self.generation_results:
            model = result.model
            if model not in model_stats:
                model_stats[model] = {"total": 0, "success": 0}
            model_stats[model]["total"] += 1
            if result.frontend_success and result.backend_success:
                model_stats[model]["success"] += 1
        
        report = f"""📊 GENERATION ANALYTICS REPORT
{'='*50}

📈 OVERVIEW
Total Generations: {total_generations}
Successful: {successful_generations}
Success Rate: {success_rate:.1f}%

🤖 MODEL PERFORMANCE
"""
        
        for model, stats in sorted(model_stats.items(), 
                                 key=lambda x: x[1]["success"]/x[1]["total"] if x[1]["total"] > 0 else 0, 
                                 reverse=True):
            model_success_rate = (stats["success"] / stats["total"]) * 100 if stats["total"] > 0 else 0
            model_display = model.replace(":", " ").replace("/", " / ")
            report += f"\n{model_display}:\n"
            report += f"  Success: {stats['success']}/{stats['total']} ({model_success_rate:.1f}%)\n"
        
        # App performance
        app_stats = {}
        for result in self.generation_results:
            app_key = f"App {result.app_num}: {result.app_name}"
            if app_key not in app_stats:
                app_stats[app_key] = {"total": 0, "success": 0}
            app_stats[app_key]["total"] += 1
            if result.frontend_success and result.backend_success:
                app_stats[app_key]["success"] += 1
        
        report += "\n\n📱 APPLICATION PERFORMANCE\n"
        for app, stats in sorted(app_stats.items(), 
                               key=lambda x: x[1]["success"]/x[1]["total"] if x[1]["total"] > 0 else 0,
                               reverse=True):
            app_success_rate = (stats["success"] / stats["total"]) * 100 if stats["total"] > 0 else 0
            report += f"\n{app}:\n"
            report += f"  Success: {stats['success']}/{stats['total']} ({app_success_rate:.1f}%)\n"
        
        report += f"\n\n📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return report
    
    # Generation Process
    def _start_generation(self):
        """Start the generation process"""
        if self.is_generating:
            messagebox.showwarning("Warning", "Generation already in progress!")
            return
        
        # Get selected templates
        selected_templates = [template for var, template in self.template_vars if var.get()]
        if not selected_templates:
            messagebox.showwarning("Warning", "Please select at least one template.")
            return
        
        # Get selected models
        selected_models = [model for var, model in self.model_vars if var.get()]
        if not selected_models:
            messagebox.showwarning("Warning", "Please select at least one model.")
            return
        
        # Calculate totals with parallel processing
        total_requests = len(selected_templates) * len(selected_models) * 2
        rate_limit = self.rate_limit_var.get()
        workers = self.parallel_workers
        
        # Calculate more accurate time estimate
        base_time_per_request = rate_limit + 3
        effective_workers = min(workers, total_requests)
        parallel_efficiency = 0.8
        
        if effective_workers > 1:
            estimated_time = (total_requests * base_time_per_request) / (effective_workers * parallel_efficiency)
        else:
            estimated_time = total_requests * base_time_per_request
        
        # Confirmation
        confirm_message = f"""🚀 Documentation Generation & Extraction Confirmation

Selected Templates: {len(selected_templates)}
Selected Models: {len(selected_models)}
Total API Requests: {total_requests}
Parallel Workers: {workers}
Estimated Time: ~{int(estimated_time)//60}m {int(estimated_time)%60}s

Output Options:
• Save Markdown: {'Yes' if self.save_markdown_var.get() else 'No'}
• Save JSON Export: {'Yes' if self.save_json_var.get() else 'No'}
• Save Detailed Metadata: {'Yes' if self.save_detailed_metadata_var.get() else 'No'}
• Auto-extract Files: {'Yes' if self.auto_extract_var.get() else 'No'}

Generation Parameters:
• Temperature: {self.temperature_var.get():.1f}
• Max Tokens: {self.max_tokens_var.get():,}
• Rate Limit: {rate_limit}s between requests

⚠️ This will make {total_requests} API requests to OpenRouter using {workers} parallel workers.
Make sure you have sufficient credits/quota.
Make sure you have sufficient credits/quota.

Do you want to proceed?"""
        
        if not messagebox.askyesno("Confirm Generation", confirm_message, icon='question'):
            return
        
        try:
            # Update config
            self.config.temperature = self.temperature_var.get()
            self.config.max_tokens = self.max_tokens_var.get()
            self.config.save_raw_markdown = self.save_markdown_var.get()
            self.config.save_json_export = self.save_json_var.get()
            
            # Initialize generator
            self.generator = OpenRouterCodeGenerator(config=self.config)
            
            # Clear previous results
            self.generation_results.clear()
            self._clear_trees()
            
            self.is_generating = True
            self.progress_var.set(0)
            self.progress_label.config(text="0%")
            self.log_message(f"🚀 Starting parallel generation with {self.parallel_workers} workers...", "info")
            
            # Start generation thread
            self.generation_thread = threading.Thread(
                target=self._generation_worker,
                args=(selected_templates, selected_models),
                daemon=True
            )
            self.generation_thread.start()
            
            # Start checking for updates
            self.after(100, self._check_generation_progress)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start generation: {e}")
            self.log_message(f"❌ Error: {e}", "error")
            self.is_generating = False
    
    def _generation_worker(self, templates, models):
        """Worker thread for parallel generation"""
        try:
            if not self.generator:
                self.generator = OpenRouterCodeGenerator(config=self.config)
            
            # Create all generation tasks
            tasks = []
            task_counter = 0
            for template in templates:
                for model in models:
                    # Frontend task
                    tasks.append(GenerationTask(
                        template=template,
                        model=model,
                        is_frontend=True,
                        task_id=f"task_{task_counter:04d}_f"
                    ))
                    task_counter += 1
                    
                    # Backend task
                    tasks.append(GenerationTask(
                        template=template,
                        model=model,
                        is_frontend=False,
                        task_id=f"task_{task_counter:04d}_b"
                    ))
                    task_counter += 1
            
            total_tasks = len(tasks)
            completed_tasks = 0
            
            self.generation_queue.put(("log", f"� Starting parallel generation with {self.parallel_workers} workers", "info"))
            self.generation_queue.put(("log", f"📊 Total tasks: {total_tasks}", "info"))
            
            # Group tasks by template/model pairs for result collection
            task_groups = {}
            for task in tasks:
                group_key = f"{task.template.app_num}_{task.model}"
                if group_key not in task_groups:
                    task_groups[group_key] = {
                        'template': task.template,
                        'model': task.model,
                        'frontend_task': None,
                        'backend_task': None,
                        'frontend_result': None,
                        'backend_result': None,
                        'frontend_stats': None,
                        'backend_stats': None
                    }
                
                if task.is_frontend:
                    task_groups[group_key]['frontend_task'] = task
                else:
                    task_groups[group_key]['backend_task'] = task
            
            # Execute tasks in parallel
            with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                # Submit all tasks
                future_to_task = {
                    executor.submit(self._execute_generation_task, task): task
                    for task in tasks
                }
                
                # Process completed tasks
                for future in as_completed(future_to_task):
                    if not self.is_generating:
                        # Cancel remaining tasks
                        for f in future_to_task:
                            f.cancel()
                        break
                    
                    task = future_to_task[future]
                    group_key = f"{task.template.app_num}_{task.model}"
                    
                    try:
                        result_content, success, stats = future.result()
                        
                        # Store results in task group
                        if task.is_frontend:
                            task_groups[group_key]['frontend_result'] = (result_content, success)
                            task_groups[group_key]['frontend_stats'] = stats
                        else:
                            task_groups[group_key]['backend_result'] = (result_content, success)
                            task_groups[group_key]['backend_stats'] = stats
                        
                        # Log completion
                        self.generation_queue.put((
                            "log", 
                            f"✅ {task.task_type.title()} completed for {task.template.name} ({task.model})",
                            "success"
                        ))
                        
                        # Log timing stats
                        if stats and stats.attempts > 1:
                            self.generation_queue.put((
                                "log", 
                                f"🔄 {task.task_type.title()}: {stats.attempts} attempts, {stats.total_duration:.1f}s total",
                                "warning"
                            ))
                        elif stats:
                            self.generation_queue.put((
                                "log", 
                                f"⏱️ {task.task_type.title()}: {stats.total_duration:.1f}s",
                                "info"
                            ))
                        
                        completed_tasks += 1
                        progress = (completed_tasks / total_tasks) * 100
                        self.generation_queue.put(("progress", progress))
                        
                        # Check if both frontend and backend are complete for this group
                        group = task_groups[group_key]
                        if (group['frontend_result'] is not None and 
                            group['backend_result'] is not None):
                            
                            # Process complete result group
                            self._process_completed_group(group)
                        
                    except Exception as e:
                        self.generation_queue.put((
                            "log", 
                            f"❌ Task failed: {task.task_type} for {task.template.name} ({task.model}): {e}",
                            "error"
                        ))
                        
                        completed_tasks += 1
                        progress = (completed_tasks / total_tasks) * 100
                        self.generation_queue.put(("progress", progress))
            
            # Final tasks
            self.generation_queue.put(("status", "Generation completed"))
            self.generation_queue.put(("log", "✅ Parallel generation and extraction completed!", "success"))
            
            # Save exports
            if self.config.save_json_export:
                self.generation_queue.put(("log", "📝 Creating JSON export...", "info"))
                self._save_json_export()
            
            if hasattr(self, 'save_detailed_metadata_var') and self.save_detailed_metadata_var.get():
                self.generation_queue.put(("log", "� Creating detailed metadata...", "info"))
                self._save_detailed_metadata(templates)
            
            if hasattr(self, 'create_index_var') and self.create_index_var.get():
                self.generation_queue.put(("log", "🌐 Creating index.html...", "info"))
                self._create_markdown_index(self.output_dir)
                
        except Exception as e:
            self.generation_queue.put(("error", str(e)))
            logger.error(f"Generation worker error: {e}", exc_info=True)
        finally:
            self.generation_queue.put(("finished",))
    
    def _execute_generation_task(self, task: GenerationTask) -> Tuple[Optional[str], bool, Optional[APICallStats]]:
        """Execute a single generation task"""
        try:
            if not self.generator:
                return None, False, None
                
            return self.generator.generate_markdown(
                task.template.frontend_template if task.is_frontend else task.template.backend_template,
                task.model,
                is_frontend=task.is_frontend,
                app_name=task.template.name,
                requirements=task.template.requirements
            )
        except Exception as e:
            logger.error(f"Task execution error for {task.task_id}: {e}")
            return None, False, None
    
    def _process_completed_group(self, group):
        """Process a completed frontend/backend pair"""
        try:
            template = group['template']
            model = group['model']
            
            frontend_markdown, frontend_success = group['frontend_result']
            backend_markdown, backend_success = group['backend_result']
            
            # Create result
            result = GenerationResult(
                app_num=template.app_num,
                app_name=template.name,
                model=model,
                frontend_markdown=frontend_markdown or "",
                backend_markdown=backend_markdown or "",
                frontend_success=frontend_success,
                backend_success=backend_success,
                timestamp=datetime.now(),
                requirements=template.requirements,
                extracted_blocks=[]
            )
            
            # Save markdown
            if self.config.save_raw_markdown:
                self._save_raw_markdown_files(result, template)
            
            # Extract code
            if hasattr(self, 'auto_extract_var') and self.auto_extract_var.get():
                self.generation_queue.put(("log", f"🔍 Extracting code blocks for {template.name} ({model})...", "info"))
                
                if frontend_markdown:
                    model_info = ModelDetector.analyze_model("temp", {"model": model})
                    frontend_blocks = self.extractor._extract_code_blocks(
                        frontend_markdown, model_info, f"msg-{template.app_num}-frontend"
                    )
                    for block in frontend_blocks:
                        block.app_num = template.app_num
                    result.extracted_blocks.extend(frontend_blocks)
                
                if backend_markdown:
                    model_info = ModelDetector.analyze_model("temp", {"model": model})
                    backend_blocks = self.extractor._extract_code_blocks(
                        backend_markdown, model_info, f"msg-{template.app_num}-backend"
                    )
                    for block in backend_blocks:
                        block.app_num = template.app_num
                    result.extracted_blocks.extend(backend_blocks)
                
                # Save files
                saved_blocks = []
                for block in result.extracted_blocks:
                    success = self.file_manager.save_code_block(block)
                    if success:
                        saved_blocks.append(block)
                    self.generation_queue.put(("extraction_result", block, success))
                
                # Create project index if files were saved
                if saved_blocks:
                    model_name = result.model.replace('/', '_').replace(':', '_')
                    self.file_manager.create_project_index(saved_blocks, model_name, template.app_num)
            
            # Update stats
            self.extraction_stats['total_blocks'] += len(result.extracted_blocks)
            
            self.generation_queue.put(("result", result))
            
        except Exception as e:
            self.generation_queue.put(("log", f"❌ Failed to process completed group: {e}", "error"))
            logger.error(f"Error processing completed group: {e}", exc_info=True)
    
    def _save_raw_markdown_files(self, result: GenerationResult, template: AppTemplate):
        """Save raw markdown files"""
        try:
            model_safe = result.model.replace('/', '_').replace(':', '_')
            model_dir = self.output_dir / model_safe
            model_dir.mkdir(parents=True, exist_ok=True)
            
            # Save frontend
            if result.frontend_markdown and result.frontend_success:
                frontend_filename = f"app_{result.app_num}_frontend_{template.name.lower().replace(' ', '_')}.md"
                frontend_path = model_dir / frontend_filename
                frontend_path.write_text(result.frontend_markdown, encoding='utf-8')
                self.generation_queue.put(("log", f"💾 Saved frontend markdown: {frontend_filename}", "success"))
            
            # Save backend
            if result.backend_markdown and result.backend_success:
                backend_filename = f"app_{result.app_num}_backend_{template.name.lower().replace(' ', '_')}.md"
                backend_path = model_dir / backend_filename
                backend_path.write_text(result.backend_markdown, encoding='utf-8')
                self.generation_queue.put(("log", f"💾 Saved backend markdown: {backend_filename}", "success"))
                
        except Exception as e:
            self.generation_queue.put(("log", f"❌ Failed to save markdown files: {e}", "error"))
    
    def _save_json_export(self):
        """Save JSON export"""
        try:
            json_data = self._create_conversation_json()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_export_{timestamp}.json"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            self.generation_queue.put(("log", f"💾 Saved JSON export: {filename}", "success"))
            
        except Exception as e:
            self.generation_queue.put(("log", f"❌ Failed to save JSON export: {e}", "error"))
    
    def _create_conversation_json(self):
        """Create conversation JSON"""
        characters = {}
        messages = {}
        
        # Get unique models
        unique_models = list(set(r.model for r in self.generation_results))
        
        for model in unique_models:
            char_id = hashlib.md5(model.encode()).hexdigest()[:12]
            
            characters[char_id] = {
                "id": char_id,
                "model": model,
                "standardized_name": model.replace(":", "_").replace("/", "_")
            }
        
        # Create messages
        for result in self.generation_results:
            char_id = hashlib.md5(result.model.encode()).hexdigest()[:12]
            
            # Frontend message
            if result.frontend_markdown:
                msg_id = f"msg-{int(time.time())}-{uuid.uuid4().hex[:8]}"
                messages[msg_id] = {
                    "characterId": char_id,
                    "content": result.frontend_markdown,
                    "metadata": {
                        "app_num": result.app_num,
                        "app_name": result.app_name,
                        "code_type": "frontend",
                        "extracted_files": len([b for b in result.extracted_blocks if b.file_type and b.file_type.startswith("frontend")])
                    }
                }
            
            # Backend message
            if result.backend_markdown:
                msg_id = f"msg-{int(time.time())}-{uuid.uuid4().hex[:8]}"
                messages[msg_id] = {
                    "characterId": char_id,
                    "content": result.backend_markdown,
                    "metadata": {
                        "app_num": result.app_num,
                        "app_name": result.app_name,
                        "code_type": "backend",
                        "extracted_files": len([b for b in result.extracted_blocks if b.file_type and b.file_type.startswith("backend")])
                    }
                }
        
        return {
            "version": "combined_app_2.0",
            "characters": characters,
            "messages": messages,
            "metadata": {
                "total_generations": len(self.generation_results),
                "total_extractions": sum(len(r.extracted_blocks) for r in self.generation_results),
                "timestamp": datetime.now().isoformat()
            }
        }
    
    def _save_detailed_metadata(self, templates):
        """Save detailed metadata"""
        try:
            metadata = self._create_detailed_metadata_json(templates)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            metadata_filename = f"metadata_detailed_{timestamp}.json"
            metadata_filepath = self.output_dir / metadata_filename
            
            with open(metadata_filepath, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            report = self._create_summary_report(templates)
            report_filename = f"summary_report_{timestamp}.md"
            report_filepath = self.output_dir / report_filename
            
            with open(report_filepath, 'w', encoding='utf-8') as f:
                f.write(report)
            
            self.generation_queue.put(("log", f"📊 Saved metadata: {metadata_filename}", "success"))
            self.generation_queue.put(("log", f"📋 Saved report: {report_filename}", "success"))
            
        except Exception as e:
            self.generation_queue.put(("log", f"❌ Failed to save metadata: {e}", "error"))
    
    def _create_detailed_metadata_json(self, templates: List[AppTemplate]) -> Dict:
        """Create detailed metadata JSON"""
        generation_start = min(r.timestamp for r in self.generation_results) if self.generation_results else datetime.now()
        generation_end = max(r.timestamp for r in self.generation_results) if self.generation_results else datetime.now()
        duration = (generation_end - generation_start).total_seconds()
        
        apps_stats = {}
        models_stats = {}
        
        for result in self.generation_results:
            # App statistics
            if result.app_num not in apps_stats:
                apps_stats[result.app_num] = {
                    "app_num": result.app_num,
                    "app_name": result.app_name,
                    "requirements": result.requirements,
                    "models_attempted": [],
                    "successful_models": [],
                    "failed_models": [],
                    "total_content_length": 0,
                    "avg_content_length": 0
                }
            
            app_stat = apps_stats[result.app_num]
            app_stat["models_attempted"].append(result.model)
            
            if result.frontend_success and result.backend_success:
                app_stat["successful_models"].append(result.model)
                app_stat["total_content_length"] += len(result.frontend_markdown) + len(result.backend_markdown)
            else:
                app_stat["failed_models"].append(result.model)
            
            # Model statistics
            if result.model not in models_stats:
                models_stats[result.model] = {
                    "model": result.model,
                    "provider": result.model.split('/')[0],
                    "is_free": ":free" in result.model,
                    "display_name": self._get_model_display_name(result.model),
                    "apps_attempted": [],
                    "successful_apps": [],
                    "failed_apps": [],
                    "total_tokens_estimated": 0,
                    "avg_response_quality": 0
                }
            
            model_stat = models_stats[result.model]
            model_stat["apps_attempted"].append(result.app_num)
            
            if result.frontend_success and result.backend_success:
                model_stat["successful_apps"].append(result.app_num)
                model_stat["total_tokens_estimated"] += len(result.frontend_markdown.split()) + len(result.backend_markdown.split())
            else:
                model_stat["failed_apps"].append(result.app_num)
        
        # Calculate averages
        for app_stat in apps_stats.values():
            if app_stat["successful_models"]:
                app_stat["avg_content_length"] = app_stat["total_content_length"] / len(app_stat["successful_models"])
                app_stat["success_rate"] = len(app_stat["successful_models"]) / len(app_stat["models_attempted"])
            else:
                app_stat["success_rate"] = 0
        
        for model_stat in models_stats.values():
            if model_stat["successful_apps"]:
                model_stat["avg_response_quality"] = model_stat["total_tokens_estimated"] / len(model_stat["successful_apps"])
                model_stat["success_rate"] = len(model_stat["successful_apps"]) / len(model_stat["apps_attempted"])
            else:
                model_stat["success_rate"] = 0
        
        return {
            "metadata_version": "2.0",
            "generation_info": {
                "start_time": generation_start.isoformat(),
                "end_time": generation_end.isoformat(),
                "duration_seconds": duration,
                "generator_version": "Combined OpenRouter Code Generator & Extractor v2.0",
                "python_version": sys.version,
                "platform": os.name
            },
            "configuration": {
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "system_prompt": self.config.system_prompt,
                "save_raw_markdown": self.config.save_raw_markdown,
                "save_json_export": self.config.save_json_export,
                "models_selected": [model for var, model in self.model_vars if var.get()]
            },
            "templates_info": [
                {
                    "app_num": template.app_num,
                    "name": template.name,
                    "frontend_template_size": len(template.frontend_template),
                    "backend_template_size": len(template.backend_template),
                    "requirements_count": len(template.requirements),
                    "requirements": template.requirements,
                    "frontend_file": str(template.frontend_file) if template.frontend_file else None,
                    "backend_file": str(template.backend_file) if template.backend_file else None
                }
                for template in templates
            ],
            "generation_summary": {
                "total_templates": len(templates),
                "total_models": len(set(r.model for r in self.generation_results)),
                "total_generations": len(self.generation_results),
                "successful_generations": sum(1 for r in self.generation_results if r.frontend_success and r.backend_success),
                "failed_generations": sum(1 for r in self.generation_results if not (r.frontend_success and r.backend_success)),
                "partial_success_generations": sum(1 for r in self.generation_results if (r.frontend_success and not r.backend_success) or (not r.frontend_success and r.backend_success)),
                "overall_success_rate": sum(1 for r in self.generation_results if r.frontend_success and r.backend_success) / len(self.generation_results) if self.generation_results else 0,
                "total_api_requests": len(self.generation_results) * 2,
                "estimated_total_cost": sum(0.05 for r in self.generation_results if ":free" not in r.model),
                "free_model_requests": sum(1 for r in self.generation_results if ":free" in r.model),
                "paid_model_requests": sum(1 for r in self.generation_results if ":free" not in r.model)
            },
            "apps_statistics": list(apps_stats.values()),
            "models_statistics": list(models_stats.values()),
            "performance_metrics": {
                "avg_generation_time_per_request": duration / (len(self.generation_results) * 2) if self.generation_results else 0,
                "fastest_model": min(models_stats.keys(), key=lambda m: models_stats[m].get("success_rate", 0)) if models_stats else None,
                "slowest_model": max(models_stats.keys(), key=lambda m: models_stats[m].get("success_rate", 0)) if models_stats else None,
                "most_successful_app": max(apps_stats.keys(), key=lambda a: apps_stats[a].get("success_rate", 0)) if apps_stats else None,
                "least_successful_app": min(apps_stats.keys(), key=lambda a: apps_stats[a].get("success_rate", 0)) if apps_stats else None
            },
            "file_outputs": {
                "markdown_files_generated": sum(1 for r in self.generation_results if r.frontend_success) + sum(1 for r in self.generation_results if r.backend_success),
                "json_export_created": self.config.save_json_export,
                "extraction_enabled": self.auto_extract_var.get(),
                "files_extracted": sum(len(r.extracted_blocks) for r in self.generation_results),
                "output_directory": str(self.output_dir)
            }
        }
    
    def _get_model_display_name(self, model: str) -> str:
        """Get display name for model"""
        name = model.split('/')[-1]
        name = name.replace(':free', ' (Free)')
        name = name.replace('-', ' ').title()
        return name
    
    def _create_summary_report(self, templates: List[AppTemplate]) -> str:
        """Create summary report"""
        if not self.generation_results:
            return "No generation results to report."
        
        total_apps = len(set(r.app_num for r in self.generation_results))
        total_models = len(set(r.model for r in self.generation_results))
        successful_generations = sum(1 for r in self.generation_results if r.frontend_success and r.backend_success)
        total_generations = len(self.generation_results)
        success_rate = (successful_generations / total_generations) * 100 if total_generations > 0 else 0
        
        free_requests = sum(1 for r in self.generation_results if ":free" in r.model)
        paid_requests = sum(1 for r in self.generation_results if ":free" not in r.model)
        estimated_cost = paid_requests * 0.05
        
        generation_start = min(r.timestamp for r in self.generation_results)
        generation_end = max(r.timestamp for r in self.generation_results)
        duration = (generation_end - generation_start).total_seconds()
        
        # Model performance
        model_stats = {}
        for result in self.generation_results:
            if result.model not in model_stats:
                model_stats[result.model] = {"total": 0, "success": 0}
            model_stats[result.model]["total"] += 1
            if result.frontend_success and result.backend_success:
                model_stats[result.model]["success"] += 1
        
        sorted_models = sorted(model_stats.items(), 
                             key=lambda x: x[1]["success"] / x[1]["total"] if x[1]["total"] > 0 else 0, 
                             reverse=True)
        
        report = f"""
# Generation Summary Report
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Generator: Combined OpenRouter Code Generator & Extractor

## Overview
- **Total Applications**: {total_apps}
- **Total Models Used**: {total_models}
- **Total Generations**: {total_generations}
- **Successful Generations**: {successful_generations}
- **Overall Success Rate**: {success_rate:.1f}%
- **Generation Duration**: {duration:.1f} seconds ({duration/60:.1f} minutes)

## Cost Analysis
- **Free Model Requests**: {free_requests}
- **Paid Model Requests**: {paid_requests}
- **Estimated Total Cost**: ${estimated_cost:.2f}

## Configuration Used
- **Temperature**: {self.config.temperature}
- **Max Tokens**: {self.config.max_tokens}
- **Auto-extraction**: {'Enabled' if self.auto_extract_var.get() else 'Disabled'}

## Model Performance
"""
        
        for model, stats in sorted_models:
            success_rate = (stats["success"] / stats["total"]) * 100 if stats["total"] > 0 else 0
            model_display = self._get_model_display_name(model)
            report += f"- **{model_display}**: {stats['success']}/{stats['total']} ({success_rate:.1f}%)\n"
        
        report += """
## Application Results
"""
        
        app_stats = {}
        for result in self.generation_results:
            if result.app_num not in app_stats:
                app_stats[result.app_num] = {
                    "name": result.app_name,
                    "total": 0,
                    "success": 0,
                    "models": []
                }
            app_stats[result.app_num]["total"] += 1
            app_stats[result.app_num]["models"].append(result.model)
            if result.frontend_success and result.backend_success:
                app_stats[result.app_num]["success"] += 1
        
        for app_num, stats in sorted(app_stats.items()):
            success_rate = (stats["success"] / stats["total"]) * 100 if stats["total"] > 0 else 0
            report += f"- **App {app_num}: {stats['name']}**: {stats['success']}/{stats['total']} ({success_rate:.1f}%)\n"
        
        if hasattr(self, 'file_manager') and self.file_manager.save_stats['files_written'] > 0:
            report += f"""
## File Extraction Statistics
- **Files Written**: {self.file_manager.save_stats['files_written']}
- **Files Failed**: {self.file_manager.save_stats['files_failed']}
- **Port Replacements**: {self.file_manager.save_stats['port_replacements']}
"""
        
        report += f"""
## Technical Details
- **Generator Version**: Combined OpenRouter Code Generator & Extractor v2.0
- **Python Version**: {sys.version.split()[0]}
- **Platform**: {os.name}
- **Total API Requests**: {len(self.generation_results) * 2}
- **Average Response Time**: {duration / (len(self.generation_results) * 2):.2f} seconds per request

---
This report was automatically generated by the Combined OpenRouter Code Generator & Extractor.
"""
        
        return report
    
    def _create_markdown_index(self, output_dir):
        """Create index.html for markdown files"""
        try:
            model_dirs = [d for d in output_dir.iterdir() if d.is_dir() and not d.name.startswith('generated_')]
            if not model_dirs:
                return
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Generated App Documentation</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        .model-section {{ margin: 20px 0; }}
        .model-header {{ background: #007bff; color: white; padding: 10px; border-radius: 4px; margin: 10px 0; }}
        .file-list {{ list-style: none; padding: 0; }}
        .file-item {{ padding: 8px; margin: 4px 0; background: #f8f9fa; border-radius: 4px; }}
        .file-item:hover {{ background: #e9ecef; }}
        a {{ color: #007bff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Generated App Documentation</h1>
        <p class="timestamp">Generated: {timestamp}</p>
"""
            
            for model_dir in sorted(model_dirs):
                if model_dir.is_dir():
                    model_name = model_dir.name.replace('_', '/').replace('/free', ' (Free)')
                    html_content += f'<div class="model-section"><h2 class="model-header">🤖 {model_name}</h2><ul class="file-list">'
                    
                    for md_file in sorted(model_dir.rglob("*.md")):
                        relative_path = md_file.relative_to(output_dir)
                        html_content += f'<li class="file-item"><a href="{relative_path}">{md_file.name}</a></li>'
                    
                    html_content += '</ul></div>'
            
            html_content += """
        </div>
    </body>
    </html>"""
            
            index_file = output_dir / "index.html"
            index_file.write_text(html_content, encoding='utf-8')
            
            self.generation_queue.put(("log", "📄 Created index.html", "success"))
            
        except Exception as e:
            self.generation_queue.put(("log", f"Failed to create index: {e}", "warning"))
    
    def _check_generation_progress(self):
        """Check generation queue for updates"""
        try:
            while True:
                try:
                    msg_type, *args = self.generation_queue.get_nowait()
                    
                    if msg_type == "progress":
                        progress = args[0]
                        self.progress_var.set(progress)
                        self.progress_label.config(text=f"{progress:.1f}%")
                    
                    elif msg_type == "status":
                        status = args[0]
                        if hasattr(self, 'status_var') and self.status_var:
                            self.status_var.set(status)
                    
                    elif msg_type == "log":
                        message, tag = args[0], args[1] if len(args) > 1 else None
                        self.log_message(message, tag)
                    
                    elif msg_type == "result":
                        result = args[0]
                        self.generation_results.append(result)
                        self._add_result_to_tree(result)
                    
                    elif msg_type == "extraction_result":
                        block, success = args[0], args[1]
                        self._add_extraction_to_tree(block, success)
                        if success:
                            self.extraction_stats['saved_blocks'] += 1
                        else:
                            self.extraction_stats['failed_blocks'] += 1
                        self._update_extraction_stats()
                    
                    elif msg_type == "error":
                        error = args[0]
                        self.log_message(f"❌ Error: {error}", "error")
                        messagebox.showerror("Generation Error", f"An error occurred: {error}")
                        self.is_generating = False
                    
                    elif msg_type == "finished":
                        self.is_generating = False
                        self.progress_var.set(100)
                        self.progress_label.config(text="100%")
                        if hasattr(self, 'status_var') and self.status_var:
                            self.status_var.set("Generation completed")
                        break
                
                except Empty:
                    break
            
            if self.is_generating:
                self.after(100, self._check_generation_progress)
                
        except Exception as e:
            logger.error(f"Error in progress check: {e}", exc_info=True)
            self.log_message(f"❌ Progress check error: {e}", "error")
    
    def _stop_generation(self):
        """Stop generation process"""
        if self.is_generating:
            response = messagebox.askyesno(
                "Stop Generation",
                "Are you sure you want to stop the generation process?"
            )
            if response:
                self.is_generating = False
                if hasattr(self, 'status_var') and self.status_var:
                    self.status_var.set("Generation stopped by user")
                self.log_message("⏹️ Generation stopped by user", "warning")
    
    # UI Update Methods
    def _add_result_to_tree(self, result: GenerationResult):
        """Add result to tree with multiple file information"""
        if not hasattr(self, 'results_tree') or self.results_tree is None:
            return
        
        model_display = result.model.replace(":free", " (Free)")
        frontend_status = "✅" if result.frontend_success else "❌"
        backend_status = "✅" if result.backend_success else "❌"
        
        # Count different file types
        jsx_files = len([b for b in result.extracted_blocks if b.language.lower() in ['jsx', 'javascript', 'js']])
        py_files = len([b for b in result.extracted_blocks if b.language.lower() == 'python'])
        html_files = len([b for b in result.extracted_blocks if b.language.lower() == 'html'])
        total_files = len(result.extracted_blocks)
        
        # Enhanced status with file counts
        files_info = f"({total_files} files: {jsx_files}jsx, {py_files}py, {html_files}html)" if total_files > 2 else ""
        
        self.results_tree.insert(
            "", "end",
            values=[
                f"App {result.app_num}",
                model_display,
                f"{frontend_status} {backend_status} {files_info}",
                result.timestamp.strftime("%H:%M:%S")
            ]
        )
        files_count = len(result.extracted_blocks)
        time_str = result.timestamp.strftime("%H:%M:%S")
        
        result_idx = len(self.generation_results) - 1
        self.results_tree.insert(
            "",
            "end",
            text=str(result_idx),
            values=(
                f"App {result.app_num}: {result.app_name}",
                model_display,
                frontend_status,
                backend_status,
                f"{files_count} files",
                time_str
            )
        )
    
    def _add_extraction_to_tree(self, block: CodeBlock, success: bool):
        """Add extraction to tree with enhanced file information"""
        model_display = block.model_info.standardized_name
        
        # Enhanced file info
        file_info = block.file_type or "Unknown"
        extra_info = []
        
        if hasattr(block, 'file_index') and block.file_index > 0:
            extra_info.append(f"#{block.file_index}")
        
        if hasattr(block, 'is_main_component') and block.is_main_component:
            extra_info.append("MAIN")
        
        if hasattr(block, 'html_compatibility_score') and block.html_compatibility_score > 0:
            extra_info.append(f"HTML:{block.html_compatibility_score:.2f}")
        
        if extra_info:
            file_info += f" ({', '.join(extra_info)})"
        
        app_display = f"App {block.app_num}"
        
        port_parts = []
        if block.backend_port:
            port_parts.append(f"B:{block.backend_port}")
        if block.frontend_port:
            port_parts.append(f"F:{block.frontend_port}")
        if block.port_replacements:
            port_parts.append(f"({len(block.port_replacements)} repl)")
        
        port_display = " ".join(port_parts) if port_parts else "No ports"
        status_display = "✅ Saved" if success else "❌ Failed"
        
        self.extraction_tree.insert(
            "",
            "end",
            text=f"#{block.checksum}",
            values=(
                model_display,
                app_display,
                file_info,  # Use enhanced file_info instead of file_display
                port_display,
                status_display
            )
        )
    
    def _update_extraction_stats(self):
        """Update extraction statistics"""
        if self.file_manager:
            stats = self.file_manager.save_stats
            self.extraction_stats_label.config(
                text=f"Files: {stats['files_written']} written, {stats['files_failed']} failed | "
                f"Port replacements: {stats['port_replacements']}"
            )
    
    def _clear_trees(self):
        """Clear all trees"""
        if hasattr(self, 'results_tree') and self.results_tree:
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
        if hasattr(self, 'extraction_tree') and self.extraction_tree:
            for item in self.extraction_tree.get_children():
                self.extraction_tree.delete(item)
    
    # Other Methods
    def _reload_port_config(self):
        """Reload port configuration"""
        if self.port_manager:
            self.port_manager.reload_configuration()
            self.log_message("🔄 Port configuration reloaded", "info")
            messagebox.showinfo("Success", "Port configuration reloaded")
    
    def _reload_models(self):
        """Reload models"""
        try:
            old_count = len(OpenRouterCodeGenerator.AVAILABLE_MODELS)
            success = OpenRouterCodeGenerator.reload_models()
            new_count = len(OpenRouterCodeGenerator.AVAILABLE_MODELS)
            
            if success and new_count > 0:
                self.log_message(f"🔄 Models reloaded: {new_count} models available", "success")
                self._populate_models_checkboxes()
                self._update_selection_info()
                if self.models_status_label:
                    self.models_status_label.config(text=f"Models: ✅ {new_count}")
                messagebox.showinfo("Success", f"Models reloaded successfully!\n\nOld count: {old_count}\nNew count: {new_count}")
            else:
                self.log_message("⚠️ No models loaded - check models_summary.json", "warning")
                self._populate_models_checkboxes()
                self._update_selection_info()
                if self.models_status_label:
                    self.models_status_label.config(text="Models: ⚠️ 0")
                messagebox.showwarning("Warning", "No models could be loaded.\nPlease check models_summary.json file.")
                
        except Exception as e:
            self.log_message(f"❌ Error reloading models: {e}", "error")
            if self.models_status_label:
                self.models_status_label.config(text="Models: ❌")
            messagebox.showerror("Error", f"Error reloading models: {e}")
    
    def _fetch_live_model_data(self):
        """Fetch live model data from OpenRouter API"""
        try:
            # Create a generator instance to use the API methods
            generator = OpenRouterCodeGenerator()
            
            self.log_message("🌐 Fetching live model data from OpenRouter API...", "info")
            
            # Fetch live data in a separate thread to avoid UI blocking
            def fetch_data():
                return generator.fetch_live_model_data()
            
            # Run in thread
            import threading
            
            def on_complete(success):
                if success:
                    self.log_message("✅ Live model data fetched and capabilities updated", "success")
                    self.log_message("📄 Enhanced model_capabilities.json file generated", "info")
                    messagebox.showinfo("Success", 
                                      "Live model data fetched successfully!\n\n" +
                                      "Features updated:\n" +
                                      "• Latest pricing information\n" +
                                      "• Current model capabilities\n" +
                                      "• Context windows and limits\n" +
                                      "• Supported parameters\n" +
                                      "• Provider information\n\n" +
                                      "Check model_capabilities.json for details.")
                else:
                    self.log_message("⚠️ Failed to fetch live model data", "warning")
                    messagebox.showwarning("Warning", 
                                         "Failed to fetch live model data.\n\n" +
                                         "This may be due to:\n" +
                                         "• Network connectivity issues\n" +
                                         "• API rate limits\n" +
                                         "• Invalid API key\n\n" +
                                         "Using cached model data instead.")
            
            def fetch_thread():
                try:
                    success = fetch_data()
                    # Schedule UI update on main thread
                    self.after(0, lambda: on_complete(success))
                except Exception as e:
                    self.log_message(f"❌ Error fetching live model data: {e}", "error")
                    self.after(0, lambda: on_complete(False))
            
            thread = threading.Thread(target=fetch_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            self.log_message(f"❌ Error initiating live data fetch: {e}", "error")
            messagebox.showerror("Error", f"Error fetching live model data: {e}")
    
    def _view_model_capabilities(self):
        """View detailed model capabilities"""
        try:
            # Use script directory instead of current working directory
            script_dir = Path(__file__).parent
            capabilities_file = script_dir / "model_capabilities.json"
            if not capabilities_file.exists():
                messagebox.showwarning("Warning", 
                                     "Model capabilities file not found.\n\n" +
                                     "Please run 'Fetch Live Data' first to generate " +
                                     "the comprehensive capabilities file.")
                return
            
            # Create a new window to display capabilities
            caps_window = tk.Toplevel(self)
            caps_window.title("Model Capabilities Viewer")
            caps_window.geometry("1000x700")
            caps_window.transient(self)
            
            # Create notebook for different views
            notebook = ttk.Notebook(caps_window)
            notebook.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Summary tab
            summary_frame = ttk.Frame(notebook)
            notebook.add(summary_frame, text="📊 Summary")
            
            summary_text = scrolledtext.ScrolledText(summary_frame, wrap=tk.WORD, 
                                                   font=("Consolas", 10))
            summary_text.pack(fill='both', expand=True, padx=5, pady=5)
            
            # Models tab
            models_frame = ttk.Frame(notebook)
            notebook.add(models_frame, text="🤖 Detailed Models")
            
            models_text = scrolledtext.ScrolledText(models_frame, wrap=tk.WORD,
                                                  font=("Consolas", 9))
            models_text.pack(fill='both', expand=True, padx=5, pady=5)
            
            # Load and display data
            with open(capabilities_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Display summary
            metadata = data.get("metadata", {})
            summary = data.get("capabilities_summary", {})
            
            summary_content = "MODEL CAPABILITIES SUMMARY\n"
            summary_content += "=" * 50 + "\n\n"
            summary_content += f"Generated: {metadata.get('generated_at', 'Unknown')}\n"
            summary_content += f"Total Models: {metadata.get('total_models', 0)}\n"
            summary_content += f"Data Source: {metadata.get('data_source', 'Unknown')}\n\n"
            
            summary_content += "FEATURE BREAKDOWN:\n"
            summary_content += f"• Free Models: {summary.get('total_free_models', 0)}\n"
            summary_content += f"• Vision Capable: {summary.get('total_vision_models', 0)}\n"
            summary_content += f"• Function Calling: {summary.get('total_function_calling_models', 0)}\n"
            summary_content += f"• Reasoning Models: {summary.get('total_reasoning_models', 0)}\n"
            summary_content += f"• Average Context: {summary.get('avg_context_window', 0):,} tokens\n\n"
            
            # Provider breakdown
            summary_content += "PROVIDER BREAKDOWN:\n"
            providers = summary.get("providers", {})
            for provider, stats in sorted(providers.items(), key=lambda x: x[1]["count"], reverse=True):
                summary_content += f"• {provider.upper()}: {stats['count']} models\n"
            
            summary_text.insert('1.0', summary_content)
            summary_text.config(state='disabled')
            
            # Display detailed models (first 50 for performance)
            models = data.get("models", {})
            models_content = "DETAILED MODEL INFORMATION\n"
            models_content += "=" * 50 + "\n\n"
            
            for i, (model_id, caps) in enumerate(models.items()):
                if i >= 50:  # Limit for performance
                    models_content += f"\n... and {len(models) - 50} more models\n"
                    break
                    
                models_content += f"{model_id}:\n"
                models_content += f"  Provider: {caps.get('provider', 'Unknown')}\n"
                models_content += f"  Context: {caps.get('context_window', 0):,} tokens\n"
                models_content += f"  Max Output: {caps.get('max_output_tokens', 0):,} tokens\n"
                
                pricing = caps.get('pricing', {})
                models_content += f"  Pricing: ${pricing.get('prompt_tokens', '0')} / ${pricing.get('completion_tokens', '0')}\n"
                
                capabilities = caps.get('capabilities', {})
                features = [k for k, v in capabilities.items() if v]
                models_content += f"  Features: {', '.join(features) if features else 'Basic'}\n\n"
            
            models_text.insert('1.0', models_content)
            models_text.config(state='disabled')
            
            # Buttons frame
            buttons_frame = ttk.Frame(caps_window)
            buttons_frame.pack(fill='x', padx=10, pady=5)
            
            ttk.Button(buttons_frame, text="📄 Open File", 
                      command=lambda: os.startfile(capabilities_file)).pack(side='left', padx=5)
            ttk.Button(buttons_frame, text="🔄 Refresh", 
                      command=lambda: self._view_model_capabilities()).pack(side='left', padx=5)
            ttk.Button(buttons_frame, text="❌ Close", 
                      command=caps_window.destroy).pack(side='right', padx=5)
            
        except Exception as e:
            self.log_message(f"❌ Error viewing model capabilities: {e}", "error")
            messagebox.showerror("Error", f"Error viewing model capabilities: {e}")
    
    def _auto_reload_models_on_startup(self):
        """Auto-reload models on startup"""
        try:
            # Use script directory instead of current working directory
            script_dir = Path(__file__).parent
            models_file = script_dir / "models_summary.json"
            success = OpenRouterCodeGenerator.reload_models()
            new_count = len(OpenRouterCodeGenerator.AVAILABLE_MODELS)
            
            if success and new_count > 0:
                self.log_message(f"✅ Auto-loaded {new_count} models from {models_file.name}", "success")
                self.log_message(f"📊 Models by provider: {self._get_provider_summary()}", "info")
                if hasattr(self, 'models_status_label') and self.models_status_label:
                    self.models_status_label.config(text=f"Models: ✅ {new_count}")
            else:
                self.log_message(f"⚠️ No models loaded - {models_file.name} not found or empty", "warning")
                if hasattr(self, 'models_status_label') and self.models_status_label:
                    self.models_status_label.config(text="Models: ⚠️ 0")
            
            if hasattr(self, 'models_scrollable_frame'):
                self._populate_models_checkboxes()
                self._update_selection_info()
            
        except Exception as e:
            self.log_message(f"❌ Error auto-loading models: {e}", "error")
            if hasattr(self, 'models_status_label') and self.models_status_label:
                self.models_status_label.config(text="Models: ❌")
    
    def _get_provider_summary(self) -> str:
        """Get provider summary"""
        providers = {}
        for model in OpenRouterCodeGenerator.AVAILABLE_MODELS:
            provider = model.split('/')[0]
            providers[provider] = providers.get(provider, 0) + 1
        
        sorted_providers = sorted(providers.items(), key=lambda x: x[1], reverse=True)[:5]
        return ", ".join([f"{p}({c})" for p, c in sorted_providers])
    
    def _open_models_folder(self):
        """Open models folder"""
        if self.models_dir.exists():
            if sys.platform == "win32":
                os.startfile(self.models_dir)
            elif sys.platform == "darwin":
                os.system(f"open '{self.models_dir}'")
            else:
                os.system(f"xdg-open '{self.models_dir}'")
    
    def _open_output_folder(self):
        """Open output folder"""
        if self.output_dir.exists():
            if sys.platform == "win32":
                os.startfile(self.output_dir)
            elif sys.platform == "darwin":
                os.system(f"open '{self.output_dir}'")
            else:
                os.system(f"xdg-open '{self.output_dir}'")
    
    def _view_markdown(self):
        """View markdown for selected result"""
        if not hasattr(self, 'results_tree') or not self.results_tree:
            messagebox.showinfo("Info", "Results tree not available")
            return
        
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a result to view")
            return
        
        item_id = selection[0]
        result_idx = int(self.results_tree.item(item_id, "text"))
        
        if 0 <= result_idx < len(self.generation_results):
            result = self.generation_results[result_idx]
            
            # Create preview window
            preview = tk.Toplevel(self)
            preview.title(f"Markdown Preview - {result.app_name} ({result.model})")
            preview.geometry("900x700")
            
            # Create notebook
            notebook = ttk.Notebook(preview)
            notebook.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Frontend tab
            if result.frontend_markdown:
                frontend_frame = ttk.Frame(notebook)
                notebook.add(frontend_frame, text="Frontend")
                
                frontend_text = scrolledtext.ScrolledText(frontend_frame, wrap=tk.WORD, font=("Consolas", 10))
                frontend_text.pack(fill="both", expand=True)
                frontend_text.insert(1.0, result.frontend_markdown)
                frontend_text.config(state="disabled")
            
            # Backend tab
            if result.backend_markdown:
                backend_frame = ttk.Frame(notebook)
                notebook.add(backend_frame, text="Backend")
                
                backend_text = scrolledtext.ScrolledText(backend_frame, wrap=tk.WORD, font=("Consolas", 10))
                backend_text.pack(fill="both", expand=True)
                backend_text.insert(1.0, result.backend_markdown)
                backend_text.config(state="disabled")
            
            # Close button
            ttk.Button(preview, text="Close", command=preview.destroy).pack(pady=10)
    
    def _clear_results(self):
        """Clear all results"""
        response = messagebox.askyesno("Confirm", "Clear all results?")
        if response:
            self.generation_results.clear()
            self._clear_trees()
            if self.file_manager:
                self.file_manager.reset_statistics()
            self._update_extraction_stats()
            self.log_message("Cleared all results", "info")

# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main application entry point"""
    try:
        logger.info("="*60)
        logger.info("Starting Combined OpenRouter Code Generator & Extractor")
        logger.info("="*60)
        
        app = CombinedApp()
        app.mainloop()
        
        logger.info("Application shutdown")
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        
        try:
            messagebox.showerror(
                "Fatal Error", 
                f"Application failed to start:\n\n{str(e)}"
            )
        except Exception:
            print(f"FATAL ERROR: {e}")
        
        raise

if __name__ == "__main__":
    main()