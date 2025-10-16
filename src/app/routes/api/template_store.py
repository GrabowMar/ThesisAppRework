from __future__ import annotations
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest, NotFound
from app.services.template_store_service import get_template_store_service, TemplateStoreService, Profile

bp = Blueprint('template_store_api', __name__, url_prefix='/api/template-store')

ts: TemplateStoreService = get_template_store_service()

# ---------------- Templates ----------------
@bp.get('/')
def list_all():
    category = request.args.get('category')
    metas = ts.list(category=category)
    return jsonify({'items': [m.__dict__ for m in metas]})

@bp.get('/<category>/<path:rel_path>')
def read_template(category: str, rel_path: str):
    try:
        data = ts.read(category, rel_path)
        return jsonify(data)
    except FileNotFoundError:
        raise NotFound(f"Template not found: {rel_path}")

@bp.post('/<category>/<path:rel_path>')
def save_template(category: str, rel_path: str):
    body = request.get_json(force=True, silent=True) or {}
    content = body.get('content')
    if content is None:
        raise BadRequest('Missing content')
    data = ts.save(category, rel_path, content)
    return jsonify(data)

@bp.delete('/<category>/<path:rel_path>')
def delete_template(category: str, rel_path: str):
    ok = ts.delete(category, rel_path)
    if not ok:
        raise NotFound(f"Template not found: {rel_path}")
    return jsonify({'deleted': True})

# ---------------- Profiles ----------------
@bp.get('/profiles')
def list_profiles():
    profs = ts.list_profiles()
    return jsonify({'profiles': [p.__dict__ for p in profs]})

@bp.post('/profiles')
def save_profile():
    body = request.get_json(force=True, silent=True) or {}
    name = body.get('name')
    if not name:
        raise BadRequest('Profile name required')
    description = body.get('description')
    templates = body.get('templates') or []
    if not isinstance(templates, list):
        raise BadRequest('templates must be list of relative paths')
    config = body.get('config') or {}
    profile = Profile(name=name, description=description, templates=templates, config=config)
    ts.save_profile(profile)
    return jsonify({'saved': True, 'profile': profile.__dict__})

@bp.delete('/profiles/<name>')
def delete_profile(name: str):
    ok = ts.delete_profile(name)
    if not ok:
        raise NotFound(f"Profile not found: {name}")
    return jsonify({'deleted': True})
