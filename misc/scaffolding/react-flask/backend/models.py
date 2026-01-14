# Database Models
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# LLM: Implement User model with fields:
#   id, username, email, password_hash, is_admin, is_active, created_at
# Methods: set_password(pw), check_password(pw), to_dict()
# Use bcrypt for password hashing


# LLM: Add application-specific models below
# Each model needs: id (primary key), created_at, to_dict() method

