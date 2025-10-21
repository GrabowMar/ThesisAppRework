#!/usr/bin/env python3
"""
AI Client for Thesis Platform
==============================

Simple Python client for AI models (Claude, GPT-4, etc.) to interact with the platform.
Supports both interactive and programmatic usage.

Usage Examples:
    # Interactive mode
    python ai_client.py

    # Direct commands
    python ai_client.py --token YOUR_TOKEN list-models
    python ai_client.py --token YOUR_TOKEN list-apps
    python ai_client.py --token YOUR_TOKEN stats
    python ai_client.py --token YOUR_TOKEN generate --model openai_gpt-4 --template 1 --name my-app
    
    # Get a token first
    python ai_client.py get-token --username admin --password admin123
"""

import argparse
import json
import sys
from typing import Optional, Dict, Any
import urllib.request
import urllib.parse
import urllib.error


class ThesisPlatformClient:
    """Client for interacting with the Thesis Platform API."""
    
    def __init__(self, base_url: str = "http://localhost:5000", token: Optional[str] = None):
        """
        Initialize the client.
        
        Args:
            base_url: Base URL of the platform (default: http://localhost:5000)
            token: API token for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
    
    def _make_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None, 
                     require_auth: bool = True) -> Dict[str, Any]:
        """
        Make an HTTP request to the API.
        
        Args:
            endpoint: API endpoint (e.g., '/api/models')
            method: HTTP method (GET, POST, etc.)
            data: Request body data (for POST/PUT)
            require_auth: Whether authentication is required
            
        Returns:
            JSON response as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if require_auth and self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        elif require_auth and not self.token:
            raise ValueError("Authentication required but no token provided")
        
        request_data = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(url, data=request_data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                error_json = json.loads(error_body)
                raise Exception(f"HTTP {e.code}: {error_json.get('error', error_body)}")
            except json.JSONDecodeError:
                raise Exception(f"HTTP {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise Exception(f"Connection error: {e.reason}")
    
    def get_token(self, username: str, password: str) -> str:
        """
        Login and generate an API token.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            API token string
        """
        # First, login to get a session cookie
        login_url = f"{self.base_url}/auth/login"
        login_data = urllib.parse.urlencode({
            'username': username,
            'password': password
        }).encode('utf-8')
        
        # Create cookie handler
        import http.cookiejar
        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        
        # Login
        req = urllib.request.Request(login_url, data=login_data, method='POST')
        try:
            opener.open(req)
        except urllib.error.HTTPError as e:
            if e.code != 302:  # 302 is expected redirect after successful login
                raise Exception(f"Login failed: HTTP {e.code}")
        
        # Generate token
        token_url = f"{self.base_url}/api/tokens/generate"
        req = urllib.request.Request(token_url, method='POST')
        try:
            response = opener.open(req)
            result = json.loads(response.read().decode('utf-8'))
            if result.get('success'):
                return result['token']
            else:
                raise Exception(f"Token generation failed: {result.get('error', 'Unknown error')}")
        except urllib.error.HTTPError as e:
            raise Exception(f"Token generation failed: HTTP {e.code}")
    
    def verify_token(self) -> Dict[str, Any]:
        """Verify the current token is valid."""
        return self._make_request('/api/tokens/verify', require_auth=True)
    
    def list_models(self) -> Dict[str, Any]:
        """Get all available AI models."""
        return self._make_request('/api/models', require_auth=True)
    
    def list_applications(self) -> Dict[str, Any]:
        """Get all generated applications."""
        return self._make_request('/api/applications', require_auth=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics."""
        return self._make_request('/api/dashboard/stats', require_auth=True)
    
    def health_check(self) -> Dict[str, Any]:
        """Check system health (no auth required)."""
        return self._make_request('/api/health', require_auth=False)
    
    def generate_app(self, model: str, template_id: int, app_name: str, 
                    description: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a new application.
        
        Args:
            model: Model identifier (e.g., 'openai_gpt-4')
            template_id: Template ID number
            app_name: Name for the generated application
            description: Optional description
            
        Returns:
            Generation result
        """
        data = {
            'model': model,
            'template_id': template_id,
            'app_name': app_name
        }
        if description:
            data['description'] = description
        
        return self._make_request('/api/gen/generate', method='POST', data=data, require_auth=True)


def print_json(data: Any, indent: int = 2):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=indent))


def interactive_mode(client: ThesisPlatformClient):
    """Interactive mode for exploring the API."""
    print("=" * 60)
    print("Thesis Platform - Interactive AI Client")
    print("=" * 60)
    print()
    
    if not client.token:
        print("⚠️  No token provided. Limited functionality available.")
        print("   Use --token flag or get-token command to authenticate.")
        print()
    
    commands = {
        '1': ('List Models', lambda: print_json(client.list_models())),
        '2': ('List Applications', lambda: print_json(client.list_applications())),
        '3': ('Get Statistics', lambda: print_json(client.get_stats())),
        '4': ('Health Check', lambda: print_json(client.health_check())),
        '5': ('Verify Token', lambda: print_json(client.verify_token())),
        'q': ('Quit', lambda: sys.exit(0))
    }
    
    while True:
        print("\nAvailable Commands:")
        for key, (name, _) in commands.items():
            print(f"  {key}. {name}")
        print()
        
        choice = input("Enter command: ").strip().lower()
        
        if choice in commands:
            _, func = commands[choice]
            try:
                print()
                func()
            except Exception as e:
                print(f"❌ Error: {e}")
        else:
            print("❌ Invalid choice. Try again.")


def main():
    parser = argparse.ArgumentParser(
        description='AI Client for Thesis Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get a token first
  %(prog)s get-token --username admin --password admin123
  
  # List all models
  %(prog)s --token YOUR_TOKEN list-models
  
  # Get system statistics
  %(prog)s --token YOUR_TOKEN stats
  
  # Generate an application
  %(prog)s --token YOUR_TOKEN generate --model openai_gpt-4 --template 1 --name my-app
  
  # Interactive mode
  %(prog)s --token YOUR_TOKEN
        """
    )
    
    parser.add_argument('--base-url', default='http://localhost:5000',
                       help='Base URL of the platform (default: http://localhost:5000)')
    parser.add_argument('--token', help='API authentication token')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # get-token command
    token_parser = subparsers.add_parser('get-token', help='Login and generate an API token')
    token_parser.add_argument('--username', required=True, help='Username')
    token_parser.add_argument('--password', required=True, help='Password')
    
    # list-models command
    subparsers.add_parser('list-models', help='List all available AI models')
    
    # list-apps command
    subparsers.add_parser('list-apps', help='List all generated applications')
    
    # stats command
    subparsers.add_parser('stats', help='Get dashboard statistics')
    
    # health command
    subparsers.add_parser('health', help='Check system health')
    
    # verify command
    subparsers.add_parser('verify', help='Verify token is valid')
    
    # generate command
    gen_parser = subparsers.add_parser('generate', help='Generate a new application')
    gen_parser.add_argument('--model', required=True, help='Model identifier (e.g., openai_gpt-4)')
    gen_parser.add_argument('--template', type=int, required=True, help='Template ID')
    gen_parser.add_argument('--name', required=True, help='Application name')
    gen_parser.add_argument('--description', help='Optional description')
    
    args = parser.parse_args()
    
    # Create client
    client = ThesisPlatformClient(base_url=args.base_url, token=args.token)
    
    try:
        # Handle commands
        if args.command == 'get-token':
            print("🔐 Logging in and generating token...")
            token = client.get_token(args.username, args.password)
            print(f"\n✅ Token generated successfully!")
            print(f"\n🔑 Your API Token:")
            print(f"{token}")
            print(f"\n💡 Save this token! Use it with:")
            print(f"   python {sys.argv[0]} --token {token} list-models")
            
        elif args.command == 'list-models':
            result = client.list_models()
            print(f"📋 Found {len(result.get('models', []))} models:")
            print_json(result)
            
        elif args.command == 'list-apps':
            result = client.list_applications()
            print(f"📱 Found {len(result.get('applications', []))} applications:")
            print_json(result)
            
        elif args.command == 'stats':
            result = client.get_stats()
            print("📊 Dashboard Statistics:")
            print_json(result)
            
        elif args.command == 'health':
            result = client.health_check()
            print("💚 System Health:")
            print_json(result)
            
        elif args.command == 'verify':
            result = client.verify_token()
            if result.get('valid'):
                print("✅ Token is valid!")
                print_json(result)
            else:
                print("❌ Token is invalid!")
                print_json(result)
                sys.exit(1)
                
        elif args.command == 'generate':
            print(f"🚀 Generating application '{args.name}' with {args.model}...")
            result = client.generate_app(
                model=args.model,
                template_id=args.template,
                app_name=args.name,
                description=args.description
            )
            print("✅ Generation request submitted!")
            print_json(result)
            
        else:
            # No command specified, enter interactive mode
            interactive_mode(client)
            
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
