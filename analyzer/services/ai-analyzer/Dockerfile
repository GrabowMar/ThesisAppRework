# AI Requirements Analyzer Container - GPT4All & OpenRouter Analysis
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching (from repo root context)
COPY services/ai-analyzer/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -u 1000 -m analyzer
USER analyzer

# Copy shared analyzer package and service code
COPY --chown=analyzer:analyzer __init__.py ./analyzer/__init__.py
COPY --chown=analyzer:analyzer shared ./analyzer/shared
COPY --chown=analyzer:analyzer services/ai-analyzer/ .

# Copy requirements templates for the new AI tools (copied from misc/requirements during build)
COPY --chown=analyzer:analyzer services/ai-analyzer/requirements_templates /app/misc/requirements

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python health_check.py

# Expose port
EXPOSE 2004

# Run the analyzer
CMD ["python", "main.py"]
