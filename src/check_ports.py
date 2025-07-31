#!/usr/bin/env python3

from extensions import db
from models import PortConfiguration
from app import create_app

app = create_app()
app.app_context().push()

# Check a few samples to understand the data structure
samples = PortConfiguration.query.limit(5).all()
for sample in samples:
    metadata = sample.get_metadata()
    print(f'Port config: frontend={sample.frontend_port}, backend={sample.backend_port}')
    print(f'Model name: {metadata.get("model_name")}, App number: {metadata.get("app_number")}')
    print('---')

# Test querying by model name and app number
model_name = "anthropic_claude-3.7-sonnet"
app_number = 1

# Query all and filter in Python
print('\nUsing Python filtering:')
all_configs = PortConfiguration.query.all()
for config in all_configs:
    metadata = config.get_metadata()
    if metadata.get("model_name") == model_name and metadata.get("app_number") == app_number:
        print(f'Found: frontend={config.frontend_port}, backend={config.backend_port}')
        break
