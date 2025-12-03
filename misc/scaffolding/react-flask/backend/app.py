# Flask Backend Scaffold - Minimal Blueprint
# Model implements all application logic based on requirements
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

db = SQLAlchemy()

# ============================================================================
# MODELS - Define your database models here
# ============================================================================
# Example:
# class Item(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(255), nullable=False)
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
#     
#     def to_dict(self):
#         return {'id': self.id, 'name': self.name, 'created_at': self.created_at.isoformat()}


# ============================================================================
# ROUTES - Define your API endpoints here
# ============================================================================
# All routes should start with /api/
# Example:
# @app.route('/api/items', methods=['GET'])
# def get_items():
#     items = Item.query.all()
#     return jsonify([item.to_dict() for item in items])


@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'backend'})


# ============================================================================
# APP INITIALIZATION
# ============================================================================
def init_app():
    """Initialize database and create tables."""
    db.init_app(app)
    with app.app_context():
        db.create_all()
        logger.info("Database initialized")

init_app()

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5000)))
    app.run(host='0.0.0.0', port=port)
