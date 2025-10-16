"""
Documentation routes for the Flask application
===============================================

Routes for displaying markdown documentation files.
"""

import os
import markdown
from flask import Blueprint, flash, current_app, abort

from app.utils.template_paths import render_template_compat as render_template

# Create blueprint
docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

@docs_bp.route('/')
def docs_index():
    """Documentation index page."""
    docs_path = os.path.join(current_app.root_path, '..', '..', 'docs')
    docs_files = []

    # Get main docs files
    if os.path.exists(docs_path):
        for file in os.listdir(docs_path):
            if file.endswith('.md') and file != 'index.md':
                docs_files.append({
                    'name': file.replace('.md', '').replace('_', ' ').title(),
                    'filename': file,
                    'path': 'docs'
                })

    # Get frontend docs files
    frontend_path = os.path.join(docs_path, 'frontend')
    if os.path.exists(frontend_path):
        for file in os.listdir(frontend_path):
            if file.endswith('.md'):
                docs_files.append({
                    'name': file.replace('.md', '').replace('_', ' ').title(),
                    'filename': file,
                    'path': 'docs/frontend'
                })

    return render_template('pages/docs/docs_index.html', docs_files=docs_files)

@docs_bp.route('/<path:filepath>')
def docs_file(filepath):
    """Display a specific markdown documentation file."""
    try:
        # Build the full path to the docs directory
        docs_base = os.path.join(current_app.root_path, '..', '..', 'docs')
        full_path = os.path.join(docs_base, filepath)

        # Security check - ensure the file is within the docs directory
        if not os.path.abspath(full_path).startswith(os.path.abspath(docs_base)):
            abort(403)

        # Check if file exists
        if not os.path.exists(full_path) or not full_path.endswith('.md'):
            abort(404)

        # Read and convert markdown to HTML
        with open(full_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # Convert markdown to HTML with extensions
        html_content = markdown.markdown(
            md_content,
            extensions=[
                'fenced_code',      # ``` code blocks
                'codehilite',      # Syntax highlighting
                'tables',          # Table support
                'toc',             # Table of contents
                'nl2br',           # Line breaks
                'sane_lists'       # Better list handling
            ]
        )

        # Get file info for the template
        filename = os.path.basename(filepath)
        title = filename.replace('.md', '').replace('_', ' ').title()

        return render_template(
            'pages/docs/docs_file.html',
            title=title,
            content=html_content,
            filepath=filepath,
            filename=filename
        )

    except Exception as e:
        current_app.logger.error(f"Error loading docs file {filepath}: {e}")
        flash(f'Error loading documentation: {str(e)}', 'error')
        return render_template(
            'pages/errors/errors_main.html',
            error_code=500,
            error_message=str(e),
            error_title='Documentation Error'
        ), 500