# Simple Generation System

## Overview

The Simple Generation System is a lightweight alternative to the full AI generation pipeline. It allows for quick scaffolding of applications using predefined templates and minimal AI intervention.

## Usage

1.  **Select Template**: Choose from available templates (e.g., "React + Flask", "Simple HTML").
2.  **Configure**: Set basic parameters (App Name, Description).
3.  **Generate**: The system copies the template and customizes it.

## Templates

Templates are stored in `misc/scaffolding/`.
- **react-flask**: A modern stack with React frontend and Flask backend.
- **html-js**: A simple static site structure.

## Extending

To add a new template:
1.  Create a folder in `misc/scaffolding/`.
2.  Add a `manifest.json` describing the template.
3.  Add template files with Jinja2 placeholders (e.g., `{{ app_name }}`).
