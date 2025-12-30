# Routes Package - Blueprint definitions
from flask import Blueprint

user_bp = Blueprint('user', __name__, url_prefix='/api')
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

from routes.user import *
from routes.admin import *
from routes.auth import *
