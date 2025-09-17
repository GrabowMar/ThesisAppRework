# Performance Testing Container - Locust Load Testing
FROM python:3.11-slim

# Install Node.js for Artillery and performance tools
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    apache2-utils \
    wrk \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Artillery globally
RUN npm install -g artillery

# Set working directory
WORKDIR /app

# Copy requirements first for better caching (from repo root context)
COPY services/performance-tester/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -u 1000 -m analyzer
USER analyzer

# Copy shared analyzer package and service code
COPY --chown=analyzer:analyzer __init__.py ./analyzer/__init__.py
COPY --chown=analyzer:analyzer shared ./analyzer/shared
COPY --chown=analyzer:analyzer services/performance-tester/ .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python health_check.py

# Expose port
EXPOSE 2003

# Run the analyzer
CMD ["python", "main.py"]
