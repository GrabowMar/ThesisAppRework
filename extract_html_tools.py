import re

with open('results_page.html', 'r', encoding='utf-8') as f:
    html = f.read()

print('HTML file size:', len(html), 'bytes')
print()

# Extract all tool names from tool-name divs
tool_names = re.findall(r'<div[^>]*class="[^"]*tool-name[^"]*"[^>]*>([^<]+)</div>', html)
print('Total tool-name divs found:', len(tool_names))

if tool_names:
    print('\nAll tools found in HTML:')
    for i, name in enumerate(tool_names, 1):
        print(f'  {i}. {name.strip()}')

# Check for metadata contamination
metadata_keywords = ['tool_status', '_metadata', 'structure', 'file_counts', 
                     'CONNECTIVITY', 'VULNERABILITY', 'PORT_SCAN', 'ZAP_SECURITY',
                     'Tool Runs', 'http://']
contaminated = [name for name in tool_names if any(kw.lower() in name.lower() for kw in metadata_keywords)]
if contaminated:
    print('\n⚠️  METADATA CONTAMINATION DETECTED:')
    for name in contaminated:
        print(f'  - {name}')
else:
    print('\n✓ No metadata contamination detected')

# Check AI section
if 'AI requirements analysis not available' in html:
    print('\n⚠️  AI TAB: Shows "not available"')
elif 'compliance_percentage' in html or 'Compliance:' in html:
    print('\n✓ AI TAB: Compliance data present')
    comp_match = re.search(r'Compliance:\s*(\d+\.?\d*)%', html)
    if comp_match:
        print(f'  Compliance: {comp_match.group(1)}%')
else:
    print('\n⚠️  AI TAB: Unknown state (no compliance data or "not available" message)')
