# Admin Routes - Administrative API endpoints with JWT auth protection
# All routes use the admin_bp blueprint with /api/admin prefix
# These routes provide administrative functionality (view all, delete, toggle states, stats)
from flask import jsonify, request
from routes import admin_bp
from routes.auth import admin_required, token_required
from models import db, User

# ============================================================================
# ADMIN AUTH - Uses JWT token from routes/auth.py
# ============================================================================
#
# Admin routes are protected by the @admin_required decorator, which:
# 1. Validates the JWT token in Authorization header
# 2. Checks that the user has is_admin=True
# 3. Passes the current_user to the route function
#
# Usage:
#   @admin_bp.route('/items', methods=['GET'])
#   @admin_required
#   def admin_get_items(current_user):
#       ...


# ============================================================================
# USER MANAGEMENT ENDPOINTS (Built-in admin functionality)
# ============================================================================

@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_all_users(current_user):
    """Get all users (admin only)."""
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([user.to_dict() for user in users])


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(current_user, user_id):
    """Get a specific user by ID."""
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_user_active(current_user, user_id):
    """Toggle user active status."""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deactivating themselves
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot deactivate your own account'}), 400
    
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_user_admin(current_user, user_id):
    """Toggle user admin status."""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from removing their own admin status
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot modify your own admin status'}), 400
    
    user.is_admin = not user.is_admin
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(current_user, user_id):
    """Delete a user account."""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User deleted successfully'})


@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_admin_stats(current_user):
    """Get admin dashboard statistics."""
    return jsonify({
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'admin_users': User.query.filter_by(is_admin=True).count(),
    })


# ============================================================================
# ADMIN API ENDPOINTS - Implement admin-only routes here
# ============================================================================
#
# These routes are for administrative functions.
# All routes are prefixed with /api/admin/ (defined in __init__.py)
# Use @admin_required decorator on routes that need admin protection.
# Use @token_required for routes that just need any authenticated user.
#
# Admin routes typically include:
# - View ALL items (including inactive/deleted)
# - Bulk operations (delete multiple, export)
# - Toggle states (activate/deactivate)
# - Statistics and dashboard data
# - User management (built-in above)
#
# Example routes:
#
# @admin_bp.route('/items', methods=['GET'])
# @admin_required
# def admin_get_all_items(current_user):
#     """Get all items including inactive ones for admin."""
#     items = Item.query.order_by(Item.created_at.desc()).all()
#     return jsonify([item.to_dict() for item in items])
#
# @admin_bp.route('/items/<int:item_id>/toggle', methods=['POST'])
# @admin_required
# def toggle_item_status(current_user, item_id):
#     """Toggle item active status."""
#     item = Item.query.get_or_404(item_id)
#     item.is_active = not item.is_active
#     db.session.commit()
#     return jsonify(item.to_dict())
#
# @admin_bp.route('/items/bulk-delete', methods=['POST'])
# @admin_required
# def bulk_delete_items(current_user):
#     """Delete multiple items at once."""
#     data = request.get_json()
#     ids = data.get('ids', [])
#     Item.query.filter(Item.id.in_(ids)).delete(synchronize_session=False)
#     db.session.commit()
#     return jsonify({'message': f'Deleted {len(ids)} items'})
#
# IMPLEMENT YOUR ADMIN ROUTES BELOW:
# ============================================================================

