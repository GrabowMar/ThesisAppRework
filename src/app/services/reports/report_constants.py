"""
Shared constants for report generators.

Contains merged tool classification and CWE categorization data used across
AppReportGenerator, ToolReportGenerator, and report_service.
"""
from typing import Dict


# Tool classification for categorization — union of app + tool generator entries.
# Keys: tool name, Values: {category, language}
KNOWN_TOOLS: Dict[str, Dict[str, str]] = {
    # Python security
    'bandit': {'category': 'security', 'language': 'python'},
    'safety': {'category': 'security', 'language': 'python'},
    'pip-audit': {'category': 'security', 'language': 'python'},
    'semgrep': {'category': 'security', 'language': 'multi'},
    'detect-secrets': {'category': 'security', 'language': 'multi'},

    # Python quality
    'pylint': {'category': 'quality', 'language': 'python'},
    'flake8': {'category': 'quality', 'language': 'python'},
    'ruff': {'category': 'quality', 'language': 'python'},
    'mypy': {'category': 'type-checking', 'language': 'python'},
    'vulture': {'category': 'quality', 'language': 'python'},
    'radon': {'category': 'complexity', 'language': 'python'},

    # JavaScript/Node
    'eslint': {'category': 'quality', 'language': 'javascript'},
    'jshint': {'category': 'quality', 'language': 'javascript'},
    'npm-audit': {'category': 'security', 'language': 'javascript'},
    'stylelint': {'category': 'quality', 'language': 'css'},
    'html-validator': {'category': 'quality', 'language': 'html'},

    # Dynamic/Security
    'zap': {'category': 'security', 'language': 'web'},
    'zap-quick': {'category': 'security', 'language': 'web'},
    'zap-baseline': {'category': 'security', 'language': 'web'},
    'zap-full': {'category': 'security', 'language': 'web'},
    'owasp-zap': {'category': 'security', 'language': 'web'},
    'nmap': {'category': 'security', 'language': 'network'},
    'curl': {'category': 'probe', 'language': 'http'},
    'port_scan': {'category': 'security', 'language': 'network'},
    'structure': {'category': 'meta', 'language': 'multi'},

    # Performance
    'ab': {'category': 'performance', 'language': 'http'},
    'aiohttp': {'category': 'performance', 'language': 'python'},
    'locust': {'category': 'performance', 'language': 'python'},
    'artillery': {'category': 'performance', 'language': 'javascript'},

    # AI
    'ai_analysis': {'category': 'ai', 'language': 'multi'},
    'ai-analyzer': {'category': 'ai', 'language': 'multi'},
    'openrouter': {'category': 'ai', 'language': 'multi'},
}


# CWE categorization — union of app + tool generator entries (all 27 unique IDs).
CWE_CATEGORIES: Dict[str, str] = {
    # Injection
    'CWE-78': 'OS Command Injection',
    'CWE-79': 'Cross-Site Scripting (XSS)',
    'CWE-89': 'SQL Injection',
    'CWE-94': 'Code Injection',
    'CWE-95': 'Eval Injection',

    # Memory
    'CWE-119': 'Buffer Overflow',
    'CWE-125': 'Out-of-bounds Read',

    # Information exposure
    'CWE-200': 'Information Exposure',
    'CWE-532': 'Log Injection',
    'CWE-117': 'Log Forging',

    # Credentials / secrets
    'CWE-259': 'Hard-coded Password',
    'CWE-798': 'Hardcoded Credentials',
    'CWE-312': 'Cleartext Storage',

    # Crypto
    'CWE-326': 'Inadequate Encryption',
    'CWE-327': 'Weak Cryptography',
    'CWE-311': 'Missing Encryption',

    # Auth
    'CWE-284': 'Access Control',
    'CWE-287': 'Authentication Issues',
    'CWE-306': 'Missing Authentication',
    'CWE-862': 'Missing Authorization',
    'CWE-863': 'Incorrect Authorization',

    # Deserialization / upload
    'CWE-502': 'Deserialization',
    'CWE-434': 'Unrestricted Upload',

    # Other
    'CWE-22': 'Path Traversal',
    'CWE-352': 'Cross-Site Request Forgery',
    'CWE-400': 'Resource Exhaustion',
    'CWE-770': 'Allocation without Limits',
    'CWE-601': 'Open Redirect',
    'CWE-611': 'XML External Entity',
    'CWE-918': 'SSRF',
}
