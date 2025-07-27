from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({'message': 'Hello from mistralai_mistral-small-3.2-24b-instruct Flask Backend!'})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5225)
