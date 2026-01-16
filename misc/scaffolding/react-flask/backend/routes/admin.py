# Admin Routes - Protected API (/api/admin prefix)
from flask import jsonify, request
from routes import admin_bp
from routes.auth import admin_required
from models import db


# LLM: Implement admin-only API endpoints
# ALL routes must use @admin_required decorator from routes.auth
# NOTE: admin_bp already uses url_prefix='/api/admin' so routes should NOT start with /api
# Example:
# @admin_bp.route('/stats', methods=['GET'])
# @admin_required
# def get_stats(current_user):
#     return jsonify({'total': Item.query.count()})

