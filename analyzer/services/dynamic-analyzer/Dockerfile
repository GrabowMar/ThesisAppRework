# Dynamic Analysis Container - Network Tools + OWASP ZAP
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    nmap \
    openjdk-21-jre-headless \
    xvfb \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Download and install OWASP ZAP
# Using the cross-platform package
ENV ZAP_VERSION=2.16.1
ENV ZAP_PATH=/zap/ZAP_${ZAP_VERSION}
RUN mkdir -p /zap && \
    curl -sSL "https://github.com/zaproxy/zaproxy/releases/download/v${ZAP_VERSION}/ZAP_${ZAP_VERSION}_Crossplatform.zip" \
    -o /tmp/zap.zip && \
    cd /tmp && \
    unzip -q zap.zip && \
    mv ZAP_${ZAP_VERSION} /zap/ && \
    chmod +x ${ZAP_PATH}/zap.sh && \
    rm /tmp/zap.zip

# Add ZAP to PATH
ENV PATH="${ZAP_PATH}:${PATH}"

# Set working directory
WORKDIR /app

# Copy requirements first for better caching (from repo root context)
COPY analyzer/services/dynamic-analyzer/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -u 1000 -m analyzer

# Copy shared analyzer package, configs, and service code
COPY --chown=analyzer:analyzer analyzer/__init__.py ./analyzer/__init__.py
COPY --chown=analyzer:analyzer analyzer/shared ./analyzer/shared
COPY --chown=analyzer:analyzer analyzer/config_loader.py ./analyzer/config_loader.py
COPY --chown=analyzer:analyzer analyzer/configs ./analyzer/configs
COPY --chown=analyzer:analyzer analyzer/services/dynamic-analyzer/main.py .
COPY --chown=analyzer:analyzer analyzer/services/dynamic-analyzer/health_check.py .
COPY --chown=analyzer:analyzer analyzer/services/dynamic-analyzer/zap_scanner.py .
COPY --chown=analyzer:analyzer analyzer/services/dynamic-analyzer/sarif_parsers.py .
COPY --chown=analyzer:analyzer analyzer/services/dynamic-analyzer/start_services.sh .

# Make startup script executable
RUN chmod +x start_services.sh

# Switch to non-root user
USER analyzer

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python health_check.py

# Expose ports (2002 for analyzer, 8090 for ZAP daemon)
EXPOSE 2002 8090

# Run the startup script that launches ZAP then the analyzer
CMD ["bash", "start_services.sh"]
