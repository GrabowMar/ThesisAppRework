# Security Analyzer Dockerfile with modern best practices
FROM python:3.12-slim AS build

# Install system dependencies for security tools
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.12-slim

# Install runtime dependencies for security tools
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 analyzer && \
    mkdir -p /app /app/shared /app/sources /app/results && \
    chown -R analyzer:analyzer /app

# Copy Python packages from build stage
COPY --from=build /root/.local /home/analyzer/.local

# Copy application code
COPY --chown=analyzer:analyzer main.py /app/
COPY --chown=analyzer:analyzer ../../shared/ /app/shared/

# Set environment
ENV PATH=/home/analyzer/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER analyzer
WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose port for health checks
EXPOSE 8001

# Run the security analyzer
CMD ["python", "main.py"]
