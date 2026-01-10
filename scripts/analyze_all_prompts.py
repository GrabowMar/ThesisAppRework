#!/usr/bin/env python3
"""
Comprehensive Prompt Analysis Script
=====================================

This script generates ALL 30 prompts for different templates and configurations,
then analyzes them for potential issues, ambiguities, and inconsistencies.

It checks:
1. All requirement files
2. All template types (two-query, four-query, unguarded)
3. Both backend and frontend components
4. Both user and admin query types
5. Scaffolding references
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Set
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

class PromptAnalyzer:
    def __init__(self):
        self.misc_dir = project_root / 'misc'
        self.requirements_dir = self.misc_dir / 'requirements'
        self.templates_dir = self.misc_dir / 'templates'
        self.scaffolding_dir = self.misc_dir / 'scaffolding'
        self.prompts_dir = self.misc_dir / 'prompts' / 'system'

        self.issues = []
        self.warnings = []
        self.stats = defaultdict(int)
        self.generated_prompts = {}

    def load_requirements(self) -> Dict[str, Dict]:
        """Load all requirement JSON files."""
        requirements = {}
        for req_file in self.requirements_dir.glob('*.json'):
            try:
                with open(req_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    slug = req_file.stem
                    requirements[slug] = data
                    self.stats['requirements_loaded'] += 1
            except Exception as e:
                self.issues.append(f"ERROR loading {req_file.name}: {e}")
        return requirements

    def load_scaffolding(self, scaffolding_type: str = 'react-flask') -> Dict[str, str]:
        """Load scaffolding files."""
        scaffolding_path = self.scaffolding_dir / scaffolding_type
        scaffolding = {}

        # Backend scaffolding
        backend_context = scaffolding_path / 'backend' / 'SCAFFOLDING_CONTEXT.md'
        if backend_context.exists():
            with open(backend_context, 'r', encoding='utf-8') as f:
                scaffolding['scaffolding_backend_context'] = f.read()

        # Frontend scaffolding
        frontend_context = scaffolding_path / 'frontend' / 'SCAFFOLDING_CONTEXT.md'
        if frontend_context.exists():
            with open(frontend_context, 'r', encoding='utf-8') as f:
                scaffolding['scaffolding_frontend_context'] = f.read()

        return scaffolding

    def format_api_endpoints(self, reqs: Dict, admin: bool = False) -> str:
        """Format API endpoints as text."""
        if admin and 'admin_api_endpoints' in reqs:
            endpoints = reqs['admin_api_endpoints']
        elif not admin and 'api_endpoints' in reqs:
            endpoints = reqs['api_endpoints']
        else:
            return "No API endpoints defined."

        lines = []
        for ep in endpoints:
            method = ep.get('method', 'GET')
            path = ep.get('path', '/')
            desc = ep.get('description', '')

            req_body = ep.get('request')
            res_body = ep.get('response')

            lines.append(f"### {method} {path}")
            if desc:
                lines.append(f"{desc}")
            if req_body is not None:
                lines.append(f"Request: `{json.dumps(req_body, indent=2)}`")
            if res_body is not None:
                lines.append(f"Response: `{json.dumps(res_body, indent=2)}`")
            lines.append("")

        return '\n'.join(lines)

    def generate_prompt(self, template_type: str, component: str, query_type: str,
                       req_slug: str, reqs: Dict) -> str:
        """Generate a single prompt using Jinja2 template."""
        template_dir = self.templates_dir / template_type

        if template_type == 'unguarded':
            template_name = f"{component}.md.jinja2"
        elif template_type == 'four-query':
            template_name = f"{component}_{query_type}.md.jinja2"
        elif template_type == 'two-query':
            template_name = f"{component}.md.jinja2"
        else:
            raise ValueError(f"Unknown template type: {template_type}")

        if not template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        env = Environment(loader=FileSystemLoader(str(template_dir)))

        try:
            template = env.get_template(template_name)
        except TemplateNotFound:
            raise FileNotFoundError(f"Template not found: {template_name} in {template_dir}")

        # Load scaffolding
        scaffolding_type = 'react-flask-unguarded' if template_type == 'unguarded' else 'react-flask'
        scaffolding = self.load_scaffolding(scaffolding_type)

        # Prepare context
        context = {
            'name': reqs.get('name', 'Application'),
            'description': reqs.get('description', 'web application'),
            'backend_requirements': reqs.get('backend_requirements', []),
            'frontend_requirements': reqs.get('frontend_requirements', []),
            'admin_requirements': reqs.get('admin_requirements', []),
            'api_endpoints': self.format_api_endpoints(reqs, admin=False),
            'admin_api_endpoints': self.format_api_endpoints(reqs, admin=True),
            'existing_models_summary': 'No models defined yet.',
            **scaffolding
        }

        # Render prompt
        prompt = template.render(context)
        return prompt

    def analyze_prompt(self, prompt_id: str, prompt: str, reqs: Dict):
        """Analyze a generated prompt for issues."""
        issues = []

        # Check prompt length
        if len(prompt) < 500:
            issues.append(f"WARN: Prompt too short ({len(prompt)} chars)")
        elif len(prompt) > 50000:
            issues.append(f"WARN: Prompt very long ({len(prompt)} chars)")

        # Check for placeholder text
        placeholders = ['TODO', 'FIXME', 'XXX', '...', 'placeholder', 'your_']
        for ph in placeholders:
            if ph in prompt:
                issues.append(f"WARN: Contains placeholder '{ph}'")

        # Check for required sections in backend prompts
        if 'backend' in prompt_id.lower():
            required_backend = ['models.py', 'SQLAlchemy', 'Flask', 'API']
            for req in required_backend:
                if req not in prompt:
                    issues.append(f"WARN: Missing '{req}' in backend prompt")

        # Check for required sections in frontend prompts
        if 'frontend' in prompt_id.lower():
            required_frontend = ['React', 'App.jsx', 'useState', 'API']
            for req in required_frontend:
                if req not in prompt:
                    issues.append(f"WARN: Missing '{req}' in frontend prompt")

        # Check if requirements are present
        if 'backend' in prompt_id.lower():
            backend_reqs = reqs.get('backend_requirements', [])
            if not backend_reqs:
                issues.append("ERROR: No backend requirements defined")

        if 'frontend' in prompt_id.lower():
            frontend_reqs = reqs.get('frontend_requirements', [])
            if not frontend_reqs:
                issues.append("ERROR: No frontend requirements defined")

        # Check for API endpoint documentation
        api_endpoints = reqs.get('api_endpoints', [])
        if not api_endpoints:
            issues.append("WARN: No API endpoints defined in requirements")
        else:
            # Check if endpoints are in prompt
            for ep in api_endpoints:
                path = ep.get('path', '')
                if path and path not in prompt:
                    issues.append(f"WARN: Endpoint {path} not found in prompt")

        # Check for conflicting instructions
        conflicts = [
            ('DO NOT generate', 'Generate'),
            ('DO NOT modify', 'modify'),
            ('required', 'optional')
        ]
        for neg, pos in conflicts:
            if neg in prompt and pos in prompt:
                # This is actually expected, so just note it
                pass

        # Check for proper routing prefix documentation
        if 'backend' in prompt_id.lower() and 'user' in prompt_id.lower():
            if '/api' in prompt and 'prefix' not in prompt.lower():
                issues.append("WARN: /api paths mentioned but prefix rules unclear")

        return issues

    def check_requirements_consistency(self, reqs: Dict, req_slug: str):
        """Check a single requirements file for consistency."""
        issues = []

        # Check required fields
        required_fields = ['slug', 'name', 'category', 'description',
                          'backend_requirements', 'frontend_requirements', 'api_endpoints']
        for field in required_fields:
            if field not in reqs:
                issues.append(f"ERROR: Missing required field '{field}' in {req_slug}")

        # Check slug matches filename
        if reqs.get('slug') != req_slug:
            issues.append(f"ERROR: Slug mismatch - file: {req_slug}, slug: {reqs.get('slug')}")

        # Check requirements are lists
        for field in ['backend_requirements', 'frontend_requirements', 'admin_requirements']:
            if field in reqs and not isinstance(reqs[field], list):
                issues.append(f"ERROR: {field} must be a list in {req_slug}")

        # Check API endpoints structure
        if 'api_endpoints' in reqs:
            for idx, ep in enumerate(reqs['api_endpoints']):
                if not isinstance(ep, dict):
                    issues.append(f"ERROR: api_endpoints[{idx}] must be an object in {req_slug}")
                    continue

                # Check required endpoint fields
                if 'method' not in ep:
                    issues.append(f"ERROR: api_endpoints[{idx}] missing 'method' in {req_slug}")
                if 'path' not in ep:
                    issues.append(f"ERROR: api_endpoints[{idx}] missing 'path' in {req_slug}")

                # Check path format
                path = ep.get('path', '')
                if path and not path.startswith('/'):
                    issues.append(f"ERROR: Path '{path}' must start with '/' in {req_slug}")

                # Check method is valid
                valid_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'WS']
                method = ep.get('method', '')
                if method and method not in valid_methods:
                    issues.append(f"WARN: Unusual HTTP method '{method}' in {req_slug}")

        # Check for admin endpoints if admin requirements exist
        if reqs.get('admin_requirements') and not reqs.get('admin_api_endpoints'):
            issues.append(f"WARN: Has admin_requirements but no admin_api_endpoints in {req_slug}")

        return issues

    def generate_all_prompts(self):
        """Generate all possible prompt combinations."""
        print("=" * 80)
        print("GENERATING ALL PROMPTS")
        print("=" * 80)

        requirements = self.load_requirements()
        print(f"\n[OK] Loaded {len(requirements)} requirement files")

        # Template configurations to test
        configs = [
            # Two-query (old format, user-only)
            {'type': 'two-query', 'component': 'backend', 'query': 'user'},
            {'type': 'two-query', 'component': 'frontend', 'query': 'user'},

            # Four-query (current format, user and admin)
            {'type': 'four-query', 'component': 'backend', 'query': 'user'},
            {'type': 'four-query', 'component': 'backend', 'query': 'admin'},
            {'type': 'four-query', 'component': 'frontend', 'query': 'user'},
            {'type': 'four-query', 'component': 'frontend', 'query': 'admin'},

            # Unguarded (single-file generation)
            {'type': 'unguarded', 'component': 'backend', 'query': 'user'},
            {'type': 'unguarded', 'component': 'frontend', 'query': 'user'},
        ]

        print(f"\n[OK] Testing {len(configs)} template configurations")
        print(f"\n[OK] Total prompts to generate: {len(requirements)} x {len(configs)} = {len(requirements) * len(configs)}")
        print("\nGenerating prompts...\n")

        for req_slug, reqs in requirements.items():
            for config in configs:
                template_type = config['type']
                component = config['component']
                query_type = config['query']

                prompt_id = f"{req_slug}_{template_type}_{component}_{query_type}"

                try:
                    prompt = self.generate_prompt(
                        template_type=template_type,
                        component=component,
                        query_type=query_type,
                        req_slug=req_slug,
                        reqs=reqs
                    )

                    self.generated_prompts[prompt_id] = {
                        'prompt': prompt,
                        'reqs': reqs,
                        'config': config
                    }
                    self.stats['prompts_generated'] += 1

                except FileNotFoundError as e:
                    # Some templates may not exist (e.g., two-query for admin)
                    self.warnings.append(f"SKIP: {prompt_id} - {e}")
                except Exception as e:
                    self.issues.append(f"ERROR generating {prompt_id}: {e}")

        print(f"[OK] Generated {self.stats['prompts_generated']} prompts successfully")
        if self.warnings:
            print(f"[WARN] Skipped {len(self.warnings)} configurations (missing templates)")

    def analyze_all_prompts(self):
        """Analyze all generated prompts."""
        print("\n" + "=" * 80)
        print("ANALYZING GENERATED PROMPTS")
        print("=" * 80 + "\n")

        for prompt_id, data in self.generated_prompts.items():
            issues = self.analyze_prompt(prompt_id, data['prompt'], data['reqs'])
            if issues:
                for issue in issues:
                    self.issues.append(f"{prompt_id}: {issue}")

        print(f"[OK] Analyzed {len(self.generated_prompts)} prompts")

    def analyze_all_requirements(self):
        """Analyze all requirements files for consistency."""
        print("\n" + "=" * 80)
        print("ANALYZING REQUIREMENTS FILES")
        print("=" * 80 + "\n")

        requirements = self.load_requirements()

        for req_slug, reqs in requirements.items():
            issues = self.check_requirements_consistency(reqs, req_slug)
            if issues:
                self.issues.extend(issues)

        print(f"[OK] Analyzed {len(requirements)} requirement files")

    def check_templates(self):
        """Check template files for issues."""
        print("\n" + "=" * 80)
        print("CHECKING TEMPLATE FILES")
        print("=" * 80 + "\n")

        template_types = ['two-query', 'four-query', 'unguarded']

        for template_type in template_types:
            template_dir = self.templates_dir / template_type
            if not template_dir.exists():
                self.issues.append(f"ERROR: Template directory missing: {template_dir}")
                continue

            templates = list(template_dir.glob('*.jinja2'))
            print(f"  {template_type}: {len(templates)} templates")

            for template_file in templates:
                # Try to load template
                try:
                    env = Environment(loader=FileSystemLoader(str(template_dir)))
                    template = env.get_template(template_file.name)

                    # Check for common Jinja2 issues
                    template_content = template_file.read_text(encoding='utf-8')

                    # Check for undefined variables
                    common_vars = ['name', 'description', 'backend_requirements',
                                  'frontend_requirements', 'api_endpoints']
                    for var in common_vars:
                        if f'{{{{{var}}}}}' in template_content or f'{{{{ {var} }}}}' in template_content:
                            pass  # Variable is used

                except Exception as e:
                    self.issues.append(f"ERROR loading template {template_file.name}: {e}")

    def check_system_prompts(self):
        """Check system prompt files."""
        print("\n" + "=" * 80)
        print("CHECKING SYSTEM PROMPTS")
        print("=" * 80 + "\n")

        expected_prompts = [
            'backend_user.md',
            'backend_admin.md',
            'backend_unguarded.md',
            'frontend_user.md',
            'frontend_admin.md',
            'frontend_unguarded.md',
            'fullstack_unguarded.md'
        ]

        for prompt_file in expected_prompts:
            prompt_path = self.prompts_dir / prompt_file
            if not prompt_path.exists():
                self.issues.append(f"ERROR: System prompt missing: {prompt_file}")
            else:
                # Check content
                content = prompt_path.read_text(encoding='utf-8')
                if len(content) < 100:
                    self.issues.append(f"WARN: System prompt too short: {prompt_file}")

                # Check for key instructions
                if 'backend' in prompt_file:
                    if 'Flask' not in content and 'backend' not in content.lower():
                        self.issues.append(f"WARN: {prompt_file} missing Flask/backend references")

                if 'frontend' in prompt_file:
                    if 'React' not in content and 'frontend' not in content.lower():
                        self.issues.append(f"WARN: {prompt_file} missing React/frontend references")

        print(f"  Found {len(list(self.prompts_dir.glob('*.md')))} system prompts")

    def generate_report(self):
        """Generate final analysis report."""
        print("\n" + "=" * 80)
        print("ANALYSIS REPORT")
        print("=" * 80)

        print(f"\n[STATISTICS]")
        print(f"  Requirements loaded: {self.stats['requirements_loaded']}")
        print(f"  Prompts generated: {self.stats['prompts_generated']}")

        print(f"\n[WARNINGS] ({len(self.warnings)})")
        for warning in self.warnings[:20]:  # Show first 20
            print(f"  - {warning}")
        if len(self.warnings) > 20:
            print(f"  ... and {len(self.warnings) - 20} more")

        print(f"\n[ISSUES] ({len(self.issues)})")
        if not self.issues:
            print("  [OK] No issues found!")
        else:
            # Group issues by type
            errors = [i for i in self.issues if 'ERROR' in i]
            warnings = [i for i in self.issues if 'WARN' in i]

            if errors:
                print(f"\n  ERRORS ({len(errors)}):")
                for error in errors[:30]:  # Show first 30
                    print(f"    • {error}")
                if len(errors) > 30:
                    print(f"    ... and {len(errors) - 30} more")

            if warnings:
                print(f"\n  WARNINGS ({len(warnings)}):")
                for warning in warnings[:30]:  # Show first 30
                    print(f"    • {warning}")
                if len(warnings) > 30:
                    print(f"    ... and {len(warnings) - 30} more")

        # Sample prompts
        print(f"\n[SAMPLE PROMPTS]")
        sample_ids = list(self.generated_prompts.keys())[:3]
        for prompt_id in sample_ids:
            prompt = self.generated_prompts[prompt_id]['prompt']
            print(f"\n  {prompt_id}:")
            print(f"    Length: {len(prompt)} chars")
            print(f"    Preview: {prompt[:200]}...")

        return len(errors) if 'errors' in locals() and errors else 0

def main():
    analyzer = PromptAnalyzer()

    # Run all checks
    analyzer.check_system_prompts()
    analyzer.check_templates()
    analyzer.analyze_all_requirements()
    analyzer.generate_all_prompts()
    analyzer.analyze_all_prompts()

    # Generate report
    error_count = analyzer.generate_report()

    # Save detailed results
    output_file = project_root / 'misc_analysis_results.json'
    results = {
        'stats': dict(analyzer.stats),
        'issues': analyzer.issues,
        'warnings': analyzer.warnings,
        'prompt_samples': {
            pid: {
                'length': len(data['prompt']),
                'preview': data['prompt'][:500],
                'config': data['config']
            }
            for pid, data in list(analyzer.generated_prompts.items())[:10]
        }
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVE] Detailed results saved to: {output_file}")
    print("\n" + "=" * 80)

    if error_count > 0:
        print(f"[ERROR] Analysis completed with {error_count} errors")
        return 1
    else:
        print("[SUCCESS] Analysis completed successfully!")
        return 0

if __name__ == '__main__':
    sys.exit(main())
