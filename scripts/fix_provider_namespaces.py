#!/usr/bin/env python3
"""
Fix provider namespace mismatches for remaining invalid models.
Maps database model IDs to their correct OpenRouter equivalents.
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

# Load environment and app
from dotenv import load_dotenv
env_path = project_root / '.env'
load_dotenv(env_path)

from app.factory import create_app
from app.models import ModelCapability
from app.extensions import db

# Provider namespace corrections
# Database uses organization prefix (e.g., deepseek-ai), OpenRouter uses provider name (e.g., deepseek)
PROVIDER_CORRECTIONS = {
    # DeepSeek: deepseek-ai/* → deepseek/*
    'deepseek_deepseek-v3.2-exp': 'deepseek/deepseek-v3.2-exp',
    'deepseek_deepseek-v3.1-terminus': 'deepseek/deepseek-v3.1-terminus',
    'deepseek_deepseek-chat-v3.1': 'deepseek/deepseek-chat-v3.1',
    'deepseek_deepseek-r1-0528': 'deepseek/deepseek-r1-0528',
    'deepseek_deepseek-r1-0528-qwen3-8b': 'deepseek/deepseek-r1-0528-qwen3-8b',
    'deepseek_deepseek-prover-v2': 'deepseek/deepseek-prover-v2',
    'deepseek_deepseek-chat-v3-0324': 'deepseek/deepseek-chat-v3-0324',
    'deepseek_deepseek-r1-distill-qwen-32b': 'deepseek/deepseek-r1-distill-qwen-32b',
    'deepseek_deepseek-r1-distill-qwen-14b': 'deepseek/deepseek-r1-distill-qwen-14b',
    'deepseek_deepseek-r1-distill-llama-70b': 'deepseek/deepseek-r1-distill-llama-70b',
    'deepseek_deepseek-r1': 'deepseek/deepseek-r1',
    'deepseek_deepseek-chat-v3': 'deepseek/deepseek-chat',  # Note: v3 → chat
    
    # MiniMax: MiniMaxAI/* → minimax/*
    'minimax_minimax-m2': 'minimax/minimax-m2',
    'minimax_minimax-01': 'minimax/minimax-01',
    
    # Liquid: LiquidAI/* → liquid/*
    'liquid_lfm2-8b-a1b': 'liquid/lfm2-8b-a1b',
    'liquid_lfm-2.2-6b': 'liquid/lfm-2.2-6b',
    
    # Alibaba: Alibaba-NLP/* → alibaba/*
    'alibaba_tongyi-deepresearch-30b-a3b': 'alibaba/tongyi-deepresearch-30b-a3b',
    
    # Meituan: meituan-longcat/* → meituan/*
    'meituan_longcat-flash-chat': 'meituan/longcat-flash-chat',
    
    # AI21: ai21labs/* → ai21/*
    'ai21_jamba-mini-1.7': 'ai21/jamba-mini',
    'ai21_jamba-large-1.7': 'ai21/jamba-large',
    
    # ByteDance: ByteDance-Seed/* → bytedance/*
    'bytedance_ui-tars-1.5-7b': 'bytedance/ui-tars-7b',
    
    # Cohere: CohereForAI/* → cohere/*
    'cohere_command-a-03-2025': 'cohere/command-a',
    
    # Note: Some models might not have direct equivalents, will verify against catalog
}

def main(dry_run=True):
    """Fix provider namespace mismatches."""
    app = create_app()
    
    with app.app_context():
        print('=' * 80)
        print('Provider Namespace Correction')
        print('=' * 80)
        print()
        
        total = 0
        fixed = 0
        skipped = 0
        
        for slug, correct_id in PROVIDER_CORRECTIONS.items():
            total += 1
            model = ModelCapability.query.filter_by(canonical_slug=slug).first()
            
            if not model:
                print(f'⚠️  Model not found: {slug}')
                skipped += 1
                continue
            
            old_id = model.hugging_face_id
            
            if old_id == correct_id:
                print(f'✅ Already correct: {slug}')
                print(f'   ID: {old_id}')
                skipped += 1
            else:
                print(f'💡 Fix needed: {slug}')
                print(f'   Old: {old_id}')
                print(f'   New: {correct_id}')
                
                if not dry_run:
                    model.hugging_face_id = correct_id
                    fixed += 1
                    print(f'   ✅ Updated')
                else:
                    print(f'   (dry run - no changes)')
                    fixed += 1
            
            print()
        
        if not dry_run and fixed > 0:
            db.session.commit()
            print(f'✅ Committed {fixed} changes to database')
        
        print('=' * 80)
        print('Summary:')
        print(f'  Total processed: {total}')
        print(f'  Fixed: {fixed}')
        print(f'  Skipped: {skipped}')
        print('=' * 80)
        
        if dry_run and fixed > 0:
            print()
            print('ℹ️  Dry run mode - no changes made')
            print('   Run with --fix to apply corrections')

if __name__ == '__main__':
    dry_run = '--fix' not in sys.argv
    main(dry_run=dry_run)
