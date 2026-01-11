# misc/

This folder contains **all inputs** used by the generation pipeline (prompts, templates, requirements, and scaffolding).

## What lives where

- `misc/requirements/`
  - JSON requirement sets (loaded by the app).
  - See `misc/requirements/README.md` for the schema.

- `misc/templates/`
  - Jinja2 templates used to build **user prompts**.
  - `four-query/` is the primary guarded flow; `two-query/` is a fallback; `unguarded/` supports simplified generation.

- `misc/prompts/system/`
  - **System prompts** selected by component + query type + generation mode.
  - Guarded: `{component}_{user|admin}.md`, with `{component}.md` as a fallback.
  - Unguarded: `{component}_unguarded.md`.

- `misc/scaffolding/`
  - The “sacred” base project scaffolding copied into `generated/apps/...` before code generation.

## Runtime usage

The generator loads these paths via `src/app/paths.py`:
- `TEMPLATES_V2_DIR = misc/templates`
- `REQUIREMENTS_DIR = misc/requirements`
- `SCAFFOLDING_DIR = misc/scaffolding`
- System prompts are loaded from `misc/prompts/system`
