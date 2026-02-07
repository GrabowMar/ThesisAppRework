"""Backend Scanner
=================

Scans generated backend code to extract API information for frontend generation.
Provides structured context about endpoints, models, and auth to inform frontend prompts.
"""

import re
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EndpointInfo:
    """Information about an API endpoint."""
    method: str
    path: str
    blueprint: str  # user, admin, auth
    requires_auth: bool = False
    requires_admin: bool = False
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'method': self.method,
            'path': self.path,
            'blueprint': self.blueprint,
            'requires_auth': self.requires_auth,
            'requires_admin': self.requires_admin,
            'description': self.description,
        }


@dataclass 
class ModelInfo:
    """Information about a database model."""
    name: str
    fields: List[str] = field(default_factory=list)
    has_to_dict: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'fields': self.fields,
            'has_to_dict': self.has_to_dict,
        }


@dataclass
class BackendScanResult:
    """Result of scanning backend code."""
    endpoints: List[EndpointInfo] = field(default_factory=list)
    models: List[ModelInfo] = field(default_factory=list)
    has_auth: bool = False
    has_admin: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'endpoints': [e.to_dict() for e in self.endpoints],
            'models': [m.to_dict() for m in self.models],
            'has_auth': self.has_auth,
            'has_admin': self.has_admin,
        }
    
    def to_frontend_context(self) -> str:
        """Generate minimal context string for frontend prompt."""
        lines = []
        
        # Group endpoints by blueprint
        auth_endpoints = [e for e in self.endpoints if e.blueprint == 'auth']
        user_endpoints = [e for e in self.endpoints if e.blueprint == 'user']
        admin_endpoints = [e for e in self.endpoints if e.blueprint == 'admin']
        
        if auth_endpoints:
            lines.append("## Auth Endpoints")
            for e in auth_endpoints:
                auth_note = ""
                lines.append(f"- {e.method} {e.path}{auth_note}")
        
        if user_endpoints:
            lines.append("\n## User API Endpoints")
            for e in user_endpoints:
                auth_note = " (auth required)" if e.requires_auth else ""
                lines.append(f"- {e.method} {e.path}{auth_note}")
        
        if admin_endpoints:
            lines.append("\n## Admin API Endpoints (admin required)")
            for e in admin_endpoints:
                lines.append(f"- {e.method} {e.path}")
        
        if self.models:
            lines.append("\n## Data Models")
            for m in self.models:
                if m.name != 'User':  # User is standard, skip
                    fields_str = ', '.join(m.fields[:5])  # First 5 fields
                    if len(m.fields) > 5:
                        fields_str += '...'
                    lines.append(f"- {m.name}: {fields_str}")
        
        return '\n'.join(lines)


class BackendScanner:
    """Scans generated backend code to extract API structure.
    
    Works with single app.py file containing all models and routes.
    """
    
    def scan(self, backend_code: Dict[str, str]) -> BackendScanResult:
        """Scan backend code dict and extract API info.
        
        Args:
            backend_code: Dict with keys like 'app' or raw code string
        
        Returns:
            BackendScanResult with extracted info
        """
        result = BackendScanResult()
        
        # Combine all code for scanning (usually just app.py)
        all_code = '\n\n'.join(backend_code.values()) if isinstance(backend_code, dict) else str(backend_code)
        
        # Scan models
        result.models = self._extract_models(all_code)
        
        # Scan endpoints from combined code
        result.endpoints = self._extract_endpoints(all_code)
        
        # Check for auth/admin
        result.has_auth = any(e.path.startswith('/api/auth') for e in result.endpoints)
        result.has_admin = any(e.path.startswith('/api/admin') for e in result.endpoints)
        
        logger.info(f"Scanned backend: {len(result.endpoints)} endpoints, {len(result.models)} models")
        
        return result
    
    def scan_raw_response(self, raw_response: str) -> BackendScanResult:
        """Scan raw LLM response text containing code blocks.
        
        Args:
            raw_response: Raw LLM output with ```python:filename blocks
            
        Returns:
            BackendScanResult
        """
        # Extract code blocks
        code_dict = self._extract_code_blocks(raw_response)
        return self.scan(code_dict)
    
    def _extract_code_blocks(self, content: str) -> Dict[str, str]:
        """Extract annotated code blocks from LLM response."""
        blocks = {}
        pattern = re.compile(
            r"```(?:python)(?::(?P<filename>[^\n\r`]+))?\s*[\r\n]+(.*?)```",
            re.DOTALL
        )
        
        for match in pattern.finditer(content or ""):
            filename = (match.group('filename') or 'main').strip().lower()
            code = (match.group(2) or '').strip()
            if code:
                # Normalize filename by removing .py extension and routes/ prefix
                # This creates consistent keys like 'app', 'models', 'main'
                key = filename.replace('.py', '').replace('routes/', '')
                blocks[key] = code
        
        return blocks
    
    def _extract_models(self, code: str) -> List[ModelInfo]:
        """Extract model class definitions."""
        models = []
        
        # Match SQLAlchemy model class patterns: class Name(db.Model):
        # Uses non-greedy matching to capture class body until next class or end
        class_pattern = re.compile(
            r'class\s+(\w+)\s*\(\s*db\.Model\s*\)\s*:(.+?)(?=\nclass\s|\Z)',
            re.DOTALL
        )
        
        for match in class_pattern.finditer(code):
            name = match.group(1)
            body = match.group(2)
            
            # Extract field names from db.Column() definitions using regex
            # Matches patterns like: field_name = db.Column(
            fields = re.findall(r'(\w+)\s*=\s*db\.Column\s*\(', body)
            
            # Check if model has a to_dict() method for JSON serialization
            has_to_dict = 'def to_dict' in body
            
            models.append(ModelInfo(
                name=name,
                fields=fields,
                has_to_dict=has_to_dict,
            ))
        
        return models
    
    def _extract_endpoints(self, code: str) -> List[EndpointInfo]:
        """Extract route definitions from code.
        
        Handles both @app.route and @blueprint.route patterns.
        """
        endpoints = []
        
        # Complex regex to match Flask route decorators:
        # Group 1: route object name ('app' or blueprint variable)
        # Group 2: URL path in quotes
        # Group 3: Optional methods list like methods=['GET', 'POST']
        route_pattern = re.compile(
            r"@(\w+)\.route\s*\(\s*['\"]([^'\"]+)['\"]"
            r"(?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?\s*\)",
            re.MULTILINE
        )
        
        for match in route_pattern.finditer(code):
            route_obj = match.group(1)  # 'app' or blueprint name
            path = match.group(2)
            methods_str = match.group(3)
            
            # Determine blueprint type from path patterns or variable names
            # Admin routes: contain '/admin' or use 'admin' blueprint
            if '/admin' in path or 'admin' in route_obj:
                blueprint = 'admin'
            # Auth routes: contain '/auth' or use 'auth' blueprint  
            elif '/auth' in path or 'auth' in route_obj:
                blueprint = 'auth'
            else:
                blueprint = 'user'
            
            # Parse HTTP methods from decorator, default to GET if not specified
            if methods_str:
                methods = [m.strip().strip("'\"") for m in methods_str.split(',')]
            else:
                methods = ['GET']
            
            # Check for authentication decorators in surrounding code context
            # Look 200 chars before and 100 chars after the route decorator
            start = max(0, match.start() - 200)
            end = min(len(code), match.end() + 100)
            context = code[start:end]
            
            # Check for common auth decorator patterns
            requires_auth = bool(re.search(r'@token_required|@login_required', context))
            requires_admin = bool(re.search(r'@admin_required', context)) or blueprint == 'admin'
            
            # Normalize path to ensure it starts with /api prefix
            if not path.startswith('/api'):
                if blueprint == 'admin':
                    # Admin routes: /api/admin/path
                    path = f'/api/admin{path}' if not path.startswith('/') else f'/api/admin{path}'
                elif blueprint == 'auth':
                    # Auth routes: /api/auth/path
                    path = f'/api/auth{path}' if not path.startswith('/') else f'/api/auth{path}'
                else:
                    # User routes: /api/path
                    path = f'/api{path}' if not path.startswith('/') else f'/api{path}'
            
            # Create endpoint info for each HTTP method
            for method in methods:
                endpoints.append(EndpointInfo(
                    method=method.upper(),
                    path=path,
                    blueprint=blueprint,
                    requires_auth=requires_auth or requires_admin,
                    requires_admin=requires_admin,
                ))
        
        return endpoints


# Singleton instance
_scanner: Optional[BackendScanner] = None


def get_backend_scanner() -> BackendScanner:
    """Get shared scanner instance."""
    global _scanner
    if _scanner is None:
        _scanner = BackendScanner()
    return _scanner


def scan_backend_code(code: Dict[str, str]) -> BackendScanResult:
    """Convenience function to scan backend code."""
    return get_backend_scanner().scan(code)


def scan_backend_response(raw_response: str) -> BackendScanResult:
    """Convenience function to scan raw LLM response."""
    return get_backend_scanner().scan_raw_response(raw_response)
