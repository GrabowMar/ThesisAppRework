#!/usr/bin/env python3
"""Fix celery-worker healthcheck in docker-compose.yml"""

import re

filepath = '/home/coder/ThesisAppRework/docker-compose.yml'

with open(filepath, 'r') as f:
    content = f.read()

# Find celery-worker section and add healthcheck before restart
old_block = """    depends_on:
      - redis
      - web
    restart: unless-stopped
    networks:"""

new_block = """    depends_on:
      - redis
      - web
    healthcheck:
      test: ["CMD", "pgrep", "-f", "celery"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    networks:"""

if old_block in content:
    content = content.replace(old_block, new_block, 1)
    with open(filepath, 'w') as f:
        f.write(content)
    print("Successfully added healthcheck to celery-worker!")
else:
    print("Could not find the expected block to replace.")
    print("Looking for patterns...")
    if "celery-worker:" in content:
        print("Found celery-worker section")
    if "restart: unless-stopped" in content:
        print("Found restart: unless-stopped")
