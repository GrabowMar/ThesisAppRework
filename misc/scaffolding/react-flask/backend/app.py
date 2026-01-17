# Flask Application Entry Point
from flask import Flask, jsonify
from flask_cors import CORS
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# CORS config (env-driven, defaults to allow all for scaffolding)
cors_origins = os.environ.get('CORS_ORIGINS', '').strip()
if cors_origins:
    origins_list = [o.strip() for o in cors_origins.split(',') if o.strip()]
    CORS(app, supports_credentials=True, origins=origins_list)
else:
    CORS(app, supports_credentials=True)

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:////app/data/app.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', app.config['SECRET_KEY'])

# Initialize database
from models import db
db.init_app(app)

# Register blueprints
from routes import user_bp, admin_bp, auth_bp
app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)


@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy'})


def init_app():
    """Initialize database. LLM: Add seed data here."""
    with app.app_context():
        db.create_all()
        logger.info("Database initialized")
        # LLM: Create default admin user here


init_app()

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(host='0.0.0.0', port=port)
