"""Maintenance service consolidating former script-based operational tasks.

Provides in-process methods for database population, verification, initialization,
log cleanup, and lightweight smoke placeholders. This removes the need for the
Flask app to import or spawn scripts under the top-level `scripts/` directory.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime
from typing import Any, Dict, Callable

from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models import (
    ModelCapability,
    PortConfiguration,
    GeneratedApplication,
)
from app.services.model_service import ModelService

logger = logging.getLogger(__name__)


class MaintenanceService:
    """Centralized maintenance operations."""

    def __init__(self, app=None):
        self.app = app or current_app

    # ------------------------------------------------------------------
    # Database operations
    # ------------------------------------------------------------------
    def init_database(self, drop_existing: bool = False) -> Dict[str, Any]:
        if drop_existing:
            logger.warning("Dropping all tables before init (drop_existing=True)")
            db.drop_all()
        db.create_all()
        return {
            "operation": "init_database",
            "dropped": drop_existing,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def populate_database(self, verify: bool = True) -> Dict[str, Any]:
        logger.info("MaintenanceService.populate_database starting")
        
        # Use DataInitializationService for comprehensive data loading including OpenRouter
        from app.services.data_initialization import DataInitializationService
        data_init_service = DataInitializationService()
        
        results = data_init_service.initialize_all_data()
        verification = self.verify_database() if verify else {}
        
        payload = {
            "operation": "populate_database",
            "results": results,
            "verification": verification,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        logger.info("MaintenanceService.populate_database finished: %s", payload)
        return payload

    def verify_database(self) -> Dict[str, Any]:
        model_count = ModelCapability.query.count()
        port_count = PortConfiguration.query.count()
        app_count = GeneratedApplication.query.count()
        providers_raw = (
            ModelCapability.query.with_entities(
                ModelCapability.provider,
                func.count(ModelCapability.id).label("count"),
            )
            .group_by(ModelCapability.provider)
            .all()
        )
        providers = {p: c for p, c in providers_raw}
        return {
            "models": model_count,
            "ports": port_count,
            "applications": app_count,
            "providers": providers,
            "status": "ok",
        }

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------
    def cleanup_logs(self, max_age_days: int = 7) -> Dict[str, Any]:
        logs_dir = self.app.config.get("LOGS_DIR", "logs")
        removed, kept = [], []
        if not os.path.isdir(logs_dir):
            return {
                "operation": "cleanup_logs",
                "status": "no_logs_dir",
                "logs_dir": logs_dir,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        now_ts = datetime.utcnow().timestamp()
        cutoff = max_age_days * 86400
        for name in os.listdir(logs_dir):
            path = os.path.join(logs_dir, name)
            try:
                if os.path.isfile(path):
                    age = now_ts - os.path.getmtime(path)
                    if age > cutoff:
                        os.remove(path)
                        removed.append(name)
                    else:
                        kept.append(name)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to process log file %s: %s", name, e)
        return {
            "operation": "cleanup_logs",
            "removed": removed,
            "kept": kept,
            "max_age_days": max_age_days,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    # ------------------------------------------------------------------
    # Smoke placeholders (extend later)
    # ------------------------------------------------------------------
    def sample_generation_smoke(self) -> Dict[str, Any]:
        return {
            "operation": "sample_generation_smoke",
            "status": "stub",
            "message": "Implement real sample generation smoke test",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def http_smoke(self) -> Dict[str, Any]:
        return {
            "operation": "http_smoke",
            "status": "stub",
            "message": "Implement real HTTP smoke test",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------
    def run_action(self, action: str) -> Dict[str, Any]:
        mapping: dict[str, Callable[[], Dict[str, Any]]] = {
            "init-db": lambda: self.init_database(drop_existing=False),
            "populate-db": lambda: self.populate_database(verify=True),
            "log-cleanup": self.cleanup_logs,
            "sample-generation-smoke": self.sample_generation_smoke,
            "sample-smoke": self.sample_generation_smoke,
            "http-smoke": self.http_smoke,
        }
        fn = mapping.get(action)
        if not fn:
            return {"ok": False, "error": f"Unknown action '{action}'"}
        try:
            result = fn()
            return {"ok": True, "result": result, "action": action}
        except Exception as e:  # noqa: BLE001
            logger.exception("Maintenance action failed: %s", action)
            return {"ok": False, "error": str(e), "action": action}


__all__ = ["MaintenanceService"]
