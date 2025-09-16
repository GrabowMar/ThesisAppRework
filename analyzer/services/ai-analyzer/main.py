#!/usr/bin/env python3
"""
AI Analyzer Service - AI-Powered Code Analysis
==============================================

Refactored to use BaseWSService for uniform server lifecycle and logging.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from analyzer.shared.service_base import BaseWSService
import aiohttp
from pathlib import Path

class AIAnalyzer(BaseWSService):
    """AI-powered code analysis service."""
    
    def __init__(self):
        super().__init__(service_name="ai-analyzer", default_port=2004, version="1.0.0")
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
        self.log.debug(f"Available AI models: {len(models)}")
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
                            self.log.debug(f"Could not read {file_path}: {e}")
            
            self.log.debug(f"Read {len(files_content)} source files from {source_path}")
            return files_content
            
        except Exception as e:
            self.log.error(f"Error reading source files: {e}")
            return {}
    
    async def analyze_with_ai(self, prompt: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze code using AI model via OpenRouter with custom configuration."""
        # Get configuration parameters
        openrouter_config = config.get('openrouter', {}) if config else {}
        
        try:
            if not self.openrouter_api_key:
                return {
                    'status': 'error',
                    'error': 'OpenRouter API key not configured'
                }
            
            model_to_use = openrouter_config.get('model', self.default_model)
            max_tokens = openrouter_config.get('max_tokens', 4000)
            temperature = openrouter_config.get('temperature', 0.1)
            top_p = openrouter_config.get('top_p', 1.0)
            frequency_penalty = openrouter_config.get('frequency_penalty', 0.0)
            presence_penalty = openrouter_config.get('presence_penalty', 0.0)
            stop_sequences = openrouter_config.get('stop', [])
            stream = openrouter_config.get('stream', False)
            timeout = openrouter_config.get('timeout', 120)
            
            headers = {
                'Authorization': f'Bearer {self.openrouter_api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'http://localhost:2004',
                'X-Title': 'AI Code Analyzer'
            }
            
            # Add custom headers if specified
            if openrouter_config.get('custom_headers'):
                headers.update(openrouter_config['custom_headers'])
            
            # Prepare system prompt
            system_prompt = openrouter_config.get('system_prompt')
            if not system_prompt:
                system_prompt = '''You are an expert code analyst. Analyze the provided code for:
1. Security vulnerabilities and concerns
2. Code quality issues and improvements
3. Performance bottlenecks
4. Best practices violations
5. Architecture and design patterns
6. Maintainability concerns

Provide structured analysis with specific recommendations.'''
            
            messages = [
                {
                    'role': 'system',
                    'content': system_prompt
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ]
            
            payload = {
                'model': model_to_use,
                'messages': messages,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'top_p': top_p,
                'frequency_penalty': frequency_penalty,
                'presence_penalty': presence_penalty,
                'stream': stream
            }
            
            if stop_sequences:
                payload['stop'] = stop_sequences
            
            # Add reasoning parameters if enabled
            if openrouter_config.get('reasoning_enabled', False):
                reasoning_config = {
                    'effort': openrouter_config.get('reasoning_effort', 'medium')
                }
                if not openrouter_config.get('include_reasoning', True):
                    reasoning_config['exclude'] = True
                payload['reasoning'] = reasoning_config
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        if 'choices' in result and len(result['choices']) > 0:
                            choice = result['choices'][0]
                            message = choice['message']
                            analysis_text = message['content']
                            
                            # Extract reasoning if present
                            reasoning = None
                            if 'reasoning' in message and openrouter_config.get('include_reasoning'):
                                reasoning = message['reasoning']
                            
                            return {
                                'status': 'success',
                                'model': model_to_use,
                                'analysis': analysis_text,
                                'reasoning': reasoning,
                                'usage': result.get('usage', {}),
                                'timestamp': datetime.now().isoformat(),
                                'config_used': openrouter_config
                            }
                        else:
                            return {
                                'status': 'error',
                                'error': 'No response from AI model',
                                'model': model_to_use,
                                'config_used': openrouter_config
                            }
                    else:
                        error_text = await response.text()
                        return {
                            'status': 'error',
                            'error': f'API error {response.status}: {error_text}',
                            'model': model_to_use,
                            'config_used': openrouter_config
                        }
                        
        except asyncio.TimeoutError:
            return {
                'status': 'timeout',
                'error': 'AI analysis request timed out',
                'model': openrouter_config.get('model', self.default_model),
                'config_used': openrouter_config
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'model': openrouter_config.get('model', self.default_model),
                'config_used': openrouter_config
            }
    
    async def analyze_with_gpt4all(self, prompt: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze code using local GPT4All model with custom configuration."""
        gpt4all_config = config.get('gpt4all', {}) if config else {}
        
        try:
            # GPT4All configuration
            api_url = gpt4all_config.get('api_url', os.getenv('GPT4ALL_API_URL', 'http://localhost:4891/v1'))
            preferred_model = gpt4all_config.get('preferred_model', 'Llama 3 8B Instruct')
            max_tokens = gpt4all_config.get('max_tokens', 4000)
            temperature = gpt4all_config.get('temperature', 0.1)
            timeout = gpt4all_config.get('timeout', 120)
            
            # Available models preference order
            preferred_models = [
                "Llama 3 8B Instruct",
                "DeepSeek-R1-Distill-Qwen-7B", 
                "Nous Hermes 2 Mistral DPO",
                "GPT4All Falcon",
                "Mistral 7B Instruct"
            ]
            
            # Check server availability
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                    async with session.get(f"{api_url}/models") as response:
                        if response.status != 200:
                            return {
                                'status': 'error',
                                'error': 'GPT4All server not available',
                                'config_used': gpt4all_config
                            }
                        
                        models_data = await response.json()
                        available_models = []
                        for model in models_data.get('data', []):
                            if isinstance(model, dict) and 'id' in model:
                                available_models.append(model['id'])
                            elif isinstance(model, str):
                                available_models.append(model)
                        
                        # Select best available model
                        model_to_use = preferred_model
                        if preferred_model and preferred_model in available_models:
                            model_to_use = preferred_model
                        else:
                            for model in preferred_models:
                                if model in available_models:
                                    model_to_use = model
                                    break
                            else:
                                if available_models:
                                    model_to_use = available_models[0]
                                else:
                                    model_to_use = "Llama 3 8B Instruct"
                        
                        self.log.info(f"Using GPT4All model: {model_to_use}")
                        
            except Exception as e:
                return {
                    'status': 'error',
                    'error': f'Failed to connect to GPT4All server: {str(e)}',
                    'config_used': gpt4all_config
                }
            
            # Prepare system prompt for code analysis
            system_prompt = gpt4all_config.get('system_prompt', '''You are an expert code reviewer focused on determining if code meets specific requirements.
Analyze the provided code and determine if it satisfies the given requirement.
Focus on concrete evidence in the code, not assumptions.
Some code may be summarized or simplified - look for key patterns and functionality.
Respond with JSON containing only the following fields:
{
  "met": true/false,
  "confidence": "HIGH"/"MEDIUM"/"LOW",
  "explanation": "Brief explanation with specific code evidence"
}''')
            
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            payload = {
                "model": model_to_use,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            # Make request to GPT4All
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.post(
                    f"{api_url}/chat/completions",
                    headers={'Content-Type': 'application/json'},
                    json=payload
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        if 'choices' in result and len(result['choices']) > 0:
                            choice = result['choices'][0]
                            message = choice['message']
                            analysis_text = message['content']
                            
                            # Try to parse JSON response
                            try:
                                # Look for JSON in the response
                                import re
                                json_match = re.search(r'```(?:json)?\\s*({.*?})\\s*```', analysis_text, re.DOTALL)
                                if json_match:
                                    json_content = json.loads(json_match.group(1))
                                else:
                                    json_match = re.search(r'({.*?})', analysis_text, re.DOTALL)
                                    if json_match:
                                        json_content = json.loads(json_match.group(1))
                                    else:
                                        # Fallback parsing
                                        json_content = {
                                            "met": "meets the requirement" in analysis_text.lower() or "requirement is met" in analysis_text.lower(),
                                            "confidence": "LOW",
                                            "explanation": analysis_text[:200] + ("..." if len(analysis_text) > 200 else "")
                                        }
                                        
                                return {
                                    'status': 'success',
                                    'model': model_to_use,
                                    'analysis': json_content,
                                    'raw_response': analysis_text,
                                    'usage': result.get('usage', {}),
                                    'timestamp': datetime.now().isoformat(),
                                    'config_used': gpt4all_config
                                }
                                
                            except json.JSONDecodeError:
                                # Return raw analysis if JSON parsing fails
                                return {
                                    'status': 'success',
                                    'model': model_to_use,
                                    'analysis': analysis_text,
                                    'usage': result.get('usage', {}),
                                    'timestamp': datetime.now().isoformat(),
                                    'config_used': gpt4all_config
                                }
                        else:
                            return {
                                'status': 'error',
                                'error': 'No response from GPT4All model',
                                'model': model_to_use,
                                'config_used': gpt4all_config
                            }
                    else:
                        error_text = await response.text()
                        return {
                            'status': 'error',
                            'error': f'GPT4All API error {response.status}: {error_text}',
                            'model': model_to_use,
                            'config_used': gpt4all_config
                        }
                        
        except asyncio.TimeoutError:
            return {
                'status': 'timeout',
                'error': 'GPT4All analysis request timed out',
                'model': gpt4all_config.get('preferred_model', 'Llama 3 8B Instruct'),
                'config_used': gpt4all_config
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': f'GPT4All analysis failed: {str(e)}',
                'model': gpt4all_config.get('preferred_model', 'Llama 3 8B Instruct'),
                'config_used': gpt4all_config
            }
    
    def _fallback_analyze_code(self, requirement: str, code: str, is_frontend: bool) -> Dict[str, Any]:
        """Fallback analysis using basic pattern matching when AI unavailable."""
        self.log.info(f"Using fallback analysis for {'frontend' if is_frontend else 'backend'} code")
        
        req_lower = requirement.lower()
        
        result = {
            "met": False,
            "confidence": "LOW",
            "explanation": f"Fallback analysis: Unable to analyze with AI API. Basic pattern matching used."
        }
        
        if is_frontend:
            # Basic frontend pattern matching
            if any(term in req_lower for term in ['form', 'input', 'submit']):
                result["met"] = any(term in code.lower() for term in ['<form', 'input', 'submit', 'button'])
            elif any(term in req_lower for term in ['navigation', 'menu', 'nav']):
                result["met"] = any(term in code.lower() for term in ['nav', 'menu', 'header', 'sidebar'])
            elif any(term in req_lower for term in ['responsive', 'mobile']):
                result["met"] = any(term in code.lower() for term in ['@media', 'mobile', 'responsive', 'grid', 'flex'])
        else:
            # Basic backend pattern matching
            if any(term in req_lower for term in ['database', 'db', 'sql']):
                result["met"] = any(term in code.lower() for term in ['database', 'db', 'sql', 'query', 'select', 'insert'])
            elif any(term in req_lower for term in ['api', 'endpoint', 'route']):
                result["met"] = any(term in code.lower() for term in ['@app.route', 'def ', 'api', 'endpoint', 'get', 'post'])
            elif any(term in req_lower for term in ['authentication', 'auth', 'login']):
                result["met"] = any(term in code.lower() for term in ['auth', 'login', 'password', 'token', 'session'])
        
        if result["met"]:
            result["confidence"] = "MEDIUM"
        return result
    
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
    
    async def analyze_application_ai(self, model_slug: str, app_number: int, source_path: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform comprehensive AI analysis of application."""
        try:
            self.log.info(f"AI analyzing {model_slug} app {app_number}")
            
            # Read source files
            files_content = await self.read_source_files(source_path)
            
            if not files_content:
                return {
                    'status': 'error',
                    'error': f'No source files found in {source_path}',
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'config_used': config or {}
                }
            
            # Analyze code structure
            structure_analysis = await self.analyze_code_structure(files_content)
            
            # Generate code summary for AI
            code_summary = await self.generate_code_summary(files_content)
            
            # Perform AI analysis with configuration
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
            
            ai_analysis = await self.analyze_with_ai(ai_prompt, config)
            
            # Compile results
            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'source_path': source_path,
                'structure_analysis': structure_analysis,
                'ai_analysis': ai_analysis,
                'files_analyzed': len(files_content),
                'service': self.info.name,
                'version': self.info.version,
                'config_used': config or {}
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
            self.log.error(f"AI analysis failed: {e}")
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
            
            if msg_type == "ai_analysis":
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 1)
                source_path = message_data.get("source_path", "")
                
                if not source_path:
                    # Generate default path
                    source_path = f"/workspace/misc/models/{model_slug}/app{app_number}"
                
                self.log.debug(f"Starting AI analysis for {model_slug} app {app_number}")
                
                analysis_results = await self.analyze_application_ai(model_slug, app_number, source_path)
                
                response = {
                    "type": "ai_analysis_result",
                    "status": "success",
                    "service": self.info.name,
                    "analysis": analysis_results,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(response))
                self.log.debug(f"AI analysis completed for {model_slug} app {app_number}")
                
            elif msg_type == "list_models":
                response = {
                    "type": "models_list",
                    "available_models": self.available_models,
                    "default_model": self.default_model,
                    "service": self.info.name
                }
                await websocket.send(json.dumps(response))
                
            else:
                response = {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                    "service": self.info.name
                }
                await websocket.send(json.dumps(response))
                
        except Exception as e:
            self.log.error(f"Error handling message: {e}")
            error_response = {
                "type": "error",
                "message": f"Internal error: {str(e)}",
                "service": self.info.name
            }
            try:
                await websocket.send(json.dumps(error_response))
            except Exception:
                pass

async def main():
    # Log API key presence for visibility
    if not os.getenv('OPENROUTER_API_KEY'):
        print("[ai-analyzer] WARNING: OPENROUTER_API_KEY not set - AI analysis will be limited")
    service = AIAnalyzer()
    await service.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
