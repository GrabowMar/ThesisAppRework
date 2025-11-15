#!/usr/bin/env python3
"""
Check remaining invalid models against OpenRouter catalog.
"""
import os
import sys
import asyncio
import aiohttp
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env from {env_path}")
else:
    print(f"⚠️  No .env file found at {env_path}")

async def check_models():
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print('❌ OPENROUTER_API_KEY not set')
        print('   Please set it in .env file')
        return
    
    # Models that appear invalid (provider namespace mismatches)
    db_models = {
        'deepseek_deepseek-v3.2-exp': 'deepseek-ai/DeepSeek-V3.2-Exp',
        'deepseek_deepseek-v3.1-terminus': 'deepseek-ai/DeepSeek-V3.1-Terminus',
        'deepseek_deepseek-chat-v3.1': 'deepseek-ai/DeepSeek-V3.1',
        'deepseek_deepseek-r1-0528': 'deepseek-ai/DeepSeek-R1-0528',
        'deepseek_deepseek-r1-0528-qwen3-8b': 'deepseek-ai/deepseek-r1-0528-qwen3-8b',
        'deepseek_deepseek-prover-v2': 'deepseek-ai/DeepSeek-Prover-V2-671B',
        'deepseek_deepseek-chat-v3-0324': 'deepseek-ai/DeepSeek-V3-0324',
        'deepseek_deepseek-r1-distill-qwen-32b': 'deepseek-ai/DeepSeek-R1-Distill-Qwen-32B',
        'deepseek_deepseek-r1-distill-qwen-14b': 'deepseek-ai/DeepSeek-R1-Distill-Qwen-14B',
        'deepseek_deepseek-r1-distill-llama-70b': 'deepseek-ai/DeepSeek-R1-Distill-Llama-70B',
        'deepseek_deepseek-r1': 'deepseek-ai/DeepSeek-R1',
        'deepseek_deepseek-chat-v3': 'deepseek-ai/DeepSeek-V3',
        'minimax_minimax-m2': 'MiniMaxAI/MiniMax-M2',
        'minimax_minimax-01': 'MiniMaxAI/MiniMax-Text-01',
        'liquid_lfm2-8b-a1b': 'LiquidAI/LFM2-8B-A1B',
        'liquid_lfm-2.2-6b': 'LiquidAI/LFM2-2.6B',
        'alibaba_tongyi-deepresearch-30b-a3b': 'Alibaba-NLP/Tongyi-DeepResearch-30B-A3B',
        'meituan_longcat-flash-chat': 'meituan-longcat/LongCat-Flash-Chat',
        'z-ai_glm-4.5v': 'zai-org/GLM-4.5V',
        'z-ai_glm-4.5': 'zai-org/GLM-4.5',
        'z-ai_glm-4.5-air': 'zai-org/GLM-4.5-Air',
        'ai21_jamba-mini-1.7': 'ai21labs/AI21-Jamba-Mini-1.7',
        'ai21_jamba-large-1.7': 'ai21labs/AI21-Jamba-Large-1.7',
        'bytedance_ui-tars-1.5-7b': 'ByteDance-Seed/UI-TARS-1.5-7B',
        'cohere_command-a-03-2025': 'CohereForAI/c4ai-command-a-03-2025',
        'aion-labs_aion-1.0-mini': 'FuseAI/FuseO1-DeepSeekR1-QwQ-SkyT1-32B-Preview'
    }
    
    async with aiohttp.ClientSession() as session:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'HTTP-Referer': 'https://github.com/yourusername/yourrepo',
            'X-Title': 'ThesisAppRework'
        }
        
        print('Fetching OpenRouter catalog...')
        async with session.get('https://openrouter.ai/api/v1/models', headers=headers) as response:
            if response.status != 200:
                print(f'❌ API returned {response.status}')
                return
            
            data = await response.json()
            catalog = {m['id'].lower(): m['id'] for m in data.get('data', [])}
            
            print(f'✅ Fetched {len(catalog)} models from OpenRouter')
            print('=' * 80)
            print('Checking database model IDs against catalog...')
            print('=' * 80)
            
            valid = []
            case_fixes = []
            not_found = []
            
            for slug, db_id in db_models.items():
                db_lower = db_id.lower()
                if db_lower in catalog:
                    canonical = catalog[db_lower]
                    if canonical != db_id:
                        case_fixes.append((slug, db_id, canonical))
                        print(f'✅ FOUND (case fix needed)')
                        print(f'   Slug: {slug}')
                        print(f'   DB:   {db_id}')
                        print(f'   Real: {canonical}')
                        print()
                    else:
                        valid.append((slug, db_id))
                        print(f'✅ VALID: {slug} → {db_id}')
                else:
                    not_found.append((slug, db_id))
                    print(f'❌ NOT FOUND: {slug} → {db_id}')
            
            print('=' * 80)
            print(f'Summary:')
            print(f'  Total checked:     {len(db_models)}')
            print(f'  ✅ Already valid:  {len(valid)}')
            print(f'  💡 Fixable (case): {len(case_fixes)}')
            print(f'  ❌ Not found:      {len(not_found)}')
            
            if case_fixes:
                print('\n' + '=' * 80)
                print('Fixable Models (case normalization):')
                print('=' * 80)
                for slug, old_id, new_id in case_fixes:
                    print(f'{slug}:')
                    print(f'  {old_id} → {new_id}')

if __name__ == '__main__':
    asyncio.run(check_models())
