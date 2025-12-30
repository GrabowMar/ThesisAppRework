# Admin Routes - Protected API endpoints (/api/admin prefix)
from flask import jsonify, request
from routes import admin_bp
from routes.auth import admin_required, token_required
from models import db, User


@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_all_users(current_user):
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([user.to_dict() for user in users])


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_user_active(current_user, user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot modify your own account'}), 400
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_admin_stats(current_user):
    return jsonify({
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'admin_users': User.query.filter_by(is_admin=True).count(),
    })


# Add admin routes below:

