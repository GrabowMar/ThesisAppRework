# Minimal Flask scaffold - will be replaced by AI-generated code
from flask import Flask

app = Flask(__name__)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5000)))
    app.run(host='0.0.0.0', port=port)
