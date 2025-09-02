```python
# Mock backend for test_api (model: mock/local-model)
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify(status='ok', template='test_api', model='mock/local-model')

if __name__ == '__main__':
    app.run(port=5000)
```
```text
flask
```