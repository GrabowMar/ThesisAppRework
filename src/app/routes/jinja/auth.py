"""
Authentication Routes
====================

Handles user login, logout, and registration.
"""

from flask import Blueprint, request, flash, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.extensions import db
from app.utils.template_paths import render_template_compat as render_template

# Create blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page and handler."""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember', False))
        
        if not username or not password:
            flash('Please provide both username and password.', 'error')
            return render_template('pages/auth/login.html', page_title='Login')
        
        # Find user
        user = User.query.filter_by(username=username).first()
        
        # Verify credentials
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been disabled.', 'error')
                return render_template('pages/auth/login.html', page_title='Login')
            
            # Log the user in
            login_user(user, remember=remember)
            user.update_last_login()
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('pages/auth/login.html', page_title='Login')


@auth_bp.route('/logout')
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page and handler."""
    # Check if registration is enabled
    if not current_app.config.get('REGISTRATION_ENABLED', False):
        flash('Registration is currently disabled. Please contact an administrator.', 'error')
        return redirect(url_for('auth.login'))
    
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        full_name = request.form.get('full_name')
        
        # Validation
        if not all([username, email, password, password_confirm]):
            flash('All fields are required.', 'error')
            return render_template('pages/auth/register.html', page_title='Register')
        
        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return render_template('pages/auth/register.html', page_title='Register')
        
        # Type narrowing: validation above ensures these are not None
        assert username is not None and email is not None and password is not None
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('pages/auth/register.html', page_title='Register')
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return render_template('pages/auth/register.html', page_title='Register')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('pages/auth/register.html', page_title='Register')
        
        try:
            # Create new user
            user = User(
                username=username,
                email=email,
                full_name=full_name
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration error: {e}")
            flash('An error occurred during registration. Please try again.', 'error')
    
    return render_template('pages/auth/register.html', page_title='Register')
