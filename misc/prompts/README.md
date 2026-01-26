# Generation Prompts

This directory contains the **templates and prompts** used by the app’s code-generation pipeline.

## Directory Structure

```
prompts/
├── README.md                          # This file
├── PROMPT_ENGINEERING_RESEARCH.md     # Scientific bibliography & research findings
└── v2/                                # Standardized Jinja2 templates for PromptLoader
    ├── backend/
    │   ├── system.md.jinja2
    │   └── user.md.jinja2
    └── frontend/
        ├── system.md.jinja2
        └── user.md.jinja2
```

## Prompt Design Notes

The prompts are informed by the references collected in
[PROMPT_ENGINEERING_RESEARCH.md](PROMPT_ENGINEERING_RESEARCH.md). In practice, this repo’s prompts focus on:

- Clear requirements + constraints
- Explicit output format (file blocks)
- Common mistakes / anti-patterns
- Lightweight self-checks (success criteria)
- “Internal planning is allowed, but output must be code-only”

## How Prompts Work

1. **PromptLoader** (`src/app/services/generation_v2/prompt_loader.py`):
   - Loads templates from `prompts/v2/`.
   - Injects context (scaffolding, requirements, API specs).

2. **Templates** (in `v2/`):
   - `backend/system.md.jinja2`: Defines backend role and constraints.
   - `backend/user.md.jinja2`: Combines requirements + scaffolding example.
   - `frontend/system.md.jinja2`: Defines frontend role and constraints.
   - `frontend/user.md.jinja2`: Combines UI requirements + generated Backend API context.

## References

See [PROMPT_ENGINEERING_RESEARCH.md](PROMPT_ENGINEERING_RESEARCH.md) for the collected sources.
