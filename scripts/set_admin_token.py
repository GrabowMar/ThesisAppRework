"""
Set API token for admin user directly
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Set Flask to not run dev server
import os
os.environ['WERKZEUG_RUN_MAIN'] = 'true'

from app.factory import create_app
from app.models import User
from app.extensions import db

def set_token():
    """Set API token for admin user"""
    app = create_app()
    
    with app.app_context():
        # Find admin user
        admin = User.query.filter_by(username='admin').first()
        
        if not admin:
            print("❌ Admin user not found")
            return None
        
        # Generate token
        token = admin.generate_api_token()
        
        print(f"✅ Token set for user: {admin.username}")
        print(f"Token: {token}")
        print(f"\n💾 Token saved to database")
        
        # Check it's actually in the DB
        db.session.refresh(admin)
        print(f"Verified in DB: api_token = {admin.api_token[:20]}...")
        
        return token

if __name__ == '__main__':
    token = set_token()
    
    if token:
        # Update .env
        env_file = Path('.env')
        lines = []
        found = False
        
        if env_file.exists():
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            # Replace existing or add new
            for i, line in enumerate(lines):
                if line.startswith('API_KEY_FOR_APP='):
                    lines[i] = f'API_KEY_FOR_APP={token}\n'
                    found = True
                    break
            
            if not found:
                lines.append(f'\n# API Token\nAPI_KEY_FOR_APP={token}\n')
            
            with open(env_file, 'w') as f:
                f.writelines(lines)
            
            print(f"✅ .env updated")
