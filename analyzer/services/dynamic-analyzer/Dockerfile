# Dynamic Analysis Container - OWASP ZAP Security Scanner
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    openjdk-11-jre-headless \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install OWASP ZAP
RUN wget -q https://github.com/zaproxy/zaproxy/releases/download/v2.14.0/ZAP_2_14_0_unix.sh \
    && chmod +x ZAP_2_14_0_unix.sh \
    && ./ZAP_2_14_0_unix.sh -q -dir /opt/zaproxy \
    && rm ZAP_2_14_0_unix.sh

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

# Set environment variables
ENV ZAP_PATH=/opt/zaproxy
ENV DISPLAY=:99

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python health_check.py

# Expose port
EXPOSE 8002

# Run the analyzer
CMD ["python", "main.py"]
