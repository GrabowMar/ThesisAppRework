# Analysis Container for Thesis Research Platform
# Contains all security, performance, and code quality analysis tools
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Build tools
    gcc \
    g++ \
    make \
    git \
    curl \
    wget \
    unzip \
    # Node.js for frontend analysis
    nodejs \
    npm \
    # Java for OWASP ZAP and SonarQube
    default-jdk \
    # Additional utilities
    jq \
    procps \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python analysis tools
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js analysis tools globally
RUN npm install -g \
    eslint \
    @typescript-eslint/parser \
    @typescript-eslint/eslint-plugin \
    eslint-plugin-security \
    eslint-plugin-react \
    eslint-plugin-react-hooks \
    retire \
    audit-ci \
    snyk \
    lighthouse \
    @angular/cli \
    create-react-app

# Install Go for additional security tools
RUN wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz && \
    rm go1.21.0.linux-amd64.tar.gz

ENV PATH="/usr/local/go/bin:${PATH}"

# Install additional security tools
RUN go install github.com/securecodewarrior/sast-scan@latest && \
    go install github.com/trufflesecurity/trufflehog/v3@latest

# Download and install OWASP ZAP
RUN wget https://github.com/zaproxy/zaproxy/releases/download/v2.14.0/ZAP_2_14_0_unix.sh && \
    chmod +x ZAP_2_14_0_unix.sh && \
    ./ZAP_2_14_0_unix.sh -q && \
    rm ZAP_2_14_0_unix.sh

# Install SonarQube Scanner
RUN wget https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip && \
    unzip sonar-scanner-cli-5.0.1.3006-linux.zip && \
    mv sonar-scanner-5.0.1.3006-linux /opt/sonar-scanner && \
    rm sonar-scanner-cli-5.0.1.3006-linux.zip

ENV PATH="/opt/sonar-scanner/bin:${PATH}"

# Copy analysis scripts and configuration
COPY analysis/ ./analysis/
COPY config/ ./config/
COPY api/ ./api/

# Make scripts executable
RUN chmod +x analysis/*.sh
RUN chmod +x analysis/*.py

# Create directories for analysis results
RUN mkdir -p /results /workspace /temp

# Set environment variables
ENV PYTHONPATH="/app"
ENV JAVA_HOME="/usr/lib/jvm/default-java"
ENV ZAP_HOME="/opt/zaproxy"
ENV GOPATH="/opt/go"
ENV PATH="/opt/go/bin:${PATH}"

# Expose API port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start the analysis API server
CMD ["python", "api/server.py"]
