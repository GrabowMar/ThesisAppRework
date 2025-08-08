# Analyzer Infrastructure Documentation
# ====================================
# 
# This is the comprehensive documentation for the containerized analyzer
# infrastructure used in the ThesisAppRework project.
#
# Generated on: August 8, 2025
# Version: 2.0.0

"""
ANALYZER INFRASTRUCTURE OVERVIEW
================================

The analyzer infrastructure consists of 5 containerized services that provide
comprehensive analysis of AI-generated web applications:

1. Static Analyzer (Port 2001) - Code quality and security analysis
2. Dynamic Analyzer (Port 2002) - Runtime security scanning  
3. Performance Tester (Port 2003) - Load testing and optimization
4. AI Analyzer (Port 2004) - AI-powered code analysis
5. Security Analyzer (Port 2005) - Dedicated security tools

QUICK START
===========

1. Start all services:
   python start_analyzers.py start

2. Check status:
   python start_analyzers.py status

3. Run tests:
   python test_all_analyzers.py

4. View logs:
   python start_analyzers.py logs

SERVICE DETAILS
===============

Static Analyzer (static-analyzer:2001)
--------------------------------------
Tools: Bandit, Pylint, MyPy, ESLint, Stylelint
Purpose: Multi-language static code analysis
Message Types: static_analysis, health_check, ping

Dynamic Analyzer (dynamic-analyzer:2002) 
-----------------------------------------
Tools: OWASP ZAP, Custom vulnerability scanners
Purpose: Runtime security scanning and penetration testing
Message Types: dynamic_analysis, health_check, ping

Performance Tester (performance-tester:2003)
--------------------------------------------
Tools: Apache Bench, Locust, Custom load testers
Purpose: Performance benchmarking and optimization
Message Types: performance_test, health_check, ping

AI Analyzer (ai-analyzer:2004)
------------------------------
Tools: OpenRouter API, Custom AI analysis
Purpose: AI-powered code review and pattern detection
Message Types: ai_analysis, health_check, ping
Environment: Requires OPENROUTER_API_KEY

Security Analyzer (security-analyzer:2005)
------------------------------------------
Tools: Bandit, Safety, Pylint (security focus)
Purpose: Comprehensive security vulnerability detection
Message Types: security_analyze, health_check, ping

DOCKER CONFIGURATION
====================

All services are configured with:
- Port range: 2001-2005
- Volume mounts: ../misc/models:/workspace/misc/models:ro
- Health checks: 30s intervals
- Resource limits: 1-2GB RAM per service
- Non-root users: UID 1000

API PROTOCOL
============

All services use WebSocket connections with JSON messages:

Request Format:
{
    "type": "service_analysis",
    "model_slug": "anthropic_claude-3.7-sonnet", 
    "app_number": 1,
    "source_path": "/workspace/misc/models/...",
    "options": {}
}

Response Format:
{
    "type": "service_analysis_result",
    "status": "success|error",
    "service": "service-name",
    "analysis": {...},
    "timestamp": "2025-08-08T..."
}

TESTING
=======

Primary test script: test_all_analyzers.py
- Tests all 5 services
- Validates health checks
- Performs functional analysis
- Generates comprehensive reports

Management script: start_analyzers.py
- Start/stop/restart services
- View status and logs
- Run test suites

TROUBLESHOOTING
===============

Common Issues:
1. Port conflicts: Use netstat -ano | findstr :200X to check
2. Docker issues: Check docker-compose ps and logs
3. Tool failures: Rebuild containers with --no-cache
4. Memory issues: Increase Docker resource limits

Performance:
- Analysis time: 30s-5min depending on app size and service
- Memory usage: 512MB-2GB per service during analysis
- CPU usage: 0.5-2.0 cores per service during analysis

INTEGRATION
===========

The analyzer infrastructure integrates with:
- Main Flask application via WebSocket APIs
- Database for model/application targeting
- Docker Compose for orchestration
- Redis for caching and task queues

File Structure:
analyzer/
├── docker-compose.yml           # Main orchestration
├── start_analyzers.py          # Management script
├── test_all_analyzers.py       # Test suite
└── services/                   # Individual services
    ├── static-analyzer/        
    ├── dynamic-analyzer/
    ├── performance-tester/
    ├── ai-analyzer/
    └── security-analyzer/

SECURITY
========

Security measures implemented:
- Container isolation with non-root users
- Read-only source code mounts
- Resource limits to prevent DoS
- Secure API key handling for AI services
- Network isolation between services

MONITORING
==========

Health monitoring includes:
- WebSocket connectivity checks
- Tool availability verification
- Resource usage monitoring
- Analysis result validation
- Container health status

For detailed logs:
docker-compose logs -f [service-name]

DEVELOPMENT
===========

To modify a service:
1. Edit the main.py in services/[service]/
2. Update requirements.txt if needed
3. Rebuild: docker-compose build [service]
4. Test: python test_all_analyzers.py

To add a new analyzer:
1. Create services/[new-service]/ directory
2. Add Dockerfile, main.py, requirements.txt
3. Update docker-compose.yml
4. Add to test suite

PERFORMANCE BENCHMARKS
======================

Typical analysis times for AI-generated applications:

Small App (< 10 files):
- Static: 30-60s
- Security: 15-30s  
- Dynamic: 2-5min
- Performance: 1-2min
- AI: 30-90s

Medium App (10-50 files):
- Static: 1-3min
- Security: 30-90s
- Dynamic: 3-8min  
- Performance: 2-5min
- AI: 1-3min

Large App (50+ files):
- Static: 3-5min
- Security: 1-3min
- Dynamic: 5-15min
- Performance: 3-8min  
- AI: 2-5min

CHANGELOG
=========

Version 2.0.0 (August 8, 2025):
- Complete containerized infrastructure
- All 5 analyzer services implemented
- Comprehensive test suite
- Management tools and documentation

Version 1.0.0 (December 19, 2024):
- Initial security analyzer implementation
- Basic WebSocket infrastructure
- Proof of concept validation

"""

# This file serves as both documentation and can be imported for constants
ANALYZER_SERVICES = {
    'static-analyzer': {
        'port': 2001,
        'url': 'ws://localhost:2001',
        'tools': ['bandit', 'pylint', 'mypy', 'eslint', 'stylelint'],
        'message_types': ['static_analysis', 'health_check', 'ping']
    },
    'dynamic-analyzer': {
        'port': 2002,
        'url': 'ws://localhost:2002', 
        'tools': ['owasp-zap', 'vulnerability-scanner'],
        'message_types': ['dynamic_analysis', 'health_check', 'ping']
    },
    'performance-tester': {
        'port': 2003,
        'url': 'ws://localhost:2003',
        'tools': ['apache-bench', 'locust', 'load-tester'],
        'message_types': ['performance_test', 'health_check', 'ping']
    },
    'ai-analyzer': {
        'port': 2004,
        'url': 'ws://localhost:2004',
        'tools': ['openrouter-api', 'ai-analysis'],
        'message_types': ['ai_analysis', 'health_check', 'ping']
    },
    'security-analyzer': {
        'port': 2005,
        'url': 'ws://localhost:2005',
        'tools': ['bandit', 'safety', 'pylint'],
        'message_types': ['security_analyze', 'health_check', 'ping']
    }
}

ANALYSIS_TIMEOUTS = {
    'static_analysis': 300,     # 5 minutes
    'security_analyze': 180,    # 3 minutes
    'dynamic_analysis': 600,    # 10 minutes
    'performance_test': 300,    # 5 minutes
    'ai_analysis': 180          # 3 minutes
}

RESOURCE_LIMITS = {
    'memory': '2G',
    'cpu': '1.0',
    'analysis_timeout': 600,
    'max_file_size': '100MB'
}

if __name__ == "__main__":
    print(__doc__)
