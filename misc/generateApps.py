#!/usr/bin/env python3
"""
Multi-Model Project Generator for OpenRouter AI Models

This script creates containerized web applications for multiple AI models,
organizing them in a structured directory hierarchy with proper port management.

Author: AI Model Management System
Version: 2.0
"""

import os
import shutil
import json
import datetime
import urllib.parse
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import logging


class Config:
    """Global configuration settings"""
    
    # Project paths
    DEFAULT_BASE_PATH = os.getcwd()
    MODELS_DIR = "models"
    LOGS_DIR = "_logs"
    TEMPLATES_DIR = "z_code_templates"
    
    # Port configuration
    BASE_BACKEND_PORT = 5001
    BASE_FRONTEND_PORT = 8001
    PORTS_PER_APP = 2
    BUFFER_PORTS = 10
    APPS_PER_MODEL = 30
    
    # Docker images
    PYTHON_BASE_IMAGE = "python:3.14-slim"
    
    # Provider color mappings
    PROVIDER_COLORS = {
        "mistralai": "#8B5CF6",      # Purple-500
        "moonshotai": "#10B981",     # Emerald-500
        "deepseek": "#9333EA",       # Purple-600
        "sarvamai": "#DC2626",       # Red-600
        "google": "#3B82F6",         # Blue-500
        "meta-llama": "#F59E0B",     # Amber-500
        "microsoft": "#6366F1",      # Indigo-500
        "opengvlab": "#6B7280",      # Gray-500
        "qwen": "#F43F5E",           # Rose-500
        "nvidia": "#0D9488",         # Teal-600
        "anthropic": "#D97706",      # Amber-600
        "x-ai": "#B91C1C",           # Red-700
        "minimax": "#7E22CE",        # Purple-700
        "openai": "#14B8A6",         # Teal-500
        "agentica-org": "#16A34A",   # Green-600
        "nousresearch": "#059669",   # Emerald-700
    }


class Logger:
    """Centralized logging utility"""
    
    @staticmethod
    def setup_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
        """Setup a logger with both file and console handlers"""
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger


class ModelExtractor:
    """Extracts and processes AI models from OpenRouter URLs or strings"""
    
    @staticmethod
    def extract_from_url(openrouter_url: str) -> List[str]:
        """Extract model names from OpenRouter URL"""
        try:
            parsed_url = urllib.parse.urlparse(openrouter_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            if 'models' not in query_params:
                raise ValueError("No 'models' parameter found in URL")
            
            models_param = query_params['models'][0]
            return ModelExtractor._process_model_string(models_param)
            
        except Exception as e:
            raise ValueError(f"Error extracting models from URL: {e}")

    @staticmethod
    def extract_from_string(models_string: str) -> List[str]:
        """Extract model names from comma-separated string"""
        try:
            return ModelExtractor._process_model_string(models_string)
        except Exception as e:
            raise ValueError(f"Error extracting models from string: {e}")

    @staticmethod
    def _process_model_string(models_string: str) -> List[str]:
        """Process raw model string into clean model names"""
        raw_models = [model.strip() for model in models_string.split(',')]
        processed_models = []
        
        for model in raw_models:
            if not model:
                continue
            
            # Remove :free suffix and replace / with _
            clean_model = model.replace(':free', '').replace('/', '_')
            processed_models.append(clean_model)
        
        return processed_models

    @staticmethod
    def generate_color_mapping(models: List[str]) -> Dict[str, str]:
        """Generate color mapping for models based on their providers"""
        color_mapping = {}
        
        for model in models:
            provider = model.split('_')[0] if '_' in model else model
            color = Config.PROVIDER_COLORS.get(provider, "#666666")
            color_mapping[model] = f"`{color}`"
        
        return color_mapping

    @classmethod
    def parse_input(cls, input_string: str) -> Tuple[List[str], Dict[str, str]]:
        """Parse input (URL or model string) and return models and colors"""
        if not input_string.strip():
            raise ValueError("Input string is empty")
        
        # Determine input type and extract models
        if input_string.startswith('http'):
            print("Detected URL input, extracting models...")
            models = cls.extract_from_url(input_string)
        else:
            print("Detected string input, parsing models...")
            models = cls.extract_from_string(input_string)
        
        if not models:
            raise ValueError("No models found in input")
        
        # Generate color mapping
        colors = cls.generate_color_mapping(models)
        
        print(f"Extracted {len(models)} models:")
        for i, model in enumerate(models, 1):
            print(f"  {i:2d}. {model}")
        
        return models, colors


class PortManager:
    """Manages port allocation across all models"""
    
    @staticmethod
    def calculate_port_range(model_index: int) -> Tuple[int, int]:
        """Calculate port ranges for a specific model index"""
        ports_needed_per_model = Config.APPS_PER_MODEL * Config.PORTS_PER_APP + Config.BUFFER_PORTS
        
        backend_start = Config.BASE_BACKEND_PORT + (model_index * ports_needed_per_model)
        frontend_start = Config.BASE_FRONTEND_PORT + (model_index * ports_needed_per_model)
        
        return backend_start, frontend_start

    @staticmethod
    def get_app_ports(model_index: int, app_number: int) -> Dict[str, int]:
        """Get specific ports for an app within a model (1-based app numbering)"""
        backend_base, frontend_base = PortManager.calculate_port_range(model_index)
        offset = (app_number - 1) * Config.PORTS_PER_APP
        
        return {
            'backend': backend_base + offset,
            'frontend': frontend_base + offset
        }


class ProjectStructure:
    """Manages project directory structure and file operations"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.models_dir = self.base_path / Config.MODELS_DIR
        self.logs_dir = self.models_dir / Config.LOGS_DIR
        self.templates_dir = Path(__file__).parent / Config.TEMPLATES_DIR
        
    def ensure_directories(self):
        """Ensure all required directories exist"""
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
    def get_model_dir(self, model_name: str) -> Path:
        """Get the directory path for a specific model"""
        return self.models_dir / model_name
        
    def get_log_file(self, model_name: str) -> Path:
        """Get the log file path for a specific model"""
        sanitized_name = "".join(c if c.isalnum() else "_" for c in model_name)
        return self.logs_dir / f"setup_{sanitized_name}.log"
        
    def validate_templates(self) -> bool:
        """Validate that all required templates exist"""
        required_templates = [
            "backend/app.py.template",
            "backend/requirements.txt",
            "backend/Dockerfile.template",
            "frontend/package.json.template",
            "frontend/vite.config.js.template",
            "frontend/src/App.jsx.template",
            "frontend/src/App.css",
            "frontend/index.html.template",
            "frontend/Dockerfile.template",
            "docker-compose.yml.template"
        ]
        
        missing_templates = []
        for template in required_templates:
            if not (self.templates_dir / template).exists():
                missing_templates.append(template)
        
        if missing_templates:
            print(f"Missing templates: {missing_templates}")
            return False
        
        return True


class TemplateProcessor:
    """Handles template file processing and substitution"""
    
    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        
    def process_template(self, template_path: str, target_path: Path, 
                        substitutions: Dict[str, str]) -> bool:
        """Process a template file with substitutions"""
        try:
            template_file = self.templates_dir / template_path
            
            if not template_file.exists():
                print(f"Warning: Template not found: {template_file}")
                return False
            
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Apply substitutions
            for key, value in substitutions.items():
                content = content.replace(f"{{{key}}}", str(value))
            
            # Ensure target directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            print(f"Error processing template {template_path}: {e}")
            return False
    
    def copy_file(self, source_path: str, target_path: Path) -> bool:
        """Copy a file from templates to target location"""
        try:
            source_file = self.templates_dir / source_path
            
            if not source_file.exists():
                print(f"Warning: Source file not found: {source_file}")
                return False
            
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_path)
            return True
            
        except Exception as e:
            print(f"Error copying file {source_path}: {e}")
            return False


class ApplicationBuilder:
    """Builds individual applications (backend, frontend, docker-compose)"""
    
    def __init__(self, template_processor: TemplateProcessor, logger: logging.Logger):
        self.template_processor = template_processor
        self.logger = logger
        
    def build_backend(self, backend_dir: Path, model_name: str, port: int) -> bool:
        """Build backend application"""
        try:
            substitutions = {
                'model_name': model_name,
                'port': port,
                'python_base_image': Config.PYTHON_BASE_IMAGE
            }
            
            success = True
            success &= self.template_processor.process_template(
                "backend/app.py.template", 
                backend_dir / "app.py", 
                substitutions
            )
            success &= self.template_processor.copy_file(
                "backend/requirements.txt", 
                backend_dir / "requirements.txt"
            )
            success &= self.template_processor.process_template(
                "backend/Dockerfile.template", 
                backend_dir / "Dockerfile", 
                substitutions
            )
            
            if success:
                self.logger.info(f"Backend created successfully for {model_name}")
            else:
                self.logger.error(f"Failed to create backend for {model_name}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error building backend for {model_name}: {e}")
            return False
    
    def build_frontend(self, frontend_dir: Path, model_name: str, 
                      frontend_port: int, backend_port: int) -> bool:
        """Build frontend application"""
        try:
            sanitized_model = "".join(c if c.isalnum() or c == '-' else '_' 
                                    for c in model_name.lower())
            
            substitutions = {
                'model_name': model_name,
                'model_name_lower': sanitized_model,
                'port': frontend_port,
                'backend_port': backend_port,
                'backend_port_for_proxy': backend_port,
            }
            
            success = True
            success &= self.template_processor.process_template(
                "frontend/package.json.template",
                frontend_dir / "package.json",
                substitutions
            )
            success &= self.template_processor.process_template(
                "frontend/vite.config.js.template",
                frontend_dir / "vite.config.js",
                substitutions
            )
            success &= self.template_processor.process_template(
                "frontend/src/App.jsx.template",
                frontend_dir / "src" / "App.jsx",
                substitutions
            )
            success &= self.template_processor.copy_file(
                "frontend/src/App.css",
                frontend_dir / "src" / "App.css"
            )
            success &= self.template_processor.process_template(
                "frontend/index.html.template",
                frontend_dir / "index.html",
                substitutions
            )
            success &= self.template_processor.process_template(
                "frontend/Dockerfile.template",
                frontend_dir / "Dockerfile",
                substitutions
            )
            
            if success:
                self.logger.info(f"Frontend created successfully for {model_name}")
            else:
                self.logger.error(f"Failed to create frontend for {model_name}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error building frontend for {model_name}: {e}")
            return False
    
    def build_docker_compose(self, project_dir: Path, service_prefix: str,
                           backend_port: int, frontend_port: int) -> bool:
        """Build docker-compose configuration"""
        try:
            substitutions = {
                'service_prefix': service_prefix,
                'host_backend_port': backend_port,
                'host_frontend_port': frontend_port,
                'backend_port': backend_port,  # Backward compatibility
                'frontend_port': frontend_port,  # Backward compatibility
                'model_prefix': service_prefix  # Backward compatibility
            }
            
            success = self.template_processor.process_template(
                "docker-compose.yml.template",
                project_dir / "docker-compose.yml",
                substitutions
            )
            
            if success:
                self.logger.info(f"Docker compose created for {service_prefix}")
            else:
                self.logger.error(f"Failed to create docker compose for {service_prefix}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error building docker compose for {service_prefix}: {e}")
            return False


class ModelManager:
    """Main manager for handling multiple models and their applications"""
    
    def __init__(self, base_path: str = Config.DEFAULT_BASE_PATH):
        self.structure = ProjectStructure(base_path)
        self.structure.ensure_directories()
        
        # Setup main logger
        main_log_file = self.structure.logs_dir / "main.log"
        self.logger = Logger.setup_logger("ModelManager", str(main_log_file))
        
        self.template_processor = TemplateProcessor(self.structure.templates_dir)
        self.app_builder = ApplicationBuilder(self.template_processor, self.logger)
        
        self.models: List[str] = []
        self.model_colors: Dict[str, str] = {}
        
    def validate_setup(self) -> bool:
        """Validate that the system is properly set up"""
        if not self.structure.validate_templates():
            self.logger.error("Template validation failed")
            return False
        
        self.logger.info("System validation passed")
        return True
        
    def load_models(self, input_string: str) -> bool:
        """Load models from input string or URL"""
        try:
            self.models, self.model_colors = ModelExtractor.parse_input(input_string)
            self.logger.info(f"Loaded {len(self.models)} models")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load models: {e}")
            return False
    
    def create_model_applications(self, model_name: str, model_index: int) -> bool:
        """Create all applications for a single model"""
        model_logger = Logger.setup_logger(
            f"Model_{model_name}",
            str(self.structure.get_log_file(model_name))
        )
        
        try:
            model_dir = self.structure.get_model_dir(model_name)
            model_dir.mkdir(parents=True, exist_ok=True)
            
            model_logger.info(f"Creating applications for model: {model_name}")
            
            success_count = 0
            total_apps = Config.APPS_PER_MODEL
            
            for app_num in range(1, total_apps + 1):
                app_dir = model_dir / f"app{app_num}"
                ports = PortManager.get_app_ports(model_index, app_num)
                
                # Create service prefix for docker compose
                sanitized_model = "".join(c if c.isalnum() else "_" 
                                        for c in model_name.lower())
                service_prefix = f"{sanitized_model}_app{app_num}"
                
                # Build application components
                app_success = True
                app_success &= self.app_builder.build_backend(
                    app_dir / "backend", model_name, ports['backend']
                )
                app_success &= self.app_builder.build_frontend(
                    app_dir / "frontend", model_name, 
                    ports['frontend'], ports['backend']
                )
                app_success &= self.app_builder.build_docker_compose(
                    app_dir, service_prefix, ports['backend'], ports['frontend']
                )
                
                if app_success:
                    success_count += 1
                    model_logger.info(
                        f"App {app_num} created successfully "
                        f"(Backend: {ports['backend']}, Frontend: {ports['frontend']})"
                    )
                else:
                    model_logger.error(f"Failed to create app {app_num}")
            
            model_logger.info(
                f"Model {model_name} completed: {success_count}/{total_apps} apps created"
            )
            
            return success_count == total_apps
            
        except Exception as e:
            model_logger.error(f"Critical error creating model {model_name}: {e}")
            return False
    
    def create_all_models(self) -> bool:
        """Create applications for all loaded models"""
        if not self.models:
            self.logger.error("No models loaded")
            return False
        
        self.logger.info(f"Starting creation of {len(self.models)} models")
        
        successful_models = 0
        
        for model_index, model_name in enumerate(self.models):
            print(f"\nProcessing model {model_index + 1}/{len(self.models)}: {model_name}")
            
            if self.create_model_applications(model_name, model_index):
                successful_models += 1
                print(f"✅ {model_name} completed successfully")
            else:
                print(f"❌ {model_name} failed")
        
        self.logger.info(
            f"Model creation completed: {successful_models}/{len(self.models)} successful"
        )
        
        return successful_models == len(self.models)
    
    def generate_configuration_files(self) -> bool:
        """Generate JSON configuration files"""
        try:
            # Generate port configuration
            ports_data = []
            
            for model_index, model_name in enumerate(self.models):
                for app_num in range(1, Config.APPS_PER_MODEL + 1):
                    ports = PortManager.get_app_ports(model_index, app_num)
                    
                    ports_data.append({
                        "model_name": model_name,
                        "app_number": app_num,
                        "backend_port": ports['backend'],
                        "frontend_port": ports['frontend']
                    })
            
            # Sort by model name and app number
            ports_data.sort(key=lambda x: (x['model_name'], x['app_number']))
            
            # Write port configuration
            port_config_file = self.structure.base_path / "port_config.json"
            with open(port_config_file, 'w', encoding='utf-8') as f:
                json.dump(ports_data, f, indent=2, ensure_ascii=False)
            
            # Generate models summary
            models_summary = {
                "extraction_timestamp": datetime.datetime.now().isoformat(),
                "total_models": len(self.models),
                "apps_per_model": Config.APPS_PER_MODEL,
                "models": [
                    {
                        "name": model,
                        "color": self.model_colors.get(model, "#666666").strip('`'),
                        "provider": model.split('_')[0] if '_' in model else model
                    }
                    for model in self.models
                ]
            }
            
            summary_file = self.structure.base_path / "models_summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(models_summary, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Configuration files created: {port_config_file}, {summary_file}")
            print(f"\n📄 Configuration files created:")
            print(f"   Port config: {port_config_file}")
            print(f"   Models summary: {summary_file}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to generate configuration files: {e}")
            return False


def get_user_input() -> str:
    """Get OpenRouter input from user"""
    print("=" * 80)
    print("AI Model Management System - Dynamic Model Generator v2.0")
    print("=" * 80)
    print("\nPlease provide models from OpenRouter in one of the following formats:")
    print("1. Full OpenRouter URL (e.g., https://openrouter.ai/chat?models=...)")
    print("2. Just the models string (e.g., mistralai/mistral-small:free,openai/gpt-4...)")
    print("\nExample URL:")
    print("https://openrouter.ai/chat?models=mistralai/mistral-small-3.2-24b-instruct:free,openai/gpt-4.1")
    print("\nExample string:")
    print("mistralai/mistral-small-3.2-24b-instruct:free,openai/gpt-4.1,anthropic/claude-sonnet-4")
    print("-" * 80)
    
    user_input = input("Enter OpenRouter URL or models string: ").strip()
    return user_input


def confirm_operation(models: List[str]) -> bool:
    """Ask user to confirm the operation"""
    print(f"\nFound {len(models)} models:")
    for i, model in enumerate(models, 1):
        print(f"  {i:2d}. {model}")
    
    print(f"\nThis will create {len(models) * Config.APPS_PER_MODEL} applications.")
    print("Do you want to continue? (y/N)")
    
    confirm = input().strip().lower()
    return confirm in ['y', 'yes']


def main():
    """Main execution function"""
    try:
        # Get user input
        user_input = get_user_input()
        if not user_input:
            print("Error: No input provided!")
            return 1
        
        # Initialize manager
        manager = ModelManager()
        
        # Validate system setup
        if not manager.validate_setup():
            print("System validation failed. Please check template directory.")
            return 1
        
        # Load models
        if not manager.load_models(user_input):
            print("Failed to load models from input.")
            return 1
        
        # Confirm operation
        if not confirm_operation(manager.models):
            print("Operation cancelled by user.")
            return 0
        
        # Create all model applications
        print("\nStarting model application generation...")
        success = manager.create_all_models()
        
        # Generate configuration files
        config_success = manager.generate_configuration_files()
        
        # Display final summary
        print("\n" + "=" * 80)
        print("GENERATION SUMMARY")
        print("=" * 80)
        
        if success and config_success:
            print(f"✅ Successfully generated applications for {len(manager.models)} models")
            print(f"📁 Base directory: {manager.structure.base_path}")
            print(f"📁 Models directory: {manager.structure.models_dir}")
            print(f"📝 Logs directory: {manager.structure.logs_dir}")
            print(f"🔢 Total applications: {len(manager.models) * Config.APPS_PER_MODEL}")
            print("=" * 80)
            return 0
        else:
            print("❌ Some operations failed. Check logs for details.")
            print("=" * 80)
            return 1
            
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user (Ctrl+C)")
        return 1
    except Exception as e:
        print(f"\nCritical error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())