# Performance Testing Container - Locust Load Testing
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    apache2-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -u 1000 -m analyzer
USER analyzer

# Copy application code
COPY --chown=analyzer:analyzer . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python health_check.py

# Expose port
EXPOSE 2003

# Run the analyzer
CMD ["python", "main.py"]
