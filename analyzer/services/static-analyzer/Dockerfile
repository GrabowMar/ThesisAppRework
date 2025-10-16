# Static Analysis Container - Frontend & Backend Security/Quality
FROM python:3.11-slim

# Install Node.js for frontend analysis
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching (from repo root context)
COPY services/static-analyzer/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies globally
RUN npm install -g \
    eslint \
    @typescript-eslint/parser \
    @typescript-eslint/eslint-plugin \
    eslint-plugin-security \
    eslint-plugin-react \
    eslint-plugin-vue \
    stylelint \
    stylelint-config-standard \
    jshint \
    snyk \
    prettier \
    csslint

# Create non-root user
RUN useradd -u 1000 -m analyzer
USER analyzer

# Copy shared analyzer package and service code
COPY --chown=analyzer:analyzer __init__.py ./analyzer/__init__.py
COPY --chown=analyzer:analyzer shared ./analyzer/shared
COPY --chown=analyzer:analyzer services/static-analyzer/ .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python health_check.py

# Expose port
EXPOSE 2001

# Run the analyzer
CMD ["python", "main.py"]
