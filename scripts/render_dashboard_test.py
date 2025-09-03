"""Render dashboard template using a minimal Flask app to verify templates.

This script does NOT import the project package; it only uses Flask to
render the `pages/index/index_main.html` template with a minimal context.
Run from the workspace root using the project's venv Python.
"""
from flask import Flask, render_template
import sys

app = Flask(__name__, template_folder='src/templates', static_folder='src/static')

def main():
    ctx = app.test_request_context('/')
    ctx.push()
    try:
        html = render_template('pages/index/index_main.html', stats={}, summary=None)
        # Print the first 1000 chars to avoid huge output
        print(html[:4000])
        return 0
    except Exception as e:
        print('TEMPLATE_RENDER_ERROR:', e, file=sys.stderr)
        raise
    finally:
        ctx.pop()

if __name__ == '__main__':
    sys.exit(main())
