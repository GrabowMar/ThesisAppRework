from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({'message': 'Hello from nousresearch_deephermes-3-llama-3-8b-preview Flask Backend!'})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5745)
