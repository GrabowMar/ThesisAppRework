from flask import Flask, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({'message': 'Hello from anthropic_claude-3.7-sonnet Flask Backend!'})

if __name__ == "__main__":
    port = int(os.environ.get("APP_PORT", 6051))
    app.run(host='0.0.0.0', port=port)
