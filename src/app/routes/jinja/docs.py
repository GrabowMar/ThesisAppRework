"""
Documentation routes for the Flask application
===============================================

Routes for displaying markdown documentation files.
"""

import os
import markdown
from flask import Blueprint, flash, current_app, abort, redirect, url_for, request
from flask_login import current_user

from app.utils.template_paths import render_template_compat as render_template
from app.services.docs_service import DocsService

# Create blueprint
docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

# Require authentication
@docs_bp.before_request
def require_authentication():
    """Require authentication for all docs endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access documentation.', 'info')
        return redirect(url_for('auth.login', next=request.url))

@docs_bp.route('/')
def docs_index():
    """Documentation index page."""
    sections = DocsService.build_sections()
    # Back-compat flat list for existing blocks in template
    docs_files = [
        {
            'name': item.title,
            'filename': item.filename,
            'path': f'docs/{item.category.lower().replace(" ", "-")}' if "/" not in item.relpath else f'docs/{os.path.dirname(item.relpath)}',
            'relpath': item.relpath,
            'category': item.category,
        }
        for section in sections for item in section.items
    ]
    return render_template('pages/docs/docs_main.html', sections=sections, docs_files=docs_files)

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


@docs_bp.route('/search')
def docs_search():
    """HTMX endpoint to search docs (returns minimal list HTML)."""
    query = request.args.get('q', type=str, default='')
    results = DocsService.search(query)
    # Render a small partial list to be injected by HTMX
    return render_template(
        'pages/docs/partials/_search_results.html',
        query=query,
        results=results,
    )