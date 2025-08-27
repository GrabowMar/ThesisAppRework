"""Report history & downloads routes."""
from pathlib import Path
from datetime import datetime
from flask import Blueprint, send_file, abort, request
from .batch import render_template  # reuse compatibility wrapper
from ..constants import Paths

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


def _gather_reports(limit: int | None = None):
    reports_dir = Paths.REPORTS_DIR
    if not reports_dir.exists():
        return []
    files = []
    for p in sorted(reports_dir.glob('*'), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file():
            continue
        stat = p.stat()
        files.append({
            'name': p.name,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'ext': p.suffix.lower().lstrip('.'),
        })
        if limit and len(files) >= limit:
            break
    return files

@reports_bp.route('/')
def reports_index():
    files = _gather_reports()
    hx = request.headers.get('HX-Request')
    template = 'pages/reports/index.html'
    return render_template(template, files=files)

@reports_bp.route('/download/<path:fname>')
def download_report(fname: str):
    target = Paths.REPORTS_DIR / fname
    if not target.exists() or not target.is_file():
        abort(404)
    # Basic path traversal guard
    if target.resolve().parent != Paths.REPORTS_DIR.resolve():
        abort(400)
    return send_file(target, as_attachment=True, download_name=target.name)
