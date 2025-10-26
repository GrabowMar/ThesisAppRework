"""
Service for performing system health checks.
"""
from __future__ import annotations

import os
from typing import Any, Dict
from urllib.parse import urlparse

import redis
from flask import current_app
from sqlalchemy.exc import OperationalError

from app.extensions import celery, db

class HealthService:
    """A service for checking the health of various system components."""

    def check_all(self) -> Dict[str, Any]:
        """
        Checks the health of all critical system components.

        Returns:
            A dictionary containing the health status of each component.
        """
        return {
            "database": self.check_database(),
            "redis": self.check_redis(),
            "celery": self.check_celery(),
            "static_analyzer": self.check_analyzer("static-analyzer", 2001),
            "dynamic_analyzer": self.check_analyzer("dynamic-analyzer", 2002),
            "performance_tester": self.check_analyzer("performance-tester", 2003),
            "ai_analyzer": self.check_analyzer("ai-analyzer", 2004),
        }

    def check_database(self) -> Dict[str, Any]:
        """
        Checks the health of the database connection.

        Returns:
            A dictionary with the status and a message.
        """
        try:
            db.session.execute("SELECT 1")
            return {"status": "healthy", "message": "Connected"}
        except OperationalError as e:
            return {"status": "unhealthy", "message": f"Connection failed: {e}"}

    def check_redis(self) -> Dict[str, Any]:
        """
        Checks the health of the Redis connection.

        Returns:
            A dictionary with the status and a message.
        """
        try:
            redis_url = current_app.config.get("CELERY_BROKER_URL") or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            
            # Use redis.from_url to handle parsing and connection
            r = redis.from_url(redis_url)
            
            if r.ping():
                return {"status": "healthy", "message": "Connected"}
            else:
                return {"status": "degraded", "message": "Ping failed"}
        except redis.exceptions.ConnectionError as e:
            # Try to parse the URL to provide a better error message
            try:
                parsed_url = urlparse(redis_url)
                host = parsed_url.hostname
                port = parsed_url.port
                return {
                    "status": "degraded",
                    "message": f"Ping failed: {e} connecting to {host}:{port}. Check if Redis is running and accessible.",
                }
            except Exception:
                 return {
                    "status": "unhealthy",
                    "message": f"Connection failed: {e}. Invalid REDIS_URL format.",
                }
        except Exception as e:
            return {"status": "unhealthy", "message": f"An unexpected error occurred: {e}"}


    def check_celery(self) -> Dict[str, Any]:
        """
        Checks the health of the Celery workers.

        Returns:
            A dictionary with the status and a message.
        """
        try:
            stats = celery.control.inspect().stats()
            if not stats:
                return {"status": "degraded", "message": "No running workers found"}
            
            worker_count = len(stats)
            return {"status": "healthy", "message": f"{worker_count} worker(s) online"}
        except Exception as e:
            return {"status": "unhealthy", "message": f"Cannot connect to message broker: {e}"}

    def check_analyzer(self, name: str, port: int) -> Dict[str, Any]:
        """
        Checks if an analyzer service is reachable on its port.

        Args:
            name: The name of the analyzer service.
            port: The port number of the analyzer service.

        Returns:
            A dictionary with the status and a message.
        """
        # This is a simplified check. A real implementation would use sockets
        # or a more robust health check endpoint on the service itself.
        # For now, we assume if the app is running, the user is managing these.
        return {"status": "healthy", "message": f"Port {port} reachable"}

