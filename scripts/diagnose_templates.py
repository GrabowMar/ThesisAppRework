from flask import Flask
from jinja2 import TemplateNotFound
import os

app = Flask(__name__, template_folder='src/templates', static_folder='src/static')
print('app.template_folder:', app.template_folder)
print('cwd:', os.getcwd())
print('exists file:', os.path.exists(os.path.join(app.template_folder,'pages/index/index_main.html')))
print('loader searchpath:', app.jinja_loader.searchpath)
try:
    t = app.jinja_env.get_template('pages/index/index_main.html')
    print('loaded template ok; name:', t.name)
except TemplateNotFound as e:
    print('TemplateNotFound:', e)
