"""Apply 'installed' column to model_capabilities table if missing.

This script uses the Flask app factory to get the SQLAlchemy engine and then
adds the column and index if they are not present. Designed to be idempotent.

Run:
    C:/Users/grabowmar/Desktop/ThesisAppRework/.venv/Scripts/python.exe scripts/apply_installed_column.py
"""
import sys
import logging
from pathlib import Path
from sqlalchemy import inspect, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    try:
        # Ensure 'src' is on sys.path so package imports like 'app' work
        repo_root = Path(__file__).resolve().parent.parent
        src_path = str(repo_root / 'src')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

        # Import the app factory and extensions
        from app.factory import create_app
        from app.extensions import db
    except Exception as e:
        logger.error("Failed to import app factory: %s", e)
        sys.exit(1)

    app = create_app()
    with app.app_context():
        engine = db.session.get_bind() if hasattr(db.session, 'get_bind') else db.engine
        inspector = inspect(engine)
        cols = [c['name'] for c in inspector.get_columns('model_capabilities')]
        if 'installed' in cols:
            logger.info("Column 'installed' already exists on model_capabilities")
            return

        dialect = engine.dialect.name
        logger.info("DB dialect: %s", dialect)

        try:
            if dialect in ('postgresql', 'postgres'):
                add_sql = 'ALTER TABLE model_capabilities ADD COLUMN installed boolean DEFAULT false'
                idx_sql = 'CREATE INDEX IF NOT EXISTS ix_model_capabilities_installed ON model_capabilities (installed)'
            elif dialect == 'sqlite':
                # SQLite supports adding columns but not IF NOT EXISTS for index in older versions
                add_sql = "ALTER TABLE model_capabilities ADD COLUMN installed BOOLEAN DEFAULT 0"
                idx_sql = 'CREATE INDEX IF NOT EXISTS ix_model_capabilities_installed ON model_capabilities (installed)'
            elif dialect in ('mysql', 'mariadb'):
                add_sql = "ALTER TABLE model_capabilities ADD COLUMN installed TINYINT(1) DEFAULT 0"
                idx_sql = 'CREATE INDEX ix_model_capabilities_installed ON model_capabilities (installed)'
            else:
                # Generic fallback
                add_sql = "ALTER TABLE model_capabilities ADD COLUMN installed BOOLEAN DEFAULT false"
                idx_sql = 'CREATE INDEX ix_model_capabilities_installed ON model_capabilities (installed)'

            logger.info("Applying SQL: %s", add_sql)
            with engine.begin() as conn:
                conn.execute(text(add_sql))
                conn.execute(text(idx_sql))
            logger.info("Column and index added successfully.")
        except Exception as e:
            logger.error("Failed to add column/index: %s", e)
            sys.exit(1)


if __name__ == '__main__':
    main()
