"""
API Token Management
====================

Endpoints for generating and managing API tokens for programmatic access.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models import User

# Create blueprint
tokens_bp = Blueprint('tokens', __name__, url_prefix='/api/tokens')


@tokens_bp.route('/generate', methods=['POST'])
@login_required
def generate_token():
    """
    Generate a new API token for the current user.
    
    Returns:
        JSON with the new token
    """
    try:
        token = current_user.generate_api_token()
        return jsonify({
            'success': True,
            'token': token,
            'message': 'API token generated successfully. Save this token - it will not be shown again.',
            'usage': 'Use in header: Authorization: Bearer ' + token
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tokens_bp.route('/revoke', methods=['POST'])
@login_required
def revoke_token():
    """
    Revoke the current user's API token.
    
    Returns:
        JSON confirmation
    """
    try:
        current_user.revoke_api_token()
        return jsonify({
            'success': True,
            'message': 'API token revoked successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@tokens_bp.route('/status', methods=['GET'])
@login_required
def token_status():
    """
    Check if the current user has an active API token.
    
    Returns:
        JSON with token status
    """
    has_token = current_user.api_token is not None
    return jsonify({
        'has_token': has_token,
        'created_at': current_user.api_token_created_at.isoformat() if has_token and current_user.api_token_created_at else None
    }), 200


@tokens_bp.route('/verify', methods=['GET'])
def verify_token():
    """
    Verify if a token is valid (requires token in Authorization header).
    
    Returns:
        JSON with verification result
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({
            'valid': False,
            'error': 'No token provided'
        }), 400
    
    token = auth_header.replace('Bearer ', '', 1)
    user = User.verify_api_token(token)
    
    if user:
        return jsonify({
            'valid': True,
            'user': {
                'username': user.username,
                'email': user.email,
                'is_admin': user.is_admin
            }
        }), 200
    else:
        return jsonify({
            'valid': False,
            'error': 'Invalid or expired token'
        }), 401
