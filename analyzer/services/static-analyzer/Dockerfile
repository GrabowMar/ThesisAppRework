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
COPY analyzer/services/static-analyzer/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies globally (consolidated single install)
RUN npm install -g --no-audit --no-fund \
    eslint@8.57.0 \
    @typescript-eslint/parser@latest \
    @typescript-eslint/eslint-plugin@latest \
    eslint-plugin-security@latest \
    eslint-plugin-react@latest \
    eslint-plugin-vue@latest \
    stylelint@latest \
    stylelint-config-standard@latest \
    prettier@latest \
    html-validator-cli@latest \
    @microsoft/eslint-formatter-sarif@3.1.0 && \
    npm cache clean --force

# Set NODE_PATH so global modules are found
ENV NODE_PATH=/usr/lib/node_modules

# Create non-root user
RUN useradd -u 1000 -m analyzer
USER analyzer

# Copy shared analyzer package and service code
COPY --chown=analyzer:analyzer analyzer/__init__.py ./analyzer/__init__.py
COPY --chown=analyzer:analyzer analyzer/shared ./analyzer/shared
COPY --chown=analyzer:analyzer analyzer/services/static-analyzer/main.py .
COPY --chown=analyzer:analyzer analyzer/services/static-analyzer/health_check.py .
COPY --chown=analyzer:analyzer analyzer/services/static-analyzer/parsers.py .
COPY --chown=analyzer:analyzer analyzer/services/static-analyzer/sarif_parsers.py .
COPY --chown=analyzer:analyzer analyzer/services/static-analyzer/package.json .
COPY --chown=analyzer:analyzer analyzer/services/static-analyzer/.eslintrc.json .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python health_check.py

# Expose port
EXPOSE 2001

# Run the analyzer
CMD ["python", "main.py"]
