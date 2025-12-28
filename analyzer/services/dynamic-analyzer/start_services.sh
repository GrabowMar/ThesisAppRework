#!/bin/bash
# Start ZAP daemon in background and then start the analyzer service

set -e

echo "Starting OWASP ZAP daemon in background..."

# Create ZAP home directory
mkdir -p /tmp/zap_home

# Get ZAP path from environment or auto-detect
ZAP_VERSION="${ZAP_VERSION:-2.16.1}"
ZAP_PATH="${ZAP_PATH:-/zap/ZAP_${ZAP_VERSION}}"

# Start ZAP in daemon mode with xvfb
xvfb-run -a ${ZAP_PATH}/zap.sh \
    -daemon \
    -port 8090 \
    -dir /tmp/zap_home \
    -config api.key=changeme-zap-api-key \
    -config api.addrs.addr.name=.* \
    -config api.addrs.addr.regex=true \
    -config ajaxSpider.browserId=htmlunit \
    -config api.disablekey=false \
    -addoninstall ascanrules \
    -addoninstall pscanrules \
    > /tmp/zap_stdout.log 2> /tmp/zap_stderr.log &

ZAP_PID=$!
echo "ZAP started with PID: $ZAP_PID"

# Wait for ZAP to be ready (check API endpoint)
echo "Waiting for ZAP to be ready..."
for i in {1..60}; do
    if curl -s "http://localhost:8090/JSON/core/view/version/?apikey=changeme-zap-api-key" > /dev/null 2>&1; then
        echo "ZAP is ready after ${i} attempts"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "WARNING: ZAP may not be fully ready yet"
        cat /tmp/zap_stdout.log
        cat /tmp/zap_stderr.log
    fi
    sleep 2
done

# Start the analyzer service
echo "Starting dynamic analyzer service..."
exec python main.py
