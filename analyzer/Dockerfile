# Analyzer WebSocket Gateway Dockerfile with modern 2025 best practices
FROM python:3.12-slim AS build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.12-slim

# Create non-root user
RUN useradd -m -u 1000 analyzer && \
    mkdir -p /app /app/shared && \
    chown -R analyzer:analyzer /app

# Copy Python packages from build stage
COPY --from=build /root/.local /home/analyzer/.local

# Copy application code
COPY --chown=analyzer:analyzer shared/ /app/shared/
COPY --chown=analyzer:analyzer websocket_gateway.py /app/

# Set environment
ENV PATH=/home/analyzer/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER analyzer
WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; import websockets; asyncio.run(websockets.connect('ws://localhost:8765')).__aenter__()" || exit 1

# Expose port
EXPOSE 8765

# Run the gateway
CMD ["python", "websocket_gateway.py"]
