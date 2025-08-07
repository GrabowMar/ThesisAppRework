"""
AI Analyzer Service - OpenRouter Integration
==========================================

FastAPI service for AI-powered code analysis using OpenRouter API.
Analyzes AI-generated applications for quality, adherence to requirements,
and improvement suggestions.
"""

import os
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("ai_analyzer")

# Initialize FastAPI app
app = FastAPI(
    title="AI Analyzer Service", 
    description="OpenRouter-powered AI code analysis service",
    version="1.0.0"
)

# Configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
SERVICE_ENABLED = bool(OPENROUTER_API_KEY)

# Default analysis models - fallback order
DEFAULT_ANALYSIS_MODELS = [
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "openai/gpt-4-turbo",
    "google/gemini-pro-1.5",
    "meta-llama/llama-3.1-70b-instruct"
]

if not SERVICE_ENABLED:
    logger.warning("AI Analyzer service starting in disabled mode - no OpenRouter API key")
else:
    logger.info("AI Analyzer service starting with OpenRouter integration")


# Request/Response Models
class AnalysisRequest(BaseModel):
    """Request model for code analysis."""
    model_slug: str = Field(..., description="Model identifier (e.g., 'anthropic_claude-3-sonnet')")
    app_number: int = Field(..., ge=1, le=30, description="Application number (1-30)")
    requirements: Optional[str] = Field(None, description="Optional analysis requirements")
    analysis_model: Optional[str] = Field(None, description="Specific model to use for analysis")
    include_suggestions: bool = Field(True, description="Include improvement suggestions")
    max_files: int = Field(50, ge=1, le=100, description="Maximum files to analyze")


class AnalysisResponse(BaseModel):
    """Response model for analysis results."""
    success: bool
    analysis_id: Optional[str] = None
    data: Dict[str, Any] = {}
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str
    openrouter_enabled: bool
    timestamp: str
    version: str


# HTTP client for OpenRouter API
http_client = httpx.AsyncClient(timeout=120.0)


async def get_application_source_code(model_slug: str, app_number: int, max_files: int = 50) -> Optional[Dict[str, Any]]:
    """
    Get source code files for the specified application.
    
    Args:
        model_slug: Model identifier
        app_number: Application number
        max_files: Maximum number of files to collect
        
    Returns:
        Dictionary containing source code or None if not found
    """
    try:
        # Path to application directory
        sources_dir = Path("/app/sources")  # Mounted volume in container
        app_dir = sources_dir / model_slug / f"app{app_number}"
        
        if not app_dir.exists():
            logger.warning("Application directory not found", 
                         model=model_slug, app_number=app_number, path=str(app_dir))
            return None
        
        source_files = {}
        file_count = 0
        
        # Supported file extensions for analysis
        source_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.scss',
            '.json', '.yml', '.yaml', '.md', '.txt', '.env', '.dockerfile',
            '.sql', '.sh', '.bat'
        }
        
        # Collect files from backend and frontend directories
        for component in ['backend', 'frontend']:
            component_dir = app_dir / component
            if component_dir.exists():
                component_files = {}
                
                for file_path in component_dir.rglob('*'):
                    if file_count >= max_files:
                        logger.warning("File limit reached", limit=max_files)
                        break
                        
                    if (file_path.is_file() and 
                        file_path.suffix.lower() in source_extensions and
                        not any(skip in str(file_path) for skip in ['node_modules', '__pycache__', '.git'])):
                        
                        try:
                            relative_path = file_path.relative_to(component_dir)
                            content = file_path.read_text(encoding='utf-8', errors='ignore')
                            component_files[str(relative_path)] = content
                            file_count += 1
                        except Exception as e:
                            logger.debug("Could not read file", 
                                       file=str(file_path), error=str(e))
                            continue
                
                if component_files:
                    source_files[component] = component_files
        
        # Also collect docker-compose.yml and other config files
        for config_file in ['docker-compose.yml', 'requirements.txt', 'package.json', 'README.md']:
            config_path = app_dir / config_file
            if config_path.exists():
                try:
                    source_files[config_file] = config_path.read_text(encoding='utf-8')
                except Exception as e:
                    logger.debug("Could not read config file", 
                               file=config_file, error=str(e))
        
        logger.info("Source code collected", 
                   model=model_slug, app_number=app_number, 
                   files_count=file_count, components=list(source_files.keys()))
        
        return source_files if source_files else None
        
    except Exception as e:
        logger.error("Failed to collect source code", 
                    model=model_slug, app_number=app_number, error=str(e))
        return None


def build_analysis_prompt(source_code: Dict[str, Any], requirements: Optional[str] = None) -> str:
    """
    Build comprehensive analysis prompt for OpenRouter.
    
    Args:
        source_code: Dictionary containing source code files
        requirements: Optional specific requirements to analyze against
        
    Returns:
        Formatted analysis prompt
    """
    prompt_parts = [
        "# AI-Generated Web Application Code Analysis",
        "",
        "You are an expert software engineer conducting a comprehensive code review of an AI-generated web application. Please analyze the provided code for:",
        "",
        "## Analysis Criteria:",
        "1. **Code Quality**: Clean code principles, readability, maintainability",
        "2. **Architecture**: Overall structure, separation of concerns, design patterns",
        "3. **Security**: Common vulnerabilities, input validation, authentication",
        "4. **Performance**: Efficiency, optimization opportunities, scalability",
        "5. **Best Practices**: Framework conventions, coding standards",
        "6. **Functionality**: Does the code appear to work as intended?",
        "7. **Error Handling**: Robustness, exception handling, edge cases",
        ""
    ]
    
    if requirements:
        prompt_parts.extend([
            "## Specific Requirements to Evaluate Against:",
            requirements,
            ""
        ])
    
    prompt_parts.extend([
        "## Application Structure:",
        ""
    ])
    
    # Add source code with appropriate formatting
    total_files = sum(len(files) for files in source_code.values() if isinstance(files, dict))
    
    for component, files in source_code.items():
        if isinstance(files, dict):
            prompt_parts.append(f"### {component.upper()} Component:")
            for file_path, content in list(files.items())[:10]:  # Limit files per component
                prompt_parts.extend([
                    f"#### File: `{file_path}`",
                    "```",
                    content[:2000] + ("..." if len(content) > 2000 else ""),  # Limit content length
                    "```",
                    ""
                ])
        else:
            prompt_parts.extend([
                f"### {component}:",
                "```",
                str(files)[:1000] + ("..." if len(str(files)) > 1000 else ""),
                "```",
                ""
            ])
    
    prompt_parts.extend([
        "",
        "## Please provide analysis in this JSON format:",
        "```json",
        "{",
        '  "overall_score": 85,',
        '  "summary": "Brief overall assessment",',
        '  "strengths": ["List of positive aspects"],',
        '  "issues": [',
        '    {"severity": "high|medium|low", "category": "security|performance|quality|architecture", "description": "Issue description", "file": "affected_file", "suggestion": "How to fix"}',
        '  ],',
        '  "recommendations": ["List of improvement suggestions"],',
        '  "security_concerns": ["Security-specific issues"],',
        '  "performance_notes": ["Performance-related observations"],',
        '  "code_quality_score": 80,',
        '  "architecture_score": 75,',
        '  "security_score": 90,',
        '  "maintainability_score": 85',
        "}",
        "```",
        "",
        f"Note: Analyzing {total_files} files across components: {', '.join(source_code.keys())}"
    ])
    
    return "\n".join(prompt_parts)


async def send_to_openrouter(prompt: str, model: str = None) -> Dict[str, Any]:
    """
    Send analysis request to OpenRouter API.
    
    Args:
        prompt: Analysis prompt
        model: Specific model to use (optional)
        
    Returns:
        API response data
    """
    if not SERVICE_ENABLED:
        return {
            'success': False,
            'error': 'OpenRouter API key not configured'
        }
    
    # Try models in order of preference
    models_to_try = [model] if model else DEFAULT_ANALYSIS_MODELS
    
    for model_name in models_to_try:
        if not model_name:
            continue
            
        try:
            logger.info("Sending analysis request to OpenRouter", model=model_name)
            
            headers = {
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/thesis-ai-testing-framework',
                'X-Title': 'AI Testing Framework Analysis'
            }
            
            payload = {
                'model': model_name,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': 4000,
                'temperature': 0.1,  # Low temperature for consistent analysis
                'top_p': 0.9
            }
            
            async with http_client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                
                if response.status_code == 200:
                    result = await response.json()
                    
                    if 'choices' in result and len(result['choices']) > 0:
                        analysis_text = result['choices'][0]['message']['content']
                        
                        return {
                            'success': True,
                            'analysis': analysis_text,
                            'model_used': model_name,
                            'usage': result.get('usage', {}),
                            'raw_response': result
                        }
                    else:
                        logger.warning("Empty response from OpenRouter", model=model_name)
                        continue
                        
                elif response.status_code == 429:
                    logger.warning("Rate limit hit, trying next model", model=model_name)
                    continue
                    
                else:
                    error_text = await response.text()
                    logger.error("OpenRouter API error", 
                               model=model_name, 
                               status=response.status_code,
                               error=error_text)
                    continue
                    
        except Exception as e:
            logger.error("Request to OpenRouter failed", 
                        model=model_name, error=str(e))
            continue
    
    return {
        'success': False,
        'error': 'All analysis models failed or unavailable'
    }


def parse_analysis_response(analysis_text: str) -> Dict[str, Any]:
    """
    Parse and structure the analysis response from OpenRouter.
    
    Args:
        analysis_text: Raw analysis text from AI model
        
    Returns:
        Structured analysis data
    """
    try:
        # Try to extract JSON from the response
        json_start = analysis_text.find('{')
        json_end = analysis_text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = analysis_text[json_start:json_end]
            parsed_data = json.loads(json_str)
            
            # Validate required fields
            if 'overall_score' in parsed_data and 'summary' in parsed_data:
                return parsed_data
    
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Could not parse JSON from analysis", error=str(e))
    
    # Fallback: create structured data from text
    return {
        'overall_score': 75,  # Default score
        'summary': analysis_text[:500] + "..." if len(analysis_text) > 500 else analysis_text,
        'strengths': [],
        'issues': [],
        'recommendations': [],
        'security_concerns': [],
        'performance_notes': [],
        'code_quality_score': 75,
        'architecture_score': 75,
        'security_score': 75,
        'maintainability_score': 75,
        'raw_analysis': analysis_text
    }


# API Endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy" if SERVICE_ENABLED else "degraded",
        service="ai-analyzer",
        openrouter_enabled=SERVICE_ENABLED,
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_code(request: AnalysisRequest):
    """
    Analyze AI-generated application code using OpenRouter models.
    
    Args:
        request: Analysis request parameters
        
    Returns:
        Analysis results
    """
    if not SERVICE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="AI Analyzer service unavailable - OpenRouter API key not configured"
        )
    
    analysis_id = f"{request.model_slug}_app{request.app_number}_{int(datetime.now().timestamp())}"
    
    try:
        logger.info("Starting code analysis", 
                   model=request.model_slug, 
                   app_number=request.app_number,
                   analysis_id=analysis_id)
        
        # Get application source code
        source_code = await get_application_source_code(
            request.model_slug, 
            request.app_number, 
            request.max_files
        )
        
        if not source_code:
            raise HTTPException(
                status_code=404,
                detail=f"Source code not found for {request.model_slug} app{request.app_number}"
            )
        
        # Build analysis prompt
        analysis_prompt = build_analysis_prompt(source_code, request.requirements)
        
        # Send to OpenRouter
        result = await send_to_openrouter(analysis_prompt, request.analysis_model)
        
        if result['success']:
            # Parse and structure the response
            parsed_analysis = parse_analysis_response(result['analysis'])
            
            response_data = {
                'analysis': parsed_analysis,
                'model_analyzed': request.model_slug,
                'app_number': request.app_number,
                'timestamp': datetime.now().isoformat(),
                'analyzer_model': result.get('model_used', 'unknown'),
                'token_usage': result.get('usage', {}),
                'source_files_count': sum(
                    len(files) if isinstance(files, dict) else 1 
                    for files in source_code.values()
                )
            }
            
            logger.info("Analysis completed successfully", 
                       analysis_id=analysis_id,
                       model=request.model_slug,
                       app_number=request.app_number)
            
            return AnalysisResponse(
                success=True,
                analysis_id=analysis_id,
                data=response_data,
                metadata={
                    'processing_time': 'calculated_by_caller',
                    'service_version': '1.0.0'
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {result.get('error', 'Unknown error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Analysis failed with exception", 
                    analysis_id=analysis_id,
                    error=str(e),
                    traceback=traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/models")
async def get_available_models():
    """Get list of available analysis models."""
    return {
        "available_models": DEFAULT_ANALYSIS_MODELS,
        "default_model": DEFAULT_ANALYSIS_MODELS[0] if DEFAULT_ANALYSIS_MODELS else None,
        "service_enabled": SERVICE_ENABLED
    }


@app.get("/status")
async def get_service_status():
    """Get detailed service status."""
    return {
        "service": "ai-analyzer",
        "status": "operational" if SERVICE_ENABLED else "disabled",
        "openrouter_configured": SERVICE_ENABLED,
        "api_base_url": OPENROUTER_BASE_URL,
        "available_models": len(DEFAULT_ANALYSIS_MODELS),
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Service startup initialization."""
    logger.info("AI Analyzer service starting up",
               openrouter_enabled=SERVICE_ENABLED,
               models_available=len(DEFAULT_ANALYSIS_MODELS))


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Service shutdown cleanup."""
    await http_client.aclose()
    logger.info("AI Analyzer service shutting down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
