import pytest

pytestmark = [pytest.mark.integration, pytest.mark.web_ui]

"""
Simulate web browser interaction with the analysis system.
Tests both API endpoints and HTML form submissions.
"""
import requests
from bs4 import BeautifulSoup
import json
import time
from typing import Dict, Optional

# Configuration
BASE_URL = "http://localhost:5000"
API_TOKEN = "rVeT8CcWIfqPLeGFJcO1FHKYx3vvXVJbjrnCHeoGbB0at6cJwWmMks4baFn9AT2w"

class WebAnalysisSimulator:
    def __init__(self, base_url: str, api_token: Optional[str] = None):
        self.base_url = base_url
        self.session = requests.Session()
        self.api_token = api_token
        
    def test_home_page(self):
        """Test accessing the home page."""
        print("\n" + "="*80)
        print("TEST 1: Home Page Access")
        print("="*80)
        
        response = self.session.get(f"{self.base_url}/")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.find('title')
            print(f"Page Title: {title.text if title else 'No title'}")
            
            # Find navigation links
            nav_links = soup.find_all('a', href=True)
            print(f"\nFound {len(nav_links)} navigation links")
            for link in nav_links[:10]:  # Show first 10
                print(f"  - {link.text.strip()}: {link['href']}")
        
        return response.status_code == 200
    
    def test_analysis_page(self):
        """Test accessing the analysis creation page."""
        print("\n" + "="*80)
        print("TEST 2: Analysis Creation Page")
        print("="*80)
        
        response = self.session.get(f"{self.base_url}/analysis/create")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find forms
            forms = soup.find_all('form')
            print(f"\nFound {len(forms)} form(s)")
            
            # Find model selection elements
            selects = soup.find_all('select')
            print(f"Found {len(selects)} select element(s)")
            
            for select in selects:
                select_name = select.get('name', 'unnamed')
                options = select.find_all('option')
                print(f"\n  Select '{select_name}': {len(options)} options")
                for opt in options[:5]:  # Show first 5
                    print(f"    - {opt.text.strip()}")
        
        return response.status_code == 200
    
    def test_api_token_verification(self):
        """Test API token verification."""
        print("\n" + "="*80)
        print("TEST 3: API Token Verification")
        print("="*80)
        
        if not self.api_token:
            print("[SKIP] No API token provided")
            return False
        
        headers = {"Authorization": f"Bearer {self.api_token}"}
        response = self.session.get(f"{self.base_url}/api/tokens/verify", headers=headers)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Token Valid: {data.get('valid', False)}")
            print(f"Response: {json.dumps(data, indent=2)}")
        
        return response.status_code == 200
    
    def test_api_comprehensive_analysis(self, model_slug: str, app_number: int):
        """Test creating a comprehensive analysis via API."""
        print("\n" + "="*80)
        print(f"TEST 4: API Comprehensive Analysis - {model_slug} app{app_number}")
        print("="*80)
        
        if not self.api_token:
            print("[SKIP] No API token provided")
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model_slug": model_slug,
            "app_number": app_number,
            "analysis_type": "comprehensive"
        }
        
        print(f"\nPayload: {json.dumps(payload, indent=2)}")
        
        response = self.session.post(
            f"{self.base_url}/api/analysis/run",
            headers=headers,
            json=payload
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            task_id = data.get('task_id')
            print(f"✓ Task Created: {task_id}")
            print(f"Response: {json.dumps(data, indent=2)}")
            return task_id
        else:
            print(f"✗ Failed: {response.text}")
            return None
    
    def test_api_security_analysis(self, model_slug: str, app_number: int):
        """Test creating a security analysis via API."""
        print("\n" + "="*80)
        print(f"TEST 5: API Security Analysis - {model_slug} app{app_number}")
        print("="*80)
        
        if not self.api_token:
            print("[SKIP] No API token provided")
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model_slug": model_slug,
            "app_number": app_number,
            "analysis_type": "security",
            "tools": ["bandit", "safety"]
        }
        
        print(f"\nPayload: {json.dumps(payload, indent=2)}")
        
        response = self.session.post(
            f"{self.base_url}/api/analysis/run",
            headers=headers,
            json=payload
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            task_id = data.get('task_id')
            print(f"✓ Task Created: {task_id}")
            print(f"Response: {json.dumps(data, indent=2)}")
            return task_id
        else:
            print(f"✗ Failed: {response.text}")
            return None
    
    def test_task_status(self, task_id: str):
        """Check task status via API."""
        print("\n" + "="*80)
        print(f"TEST 6: Task Status Check - {task_id}")
        print("="*80)
        
        if not self.api_token:
            print("[SKIP] No API token provided")
            return None
        
        headers = {"Authorization": f"Bearer {self.api_token}"}
        response = self.session.get(
            f"{self.base_url}/api/tasks/{task_id}/status",
            headers=headers
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nTask Status: {data.get('status')}")
            print(f"Progress: {data.get('progress_percentage', 0):.1f}%")
            print(f"Response: {json.dumps(data, indent=2)}")
            return data
        else:
            print(f"✗ Failed: {response.text}")
            return None
    
    def test_wait_for_completion(self, task_id: str, max_wait: int = 300, poll_interval: int = 5):
        """Wait for task to complete."""
        print("\n" + "="*80)
        print(f"TEST 7: Waiting for Task Completion - {task_id}")
        print("="*80)
        
        if not self.api_token:
            print("[SKIP] No API token provided")
            return None
        
        headers = {"Authorization": f"Bearer {self.api_token}"}
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait:
            response = self.session.get(
                f"{self.base_url}/api/tasks/{task_id}/status",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                progress = data.get('progress_percentage', 0)
                
                print(f"[{int(time.time() - start_time)}s] Status: {status}, Progress: {progress:.1f}%")
                
                if status in ['completed', 'failed', 'error']:
                    print(f"\n✓ Task finished with status: {status}")
                    return data
            
            time.sleep(poll_interval)
        
        print(f"\n✗ Timeout after {max_wait}s")
        return None
    
    def test_get_results(self, task_id: str):
        """Get task results via API."""
        print("\n" + "="*80)
        print(f"TEST 8: Get Task Results - {task_id}")
        print("="*80)
        
        if not self.api_token:
            print("[SKIP] No API token provided")
            return None
        
        headers = {"Authorization": f"Bearer {self.api_token}"}
        response = self.session.get(
            f"{self.base_url}/api/tasks/{task_id}/results",
            headers=headers
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Print summary
            if 'results' in data:
                results = data['results']
                print(f"\n✓ Results retrieved successfully")
                print(f"  Total findings: {results.get('total_findings', 0)}")
                print(f"  Services: {len(results.get('services', {}))}")
                print(f"  Tools: {len(results.get('tools', {}))}")
                
                # Show tool summary
                tools = results.get('tools', {})
                if tools:
                    print(f"\n  Tool Results:")
                    for tool_name, tool_data in list(tools.items())[:10]:
                        status = tool_data.get('status', 'unknown')
                        findings = len(tool_data.get('findings', []))
                        print(f"    - {tool_name}: {status} ({findings} findings)")
            
            return data
        else:
            print(f"✗ Failed: {response.text}")
            return None
    
    def test_health_check(self):
        """Test application health endpoint."""
        print("\n" + "="*80)
        print("TEST 9: Health Check")
        print("="*80)
        
        response = self.session.get(f"{self.base_url}/health")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Health Status: {data.get('status')}")
            print(f"Response: {json.dumps(data, indent=2)}")
        
        return response.status_code == 200
    
    def run_full_simulation(self):
        """Run complete simulation."""
        print("\n" + "#"*80)
        print("#" + " "*78 + "#")
        print("#" + " "*20 + "WEB ANALYSIS SIMULATION" + " "*35 + "#")
        print("#" + " "*78 + "#")
        print("#"*80)
        
        # Test 1: Home page
        self.test_home_page()
        
        # Test 2: Analysis page
        self.test_analysis_page()
        
        # Test 3: API token
        self.test_api_token_verification()
        
        # Test 4: Health check
        self.test_health_check()
        
        # Test 5: Create comprehensive analysis
        task_id = self.test_api_comprehensive_analysis(
            "anthropic_claude-4.5-haiku-20251001", 
            1
        )
        
        if task_id:
            # Test 6-7: Wait for completion
            final_status = self.test_wait_for_completion(task_id, max_wait=600)
            
            if final_status and final_status.get('status') == 'completed':
                # Test 8: Get results
                self.test_get_results(task_id)
        
        # Test 9: Create security-only analysis
        task_id_2 = self.test_api_security_analysis(
            "anthropic_claude-4.5-sonnet-20250929",
            1
        )
        
        if task_id_2:
            print(f"\n✓ Second task created: {task_id_2}")
            print("  (Not waiting for completion in this simulation)")
        
        print("\n" + "#"*80)
        print("#" + " "*20 + "SIMULATION COMPLETE" + " "*39 + "#")
        print("#"*80)


def main():
    """Main entry point."""
    simulator = WebAnalysisSimulator(BASE_URL, API_TOKEN)
    simulator.run_full_simulation()


if __name__ == "__main__":
    main()
