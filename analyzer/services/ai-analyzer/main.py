"""
AI Analysis Service - Requirements Testing and Code Review
Performs AI-powered analysis using OpenRouter API for requirements checking and code review.
"""

import asyncio
import json
import logging
import os
import websockets
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import uuid
import requests

# Add parent directory to path for shared imports
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.protocol import (
    WebSocketMessage, MessageType, AIAnalysisRequest, 
    AnalysisResult, ProgressUpdate, AnalysisStatus,
    AnalysisIssue, SeverityLevel, create_request_from_dict
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIAnalyzer:
    """OpenRouter AI-powered code analysis and requirements testing."""
    
    def __init__(self):
        self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        self.openrouter_base_url = "https://openrouter.ai/api/v1"
        
        if not self.openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY not set - AI analysis will be limited")
        
        self.analysis_types = {
            'requirements_check': self._analyze_requirements_compliance,
            'code_review': self._perform_code_review,
            'security_audit': self._perform_security_audit,
            'architecture_review': self._review_architecture,
            'documentation_check': self._check_documentation
        }
        
    async def analyze(self, request: AIAnalysisRequest, websocket) -> AnalysisResult:
        """
        Perform AI-powered analysis of code and requirements.
        """
        analysis_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        logger.info(f"Starting AI analysis: {request.analysis_focus}")
        
        # Send initial progress
        await self._send_progress(websocket, analysis_id, "Initializing AI analysis", 0.0)
        
        issues = []
        
        try:
            # Load source code
            await self._send_progress(websocket, analysis_id, "Loading source code", 0.1)
            source_code = await self._load_source_code(request.source_path)
            
            # Perform specific analysis type
            analysis_func = self.analysis_types.get(
                request.analysis_focus, 
                self._analyze_requirements_compliance
            )
            
            await self._send_progress(websocket, analysis_id, f"Running {request.analysis_focus}", 0.3)
            issues = await analysis_func(request, source_code, websocket, analysis_id)
            
            # Generate summary
            await self._send_progress(websocket, analysis_id, "Generating summary", 0.9)
            summary = self._generate_summary(issues, request)
            
            # Final progress
            await self._send_progress(websocket, analysis_id, "Analysis complete", 1.0)
            
            return AnalysisResult(
                analysis_id=analysis_id,
                status=AnalysisStatus.COMPLETED,
                analysis_type=request.analysis_type,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration=(datetime.utcnow() - started_at).total_seconds(),
                issues=issues,
                summary=summary,
                metadata={
                    'analyzer': 'ai-analyzer',
                    'analysis_focus': request.analysis_focus,
                    'model_used': request.model_name,
                    'requirements_count': len(request.requirements)
                }
            )
                
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")
            await self._send_progress(websocket, analysis_id, f"Analysis failed: {str(e)}", 1.0)
            
            return AnalysisResult(
                analysis_id=analysis_id,
                status=AnalysisStatus.FAILED,
                analysis_type=request.analysis_type,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration=(datetime.utcnow() - started_at).total_seconds(),
                issues=[],
                summary={},
                metadata={'analyzer': 'ai-analyzer'},
                error_message=str(e)
            )
    
    async def _load_source_code(self, source_path: str) -> Dict[str, str]:
        """Load source code files from the specified path."""
        source_code = {}
        
        try:
            path = Path(source_path)
            if path.exists() and path.is_dir():
                # Load common source files
                for pattern in ['**/*.py', '**/*.js', '**/*.html', '**/*.css', '**/*.md', '**/*.txt']:
                    for file_path in path.glob(pattern):
                        if self._should_include_file(file_path):
                            try:
                                relative_path = file_path.relative_to(path)
                                content = file_path.read_text(encoding='utf-8', errors='ignore')
                                source_code[str(relative_path)] = content
                            except Exception as e:
                                logger.warning(f"Failed to read {file_path}: {str(e)}")
                                
        except Exception as e:
            logger.error(f"Failed to load source code: {str(e)}")
        
        return source_code
    
    def _should_include_file(self, file_path: Path) -> bool:
        """Check if file should be included in analysis."""
        ignore_patterns = [
            'node_modules', '.git', '__pycache__', '.pytest_cache',
            'venv', '.venv', 'env', '.env', 'build', 'dist',
            '.min.js', '.min.css', 'vendor', 'coverage'
        ]
        
        path_str = str(file_path).lower()
        return not any(pattern in path_str for pattern in ignore_patterns)
    
    async def _analyze_requirements_compliance(
        self, 
        request: AIAnalysisRequest, 
        source_code: Dict[str, str], 
        websocket, 
        analysis_id: str
    ) -> List[AnalysisIssue]:
        """Analyze if the code meets the specified requirements."""
        issues = []
        
        if not request.requirements:
            return issues
        
        # Prepare analysis prompt
        code_summary = self._summarize_code(source_code)
        
        for i, requirement in enumerate(request.requirements):
            await self._send_progress(
                websocket, analysis_id,
                f"Checking requirement {i+1}/{len(request.requirements)}",
                0.3 + (i / len(request.requirements)) * 0.5
            )
            
            prompt = f"""
Analyze the following code implementation against this requirement:

Requirement: {requirement}

Code Summary:
{code_summary}

Please evaluate:
1. Is this requirement implemented in the code?
2. Is the implementation complete and correct?
3. Are there any missing components or issues?
4. Rate the compliance (Complete, Partial, Missing, Unknown)

Provide specific findings with file references if possible.
"""
            
            try:
                ai_response = await self._call_ai_model(request.model_name, prompt, request.max_tokens)
                
                # Parse AI response and create issues
                compliance_issues = self._parse_requirements_response(ai_response, requirement)
                issues.extend(compliance_issues)
                
            except Exception as e:
                logger.error(f"AI analysis failed for requirement: {str(e)}")
                issues.append(AnalysisIssue(
                    tool='ai-analyzer',
                    severity=SeverityLevel.MEDIUM,
                    confidence='LOW',
                    file_path='',
                    message=f"Could not analyze requirement: {requirement[:100]}...",
                    description=f"AI analysis failed: {str(e)}",
                    rule_id='ai_analysis_failed'
                ))
            
            # Rate limiting
            await asyncio.sleep(1)
        
        return issues
    
    async def _perform_code_review(
        self, 
        request: AIAnalysisRequest, 
        source_code: Dict[str, str], 
        websocket, 
        analysis_id: str
    ) -> List[AnalysisIssue]:
        """Perform AI-powered code review."""
        issues = []
        
        file_count = len(source_code)
        for i, (file_path, content) in enumerate(source_code.items()):
            await self._send_progress(
                websocket, analysis_id,
                f"Reviewing file {i+1}/{file_count}: {file_path}",
                0.3 + (i / file_count) * 0.5
            )
            
            # Skip very large files
            if len(content) > 10000:
                content = content[:10000] + "\n... (truncated)"
            
            prompt = f"""
Perform a comprehensive code review of this file:

File: {file_path}

```
{content}
```

Please identify:
1. Code quality issues (readability, maintainability)
2. Potential bugs or logic errors
3. Performance concerns
4. Security vulnerabilities
5. Best practice violations
6. Documentation issues

For each issue, provide:
- Severity (High, Medium, Low)
- Line number if applicable
- Description of the issue
- Suggested fix
"""
            
            try:
                ai_response = await self._call_ai_model(request.model_name, prompt, request.max_tokens)
                
                # Parse AI response and create issues
                review_issues = self._parse_code_review_response(ai_response, file_path)
                issues.extend(review_issues)
                
            except Exception as e:
                logger.error(f"Code review failed for {file_path}: {str(e)}")
                
            # Rate limiting
            await asyncio.sleep(1)
        
        return issues
    
    async def _perform_security_audit(
        self, 
        request: AIAnalysisRequest, 
        source_code: Dict[str, str], 
        websocket, 
        analysis_id: str
    ) -> List[AnalysisIssue]:
        """Perform AI-powered security audit."""
        issues = []
        
        # Combine all source code for security analysis
        all_code = "\n\n".join([f"# {path}\n{content}" for path, content in source_code.items()])
        
        # Truncate if too large
        if len(all_code) > 20000:
            all_code = all_code[:20000] + "\n... (truncated)"
        
        prompt = f"""
Perform a security audit of this application code:

```
{all_code}
```

Focus on identifying:
1. SQL injection vulnerabilities
2. Cross-site scripting (XSS) risks
3. Authentication and authorization issues
4. Data validation problems
5. Insecure direct object references
6. Cryptographic issues
7. Information disclosure
8. Input validation failures

For each security issue found:
- Classify severity (Critical, High, Medium, Low)
- Identify the vulnerable code location
- Explain the potential impact
- Provide remediation guidance
"""
        
        try:
            await self._send_progress(websocket, analysis_id, "Running security audit", 0.5)
            ai_response = await self._call_ai_model(request.model_name, prompt, request.max_tokens)
            
            # Parse AI response and create issues
            security_issues = self._parse_security_response(ai_response)
            issues.extend(security_issues)
            
        except Exception as e:
            logger.error(f"Security audit failed: {str(e)}")
        
        return issues
    
    async def _review_architecture(
        self, 
        request: AIAnalysisRequest, 
        source_code: Dict[str, str], 
        websocket, 
        analysis_id: str
    ) -> List[AnalysisIssue]:
        """Review application architecture."""
        issues = []
        
        # Create architecture overview
        file_structure = list(source_code.keys())
        code_summary = self._summarize_code(source_code)
        
        prompt = f"""
Review the architecture of this application:

File Structure:
{chr(10).join(file_structure)}

Code Summary:
{code_summary}

Please analyze:
1. Overall architecture pattern (MVC, layered, microservices, etc.)
2. Separation of concerns
3. Code organization and structure
4. Dependency management
5. Scalability considerations
6. Maintainability issues
7. Design pattern usage
8. SOLID principles adherence

Identify architectural issues and provide recommendations.
"""
        
        try:
            await self._send_progress(websocket, analysis_id, "Reviewing architecture", 0.5)
            ai_response = await self._call_ai_model(request.model_name, prompt, request.max_tokens)
            
            # Parse AI response and create issues
            arch_issues = self._parse_architecture_response(ai_response)
            issues.extend(arch_issues)
            
        except Exception as e:
            logger.error(f"Architecture review failed: {str(e)}")
        
        return issues
    
    async def _check_documentation(
        self, 
        request: AIAnalysisRequest, 
        source_code: Dict[str, str], 
        websocket, 
        analysis_id: str
    ) -> List[AnalysisIssue]:
        """Check documentation quality and completeness."""
        issues = []
        
        # Find documentation files
        doc_files = {path: content for path, content in source_code.items() 
                    if any(doc_ext in path.lower() for doc_ext in ['.md', '.txt', '.rst', 'readme'])}
        
        # Find code files that should have documentation
        code_files = {path: content for path, content in source_code.items() 
                     if any(ext in path for ext in ['.py', '.js', '.html'])}
        
        prompt = f"""
Analyze the documentation of this project:

Documentation Files:
{chr(10).join([f"- {path}" for path in doc_files.keys()])}

Code Files:
{chr(10).join([f"- {path}" for path in code_files.keys()])}

Sample Documentation Content:
{chr(10).join([f"## {path}\\n{content[:500]}..." for path, content in list(doc_files.items())[:3]])}

Please evaluate:
1. Documentation completeness
2. Documentation quality and clarity
3. Missing documentation for key components
4. Code comments and inline documentation
5. API documentation (if applicable)
6. Setup and installation instructions
7. Usage examples

Identify documentation gaps and quality issues.
"""
        
        try:
            await self._send_progress(websocket, analysis_id, "Checking documentation", 0.5)
            ai_response = await self._call_ai_model(request.model_name, prompt, request.max_tokens)
            
            # Parse AI response and create issues
            doc_issues = self._parse_documentation_response(ai_response)
            issues.extend(doc_issues)
            
        except Exception as e:
            logger.error(f"Documentation check failed: {str(e)}")
        
        return issues
    
    def _summarize_code(self, source_code: Dict[str, str]) -> str:
        """Create a summary of the source code."""
        summary_parts = []
        
        for file_path, content in source_code.items():
            # Limit content length for summary
            content_preview = content[:500] if len(content) > 500 else content
            summary_parts.append(f"File: {file_path}\n{content_preview}")
            
            if len(summary_parts) >= 10:  # Limit number of files in summary
                break
        
        return "\n\n".join(summary_parts)
    
    async def _call_ai_model(self, model_name: str, prompt: str, max_tokens: int) -> str:
        """Call OpenRouter AI model."""
        if not self.openrouter_api_key:
            raise Exception("OpenRouter API key not configured")
        
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/yourusername/analyzer",
            "X-Title": "Code Analyzer"
        }
        
        data = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert code reviewer and software architect. Provide detailed, actionable feedback."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                f"{self.openrouter_base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            logger.error(f"AI model call failed: {str(e)}")
            raise
    
    def _parse_requirements_response(self, ai_response: str, requirement: str) -> List[AnalysisIssue]:
        """Parse AI response for requirements compliance."""
        issues = []
        
        # Simple parsing - in a real implementation, you'd want more sophisticated parsing
        if "missing" in ai_response.lower() or "not implemented" in ai_response.lower():
            issues.append(AnalysisIssue(
                tool='ai-analyzer',
                severity=SeverityLevel.HIGH,
                confidence='MEDIUM',
                file_path='',
                message=f"Requirement not fully implemented: {requirement[:100]}...",
                description=ai_response[:500],
                rule_id='requirement_missing',
                fix_suggestion="Implement the missing requirement components"
            ))
        elif "partial" in ai_response.lower() or "incomplete" in ai_response.lower():
            issues.append(AnalysisIssue(
                tool='ai-analyzer',
                severity=SeverityLevel.MEDIUM,
                confidence='MEDIUM',
                file_path='',
                message=f"Requirement partially implemented: {requirement[:100]}...",
                description=ai_response[:500],
                rule_id='requirement_partial',
                fix_suggestion="Complete the partial implementation"
            ))
        
        return issues
    
    def _parse_code_review_response(self, ai_response: str, file_path: str) -> List[AnalysisIssue]:
        """Parse AI response for code review issues."""
        issues = []
        
        # Extract issues from AI response (simplified parsing)
        lines = ai_response.split('\n')
        current_issue = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if any(severity in line.lower() for severity in ['high', 'medium', 'low', 'critical']):
                if current_issue:
                    # Create issue from current_issue
                    severity_map = {
                        'critical': SeverityLevel.CRITICAL,
                        'high': SeverityLevel.HIGH,
                        'medium': SeverityLevel.MEDIUM,
                        'low': SeverityLevel.LOW
                    }
                    
                    severity = SeverityLevel.MEDIUM
                    for sev_key, sev_val in severity_map.items():
                        if sev_key in line.lower():
                            severity = sev_val
                            break
                    
                    issues.append(AnalysisIssue(
                        tool='ai-analyzer',
                        severity=severity,
                        confidence='MEDIUM',
                        file_path=file_path,
                        message=current_issue.get('message', line),
                        description=current_issue.get('description', ''),
                        rule_id='code_review_issue',
                        fix_suggestion=current_issue.get('fix', '')
                    ))
                
                current_issue = {'message': line}
            else:
                if current_issue:
                    if 'description' not in current_issue:
                        current_issue['description'] = line
                    elif 'fix' not in current_issue:
                        current_issue['fix'] = line
        
        return issues
    
    def _parse_security_response(self, ai_response: str) -> List[AnalysisIssue]:
        """Parse AI response for security issues."""
        issues = []
        
        # Look for security-related keywords
        security_keywords = [
            'sql injection', 'xss', 'csrf', 'authentication', 'authorization',
            'validation', 'encryption', 'security', 'vulnerability'
        ]
        
        lines = ai_response.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in security_keywords):
                severity = SeverityLevel.HIGH
                if 'critical' in line_lower:
                    severity = SeverityLevel.CRITICAL
                elif 'medium' in line_lower or 'moderate' in line_lower:
                    severity = SeverityLevel.MEDIUM
                elif 'low' in line_lower or 'minor' in line_lower:
                    severity = SeverityLevel.LOW
                
                issues.append(AnalysisIssue(
                    tool='ai-analyzer',
                    severity=severity,
                    confidence='MEDIUM',
                    file_path='',
                    message=line.strip(),
                    description=line.strip(),
                    rule_id='security_issue'
                ))
        
        return issues
    
    def _parse_architecture_response(self, ai_response: str) -> List[AnalysisIssue]:
        """Parse AI response for architecture issues."""
        issues = []
        
        # Look for architecture-related issues
        arch_keywords = [
            'coupling', 'cohesion', 'separation', 'solid', 'pattern',
            'architecture', 'design', 'maintainability', 'scalability'
        ]
        
        lines = ai_response.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in arch_keywords):
                issues.append(AnalysisIssue(
                    tool='ai-analyzer',
                    severity=SeverityLevel.MEDIUM,
                    confidence='MEDIUM',
                    file_path='',
                    message=line.strip(),
                    description=line.strip(),
                    rule_id='architecture_issue'
                ))
        
        return issues
    
    def _parse_documentation_response(self, ai_response: str) -> List[AnalysisIssue]:
        """Parse AI response for documentation issues."""
        issues = []
        
        # Look for documentation issues
        doc_keywords = [
            'missing', 'incomplete', 'unclear', 'documentation',
            'comment', 'readme', 'api doc', 'example'
        ]
        
        lines = ai_response.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in doc_keywords):
                issues.append(AnalysisIssue(
                    tool='ai-analyzer',
                    severity=SeverityLevel.LOW,
                    confidence='MEDIUM',
                    file_path='',
                    message=line.strip(),
                    description=line.strip(),
                    rule_id='documentation_issue'
                ))
        
        return issues
    
    def _generate_summary(self, issues: List[AnalysisIssue], request: AIAnalysisRequest) -> Dict[str, Any]:
        """Generate AI analysis summary."""
        summary = {
            'analysis_type': request.analysis_focus,
            'total_issues': len(issues),
            'by_severity': {},
            'by_category': {},
            'ai_model_used': request.model_name,
            'recommendations': []
        }
        
        # Count by severity
        for issue in issues:
            severity = issue.severity.value
            summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
            
            # Count by rule type
            rule_id = issue.rule_id
            summary['by_category'][rule_id] = summary['by_category'].get(rule_id, 0) + 1
        
        # Generate recommendations based on analysis type
        if request.analysis_focus == 'requirements_check':
            if summary['by_severity'].get('high', 0) > 0:
                summary['recommendations'].append("Address missing or incomplete requirements")
        elif request.analysis_focus == 'security_audit':
            if summary['by_severity'].get('critical', 0) > 0:
                summary['recommendations'].append("Immediately address critical security vulnerabilities")
        
        return summary
    
    async def _send_progress(self, websocket, analysis_id: str, message: str, progress: float):
        """Send progress update to client."""
        try:
            progress_update = ProgressUpdate(
                analysis_id=analysis_id,
                stage="analyzing",
                progress=progress,
                message=message
            )
            
            ws_message = WebSocketMessage(
                type=MessageType.PROGRESS_UPDATE,
                data=progress_update.to_dict()
            )
            
            await websocket.send(ws_message.to_json())
        except Exception as e:
            logger.error(f"Failed to send progress: {str(e)}")


async def handle_client(websocket, path):
    """Handle incoming WebSocket connections."""
    analyzer = AIAnalyzer()
    logger.info(f"New client connected: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            try:
                # Parse incoming message
                ws_message = WebSocketMessage.from_json(message)
                
                if ws_message.type == MessageType.ANALYSIS_REQUEST:
                    # Parse analysis request
                    request = create_request_from_dict(ws_message.data)
                    
                    # Only handle AI analysis requests
                    if isinstance(request, AIAnalysisRequest):
                        # Perform analysis
                        result = await analyzer.analyze(request, websocket)
                        
                        # Send result back
                        response = WebSocketMessage(
                            type=MessageType.ANALYSIS_RESULT,
                            data=result.to_dict(),
                            correlation_id=ws_message.id
                        )
                        
                        await websocket.send(response.to_json())
                    else:
                        # Not a supported request type
                        error_msg = WebSocketMessage(
                            type=MessageType.ERROR,
                            data={
                                'code': 'UNSUPPORTED_REQUEST',
                                'message': 'This service only handles AI analysis requests'
                            },
                            correlation_id=ws_message.id
                        )
                        await websocket.send(error_msg.to_json())
                
                elif ws_message.type == MessageType.HEARTBEAT:
                    # Respond to heartbeat
                    response = WebSocketMessage(
                        type=MessageType.HEARTBEAT,
                        data={'status': 'healthy', 'service': 'ai-analyzer'}
                    )
                    await websocket.send(response.to_json())
                    
            except json.JSONDecodeError:
                logger.error("Received invalid JSON message")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")


def main():
    """Start the AI analyzer service."""
    host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
    port = int(os.getenv('WEBSOCKET_PORT', 8004))
    
    logger.info(f"Starting AI Analyzer service on {host}:{port}")
    
    start_server = websockets.serve(handle_client, host, port)
    
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
