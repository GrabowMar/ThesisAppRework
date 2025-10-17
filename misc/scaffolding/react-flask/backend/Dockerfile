# Backend Dockerfile for Flask Application
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    libxml2-dev \
    libxslt-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with verbose output for debugging
RUN pip install --no-cache-dir -r requirements.txt || \
    (echo "ERROR: Failed to install Python dependencies. Check requirements.txt for errors." && exit 1)

# Copy application code
COPY . .

# Validate that app.py exists and has no obvious syntax errors
RUN python -m py_compile app.py || \
    (echo "ERROR: app.py has syntax errors. Check your Python code." && exit 1)

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose Flask port (configurable via environment)
EXPOSE 5000

# Health check - try /health first, fallback to /
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || curl -f http://localhost:5000/ || exit 1

# Run the application with better error messages
CMD python app.py || (echo "ERROR: Flask app crashed. Check application logs for details." && exit 1)
