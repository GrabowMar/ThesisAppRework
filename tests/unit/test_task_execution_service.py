import time

from app.services.task_service import task_service
from app.models import AnalyzerConfiguration, AnalysisTask
from app.constants import AnalysisType, AnalysisStatus


def test_task_execution_service_lifecycle(app):
    """Ensure pending tasks are advanced to completed by execution service."""
    with app.app_context():
        # Create minimal analyzer config if none exists
        if not AnalyzerConfiguration.query.first():
            cfg = AnalyzerConfiguration()
            cfg.name = "TestCfg"
            cfg.analyzer_type = list(AnalysisType)[0]
            cfg.config_data = "{}"
            from app.extensions import db
            db.session.add(cfg)
            db.session.commit()

        # Create several tasks
        created = [
            task_service.create_task(
                model_slug="modelX", app_number=i + 1, analysis_type=list(AnalysisType)[0].value
            )
            for i in range(2)
        ]

        # All should start pending
        assert all(t.status == AnalysisStatus.PENDING for t in created)

        # Deterministically advance tasks using synchronous helper instead of waiting on thread
        from app.services.task_execution_service import task_execution_service
        assert task_execution_service is not None
        deadline = time.time() + 5
        while time.time() < deadline:
            transitioned = task_execution_service.process_once(limit=5)
            # Expire session state to avoid stale cached objects
            from app.extensions import db
            try:
                db.session.expire_all()
            except Exception:
                pass
            done = AnalysisTask.query.filter_by(status=AnalysisStatus.COMPLETED).count()
            if done >= len(created):
                break
            if transitioned == 0:
                time.sleep(0.05)

        from app.extensions import db
        try:
            db.session.expire_all()
        except Exception:
            pass
        completed_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.COMPLETED).all()
        assert len(completed_tasks) == len(created), "All tasks should complete via executor"
        for t in completed_tasks:
            assert t.progress_percentage == 100.0
            assert t.started_at is not None
            assert t.completed_at is not None