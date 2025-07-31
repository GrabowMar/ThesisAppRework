#!/usr/bin/env python3
"""Quick test script for statistics functions."""

import sys
from pathlib import Path

# Add src to path
sys.path.append('src')

from web_routes import load_generation_statistics, load_recent_generations, load_top_performing_models

def test_statistics():
    print("=" * 50)
    print("Testing Statistics Functions")
    print("=" * 50)
    
    # Test generation statistics
    print("\n1. Testing load_generation_statistics:")
    stats = load_generation_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Test recent generations
    print("\n2. Testing load_recent_generations:")
    recent = load_recent_generations()
    print(f"   Found {len(recent)} recent generations")
    if recent:
        print("   Sample generation:")
        for key, value in recent[0].items():
            print(f"     {key}: {value}")
    
    # Test top performing models
    print("\n3. Testing load_top_performing_models:")
    top_models = load_top_performing_models()
    print(f"   Found {len(top_models)} models")
    if top_models:
        print("   Top model:")
        for key, value in top_models[0].items():
            print(f"     {key}: {value}")
    
    print("\n" + "=" * 50)
    print("All statistics functions working!")
    print("=" * 50)

if __name__ == "__main__":
    test_statistics()
