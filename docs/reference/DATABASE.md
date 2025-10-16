# Database Schema Reference

> Complete database schema and model reference for ThesisApp

---

## Overview

ThesisApp uses **SQLAlchemy ORM** with support for both SQLite (development) and PostgreSQL (production).

```mermaid
erDiagram
    GeneratedApplication ||--o{ AnalysisTask : has
    GeneratedApplication ||--o{ PortAllocation : has
    ModelCapability ||--o{ GeneratedApplication : generates
    AnalysisTask ||--o{ TaskResult : produces
    
    GeneratedApplication {
        int id PK
        string model_slug FK
        int app_number
        string status
        datetime created_at
        json metadata
    }
    
    ModelCapability {
        int id PK
        string canonical_slug UK
        string display_name
        string provider
        float parameters_billions
        int context_length
    }
    
    AnalysisTask {
        int id PK
        int application_id FK
        string task_type
        string status
        datetime started_at
        datetime completed_at
    }
    
    PortAllocation {
        int id PK
        string model_name
        int app_number
        int backend_port
        int frontend_port
    }
```

---

## Core Models

### GeneratedApplication

Stores metadata about AI-generated applications.

**Table**: `generated_applications`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PRIMARY KEY | Unique identifier |
| `model_slug` | String(200) | NOT NULL, INDEXED | Model identifier (e.g., `anthropic_claude-3.5-sonnet`) |
| `app_number` | Integer | NOT NULL | Application number (1-30) |
| `status` | String(50) | DEFAULT 'created' | Container status: `running`, `stopped`, `not_created`, `no_compose` |
| `created_at` | DateTime | DEFAULT now() | Creation timestamp |
| `updated_at` | DateTime | ON UPDATE now() | Last update timestamp |
| `last_status_check` | DateTime | NULLABLE | Last status check timestamp |
| `generation_metadata` | JSON | NULLABLE | Generation details |

**Indexes**:
- `UNIQUE(model_slug, app_number)` - Prevents duplicates
- `INDEX(last_status_check)` - Optimizes status queries

**Example**:
```python
app = GeneratedApplication(
    model_slug='anthropic_claude-3.5-sonnet',
    app_number=1,
    status='running',
    generation_metadata={
        'template_id': 5,
        'template_name': 'Shopping Cart',
        'generation_time': 87.3
    }
)
```

---

### ModelCapability

Stores AI model metadata and capabilities.

**Table**: `model_capabilities`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PRIMARY KEY | Unique identifier |
| `canonical_slug` | String(200) | UNIQUE, NOT NULL | Normalized model name |
| `display_name` | String(200) | NOT NULL | Human-readable name |
| `provider` | String(100) | NOT NULL | Provider (e.g., `anthropic`, `openai`) |
| `model_id_openrouter` | String(200) | NULLABLE | OpenRouter model ID |
| `parameters_billions` | Float | NULLABLE | Model size in billions |
| `context_length` | Integer | NULLABLE | Maximum context tokens |
| `pricing_prompt` | Float | NULLABLE | Cost per 1M prompt tokens |
| `pricing_completion` | Float | NULLABLE | Cost per 1M completion tokens |

**Example**:
```python
model = ModelCapability(
    canonical_slug='anthropic_claude-3.5-sonnet',
    display_name='Claude 3.5 Sonnet',
    provider='anthropic',
    model_id_openrouter='anthropic/claude-3.5-sonnet',
    parameters_billions=200.0,
    context_length=200000,
    pricing_prompt=3.0,
    pricing_completion=15.0
)
```

---

### AnalysisTask

Tracks analysis execution and results.

**Table**: `analysis_tasks`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PRIMARY KEY | Unique identifier |
| `task_id` | String(100) | UNIQUE, NOT NULL | Task identifier |
| `application_id` | Integer | FOREIGN KEY | Reference to generated_applications |
| `task_type` | String(50) | NOT NULL | Type: `security`, `performance`, `quality`, `ai_review` |
| `status` | String(50) | DEFAULT 'pending' | Status: `pending`, `running`, `completed`, `failed` |
| `started_at` | DateTime | NULLABLE | Start timestamp |
| `completed_at` | DateTime | NULLABLE | Completion timestamp |
| `results_path` | String(500) | NULLABLE | Path to results file |
| `error_message` | Text | NULLABLE | Error details if failed |

**Example**:
```python
task = AnalysisTask(
    task_id='task_20251014_143022',
    application_id=1,
    task_type='security',
    status='completed',
    started_at=datetime(2025, 10, 14, 14, 30, 22),
    completed_at=datetime(2025, 10, 14, 14, 33, 15),
    results_path='results/anthropic_claude-3.5-sonnet/app1/task_20251014_143022.json'
)
```

---

### PortAllocation

Manages unique port assignments for generated applications.

**Table**: `port_allocations`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PRIMARY KEY | Unique identifier |
| `model_name` | String(200) | NOT NULL | Model identifier |
| `app_number` | Integer | NOT NULL | Application number |
| `backend_port` | Integer | UNIQUE, NOT NULL | Backend API port (5001+) |
| `frontend_port` | Integer | UNIQUE, NOT NULL | Frontend dev port (8001+) |
| `allocated_at` | DateTime | DEFAULT now() | Allocation timestamp |

**Constraints**:
- `UNIQUE(model_name, app_number)` - One allocation per app
- `UNIQUE(backend_port)` - No port conflicts
- `UNIQUE(frontend_port)` - No port conflicts

**Example**:
```python
allocation = PortAllocation(
    model_name='anthropic_claude-3.5-sonnet',
    app_number=1,
    backend_port=5001,
    frontend_port=8001
)
```

---

## Relationships

```python
# GeneratedApplication has many AnalysisTasks
application.analysis_tasks  # List[AnalysisTask]

# GeneratedApplication has one PortAllocation
application.port_allocation  # PortAllocation

# ModelCapability generates many GeneratedApplications
model.generated_applications  # List[GeneratedApplication]

# AnalysisTask belongs to one GeneratedApplication
task.application  # GeneratedApplication
```

---

## Queries

### Common Operations

```python
# Get application by model and number
app = GeneratedApplication.query.filter_by(
    model_slug='anthropic_claude-3.5-sonnet',
    app_number=1
).first()

# Get all running applications
running = GeneratedApplication.query.filter_by(
    status='running'
).all()

# Get applications needing status update
stale = GeneratedApplication.query.filter(
    GeneratedApplication.last_status_check < datetime.now() - timedelta(seconds=300)
).all()

# Get analysis tasks for an application
tasks = AnalysisTask.query.filter_by(
    application_id=app.id
).order_by(AnalysisTask.started_at.desc()).all()

# Get port allocation
ports = PortAllocation.query.filter_by(
    model_name='anthropic_claude-3.5-sonnet',
    app_number=1
).first()
```

---

## Migrations

### Creating Migrations

```bash
cd src
flask db init          # Initialize migrations (first time only)
flask db migrate -m "Description of changes"
flask db upgrade
```

### Manual Schema Updates

```sql
-- Add column
ALTER TABLE generated_applications ADD COLUMN new_field VARCHAR(100);

-- Create index
CREATE INDEX idx_model_app ON generated_applications(model_slug, app_number);

-- Drop table
DROP TABLE IF EXISTS old_table;
```

---

## Database Configuration

### Development (SQLite)

```python
# .env
DATABASE_URL=sqlite:///app.db
```

### Production (PostgreSQL)

```python
# .env
DATABASE_URL=postgresql://user:password@localhost:5432/thesisapp
```

---

## Last Updated

October 2025
