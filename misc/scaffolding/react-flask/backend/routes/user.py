# User Routes - Public API (/api prefix)
from flask import jsonify, request
from routes import user_bp
from models import db


# LLM: Implement user-facing API endpoints
# Use @token_required from routes.auth for protected routes
# Example:
# @user_bp.route('/items', methods=['GET'])
# def get_items():
#     items = Item.query.filter_by(is_active=True).all()
#     return jsonify([i.to_dict() for i in items])

