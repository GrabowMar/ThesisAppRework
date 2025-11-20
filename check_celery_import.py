
try:
    import celery
    print("Celery imported successfully")
except ImportError as e:
    print(f"Celery import failed: {e}")

try:
    from app.tasks import execute_subtask
    print("app.tasks imported successfully")
except ImportError as e:
    print(f"app.tasks import failed: {e}")
except Exception as e:
    print(f"app.tasks import error: {e}")
