FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install Node.js security tools globally
RUN npm install -g \
    eslint \
    @typescript-eslint/eslint-plugin \
    @typescript-eslint/parser \
    retire \
    jshint \
    && npm cache clean --force

# Install Snyk CLI
RUN npm install -g snyk

# Create app directory
WORKDIR /app

# Copy application files
COPY app/ ./app/
COPY shared/ ./shared/

# Create required directories
RUN mkdir -p /app/sources /app/results /app/logs

# Set Python path
ENV PYTHONPATH=/app/shared/api-contracts:/app

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application
CMD ["python", "-m", "app.main"]
