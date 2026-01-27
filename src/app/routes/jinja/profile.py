"""Profile routes - User profile and settings management."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import User

profile_bp = Blueprint(
    'profile',
    __name__,
    url_prefix='/profile'
)


@profile_bp.route('/')
@login_required
def index():
    """Display user profile page (redirects to settings)."""
    return redirect(url_for('profile.settings'))


@profile_bp.route('/settings')
@login_required
def settings():
    """Display unified settings page."""
    return render_template('pages/settings/settings_unified.html')


@profile_bp.route('/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile information."""
    try:
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        
        if not email:
            flash('Email is required', 'danger')
            return redirect(url_for('profile.settings') + '#tabs-profile')
        
        # Check if email is already taken by another user
        existing_user = User.query.filter(
            User.email == email,  # type: ignore[arg-type]
            User.id != current_user.id
        ).first()
        
        if existing_user:
            flash('Email address already in use', 'danger')
            return redirect(url_for('profile.settings') + '#tabs-profile')
        
        # Update user information
        current_user.email = email
        current_user.full_name = full_name
        db.session.commit()
        
        flash('Profile updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating profile: {str(e)}', 'danger')
    
    return redirect(url_for('profile.settings') + '#tabs-profile')


@profile_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password."""
    try:
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate inputs
        if not all([current_password, new_password, confirm_password]):
            flash('All password fields are required', 'danger')
            return redirect(url_for('profile.settings') + '#tabs-profile')
        
        # Check current password
        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('profile.settings') + '#tabs-profile')
        
        # Check new passwords match
        if new_password != confirm_password:
            flash('New passwords do not match', 'danger')
            return redirect(url_for('profile.settings') + '#tabs-profile')
        
        # Validate new password length
        if len(new_password) < 8:
            flash('New password must be at least 8 characters long', 'danger')
            return redirect(url_for('profile.settings') + '#tabs-profile')
        
        # Check new password is different from current
        if current_password == new_password:
            flash('New password must be different from current password', 'warning')
            return redirect(url_for('profile.settings') + '#tabs-profile')
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Password changed successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error changing password: {str(e)}', 'danger')
    
    return redirect(url_for('profile.settings') + '#tabs-profile')


@profile_bp.route('/update-settings', methods=['POST'])
@login_required
def update_settings():
    """Update user settings/preferences."""
    # Placeholder for future settings implementation
    flash('Settings functionality coming soon', 'info')
    return redirect(url_for('profile.settings'))
