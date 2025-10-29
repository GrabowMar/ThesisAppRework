"""
Generate API token for testing
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models import User
from app.extensions import db
import secrets

def generate_token():
    """Generate API token for admin user"""
    app = create_app()
    
    with app.app_context():
        # Find admin user
        admin = User.query.filter_by(username='admin').first()
        
        if not admin:
            print("❌ Admin user not found. Create one with: python scripts/create_admin.py")
            return None
        
        # Generate token using the User model's method
        token = admin.generate_api_token()
        
        print(f"✅ API Token generated for user: {admin.username}")
        print(f"\nToken: {token}")
        print(f"\nAdd to .env file:")
        print(f"API_KEY_FOR_APP={token}")
        
        return token

if __name__ == '__main__':
    token = generate_token()
    
    if token:
        # Optionally append to .env
        env_file = Path('.env')
        if env_file.exists():
            with open(env_file, 'a') as f:
                f.write(f"\n# API Token (generated {__import__('datetime').datetime.now()})\n")
                f.write(f"API_KEY_FOR_APP={token}\n")
            print(f"\n✅ Token appended to .env file")
