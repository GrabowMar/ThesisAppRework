"""Generate markdown file showing XSD Verifier prompts."""
import sys
sys.path.insert(0, 'src')

from pathlib import Path
from app.services.generation_v2 import CodeGenerator, GenerationConfig

# Initialize generator
generator = CodeGenerator()

# Backend config
backend_config = GenerationConfig(
    model_slug='test',
    app_num=999,
    template_id=3,  # xsd_verifier
    component='backend'
)

# Frontend config
frontend_config = GenerationConfig(
    model_slug='test',
    app_num=999,
    template_id=3,  # xsd_verifier
    component='frontend'
)

# Build prompts
backend_system = generator._get_system_prompt('backend')
backend_user = generator._build_prompt(backend_config)
frontend_system = generator._get_system_prompt('frontend')
frontend_user = generator._build_prompt(frontend_config)

# Create markdown
parts = []
parts.append("# XSD Verifier App - OpenRouter Prompts\n")
parts.append("**Generated:** October 16, 2025\n\n")
parts.append("This document shows the exact prompts that would be sent to OpenRouter API for generating the XSD Verifier application using the new template-based system.\n\n")
parts.append("---\n\n")

parts.append("## 🔧 Backend Generation Prompt\n\n")
parts.append("### System Prompt (Backend)\n\n")
parts.append("```\n")
parts.append(backend_system)
parts.append("\n```\n\n")
parts.append("### User Prompt (Backend)\n\n")
parts.append("```markdown\n")
parts.append(backend_user)
parts.append("\n```\n\n")
parts.append("---\n\n")

parts.append("## 🎨 Frontend Generation Prompt\n\n")
parts.append("### System Prompt (Frontend)\n\n")
parts.append("```\n")
parts.append(frontend_system)
parts.append("\n```\n\n")
parts.append("### User Prompt (Frontend)\n\n")
parts.append("```markdown\n")
parts.append(frontend_user)
parts.append("\n```\n\n")
parts.append("---\n\n")

parts.append("## 📊 Prompt Statistics\n\n")
parts.append("| Component | System Prompt | User Prompt | Total |\n")
parts.append("|-----------|--------------|-------------|-------|\n")
parts.append(f"| Backend | {len(backend_system):,} chars | {len(backend_user):,} chars | **{len(backend_system) + len(backend_user):,} chars** |\n")
parts.append(f"| Frontend | {len(frontend_system):,} chars | {len(frontend_user):,} chars | **{len(frontend_system) + len(frontend_user):,} chars** |\n\n")
parts.append(f"**Grand Total:** {len(backend_system) + len(backend_user) + len(frontend_system) + len(frontend_user):,} characters\n\n")
parts.append("---\n\n")

parts.append("## 🏗️ Template Structure\n\n")
parts.append("Each prompt consists of:\n\n")
parts.append("1. **System Prompt** (~450 chars)\n")
parts.append("   - Role definition (expert Flask/React developer)\n")
parts.append("   - Task overview (generate ONLY app code)\n")
parts.append("   - Rules (DO/DON'T lists)\n")
parts.append("   - Output format (code blocks)\n\n")
parts.append("2. **User Prompt** (~8,000-9,000 chars)\n")
parts.append("   - **Scaffolding Information** (~3,500 chars)\n")
parts.append("     - Complete Docker infrastructure documentation\n")
parts.append("     - Existing files that AI should NOT regenerate\n")
parts.append("     - Base app structure and available dependencies\n")
parts.append("   - **Application Specification** (~100 chars)\n")
parts.append("     - App name and description from requirements JSON\n")
parts.append("   - **Requirements List** (~500 chars)\n")
parts.append("     - Specific features to implement\n")
parts.append("   - **Implementation Guidelines** (~2,000 chars)\n")
parts.append("     - Best practices for Flask/React\n")
parts.append("     - Code structure and quality standards\n")
parts.append("   - **Constraints** (~500 chars)\n")
parts.append("     - DO: Generate complete app code\n")
parts.append("     - DON'T: Generate infrastructure files\n")
parts.append("   - **Output Format** (~100 chars)\n")
parts.append("     - Single code block with all application code\n\n")
parts.append("---\n\n")

parts.append("## 🎯 Key Improvements\n\n")
parts.append("### Old System (Generic)\n")
parts.append('```python\n')
parts.append('"You are a Flask developer. Generate an XSD validator with file upload."\n')
parts.append('```\n\n')
parts.append("### New System (Context-Aware)\n")
parts.append('```python\n')
parts.append('Scaffolding Info (what exists) + \n')
parts.append('Template Structure (how to organize) + \n')
parts.append('Requirements (what to build) = \n')
parts.append('Complete Prompt (~9,000 chars)\n')
parts.append('```\n\n')
parts.append("The AI now knows:\n")
parts.append("- ✅ What files already exist (don't regenerate)\n")
parts.append("- ✅ What structure to follow (Flask app with routes, SQLAlchemy models)\n")
parts.append("- ✅ What dependencies are available (Flask, SQLAlchemy, React, axios)\n")
parts.append("- ✅ Exactly what to build (specific requirements list)\n")
parts.append("- ✅ How to format output (single code block, no infrastructure)\n\n")
parts.append("---\n\n")

parts.append("## 📝 XSD Verifier Requirements\n\n")
parts.append("### Backend Requirements\n\n")
if backend_config.requirements and 'backend_requirements' in backend_config.requirements:
    for i, req in enumerate(backend_config.requirements['backend_requirements'], 1):
        parts.append(f"{i}. {req}\n")
else:
    parts.append("*(Requirements not loaded)*\n")

parts.append("\n### Frontend Requirements\n\n")
if frontend_config.requirements and 'frontend_requirements' in frontend_config.requirements:
    for i, req in enumerate(frontend_config.requirements['frontend_requirements'], 1):
        parts.append(f"{i}. {req}\n")
else:
    parts.append("*(Requirements not loaded)*\n")

parts.append("\n---\n\n")
parts.append("## 🚀 Usage\n\n")
parts.append("These prompts are sent to OpenRouter API:\n\n")
parts.append('```python\n')
parts.append('# Backend generation\n')
parts.append('POST https://openrouter.ai/api/v1/chat/completions\n')
parts.append('{\n')
parts.append('  "model": "anthropic/claude-3.5-sonnet",\n')
parts.append('  "messages": [\n')
parts.append('    {"role": "system", "content": "<backend_system_prompt>"},\n')
parts.append('    {"role": "user", "content": "<backend_user_prompt>"}\n')
parts.append('  ],\n')
parts.append('  "temperature": 0.3,\n')
parts.append('  "max_tokens": 16000\n')
parts.append('}\n\n')
parts.append('# Frontend generation (similar structure)\n')
parts.append('```\n\n')
parts.append("The AI's response is then merged into the scaffolding to create the complete application.\n")

markdown = ''.join(parts)

# Save to file
output_path = Path('XSD_VERIFIER_PROMPTS.md')
output_path.write_text(markdown, encoding='utf-8')

print(f'✅ Prompts saved to: {output_path.absolute()}')
print()
print('📊 Statistics:')
print(f'   Backend:  {len(backend_system) + len(backend_user):,} chars')
print(f'   Frontend: {len(frontend_system) + len(frontend_user):,} chars')
print(f'   Total:    {len(backend_system) + len(backend_user) + len(frontend_system) + len(frontend_user):,} chars')
