"""Legacy Template API shim – all routes now emit 410 Gone responses."""

from __future__ import annotations

from flask import Blueprint

from app.utils.helpers import create_error_response


templates_bp = Blueprint('templates_api', __name__, url_prefix='/api/templates')


@templates_bp.route('/', defaults={'_path': ''}, methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
@templates_bp.route('/<_path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def _deprecated(_path: str):
    """Return a consistent 410 Gone for the removed template API."""
    return create_error_response(
        "The /api/templates endpoints were retired. Use /api/gen equivalents.",
        410,
    )


__all__ = ['templates_bp']
