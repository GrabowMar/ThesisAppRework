# Multi-stage Dockerfile for ThesisApp Flask Application
# Uses Python 3.12 and modern 2025 best practices

FROM python:3.12-slim AS build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /app/src /app/logs /app/generated /app/results /app/misc && \
    chown -R appuser:appuser /app

# Copy Python packages from build stage
COPY --from=build /root/.local /home/appuser/.local

# Set environment
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=main.py
ENV HOST=0.0.0.0

# Copy application code
WORKDIR /app
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser misc/ ./misc/
COPY --chown=appuser:appuser analyzer/ ./analyzer/

# Create necessary directories with correct permissions
RUN mkdir -p /app/src/data /app/logs /app/generated/apps /app/results && \
    chown -R appuser:appuser /app/src/data /app/logs /app/generated /app/results

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose Flask port
EXPOSE 5000

# Run Flask application
CMD ["python", "src/main.py"]
