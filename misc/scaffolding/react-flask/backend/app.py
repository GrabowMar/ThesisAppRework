# This file will be replaced by AI-generated code
# DO NOT modify this file - it's just a placeholder for scaffolding

from flask import Flask, jsonify
from flask_cors import CORS
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

@app.route('/')
def index():
    """Root endpoint - provides API information"""
    return jsonify({
        'message': 'AI-Generated Application API',
        'status': 'running',
        'version': '1.0.0',
        'endpoints': {
            '/': 'API information',
            '/health': 'Health check endpoint'
        }
    })

@app.route('/health')
def health():
    """Health check endpoint for Docker healthcheck"""
    return jsonify({
        'status': 'healthy',
        'service': 'backend'
    }), 200

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found', 'message': 'The requested endpoint does not exist'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f'Internal error: {error}')
    return jsonify({'error': 'Internal server error', 'message': 'An unexpected error occurred'}), 500

if __name__ == '__main__':
    # Get port from environment variable with fallback
    port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5000)))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    
    logger.info(f'Starting Flask application on port {port}')
    logger.info(f'Debug mode: {debug}')
    
    try:
        app.run(host='0.0.0.0', port=port, debug=debug)
    except Exception as e:
        logger.error(f'Failed to start Flask application: {e}')
        raise
