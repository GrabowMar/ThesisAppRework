```python
# Mock backend for mini_api_one (model: minimax/minimax-12b-chat)
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify(status='ok', template='mini_api_one', model='minimax/minimax-12b-chat')

if __name__ == '__main__':
    app.run(port=5000)
```
```text
flask
```