#!/usr/bin/env python3
import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from app import create_app
from core_services import get_port_config

app = create_app()

with app.app_context():
    configs = get_port_config()
    print(f"Type: {type(configs)}")
    print(f"Length: {len(configs)}")
    
    if configs:
        print(f"First item type: {type(configs[0])}")
        print(f"First item: {configs[0]}")
        
        # Check if it's iterating incorrectly
        for i, item in enumerate(configs[:2]):
            print(f"Item {i}: type={type(item)}, value={item}")
    else:
        print("Empty configs")
