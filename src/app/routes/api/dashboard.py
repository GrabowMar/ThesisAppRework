"""
Dashboard API routes
====================

Endpoints for dashboard overview, statistics, and HTMX fragments.
"""

from flask import Blueprint, current_app, jsonify, request
import logging
from typing import Any
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models import (
    ModelCapability, GeneratedApplication, SecurityAnalysis, 
    PerformanceTest, BatchAnalysis
)
from app.services.statistics_service import (
    get_application_statistics, get_model_statistics, get_analysis_statistics,
    get_recent_statistics, get_model_distribution, get_generation_trends,
    get_analysis_summary, export_statistics, get_generation_statistics_by_models
)
from app.services.dashboard_service import (
    build_summary_payload,
    build_system_status_payload,
    get_recent_activity_entries,
    get_recent_applications,
    get_recent_analysis_summary,
)
from .common import api_success, api_error

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard_api', __name__)


@dashboard_bp.route('/overview')
def api_dashboard_overview():
    """Get dashboard overview data."""
    try:
        # Total counts
        total_apps = db.session.query(db.func.count(GeneratedApplication.id)).scalar()
        total_models = db.session.query(db.func.count(ModelCapability.id)).scalar()
        total_security = db.session.query(db.func.count(SecurityAnalysis.id)).scalar()
        total_performance = db.session.query(db.func.count(PerformanceTest.id)).scalar()

        # Recent activity (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_apps = (
            db.session.query(db.func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.created_at >= week_ago)
            .scalar()
        )

        # Active applications
        active_apps = (
            db.session.query(db.func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.container_status == 'running')
            .scalar()
        )

        # Success rates
        completed_security = (
            db.session.query(db.func.count(SecurityAnalysis.id))
            .filter(SecurityAnalysis.status == 'completed')
            .scalar()
        )
        security_rate = (completed_security / total_security * 100) if total_security > 0 else 0

        completed_performance = (
            db.session.query(db.func.count(PerformanceTest.id))
            .filter(PerformanceTest.status == 'completed')
            .scalar()
        )
        performance_rate = (completed_performance / total_performance * 100) if total_performance > 0 else 0

        return api_success({
            'totals': {
                'applications': total_apps,
                'models': total_models,
                'security_analyses': total_security,
                'performance_tests': total_performance
            },
            'activity': {
                'recent_applications': recent_apps,
                'active_applications': active_apps
            },
            'success_rates': {
                'security': round(security_rate, 2),
                'performance': round(performance_rate, 2)
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting dashboard overview: {e}")
        return api_error("Failed to retrieve dashboard overview", details={"reason": str(e)})


@dashboard_bp.route('/summary')
def dashboard_summary():
    """Return aggregated dashboard summary metrics."""
    data = build_summary_payload()
    return api_success(data)


@dashboard_bp.route('/system-status')
def dashboard_system_status_light():
    """Return lightweight system status snapshot."""
    data = build_system_status_payload()
    return api_success(data)


@dashboard_bp.route('/fragments/summary-cards')
def dashboard_summary_cards_fragment():
    from app.utils.template_paths import render_template_compat as render_template

    summary = build_summary_payload()
    return render_template('pages/index/partials/summary_cards.html', summary=summary)


@dashboard_bp.route('/fragments/system-status')
def dashboard_system_status_fragment():
    from app.utils.template_paths import render_template_compat as render_template

    status = build_system_status_payload()
    return render_template('pages/index/partials/system_status.html', system=status)


@dashboard_bp.route('/fragments/recent-activity')
def dashboard_recent_activity_fragment():
    from app.utils.template_paths import render_template_compat as render_template

    entries = get_recent_activity_entries()
    return render_template('pages/index/partials/activity_feed.html', entries=entries)


@dashboard_bp.route('/fragments/recent-applications')
def dashboard_recent_applications_fragment():
    from app.utils.template_paths import render_template_compat as render_template

    apps = get_recent_applications()
    return render_template('pages/index/partials/recent_applications.html', applications=apps)


@dashboard_bp.route('/fragments/recent-analyses')
def dashboard_recent_analyses_fragment():
    from app.utils.template_paths import render_template_compat as render_template

    analyses = get_recent_analysis_summary()
    return render_template('pages/index/partials/recent_analyses.html', analyses=analyses)


@dashboard_bp.route('/stats')
def api_dashboard_stats():
    """Enhanced dashboard statistics."""
    try:
        # Basic counts
        models_count = ModelCapability.query.count()
        apps_count = GeneratedApplication.query.count()
        security_count = SecurityAnalysis.query.count()
        performance_count = PerformanceTest.query.count()

        # Provider breakdown
        provider_stats = db.session.query(
            ModelCapability.provider,
            db.func.count(ModelCapability.id).label('count')
        ).group_by(ModelCapability.provider).all()

        # Application framework breakdown
        framework_stats = db.session.query(
            GeneratedApplication.backend_framework,
            db.func.count(GeneratedApplication.id).label('count')
        ).group_by(GeneratedApplication.backend_framework).all()

        # Recent activity
        recent_models = ModelCapability.query.order_by(
            ModelCapability.created_at.desc()
        ).limit(5).all()

        recent_apps = GeneratedApplication.query.order_by(
            GeneratedApplication.created_at.desc()
        ).limit(5).all()

        return api_success({
            'counts': {
                'models': models_count,
                'applications': apps_count,
                'security_tests': security_count,
                'performance_tests': performance_count
            },
            'providers': [{'name': p[0], 'count': p[1]} for p in provider_stats],
            'frameworks': [{'name': f[0] or 'Unknown', 'count': f[1]} for f in framework_stats],
            'recent_models': [m.to_dict() for m in recent_models],
            'recent_apps': [a.to_dict() for a in recent_apps],
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error getting dashboard stats: {e}")
        return api_error("Failed to retrieve dashboard stats", details={"reason": str(e)})


@dashboard_bp.route('/sidebar_stats')
def sidebar_stats():
    """HTMX endpoint for sidebar statistics."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'total_apps': db.session.query(GeneratedApplication).count(),
            'security_tests': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count()
        }
        return render_template('partials/common/_sidebar_stats_inner.html', stats=stats)
    except Exception as e:
        current_app.logger.error(f"Error getting sidebar stats: {e}")
        from app.utils.template_paths import render_template_compat as render_template
        return render_template('partials/common/_sidebar_stats_inner.html', stats={
            'total_models': 0, 'total_apps': 0, 'security_tests': 0, 'performance_tests': 0
        })


@dashboard_bp.route('/stats-fragment')
def dashboard_stats_fragment():
    """HTMX endpoint returning dashboard stats inner fragment HTML."""
    try:
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'total_apps': db.session.query(GeneratedApplication).count(),
            'security_tests': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count(),
        }
        # Return inline HTML fragment (removed external template dependency)
        return (
            '<div class="row g-3">'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["total_models"]}</div><div class="text-muted small">Models</div>'
            '</div></div></div>'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["total_apps"]}</div><div class="text-muted small">Apps</div>'
            '</div></div></div>'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["security_tests"]}</div><div class="text-muted small">Security</div>'
            '</div></div></div>'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["performance_tests"]}</div><div class="text-muted small">Perf</div>'
            '</div></div></div>'
            '</div>'
        )
    except Exception as e:
        current_app.logger.error(f"Error rendering dashboard stats fragment: {e}")
        return (
            '<div class="row g-3">'
            '<div class="col-12 text-muted small">Stats unavailable</div>'
            '</div>'
        )


@dashboard_bp.route('/system-health-fragment')
def dashboard_system_health_fragment():
    """Return small system health fragment."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        health = {
            'status': 'healthy',
            'uptime_minutes': 0,
            'active_tasks': 0,
        }
        return render_template('pages/system/partials/_system_health_inner.html', health=health)
    except Exception as e:
        current_app.logger.error(f"Error rendering system health: {e}")
        return '<div class="text-muted small">Health unavailable</div>'


@dashboard_bp.route('/system-stats')
def dashboard_system_stats():
    """Compatibility JSON endpoint for live system stats used by dashboard JS.

    Returns counts and basic system resource metrics. If psutil is unavailable,
    resource metrics will be omitted, but counts will still be provided.
    """
    try:
        counts = {
            'models': db.session.query(ModelCapability).count(),
            'applications': db.session.query(GeneratedApplication).count(),
            'security_analyses': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count(),
        }

        data = {
            'counts': counts,
            'resources': {},
            'uptime_seconds': 0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        try:
            import psutil  # type: ignore
            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            boot_time = psutil.boot_time()
            uptime_seconds = int(datetime.now(timezone.utc).timestamp() - boot_time)
            data['resources'] = {
                'cpu_percent': cpu_percent,
                'memory_percent': getattr(mem, 'percent', 0),
                'disk_percent': getattr(disk, 'percent', 0),
                'memory_gb': round(getattr(mem, 'total', 0) / 1024**3, 2) if getattr(mem, 'total', 0) else 0,
                'disk_free_gb': round(getattr(disk, 'free', 0) / 1024**3, 2) if getattr(disk, 'free', 0) else 0,
            }
            data['uptime_seconds'] = uptime_seconds
        except Exception:  # psutil missing or runtime error
            pass

        return jsonify(data)
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error building dashboard system stats: {e}")
        return jsonify({'error': 'Failed to gather system stats', 'details': str(e)}), 500


@dashboard_bp.route('/system-health-comprehensive')
def comprehensive_system_health():
    """Get comprehensive system health including all services, analyzers, and connections."""
    try:
        import subprocess
        import os
        import socket
        
        health_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'overall_status': 'healthy',
            'components': {}
        }
        
        # Database health
        try:
            db.session.execute(db.text('SELECT 1'))
            health_data['components']['database'] = {
                'status': 'healthy',
                'message': 'Database connection active',
                'response_time_ms': None
            }
        except Exception as e:
            health_data['components']['database'] = {
                'status': 'unhealthy',
                'message': f'Database error: {str(e)}',
                'response_time_ms': None
            }
            health_data['overall_status'] = 'degraded'
        
        # Container Tool Registry health
        try:
            from app.engines.container_tool_registry import get_container_tool_registry
            registry = get_container_tool_registry()
            all_tools = registry.get_all_tools()
            container_info = registry.get_container_info()
            
            health_data['tool_registry'] = {
                'status': 'healthy',
                'total_tools': len(all_tools),
                'available_tools': sum(1 for tool in all_tools.values() if tool.available),
                'containers': len(container_info)
            }
        except Exception as e:
            health_data['tool_registry'] = {
                'status': 'unhealthy',
                'message': f'Container tool registry error: {str(e)}'
            }
            health_data['overall_status'] = 'degraded'
        
        # Analyzer services health (initialize with defaults so UI always shows entries)
        analyzer_services = [
            {'name': 'static-analyzer', 'port': 2001, 'type': 'static'},
            {'name': 'dynamic-analyzer', 'port': 2002, 'type': 'dynamic'},
            {'name': 'performance-tester', 'port': 2003, 'type': 'performance'},
            {'name': 'ai-analyzer', 'port': 2004, 'type': 'ai'},
            {'name': 'gateway', 'port': 8765, 'type': 'gateway'}
        ]

        health_data['components']['analyzers'] = {
            svc['name']: {
                'status': 'unknown',
                'message': 'Not checked',
                'port': svc['port'],
                'type': svc['type']
            } for svc in analyzer_services
        }

        try:
            analyzer_dir = os.path.join(os.getcwd(), 'analyzer')
            def _compose(args: list[str], timeout: int = 5):
                for base in (['docker', 'compose'], ['docker-compose']):
                    try:
                        return subprocess.run(base + args, cwd=analyzer_dir, capture_output=True, text=True, timeout=timeout)
                    except Exception:
                        continue
                return None

            if os.path.exists(analyzer_dir):
                for service in analyzer_services:
                    svc_name = service['name']
                    # First try analyzer_manager health (for services it knows)
                    used_fallback = False
                    try:
                        if svc_name != 'gateway':
                            result = subprocess.run(
                                ['python', 'analyzer_manager.py', 'health', svc_name],
                                cwd=analyzer_dir, capture_output=True, text=True, timeout=5
                            )
                        else:
                            result = None
                        if result and result.returncode == 0:
                            health_data['components']['analyzers'][svc_name].update({
                                'status': 'healthy',
                                'message': f"Service {svc_name} responding"
                            })
                            continue
                        else:
                            used_fallback = True
                    except Exception:
                        used_fallback = True

                    # Fallback: use docker compose published port and attempt TCP connect
                    try:
                        port_str = str(service['port'])
                        comp = _compose(['port', svc_name, port_str], timeout=4)
                        if comp and comp.returncode == 0 and comp.stdout.strip():
                            hostport = comp.stdout.strip().splitlines()[0].strip()
                            # Expect '0.0.0.0:PORT' or '127.0.0.1:PORT'
                            hp = hostport.rsplit(':', 1)
                            if len(hp) == 2:
                                host, pub_port = hp[0], int(hp[1])
                                connect_host = '127.0.0.1' if host in ('0.0.0.0', '::') else host
                                try:
                                    with socket.create_connection((connect_host, pub_port), timeout=1.5):
                                        ok = True
                                except Exception:
                                    ok = False
                                if ok:
                                    health_data['components']['analyzers'][svc_name].update({
                                        'status': 'healthy',
                                        'message': f'Port {connect_host}:{pub_port} reachable'
                                    })
                                else:
                                    health_data['components']['analyzers'][svc_name].update({
                                        'status': 'unhealthy',
                                        'message': f'Port {connect_host}:{pub_port} not reachable'
                                    })
                                    health_data['overall_status'] = 'degraded'
                            else:
                                health_data['components']['analyzers'][svc_name].update({
                                    'status': 'unhealthy',
                                    'message': 'Could not resolve published port'
                                })
                                health_data['overall_status'] = 'degraded'
                        else:
                            # If fallback attempted and compose had no mapping, mark unknown
                            if used_fallback:
                                health_data['components']['analyzers'][svc_name].update({
                                    'status': 'unknown',
                                    'message': 'No details'
                                })
                    except Exception as e:
                        health_data['components']['analyzers'][svc_name].update({
                            'status': 'error',
                            'message': f'Docker check failed: {str(e)[:200]}'
                        })
        except Exception:
            pass

        # Compute overall analyzers summary for the System Health tile
        try:
            analyzer_entries = health_data['components'].get('analyzers', {})
            total = len(analyzer_entries)
            healthy = sum(1 for v in analyzer_entries.values() if v.get('status') == 'healthy')
            unhealthy = sum(1 for v in analyzer_entries.values() if v.get('status') == 'unhealthy')
            if total == 0:
                summary_status = 'unknown'
                message = 'No details'
            elif healthy == total:
                summary_status = 'healthy'
                message = f'All {total} services healthy'
            elif healthy == 0 and unhealthy == 0:
                summary_status = 'unknown'
                message = 'No details'
            else:
                summary_status = 'degraded'
                message = f'{healthy}/{total} services healthy'
            health_data['components']['analyzers_summary'] = {
                'status': summary_status,
                'message': message,
                'details': {'healthy': healthy, 'total': total}
            }
        except Exception:
            pass
        
        # Celery health (use accessor from extensions)
        try:
            from app.extensions import get_celery
            celery_app = get_celery()
            if celery_app:
                try:
                    inspect = celery_app.control.inspect()
                    stats = inspect.stats() if inspect else None
                except Exception:
                    stats = None

                if stats:
                    active_workers = len(stats)
                    health_data['components']['celery'] = {
                        'status': 'healthy',
                        'message': f'{active_workers} worker(s) active',
                        'details': {'active_workers': active_workers}
                    }
                else:
                    health_data['components']['celery'] = {
                        'status': 'unhealthy',
                        'message': 'No active Celery workers'
                    }
                    health_data['overall_status'] = 'degraded'
            else:
                health_data['components']['celery'] = {
                    'status': 'not_configured',
                    'message': 'Celery not initialized in app components'
                }
        except Exception as e:
            health_data['components']['celery'] = {
                'status': 'error',
                'message': f'Celery check failed: {str(e)}'
            }
        
        # OpenRouter connection health
        try:
            # Prefer app config, but fallback to environment for flexibility
            import os as _os
            openrouter_key = current_app.config.get('OPENROUTER_API_KEY') or _os.getenv('OPENROUTER_API_KEY')
            if openrouter_key:
                # Try a simple API call to test connection
                import requests
                headers = {
                    'Authorization': f'Bearer {openrouter_key}',
                    'Content-Type': 'application/json'
                }
                response = requests.get(
                    'https://openrouter.ai/api/v1/models', 
                    headers=headers, 
                    timeout=5
                )
                if response.status_code == 200:
                    models_data = response.json()
                    model_count = len(models_data.get('data', []))
                    health_data['components']['openrouter'] = {
                        'status': 'healthy',
                        'message': f'OpenRouter API accessible ({model_count} models available)',
                        'details': {'available_models': model_count}
                    }
                else:
                    health_data['components']['openrouter'] = {
                        'status': 'unhealthy',
                        'message': f'OpenRouter API error: {response.status_code}'
                    }
                    health_data['overall_status'] = 'degraded'
            else:
                health_data['components']['openrouter'] = {
                    'status': 'not_configured',
                    'message': 'OpenRouter API key not configured'
                }
        except Exception as e:
            health_data['components']['openrouter'] = {
                'status': 'error',
                'message': f'OpenRouter check failed: {str(e)}'
            }
        
        # Redis health (derive from configuration; avoid importing non-existent redis_client)
        try:
            redis_url = (
                current_app.config.get('REDIS_URL')
                or current_app.config.get('CELERY_BROKER_URL')
                or current_app.config.get('CELERY_RESULT_BACKEND')
            )
            redis_url_synthetic = bool(current_app.config.get('REDIS_URL_SYNTHETIC'))
            if redis_url and str(redis_url).startswith('redis'):
                try:
                    import redis  # type: ignore
                    client: Any = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
                    client.ping()
                    health_data['components']['redis'] = {
                        'status': 'healthy',
                        'message': 'Redis connection active',
                        'details': {'url': redis_url.split('@')[-1] if '@' in redis_url else redis_url}
                    }
                except Exception as e:
                    # Attempt Docker Compose port resolution as a fallback for API-Docker context
                    try:
                        analyzer_dir = os.path.join(os.getcwd(), 'analyzer')
                        def _compose(args: list[str], timeout: int = 5):
                            for base in (['docker', 'compose'], ['docker-compose']):
                                try:
                                    return subprocess.run(base + args, cwd=analyzer_dir, capture_output=True, text=True, timeout=timeout)
                                except Exception:
                                    continue
                            return None
                        comp = _compose(['port', 'redis', '6379'], timeout=4)
                        if comp and comp.returncode == 0 and comp.stdout.strip():
                            hostport = comp.stdout.strip().splitlines()[0].strip()
                            hp = hostport.rsplit(':', 1)
                            if len(hp) == 2:
                                host, pub_port = hp[0], int(hp[1])
                                connect_host = '127.0.0.1' if host in ('0.0.0.0', '::') else host
                                import redis  # type: ignore
                                url = f"redis://{connect_host}:{pub_port}/0"
                                client2: Any = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
                                client2.ping()
                                health_data['components']['redis'] = {
                                    'status': 'healthy',
                                    'message': 'Redis connection active (via Docker)',
                                    'details': {'url': url}
                                }
                            else:
                                raise RuntimeError('Could not parse docker port output')
                        else:
                            raise RuntimeError('Docker compose port did not return mapping')
                    except Exception:
                        if redis_url_synthetic:
                            health_data['components']['redis'] = {
                                'status': 'not_configured',
                                'message': 'Redis not available in this environment'
                            }
                        else:
                            health_data['components']['redis'] = {
                                'status': 'unhealthy',
                                'message': f'Redis ping failed: {str(e)[:200]}'
                            }
                            health_data['overall_status'] = 'degraded'
                    # Final fallback: direct TCP to localhost:6379
                    try:
                        with socket.create_connection(('127.0.0.1', 6379), timeout=1.0):
                            # If TCP open, try a ping
                            import redis  # type: ignore
                            url = 'redis://127.0.0.1:6379/0'
                            client3: Any = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
                            client3.ping()
                            health_data['components']['redis'] = {
                                'status': 'healthy',
                                'message': 'Redis connection active (localhost)',
                                'details': {'url': url}
                            }
                    except Exception:
                        pass
            else:
                health_data['components']['redis'] = {
                    'status': 'not_configured',
                    'message': 'Redis URL not configured'
                }
        except Exception as e:
            health_data['components']['redis'] = {
                'status': 'error',
                'message': f'Redis check failed: {str(e)[:200]}'
            }
        
        return jsonify(health_data)
        
    except Exception as e:
        current_app.logger.error(f"Comprehensive health check failed: {e}")
        return api_error("Health check failed", details={"reason": str(e)})


@dashboard_bp.route('/tool-registry-summary')
def tool_registry_summary():
    """Get tool registry summary for dashboard."""
    try:
        # Try to fetch analyzer-reported available tools per service (fast, best-effort)
        try:
            from app.services.analyzer_integration import get_available_toolsets  # type: ignore
            available_toolsets = get_available_toolsets() or {}
        except Exception:
            available_toolsets = {}
        
        # Use unified tool registry
        try:
            from app.engines.unified_registry import get_unified_tool_registry
            registry = get_unified_tool_registry()
            all_tools_detailed = registry.list_tools_detailed()
            
            # Convert to format expected by UI
            tools = []
            for idx, tool_data in enumerate(all_tools_detailed):
                tools.append({
                    'id': idx + 1,
                    'name': tool_data['name'],
                    'display_name': tool_data['display_name'],
                    'description': tool_data['description'],
                    'category': tool_data['container'],
                    'is_enabled': tool_data['available']
                })
            
            # Create profiles from containers
            summary = registry.info_summary()
            containers = summary.get('containers', {}) if isinstance(summary, dict) else {}
            if not isinstance(containers, dict):
                containers = {}
            profiles = []
            for idx, (container_name, tool_names) in enumerate(sorted(containers.items())):
                profiles.append({
                    'id': idx + 1,
                    'name': f"{container_name.replace('-', ' ').title()} Profile",
                    'description': f"Auto-generated profile for {container_name} tools"
                })
            
            # Create categories from containers
            categories = list(containers.keys())
            
            # Group tools by category (container)
            tools_by_category = {}
            for container_name in containers:
                tools_by_category[container_name] = [
                    tool for tool in tools if tool['category'] == container_name
                ]
        except Exception as e:
            return api_error(f"Unified tool registry error: {str(e)}")
        
        # Count tools by service
        tools_by_service = {}
        for tool in tools:
            service = tool.get('service_name', 'unknown')
            if service not in tools_by_service:
                tools_by_service[service] = []
            tools_by_service[service].append(tool)
        
        # Count enabled vs disabled tools
        enabled_tools = [t for t in tools if t.get('is_enabled', False)]
        disabled_tools = [t for t in tools if not t.get('is_enabled', True)]

        # Annotate availability from analyzer services
        def _normalize_service(name: str) -> str:
            mapping = {
                'static': 'static-analyzer',
                'security': 'static-analyzer',
                'static-analyzer': 'static-analyzer',
                'dynamic-analyzer': 'dynamic-analyzer',
                'performance-tester': 'performance-tester',
                'ai-analyzer': 'ai-analyzer',
            }
            return mapping.get((name or '').lower(), name or 'unknown')

        annotated_tools = []
        available_by_service: dict[str, int] = {}
        available_by_category: dict[str, int] = {}
        for t in tools:
            svc = _normalize_service(t.get('service_name', 'unknown'))
            raw_list = available_toolsets.get(svc, None)
            avail = set(x.lower() for x in (raw_list or []))
            tname = str(t.get('name', '')).lower()
            # Availability policy:
            # - If analyzer reported a non-empty list: use membership
            # - If analyzer explicitly reported empty list for service: treat as unavailable
            # - If analyzer provided no entry for the service (unknown): infer from registry enabled flag
            if raw_list is None:
                is_available = bool(t.get('is_enabled', True))
                availability_source = 'inferred'
            elif not avail:
                is_available = False
                availability_source = 'analyzer'
            else:
                is_available = tname in avail
                availability_source = 'analyzer'
            item = dict(t)
            item['available'] = is_available
            item['availability_source'] = availability_source
            annotated_tools.append(item)
            if is_available:
                available_by_service[svc] = available_by_service.get(svc, 0) + 1
                cat = t.get('category') or 'other'
                available_by_category[cat] = available_by_category.get(cat, 0) + 1
        
        return api_success({
            'summary': {
                'total_tools': len(tools),
                'enabled_tools': len(enabled_tools),
                'disabled_tools': len(disabled_tools),
                'total_profiles': len(profiles),
                'total_categories': len(categories),
                'available_tools_total': sum(available_by_service.values()) if available_by_service else 0
            },
            'tools_by_category': {cat: len(tools_list) for cat, tools_list in tools_by_category.items()},
            'tools_by_service': {svc: len(tools_list) for svc, tools_list in tools_by_service.items()},
            'available_by_service': available_by_service,
            'available_by_category': available_by_category,
            'recent_tools': annotated_tools[:5],  # First 5 tools as recent (with availability)
            'tools_annotated': annotated_tools,  # Full list with availability flag
            'builtin_profiles': [p for p in profiles if p.get('is_builtin', False)]
        })
        
    except Exception as e:
        current_app.logger.error(f"Tool registry summary failed: {e}")
        return api_error("Failed to get tool registry summary", details={"reason": str(e)})


@dashboard_bp.route('/analyzer-services')
def dashboard_analyzer_services():
    """Return analyzer services status cards."""
    try:
        services = [
            {'name': 'Security', 'status': 'healthy', 'version': '1.0'},
            {'name': 'Performance', 'status': 'healthy', 'version': '1.0'},
        ]
        cards = []
        for svc in services:
            cards.append(
                '<div class="col-md-3">'
                '<div class="card h-100 service-card">'
                '<div class="card-body py-2 px-3">'
                '<div class="d-flex justify-content-between align-items-center">'
                f'<strong class="small">{svc["name"]}</strong>'
                f'<span class="badge bg-{"success" if svc["status"]=="healthy" else "secondary"}">{svc["status"]}</span>'
                '</div>'
                f'<div class="small text-muted">v{svc.get("version") or "1.0"}</div>'
                '</div>'
                '</div>'
                '</div>'
            )
        return '<div class="row g-2">' + ''.join(cards) + '</div>'
    except Exception:
        current_app.logger.error("Analyzer services fragment failed", exc_info=True)
        return '<div class="text-muted small">Analyzer services unavailable</div>'


@dashboard_bp.route('/recent_activity')
def recent_activity():
    """HTMX endpoint for recent activity timeline."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        # Get recent activities (last 10 items)
        try:
            recent_security = db.session.query(SecurityAnalysis).order_by(db.desc(SecurityAnalysis.started_at)).limit(5).all()
        except Exception:
            recent_security = []
        try:
            recent_performance = db.session.query(PerformanceTest).order_by(db.desc(PerformanceTest.started_at)).limit(5).all()
        except Exception:
            recent_performance = []
        try:
            recent_batch = db.session.query(BatchAnalysis).order_by(db.desc(BatchAnalysis.created_at)).limit(5).all()
        except Exception:
            recent_batch = []

        activities = []

        # Add security activities
        for analysis in recent_security:
            if analysis.started_at:
                activities.append({
                    'type': 'security',
                    'description': 'Security analysis completed',
                    'timestamp': analysis.started_at,
                    'status': analysis.status.value if analysis.status else 'unknown'
                })

        # Add performance activities
        for test in recent_performance:
            if test.started_at:
                activities.append({
                    'type': 'performance',
                    'description': 'Performance test completed',
                    'timestamp': test.started_at,
                    'status': test.status.value if test.status else 'unknown'
                })

        # Add batch activities
        for batch in recent_batch:
            if batch.created_at:
                activities.append({
                    'type': 'batch',
                    'description': f'Batch analysis #{batch.id}',
                    'timestamp': batch.created_at,
                    'status': batch.status.value if batch.status else 'unknown'
                })

        # Sort by timestamp
        activities.sort(key=lambda x: x['timestamp'] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        activities = activities[:10]  # Keep only the 10 most recent

        if not activities:
            return '<div class="text-center py-3"><p class="text-muted">Unable to load activity</p></div>'
        try:
            return render_template('components/dashboard/activity-timeline.html', activities=activities)
        except Exception as _tpl_err:
            current_app.logger.warning(f"Activity timeline render failed: {_tpl_err}")
            return '<div class="text-center py-3"><p class="text-muted">No recent activity</p></div>'
    except Exception as e:
        current_app.logger.error(f"Error getting recent activity: {e}")
        from app.utils.template_paths import render_template_compat as render_template
        try:
            return render_template('components/dashboard/activity-timeline.html', activities=[])
        except Exception:
            return '<div class="text-center py-3"><p class="text-muted">No recent activity</p></div>'


@dashboard_bp.route('/actions/<string:action_name>', methods=['POST'])
def execute_action(action_name: str):
    """Execute a system action from the dashboard."""
    from app.services.system_service import execute_dashboard_action
    
    allowed_actions = [
        'clear_redis_cache',
        'rebuild_config_cache',
        'prune_celery_tasks'
    ]
    
    if action_name not in allowed_actions:
        return api_error('Invalid action specified', 400)
    
    try:
        result = execute_dashboard_action(action_name)
        if result.get('success'):
            return api_success(result, message=f"Action '{action_name}' executed successfully.")
        else:
            return api_error(result.get('error', 'Action failed'), details=result)
    except Exception as e:
        current_app.logger.error(f"Error executing dashboard action '{action_name}': {e}", exc_info=True)
        return api_error(f"Failed to execute action '{action_name}'", details={'reason': str(e)})


@dashboard_bp.route('/chart-data')
def dashboard_chart_data():
    """Provide time-series data for recent dashboard activity charts."""
    try:
        # Use the past 14 days for a compact yet informative view
        today = datetime.now(timezone.utc).date()
        day_span = 14

        labels: list[str] = []
        security_counts: list[int] = []
        performance_counts: list[int] = []
        app_counts: list[int] = []

        for delta in range(day_span - 1, -1, -1):
            day = today - timedelta(days=delta)
            day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)

            labels.append(day.strftime('%b %d'))

            security_counts.append(
                SecurityAnalysis.query
                .filter(SecurityAnalysis.created_at >= day_start)
                .filter(SecurityAnalysis.created_at < day_end)
                .count()
            )

            performance_counts.append(
                PerformanceTest.query
                .filter(PerformanceTest.started_at >= day_start)
                .filter(PerformanceTest.started_at < day_end)
                .count()
            )

            app_counts.append(
                GeneratedApplication.query
                .filter(GeneratedApplication.created_at >= day_start)
                .filter(GeneratedApplication.created_at < day_end)
                .count()
            )

        datasets = [
            {
                'label': 'Security Analyses',
                'data': security_counts,
                'borderColor': '#0d6efd',
                'backgroundColor': 'rgba(13,110,253,0.15)',
                'tension': 0.35,
                'fill': True,
            },
            {
                'label': 'Performance Tests',
                'data': performance_counts,
                'borderColor': '#20c997',
                'backgroundColor': 'rgba(32,201,151,0.15)',
                'tension': 0.35,
                'fill': True,
            },
            {
                'label': 'Generated Apps',
                'data': app_counts,
                'borderColor': '#ffc107',
                'backgroundColor': 'rgba(255,193,7,0.2)',
                'tension': 0.35,
                'fill': True,
            }
        ]

        return api_success({
            'labels': labels,
            'datasets': datasets
        })
    except Exception as exc:  # pragma: no cover - best-effort analytics endpoint
        current_app.logger.error(f"Failed to build dashboard chart data: {exc}", exc_info=True)
        return api_error('Unable to build chart data', details={'reason': str(exc)})


# =================================================================
# STATISTICS API ROUTES (moved from main api.py)
# =================================================================

@dashboard_bp.route('/stats/apps')
def api_stats_apps():
    data = get_application_statistics()
    return api_success(data, message="Application statistics fetched")


@dashboard_bp.route('/stats/models')
def api_stats_models():
    data = get_model_statistics()
    return api_success(data, message="Model statistics fetched")


@dashboard_bp.route('/stats/analysis')
def api_stats_analysis():
    data = get_analysis_statistics()
    return api_success(data, message="Analysis statistics fetched")


@dashboard_bp.route('/stats/recent')
def api_stats_recent():
    data = get_recent_statistics()
    return api_success(data, message="Recent statistics fetched")


@dashboard_bp.route('/models/distribution')
def api_models_distribution():
    data = get_model_distribution()
    return api_success(data, message="Model distribution fetched")


@dashboard_bp.route('/generation/trends')
def api_generation_trends():
    data = get_generation_trends()
    return api_success(data, message="Generation trends fetched")


@dashboard_bp.route('/analysis/summary')
def api_analysis_summary():
    data = get_analysis_summary()
    return api_success(data, message="Analysis summary fetched")


@dashboard_bp.route('/export')
def api_export_statistics():
    data = export_statistics()
    return api_success(data, message="Statistics exported")


@dashboard_bp.route('/statistics/generation/by-models', methods=['POST'])
def api_generation_stats_by_models():
    """Get generation statistics for specific models."""
    try:
        payload = request.get_json()
        if not payload or 'models' not in payload:
            return api_error("Missing 'models' field in request body", status=400)
        
        models = payload['models']
        if not isinstance(models, list) or not models:
            return api_error("'models' must be a non-empty list", status=400)
        
        data = get_generation_statistics_by_models(models)
        return api_success(data, message="Generation statistics fetched")
    except Exception as e:
        logger.exception("Failed to fetch generation statistics by models")
        return api_error(f"Failed to fetch generation statistics: {str(e)}", status=500)


@dashboard_bp.route('/statistics/wipe', methods=['POST'])
def api_wipe_statistics():
    """Wipe all statistics from the database (security, performance, ZAP, AI analyses)."""
    try:
        from app.models import (
            SecurityAnalysis, PerformanceTest, ZAPAnalysis, OpenRouterAnalysis,
            AnalysisTask, AnalysisResult, AnalysisResultsCache, SecurityFindingCache,
            PerformanceMetricCache, QualityIssueCache
        )
        
        deleted_count = 0
        
        # Delete all analysis records
        deleted_count += db.session.query(SecurityAnalysis).delete()
        deleted_count += db.session.query(PerformanceTest).delete()
        deleted_count += db.session.query(ZAPAnalysis).delete()
        deleted_count += db.session.query(OpenRouterAnalysis).delete()
        deleted_count += db.session.query(AnalysisTask).delete()
        deleted_count += db.session.query(AnalysisResult).delete()
        
        # Delete cached results
        deleted_count += db.session.query(AnalysisResultsCache).delete()
        deleted_count += db.session.query(SecurityFindingCache).delete()
        deleted_count += db.session.query(PerformanceMetricCache).delete()
        deleted_count += db.session.query(QualityIssueCache).delete()
        
        # Commit all deletions
        db.session.commit()
        
        logger.info(f"Successfully wiped {deleted_count} statistics records from database")
        
        return api_success(
            {'deleted_count': deleted_count},
            message=f"Successfully wiped {deleted_count} statistics records"
        )
        
    except Exception as e:
        db.session.rollback()
        logger.exception("Failed to wipe statistics from database")
        return api_error(f"Failed to wipe statistics: {str(e)}", status=500)