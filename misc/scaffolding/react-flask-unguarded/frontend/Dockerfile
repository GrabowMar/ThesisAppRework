# Minimal Frontend Dockerfile for Unguarded Generation Mode
# Multi-stage build

# Stage 1: Build
FROM node:20-alpine AS build

WORKDIR /app

# Copy package files (AI-generated)
COPY package.json ./

# Install dependencies with fallbacks
RUN echo "=== Installing dependencies ===" && \
    (npm ci 2>/dev/null || npm install || npm install --legacy-peer-deps) && \
    echo "✓ Dependencies installed"

# Copy source
COPY . .

# Build
RUN npm run build || (echo "⚠ Build failed" && exit 1)

# Stage 2: Production
FROM nginx:alpine

RUN apk add --no-cache curl wget

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config if exists, else create default with health endpoint
COPY . /tmp/frontend-context/
RUN if [ -f /tmp/frontend-context/nginx.conf ]; then \
        cp /tmp/frontend-context/nginx.conf /etc/nginx/conf.d/default.conf; \
    else \
        echo 'server { listen 80; root /usr/share/nginx/html; index index.html; location / { try_files $uri $uri/ /index.html; } location /api { proxy_pass http://backend:5000; } location /health { access_log off; return 200 "healthy\\n"; add_header Content-Type text/plain; } }' > /etc/nginx/conf.d/default.conf; \
    fi && rm -rf /tmp/frontend-context

EXPOSE 80

HEALTHCHECK --interval=120s --timeout=10s --start-period=60s --retries=3 \
    CMD wget -q --spider http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
