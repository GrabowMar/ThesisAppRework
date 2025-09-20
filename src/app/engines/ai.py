"""
AI Analysis Tools
================

AI-powered analysis tools that run in the ai-analyzer container.
Includes code review, requirements analysis, and intelligent security assessment.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import (
    BaseAnalysisTool, ToolResult, Finding, ToolStatus, Severity, Confidence,
    analysis_tool
)

logger = __import__('logging').getLogger(__name__)

@analysis_tool
class AICodeReviewTool(BaseAnalysisTool):
    """AI-powered code review and analysis."""
    
    @property
    def name(self) -> str:
        return "ai-review"
    
    @property
    def display_name(self) -> str:
        return "AI Code Review"
    
    @property
    def description(self) -> str:
        return "AI-powered code review for security, quality, and best practices"
    
    @property
    def tags(self) -> Set[str]:
        return {"ai", "code_review", "security", "quality", "intelligent"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"python", "javascript", "typescript", "java", "cpp", "csharp", "web"}
    
    def is_available(self) -> bool:
        """Check if AI analysis is available."""
        # AI tools are integrated into the ai-analyzer container
        return True
    
    def get_version(self) -> Optional[str]:
        """Get AI analyzer version."""
        return "1.0.0"
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run AI-powered code analysis."""
        start_time = time.time()
        
        try:
            # Collect code files for analysis
            code_files = self._collect_code_files(target_path)
            
            if not code_files:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SKIPPED.value,
                    metadata={'reason': 'No code files found for analysis'},
                    duration_seconds=time.time() - start_time
                )
            
            findings = []
            metadata = {
                'files_analyzed': len(code_files),
                'file_types': list(set(f.suffix for f in code_files))
            }
            
            # Analyze each file
            for file_path in code_files[:10]:  # Limit to prevent timeouts
                try:
                    file_findings = self._analyze_file(file_path, target_path)
                    findings.extend(file_findings)
                except Exception as e:
                    self.logger.warning(f"Failed to analyze {file_path}: {e}")
                    continue
            
            # Perform holistic analysis
            holistic_findings = self._holistic_analysis(target_path, code_files)
            findings.extend(holistic_findings)
            
            status = ToolStatus.SUCCESS.value
            if findings:
                status = ToolStatus.ISSUES_FOUND.value
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings[:self.config.max_issues],
                metadata=metadata,
                duration_seconds=time.time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"AI analysis failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=time.time() - start_time
            )
    
    def _collect_code_files(self, target_path: Path) -> List[Path]:
        """Collect code files for analysis."""
        code_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs'}
        code_files = []
        
        for ext in code_extensions:
            code_files.extend(target_path.rglob(f'*{ext}'))
        
        # Filter out common non-source directories
        excluded_dirs = {'node_modules', '__pycache__', '.git', 'venv', '.venv', 'build', 'dist'}
        filtered_files = []
        
        for file_path in code_files:
            if not any(excluded_dir in file_path.parts for excluded_dir in excluded_dirs):
                filtered_files.append(file_path)
        
        return filtered_files
    
    def _analyze_file(self, file_path: Path, base_path: Path) -> List[Finding]:
        """Analyze a single file for issues."""
        findings = []
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Get relative path
            try:
                rel_path = str(file_path.relative_to(base_path))
            except ValueError:
                rel_path = str(file_path)
            
            # Perform various AI-powered checks
            findings.extend(self._check_security_patterns(content, rel_path))
            findings.extend(self._check_code_quality(content, rel_path))
            findings.extend(self._check_best_practices(content, rel_path))
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze file {file_path}: {e}")
        
        return findings
    
    def _check_security_patterns(self, content: str, file_path: str) -> List[Finding]:
        """Check for security anti-patterns."""
        findings = []
        lines = content.split('\n')
        
        # Security patterns to check
        security_patterns = [
            {
                'pattern': 'password',
                'severity': Severity.HIGH.value,
                'title': 'Potential hardcoded password',
                'description': 'Hardcoded password detected in source code'
            },
            {
                'pattern': 'api_key',
                'severity': Severity.HIGH.value,
                'title': 'Potential hardcoded API key',
                'description': 'Hardcoded API key detected in source code'
            },
            {
                'pattern': 'secret',
                'severity': Severity.MEDIUM.value,
                'title': 'Potential hardcoded secret',
                'description': 'Hardcoded secret detected in source code'
            },
            {
                'pattern': 'eval(',
                'severity': Severity.HIGH.value,
                'title': 'Dangerous eval() usage',
                'description': 'Use of eval() can lead to code injection vulnerabilities'
            },
            {
                'pattern': 'exec(',
                'severity': Severity.HIGH.value,
                'title': 'Dangerous exec() usage',
                'description': 'Use of exec() can lead to code injection vulnerabilities'
            }
        ]
        
        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            for pattern_info in security_patterns:
                if pattern_info['pattern'] in line_lower:
                    findings.append(Finding(
                        tool=self.name,
                        severity=pattern_info['severity'],
                        confidence=Confidence.MEDIUM.value,
                        title=pattern_info['title'],
                        description=pattern_info['description'],
                        file_path=file_path,
                        line_number=i,
                        category="security_pattern",
                        rule_id=f"ai_security_{pattern_info['pattern']}",
                        tags=['ai', 'security', 'pattern_detection'],
                        raw_data={'line': line.strip(), 'pattern': pattern_info['pattern']}
                    ))
        
        return findings
    
    def _check_code_quality(self, content: str, file_path: str) -> List[Finding]:
        """Check for code quality issues."""
        findings = []
        lines = content.split('\n')
        
        # Check for very long functions (simple heuristic)
        function_length = 0
        function_start_line = None
        
        for i, line in enumerate(lines, 1):
            stripped_line = line.strip()
            
            # Simple function detection (Python/JavaScript)
            if (stripped_line.startswith('def ') or 
                stripped_line.startswith('function ') or
                'function(' in stripped_line):
                if function_length > 50:  # Previous function was too long
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.MEDIUM.value,
                        confidence=Confidence.LOW.value,
                        title="Long function detected",
                        description=f"Function starting at line {function_start_line} is {function_length} lines long",
                        file_path=file_path,
                        line_number=function_start_line,
                        category="code_quality",
                        rule_id="ai_long_function",
                        tags=['ai', 'quality', 'maintainability'],
                        raw_data={'function_length': function_length}
                    ))
                
                function_start_line = i
                function_length = 0
            elif stripped_line:
                function_length += 1
        
        # Check for duplicated code patterns (simple)
        line_counts = {}
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if len(stripped) > 20:  # Only check substantial lines
                if stripped in line_counts:
                    line_counts[stripped].append(i)
                else:
                    line_counts[stripped] = [i]
        
        for line, occurrences in line_counts.items():
            if len(occurrences) > 2:  # More than 2 occurrences
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.LOW.value,
                    confidence=Confidence.LOW.value,
                    title="Potential code duplication",
                    description=f"Line appears {len(occurrences)} times: {line[:50]}...",
                    file_path=file_path,
                    line_number=occurrences[0],
                    category="code_duplication",
                    rule_id="ai_code_duplication",
                    tags=['ai', 'quality', 'duplication'],
                    raw_data={'occurrences': occurrences, 'line': line}
                ))
        
        return findings
    
    def _check_best_practices(self, content: str, file_path: str) -> List[Finding]:
        """Check for best practice violations."""
        findings = []
        
        # Check file size
        if len(content) > 10000:  # More than 10k characters
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM.value,
                confidence=Confidence.HIGH.value,
                title="Large file detected",
                description=f"File is {len(content)} characters long, consider splitting into smaller modules",
                file_path=file_path,
                category="file_size",
                rule_id="ai_large_file",
                tags=['ai', 'maintainability', 'best_practices'],
                raw_data={'file_size': len(content)}
            ))
        
        # Check for missing documentation
        lines = content.split('\n')
        has_docstring = False
        
        for line in lines[:10]:  # Check first 10 lines
            if '"""' in line or "'''" in line or line.strip().startswith('#'):
                has_docstring = True
                break
        
        if not has_docstring and len(lines) > 20:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW.value,
                confidence=Confidence.MEDIUM.value,
                title="Missing documentation",
                description="No documentation or comments found in the beginning of the file",
                file_path=file_path,
                category="documentation",
                rule_id="ai_missing_docs",
                tags=['ai', 'documentation', 'best_practices'],
                raw_data={'file_length': len(lines)}
            ))
        
        return findings
    
    def _holistic_analysis(self, target_path: Path, code_files: List[Path]) -> List[Finding]:
        """Perform holistic analysis of the entire codebase."""
        findings = []
        
        try:
            # Analyze project structure
            structure_findings = self._analyze_project_structure(target_path, code_files)
            findings.extend(structure_findings)
            
            # Analyze dependencies (if present)
            dependency_findings = self._analyze_dependencies(target_path)
            findings.extend(dependency_findings)
            
        except Exception as e:
            self.logger.warning(f"Holistic analysis failed: {e}")
        
        return findings
    
    def _analyze_project_structure(self, target_path: Path, code_files: List[Path]) -> List[Finding]:
        """Analyze overall project structure."""
        findings = []
        
        # Check for proper separation of concerns
        file_types = {}
        for file_path in code_files:
            ext = file_path.suffix
            if ext in file_types:
                file_types[ext] += 1
            else:
                file_types[ext] = 1
        
        # If only one file type and many files, suggest better organization
        if len(file_types) == 1 and len(code_files) > 5:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW.value,
                confidence=Confidence.MEDIUM.value,
                title="Monolithic structure detected",
                description=f"Project contains only {list(file_types.keys())[0]} files. Consider adding configuration, documentation, or test files",
                file_path=".",
                category="project_structure",
                rule_id="ai_monolithic_structure",
                tags=['ai', 'architecture', 'best_practices'],
                raw_data={'file_types': file_types}
            ))
        
        # Check for test files
        test_files = [f for f in code_files if 'test' in f.name.lower() or f.name.startswith('test_')]
        if not test_files and len(code_files) > 3:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM.value,
                confidence=Confidence.HIGH.value,
                title="No test files detected",
                description="No test files found in the project. Consider adding unit tests for better code quality",
                file_path=".",
                category="testing",
                rule_id="ai_no_tests",
                tags=['ai', 'testing', 'best_practices'],
                raw_data={'code_files_count': len(code_files)}
            ))
        
        return findings
    
    def _analyze_dependencies(self, target_path: Path) -> List[Finding]:
        """Analyze project dependencies."""
        findings = []
        
        # Check for dependency files
        dependency_files = [
            target_path / "requirements.txt",
            target_path / "package.json",
            target_path / "pom.xml",
            target_path / "Cargo.toml"
        ]
        
        found_deps = [f for f in dependency_files if f.exists()]
        
        if not found_deps:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW.value,
                confidence=Confidence.MEDIUM.value,
                title="No dependency management files found",
                description="No dependency management files (requirements.txt, package.json, etc.) found",
                file_path=".",
                category="dependency_management",
                rule_id="ai_no_deps",
                tags=['ai', 'dependencies', 'best_practices'],
                raw_data={'checked_files': [str(f) for f in dependency_files]}
            ))
        
        return findings

@analysis_tool
class AIRequirementsAnalyzer(BaseAnalysisTool):
    """AI-powered requirements and specification analysis."""
    
    @property
    def name(self) -> str:
        return "ai-requirements"
    
    @property
    def display_name(self) -> str:
        return "AI Requirements Analyzer"
    
    @property
    def description(self) -> str:
        return "AI-powered analysis of requirements and specifications"
    
    @property
    def tags(self) -> Set[str]:
        return {"ai", "requirements", "specifications", "analysis"}
    
    @property
    def supported_languages(self) -> Set[str]:
        return {"markdown", "text", "documentation"}
    
    def is_available(self) -> bool:
        """Check if requirements analysis is available."""
        return True
    
    def get_version(self) -> Optional[str]:
        """Get requirements analyzer version."""
        return "1.0.0"
    
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run requirements analysis."""
        start_time = time.time()
        
        try:
            # Look for documentation files
            doc_files = self._find_documentation_files(target_path)
            
            if not doc_files:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SKIPPED.value,
                    metadata={'reason': 'No documentation files found'},
                    duration_seconds=time.time() - start_time
                )
            
            findings = []
            metadata = {
                'doc_files_found': len(doc_files),
                'file_types': list(set(f.suffix for f in doc_files))
            }
            
            # Analyze each documentation file
            for doc_file in doc_files:
                try:
                    file_findings = self._analyze_documentation(doc_file, target_path)
                    findings.extend(file_findings)
                except Exception as e:
                    self.logger.warning(f"Failed to analyze {doc_file}: {e}")
                    continue
            
            status = ToolStatus.SUCCESS.value
            if findings:
                status = ToolStatus.ISSUES_FOUND.value
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                findings=findings[:self.config.max_issues],
                metadata=metadata,
                duration_seconds=time.time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"Requirements analysis failed: {e}")
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR.value,
                error=str(e),
                duration_seconds=time.time() - start_time
            )
    
    def _find_documentation_files(self, target_path: Path) -> List[Path]:
        """Find documentation files."""
        doc_extensions = {'.md', '.txt', '.rst', '.doc', '.docx'}
        doc_files = []
        
        for ext in doc_extensions:
            doc_files.extend(target_path.rglob(f'*{ext}'))
        
        # Look for common documentation file names
        common_names = ['README', 'REQUIREMENTS', 'SPECIFICATION', 'DESIGN', 'API']
        for name in common_names:
            doc_files.extend(target_path.rglob(f'{name}*'))
        
        return list(set(doc_files))  # Remove duplicates
    
    def _analyze_documentation(self, doc_file: Path, base_path: Path) -> List[Finding]:
        """Analyze a documentation file."""
        findings = []
        
        try:
            with open(doc_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            try:
                rel_path = str(doc_file.relative_to(base_path))
            except ValueError:
                rel_path = str(doc_file)
            
            # Check for completeness
            findings.extend(self._check_documentation_completeness(content, rel_path))
            
            # Check for clarity and structure
            findings.extend(self._check_documentation_clarity(content, rel_path))
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze documentation {doc_file}: {e}")
        
        return findings
    
    def _check_documentation_completeness(self, content: str, file_path: str) -> List[Finding]:
        """Check if documentation is complete."""
        findings = []
        
        # Check length
        if len(content) < 100:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM.value,
                confidence=Confidence.HIGH.value,
                title="Insufficient documentation",
                description=f"Documentation file is very short ({len(content)} characters)",
                file_path=file_path,
                category="documentation_completeness",
                rule_id="ai_short_docs",
                tags=['ai', 'documentation', 'completeness'],
                raw_data={'content_length': len(content)}
            ))
        
        # Check for key sections (for README files)
        if 'readme' in file_path.lower():
            required_sections = ['installation', 'usage', 'example']
            missing_sections = []
            
            content_lower = content.lower()
            for section in required_sections:
                if section not in content_lower:
                    missing_sections.append(section)
            
            if missing_sections:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.LOW.value,
                    confidence=Confidence.MEDIUM.value,
                    title="Missing README sections",
                    description=f"README is missing common sections: {', '.join(missing_sections)}",
                    file_path=file_path,
                    category="documentation_structure",
                    rule_id="ai_missing_readme_sections",
                    tags=['ai', 'documentation', 'structure'],
                    raw_data={'missing_sections': missing_sections}
                ))
        
        return findings
    
    def _check_documentation_clarity(self, content: str, file_path: str) -> List[Finding]:
        """Check documentation clarity and structure."""
        findings = []
        
        lines = content.split('\n')
        
        # Check for headers (markdown)
        has_headers = any(line.startswith('#') for line in lines)
        if not has_headers and len(lines) > 10:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW.value,
                confidence=Confidence.MEDIUM.value,
                title="No structured headers found",
                description="Document lacks structured headers for better readability",
                file_path=file_path,
                category="documentation_structure",
                rule_id="ai_no_headers",
                tags=['ai', 'documentation', 'readability'],
                raw_data={'line_count': len(lines)}
            ))
        
        # Check for very long paragraphs
        paragraph_lengths = []
        current_paragraph = 0
        
        for line in lines:
            if line.strip():
                current_paragraph += len(line)
            else:
                if current_paragraph > 0:
                    paragraph_lengths.append(current_paragraph)
                    current_paragraph = 0
        
        if paragraph_lengths and max(paragraph_lengths) > 1000:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW.value,
                confidence=Confidence.LOW.value,
                title="Very long paragraphs detected",
                description="Document contains very long paragraphs that may be hard to read",
                file_path=file_path,
                category="documentation_readability",
                rule_id="ai_long_paragraphs",
                tags=['ai', 'documentation', 'readability'],
                raw_data={'max_paragraph_length': max(paragraph_lengths)}
            ))
        
        return findings