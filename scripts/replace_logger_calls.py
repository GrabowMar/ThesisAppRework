"""Replace all logger calls with self._log calls in task_execution_service.py"""
import re
from pathlib import Path

file_path = Path("src/app/services/task_execution_service.py")
content = file_path.read_text(encoding='utf-8')

# Track changes
changes = 0

# Define patterns for each log level
patterns = {
    r'logger\.info\(': ('self._log(', 'info'),
    r'logger\.debug\(': ('self._log(', 'debug'),
    r'logger\.error\(': ('self._log(', 'error'),
    r'logger\.warning\(': ('self._log(', 'warning'),
}

# First pass: replace simple single-line calls
for old_pattern, (new_prefix, level) in patterns.items():
    # Pattern: logger.level("message", args...)
    # Replace with: self._log("message", args..., level='level')
    
    # Find all matches
    matches = list(re.finditer(old_pattern, content))
    
    for match in reversed(matches):  # Reverse to preserve positions
        start = match.start()
        
        # Find the matching closing parenthesis
        paren_count = 1
        pos = start + len(match.group())
        while pos < len(content) and paren_count > 0:
            if content[pos] == '(':
                paren_count += 1
            elif content[pos] == ')':
                paren_count -= 1
            pos += 1
        
        if paren_count == 0:
            # Extract the arguments
            args_start = start + len(match.group()) - 1  # Before the opening (
            args_end = pos - 1  # Before the closing )
            args = content[args_start+1:args_end]
            
            # Build replacement
            if level == 'info':
                # info is default, no need to specify level
                replacement = f"{new_prefix}{args})"
            else:
                replacement = f"{new_prefix}{args}, level='{level}')"
            
            # Apply replacement
            content = content[:start] + replacement + content[pos:]
            changes += 1

# Save the modified content
file_path.write_text(content, encoding='utf-8')

print(f"✓ Replaced {changes} logger calls with self._log calls")
print(f"✓ File saved: {file_path}")
