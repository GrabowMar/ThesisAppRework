# User Routes - Public API endpoints for end users
# All routes use the user_bp blueprint with /api prefix
from flask import jsonify, request
from routes import user_bp
from models import db

# ============================================================================
# USER API ENDPOINTS - Implement public-facing routes here
# ============================================================================
#
# These routes are for regular users of the application.
# All routes are prefixed with /api/ (defined in __init__.py)
#
# Example routes:
#
# @user_bp.route('/items', methods=['GET'])
# def get_items():
#     """Get all active items for users."""
#     items = Item.query.filter_by(is_active=True).all()
#     return jsonify([item.to_dict() for item in items])
#
# @user_bp.route('/items', methods=['POST'])
# def create_item():
#     """Create a new item."""
#     data = request.get_json()
#     if not data or not data.get('name'):
#         return jsonify({'error': 'Name is required'}), 400
#     item = Item(name=data['name'], description=data.get('description'))
#     db.session.add(item)
#     db.session.commit()
#     return jsonify(item.to_dict()), 201
#
# @user_bp.route('/items/<int:item_id>', methods=['GET'])
# def get_item(item_id):
#     """Get a specific item by ID."""
#     item = Item.query.get_or_404(item_id)
#     return jsonify(item.to_dict())
#
# @user_bp.route('/items/<int:item_id>', methods=['PUT'])
# def update_item(item_id):
#     """Update an existing item."""
#     item = Item.query.get_or_404(item_id)
#     data = request.get_json()
#     if data.get('name'):
#         item.name = data['name']
#     if 'description' in data:
#         item.description = data['description']
#     db.session.commit()
#     return jsonify(item.to_dict())
#
# @user_bp.route('/items/<int:item_id>', methods=['DELETE'])
# def delete_item(item_id):
#     """Delete an item."""
#     item = Item.query.get_or_404(item_id)
#     db.session.delete(item)
#     db.session.commit()
#     return jsonify({'message': 'Item deleted'})
#
# IMPLEMENT YOUR USER ROUTES BELOW:
# ============================================================================

