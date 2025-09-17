"""
Tool Registry Service
====================

Service for managing dynamic analysis tools, configurations, and profiles.
Provides CRUD operations and intelligent tool selection.
Enhanced to integrate with the new dynamic tool system.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from ..extensions import db
from ..models.tool_registry import (
    AnalysisTool, ToolConfiguration, AnalysisProfile, CustomAnalysisRequest
)
from ..models import GeneratedApplication
from ..constants import AnalysisStatus
from .service_base import NotFoundError, ValidationError

# Import new dynamic tool system
try:
    from ..engines import get_tool_registry
    DYNAMIC_TOOLS_AVAILABLE = True
except ImportError:
    DYNAMIC_TOOLS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ToolRegistryService:
    """Service for managing analysis tools and configurations."""
    
    def __init__(self):
        self._initialized = False
    
    def _ensure_initialized(self):
        """Ensure builtin tools and profiles are initialized (lazy loading)."""
        if not self._initialized:
            try:
                self._initialize_builtin_tools()
                self._initialize_builtin_profiles()
                self._initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize builtin tools/profiles: {e}")
    
    # ==========================================
    # Tool Management
    # ==========================================
    
    def get_all_tools(self, enabled_only: bool = True, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all available analysis tools from both database and dynamic registry."""
        self._ensure_initialized()
        
        # Get database tools
        query = AnalysisTool.query
        
        if enabled_only:
            query = query.filter(AnalysisTool.is_enabled)
        
        if category:
            query = query.filter(AnalysisTool.category == category)
        
        db_tools = query.order_by(AnalysisTool.category, AnalysisTool.name).all()
        tools = [tool.to_dict() for tool in db_tools]
        
        # Integrate dynamic tools if available
        if DYNAMIC_TOOLS_AVAILABLE:
            dynamic_tools = self._get_dynamic_tools(enabled_only=enabled_only, category=category)
            tools.extend(dynamic_tools)
        
        return tools
    
    def _get_dynamic_tools(self, enabled_only: bool = False, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tools from the new dynamic tool registry."""
        try:
            from ..engines import get_tool_registry
            
            # Ensure all engine modules are imported to register tools
            self._ensure_engines_imported()
            
            dynamic_registry = get_tool_registry()
            all_dynamic_tools = dynamic_registry.get_all_tools_info()
            
            tools = []
            for tool_name, tool_info in all_dynamic_tools.items():
                # Skip if tool is not available and we only want enabled tools
                if enabled_only and not tool_info.get('available', False):
                    continue
                
                # Map dynamic tool format to expected format
                tool_dict = self._convert_dynamic_tool_to_dict(tool_name, tool_info)
                
                # Filter by category if specified
                if category and tool_dict.get('category') != category:
                    continue
                
                tools.append(tool_dict)
                
            return tools
            
        except Exception as e:
            logger.warning(f"Failed to get dynamic tools: {e}")
            return []
    
    def _ensure_engines_imported(self):
        """Ensure all engine modules are imported to register tools."""
        try:
            # Import all engine modules to trigger tool registration
            import app.engines.backend_security  # noqa: F401
            import app.engines.frontend_security  # noqa: F401
            import app.engines.performance  # noqa: F401
            # Module imports trigger @analysis_tool decorators which register tools
        except ImportError as e:
            logger.warning(f"Failed to import some engine modules: {e}")
    
    def _convert_dynamic_tool_to_dict(self, tool_name: str, tool_info: Dict[str, Any]) -> Dict[str, Any]:
        """Convert dynamic tool info to expected dictionary format."""
        # Map tags to category
        tags = tool_info.get('tags', [])
        category = self._map_tags_to_category(tags)
        
        # Map tool to service
        service_name = self._map_tool_to_service(tool_name, tags)
        
        # Estimate duration based on tool type
        estimated_duration = self._estimate_tool_duration(tool_name, tags)
        
        return {
            'id': f"dynamic_{tool_name}",  # Prefix to avoid conflicts
            'name': tool_name,
            'display_name': tool_info.get('display_name', tool_name.title()),
            'description': tool_info.get('description', ''),
            'category': category,
            'service_name': service_name,
            'is_enabled': tool_info.get('available', False),
            'estimated_duration': estimated_duration,
            'execution_time_estimate': estimated_duration,
            'compatibility': list(tool_info.get('supported_languages', [])),
            'tags': tags,
            'version': tool_info.get('version'),
            'prerequisites': tool_info.get('prerequisites', []),
            'default_config': tool_info.get('config', {}),
            'source': 'dynamic'  # Mark as dynamic tool
        }
    
    def _map_tags_to_category(self, tags: List[str]) -> str:
        """Map tool tags to category."""
        tag_set = set(tag.lower() for tag in tags)
        
        if 'security' in tag_set:
            return 'security'
        elif 'performance' in tag_set:
            return 'performance'
        elif 'quality' in tag_set:
            return 'code_quality'
        elif 'dynamic' in tag_set:
            return 'dynamic_analysis'
        else:
            return 'other'
    
    def _map_tool_to_service(self, tool_name: str, tags: List[str]) -> str:
        """Map tool to analyzer service."""
        tag_set = set(tag.lower() for tag in tags)
        
        if 'performance' in tag_set:
            return 'performance-tester'
        elif 'dynamic' in tag_set or tool_name in ['zap', 'zap-baseline']:
            return 'dynamic-analyzer'
        elif 'security' in tag_set or 'quality' in tag_set:
            return 'static-analyzer'
        else:
            return 'static-analyzer'
    
    def _estimate_tool_duration(self, tool_name: str, tags: List[str]) -> int:
        """Estimate tool duration in seconds."""
        # Base estimates by tool type
        if 'performance' in tags:
            return 300  # 5 minutes for performance tests
        elif tool_name in ['bandit', 'safety']:
            return 60   # 1 minute for security scanners
        elif tool_name in ['pylint', 'eslint']:
            return 120  # 2 minutes for linters
        elif tool_name in ['npm-audit']:
            return 30   # 30 seconds for dependency checks
        else:
            return 180  # 3 minutes default
    
    def get_tools_by_category(self, enabled_only: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """Get tools grouped by category including dynamic tools."""
        self._ensure_initialized()
        tools = self.get_all_tools(enabled_only=enabled_only)
        categories = {}
        
        for tool in tools:
            category = tool['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(tool)
        
        # Ensure standard categories exist even if empty
        standard_categories = ['security', 'performance', 'code_quality', 'dynamic_analysis']
        for category in standard_categories:
            if category not in categories:
                categories[category] = []
        
        return categories
    
    def get_tool_categories(self) -> List[str]:
        """Get all unique tool categories."""
        self._ensure_initialized()
        categories = db.session.query(AnalysisTool.category).distinct().order_by(AnalysisTool.category).all()
        return [category[0] for category in categories if category[0]]
    
    def get_tools_by_service(self, enabled_only: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """Get tools grouped by analyzer service."""
        self._ensure_initialized()
        tools = self.get_all_tools(enabled_only=enabled_only)
        services = {}
        
        for tool in tools:
            # Align with model's field name 'service_name'
            service = tool.get('service_name') or tool.get('analyzer_service')
            if service not in services:
                services[service] = []
            services[service].append(tool)
        
        return services
    
    def get_compatible_tools(self, technologies: List[str], enabled_only: bool = True) -> List[Dict[str, Any]]:
        """Get tools compatible with specified technologies."""
        self._ensure_initialized()
        tools = self.get_all_tools(enabled_only=enabled_only)
        compatible = []
        
        for tool in tools:
            tool_techs = tool.get('compatibility', [])
            if any(tech.lower() in [t.lower() for t in tool_techs] for tech in technologies):
                compatible.append(tool)
        
        return compatible
    
    def get_tool(self, tool_id: int) -> Dict[str, Any]:
        """Get a specific tool by ID."""
        self._ensure_initialized()
        tool = AnalysisTool.query.get_or_404(tool_id)
        return tool.to_dict()
    
    def get_tool_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a tool by name."""
        self._ensure_initialized()
        tool = AnalysisTool.query.filter_by(name=name).first()
        return tool.to_dict() if tool else None
    
    def create_tool(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new analysis tool."""
        self._ensure_initialized()
        
        # Validate required fields
        required_fields = ['name', 'category', 'service_name']
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Check for duplicate name
        existing = AnalysisTool.query.filter_by(name=data['name']).first()
        if existing:
            raise ValidationError(f"Tool with name '{data['name']}' already exists")
        
        # Create tool
        tool = AnalysisTool()
        tool.name = data['name']
        tool.display_name = data.get('display_name', data['name'])
        tool.category = data['category']
        tool.service_name = data['service_name']
        tool.description = data.get('description', '')
        tool.command = data.get('command', '')
        tool.compatibility = data.get('compatibility', [])
        tool.is_enabled = data.get('is_enabled', True)
        tool.requires_config = data.get('requires_config', False)
        # Optional JSON/int fields via setattr to appease type checkers
        for k in ['default_config', 'config_schema', 'estimated_duration', 'resource_intensive']:
            if k in data:
                setattr(tool, k, data[k])
        
        db.session.add(tool)
        db.session.commit()
        
        logger.info(f"Created analysis tool: {tool.name}")
        return tool.to_dict()
    
    def update_tool(self, tool_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing tool."""
        self._ensure_initialized()
        tool = AnalysisTool.query.get_or_404(tool_id)
        
        # Update fields
        updatable_fields = [
            'display_name', 'description', 'is_enabled', 'command',
            'compatibility', 'requires_config', 'default_config',
            'config_schema', 'estimated_duration', 'resource_intensive',
            'service_name'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(tool, field, data[field])
        
        tool.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        logger.info(f"Updated analysis tool: {tool.name}")
        return tool.to_dict()
    
    # ==========================================
    # Tool Configuration Management
    # ==========================================
    
    def get_tool_configurations(self, tool_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get tool configurations, optionally filtered by tool."""
        self._ensure_initialized()
        query = ToolConfiguration.query
        if tool_id:
            query = query.filter_by(tool_id=tool_id)
        
        configs = query.order_by(ToolConfiguration.name).all()
        return [config.to_dict() for config in configs]
    
    def create_tool_configuration(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tool configuration."""
        self._ensure_initialized()
        
        # Validate required fields
        required_fields = ['name', 'tool_id']
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Verify tool exists
        tool = AnalysisTool.query.get(data['tool_id'])
        if not tool:
            raise NotFoundError(f"Tool with ID {data['tool_id']} not found")
        
        # Create configuration
        config = ToolConfiguration()
        config.name = data['name']
        config.tool_id = data['tool_id']
        config.description = data.get('description', '')
        config.is_default = data.get('is_default', False)
        
        if 'configuration' in data:
            config.configuration = data['configuration']
        
        db.session.add(config)
        db.session.commit()
        
        logger.info(f"Created tool configuration: {config.name} for tool {tool.name}")
        return config.to_dict()
    
    # ==========================================
    # Analysis Profile Management
    # ==========================================
    
    def get_analysis_profiles(self, include_builtin: bool = True) -> List[Dict[str, Any]]:
        """Get all analysis profiles."""
        self._ensure_initialized()
        query = AnalysisProfile.query
        
        if not include_builtin:
            query = query.filter(~AnalysisProfile.is_builtin)
        
        profiles = query.order_by(AnalysisProfile.name).all()
        return [profile.to_dict() for profile in profiles]
    
    def get_analysis_profile(self, profile_id: int) -> Dict[str, Any]:
        """Get a specific analysis profile."""
        self._ensure_initialized()
        profile = AnalysisProfile.query.get_or_404(profile_id)
        return profile.to_dict()
    
    def get_analysis_profile_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get an analysis profile by name."""
        self._ensure_initialized()
        profile = AnalysisProfile.query.filter_by(name=name).first()
        return profile.to_dict() if profile else None
    
    def create_analysis_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new analysis profile."""
        self._ensure_initialized()
        
        # Validate required fields
        required_fields = ['name']
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Check for duplicate name
        existing = AnalysisProfile.query.filter_by(name=data['name']).first()
        if existing:
            raise ValidationError(f"Profile with name '{data['name']}' already exists")
        
        # Create profile
        profile = AnalysisProfile()
        profile.name = data['name']
        profile.display_name = data.get('display_name', data['name'])
        profile.description = data.get('description', '')
        profile.is_builtin = data.get('is_builtin', False)

        # Optionally attach tools by creating default ToolConfiguration entries
        tool_ids = data.get('tool_ids') or []
        if isinstance(tool_ids, list) and tool_ids:
            tools = AnalysisTool.query.filter(AnalysisTool.id.in_(tool_ids)).all()
            if len(tools) != len(tool_ids):
                raise ValidationError("One or more tool IDs are invalid")
            for tool in tools:
                cfg = ToolConfiguration()
                setattr(cfg, 'name', f"Default for {tool.name}")
                setattr(cfg, 'tool_id', tool.id)
                setattr(cfg, 'configuration', tool.default_config or {})
                setattr(cfg, 'is_default', True)
                profile.tool_configurations.append(cfg)
        
        db.session.add(profile)
        db.session.commit()
        
        logger.info(f"Created analysis profile: {profile.name} with {len(profile.tool_configurations or [])} tool configs")
        return profile.to_dict()
    
    # ==========================================
    # Custom Analysis Management
    # ==========================================
    
    def create_custom_analysis(self, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Create a new custom analysis request."""
        self._ensure_initialized()
        
        # Merge data and kwargs
        if data is None:
            data = {}
        data.update(kwargs)
        
        # Validate required fields
        required_fields = ['model_slug', 'app_number']
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate model and app exist
        app = GeneratedApplication.query.filter_by(
            model_slug=data['model_slug'],
            app_number=data['app_number']
        ).first()
        
        if not app:
            raise NotFoundError(
                f"Application not found: {data['model_slug']} app {data['app_number']}"
            )
        
        # Validate analysis mode
        analysis_mode = data.get('analysis_mode', 'custom')
        if analysis_mode not in ['profile', 'custom']:
            raise ValidationError("analysis_mode must be 'profile' or 'custom'")
        
        # Validate mode-specific requirements and normalize to model fields
        custom_tools_payload: List[Dict[str, Any]] | None = None
        if analysis_mode == 'profile':
            if 'profile_id' not in data:
                raise ValidationError("profile_id is required for profile mode")
            profile = AnalysisProfile.query.get(data['profile_id'])
            if not profile:
                raise NotFoundError(f"Profile with ID {data['profile_id']} not found")
        else:  # custom mode
            tool_ids = data.get('tool_ids') or []
            if not isinstance(tool_ids, list) or not tool_ids:
                raise ValidationError("tool_ids is required for custom mode")
            # Validate tool IDs
            tools = AnalysisTool.query.filter(AnalysisTool.id.in_(tool_ids)).all()
            if len(tools) != len(tool_ids):
                raise ValidationError("One or more tool IDs are invalid")
            # Build custom_tools list respecting optional per-tool configs
            per_tool_cfg: Dict[str, Any] = data.get('tool_configurations') or {}
            custom_tools_payload = []
            for tid in tool_ids:
                cfg = per_tool_cfg.get(str(tid)) or per_tool_cfg.get(tid) or {}
                custom_tools_payload.append({'tool_id': int(tid), 'configuration': cfg})
        
        # Create custom analysis request
        request = CustomAnalysisRequest()
        # Required descriptor
        req_name = data.get('request_name')
        if not req_name:
            from datetime import datetime, timezone
            ts = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
            req_name = f"{data['model_slug']}_app{data['app_number']}_{analysis_mode}_{ts}"
        setattr(request, 'request_name', str(req_name)[:200])
        request.model_slug = data['model_slug']
        request.app_number = data['app_number']
        # Store custom tools or profile
        if analysis_mode == 'profile':
            request.profile_id = data['profile_id']
        else:
            setattr(request, 'custom_tools', custom_tools_payload or [])
        # Core fields
        request.priority = data.get('priority', 'normal')
        # Keep status as string to match model column type
        setattr(request, 'status', AnalysisStatus.PENDING.value if hasattr(AnalysisStatus.PENDING, 'value') else 'pending')
        request.priority = data.get('priority', 'normal')
        # Optional: timeout and notifications
        if 'timeout_seconds' in data:
            try:
                setattr(request, 'timeout_seconds', int(data['timeout_seconds']))
            except Exception:
                pass
        if 'notification_settings' in data:
            setattr(request, 'notification_settings', data.get('notification_settings'))
        
        db.session.add(request)
        db.session.commit()
        
        logger.info(
            f"Created custom analysis request {request.id}: "
            f"{data['model_slug']} app {data['app_number']} in {analysis_mode} mode"
        )
        
        return request.to_dict()
    
    def get_custom_analysis(self, analysis_id: int) -> Dict[str, Any]:
        """Get a custom analysis request by ID."""
        self._ensure_initialized()
        request = CustomAnalysisRequest.query.get_or_404(analysis_id)
        return request.to_dict()
    
    def get_analysis_execution_plan(self, analysis_id: int) -> Dict[str, Any]:
        """Get execution plan for a custom analysis."""
        self._ensure_initialized()
        request = CustomAnalysisRequest.query.get_or_404(analysis_id)

        # Resolve tool IDs based on profile or custom selection
        tool_ids: List[int] = []
        if request.profile_id:
            profile = AnalysisProfile.query.get(request.profile_id)
            if not profile:
                raise NotFoundError(f"Profile {request.profile_id} not found")
            # Gather tool_ids from linked tool_configurations
            for tc in (profile.tool_configurations or []):
                if getattr(tc, 'tool_id', None):
                    tool_ids.append(tc.tool_id)
        else:
            for entry in (request.custom_tools or []):
                tid = (entry or {}).get('tool_id')
                if isinstance(tid, int):
                    tool_ids.append(tid)

        # Get tools and group by service_name
        tools = AnalysisTool.query.filter(AnalysisTool.id.in_(tool_ids)).all()
        execution_plan = {
            'analysis_id': analysis_id,
            'model_slug': request.model_slug,
            'app_number': request.app_number,
            'total_tools': len(tools),
            'services': {}
        }
        
        for tool in tools:
            service = tool.service_name
            if service not in execution_plan['services']:
                execution_plan['services'][service] = {
                    'service_name': service,
                    'tools': [],
                    'estimated_duration': 0
                }
            
            execution_plan['services'][service]['tools'].append({
                'id': tool.id,
                'name': tool.name,
                'category': tool.category,
                'timeout': tool.estimated_duration or 0
            })
            if tool.estimated_duration:
                execution_plan['services'][service]['estimated_duration'] += int(tool.estimated_duration)
        
        return execution_plan
    
    # ==========================================
    # Recommendation Engine
    # ==========================================
    
    def get_recommended_tools(
        self, 
        model_slug: str, 
        app_number: int,
        analysis_goals: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get recommended tools for a specific application."""
        self._ensure_initialized()
        
        # Get application info
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        if not app:
            raise NotFoundError(f"Application not found: {model_slug} app {app_number}")
        
        # Determine technologies
        technologies = []
        if app.has_backend:
            if app.backend_framework:
                technologies.append(app.backend_framework)
            technologies.append('backend')
        
        if app.has_frontend:
            if app.frontend_framework:
                technologies.append(app.frontend_framework)
            technologies.append('frontend')
        
        if app.has_docker_compose:
            technologies.append('docker')
        
        # Get compatible tools
        all_tools = self.get_all_tools(enabled_only=True)
        recommended = {
            'security': [],
            'performance': [],
            'quality': [],
            'ai_analysis': []
        }
        
        for tool in all_tools:
            tool_techs = tool.get('compatibility', [])
            
            # Check technology compatibility
            is_compatible = not technologies or any(
                tech.lower() in [t.lower() for t in tool_techs] for tech in technologies
            )
            
            if is_compatible:
                category = tool['category']
                if category in recommended:
                    recommended[category].append(tool)
        
        # Sort by relevance (builtin tools first, then by name)
        for category in recommended:
            recommended[category].sort(key=lambda t: (not t['is_builtin'], t['name']))
        
        return {
            'model_slug': model_slug,
            'app_number': app_number,
            'detected_technologies': technologies,
            'recommended_tools': recommended,
            'total_recommendations': sum(len(tools) for tools in recommended.values())
        }
    
    # ==========================================
    # Initialization Methods
    # ==========================================
    
    def _initialize_builtin_tools(self):
        """Initialize builtin analysis tools."""
        builtin_tools = [
            {
                'name': 'bandit',
                'display_name': 'Bandit Security Scanner',
                'category': 'security',
                'service_name': 'static-analyzer',
                'description': 'Security linter for Python code',
                'command': 'bandit -r {source_path} -f json',
                'compatibility': ['python', 'backend'],
                'is_enabled': True,
                'estimated_duration': 120,
                'default_config': {
                    'format': 'json',
                    'recursive': True,
                    'exclude_dirs': ['tests', '__pycache__']
                }
            },
            {
                'name': 'pylint',
                'display_name': 'Pylint Code Quality',
                'category': 'quality',
                'service_name': 'static-analyzer',
                'description': 'Code quality checker for Python',
                'command': 'pylint {source_path} --output-format=json',
                'compatibility': ['python', 'backend'],
                'is_enabled': True,
                'estimated_duration': 180,
                'default_config': {
                    'output_format': 'json',
                    'disable': ['C0103', 'C0111']
                }
            },
            {
                'name': 'eslint',
                'display_name': 'ESLint JavaScript Linter',
                'category': 'quality',
                'service_name': 'static-analyzer',
                'description': 'JavaScript/TypeScript linter',
                'command': 'eslint {source_path} --format json',
                'compatibility': ['javascript', 'typescript', 'frontend'],
                'is_enabled': True,
                'estimated_duration': 90,
                'default_config': {
                    'format': 'json',
                    'ext': ['.js', '.jsx', '.ts', '.tsx']
                }
            },
            {
                'name': 'zap-baseline',
                'display_name': 'OWASP ZAP Baseline',
                'category': 'security',
                'service_name': 'dynamic-analyzer',
                'description': 'OWASP ZAP baseline security scan',
                'command': 'zap-baseline.py -t {target_url} -J {output_file}',
                'compatibility': ['web', 'api', 'backend', 'frontend'],
                'is_enabled': True,
                'estimated_duration': 300,
                'default_config': {
                    'format': 'json',
                    'passive_scan': True,
                    'spider_scan': True
                }
            },
            {
                'name': 'locust-performance',
                'display_name': 'Locust Load Testing',
                'category': 'performance',
                'service_name': 'performance-tester',
                'description': 'Load testing with Locust',
                'command': 'locust --host {target_url} --users {users} --spawn-rate {spawn_rate} --run-time {duration}',
                'compatibility': ['web', 'api', 'backend'],
                'is_enabled': True,
                'estimated_duration': 600,
                'default_config': {
                    'users': 10,
                    'spawn_rate': 2,
                    'duration': '60s'
                }
            },
            {
                'name': 'ai-code-review',
                'display_name': 'AI Code Review',
                'category': 'ai_analysis',
                'service_name': 'ai-analyzer',
                'description': 'AI-powered code review and suggestions',
                'command': 'ai-analyze --source {source_path} --model {ai_model} --type code-review',
                'compatibility': ['python', 'javascript', 'typescript', 'backend', 'frontend'],
                'is_enabled': True,
                'estimated_duration': 240,
                'default_config': {
                    'analysis_depth': 'standard',
                    'include_suggestions': True,
                    'focus_areas': ['security', 'performance', 'maintainability']
                }
            }
        ]
        
        for tool_data in builtin_tools:
            existing = AnalysisTool.query.filter_by(name=tool_data['name']).first()
            if not existing:
                tool = AnalysisTool()
                for key, value in tool_data.items():
                    if key == 'default_configuration':
                        tool.default_config = value
                    elif hasattr(tool, key):
                        setattr(tool, key, value)
                
                db.session.add(tool)
                logger.info(f"Initialized builtin tool: {tool.name}")
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to initialize builtin tools: {e}")
    
    def _initialize_builtin_profiles(self):
        """Initialize builtin analysis profiles."""
        # Get tool IDs for profile creation
        tools = {tool.name: tool.id for tool in AnalysisTool.query.all()}
        
        builtin_profiles = [
            {
                'name': 'Security Focus',
                'display_name': 'Security Focus Profile',
                'description': 'Comprehensive security analysis',
                'tool_ids': [tools.get('bandit'), tools.get('zap-baseline')],
                'is_builtin': True
            },
            {
                'name': 'Quality Assurance', 
                'display_name': 'Quality Assurance Profile',
                'description': 'Code quality and standards checking',
                'tool_ids': [tools.get('pylint'), tools.get('eslint')],
                'is_builtin': True
            },
            {
                'name': 'Performance Testing',
                'display_name': 'Performance Testing Profile',
                'description': 'Load and performance testing',
                'tool_ids': [tools.get('locust-performance')],
                'is_builtin': True
            },
            {
                'name': 'Full Analysis',
                'display_name': 'Full Analysis Profile',
                'description': 'Comprehensive analysis with all tools',
                'tool_ids': list(tools.values()),
                'is_builtin': True
            }
        ]
        
        for profile_data in builtin_profiles:
            # Filter out None tool IDs
            profile_data['tool_ids'] = [tid for tid in profile_data['tool_ids'] if tid is not None]
            
            if not profile_data['tool_ids']:
                logger.warning(f"Skipping profile '{profile_data['name']}' - no valid tools found")
                continue
            
            existing = AnalysisProfile.query.filter_by(name=profile_data['name']).first()
            if not existing:
                profile = AnalysisProfile()
                for key, value in profile_data.items():
                    if key == 'profile_configuration':
                        # Skip this field as the model doesn't have it or use a different field
                        continue
                    elif hasattr(profile, key):
                        setattr(profile, key, value)
                
                db.session.add(profile)
                logger.info(f"Initialized builtin profile: {profile.name}")
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to initialize builtin profiles: {e}")


# Global service instance
tool_registry_service = ToolRegistryService()