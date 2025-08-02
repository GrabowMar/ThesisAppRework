#!/usr/bin/env python3
"""
Simple test for the new batch dashboard
"""

import requests
import re

def test_new_dashboard():
    print("🧪 TESTING NEW BATCH DASHBOARD")
    print("=" * 40)
    
    try:
        print("📡 Fetching batch dashboard...")
        response = requests.get('http://127.0.0.1:5000/batch/', timeout=10)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Dashboard loaded successfully")
            
            # Check for models in the target models select
            if 'id="targetModels"' in response.text:
                print("✅ Target models select found")
                
                # Extract the select content
                select_pattern = r'<select[^>]*id="targetModels"[^>]*>(.*?)</select>'
                select_match = re.search(select_pattern, response.text, re.DOTALL)
                
                if select_match:
                    select_content = select_match.group(1)
                    
                    # Count options
                    option_pattern = r'<option[^>]*value="([^"]+)"[^>]*>([^<]+)</option>'
                    options = re.findall(option_pattern, select_content)
                    
                    print(f"✅ Found {len(options)} model options:")
                    for i, (value, text) in enumerate(options[:5]):
                        print(f"  {i+1}. {text.strip()}")
                        print(f"     Value: {value}")
                    
                    if len(options) > 5:
                        print(f"  ... and {len(options) - 5} more")
                    
                    if len(options) >= 25:
                        print("🎉 SUCCESS: All models are loaded!")
                        return True
                    else:
                        print(f"⚠️ Only {len(options)} models found, expected 25+")
                        return False
                else:
                    print("❌ Could not parse select content")
                    return False
            else:
                print("❌ Target models select not found")
                return False
        else:
            print(f"❌ HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_new_dashboard()
    if success:
        print("\n🎉 NEW DASHBOARD IS WORKING PERFECTLY!")
    else:
        print("\n❌ Issues found with the dashboard")
