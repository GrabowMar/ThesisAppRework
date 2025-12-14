# Minimal Backend Dockerfile for Unguarded Generation Mode
# AI model is responsible for defining app structure
FROM python:3.11-slim

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements (AI-generated)
COPY requirements.txt .

# Install Python dependencies with fallback strategies
RUN echo "=== Installing dependencies ===" && \
    (pip install --no-cache-dir -r requirements.txt && echo "✓ Dependencies installed") || \
    (echo "⚠ First attempt failed, trying individually" && \
     cat requirements.txt | grep -v '^#' | grep -v '^$' | while read pkg; do \
         pip install --no-cache-dir "$pkg" || echo "⚠ Failed: $pkg"; \
     done) || \
    echo "⚠ Some dependencies may have failed"

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data && chmod 777 /app/data

# Validate main entry point exists
RUN if [ ! -f app.py ]; then \
        echo "ERROR: app.py not found" && exit 1; \
    fi && \
    python -m py_compile app.py && \
    echo "✓ Syntax check passed"

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:${FLASK_RUN_PORT:-5000}/health 2>/dev/null || \
        curl -f http://localhost:${FLASK_RUN_PORT:-5000}/ 2>/dev/null || exit 1

CMD python app.py
