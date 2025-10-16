"""App Scaffolding API
=====================

REST endpoints exposing a subset of the legacy `generateApps.py` script so the
web interface can preview & generate multi-model application scaffolds.

All endpoints are prefixed with /api/app-scaffold
"""
from __future__ import annotations

from flask import Blueprint, request, jsonify
from app.services.app_scaffolding_service import get_app_scaffolding_service

scaffold_bp = Blueprint("app_scaffold_api", __name__, url_prefix="/api/app-scaffold")

svc = get_app_scaffolding_service  # local alias to accessor

@scaffold_bp.route('/status', methods=['GET'])
def status():
    return jsonify({"success": True, "data": svc().status()})

@scaffold_bp.route('/templates/validate', methods=['GET'])
def validate_templates():
    return jsonify({"success": True, "data": svc().validate_templates()})

@scaffold_bp.route('/models/parse', methods=['POST'])
def parse_models():
    data = request.get_json(silent=True) or {}
    input_string = data.get('input') or ''
    apps_per_model = data.get('apps_per_model') or None
    try:
        models, colors = svc().parse_models(input_string)
        preview = svc().preview_generation(models, apps_per_model=apps_per_model)
        return jsonify({
            "success": True,
            "data": {
                "models": models,
                "colors": colors,
                "preview": {
                    "total_apps": preview.total_apps,
                    "models": [
                        {
                            "name": p.name,
                            "index": p.index,
                            "port_range": p.port_range,
                            "apps": [
                                {"number": a_num, "backend": a_ports.backend, "frontend": a_ports.frontend}
                                for a_num, a_ports in sorted(p.apps.items())
                            ],
                        } for p in preview.models
                    ],
                    "config_summary": preview.config_summary,
                }
            }
        })
    except Exception as e:  # noqa: BLE001
        return jsonify({"success": False, "error": str(e)}), 400

@scaffold_bp.route('/preview', methods=['POST'])
def preview_generation():
    data = request.get_json(silent=True) or {}
    models = data.get('models') or []
    apps_per_model = data.get('apps_per_model') or None
    if not models:
        return jsonify({"success": False, "error": "'models' list required"}), 400
    preview = svc().preview_generation(models, apps_per_model=apps_per_model)
    return jsonify({
        "success": True,
        "data": {
            "total_apps": preview.total_apps,
            "models": [
                {
                    "name": p.name,
                    "index": p.index,
                    "port_range": p.port_range,
                    "apps": [
                        {"number": a_num, "backend": a_ports.backend, "frontend": a_ports.frontend}
                        for a_num, a_ports in sorted(p.apps.items())
                    ],
                } for p in preview.models
            ],
            "config_summary": preview.config_summary,
        }
    })

@scaffold_bp.route('/ports', methods=['GET'])
def get_ports():
    try:
        model_name = request.args.get('model_name', '')
        model_index = int(request.args.get('model_index', 0))
        app_number = int(request.args.get('app_number', 1))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid numeric parameters"}), 400
    p = svc().get_app_ports(model_name, model_index, app_number)
    return jsonify({"success": True, "data": {"backend": p.backend, "frontend": p.frontend}})

@scaffold_bp.route('/generate', methods=['POST'])
def generate():
    data = request.get_json(silent=True) or {}
    models = data.get('models') or []
    dry_run = bool(data.get('dry_run', False))
    apps_per_model = data.get('apps_per_model') or None
    compose = bool(data.get('compose', True))
    if not models:
        return jsonify({"success": False, "error": "'models' list required"}), 400
    try:
        result = svc().generate(models, dry_run=dry_run, apps_per_model=apps_per_model, compose=compose)
        return jsonify({
            "success": True,
            "data": {
                "generated": result.generated,
                "total_apps": result.preview.total_apps,
                "apps_created": result.apps_created,
                "missing_templates": result.missing_templates,
                "errors": result.errors,
                "models": [
                    {
                        "name": p.name,
                        "index": p.index,
                        "port_range": p.port_range,
                        "apps": [
                            {"number": a_num, "backend": a_ports.backend, "frontend": a_ports.frontend}
                            for a_num, a_ports in sorted(p.apps.items())
                        ],
                    } for p in result.preview.models
                ],
                "output_paths": [str(p) for p in result.output_paths],
            }
        })
    except Exception as e:  # noqa: BLE001
        return jsonify({"success": False, "error": str(e)}), 500
