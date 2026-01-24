import json
import re
import difflib
import sys
import os

def extract_template_from_payload(payload_path, language):
    with open(payload_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # The template is usually in the system message
    messages = data.get('payload', {}).get('messages', [])
    system_message = next((m for m in messages if m['role'] == 'system'), None)
    
    if not system_message:
        print(f"No system message found in {payload_path}")
        return ""
    
    content = system_message['content']
    
    # Regex to find the code block
    # Looking for ```python:app.py ... ``` or ```jsx:App.jsx ... ```
    pattern = r"## COMPLETE WORKING EXAMPLE STRUCTURE\s+```" + language + r":\S+\s+(.*?)```"
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        return match.group(1)
    
    # Fallback
    pattern_fallback = r"```" + language + r":\S+\s+(.*?)```"
    matches = re.findall(pattern_fallback, content, re.DOTALL)
    if matches:
         return max(matches, key=len)

    print(f"No template code found in {payload_path}")
    return ""

def normalize_code(code):
    # Remove leading/trailing whitespace per line, empty lines
    lines = code.split('\n')
    cleaned = [line.strip() for line in lines if line.strip()]
    return cleaned

def calculate_similarity(generated_path, payload_path, language):
    if not os.path.exists(generated_path):
        print(f"Generated file not found: {generated_path}")
        return 0.0, 0, 0
    
    if not os.path.exists(payload_path):
        print(f"Payload file not found: {payload_path}")
        return 0.0, 0, 0

    with open(generated_path, 'r', encoding='utf-8') as f:
        generated_code = f.read()
    
    template_code = extract_template_from_payload(payload_path, language)
    
    if not template_code:
        return 0.0, 0, 0
    
    gen_lines = normalize_code(generated_code)
    tmpl_lines = normalize_code(template_code)
    
    matcher = difflib.SequenceMatcher(None, tmpl_lines, gen_lines)
    total_matches = sum(match.size for match in matcher.get_matching_blocks())
    
    if len(gen_lines) == 0:
        return 0.0, 0, 0
        
    percentage = (total_matches / len(gen_lines)) * 100
    return percentage, total_matches, len(gen_lines)

def main():
    backend_app = r"c:\Users\grabowmar\Desktop\ThesisAppRework\generated\apps\qwen_qwen3-coder-30b-a3b-instruct\app1\backend\app.py"
    backend_payload = r"c:\Users\grabowmar\Desktop\ThesisAppRework\generated\raw\payloads\qwen_qwen3-coder-30b-a3b-instruct\app1\qwen_qwen3-coder-30b-a3b-instruct_app1_backend_20260124_094804_payload.json"
    
    frontend_app = r"c:\Users\grabowmar\Desktop\ThesisAppRework\generated\apps\qwen_qwen3-coder-30b-a3b-instruct\app1\frontend\src\App.jsx"
    frontend_payload = r"c:\Users\grabowmar\Desktop\ThesisAppRework\generated\raw\payloads\qwen_qwen3-coder-30b-a3b-instruct\app1\qwen_qwen3-coder-30b-a3b-instruct_app1_frontend_20260124_094839_payload.json"
    
    with open('analysis_results.txt', 'w') as f:
        print("--- Backend Analysis ---", file=f)
        pct, match, total = calculate_similarity(backend_app, backend_payload, "python")
        print(f"Backend Similarity: {pct:.2f}% ({match}/{total} lines)", file=f)
        
        print("\n--- Frontend Analysis ---", file=f)
        pct, match, total = calculate_similarity(frontend_app, frontend_payload, "jsx")
        print(f"Frontend Similarity: {pct:.2f}% ({match}/{total} lines)", file=f)
    print("Analysis complete. Results written to analysis_results.txt")

if __name__ == "__main__":
    main()
