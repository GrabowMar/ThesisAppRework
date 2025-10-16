# Sample Generator Quick Start Guide

## Quick Reference

### Generate a Single App
```bash
# Via analyzer manager
python analyzer/analyzer_manager.py analyze <model> <app_num>

# Examples
python analyzer/analyzer_manager.py analyze anthropic_claude-3.5-sonnet 1
python analyzer/analyzer_manager.py analyze openai_gpt-4 2
```

### Generate via Web Interface
1. Navigate to `/sample-generator` in the web UI
2. Select model and app template
3. Click "Generate"
4. Monitor progress in status panel

## What Gets Generated

Each generated app includes:

```
generated/apps/<model>/app<N>/
├── docker-compose.yml          ✅ Complete orchestration
├── backend/
│   ├── app.py                 ✅ Full Flask app with auth, DB, routes
│   ├── requirements.txt       ✅ All dependencies
│   ├── Dockerfile             ✅ Production-ready
│   ├── .dockerignore          ✅ Optimized builds
│   └── .env.example           ✅ Configuration template
├── frontend/
│   ├── src/
│   │   ├── App.jsx           ✅ Complete React app with hooks, components
│   │   └── App.css           ✅ Responsive styles
│   ├── index.html            ✅ Entry point
│   ├── package.json          ✅ Dependencies
│   ├── vite.config.js        ✅ Dev server config
│   ├── Dockerfile            ✅ Production-ready
│   ├── .dockerignore         ✅ Optimized builds
│   └── .env.example          ✅ Configuration template
├── PROJECT_INDEX.md          ✅ Generated file summary
└── README.md                 ✅ Setup instructions
```

## Template Structure

### Backend (app.py)

Generated apps follow this structure:

```python
# 1. Imports
from flask import Flask, jsonify, request
from flask_cors import CORS
# ... all necessary imports

# 2. Configuration
app = Flask(__name__)
CORS(app, ...)

# 3. Database Management
@contextmanager
def get_db():
    # Context manager for connections

def init_db():
    # Table creation

# 4. Models
class User:
    @staticmethod
    def create(...): ...
    @staticmethod
    def get_by_username(...): ...

class Item:
    # Example CRUD model

# 5. API Routes
@app.route('/')
@app.route('/health')
@app.route('/api/auth/register')
@app.route('/api/auth/login')
@app.route('/api/items')
# ... all endpoints

# 6. Error Handlers
@app.errorhandler(404)
@app.errorhandler(500)

# 7. Entry Point
if __name__ == "__main__":
    init_db()
    app.run(...)
```

### Frontend (App.jsx)

Generated apps follow this structure:

```javascript
// 1. Imports
import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';

// 2. Configuration
const API_CONFIG = {
    baseURL: import.meta.env.VITE_BACKEND_URL || 'http://localhost:5000',
    timeout: 5000,
};

// 3. API Service Layer
class ApiService {
    static async request(endpoint, options) { ... }
    static async get(endpoint) { ... }
    static async post(endpoint, data) { ... }
}

// 4. Custom Hooks
function useFetch(endpoint, dependencies) { ... }
function useForm(initialValues, onSubmit) { ... }

// 5. UI Components
function LoadingSpinner({ message }) { ... }
function ErrorMessage({ error, onRetry }) { ... }
function FormInput({ label, name, ... }) { ... }
function Card({ title, children }) { ... }

// 6. Feature Components
function HealthCheck() { ... }
function ExampleForm() { ... }

// 7. Main App
function App() {
    // Navigation state
    // Views
}

// 8. Styles
const styles = { ... };

// 9. Initialization
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
```

## Running Generated Apps

### Development (Docker Compose)
```bash
cd generated/apps/<model>/app1
docker-compose up --build
```

Access:
- **Frontend**: http://localhost:<frontend_port>
- **Backend**: http://localhost:<backend_port>
- **Health**: http://localhost:<backend_port>/health

### Local Development

**Backend**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev
```

## Extending Generated Apps

### Adding a New Backend Route

Follow the existing pattern:

```python
# Add to Models section
class NewModel:
    @staticmethod
    def create(data):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO new_table ...', (...))
            return cursor.lastrowid

# Add to init_db()
def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        # ... existing tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ...
            )
        ''')

# Add to Routes section
@app.route('/api/new-resource', methods=['GET', 'POST'])
def new_resource():
    if request.method == 'GET':
        items = NewModel.get_all()
        return jsonify({'items': items}), 200
    elif request.method == 'POST':
        data = request.get_json()
        item_id = NewModel.create(data)
        return jsonify({'id': item_id}), 201
```

### Adding a New Frontend Component

Follow the existing patterns:

```javascript
// Add new feature component
function NewFeature() {
    const { data, loading, error } = useFetch('/api/new-resource');
    
    if (loading) return <LoadingSpinner />;
    if (error) return <ErrorMessage error={error} />;
    
    return (
        <Card title="New Feature">
            {/* Your component JSX */}
        </Card>
    );
}

// Add to App navigation
function App() {
    const [activeView, setActiveView] = useState('home');
    
    return (
        <div style={styles.app}>
            <header style={styles.header}>
                <nav style={styles.nav}>
                    {/* Existing buttons */}
                    <button
                        onClick={() => setActiveView('newfeature')}
                        style={activeView === 'newfeature' ? styles.navButtonActive : styles.navButton}
                    >
                        New Feature
                    </button>
                </nav>
            </header>
            
            <main style={styles.main}>
                {/* Existing views */}
                {activeView === 'newfeature' && <NewFeature />}
            </main>
        </div>
    );
}
```

## Validation

Generated code is automatically validated for:

✅ **No placeholders** - No `TODO`, `FIXME`, `... rest of code`
✅ **Complete imports** - All necessary imports present
✅ **Proper structure** - Follows template organization
✅ **Syntax correctness** - Python code compiles, JSX is balanced
✅ **Required patterns** - Flask app setup, React components, etc.

Check validation results in logs:
```bash
# Look for validation warnings
grep "Validation issues" logs/app.log
```

## Troubleshooting

### App doesn't start
1. Check Docker is running
2. Verify ports aren't in use:
   ```bash
   netstat -an | grep <port>
   ```
3. Check logs:
   ```bash
   docker-compose logs backend
   docker-compose logs frontend
   ```

### Code has placeholders
This shouldn't happen with the new system, but if it does:
1. Check generation logs for validation warnings
2. Manually complete the missing sections following template patterns
3. Report the issue with model name and app number

### Missing files
1. Check scaffold log output for copy failures
2. Manually copy from `misc/code_templates/`
3. Report the issue

### Structure doesn't match template
This indicates the AI model didn't follow instructions:
1. Check `SAMPLE_GENERATOR_IMPROVEMENTS.md` for expected structure
2. Manually restructure following the template
3. Consider trying a different model

## Best Practices

### Choosing Models
- **Best results**: GPT-4, Claude 3.5 Sonnet, Gemini 1.5 Pro
- **Good results**: GPT-4o-mini, Claude 3 Haiku, Llama 3
- **Variable**: Smaller or specialized models

### Template Selection
- App 1: Login/Authentication
- App 2: Real-time Chat
- App 3: Feedback System
- App 4: Blog/CMS
- App 5: Shopping Cart
- [See `misc/app_templates/` for full list]

### After Generation
1. ✅ Verify all files exist
2. ✅ Check for validation warnings
3. ✅ Test with `docker-compose up`
4. ✅ Verify API endpoints work
5. ✅ Check frontend loads and connects
6. ✅ Review and enhance as needed

## Advanced Usage

### Batch Generation
```bash
# Create batch file: batch.json
[
    ["anthropic_claude-3.5-sonnet", 1],
    ["anthropic_claude-3.5-sonnet", 2],
    ["openai_gpt-4", 1]
]

# Run batch
python analyzer/analyzer_manager.py batch batch.json
```

### Custom Templates
1. Create template in `misc/app_templates/`
2. Add frontend/backend requirements
3. Generate using template number

### Override Settings
```bash
# Set environment variables
export OPENROUTER_API_KEY=your_key
export MAX_RETRIES=3
export GENERATION_TIMEOUT=300

# Run generation
python analyzer/analyzer_manager.py analyze <model> <app>
```

## Support

- **Documentation**: See `docs/SAMPLE_GENERATOR_IMPROVEMENTS.md`
- **Architecture**: See `docs/ARCHITECTURE.md`
- **Issues**: Check validation logs and error messages
- **Examples**: See `generated/apps/` for reference implementations
