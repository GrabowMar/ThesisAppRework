#!/usr/bin/env bash
# Quick validation script for Docker deployment
# Tests all critical endpoints and services

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
WEB_URL="${WEB_URL:-http://localhost:5000}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

echo "========================================"
echo "ThesisApp Docker Deployment Validation"
echo "========================================"
echo ""

# Test 1: Docker is running
echo -n "Testing Docker daemon... "
if docker info &> /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "Error: Docker daemon is not running"
    exit 1
fi

# Test 2: Containers are running
echo -n "Checking containers... "
RUNNING=$(docker compose ps --status=running | grep -c "running" || echo "0")
if [ "$RUNNING" -ge 5 ]; then
    echo -e "${GREEN}✓ ($RUNNING containers)${NC}"
else
    echo -e "${YELLOW}⚠ Only $RUNNING containers running${NC}"
    docker compose ps
fi

# Test 3: Web application health
echo -n "Testing web application (${WEB_URL}/health)... "
if curl -sf "${WEB_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "Error: Web application not responding"
    echo "Try: docker compose logs web"
fi

# Test 4: Redis connection
echo -n "Testing Redis connection... "
if command -v redis-cli &> /dev/null; then
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        echo "Error: Cannot connect to Redis"
    fi
else
    if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
fi

# Test 5: Analyzer gateway
echo -n "Testing analyzer gateway (ws://localhost:8765)... "
if nc -z localhost 8765 2>/dev/null || timeout 1 bash -c 'cat < /dev/null > /dev/tcp/localhost/8765' 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ Gateway may not be ready${NC}"
fi

# Test 6: Check volumes
echo -n "Checking Docker volumes... "
VOLUMES=$(docker volume ls | grep -c "thesis" || echo "0")
if [ "$VOLUMES" -ge 1 ]; then
    echo -e "${GREEN}✓ ($VOLUMES volumes)${NC}"
else
    echo -e "${YELLOW}⚠ No volumes found${NC}"
fi

# Test 7: Database file
echo -n "Checking database file... "
if [ -f "src/data/thesis_app.db" ]; then
    SIZE=$(du -h src/data/thesis_app.db | cut -f1)
    echo -e "${GREEN}✓ ($SIZE)${NC}"
elif docker compose exec -T web test -f /app/src/data/thesis_app.db 2>/dev/null; then
    echo -e "${GREEN}✓ (in container)${NC}"
else
    echo -e "${YELLOW}⚠ Database not initialized${NC}"
    echo "Run: docker compose exec web python src/init_db.py"
fi

# Test 8: Logs directory
echo -n "Checking logs directory... "
if [ -d "logs" ] && [ "$(ls -A logs 2>/dev/null)" ]; then
    LOG_COUNT=$(ls logs/*.log 2>/dev/null | wc -l || echo "0")
    echo -e "${GREEN}✓ ($LOG_COUNT log files)${NC}"
else
    echo -e "${YELLOW}⚠ No logs yet${NC}"
fi

# Summary
echo ""
echo "========================================"
echo "Validation Complete"
echo "========================================"
echo ""
echo "Service URLs:"
echo "  Web UI:           ${WEB_URL}"
echo "  API Health:       ${WEB_URL}/health"
echo "  Analyzer Gateway: ws://localhost:8765"
echo "  Redis:            redis://${REDIS_HOST}:${REDIS_PORT}"
echo ""
echo "Management Commands:"
echo "  View logs:        docker compose logs -f [service]"
echo "  Check status:     docker compose ps"
echo "  Restart service:  docker compose restart [service]"
echo "  Stop all:         docker compose down"
echo ""

# Final status
HEALTH_STATUS=$(curl -sf "${WEB_URL}/health" 2>/dev/null || echo "unhealthy")
if echo "$HEALTH_STATUS" | grep -q "ok\|healthy\|success" ; then
    echo -e "${GREEN}✓ System is healthy and ready!${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠ System is running but some services may need attention${NC}"
    echo "Check logs for details: docker compose logs"
    exit 1
fi
