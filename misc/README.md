# misc/

This folder contains **all inputs** used by the generation pipeline (prompts, requirements, and scaffolding).

## What lives where

- `misc/requirements/`
  - JSON requirement sets (30 templates loaded by the app).
  - See `misc/requirements/README.md` for the schema.

- `misc/prompts/v2/`
  - Jinja2 **system and user prompts** for code generation.
  - `backend/`: system.md.jinja2, user.md.jinja2
  - `frontend/`: system.md.jinja2, user.md.jinja2

- `misc/scaffolding/`
  - The "sacred" base project scaffolding copied into `generated/apps/...` before code generation.
  - Single `app.py` (backend) and `App.jsx` (frontend) placeholders replaced by AI.

## Runtime usage

The generator loads these paths via `src/app/paths.py`:
- `PROMPTS_V2_DIR = misc/prompts/v2`
- `REQUIREMENTS_DIR = misc/requirements`
- `SCAFFOLDING_DIR = misc/scaffolding`
