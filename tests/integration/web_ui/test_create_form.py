#!/usr/bin/env python3
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.web_ui]

"""
Test Analysis Create Form Submission
=====================================

Simulates what the create.html form does when submitting.
"""

import requests
from bs4 import BeautifulSoup

BASE_URL = 'http://localhost:5000'
BEARER_TOKEN = 'WCVNOZZ125gzTx_Z1F6pjnW34JIWqYLyh9xTytVbaJnTUfXYFrir2EJcadpYgelI'


def test_create_form_get():
    """Test GET request to load the form"""
    print("=" * 70)
    print("TEST 1: Load Create Form (GET)")
    print("=" * 70)
    
    headers = {
        'Authorization': f'Bearer {BEARER_TOKEN}'
    }
    
    response = requests.get(f'{BASE_URL}/analysis/create', headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Content-Length: {len(response.text)} bytes")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form', id='analysis-wizard-form')
        if form:
            print(f"✓ Form found with action: {form.get('action')}")
            return True
        else:
            print(f"✗ Form not found in page")
            return False
    else:
        print(f"✗ Failed to load form")
        return False


def test_create_form_post_custom():
    """Test POST request with custom tool selection"""
    print("\n" + "=" * 70)
    print("TEST 2: Submit Create Form - Custom Tools")
    print("=" * 70)
    
    # Simulate form data as the wizard would send it
    form_data = {
        'model_slug': 'anthropic_claude-4.5-sonnet-20250929',
        'app_number': '1',
        'analysis_mode': 'custom',
        'analysis_profile': '',
        'selected_tools[]': ['bandit', 'safety'],  # List format as form sends it
        'priority': 'normal'
    }
    
    print(f"Submitting with data:")
    for key, value in form_data.items():
        print(f"  {key}: {value}")
    
    headers = {
        'Authorization': f'Bearer {BEARER_TOKEN}'
    }
    
    response = requests.post(
        f'{BASE_URL}/analysis/create',
        data=form_data,
        headers=headers,
        allow_redirects=False
    )
    
    print(f"\nStatus: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    
    if response.status_code == 302:
        print(f"✓ Redirect to: {response.headers.get('Location')}")
        return True
    elif response.status_code == 200:
        print(f"✗ No redirect - form returned (likely error)")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for flash messages
        alerts = soup.find_all('div', class_='alert')
        if alerts:
            print(f"\nFlash messages found:")
            for alert in alerts:
                print(f"  - {alert.text.strip()}")
        return False
    else:
        print(f"✗ Unexpected status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return False


def test_create_form_post_profile():
    """Test POST request with analysis profile"""
    print("\n" + "=" * 70)
    print("TEST 3: Submit Create Form - Analysis Profile")
    print("=" * 70)
    
    form_data = {
        'model_slug': 'anthropic_claude-4.5-haiku-20251001',
        'app_number': '1',
        'analysis_mode': 'profile',
        'analysis_profile': 'security',
        'selected_tools[]': [],  # Empty when using profile
        'priority': 'normal'
    }
    
    print(f"Submitting with data:")
    for key, value in form_data.items():
        print(f"  {key}: {value}")
    
    headers = {
        'Authorization': f'Bearer {BEARER_TOKEN}'
    }
    
    response = requests.post(
        f'{BASE_URL}/analysis/create',
        data=form_data,
        headers=headers,
        allow_redirects=False
    )
    
    print(f"\nStatus: {response.status_code}")
    
    if response.status_code == 302:
        print(f"✓ Redirect to: {response.headers.get('Location')}")
        return True
    elif response.status_code == 200:
        print(f"✗ No redirect - form returned (likely error)")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        alerts = soup.find_all('div', class_='alert')
        if alerts:
            print(f"\nFlash messages found:")
            for alert in alerts:
                print(f"  - {alert.text.strip()}")
        return False
    else:
        print(f"✗ Unexpected status: {response.status_code}")
        return False


def test_create_form_post_invalid():
    """Test POST request with invalid data to see error handling"""
    print("\n" + "=" * 70)
    print("TEST 4: Submit Create Form - Invalid Data (Missing Model)")
    print("=" * 70)
    
    form_data = {
        'model_slug': '',  # Missing
        'app_number': '1',
        'analysis_mode': 'custom',
        'analysis_profile': '',
        'selected_tools[]': ['bandit'],
        'priority': 'normal'
    }
    
    headers = {
        'Authorization': f'Bearer {BEARER_TOKEN}'
    }
    
    response = requests.post(
        f'{BASE_URL}/analysis/create',
        data=form_data,
        headers=headers,
        allow_redirects=False
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 400:
        print(f"✓ Validation error returned as expected")
        soup = BeautifulSoup(response.text, 'html.parser')
        alerts = soup.find_all('div', class_='alert')
        if alerts:
            print(f"\nError messages:")
            for alert in alerts:
                print(f"  - {alert.text.strip()}")
        return True
    else:
        print(f"✗ Expected 400, got {response.status_code}")
        return False


def main():
    """Run all tests"""
    print("\n" + "#" * 70)
    print("# Analysis Create Form Testing")
    print("#" * 70)
    
    results = []
    
    results.append(("Load Form", test_create_form_get()))
    results.append(("Custom Tools", test_create_form_post_custom()))
    results.append(("Profile Mode", test_create_form_post_profile()))
    results.append(("Invalid Data", test_create_form_post_invalid()))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print(f"\n✓ All tests passed!")
    else:
        print(f"\n✗ Some tests failed")
    
    return all_passed


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
