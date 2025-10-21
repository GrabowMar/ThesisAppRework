# Documentation

Welcome to the ThesisAppRework documentation.

## 📚 Knowledge Base

All documentation has been reorganized into the **[knowledge_base](knowledge_base/)** directory with topic-based organization:

### Quick Access

- **[INDEX](knowledge_base/INDEX.md)** - Main documentation index
- **[Quick Start](knowledge_base/QUICKSTART.md)** - Get started in 5 minutes
- **[Architecture](knowledge_base/architecture.md)** - System design overview
- **[Operations](knowledge_base/OPERATIONS.md)** - Day-to-day operations

### Topics

| Topic | Description |
|-------|-------------|
| [Authentication](knowledge_base/authentication/) | User auth, API tokens, security |
| [Containerization](knowledge_base/containerization/) | Docker setup and management |
| [Dashboard](knowledge_base/dashboard/) | UI and real-time features |
| [Deployment](knowledge_base/deployment/) | Production deployment guide |
| [Development](knowledge_base/development/) | Developer guide and patterns |
| [Generation](knowledge_base/generation/) | App generation system |
| [OpenRouter](knowledge_base/openrouter/) | AI model integration |
| [Testing](knowledge_base/testing/) | Test suite and analysis tools |

## 🚀 Quick Commands

```bash
# Start platform
docker compose up -d

# Generate app
curl -X POST http://localhost:5000/api/gen/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "openai_gpt-4", "template_id": 1}'

# Run analysis
python analyzer/analyzer_manager.py analyze openai_gpt-4 1 security

# Run tests
pytest -m "not integration and not analyzer"
```

## 📁 Structure

```
docs/
├── knowledge_base/       # Main documentation (organized by topic)
│   ├── INDEX.md         # Documentation index
│   ├── authentication/  # Auth docs
│   ├── containerization/
│   ├── dashboard/
│   ├── deployment/
│   ├── development/
│   ├── generation/
│   ├── openrouter/
│   └── testing/
├── archive/             # Old documentation (reference only)
├── features/            # Feature-specific docs
├── fixes/               # Bug fix documentation
├── frontend/            # Frontend-specific docs
├── guides/              # How-to guides
└── reference/           # Reference materials
```

## 🔍 Finding Information

1. **Start with [INDEX](knowledge_base/INDEX.md)** for navigation
2. **Topic-specific docs** in knowledge_base subdirectories
3. **Quick reference** in individual README files
4. **Historical context** in archive/ if needed

## 📝 Legacy Docs

Old documentation has been moved to `archive/` for reference. The knowledge_base contains current, consolidated documentation.
