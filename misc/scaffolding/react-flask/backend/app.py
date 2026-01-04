# Flask Application Entry Point
from flask import Flask, jsonify
from flask_cors import CORS
import os
import logging


class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return '/health' not in msg and 'favicon' not in msg


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').addFilter(HealthCheckFilter())

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', app.config['SECRET_KEY'])

# Initialize database
from models import db, User
db.init_app(app)

# Register blueprints
from routes import user_bp, admin_bp, auth_bp
app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)


@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'backend'})


def init_app():
    """Initialize database and create default admin user."""
    with app.app_context():
        db.create_all()
        logger.info("Database initialized")
        
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin2025')
        
        if not User.query.filter_by(username=admin_username).first():
            admin = User(username=admin_username, email='admin@example.com', is_admin=True, is_active=True)  # type: ignore[call-arg]
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            logger.info(f"Created admin user: {admin_username}")


init_app()

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5000)))
    app.run(host='0.0.0.0', port=port)
