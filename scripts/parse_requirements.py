import os
import re
import json

def extract_requirements(file_path):
    """Extract the 4 requirements from a markdown file's Directive section."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the Directive section
        directive_match = re.search(r'### \*\*4\. Directive \(The Task\)\*\*(.*?)---', content, re.DOTALL)
        if not directive_match:
            return []
        
        directive_text = directive_match.group(1)
        
        # Extract numbered requirements (1., 2., 3., 4.)
        requirements = []
        pattern = r'\d+\.\s+\*\*(.*?)\*\*(.*?)(?=\d+\.\s+\*\*|$)'
        matches = re.findall(pattern, directive_text, re.DOTALL)
        
        for match in matches:
            title = match[0].strip()
            description = match[1].strip()
            # Clean up the description
            description = re.sub(r'\s+', ' ', description)
            requirements.append(f"{title}: {description}")
        
        return requirements[:4]  # Only take first 4
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return []

def main():
    base_path = r'c:\Users\grabowmar\Desktop\ThesisAppRework\src\misc\app_templates'
    result = {}
    
    # Get all app numbers
    app_numbers = set()
    for filename in os.listdir(base_path):
        if filename.startswith('app_') and filename.endswith('.md'):
            app_num = filename.split('_')[1]
            app_numbers.add(int(app_num))
    
    app_numbers = sorted(app_numbers)
    
    for app_num in app_numbers:
        # Find actual files
        backend_files = [f for f in os.listdir(base_path) if f.startswith(f'app_{app_num}_backend_') and f.endswith('.md')]
        frontend_files = [f for f in os.listdir(base_path) if f.startswith(f'app_{app_num}_frontend_') and f.endswith('.md')]
        
        app_data = {}
        
        if backend_files:
            backend_path = os.path.join(base_path, backend_files[0])
            backend_reqs = extract_requirements(backend_path)
            if backend_reqs:
                app_data['BACKEND'] = backend_reqs
        
        if frontend_files:
            frontend_path = os.path.join(base_path, frontend_files[0])
            frontend_reqs = extract_requirements(frontend_path)
            if frontend_reqs:
                app_data['FRONTEND'] = frontend_reqs
        
        if app_data:
            result[f'APP_{app_num}'] = app_data
    
    # Save to JSON
    output_path = os.path.join(base_path, 'all_app_requirements.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {output_path}")
    print(f"Processed {len(result)} apps")

if __name__ == "__main__":
    main()