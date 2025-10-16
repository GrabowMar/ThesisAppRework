# Dynamic Analysis Container - Network Tools
FROM python:3.11-slim

# Install system dependencies and OWASP ZAP
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    nmap \
    openjdk-21-jre-headless \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# For now, ZAP will be called via curl commands to existing ZAP services
# This provides ZAP functionality without complex installation
# The ZapTool will handle external ZAP connections or basic security scans

# Set working directory
WORKDIR /app

# Copy requirements first for better caching (from repo root context)
COPY services/dynamic-analyzer/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -u 1000 -m analyzer

# Copy shared analyzer package and service code
COPY --chown=analyzer:analyzer __init__.py ./analyzer/__init__.py
COPY --chown=analyzer:analyzer shared ./analyzer/shared
COPY --chown=analyzer:analyzer services/dynamic-analyzer/ .

# Switch to non-root user
USER analyzer

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python health_check.py

# Expose port
EXPOSE 2002

# Run the analyzer
CMD ["python", "main.py"]
