from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({'message': 'Hello from qwen_qwen3-235b-a22b-2507 Flask Backend!'})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=6611)
