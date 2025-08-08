#!/usr/bin/env python3
"""
ANALYZER INFRASTRUCTURE USAGE GUIDE
===================================

Quick reference for using the containerized analyzer infrastructure.

ESSENTIAL COMMANDS
==================

# Start all analyzer services
python start_analyzers.py start

# Check service status  
python start_analyzers.py status

# Run comprehensive tests
python test_all_analyzers.py

# View logs from all services
python start_analyzers.py logs

# Stop all services
python start_analyzers.py stop

SERVICES OVERVIEW
=================

Port 2001: Static Analyzer    - Code quality & security analysis
Port 2002: Dynamic Analyzer   - Runtime security scanning
Port 2003: Performance Tester - Load testing & optimization  
Port 2004: AI Analyzer       - AI-powered code analysis
Port 2005: Security Analyzer  - Dedicated security tools

TESTING INDIVIDUAL SERVICES
============================

Static Analyzer:
  Message Type: "static_analysis"
  
Security Analyzer:
  Message Type: "security_analyze"
  
Dynamic Analyzer:
  Message Type: "dynamic_analysis"
  
Performance Tester:
  Message Type: "performance_test"
  
AI Analyzer:
  Message Type: "ai_analysis"

TROUBLESHOOTING
===============

Service won't start:
  docker-compose ps
  docker-compose logs [service-name]
  
Port conflicts:
  netstat -ano | findstr :200X
  
Reset everything:
  docker-compose down
  docker-compose up --build -d

For detailed documentation, see DOCUMENTATION.py
"""

if __name__ == "__main__":
    print(__doc__)
