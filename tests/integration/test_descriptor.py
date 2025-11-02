#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')

from app.routes.jinja.analysis import DescriptorDict

print('✓ DescriptorDict imported successfully')
d = DescriptorDict({'test': 'value', 'task_name': 'test_task'})
print(f'✓ Can access as attribute: {d.test}')
print(f'✓ Has task_name: {d.task_name}')
print(f'✓ Has display_timestamp: {hasattr(d, "display_timestamp")}')
print(f'✓ display_timestamp() returns: {d.display_timestamp()}')
print('\n✓✓✓ All tests passed! DescriptorDict is working correctly.')
