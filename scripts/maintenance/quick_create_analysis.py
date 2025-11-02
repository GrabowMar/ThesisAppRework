#!/usr/bin/env python3
"""
Quick Analysis Creator
======================

Helper script to create analysis tasks via the web UI API using
applications that actually exist in your database.
"""

import requests
import sys
from pathlib import Path

# Add src to path to access models
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.models import GeneratedApplication

BASE_URL = 'http://localhost:5000'
BEARER_TOKEN = 'WCVNOZZ125gzTx_Z1F6pjnW34JIWqYLyh9xTytVbaJnTUfXYFrir2EJcadpYgelI'


def list_available_apps():
    """List all applications available for analysis"""
    app = create_app()
    with app.app_context():
        apps = GeneratedApplication.query.all()
        print(f"\n{'='*70}")
        print(f"Available Applications for Analysis ({len(apps)} total)")
        print(f"{'='*70}\n")
        
        for app_obj in apps:
            print(f"  {app_obj.model_slug}/app{app_obj.app_number}")
        
        return [(app_obj.model_slug, app_obj.app_number) for app_obj in apps]


def create_analysis_via_form(model_slug, app_number, mode='custom', tools=None, profile=None):
    """Create analysis via the web form endpoint"""
    
    if mode == 'custom' and not tools:
        tools = ['bandit', 'safety']
    
    form_data = {
        'model_slug': model_slug,
        'app_number': str(app_number),
        'analysis_mode': mode,
        'analysis_profile': profile or '',
        'selected_tools[]': tools if mode == 'custom' else [],
        'priority': 'normal'
    }
    
    headers = {
        'Authorization': f'Bearer {BEARER_TOKEN}'
    }
    
    print(f"\nCreating analysis:")
    print(f"  Model: {model_slug}")
    print(f"  App: {app_number}")
    print(f"  Mode: {mode}")
    if mode == 'custom':
        print(f"  Tools: {', '.join(tools)}")
    elif mode == 'profile':
        print(f"  Profile: {profile}")
    
    response = requests.post(
        f'{BASE_URL}/analysis/create',
        data=form_data,
        headers=headers,
        allow_redirects=False
    )
    
    if response.status_code == 302:
        print(f"✓ SUCCESS: Analysis created!")
        print(f"  Redirect: {response.headers.get('Location')}")
        return True
    else:
        print(f"✗ FAILED: Status {response.status_code}")
        
        # Try to extract error messages
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        alerts = soup.find_all('div', class_='alert')
        if alerts:
            print(f"\nError messages:")
            for alert in alerts:
                text = alert.text.strip()
                if text and len(text) < 200:  # Skip long ones
                    print(f"  - {text}")
        return False


def main():
    """Interactive analysis creator"""
    print(f"\n{'#'*70}")
    print(f"# Quick Analysis Creator")
    print(f"{'#'*70}")
    
    # List available apps
    apps = list_available_apps()
    
    if not apps:
        print(f"\n✗ No applications found in database!")
        print(f"  Run app generation first to create applications.")
        return
    
    # Create some example analyses
    print(f"\n{'='*70}")
    print(f"Creating Example Analyses")
    print(f"{'='*70}")
    
    # Example 1: Custom tools
    model_slug, app_number = apps[0]
    create_analysis_via_form(
        model_slug, 
        app_number, 
        mode='custom', 
        tools=['bandit', 'safety', 'eslint']
    )
    
    # Example 2: Security profile
    if len(apps) > 1:
        model_slug, app_number = apps[1]
        create_analysis_via_form(
            model_slug, 
            app_number, 
            mode='profile', 
            profile='security'
        )
    
    print(f"\n{'='*70}")
    print(f"Done! Check http://localhost:5000/analysis/list to see your tasks")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    main()
