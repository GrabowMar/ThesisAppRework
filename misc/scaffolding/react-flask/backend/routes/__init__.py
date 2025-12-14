# Routes Package - Imports all route blueprints
from flask import Blueprint

# User-facing routes (public functionality)
user_bp = Blueprint('user', __name__, url_prefix='/api')

# Admin routes (administrative functionality)
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Import route handlers to register them
from routes.user import *
from routes.admin import *
