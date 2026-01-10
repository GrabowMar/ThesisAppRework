"""
Validation Utilities for Celery App

Provides validation functions for input data, models, and configurations.
"""

import re
from typing import Dict, List, Any, Union
from pathlib import Path

from ..constants import AnalysisType
from ..config.config_manager import get_config


def validate_model_slug(model_slug: str) -> Dict[str, Any]:
    """Validate model slug format and return validation result."""
    result = {
        'valid': False,
        'errors': [],
        'warnings': []
    }
    
    if not model_slug:
        result['errors'].append("Model slug cannot be empty")
        return result
    
    if not isinstance(model_slug, str):
        result['errors'].append("Model slug must be a string")
        return result
    
    # Check format: provider_model-name
    if '_' not in model_slug:
        result['errors'].append("Model slug must contain provider and model name separated by underscore")
        return result
    
    parts = model_slug.split('_', 1)
    provider = parts[0]
    model_name = parts[1]
    
    # Validate provider
    valid_providers = ['anthropic', 'openai', 'google', 'meta', 'microsoft', 'cohere', 'mistral']
    if provider not in valid_providers:
        result['warnings'].append(f"Unknown provider: {provider}")
    
    # Validate model name format
    if not model_name:
        result['errors'].append("Model name cannot be empty")
        return result
    
    # Check for invalid characters
    if re.search(r'[<>:"/\\|?*]', model_slug):
        result['errors'].append("Model slug contains invalid characters")
        return result
    
    if not result['errors']:
        result['valid'] = True
    
    return result


def validate_app_number(app_number: Union[str, int]) -> Dict[str, Any]:
    """Validate app number is in valid range."""
    result = {
        'valid': False,
        'errors': [],
        'value': None
    }
    
    try:
        num = int(app_number)
        result['value'] = num
        
        if num < 1:
            result['errors'].append("App number must be at least 1")
        elif num > 30:
            result['errors'].append("App number must be at most 30")
        else:
            result['valid'] = True
            
    except (ValueError, TypeError):
        result['errors'].append("App number must be a valid integer")
    
    return result


def validate_analysis_types(analysis_types: List[str]) -> Dict[str, Any]:
    """Validate list of analysis types."""
    result = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'valid_types': []
    }
    
    if not analysis_types:
        result['errors'].append("At least one analysis type must be specified")
        return result
    
    if not isinstance(analysis_types, list):
        result['errors'].append("Analysis types must be provided as a list")
        return result
    
    valid_type_values = [at.value for at in AnalysisType]
    
    for analysis_type in analysis_types:
        if not isinstance(analysis_type, str):
            result['errors'].append(f"Analysis type must be string, got {type(analysis_type)}")
            continue
        
        if analysis_type in valid_type_values:
            result['valid_types'].append(analysis_type)
        else:
            result['warnings'].append(f"Unknown analysis type: {analysis_type}")
    
    if not result['valid_types']:
        result['errors'].append("No valid analysis types found")
    else:
        result['valid'] = True
    
    return result


def validate_batch_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate batch analysis configuration."""
    result = {
        'valid': False,
        'errors': [],
        'warnings': []
    }
    
    required_fields = ['name', 'description', 'analysis_types', 'models', 'app_range']
    
    # Check required fields
    for field in required_fields:
        if field not in config:
            result['errors'].append(f"Missing required field: {field}")
    
    if result['errors']:
        return result
    
    # Validate name
    if not config['name'].strip():
        result['errors'].append("Job name cannot be empty")
    
    # Validate analysis types
    analysis_validation = validate_analysis_types(config['analysis_types'])
    if not analysis_validation['valid']:
        result['errors'].extend(analysis_validation['errors'])
        result['warnings'].extend(analysis_validation['warnings'])
    
    # Validate models
    if not isinstance(config['models'], list) or not config['models']:
        result['errors'].append("Models must be a non-empty list")
    else:
        for model in config['models']:
            model_validation = validate_model_slug(model)
            if not model_validation['valid']:
                result['errors'].extend([f"Model {model}: {error}" for error in model_validation['errors']])
    
    # Validate app range
    app_range_validation = validate_app_range(config['app_range'])
    if not app_range_validation['valid']:
        result['errors'].extend(app_range_validation['errors'])
    
    if not result['errors']:
        result['valid'] = True
    
    return result


def validate_app_range(app_range: str) -> Dict[str, Any]:
    """Validate app range string format."""
    result = {
        'valid': False,
        'errors': [],
        'parsed_apps': []
    }
    
    if not app_range:
        result['errors'].append("App range cannot be empty")
        return result
    
    if not isinstance(app_range, str):
        result['errors'].append("App range must be a string")
        return result
    
    # Handle 'all' keyword
    if app_range.strip().lower() == 'all':
        result['valid'] = True
        result['parsed_apps'] = list(range(1, 31))
        return result
    
    # Parse range/list format
    apps = set()
    parts = app_range.split(',')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        if '-' in part:
            # Range format (e.g., "1-5")
            try:
                start, end = map(int, part.split('-', 1))
                if start > end:
                    result['errors'].append(f"Invalid range {part}: start must be <= end")
                    continue
                
                for num in range(start, end + 1):
                    app_validation = validate_app_number(num)
                    if app_validation['valid']:
                        apps.add(num)
                    else:
                        result['errors'].extend([f"Range {part}: {error}" for error in app_validation['errors']])
                        
            except ValueError:
                result['errors'].append(f"Invalid range format: {part}")
        else:
            # Single number
            app_validation = validate_app_number(part)
            if app_validation['valid']:
                apps.add(app_validation['value'])
            else:
                result['errors'].extend([f"App {part}: {error}" for error in app_validation['errors']])
    
    if not apps and not result['errors']:
        result['errors'].append("No valid app numbers found in range")
    
    if not result['errors']:
        result['valid'] = True
        result['parsed_apps'] = sorted(list(apps))
    
    return result


def validate_security_tools(tools: List[str]) -> Dict[str, Any]:
    """Validate security analysis tools list."""
    result = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'valid_tools': []
    }
    
    config = get_config()
    valid_tools = config.get_valid_tools('security')
    
    if not tools:
        result['errors'].append("At least one security tool must be specified")
        return result
    
    if not isinstance(tools, list):
        result['errors'].append("Tools must be provided as a list")
        return result
    
    for tool in tools:
        if not isinstance(tool, str):
            result['errors'].append(f"Tool name must be string, got {type(tool)}")
            continue
        
        if tool in valid_tools:
            result['valid_tools'].append(tool)
        else:
            result['warnings'].append(f"Unknown security tool: {tool}")
    
    if not result['valid_tools']:
        result['errors'].append("No valid security tools found")
    else:
        result['valid'] = True
    
    return result


def validate_performance_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate performance test configuration."""
    result = {
        'valid': False,
        'errors': [],
        'warnings': []
    }
    
    # Default values
    defaults = {
        'users': 10,
        'spawn_rate': 1.0,
        'test_duration': 60,
        'test_type': 'load'
    }
    
    # Apply defaults
    for key, default_value in defaults.items():
        if key not in config:
            config[key] = default_value
    
    # Validate users
    try:
        users = int(config['users'])
        if users < 1:
            result['errors'].append("Number of users must be at least 1")
        elif users > 1000:
            result['warnings'].append("High number of users may cause performance issues")
    except (ValueError, TypeError):
        result['errors'].append("Number of users must be a valid integer")
    
    # Validate spawn rate
    try:
        spawn_rate = float(config['spawn_rate'])
        if spawn_rate <= 0:
            result['errors'].append("Spawn rate must be greater than 0")
        elif spawn_rate > 100:
            result['warnings'].append("High spawn rate may cause performance issues")
    except (ValueError, TypeError):
        result['errors'].append("Spawn rate must be a valid number")
    
    # Validate test duration
    try:
        duration = int(config['test_duration'])
        if duration < 10:
            result['errors'].append("Test duration must be at least 10 seconds")
        elif duration > 3600:
            result['warnings'].append("Long test duration may cause resource issues")
    except (ValueError, TypeError):
        result['errors'].append("Test duration must be a valid integer")
    
    # Validate test type
    valid_test_types = ['load', 'stress', 'spike', 'volume']
    if config['test_type'] not in valid_test_types:
        result['errors'].append(f"Test type must be one of: {', '.join(valid_test_types)}")
    
    if not result['errors']:
        result['valid'] = True
    
    return result


def validate_file_path(file_path: Union[str, Path], must_exist: bool = True) -> Dict[str, Any]:
    """Validate file path."""
    result = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'path': None
    }
    
    try:
        path = Path(file_path)
        result['path'] = path
        
        if must_exist and not path.exists():
            result['errors'].append(f"Path does not exist: {path}")
        elif must_exist and not path.is_file():
            result['errors'].append(f"Path is not a file: {path}")
        
        # Check for potential security issues
        path_str = str(path.resolve())
        if '..' in path_str:
            result['warnings'].append("Path contains parent directory references")
        
        if not result['errors']:
            result['valid'] = True
            
    except Exception as e:
        result['errors'].append(f"Invalid path: {e}")
    
    return result


def validate_url(url: str) -> Dict[str, Any]:
    """Validate URL format."""
    result = {
        'valid': False,
        'errors': [],
        'warnings': []
    }
    
    if not url:
        result['errors'].append("URL cannot be empty")
        return result
    
    if not isinstance(url, str):
        result['errors'].append("URL must be a string")
        return result
    
    # Basic URL pattern
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(url):
        result['errors'].append("Invalid URL format")
    else:
        result['valid'] = True
        
        # Check for potential security issues
        if 'localhost' in url.lower() or '127.0.0.1' in url:
            result['warnings'].append("URL points to localhost")
    
    return result


def sanitize_input(text: str, max_length: int = 1000, allow_html: bool = False) -> str:
    """Sanitize user input text."""
    if not isinstance(text, str):
        return ""
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length]
    
    # Remove HTML if not allowed
    if not allow_html:
        text = re.sub(r'<[^>]+>', '', text)
    
    # Remove null bytes and other control characters
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
    
    return text.strip()
