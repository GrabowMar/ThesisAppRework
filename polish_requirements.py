"""Polish and improve all requirements files for better clarity and consistency."""
import json
from pathlib import Path

REQUIREMENTS_DIR = Path('misc/requirements')

# Map of slug to improved requirements
IMPROVEMENTS = {
    "api_weather_display": {
        "api_endpoints": [
            {"method": "GET", "path": "/api/weather", "description": "Get weather for a city (query param: city)"},
            {"method": "GET", "path": "/api/health", "description": "Health check endpoint"}
        ],
        "backend_requirements": [
            "1. GET /api/weather?city=name - proxy to OpenWeatherMap API with your API key",
            "2. Return JSON: {city, temperature, condition, humidity, feels_like, icon}",
            "3. Cache results for 15 minutes per city to avoid API rate limits",
            "4. Handle API errors gracefully: 404 for city not found, 503 for API unavailable",
            "5. Validate city parameter is not empty, return 400 if missing"
        ]
    },
    "api_url_shortener": {
        "api_endpoints": [
            {"method": "POST", "path": "/api/shorten", "description": "Create short URL"},
            {"method": "GET", "path": "/api/urls", "description": "List all shortened URLs"},
            {"method": "GET", "path": "/:code", "description": "Redirect to original URL"},
            {"method": "GET", "path": "/api/health", "description": "Health check endpoint"}
        ]
    },
    "auth_user_login": {
        "api_endpoints": [
            {"method": "POST", "path": "/api/auth/register", "description": "Register new user"},
            {"method": "POST", "path": "/api/auth/login", "description": "Login and get JWT token"},
            {"method": "GET", "path": "/api/auth/me", "description": "Get current user info"},
            {"method": "POST", "path": "/api/auth/logout", "description": "Logout user"},
            {"method": "GET", "path": "/api/health", "description": "Health check endpoint"}
        ],
        "backend_requirements": [
            "1. User model: id, username (unique, required), password_hash, email, created_at",
            "2. POST /api/auth/register - validate username/password, hash with bcrypt, return user object",
            "3. POST /api/auth/login - verify credentials, return JWT token with 24h expiry",
            "4. GET /api/auth/me - validate JWT token, return current user info (exclude password)",
            "5. Validate: username 3-20 chars, password min 6 chars, unique username"
        ]
    },
    "fileproc_image_upload": {
        "api_endpoints": [
            {"method": "POST", "path": "/api/images/upload", "description": "Upload image file"},
            {"method": "GET", "path": "/api/images", "description": "List all images"},
            {"method": "DELETE", "path": "/api/images/:id", "description": "Delete image"},
            {"method": "GET", "path": "/uploads/:filename", "description": "Serve image file"},
            {"method": "GET", "path": "/api/health", "description": "Health check endpoint"}
        ]
    },
    "gaming_leaderboard": {
        "api_endpoints": [
            {"method": "POST", "path": "/api/scores", "description": "Submit new score"},
            {"method": "GET", "path": "/api/leaderboard", "description": "Get top scores"},
            {"method": "GET", "path": "/api/scores/:playername", "description": "Get player's scores"},
            {"method": "GET", "path": "/api/health", "description": "Health check endpoint"}
        ]
    },
    "collaboration_simple_poll": {
        "api_endpoints": [
            {"method": "POST", "path": "/api/polls", "description": "Create new poll"},
            {"method": "GET", "path": "/api/polls", "description": "List all polls"},
            {"method": "GET", "path": "/api/polls/:id", "description": "Get poll details with vote counts"},
            {"method": "POST", "path": "/api/polls/:id/vote", "description": "Vote on a poll option"},
            {"method": "GET", "path": "/api/health", "description": "Health check endpoint"}
        ]
    },
    "education_quiz_app": {
        "api_endpoints": [
            {"method": "GET", "path": "/api/quiz/questions", "description": "Get random quiz questions"},
            {"method": "POST", "path": "/api/quiz/submit", "description": "Submit quiz answers and get score"},
            {"method": "GET", "path": "/api/quiz/review/:id", "description": "Review quiz results"},
            {"method": "GET", "path": "/api/health", "description": "Health check endpoint"}
        ]
    },
    "utility_base64_tool": {
        "api_endpoints": [
            {"method": "POST", "path": "/api/base64/encode", "description": "Encode text to base64"},
            {"method": "POST", "path": "/api/base64/decode", "description": "Decode base64 to text"},
            {"method": "GET", "path": "/api/health", "description": "Health check endpoint"}
        ]
    }
}

def improve_file(filepath):
    """Apply improvements to a requirements file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        slug = data.get('slug')
        if not slug:
            print(f"  Skipped {filepath.name} (no slug)")
            return False
        
        modified = False
        
        # Apply improvements if available
        if slug in IMPROVEMENTS:
            improvements = IMPROVEMENTS[slug]
            
            for key, value in improvements.items():
                if key in data:
                    old_value = data[key]
                    data[key] = value
                    if old_value != value:
                        modified = True
                        print(f"  ✓ Updated {slug}: {key}")
        
        # Remove control_endpoints (redundant with health in api_endpoints)
        if 'control_endpoints' in data:
            del data['control_endpoints']
            modified = True
        
        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        
        return False
            
    except Exception as e:
        print(f"  ✗ Error processing {filepath.name}: {e}")
        return False

def main():
    """Process all requirements files."""
    if not REQUIREMENTS_DIR.exists():
        print(f"Error: Requirements directory not found: {REQUIREMENTS_DIR}")
        return
    
    json_files = list(REQUIREMENTS_DIR.glob('*.json'))
    if not json_files:
        print(f"No JSON files found in {REQUIREMENTS_DIR}")
        return
    
    print(f"Polishing {len(json_files)} requirement files...\n")
    
    updated_count = 0
    for filepath in sorted(json_files):
        if improve_file(filepath):
            updated_count += 1
    
    print(f"\n✓ Complete! Improved {updated_count}/{len(json_files)} files")

if __name__ == '__main__':
    main()
