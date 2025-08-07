# Database Schema Documentation

## Overview

This document provides comprehensive documentation of the database schema used in the AI Model Testing Framework. The system uses SQLite with SQLAlchemy ORM for data persistence, supporting complex relationships and JSON field storage.

## Database Configuration

**Database Engine**: SQLite  
**Location**: `src/data/thesis_app.db`  
**ORM**: SQLAlchemy 2.x  
**Migration Tool**: Alembic  
**Character Encoding**: UTF-8  

## Schema Overview

### Entity Relationship Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ ModelCapability │    │PortConfiguration│    │GeneratedApplication│
│                 │    │                 │    │                 │
│ • model_id (PK) │    │ • id (PK)       │    │ • id (PK)       │
│ • provider      │    │ • model_name    │    │ • model_slug    │
│ • model_name    │    │ • app_number    │    │ • app_number    │
│ • capabilities  │    │ • backend_port  │    │ • provider      │
│ • pricing       │    │ • frontend_port │    │ • created_at    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
        ┌──────────────────────────────────────────────┼─────────────────────────┐
        │                                              │                         │
        ▼                                              ▼                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ SecurityAnalysis│    │ PerformanceTest │    │   ZAPAnalysis   │    │OpenRouterAnalysis│
│                 │    │                 │    │                 │    │                 │
│ • id (PK)       │    │ • id (PK)       │    │ • id (PK)       │    │ • id (PK)       │
│ • application_id│    │ • application_id│    │ • application_id│    │ • application_id│
│ • tools_used    │    │ • test_config   │    │ • scan_type     │    │ • requirements  │
│ • results (JSON)│    │ • results (JSON)│    │ • results (JSON)│    │ • results (JSON)│
│ • status        │    │ • status        │    │ • status        │    │ • status        │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  BatchAnalysis  │    │    BatchJob     │    │   BatchTask     │
│                 │    │                 │    │                 │
│ • id (PK)       │    │ • id (PK)       │────┤ • id (PK)       │
│ • name          │    │ • name          │    │ • job_id (FK)   │
│ • models        │    │ • config (JSON) │    │ • model_name    │
│ • status        │    │ • status        │    │ • app_number    │
│ • results (JSON)│    │ • created_at    │    │ • status        │
└─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────┐
│ContainerizedTest│
│                 │
│ • id (PK)       │
│ • test_id       │
│ • application_id│
│ • test_type     │
│ • status        │
│ • result_data   │
└─────────────────┘
```

## Table Definitions

### 1. ModelCapability

**Purpose**: Stores AI model metadata and capabilities  
**Table Name**: `model_capabilities`

```sql
CREATE TABLE model_capabilities (
    model_id VARCHAR(100) PRIMARY KEY,
    canonical_slug VARCHAR(150) UNIQUE NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    context_window INTEGER,
    max_output_tokens INTEGER,
    input_price_per_token FLOAT,
    output_price_per_token FLOAT,
    supports_vision BOOLEAN DEFAULT FALSE,
    supports_function_calling BOOLEAN DEFAULT FALSE,
    supports_streaming BOOLEAN DEFAULT FALSE,
    supports_json_mode BOOLEAN DEFAULT FALSE,
    is_free BOOLEAN DEFAULT FALSE,
    cost_efficiency FLOAT,
    safety_score FLOAT,
    additional_capabilities TEXT, -- JSON
    created_at DATETIME DEFAULT (datetime('now', 'utc')),
    updated_at DATETIME DEFAULT (datetime('now', 'utc'))
);
```

**Key Fields:**
- `model_id`: Unique identifier for the model
- `canonical_slug`: URL-safe model identifier
- `provider`: Model provider (anthropic, openai, google, etc.)
- `additional_capabilities`: JSON field for extensible capabilities

**Sample Data:**
```json
{
  "model_id": "anthropic_claude-3.7-sonnet",
  "canonical_slug": "anthropic_claude-3.7-sonnet",
  "provider": "anthropic",
  "model_name": "claude-3.7-sonnet",
  "context_window": 200000,
  "max_output_tokens": 4096,
  "input_price_per_token": 0.000003,
  "output_price_per_token": 0.000015,
  "supports_vision": false,
  "supports_function_calling": true,
  "additional_capabilities": "{\"reasoning\": true, \"code_analysis\": true}"
}
```

### 2. PortConfiguration

**Purpose**: Docker port allocations for model applications  
**Table Name**: `port_configurations`

```sql
CREATE TABLE port_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name VARCHAR(100) NOT NULL,
    app_number INTEGER NOT NULL,
    backend_port INTEGER NOT NULL,
    frontend_port INTEGER NOT NULL,
    UNIQUE(model_name, app_number),
    UNIQUE(backend_port),
    UNIQUE(frontend_port)
);
```

**Key Constraints:**
- Unique combination of model_name + app_number
- Unique port allocations to prevent conflicts
- Port ranges: Backend (6001-6750), Frontend (9001-9750)

**Sample Data:**
```json
{
  "model_name": "anthropic_claude-3.7-sonnet",
  "app_number": 1,
  "backend_port": 6001,
  "frontend_port": 9001
}
```

### 3. GeneratedApplication

**Purpose**: Tracks AI-generated application instances  
**Table Name**: `generated_applications`

```sql
CREATE TABLE generated_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_slug VARCHAR(150) NOT NULL,
    app_number INTEGER NOT NULL,
    provider VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active',
    docker_config TEXT, -- JSON
    app_metadata TEXT, -- JSON
    created_at DATETIME DEFAULT (datetime('now', 'utc')),
    updated_at DATETIME DEFAULT (datetime('now', 'utc')),
    UNIQUE(model_slug, app_number)
);
```

**Key Features:**
- Links to model via model_slug
- Stores Docker configuration as JSON
- Metadata field for extensible application information

### 4. SecurityAnalysis

**Purpose**: Security analysis results storage  
**Table Name**: `security_analyses`

```sql
CREATE TABLE security_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    analysis_type VARCHAR(50) DEFAULT 'security',
    enabled_tools TEXT, -- JSON list
    
    -- Tool-specific flags
    bandit_enabled BOOLEAN DEFAULT FALSE,
    safety_enabled BOOLEAN DEFAULT FALSE,
    pylint_enabled BOOLEAN DEFAULT FALSE,
    eslint_enabled BOOLEAN DEFAULT FALSE,
    npm_audit_enabled BOOLEAN DEFAULT FALSE,
    
    -- Results
    issues_found INTEGER DEFAULT 0,
    critical_count INTEGER DEFAULT 0,
    high_count INTEGER DEFAULT 0,
    medium_count INTEGER DEFAULT 0,
    low_count INTEGER DEFAULT 0,
    
    -- Analysis metadata
    status VARCHAR(20) DEFAULT 'pending',
    results TEXT, -- JSON
    execution_time FLOAT,
    error_message TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now', 'utc')),
    completed_at DATETIME,
    
    FOREIGN KEY (application_id) REFERENCES generated_applications (id) ON DELETE CASCADE
);
```

**JSON Fields:**

**enabled_tools format:**
```json
["bandit", "safety", "pylint", "eslint"]
```

**results format:**
```json
{
  "bandit": {
    "issues_found": 5,
    "severity_breakdown": {
      "high": 1,
      "medium": 3,
      "low": 1
    },
    "detailed_findings": [
      {
        "file": "app.py",
        "line": 45,
        "issue": "Possible SQL injection",
        "severity": "high",
        "confidence": "high"
      }
    ]
  },
  "safety": {
    "vulnerabilities": 2,
    "packages_checked": 25
  }
}
```

### 5. PerformanceTest

**Purpose**: Performance testing results  
**Table Name**: `performance_tests`

```sql
CREATE TABLE performance_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    test_type VARCHAR(50) DEFAULT 'load_test',
    test_config TEXT, -- JSON
    
    -- Results
    requests_per_second FLOAT,
    average_response_time FLOAT,
    max_response_time FLOAT,
    min_response_time FLOAT,
    error_rate FLOAT,
    total_requests INTEGER,
    failed_requests INTEGER,
    
    -- Test metadata
    status VARCHAR(20) DEFAULT 'pending',
    results TEXT, -- JSON
    execution_time FLOAT,
    error_message TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now', 'utc')),
    completed_at DATETIME,
    
    FOREIGN KEY (application_id) REFERENCES generated_applications (id) ON DELETE CASCADE
);
```

**test_config format:**
```json
{
  "duration": 300,
  "concurrent_users": 10,
  "ramp_up_time": 30,
  "target_url": "http://localhost:6001",
  "test_scenarios": [
    {
      "name": "login_test",
      "weight": 60,
      "endpoints": ["/api/login", "/api/dashboard"]
    }
  ]
}
```

**results format:**
```json
{
  "summary": {
    "total_requests": 15000,
    "requests_per_second": 50.2,
    "average_response_time": 125,
    "error_rate": 0.02
  },
  "timeline": [
    {
      "timestamp": "2025-08-07T11:00:00Z",
      "rps": 45.1,
      "response_time": 130
    }
  ],
  "endpoints": {
    "/api/login": {
      "requests": 9000,
      "avg_response_time": 110,
      "error_rate": 0.01
    }
  }
}
```

### 6. ZAPAnalysis

**Purpose**: OWASP ZAP security scan results  
**Table Name**: `zap_analyses`

```sql
CREATE TABLE zap_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    scan_type VARCHAR(50) DEFAULT 'baseline',
    target_url VARCHAR(200),
    
    -- Results
    alerts_count INTEGER DEFAULT 0,
    high_risk_count INTEGER DEFAULT 0,
    medium_risk_count INTEGER DEFAULT 0,
    low_risk_count INTEGER DEFAULT 0,
    info_count INTEGER DEFAULT 0,
    
    -- Analysis metadata
    status VARCHAR(20) DEFAULT 'pending',
    results TEXT, -- JSON
    execution_time FLOAT,
    error_message TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now', 'utc')),
    completed_at DATETIME,
    
    FOREIGN KEY (application_id) REFERENCES generated_applications (id) ON DELETE CASCADE
);
```

### 7. OpenRouterAnalysis

**Purpose**: AI-based code analysis results  
**Table Name**: `openrouter_analyses`

```sql
CREATE TABLE openrouter_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    analysis_model VARCHAR(100),
    requirements TEXT,
    
    -- Results
    score FLOAT,
    issues_identified INTEGER DEFAULT 0,
    suggestions_count INTEGER DEFAULT 0,
    
    -- Analysis metadata
    status VARCHAR(20) DEFAULT 'pending',
    results TEXT, -- JSON
    execution_time FLOAT,
    error_message TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now', 'utc')),
    completed_at DATETIME,
    
    FOREIGN KEY (application_id) REFERENCES generated_applications (id) ON DELETE CASCADE
);
```

### 8. ContainerizedTest

**Purpose**: Track tests submitted to containerized services  
**Table Name**: `containerized_tests`

```sql
CREATE TABLE containerized_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id VARCHAR(100) UNIQUE NOT NULL,
    application_id INTEGER NOT NULL,
    
    -- Test configuration
    test_type VARCHAR(50) NOT NULL,
    service_endpoint VARCHAR(200),
    tools_used TEXT, -- JSON
    
    -- Test lifecycle
    status VARCHAR(20) DEFAULT 'pending',
    submitted_at DATETIME DEFAULT (datetime('now', 'utc')),
    started_at DATETIME,
    completed_at DATETIME,
    
    -- Results
    result_data TEXT, -- JSON
    error_message TEXT,
    execution_duration FLOAT,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now', 'utc')),
    updated_at DATETIME DEFAULT (datetime('now', 'utc')),
    
    FOREIGN KEY (application_id) REFERENCES generated_applications (id) ON DELETE CASCADE
);
```

### 9. BatchAnalysis (Legacy)

**Purpose**: Legacy batch processing records  
**Table Name**: `batch_analyses`

```sql
CREATE TABLE batch_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    models TEXT, -- JSON list
    tools TEXT, -- JSON list
    status VARCHAR(20) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    config TEXT, -- JSON
    results TEXT, -- JSON
    error_message TEXT,
    created_at DATETIME DEFAULT (datetime('now', 'utc')),
    started_at DATETIME,
    completed_at DATETIME
);
```

### 10. BatchJob (Enhanced)

**Purpose**: Enhanced batch job management  
**Table Name**: `batch_jobs`

```sql
CREATE TABLE batch_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Job configuration
    config TEXT, -- JSON
    priority VARCHAR(20) DEFAULT 'normal',
    
    -- Job status
    status VARCHAR(20) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    
    -- Results
    results TEXT, -- JSON
    total_tests INTEGER DEFAULT 0,
    completed_tests INTEGER DEFAULT 0,
    failed_tests INTEGER DEFAULT 0,
    
    -- Metadata
    error_message TEXT,
    created_by VARCHAR(100),
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now', 'utc')),
    started_at DATETIME,
    completed_at DATETIME,
    updated_at DATETIME DEFAULT (datetime('now', 'utc'))
);
```

### 11. BatchTask

**Purpose**: Individual tasks within batch jobs  
**Table Name**: `batch_tasks`

```sql
CREATE TABLE batch_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    
    -- Task definition
    model_name VARCHAR(100) NOT NULL,
    app_number INTEGER NOT NULL,
    test_type VARCHAR(50) NOT NULL,
    config TEXT, -- JSON
    
    -- Task status
    status VARCHAR(20) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    
    -- Results
    results TEXT, -- JSON
    error_message TEXT,
    
    -- Timing
    estimated_duration INTEGER,
    actual_duration FLOAT,
    
    -- Timestamps
    created_at DATETIME DEFAULT (datetime('now', 'utc')),
    started_at DATETIME,
    completed_at DATETIME,
    
    FOREIGN KEY (job_id) REFERENCES batch_jobs (id) ON DELETE CASCADE
);
```

## Enums and Constants

### Status Enums

```python
from enum import Enum

class AnalysisStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class JobPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
```

## Indexes and Performance

### Primary Indexes

```sql
-- Performance optimization indexes
CREATE INDEX idx_security_analyses_application_id ON security_analyses (application_id);
CREATE INDEX idx_security_analyses_status ON security_analyses (status);
CREATE INDEX idx_security_analyses_created_at ON security_analyses (created_at);

CREATE INDEX idx_performance_tests_application_id ON performance_tests (application_id);
CREATE INDEX idx_performance_tests_status ON performance_tests (status);

CREATE INDEX idx_batch_jobs_status ON batch_jobs (status);
CREATE INDEX idx_batch_jobs_created_at ON batch_jobs (created_at);

CREATE INDEX idx_batch_tasks_job_id ON batch_tasks (job_id);
CREATE INDEX idx_batch_tasks_status ON batch_tasks (status);

CREATE INDEX idx_containerized_tests_test_id ON containerized_tests (test_id);
CREATE INDEX idx_containerized_tests_application_id ON containerized_tests (application_id);
CREATE INDEX idx_containerized_tests_status ON containerized_tests (status);
```

### Composite Indexes

```sql
-- Composite indexes for common queries
CREATE INDEX idx_generated_applications_model_app ON generated_applications (model_slug, app_number);
CREATE INDEX idx_port_configurations_model_app ON port_configurations (model_name, app_number);
CREATE INDEX idx_batch_tasks_job_status ON batch_tasks (job_id, status);
```

## Database Migrations

### Migration Files Location
`migrations/versions/`

### Current Migration
**File**: `19355bb85378_add_zap_and_openrouter_analysis_tables.py`  
**Description**: Adds ZAP and OpenRouter analysis tables

### Migration Commands

```bash
# Generate new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Check current version
alembic current

# View migration history
alembic history
```

## Database Utilities

### Connection Management

```python
from src.extensions import get_session

# Context manager pattern
with get_session() as session:
    models = session.query(ModelCapability).all()
    # Session automatically closed

# Direct access for Flask routes
from src.extensions import db
models = db.session.query(ModelCapability).all()
```

### JSON Field Helpers

```python
# Model with JSON helpers
class SecurityAnalysis(db.Model):
    enabled_tools = db.Column(db.Text)
    
    def get_enabled_tools(self) -> List[str]:
        if self.enabled_tools:
            try:
                return json.loads(self.enabled_tools)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_enabled_tools(self, tools_list: List[str]):
        self.enabled_tools = json.dumps(tools_list) if tools_list else None
```

### Bulk Operations

```python
# Bulk insert example
def create_port_configurations(models: List[str], apps_per_model: int = 30):
    configurations = []
    
    for model_name in models:
        for app_num in range(1, apps_per_model + 1):
            config = PortConfiguration(
                model_name=model_name,
                app_number=app_num,
                backend_port=6000 + (len(configurations) + 1),
                frontend_port=9000 + (len(configurations) + 1)
            )
            configurations.append(config)
    
    with get_session() as session:
        session.bulk_save_objects(configurations)
        session.commit()
```

## Database Backup and Maintenance

### Backup Strategy

```bash
# Create backup
cp src/data/thesis_app.db src/data/backups/thesis_app_$(date +%Y%m%d_%H%M%S).db

# Automated backup script
sqlite3 src/data/thesis_app.db ".backup src/data/backups/thesis_app_backup.db"
```

### Maintenance Queries

```sql
-- Check database size
SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();

-- Analyze table statistics
ANALYZE;

-- Vacuum database (defragment)
VACUUM;

-- Check integrity
PRAGMA integrity_check;
```

## Data Constraints and Validation

### Business Rules

1. **Model-App Uniqueness**: Each model can have up to 30 applications
2. **Port Uniqueness**: No two applications can share the same port
3. **Status Progression**: Status changes follow defined state machine
4. **Cascade Deletes**: Analysis records deleted when application is removed
5. **JSON Validation**: JSON fields validated at application level

### Referential Integrity

```sql
-- Foreign key constraints
PRAGMA foreign_keys = ON;

-- Check constraint examples
ALTER TABLE batch_jobs ADD CONSTRAINT chk_progress 
CHECK (progress >= 0 AND progress <= 100);

ALTER TABLE port_configurations ADD CONSTRAINT chk_app_number
CHECK (app_number >= 1 AND app_number <= 30);
```

This database schema provides a robust foundation for the AI model testing framework with proper normalization, indexing, and constraint management.
