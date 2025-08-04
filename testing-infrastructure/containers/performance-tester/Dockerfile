FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install performance testing tools
RUN pip install --no-cache-dir \
    locust \
    requests \
    fastapi \
    uvicorn

# Copy application files
COPY app/ ./app/

# Create required directories
RUN mkdir -p /app/reports /app/logs /app/shared

# Set Python path
ENV PYTHONPATH=/app/shared/api-contracts:/app

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
