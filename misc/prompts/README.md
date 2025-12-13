# Generation Prompts

This directory contains the system prompts and templates used for AI code generation.

## Directory Structure

```
prompts/
├── README.md           # This file
└── system/             # System prompts for different generation targets
    ├── backend.md      # System prompt for Flask backend generation
    └── frontend.md     # System prompt for React frontend generation
```

## How Prompts Work

1. **System Prompts** (in `system/`): Define the AI's role and capabilities
   - `backend.md`: Flask backend generation guidelines
   - `frontend.md`: React frontend generation guidelines

2. **User Prompts** (built dynamically): Combine:
   - Requirements from `misc/requirements/*.json`
   - Templates from `misc/templates/two-query/*.jinja2`
   - Scaffolding context from `misc/scaffolding/*/SCAFFOLDING_CONTEXT.md`

## Customization

- **System prompts** can be edited to change AI behavior
- **Templates** (Jinja2) define the structure of user prompts
- **Scaffolding context** provides technical reference for the AI

## Generation Philosophy

The prompts are designed to be **permissive but reliable**:
- Models CAN generate additional files (components, utilities, CSS)
- Models CAN specify additional dependencies
- Models SHOULD NOT overwrite core infrastructure (Dockerfile, docker-compose.yml)
- Generated code should be complete and working
