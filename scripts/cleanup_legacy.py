import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def rm(path: Path):
    try:
        if path.is_dir():
            shutil.rmtree(path)
            print(f"Removed dir: {path}")
        elif path.exists():
            path.unlink()
            print(f"Removed file: {path}")
    except Exception as e:
        print(f"WARN: Failed to remove {path}: {e}")


def main():
    # Alias analysis templates to delete
    analysis = ROOT / 'src' / 'templates' / 'partials' / 'analysis'
    alias_files = [
        analysis / 'active_tasks.html',
        analysis / 'list_combined.html',
        analysis / 'list_dynamic.html',
        analysis / 'list_performance.html',
        analysis / 'list_security.html',
        analysis / 'list_shell.html',
        analysis / 'preview_shell.html',
        analysis / 'create_shell.html',
    ]

    # Testing templates/pages
    pages_testing = ROOT / 'src' / 'templates' / 'pages' / 'testing.html'
    testing_partials_dir = ROOT / 'src' / 'templates' / 'partials' / 'testing'

    # Backend testing modules
    routes_dir = ROOT / 'src' / 'app' / 'routes'
    api_dir = routes_dir / 'api'
    testing_modules = [
        routes_dir / 'testing.py',
        api_dir / 'testing.py',
        api_dir / 'testing_results.py',
        api_dir / 'testing_results_fixed.py',
        api_dir / 'testing_results_simple.py',
    ]

    for p in alias_files:
        rm(p)

    rm(pages_testing)

    # Remove all files under testing partials then remove dir
    if testing_partials_dir.exists():
        for child in testing_partials_dir.iterdir():
            rm(child)
        try:
            testing_partials_dir.rmdir()
            print(f"Removed dir: {testing_partials_dir}")
        except OSError:
            # Not empty or in use; leave but it should be empty
            pass

    for p in testing_modules:
        rm(p)

if __name__ == '__main__':
    main()
