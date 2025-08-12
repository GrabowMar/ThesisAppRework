#!/usr/bin/env python3
"""
Remove API routes from statistics.py
"""

import re
from pathlib import Path

def remove_api_routes_from_statistics():
    """Remove all API routes from the main statistics.py file."""
    
    stats_file = Path("src/app/routes/statistics.py")
    content = stats_file.read_text(encoding='utf-8')
    
    # Find all API route functions and remove them
    api_route_pattern = r'@stats_bp\.route\(\'/api/[^\']+\'\)[^@]*?(?=@\w+|def _\w+|$)'
    
    # Remove all API routes
    cleaned_content = re.sub(api_route_pattern, '', content, flags=re.DOTALL)
    
    # Clean up multiple empty lines
    cleaned_content = re.sub(r'\n\n\n+', '\n\n', cleaned_content)
    
    # Write back
    stats_file.write_text(cleaned_content, encoding='utf-8')
    print("✅ Removed API routes from statistics.py")

if __name__ == "__main__":
    remove_api_routes_from_statistics()
