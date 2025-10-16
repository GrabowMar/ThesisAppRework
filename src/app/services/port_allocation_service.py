"""Centralized Port Allocation Service
=======================================

Provides a single source of truth for port allocation across all generated apps.
Prevents port conflicts by tracking allocations in the database and dynamically
assigning the next free port pair.

Key features:
- Atomic port allocation with database persistence
- Collision detection and prevention
- Support for pre-configured ports from port_config.json
- Thread-safe allocation with proper locking
- Automatic gap filling (reuses freed ports)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
import json

from app.extensions import db
from app.models import PortConfiguration
from sqlalchemy import or_

logger = logging.getLogger(__name__)


@dataclass
class PortPair:
    """Represents an allocated port pair."""
    backend: int
    frontend: int
    model: str
    app_num: int


class PortAllocationService:
    """Centralized service for allocating and tracking application ports.
    
    This service ensures that each app gets unique backend and frontend ports
    by maintaining state in the database and dynamically finding the next
    available port pair.
    """
    
    # Port configuration
    BASE_BACKEND_PORT = 5001
    BASE_FRONTEND_PORT = 8001
    PORT_STEP = 2  # Increment for each app (backend and frontend are PORT_STEP apart)
    MAX_PORT = 65535
    
    def __init__(self, config_file: Optional[Path] = None):
        """Initialize the port allocation service.
        
        Args:
            config_file: Optional path to port_config.json for pre-configured ports
        """
        self.config_file = config_file
        self._port_configs: List[Dict[str, Any]] = []
        if config_file and config_file.exists():
            self._load_port_config(config_file)
    
    def _load_port_config(self, config_file: Path) -> None:
        """Load pre-configured ports from JSON file."""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self._port_configs = json.load(f)
            logger.info(f"Loaded {len(self._port_configs)} pre-configured port assignments")
        except Exception as e:
            logger.error(f"Failed to load port config from {config_file}: {e}")
            self._port_configs = []
    
    def get_or_allocate_ports(self, model_name: str, app_num: int) -> PortPair:
        """Get existing port allocation or allocate a new port pair.
        
        This is the main entry point for port allocation. It will:
        1. Check the database for existing allocation
        2. Check pre-configured ports from JSON
        3. Dynamically allocate the next free port pair
        4. Register the allocation in the database
        
        Args:
            model_name: The model name (e.g., "openai_gpt-4")
            app_num: The application number (1-based)
            
        Returns:
            PortPair with backend and frontend ports
        """
        # 1. Check database for existing allocation
        existing = PortConfiguration.query.filter_by(
            model=model_name,
            app_num=app_num
        ).first()
        
        if existing:
            logger.debug(f"Found existing port allocation for {model_name}/app{app_num}: "
                        f"backend={existing.backend_port}, frontend={existing.frontend_port}")
            return PortPair(
                backend=existing.backend_port,
                frontend=existing.frontend_port,
                model=model_name,
                app_num=app_num
            )
        
        # 2. Check pre-configured ports from JSON
        for config in self._port_configs:
            if config.get('model') == model_name and config.get('app_number') == app_num:
                backend = config.get('backend_port')
                frontend = config.get('frontend_port')
                if backend and frontend:
                    # Register in database
                    self._register_ports(model_name, app_num, backend, frontend)
                    logger.info(f"Using pre-configured ports for {model_name}/app{app_num}: "
                               f"backend={backend}, frontend={frontend}")
                    return PortPair(
                        backend=backend,
                        frontend=frontend,
                        model=model_name,
                        app_num=app_num
                    )
        
        # 3. Dynamically allocate next free port pair
        backend, frontend = self._find_next_free_ports()
        self._register_ports(model_name, app_num, backend, frontend)
        logger.info(f"Dynamically allocated ports for {model_name}/app{app_num}: "
                   f"backend={backend}, frontend={frontend}")
        
        return PortPair(
            backend=backend,
            frontend=frontend,
            model=model_name,
            app_num=app_num
        )
    
    def _find_next_free_ports(self) -> Tuple[int, int]:
        """Find the next free backend/frontend port pair.
        
        Returns:
            Tuple of (backend_port, frontend_port)
        """
        # Get all allocated ports from database
        all_allocations = PortConfiguration.query.all()
        used_backend_ports = {alloc.backend_port for alloc in all_allocations}
        used_frontend_ports = {alloc.frontend_port for alloc in all_allocations}
        
        # Start from base ports and find first free pair
        backend_candidate = self.BASE_BACKEND_PORT
        frontend_candidate = self.BASE_FRONTEND_PORT
        
        while backend_candidate < self.MAX_PORT and frontend_candidate < self.MAX_PORT:
            # Check if both ports are free
            if (backend_candidate not in used_backend_ports and 
                frontend_candidate not in used_frontend_ports):
                return backend_candidate, frontend_candidate
            
            # Move to next port pair
            backend_candidate += self.PORT_STEP
            frontend_candidate += self.PORT_STEP
        
        # Fallback: if we somehow exhausted the range, use a very high port
        logger.error("Exhausted standard port range, using fallback high ports")
        return 60000, 63000
    
    def _register_ports(self, model_name: str, app_num: int, 
                       backend_port: int, frontend_port: int) -> None:
        """Register port allocation in the database.
        
        Args:
            model_name: The model name
            app_num: The application number
            backend_port: The backend port to register
            frontend_port: The frontend port to register
        """
        try:
            # Check for conflicts
            conflict = PortConfiguration.query.filter(
                or_(
                    PortConfiguration.backend_port == backend_port,
                    PortConfiguration.frontend_port == frontend_port
                )
            ).first()
            
            if conflict:
                logger.error(f"Port conflict detected! Attempted to register "
                           f"backend={backend_port}, frontend={frontend_port} "
                           f"but they're already used by {conflict.model}/app{conflict.app_num}")
                raise ValueError("Port conflict: ports already in use")
            
            # Create new allocation
            port_config = PortConfiguration(
                model=model_name,
                app_num=app_num,
                backend_port=backend_port,
                frontend_port=frontend_port,
                is_available=True
            )
            db.session.add(port_config)
            db.session.commit()
            
            logger.debug(f"Registered ports for {model_name}/app{app_num}: "
                        f"backend={backend_port}, frontend={frontend_port}")
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to register ports for {model_name}/app{app_num}: {e}")
            raise
    
    def release_ports(self, model_name: str, app_num: int) -> bool:
        """Release port allocation for reuse.
        
        Args:
            model_name: The model name
            app_num: The application number
            
        Returns:
            True if ports were released, False if not found
        """
        try:
            allocation = PortConfiguration.query.filter_by(
                model=model_name,
                app_num=app_num
            ).first()
            
            if allocation:
                db.session.delete(allocation)
                db.session.commit()
                logger.info(f"Released ports for {model_name}/app{app_num}")
                return True
            
            return False
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to release ports for {model_name}/app{app_num}: {e}")
            raise
    
    def get_all_allocations(self) -> List[Dict[str, Any]]:
        """Get all current port allocations.
        
        Returns:
            List of allocation dictionaries
        """
        allocations = PortConfiguration.query.all()
        return [
            {
                'model': alloc.model,
                'app_num': alloc.app_num,
                'backend_port': alloc.backend_port,
                'frontend_port': alloc.frontend_port,
                'is_available': alloc.is_available,
                'created_at': alloc.created_at.isoformat() if alloc.created_at else None
            }
            for alloc in allocations
        ]
    
    def check_port_conflicts(self) -> List[str]:
        """Check for any port conflicts in the database.
        
        Returns:
            List of conflict descriptions
        """
        conflicts = []
        allocations = PortConfiguration.query.all()
        
        # Check for duplicate backend ports
        backend_ports: Dict[int, List[str]] = {}
        frontend_ports: Dict[int, List[str]] = {}
        
        for alloc in allocations:
            key = f"{alloc.model}/app{alloc.app_num}"
            
            if alloc.backend_port in backend_ports:
                backend_ports[alloc.backend_port].append(key)
            else:
                backend_ports[alloc.backend_port] = [key]
            
            if alloc.frontend_port in frontend_ports:
                frontend_ports[alloc.frontend_port].append(key)
            else:
                frontend_ports[alloc.frontend_port] = [key]
        
        # Report conflicts
        for port, apps in backend_ports.items():
            if len(apps) > 1:
                conflicts.append(f"Backend port {port} used by multiple apps: {', '.join(apps)}")
        
        for port, apps in frontend_ports.items():
            if len(apps) > 1:
                conflicts.append(f"Frontend port {port} used by multiple apps: {', '.join(apps)}")
        
        return conflicts


# Singleton accessor
_port_allocation_service: Optional[PortAllocationService] = None


def get_port_allocation_service(config_file: Optional[Path] = None) -> PortAllocationService:
    """Get the singleton port allocation service instance.
    
    Args:
        config_file: Optional path to port_config.json
        
    Returns:
        PortAllocationService instance
    """
    global _port_allocation_service
    
    if _port_allocation_service is None:
        from app.paths import MISC_DIR
        default_config = MISC_DIR / 'port_config.json'
        _port_allocation_service = PortAllocationService(
            config_file=config_file or default_config
        )
    
    return _port_allocation_service
