"""
Authentication Routes for AI Testing Framework
==========================================

Flask routes for user authentication, registration, and session management.
"""

from datetime import datetime, timedelta
from typing import Optional

from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.urls import url_parse

try:
    from .auth import User, SessionToken, create_default_admin
    from .extensions import db, get_session
    from .forms import LoginForm, RegistrationForm, ProfileForm, ChangePasswordForm
except ImportError:
    from auth import User, SessionToken, create_default_admin
    from extensions import db, get_session
    from forms import LoginForm, RegistrationForm, ProfileForm, ChangePasswordForm

# Create authentication blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        remember_me = form.remember_me.data
        
        with get_session() as db_session:
            # Find user by username or email
            user = db_session.query(User).filter(
                (User.username == username) | (User.email == username)
            ).first()
            
            if user is None:
                flash('Invalid username or password', 'error')
                return render_template('auth/login.html', form=form)
            
            # Check if account is locked
            if user.is_locked():
                flash('Account is temporarily locked due to failed login attempts. Try again later.', 'error')
                return render_template('auth/login.html', form=form)
            
            # Check password
            if not user.check_password(password):
                user.record_failed_login()
                db_session.commit()
                flash('Invalid username or password', 'error')
                return render_template('auth/login.html', form=form)
            
            # Check if account is active
            if not user.is_active:
                flash('Account is deactivated. Contact administrator.', 'error')
                return render_template('auth/login.html', form=form)
            
            # Successful login
            user.record_login()
            db_session.commit()
            
            login_user(user, remember=remember_me)
            flash(f'Welcome back, {user.get_display_name()}!', 'success')
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('main.index')
            
            return redirect(next_page)
    
    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout."""
    username = current_user.username if current_user.is_authenticated else 'Unknown'
    logout_user()
    flash(f'You have been logged out, {username}', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    # Check if registration is enabled
    from flask import current_app
    if not current_app.config.get('REGISTRATION_ENABLED', True):
        flash('Registration is currently disabled. Contact administrator.', 'error')
        return redirect(url_for('auth.login'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        try:
            with get_session() as db_session:
                # Check if username already exists
                existing_user = db_session.query(User).filter_by(username=form.username.data).first()
                if existing_user:
                    flash('Username already exists', 'error')
                    return render_template('auth/register.html', form=form)
                
                # Check if email already exists
                existing_email = db_session.query(User).filter_by(email=form.email.data).first()
                if existing_email:
                    flash('Email already registered', 'error')
                    return render_template('auth/register.html', form=form)
                
                # Create new user
                user = User(
                    username=form.username.data,
                    email=form.email.data,
                    password=form.password.data,
                    first_name=form.first_name.data,
                    last_name=form.last_name.data,
                    role='user'  # Default role
                )
                
                db_session.add(user)
                db_session.commit()
                
                flash('Registration successful! You can now log in.', 'success')
                return redirect(url_for('auth.login'))
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration failed: {e}")
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('auth/register.html', form=form)


@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page."""
    return render_template('auth/profile.html', user=current_user)


@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile."""
    form = ProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        try:
            with get_session() as db_session:
                user = db_session.query(User).get(current_user.id)
                
                # Check if new email is already taken by another user
                if form.email.data != user.email:
                    existing_email = db_session.query(User).filter(
                        User.email == form.email.data,
                        User.id != user.id
                    ).first()
                    if existing_email:
                        flash('Email already registered by another user', 'error')
                        return render_template('auth/edit_profile.html', form=form)
                
                # Update user data
                user.email = form.email.data
                user.first_name = form.first_name.data
                user.last_name = form.last_name.data
                
                db_session.commit()
                flash('Profile updated successfully', 'success')
                return redirect(url_for('auth.profile'))
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Profile update failed: {e}")
            flash('Failed to update profile. Please try again.', 'error')
    
    return render_template('auth/edit_profile.html', form=form)


@auth_bp.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password."""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        try:
            with get_session() as db_session:
                user = db_session.query(User).get(current_user.id)
                
                # Check current password
                if not user.check_password(form.current_password.data):
                    flash('Current password is incorrect', 'error')
                    return render_template('auth/change_password.html', form=form)
                
                # Update password
                user.set_password(form.new_password.data)
                db_session.commit()
                
                flash('Password changed successfully', 'success')
                return redirect(url_for('auth.profile'))
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Password change failed: {e}")
            flash('Failed to change password. Please try again.', 'error')
    
    return render_template('auth/change_password.html', form=form)


@auth_bp.route('/profile/api-keys')
@login_required
def api_keys():
    """Manage API keys and tokens."""
    with get_session() as db_session:
        user = db_session.query(User).get(current_user.id)
        tokens = db_session.query(SessionToken).filter_by(user_id=current_user.id).order_by(
            SessionToken.created_at.desc()
        ).all()
    
    return render_template('auth/api_keys.html', user=user, tokens=tokens)


@auth_bp.route('/profile/api-keys/create', methods=['POST'])
@login_required
def create_api_token():
    """Create a new API token."""
    try:
        data = request.get_json() or {}
        name = data.get('name', f"Token {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        expires_days = int(data.get('expires_days', 30))
        
        # Permissions
        can_read = data.get('can_read', True)
        can_write = data.get('can_write', False)
        can_admin = data.get('can_admin', False) and current_user.is_admin()
        
        with get_session() as db_session:
            token = SessionToken(
                user_id=current_user.id,
                name=name,
                expires_days=expires_days,
                can_read=can_read,
                can_write=can_write,
                can_admin=can_admin
            )
            
            db_session.add(token)
            db_session.commit()
            
            return jsonify({
                'success': True,
                'token': token.to_dict(include_token=True),
                'message': 'API token created successfully'
            })
            
    except Exception as e:
        current_app.logger.error(f"API token creation failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/profile/api-keys/<int:token_id>/revoke', methods=['POST'])
@login_required
def revoke_api_token(token_id: int):
    """Revoke an API token."""
    try:
        with get_session() as db_session:
            token = db_session.query(SessionToken).filter_by(
                id=token_id,
                user_id=current_user.id
            ).first()
            
            if not token:
                return jsonify({
                    'success': False,
                    'error': 'Token not found'
                }), 404
            
            token.revoke()
            db_session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Token revoked successfully'
            })
            
    except Exception as e:
        current_app.logger.error(f"API token revocation failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/profile/regenerate-api-key', methods=['POST'])
@login_required
def regenerate_api_key():
    """Regenerate user's primary API key."""
    try:
        with get_session() as db_session:
            user = db_session.query(User).get(current_user.id)
            old_key = user.api_key
            new_key = user.generate_api_key()
            
            db_session.commit()
            
            current_app.logger.info(f"User {user.username} regenerated API key")
            
            return jsonify({
                'success': True,
                'api_key': new_key,
                'message': 'API key regenerated successfully'
            })
            
    except Exception as e:
        current_app.logger.error(f"API key regeneration failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Admin routes
@auth_bp.route('/admin/users')
@login_required
def admin_users():
    """Admin: Manage users."""
    if not current_user.is_admin():
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    with get_session() as db_session:
        users = db_session.query(User).order_by(User.created_at.desc()).all()
    
    return render_template('auth/admin/users.html', users=users)


@auth_bp.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
def admin_toggle_user_status(user_id: int):
    """Admin: Toggle user active status."""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    try:
        with get_session() as db_session:
            user = db_session.query(User).get(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            # Don't allow deactivating yourself
            if user.id == current_user.id:
                return jsonify({'success': False, 'error': 'Cannot deactivate your own account'}), 400
            
            user.is_active = not user.is_active
            db_session.commit()
            
            action = 'activated' if user.is_active else 'deactivated'
            return jsonify({
                'success': True,
                'message': f'User {user.username} {action}',
                'is_active': user.is_active
            })
            
    except Exception as e:
        current_app.logger.error(f"User status toggle failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/admin/users/<int:user_id>/change-role', methods=['POST'])
@login_required
def admin_change_user_role(user_id: int):
    """Admin: Change user role."""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    try:
        data = request.get_json()
        new_role = data.get('role')
        
        if new_role not in ['user', 'researcher', 'admin']:
            return jsonify({'success': False, 'error': 'Invalid role'}), 400
        
        with get_session() as db_session:
            user = db_session.query(User).get(user_id)
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            # Don't allow changing your own role
            if user.id == current_user.id:
                return jsonify({'success': False, 'error': 'Cannot change your own role'}), 400
            
            old_role = user.role
            user.role = new_role
            db_session.commit()
            
            return jsonify({
                'success': True,
                'message': f'User {user.username} role changed from {old_role} to {new_role}',
                'role': new_role
            })
            
    except Exception as e:
        current_app.logger.error(f"User role change failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# API authentication endpoints
@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    """API login endpoint."""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Username and password required'
            }), 400
        
        with get_session() as db_session:
            user = db_session.query(User).filter(
                (User.username == username) | (User.email == username)
            ).first()
            
            if not user or not user.check_password(password):
                return jsonify({
                    'success': False,
                    'error': 'Invalid credentials'
                }), 401
            
            if user.is_locked():
                return jsonify({
                    'success': False,
                    'error': 'Account locked'
                }), 423
            
            if not user.is_active:
                return jsonify({
                    'success': False,
                    'error': 'Account deactivated'
                }), 403
            
            # Create session token
            token = SessionToken(
                user_id=user.id,
                name="API Login",
                expires_days=7,  # 7 days for API sessions
                can_read=True,
                can_write=user.can_create_batch_jobs(),
                can_admin=user.is_admin()
            )
            
            db_session.add(token)
            user.record_login()
            db_session.commit()
            
            return jsonify({
                'success': True,
                'token': token.token,
                'user': user.to_dict(),
                'expires_at': token.expires_at.isoformat()
            })
            
    except Exception as e:
        current_app.logger.error(f"API login failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Login failed'
        }), 500


@auth_bp.route('/api/logout', methods=['POST'])
def api_logout():
    """API logout endpoint."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': 'Invalid authorization header'
            }), 400
        
        token = auth_header.split(' ', 1)[1]
        
        with get_session() as db_session:
            session_token = db_session.query(SessionToken).filter_by(token=token).first()
            if session_token:
                session_token.revoke()
                db_session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"API logout failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Logout failed'
        }), 500


@auth_bp.route('/api/me')
def api_user_info():
    """Get current user info via API."""
    try:
        from .decorators import api_login_required
        
        @api_login_required
        def _get_user_info():
            user = getattr(request, 'current_user', None)
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'User not found'
                }), 404
            
            return jsonify({
                'success': True,
                'user': user.to_dict(include_sensitive=True)
            })
        
        return _get_user_info()
        
    except Exception as e:
        current_app.logger.error(f"API user info failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get user info'
        }), 500


# Initialize authentication
def init_auth_system(app):
    """Initialize authentication system."""
    try:
        with app.app_context():
            # Create default admin if none exists
            create_default_admin()
            
            app.logger.info("Authentication system initialized")
            
    except Exception as e:
        app.logger.error(f"Failed to initialize authentication system: {e}")


# Template context processor
@auth_bp.app_context_processor
def inject_auth_context():
    """Inject authentication context into templates."""
    return {
        'current_user': current_user
    }
