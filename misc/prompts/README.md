# Generation Prompts

This directory contains the **system prompts** used by the app’s code-generation pipeline.

## Directory Structure

```
prompts/
├── README.md                          # This file
├── PROMPT_ENGINEERING_RESEARCH.md     # Scientific bibliography & research findings
└── system/                            # System prompts for different generation targets
    ├── backend_user.md                # Flask backend (user routes) - IMPROVED
    ├── backend_admin.md               # Flask backend (admin routes)
    ├── backend_unguarded.md           # Flask backend (no auth)
    ├── frontend_user.md               # React frontend (user page) - IMPROVED
    ├── frontend_admin.md              # React frontend (admin page)
    ├── frontend_unguarded.md          # React frontend (no auth)
    └── fullstack_unguarded.md         # Combined fullstack (no auth)
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

1. **System Prompts** (in `system/`): Define the AI's role and capabilities
   - `backend_user.md`: Flask backend generation guidelines (USER routes)
   - `backend_admin.md`: Flask backend generation guidelines (ADMIN routes)
   - `frontend_user.md`: React frontend generation guidelines (USER page)
   - `frontend_admin.md`: React frontend generation guidelines (ADMIN page)

2. **User Prompts** (built dynamically): Combine:
   - Requirements from `misc/requirements/*.json`
   - Templates from `misc/templates/*/` (Jinja2 templates)
   - Scaffolding context loaded from the selected scaffolding under `misc/scaffolding/`

## Customization

- **System prompts** can be edited to change AI behavior
- **Templates** (Jinja2) define the structure of user prompts
- **Scaffolding context** provides technical reference for the AI

## Generation Philosophy

The prompts are designed to be **reliable and repeatable**:
- Output is code-only (no explanations in the generated response)
- Generated code should be complete (no placeholders)
- Error handling + validation are required
- Core scaffolding/infrastructure should not be overwritten

## References

See [PROMPT_ENGINEERING_RESEARCH.md](PROMPT_ENGINEERING_RESEARCH.md) for the collected sources.
