# Implementation Prompt for Next Agent

## Comprehensive Development Task: AI Model Testing Framework Enhancement

You are tasked with enhancing and completing the AI Model Testing Framework - a Flask-based web application that analyzes AI-generated web applications. The system has a solid foundation but requires implementation of missing features and fixes for partially working systems.

---

## 🎯 **CRITICAL PRIORITY: Complete These Systems First**

### 1. **AI Analyzer Service Recovery (HIGH PRIORITY)**
**Problem**: The ai-analyzer service (port 8004) is disabled due to OpenRouter API issues
**Status**: Container exists but functionality broken
**Required Implementation**:

```python
# Fix src/core_services.py OpenRouterAnalysisService
class OpenRouterAnalysisService:
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')  # Add to environment
        self.base_url = "https://openrouter.ai/api/v1"
        self.enabled = bool(self.api_key)  # Only enable if API key exists
    
    async def analyze_code(self, model_slug: str, app_number: int, requirements: str = None):
        """Analyze AI-generated application code using OpenRouter models"""
        # 1. Get application source code from misc/models/{model}/app{num}/
        # 2. Send to OpenRouter API with analysis prompt
        # 3. Parse response and store in OpenRouterAnalysis table
        # 4. Handle rate limiting and API errors gracefully
        # 5. Support multiple analysis models (claude, gpt-4, etc.)
```

**Files to Modify**:
- `src/core_services.py` - Fix OpenRouterAnalysisService
- `testing-infrastructure/containers/ai-analyzer/` - Update container code
- `src/web_routes.py` - Add OpenRouter analysis endpoints
- `templates/partials/openrouter_analysis.html` - Create results template

### 2. **Background Job Processing System (HIGH PRIORITY)**
**Problem**: Long-running tests block request threads, no async processing
**Current**: Synchronous execution only
**Required Implementation**:

```python
# Add Celery + Redis for background processing
# Install: pip install celery redis

# Create src/tasks.py
from celery import Celery
from src.core_services import *

celery_app = Celery('testing_framework')
celery_app.config_from_object('src.celery_config')

@celery_app.task(bind=True)
def run_security_analysis_task(self, model_slug: str, app_number: int, tools: List[str]):
    """Background task for security analysis"""
    # 1. Update BatchTask status to 'running'
    # 2. Execute security analysis via containers
    # 3. Update progress periodically using self.update_state()
    # 4. Store results in SecurityAnalysis table
    # 5. Update BatchTask status to 'completed' or 'failed'

@celery_app.task(bind=True)
def run_performance_test_task(self, model_slug: str, app_number: int, config: dict):
    """Background task for performance testing"""
    # Similar implementation for performance tests

@celery_app.task(bind=True)
def run_batch_analysis_task(self, batch_job_id: int):
    """Background task for batch analysis coordination"""
    # 1. Get BatchJob and associated BatchTasks
    # 2. Execute tasks in parallel or sequence based on config
    # 3. Update overall job progress
    # 4. Handle task failures and retries
```

**Files to Create/Modify**:
- `src/tasks.py` - Celery task definitions
- `src/celery_config.py` - Celery configuration
- `src/core_services.py` - Update services to use async tasks
- `src/web_routes.py` - Add task status endpoints
- `requirements.txt` - Add celery, redis dependencies

### 3. **User Authentication System (HIGH PRIORITY)**
**Problem**: No user management, all data is public
**Required Implementation**:

```python
# Add Flask-Login for user management
# Install: pip install flask-login flask-wtf

# Create src/auth.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='user')  # user, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add user-specific foreign keys to existing models
    # SecurityAnalysis.user_id, PerformanceTest.user_id, BatchJob.created_by

# Create authentication routes
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Handle login form and session management

@auth_bp.route('/register', methods=['GET', 'POST'])  
def register():
    # Handle user registration

@auth_bp.route('/logout')
def logout():
    # Handle logout and session cleanup
```

**Files to Create/Modify**:
- `src/auth.py` - User model and authentication logic
- `src/models.py` - Add User model and user_id foreign keys
- `src/web_routes.py` - Protect routes with @login_required
- `templates/auth/` - Login/register templates
- `migrations/` - Database migration for User table

---

## 🔧 **MEDIUM PRIORITY: Fix Partially Working Systems**

### 4. **Enhanced Error Handling & Logging**
**Problem**: Inconsistent error handling, basic logging
**Required Implementation**:

```python
# Create src/error_handlers.py
from flask import render_template, jsonify, request
import logging
import traceback

@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found', 'code': 404}), 404
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    # Log full traceback
    app.logger.error(f"Internal error: {traceback.format_exc()}")
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error', 'code': 500}), 500
    return render_template('errors/500.html'), 500

# Add structured logging
class StructuredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        
    def log_operation(self, operation: str, model: str = None, app_num: int = None, 
                     duration: float = None, status: str = None, extra: dict = None):
        """Log operations with structured data for analysis"""
        log_data = {
            'operation': operation,
            'model': model,
            'app_number': app_num,
            'duration_ms': duration,
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
            **(extra or {})
        }
        self.logger.info(json.dumps(log_data))
```

### 5. **Real-time Notifications System**
**Problem**: No notifications for job completion
**Required Implementation**:

```python
# Add WebSocket support for real-time notifications
# Install: pip install flask-socketio

# Create src/notifications.py
from flask_socketio import SocketIO, emit
from src.models import User

socketio = SocketIO()

class NotificationService:
    def __init__(self):
        self.email_enabled = os.getenv('SMTP_HOST') is not None
        
    def send_job_completion_notification(self, user_id: int, job_id: int, status: str):
        """Send notification when job completes"""
        # 1. Send WebSocket notification to user's browser
        socketio.emit('job_completed', {
            'job_id': job_id,
            'status': status,
            'timestamp': datetime.utcnow().isoformat()
        }, room=f'user_{user_id}')
        
        # 2. Send email notification if enabled
        if self.email_enabled:
            self.send_email_notification(user_id, job_id, status)
            
    def send_email_notification(self, user_id: int, job_id: int, status: str):
        """Send email notification"""
        # Implementation for email notifications
```

### 6. **Advanced Export System**
**Problem**: Only basic CSV export available
**Required Implementation**:

```python
# Create src/export_service.py
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
import pandas as pd
from jinja2 import Template

class ExportService:
    def generate_security_report_pdf(self, analysis_id: int) -> bytes:
        """Generate comprehensive PDF security report"""
        # 1. Query SecurityAnalysis with related data
        # 2. Create PDF with charts, tables, recommendations
        # 3. Include executive summary and technical details
        # 4. Add branding and professional formatting
        
    def generate_batch_excel_report(self, batch_job_id: int) -> bytes:
        """Generate Excel report with multiple sheets"""
        # 1. Create workbook with summary, details, charts sheets
        # 2. Add conditional formatting for severity levels
        # 3. Include pivot tables and analysis
        
    def generate_custom_report(self, template_name: str, data: dict) -> bytes:
        """Generate custom report from Jinja2 template"""
        # Support for custom report templates
```

---

## 📊 **NEW FEATURES TO IMPLEMENT**

### 7. **Analytics Dashboard**
**Purpose**: Trend analysis and comparative reporting
**Required Implementation**:

```python
# Create src/analytics_service.py
class AnalyticsService:
    def get_security_trends(self, days: int = 30) -> dict:
        """Get security trends over time"""
        # 1. Query SecurityAnalysis grouped by date
        # 2. Calculate trend metrics (issues over time, severity distribution)
        # 3. Return data for charting (Chart.js format)
        
    def get_model_comparison(self, models: List[str]) -> dict:
        """Compare security/performance across models"""
        # 1. Aggregate data by model
        # 2. Calculate comparative metrics
        # 3. Statistical significance testing
        
    def get_performance_benchmarks(self) -> dict:
        """Get performance benchmarks and outliers"""
        # Performance analysis across applications
```

**Files to Create**:
- `src/analytics_service.py` - Analytics calculations
- `templates/pages/analytics.html` - Dashboard with charts
- `src/static/js/analytics.js` - Chart.js integration
- `src/web_routes.py` - Analytics endpoints

### 8. **API Rate Limiting & Security**
**Purpose**: Protect API from abuse
**Required Implementation**:

```python
# Install: pip install flask-limiter

# Create src/rate_limiting.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Add to routes
@limiter.limit("5 per minute")
@app.route('/api/create-test', methods=['POST'])
def create_test():
    # Rate limited endpoint

# Add API key authentication
class APIKeyService:
    def validate_api_key(self, key: str) -> bool:
        """Validate API key and track usage"""
        # Check API key against database
        # Track usage statistics
        # Return user permissions
```

### 9. **Caching Layer Implementation**
**Purpose**: Improve performance with Redis caching
**Required Implementation**:

```python
# Install: pip install redis flask-caching

# Create src/cache_service.py
from flask_caching import Cache

cache = Cache()

class CacheService:
    def cache_model_data(self, ttl: int = 3600):
        """Cache model capabilities and configurations"""
        
    def cache_analysis_results(self, analysis_id: str, data: dict, ttl: int = 7200):
        """Cache expensive analysis results"""
        
    def invalidate_model_cache(self, model_slug: str = None):
        """Invalidate cache when data changes"""
```

---

## 🐛 **BUG FIXES REQUIRED**

### 10. **Database Session Management**
**Problem**: Inconsistent session handling in some routes
**Fix Required**:

```python
# In src/web_routes.py - ensure all routes use proper session management
# WRONG:
def some_route():
    models = db.session.query(ModelCapability).all()  # Session might not close

# CORRECT:
def some_route():
    with get_session() as session:
        models = session.query(ModelCapability).all()
    # Session automatically closed
```

### 11. **Container Health Monitoring**
**Problem**: ai-analyzer service excluded from health checks
**Fix Required**:

```python
# In src/core_services.py - DockerManager.get_infrastructure_status()
# Add conditional inclusion of ai-analyzer based on configuration
def get_infrastructure_status(self) -> InfrastructureStatus:
    services = [
        'api-gateway', 'security-scanner', 'performance-tester', 
        'zap-scanner', 'test-coordinator'
    ]
    
    # Include ai-analyzer if OpenRouter API key is configured
    if os.getenv('OPENROUTER_API_KEY'):
        services.append('ai-analyzer')
```

---

## 📋 **DEVELOPMENT PLAN**

### Phase 1: Core Fixes (Week 1)
1. ✅ Fix ai-analyzer service with proper OpenRouter integration
2. ✅ Implement Celery background processing
3. ✅ Add user authentication system
4. ✅ Enhance error handling and logging

### Phase 2: Features (Week 2)  
1. ✅ Add real-time notifications (WebSocket + email)
2. ✅ Implement advanced export system (PDF, Excel)
3. ✅ Create analytics dashboard
4. ✅ Add API rate limiting and security

### Phase 3: Optimization (Week 3)
1. ✅ Implement Redis caching layer
2. ✅ Performance optimization and testing
3. ✅ Bug fixes and edge case handling
4. ✅ Documentation updates

---

## 🛠 **IMPLEMENTATION GUIDELINES**

### Code Standards
- **Follow existing patterns**: Use Service Locator, HTMX responses, context managers
- **Database first**: Always use SQLAlchemy models, never modify JSON files
- **Service integration**: Register new services in ServiceLocator
- **Template consistency**: Use Bootstrap 5 + HTMX patterns
- **Error handling**: Comprehensive try/catch with proper logging

### Testing Requirements
- **Unit tests**: Test all new services and methods
- **Integration tests**: Test complete workflows
- **Performance tests**: Ensure new features don't degrade performance
- **Security tests**: Validate authentication and authorization

### Configuration Management
```python
# Add to src/config.py
class Config:
    # Existing config...
    
    # New configurations needed
    CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    SMTP_HOST = os.getenv('SMTP_HOST')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
```

---

## 📁 **FILES TO FOCUS ON**

### Critical Files (Must Read First)
1. **`CURRENT_IMPLEMENTATION_ANALYSIS.md`** - Complete system overview
2. **`TECHNICAL_ARCHITECTURE.md`** - Architecture details and patterns
3. **`src/models.py`** - Database models (11 tables, 750+ lines)
4. **`src/core_services.py`** - Business logic (9 services, 1500+ lines)
5. **`src/web_routes.py`** - API endpoints (8 blueprints, 600+ lines)

### Key Directories
- **`src/templates/`** - 25+ templates (preserve all)
- **`testing-infrastructure/containers/`** - 5 containerized services
- **`misc/models/`** - 750 AI-generated apps (READ-ONLY reference)
- **`migrations/`** - Database schema evolution

### Configuration Files  
- **`testing-infrastructure/docker-compose.yml`** - Container orchestration
- **`requirements.txt`** - Python dependencies
- **`src/app.py`** - Flask application factory

---

## 🎯 **SUCCESS CRITERIA**

### Functional Requirements
- ✅ All 6 containerized services operational
- ✅ Background processing for long-running jobs
- ✅ User authentication and session management
- ✅ Real-time notifications and progress tracking
- ✅ Comprehensive export capabilities (PDF, Excel, CSV)
- ✅ Analytics dashboard with trend analysis
- ✅ API security with rate limiting

### Performance Targets
- ✅ Infrastructure status: <200ms response time
- ✅ Job creation: <2 seconds initialization
- ✅ Database queries: <100ms for standard operations
- ✅ Background task startup: <5 seconds
- ✅ Report generation: <30 seconds for complex reports

### Quality Assurance
- ✅ 90%+ test coverage for new code
- ✅ No broken existing functionality
- ✅ Comprehensive error handling
- ✅ Security audit passed
- ✅ Performance benchmarks met

---

## 🚀 **QUICK START FOR NEXT AGENT**

1. **Read Documentation**: Start with `CURRENT_IMPLEMENTATION_ANALYSIS.md`
2. **Test Current System**: Run `python src/app.py` and verify base functionality
3. **Check Services**: Run `docker-compose up` in testing-infrastructure/
4. **Priority Order**: ai-analyzer → background processing → authentication
5. **Validate Changes**: Test each implementation thoroughly before moving to next

The system has excellent architecture and documentation. Focus on implementing missing features while maintaining the established patterns and quality standards.

**Current Status: Solid foundation with 75% implementation complete. Ready for feature enhancement and production preparation.**
