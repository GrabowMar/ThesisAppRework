# Minimal Flask Application Scaffolding
# This is a barebones working Flask app that does nothing by default

from flask import Flask, jsonify
from flask_cors import CORS
import logging

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'development-secret-key'
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Flask app is running'}), 200

# Root endpoint
@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({'message': 'Flask API is running', 'version': '1.0.0'}), 200

if __name__ == '__main__':
    logger.info("Starting Flask application...")
    app.run(host='0.0.0.0', port={{backend_port|5000}}, debug=True)
