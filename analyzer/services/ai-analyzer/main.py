#!/usr/bin/env python3
"""
AI Analyzer Service - AI-Powered Code Analysis
===============================================

A containerized AI analysis service that performs:
- Code quality assessment using language models
- Security pattern detection
- Architecture analysis
- Best practices compliance checking

Usage:
    docker-compose up ai-analyzer

The service will start on ws://localhost:2004
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import websockets
from websockets.asyncio.server import serve
import aiohttp
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIAnalyzer:
    """AI-powered code analysis service."""
    
    def __init__(self):
        self.service_name = "ai-analyzer"
        self.version = "1.0.0"
        self.start_time = datetime.now()
        self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        self.default_model = os.getenv('AI_MODEL', 'anthropic/claude-3-haiku')
        self.available_models = self._get_available_models()
    
    def _get_available_models(self) -> List[str]:
        """Get list of available AI models."""
        # Common models available on OpenRouter
        models = [
            'anthropic/claude-3-haiku',
            'anthropic/claude-3-sonnet',
            'openai/gpt-4o-mini',
            'openai/gpt-3.5-turbo',
            'meta-llama/llama-3.1-8b-instruct',
            'google/gemini-flash-1.5'
        ]
        
        logger.info(f"Available AI models: {len(models)}")
        return models
    
    async def read_source_files(self, source_path: str) -> Dict[str, str]:
        """Read source files from application directory."""
        try:
            files_content = {}
            source_dir = Path(source_path)
            
            if not source_dir.exists():
                return files_content
            
            # Common source file extensions
            extensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.css', '.html', '.json', '.yaml', '.yml', '.md']
            
            for ext in extensions:
                for file_path in source_dir.rglob(f'*{ext}'):
                    if file_path.is_file() and file_path.stat().st_size < 100000:  # Max 100KB
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                relative_path = str(file_path.relative_to(source_dir))
                                files_content[relative_path] = content
                        except Exception as e:
                            logger.debug(f"Could not read {file_path}: {e}")
            
            logger.info(f"Read {len(files_content)} source files from {source_path}")
            return files_content
            
        except Exception as e:
            logger.error(f"Error reading source files: {e}")
            return {}
    
    async def analyze_with_ai(self, prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Analyze code using AI model via OpenRouter."""
        try:
            if not self.openrouter_api_key:
                return {
                    'status': 'error',
                    'error': 'OpenRouter API key not configured'
                }
            
            model_to_use = model or self.default_model
            
            headers = {
                'Authorization': f'Bearer {self.openrouter_api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'http://localhost:2004',
                'X-Title': 'AI Code Analyzer'
            }
            
            payload = {
                'model': model_to_use,
                'messages': [
                    {
                        'role': 'system',
                        'content': '''You are an expert code analyst. Analyze the provided code for:
1. Security vulnerabilities and concerns
2. Code quality issues and improvements
3. Performance bottlenecks
4. Best practices violations
5. Architecture and design patterns
6. Maintainability concerns

Provide structured analysis with specific recommendations.'''
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': 4000,
                'temperature': 0.1
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
                async with session.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        if 'choices' in result and len(result['choices']) > 0:
                            analysis_text = result['choices'][0]['message']['content']
                            
                            return {
                                'status': 'success',
                                'model': model_to_use,
                                'analysis': analysis_text,
                                'usage': result.get('usage', {}),
                                'timestamp': datetime.now().isoformat()
                            }
                        else:
                            return {
                                'status': 'error',
                                'error': 'No response from AI model',
                                'model': model_to_use
                            }
                    else:
                        error_text = await response.text()
                        return {
                            'status': 'error',
                            'error': f'API error {response.status}: {error_text}',
                            'model': model_to_use
                        }
                        
        except asyncio.TimeoutError:
            return {
                'status': 'timeout',
                'error': 'AI analysis request timed out',
                'model': model_to_use
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'model': model_to_use
            }
    
    async def analyze_code_structure(self, files_content: Dict[str, str]) -> Dict[str, Any]:
        """Analyze code structure and patterns."""
        try:
            analysis = {
                'file_count': len(files_content),
                'languages': [],
                'structure': {},
                'complexity_indicators': {}
            }
            
            # Detect languages
            language_indicators = {
                '.py': 'Python',
                '.js': 'JavaScript',
                '.jsx': 'React/JavaScript',
                '.ts': 'TypeScript',
                '.tsx': 'React/TypeScript',
                '.css': 'CSS',
                '.html': 'HTML',
                '.json': 'JSON',
                '.yaml': 'YAML',
                '.yml': 'YAML',
                '.md': 'Markdown'
            }
            
            detected_languages = set()
            for file_path in files_content.keys():
                for ext, lang in language_indicators.items():
                    if file_path.endswith(ext):
                        detected_languages.add(lang)
            
            analysis['languages'] = list(detected_languages)
            
            # Analyze structure
            frontend_files = []
            backend_files = []
            config_files = []
            
            for file_path, content in files_content.items():
                if any(file_path.endswith(ext) for ext in ['.html', '.css', '.js', '.jsx', '.ts', '.tsx']):
                    frontend_files.append(file_path)
                elif file_path.endswith('.py'):
                    backend_files.append(file_path)
                elif any(file_path.endswith(ext) for ext in ['.json', '.yaml', '.yml', '.md']):
                    config_files.append(file_path)
            
            analysis['structure'] = {
                'frontend_files': frontend_files,
                'backend_files': backend_files,
                'config_files': config_files
            }
            
            # Calculate complexity indicators
            total_lines = sum(len(content.split('\n')) for content in files_content.values())
            total_chars = sum(len(content) for content in files_content.values())
            
            analysis['complexity_indicators'] = {
                'total_lines_of_code': total_lines,
                'total_characters': total_chars,
                'average_file_size': total_lines / len(files_content) if files_content else 0,
                'largest_file': max((len(content.split('\n')), path) 
                                  for path, content in files_content.items())[1] if files_content else None
            }
            
            return analysis
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def generate_code_summary(self, files_content: Dict[str, str]) -> str:
        """Generate a summary of the codebase for AI analysis."""
        try:
            summary_parts = []
            
            # Add basic info
            summary_parts.append(f"Codebase Analysis - {len(files_content)} files")
            summary_parts.append("=" * 50)
            
            # Group files by type
            file_groups = {
                'Python Files': [f for f in files_content.keys() if f.endswith('.py')],
                'JavaScript/TypeScript Files': [f for f in files_content.keys() 
                                              if any(f.endswith(ext) for ext in ['.js', '.jsx', '.ts', '.tsx'])],
                'HTML/CSS Files': [f for f in files_content.keys() 
                                 if any(f.endswith(ext) for ext in ['.html', '.css'])],
                'Configuration Files': [f for f in files_content.keys() 
                                      if any(f.endswith(ext) for ext in ['.json', '.yaml', '.yml'])]
            }
            
            # Add file listings and content samples
            for group_name, file_list in file_groups.items():
                if file_list:
                    summary_parts.append(f"\n{group_name}:")
                    summary_parts.append("-" * len(group_name))
                    
                    for file_path in file_list[:5]:  # Limit to first 5 files per group
                        content = files_content[file_path]
                        lines = content.split('\n')
                        
                        summary_parts.append(f"\n📄 {file_path} ({len(lines)} lines):")
                        
                        # Add content sample (first 30 lines)
                        sample_lines = lines[:30]
                        if len(lines) > 30:
                            sample_lines.append(f"... ({len(lines) - 30} more lines)")
                        
                        summary_parts.append('\n'.join(sample_lines))
                        summary_parts.append("")
            
            return '\n'.join(summary_parts)
            
        except Exception as e:
            return f"Error generating summary: {e}"
    
    async def analyze_application_ai(self, model_slug: str, app_number: int, source_path: str) -> Dict[str, Any]:
        """Perform comprehensive AI analysis of application."""
        try:
            logger.info(f"AI analyzing {model_slug} app {app_number}")
            
            # Read source files
            files_content = await self.read_source_files(source_path)
            
            if not files_content:
                return {
                    'status': 'error',
                    'error': f'No source files found in {source_path}',
                    'model_slug': model_slug,
                    'app_number': app_number
                }
            
            # Analyze code structure
            structure_analysis = await self.analyze_code_structure(files_content)
            
            # Generate code summary for AI
            code_summary = await self.generate_code_summary(files_content)
            
            # Perform AI analysis
            ai_prompt = f"""Please analyze this web application codebase:

{code_summary}

Focus on:
1. Security vulnerabilities and potential attack vectors
2. Code quality issues and technical debt
3. Performance optimization opportunities  
4. Best practices compliance
5. Architecture assessment
6. Maintainability and scalability concerns

Provide specific, actionable recommendations with examples."""
            
            ai_analysis = await self.analyze_with_ai(ai_prompt)
            
            # Compile results
            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'source_path': source_path,
                'structure_analysis': structure_analysis,
                'ai_analysis': ai_analysis,
                'files_analyzed': len(files_content),
                'service': self.service_name,
                'version': self.version
            }
            
            # Add summary metrics
            if ai_analysis.get('status') == 'success':
                analysis_text = ai_analysis.get('analysis', '')
                
                # Simple keyword-based scoring
                security_keywords = ['vulnerability', 'security', 'attack', 'injection', 'xss', 'csrf']
                quality_keywords = ['refactor', 'improve', 'clean', 'optimize', 'simplify']
                performance_keywords = ['performance', 'slow', 'optimize', 'cache', 'efficient']
                
                summary = {
                    'security_mentions': sum(1 for kw in security_keywords if kw in analysis_text.lower()),
                    'quality_mentions': sum(1 for kw in quality_keywords if kw in analysis_text.lower()),
                    'performance_mentions': sum(1 for kw in performance_keywords if kw in analysis_text.lower()),
                    'analysis_length': len(analysis_text),
                    'confidence_score': 'high' if len(analysis_text) > 1000 else 'medium' if len(analysis_text) > 500 else 'low'
                }
                
                results['summary'] = summary
            
            return results
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'model_slug': model_slug,
                'app_number': app_number
            }
    
    async def handle_message(self, websocket, message_data):
        """Handle incoming WebSocket messages."""
        try:
            msg_type = message_data.get("type", "unknown")
            
            if msg_type == "ping":
                response = {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                    "service": self.service_name
                }
                await websocket.send(json.dumps(response))
                
            elif msg_type == "health_check":
                uptime = (datetime.now() - self.start_time).total_seconds()
                response = {
                    "type": "health_response",
                    "status": "healthy",
                    "service": self.service_name,
                    "version": self.version,
                    "uptime": uptime,
                    "available_models": self.available_models,
                    "openrouter_configured": bool(self.openrouter_api_key),
                    "default_model": self.default_model,
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response))
                
            elif msg_type == "ai_analysis":
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 1)
                source_path = message_data.get("source_path", "")
                
                if not source_path:
                    # Generate default path
                    source_path = f"/workspace/misc/models/{model_slug}/app{app_number}"
                
                logger.info(f"Starting AI analysis for {model_slug} app {app_number}")
                
                analysis_results = await self.analyze_application_ai(model_slug, app_number, source_path)
                
                response = {
                    "type": "ai_analysis_result",
                    "status": "success",
                    "service": self.service_name,
                    "analysis": analysis_results,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(response))
                logger.info(f"AI analysis completed for {model_slug} app {app_number}")
                
            elif msg_type == "list_models":
                response = {
                    "type": "models_list",
                    "available_models": self.available_models,
                    "default_model": self.default_model,
                    "service": self.service_name
                }
                await websocket.send(json.dumps(response))
                
            else:
                response = {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                    "service": self.service_name
                }
                await websocket.send(json.dumps(response))
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error_response = {
                "type": "error",
                "message": f"Internal error: {str(e)}",
                "service": self.service_name
            }
            try:
                await websocket.send(json.dumps(error_response))
            except Exception:
                pass

async def handle_client(websocket):
    """Handle client connections."""
    analyzer = AIAnalyzer()
    client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.info(f"New client connected: {client_addr}")
    
    try:
        async for message in websocket:
            try:
                message_data = json.loads(message)
                await analyzer.handle_message(websocket, message_data)
            except json.JSONDecodeError:
                logger.error("Invalid JSON message")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {client_addr}")
    except Exception as e:
        logger.error(f"Error with client {client_addr}: {e}")

async def main():
    """Start the AI analyzer service."""
    host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
    port = int(os.getenv('WEBSOCKET_PORT', 2004))
    
    logger.info(f"Starting AI Analyzer service on {host}:{port}")
    
    # Check for API key
    if not os.getenv('OPENROUTER_API_KEY'):
        logger.warning("⚠️  OPENROUTER_API_KEY not set - AI analysis will be limited")
    else:
        logger.info("✅ OpenRouter API key configured")
    
    try:
        async with serve(handle_client, host, port):
            logger.info(f"AI Analyzer listening on ws://{host}:{port}")
            logger.info("Service ready to accept connections")
            await asyncio.Future()
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Service crashed: {e}")
        exit(1)
