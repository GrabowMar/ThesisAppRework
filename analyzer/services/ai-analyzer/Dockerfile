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
COPY analyzer/services/ai-analyzer/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -u 1000 -m analyzer
USER analyzer

# Copy shared analyzer package and service code
COPY --chown=analyzer:analyzer analyzer/__init__.py ./analyzer/__init__.py
COPY --chown=analyzer:analyzer analyzer/shared ./analyzer/shared
COPY --chown=analyzer:analyzer analyzer/services/ai-analyzer/main.py .
COPY --chown=analyzer:analyzer analyzer/services/ai-analyzer/health_check.py .

# Copy requirements templates from canonical source (misc/requirements)
# Build context is project root, so misc/requirements is directly accessible
COPY --chown=analyzer:analyzer misc/requirements /app/misc/requirements

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python health_check.py

# Expose port
EXPOSE 2004

# Run the analyzer
CMD ["python", "main.py"]
