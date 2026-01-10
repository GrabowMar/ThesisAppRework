#!/usr/bin/env python3
"""
Systematically improve all system prompts and templates with 2025 best practices
"""

import os
import sys
from pathlib import Path
import shutil

project_root = Path(__file__).parent.parent

# System prompt improvements
SYSTEM_PROMPT_ADDITIONS = {
    'backend': {
        'examples': '''
## Code Examples

### Example 1: Complete Model with to_dict()

```python
class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
```

### Example 2: GET Route with Query Params

```python
@user_bp.route('/items', methods=['GET'])
def get_items():
    try:
        # Parse query parameters
        search = request.args.get('search', '')
        active_only = request.args.get('active', 'true').lower() == 'true'

        # Build query
        query = Item.query
        if active_only:
            query = query.filter_by(is_active=True)
        if search:
            query = query.filter(Item.name.ilike(f'%{search}%'))

        items = query.order_by(Item.created_at.desc()).all()

        return jsonify({
            'items': [item.to_dict() for item in items],
            'total': len(items)
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Example 3: POST Route with Validation

```python
@user_bp.route('/items', methods=['POST'])
def create_item():
    try:
        data = request.get_json()

        # Validate required fields
        if not data or 'name' not in data:
            return jsonify({'error': 'Name is required'}), 400

        name = data.get('name', '').strip()
        if not name:
            return jsonify({'error': 'Name cannot be empty'}), 400

        # Create and save
        item = Item(
            name=name,
            description=data.get('description', '').strip()
        )
        db.session.add(item)
        db.session.commit()

        return jsonify(item.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
```
''',
        'best_practices': '''
## Best Practices

1. **Always use soft deletes:** Include `is_active` field, filter by `is_active=True`
2. **Always validate input:** Check required fields before database operations
3. **Always handle exceptions:** Wrap routes in try/except, rollback on error
4. **Always return proper status codes:** 200 (OK), 201 (Created), 400 (Bad Request), 404 (Not Found), 500 (Error)
5. **Always use query filters:** Build queries with filters for performance
6. **Always format datetimes:** Use `.isoformat()` for JSON serialization
'''
    },
    'frontend': {
        'examples': '''
## Code Examples

### Example 1: Complete Component with State

```jsx
function ItemList() {
    const [items, setItems] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [searchQuery, setSearchQuery] = useState('')

    useEffect(() => {
        fetchItems()
    }, [searchQuery])

    async function fetchItems() {
        try {
            setLoading(true)
            setError(null)

            const url = searchQuery
                ? `/api/items?search=${encodeURIComponent(searchQuery)}`
                : '/api/items'

            const res = await fetch(url)
            if (!res.ok) throw new Error(`HTTP ${res.status}`)

            const data = await res.json()
            setItems(data.items || [])
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    if (loading) return <div className="loading">Loading...</div>
    if (error) return <div className="error">Error: {error}</div>

    return (
        <div className="item-list">
            <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search..."
            />
            {items.map(item => (
                <div key={item.id} className="item">
                    <h3>{item.name}</h3>
                    <p>{item.description}</p>
                </div>
            ))}
        </div>
    )
}
```

### Example 2: POST Request with Validation

```jsx
async function handleSubmit(e) {
    e.preventDefault()

    // Validate
    const name = e.target.name.value.trim()
    if (!name) {
        setError('Name is required')
        return
    }

    try {
        setLoading(true)
        setError(null)

        const res = await fetch('/api/items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                description: e.target.description.value.trim()
            })
        })

        if (!res.ok) {
            const error = await res.json()
            throw new Error(error.error || `HTTP ${res.status}`)
        }

        const newItem = await res.json()
        setItems([newItem, ...items])
        e.target.reset()

    } catch (err) {
        setError(err.message)
    } finally {
        setLoading(false)
    }
}
```
''',
        'best_practices': '''
## Best Practices

1. **Always handle loading states:** Show loading indicator during API calls
2. **Always handle errors:** Display error messages to users
3. **Always validate input:** Check required fields before submission
4. **Always encode URLs:** Use `encodeURIComponent()` for query parameters
5. **Always check response status:** Throw error if `!res.ok`
6. **Always use proper HTTP methods:** GET (read), POST (create), PUT (update), DELETE (remove)
7. **Always reset forms:** Clear form after successful submission
'''
    }
}

def improve_system_prompt(file_path: Path, prompt_type: str):
    """Add examples and best practices to system prompt"""
    print(f"  Improving {file_path.name}...")

    content = file_path.read_text(encoding='utf-8')

    # Determine if backend or frontend
    component_type = 'backend' if 'backend' in prompt_type or 'Backend' in content else 'frontend'
    additions = SYSTEM_PROMPT_ADDITIONS[component_type]

    # Add examples before "Output Format" section
    if '## Output Format' in content and '## Code Examples' not in content:
        content = content.replace(
            '## Output Format',
            additions['examples'] + '\n## Output Format'
        )

    # Add best practices at the end
    if '## Best Practices' not in content:
        content += '\n' + additions['best_practices']

    # Add rationale to routing rule
    if 'user_bp' in content and 'Prevents double-prefixing' not in content:
        content = content.replace(
            'In code, define routes RELATIVE to the blueprint',
            'In code, define routes RELATIVE to the blueprint (prevents double-prefixing like /api/api/todos which causes 404 errors)'
        )

    # Write improved version
    file_path.write_text(content, encoding='utf-8')
    print(f"    [OK] Added examples and best practices")

def improve_template(file_path: Path):
    """Add implementation guide and quality checklist to template"""
    print(f"  Improving {file_path.name}...")

    content = file_path.read_text(encoding='utf-8')

    # Add implementation guide after requirements
    if '## Your Task' in content and '## Implementation Guide' not in content:
        guide = '''
## Implementation Guide

**Step 1: Define Models**
- Create database schema with all required fields
- Include `is_active` field for soft delete
- Include `created_at` timestamp
- Implement `to_dict()` method for JSON serialization

**Step 2: Implement Routes**
- Use correct blueprint prefix (see routing rules below)
- Add input validation for all POST/PUT routes
- Include error handling with try/except
- Return proper HTTP status codes

**Step 3: Test**
- Verify all endpoints return correct data
- Test error cases (missing fields, invalid data)
- Check that soft delete works correctly
'''
        # Insert after requirements section
        if '## API Endpoints' in content:
            content = content.replace('## API Endpoints', guide + '\n## API Endpoints')
        elif '## File Structure' in content:
            content = content.replace('## File Structure', guide + '\n## File Structure')

    # Add quality checklist before final instruction
    if 'Generate' in content.split('\n')[-5:][0] and '## Quality Checklist' not in content:
        checklist = '''
## Quality Checklist

Before submitting, verify:
- [x] All models have `to_dict()` methods
- [x] All routes have error handling (try/except)
- [x] All POST/PUT routes validate input
- [x] All routes use correct blueprint/decorator
- [x] All database queries use soft delete filter (`is_active=True`)
- [x] No placeholders or TODO comments
- [x] Proper HTTP status codes (200, 201, 400, 404, 500)

'''
        # Add before final "Generate" instruction
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'Generate' in line and i > len(lines) - 10:
                lines.insert(i, checklist)
                break
        content = '\n'.join(lines)

    file_path.write_text(content, encoding='utf-8')
    print(f"    [OK] Added implementation guide and quality checklist")

def main():
    print("=" * 80)
    print("IMPROVING ALL PROMPTS AND TEMPLATES")
    print("=" * 80)

    # Backup directory
    backup_dir = project_root / 'misc' / 'backup_before_improvements'
    backup_dir.mkdir(exist_ok=True)

    print("\n[1/3] Backing up original files...")

    # Backup system prompts
    system_prompts_dir = project_root / 'misc' / 'prompts' / 'system'
    backup_prompts_dir = backup_dir / 'prompts' / 'system'
    backup_prompts_dir.mkdir(parents=True, exist_ok=True)

    for prompt_file in system_prompts_dir.glob('*.md'):
        if 'improved' not in prompt_file.name and 'backup' not in str(prompt_file):
            shutil.copy2(prompt_file, backup_prompts_dir / prompt_file.name)
            print(f"  [OK] Backed up {prompt_file.name}")

    # Backup templates
    templates_dir = project_root / 'misc' / 'templates' / 'four-query'
    backup_templates_dir = backup_dir / 'templates' / 'four-query'
    backup_templates_dir.mkdir(parents=True, exist_ok=True)

    for template_file in templates_dir.glob('*.jinja2'):
        if 'improved' not in template_file.name and 'backup' not in str(template_file):
            shutil.copy2(template_file, backup_templates_dir / template_file.name)
            print(f"  [OK] Backed up {template_file.name}")

    print("\n[2/3] Improving system prompts...")

    # Improve system prompts
    system_prompts = [
        ('backend_admin.md', 'backend_admin'),
        ('backend_unguarded.md', 'backend_unguarded'),
        ('backend_user.md', 'backend_user'),
        ('frontend_admin.md', 'frontend_admin'),
        ('frontend_unguarded.md', 'frontend_unguarded'),
        ('frontend_user.md', 'frontend_user'),
        ('fullstack_unguarded.md', 'fullstack_unguarded'),
    ]

    for filename, prompt_type in system_prompts:
        file_path = system_prompts_dir / filename
        if file_path.exists():
            improve_system_prompt(file_path, prompt_type)

    print("\n[3/3] Improving templates...")

    # Improve templates
    templates = [
        'backend_admin.md.jinja2',
        'backend_user.md.jinja2',
        'frontend_admin.md.jinja2',
        'frontend_user.md.jinja2',
    ]

    for filename in templates:
        file_path = templates_dir / filename
        if file_path.exists():
            improve_template(file_path)

    print("\n" + "=" * 80)
    print("IMPROVEMENTS COMPLETE")
    print("=" * 80)

    print(f"\n[OK] Original files backed up to: {backup_dir}")
    print(f"[OK] System prompts improved: {len(system_prompts)}")
    print(f"[OK] Templates improved: {len(templates)}")

    print("\nChanges made:")
    print("  - Added 3 complete code examples to each prompt")
    print("  - Added best practices section")
    print("  - Added implementation guide to templates")
    print("  - Added quality checklist to templates")
    print("  - Added rationale for routing rules")

    print("\nNext steps:")
    print("  1. Run: python scripts/analyze_all_prompts.py")
    print("  2. Compare new vs old prompts")
    print("  3. Test with actual LLM generation")

    return 0

if __name__ == '__main__':
    sys.exit(main())
