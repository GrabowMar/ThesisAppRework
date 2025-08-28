"""Container Service (Deprecated)
================================

This module is retained only as a compatibility shim. A future
implementation will live in a dedicated orchestration component outside the
Flask web process (e.g. a lightweight controller or separate worker) to
avoid coupling lifecycle management with request handling.

Current State:
    * All methods raise NotImplementedError after emitting a DeprecationWarning
    * Callers should migrate to using DockerManager (if present) or upcoming
      orchestration services.

Rationale:
    Container lifecycle concerns (build / run / logs / cleanup) introduce
    blocking I/O and external process management that does not belong in
    synchronous Flask service objects. Centralizing these concerns elsewhere
    simplifies the service layer and reduces bloat.
"""

import logging
from .service_base import deprecation_warning

logger = logging.getLogger(__name__)


DEPRECATED = True


class ContainerService:  # pragma: no cover - deprecated shim
    def __init__(self, *_, **__):  # accept flexible args to avoid breakage
        deprecation_warning(
            "ContainerService is deprecated. Use DockerManager (if available) "
            "or new orchestration services instead.")
        self.logger = logger
    
    def start_containers(self, model_slug: str, app_number: int) -> None:
        """
        Start containers for an AI-generated application.
        
        Args:
            model_slug: Model identifier (e.g., 'anthropic_claude-3.7-sonnet')
            app_number: Application number (1-30)
            
        Returns:
            Dict containing operation status and details
            
        TODO: Implement container startup logic:
        - Validate docker-compose.yml exists
        - Allocate ports dynamically
        - Execute docker-compose up
        - Monitor startup health
        - Update database with container status
        """
    deprecation_warning("start_containers deprecated – no inline implementation.")
    raise NotImplementedError("ContainerService deprecated. Use DockerManager or external orchestrator.")
    
    def stop_containers(self, model_slug: str, app_number: int) -> None:
        """
        Stop containers for an AI-generated application.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            
        Returns:
            Dict containing operation status and details
            
        TODO: Implement container shutdown logic:
        - Execute docker-compose down
        - Clean up resources
        - Release allocated ports
        - Update database status
        """
    deprecation_warning("stop_containers deprecated – no inline implementation.")
    raise NotImplementedError("ContainerService deprecated. Use DockerManager or external orchestrator.")
    
    def get_container_status(self, model_slug: str, app_number: int) -> None:
        """
        Get status of containers for an AI-generated application.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            
        Returns:
            Dict containing container status information
            
        TODO: Implement status checking:
        - Query Docker for container states
        - Check health endpoints
        - Return detailed status info
        - Include resource usage metrics
        """
    deprecation_warning("get_container_status deprecated – no inline implementation.")
    raise NotImplementedError("ContainerService deprecated. Use DockerManager or external orchestrator.")
    
    def restart_containers(self, model_slug: str, app_number: int) -> None:
        """
        Restart containers for an AI-generated application.
        
        TODO: Implement restart logic
        """
    deprecation_warning("restart_containers deprecated – no inline implementation.")
    raise NotImplementedError("ContainerService deprecated. Use DockerManager or external orchestrator.")
    
    def get_container_logs(self, model_slug: str, app_number: int, 
                          container_type: str = 'backend') -> None:
        """
        Get logs from specific container.
        
        TODO: Implement log retrieval
        """
    deprecation_warning("get_container_logs deprecated – no inline implementation.")
    raise NotImplementedError("ContainerService deprecated. Use DockerManager or external orchestrator.")

__all__ = ["ContainerService", "DEPRECATED"]
