# Database Models - Define all SQLAlchemy models here
# This file is imported by app.py and shared across user/admin routes
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ============================================================================
# MODELS - Implement your database models here
# ============================================================================
# 
# Example model structure:
#
# class Item(db.Model):
#     __tablename__ = 'items'
#     
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(255), nullable=False)
#     description = db.Column(db.Text, nullable=True)
#     is_active = db.Column(db.Boolean, default=True)
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
#     updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
#     
#     def to_dict(self):
#         return {
#             'id': self.id,
#             'name': self.name,
#             'description': self.description,
#             'is_active': self.is_active,
#             'created_at': self.created_at.isoformat() if self.created_at else None,
#             'updated_at': self.updated_at.isoformat() if self.updated_at else None
#         }
#
# IMPLEMENT YOUR MODELS BELOW:
# ============================================================================

