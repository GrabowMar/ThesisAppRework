"""
Performance Configuration
========================

Configuration settings for optimizing application performance.
"""

# HTMX refresh intervals (in seconds)
HTMX_REFRESH_INTERVALS = {
    'development': {
        'sidebar_stats': 60,           # Quick stats update
        'sidebar_activity': 120,       # Activity feed update  
        'sidebar_system_status': 90,   # System health check
        'dashboard_stats': 120,        # Dashboard summary stats
        'dashboard_models': 300,       # Full models grid refresh
    },
    'production': {
        'sidebar_stats': 120,          # Slower in production
        'sidebar_activity': 300,       # Less frequent activity updates
        'sidebar_system_status': 180,  # System health every 3 minutes
        'dashboard_stats': 180,        # Dashboard stats every 3 minutes
        'dashboard_models': 600,       # Models grid every 10 minutes
    }
}

# Database optimization settings
DATABASE_OPTIMIZATION = {
    'connection_pool_size': 20,
    'max_overflow': 0,
    'pool_timeout': 30,
    'pool_recycle': 3600,  # 1 hour
    'query_timeout': 30,
    'batch_size': 100,     # Batch operations
}

# Sampling settings for expensive operations
SAMPLING_CONFIG = {
    'container_status_check': {
        'max_models_sample': 5,        # Sample max 5 models
        'max_apps_per_model': 3,       # Check max 3 apps per model
        'scale_results': True,         # Scale sample results to full dataset
    },
    'performance_metrics': {
        'enabled': True,
        'sample_rate': 0.1,            # Sample 10% of requests
    }
}

# Frontend optimization
FRONTEND_OPTIMIZATION = {
    'lazy_loading': True,              # Enable lazy loading of components
    'image_optimization': True,        # Optimize images
    'css_minification': True,          # Minify CSS in production
    'js_minification': True,           # Minify JavaScript in production
    'gzip_compression': True,          # Enable gzip compression
}

# Memory management
MEMORY_MANAGEMENT = {
    'log_rotation_size': '10MB',       # Rotate logs at 10MB
    'max_log_files': 5,                # Keep max 5 log files
}

def get_config_for_environment(env: str = 'development') -> dict:
    """Get performance configuration for specific environment."""
    return {
        'htmx_intervals': HTMX_REFRESH_INTERVALS.get(env, HTMX_REFRESH_INTERVALS['development']),
        'database': DATABASE_OPTIMIZATION,
        'sampling': SAMPLING_CONFIG,
        'frontend': FRONTEND_OPTIMIZATION,
        'memory': MEMORY_MANAGEMENT,
    }
