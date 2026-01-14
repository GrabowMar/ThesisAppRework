# Flask Application Entry Point
from flask import Flask, jsonify
from flask_cors import CORS
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

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
