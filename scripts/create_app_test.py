import os
import sys

# Ensure src/ is on sys.path so 'app' package can be imported when running
# scripts from the repository root.
repo_root = os.path.dirname(os.path.dirname(__file__))
src_dir = os.path.join(repo_root, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

os.environ.setdefault('FLASK_ENV', 'testing')

try:
    from app.factory import create_app
except Exception as e:
    print('IMPORT_FACTORY_ERROR', e)
    raise

def main():
    try:
        app = create_app('testing')
        print('App created. Routes:')
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            print(f"{rule.rule} -> {rule.endpoint}")

        with app.test_client() as c:
            resp = c.get('/')
            print('GET / status:', resp.status_code)
            # Print a short snippet of body
            print('Body snippet:', (resp.get_data(as_text=True)[:800]).replace('\n',' '))
        return 0
    except Exception as e:
        print('APP_CREATE_OR_REQUEST_ERROR', e)
        raise

if __name__ == '__main__':
    sys.exit(main())
