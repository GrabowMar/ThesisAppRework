FROM zaproxy/zap-stable:latest

# Switch to root for installation
USER root

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

# Copy application files
WORKDIR /app
COPY app/ ./app/

# Create required directories
RUN mkdir -p /app/reports /app/logs /zap/sessions /app/shared

# Set Python path
ENV PYTHONPATH=/app/shared/api-contracts:/app

# Expose ports
EXPOSE 8003 8090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

# Switch back to zap user
USER zap

# Run the application
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
