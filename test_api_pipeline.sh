#!/bin/bash
# Full Pipeline Test using HTTP API

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="http://localhost:5000"
MODEL="upstage/solar-pro-3:free"
TEMPLATE="crud_todo_list"

echo "========================================="
echo "Full Pipeline Test: Generation -> Analysis"
echo "========================================="
echo ""
echo "Configuration:"
echo "  Model: $MODEL"
echo "  Template: $TEMPLATE"
echo ""

# Step 1: Generate App
echo -e "${BLUE}[STEP 1] Generating Application...${NC}"

GEN_PAYLOAD=$(cat <<EOF
{
  "model_slug": "$MODEL",
  "template_slug": "$TEMPLATE"
}
EOF
)

echo "Sending generation request..."
GEN_RESPONSE=$(docker exec thesisapprework-web-1 curl -s -X POST \
  http://localhost:5000/api/gen/generate \
  -H "Content-Type: application/json" \
  -d "$GEN_PAYLOAD")

echo "Generation response:"
echo "$GEN_RESPONSE" | python3 -m json.tool

# Parse response
APP_NUM=$(echo "$GEN_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('data', {}).get('app_num', ''))" 2>/dev/null || echo "")

if [ -z "$APP_NUM" ]; then
  echo -e "${RED}✗ Generation failed!${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Generation successful! App number: $APP_NUM${NC}"
echo ""

# Wait a bit
sleep 2

# Step 2: Run Analysis
echo -e "${BLUE}[STEP 2] Running Analysis...${NC}"

ANALYSIS_PAYLOAD=$(cat <<EOF
{
  "model_slug": "$MODEL",
  "app_number": $APP_NUM,
  "analysis_type": "unified",
  "tools": ["bandit", "semgrep", "eslint", "locust"],
  "container_management": {
    "start_containers": true,
    "stop_after_analysis": false
  }
}
EOF
)

echo "Sending analysis request..."
ANALYSIS_RESPONSE=$(docker exec thesisapprework-web-1 curl -s -X POST \
  http://localhost:5000/api/analysis/run \
  -H "Content-Type: application/json" \
  -d "$ANALYSIS_PAYLOAD")

echo "Analysis response:"
echo "$ANALYSIS_RESPONSE" | python3 -m json.tool

# Parse response
TASK_ID=$(echo "$ANALYSIS_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('data', {}).get('task_id', ''))" 2>/dev/null || echo "")

if [ -z "$TASK_ID" ]; then
  echo -e "${RED}✗ Analysis request failed!${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Analysis started! Task ID: $TASK_ID${NC}"
echo ""

# Step 3: Monitor Progress
echo -e "${BLUE}[STEP 3] Monitoring Analysis Progress...${NC}"

MAX_ATTEMPTS=60  # 5 minutes
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  sleep 5
  ATTEMPT=$((ATTEMPT + 1))

  STATUS_RESPONSE=$(docker exec thesisapprework-web-1 curl -s \
    "http://localhost:5000/api/analysis/task/$TASK_ID")

  STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('data', {}).get('status', ''))" 2>/dev/null || echo "UNKNOWN")
  PROGRESS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('data', {}).get('progress_percentage', 0))" 2>/dev/null || echo "0")

  echo -e "${YELLOW}[$(date +%H:%M:%S)] Status: $STATUS | Progress: $PROGRESS%${NC}"

  if [ "$STATUS" = "COMPLETED" ]; then
    echo -e "${GREEN}✓ Analysis completed successfully!${NC}"
    break
  elif [ "$STATUS" = "FAILED" ]; then
    echo -e "${RED}✗ Analysis failed!${NC}"
    echo "$STATUS_RESPONSE" | python3 -m json.tool
    exit 1
  fi
done

if [ $ATTEMPT -ge $MAX_ATTEMPTS ]; then
  echo -e "${YELLOW}⚠ Analysis is still running after 5 minutes${NC}"
fi

echo ""

# Step 4: Verify Results
echo -e "${BLUE}[STEP 4] Verifying Results...${NC}"

# Check if results directory exists
RESULTS_DIR="results/$MODEL/app$APP_NUM"
if docker exec thesisapprework-web-1 ls "$RESULTS_DIR" &>/dev/null; then
  echo -e "${GREEN}✓ Results directory exists${NC}"
  echo "Result files:"
  docker exec thesisapprework-web-1 find "$RESULTS_DIR" -type f -name "*.json" | head -10
else
  echo -e "${YELLOW}⚠ Results directory not found yet${NC}"
fi

echo ""
echo "========================================="
echo -e "${GREEN}Pipeline Test Completed!${NC}"
echo "========================================="
echo ""
echo "Summary:"
echo "  Model: $MODEL"
echo "  App Number: $APP_NUM"
echo "  Task ID: $TASK_ID"
echo "  Results: $RESULTS_DIR"
echo ""
