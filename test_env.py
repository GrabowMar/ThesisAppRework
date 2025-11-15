from dotenv import load_dotenv, dotenv_values
from pathlib import Path
import os

env_path = Path('.env')
print(f'File exists: {env_path.exists()}')
print(f'File path: {env_path.absolute()}')

# Test dotenv_values (doesn't modify os.environ)
values = dotenv_values(env_path)
print(f'\ndotenv_values result:')
print(f'  Keys: {list(values.keys())}')
print(f'  OPENROUTER_API_KEY: {repr(values.get("OPENROUTER_API_KEY", "NOT FOUND"))}')

# Test load_dotenv
result = load_dotenv(env_path)
print(f'\nload_dotenv result: {result}')
print(f'OPENROUTER_API_KEY from os.environ: {repr(os.getenv("OPENROUTER_API_KEY", "NOT FOUND"))}')
print(f'All env keys with OPENROUTER: {[k for k in os.environ.keys() if "OPENROUTER" in k]}')

# Manual parse
print(f'\nManual parse:')
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        if 'OPENROUTER' in line:
            print(f'  Line: {repr(line)}')
