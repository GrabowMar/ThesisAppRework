"""Backfill hugging_face_id for all models from OpenRouter API"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import requests
from app.factory import create_app
from app.models import ModelCapability, db

def backfill_hugging_face_ids():
    """Fetch all models from OpenRouter and update hugging_face_id field"""
    api_key = "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"
    
    print("Fetching models from OpenRouter...")
    response = requests.get(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return
    
    data = response.json()
    models = data.get('data', [])
    print(f"Found {len(models)} models from OpenRouter\n")
    
    # Create mapping: model_id -> hugging_face_id
    hf_id_map = {}
    for m in models:
        model_id = m.get('id')
        hf_id = m.get('hugging_face_id')
        if model_id and hf_id:
            hf_id_map[model_id] = hf_id
            # Also map base ID (without :free suffix)
            base_id = model_id.split(':')[0]
            if base_id != model_id:
                hf_id_map[base_id] = hf_id
    
    print(f"Extracted {len(hf_id_map)} model_id -> hugging_face_id mappings\n")
    
    # Update database
    app = create_app()
    with app.app_context():
        all_models = ModelCapability.query.all()
        print(f"Found {len(all_models)} models in database\n")
        
        updated = 0
        skipped = 0
        
        for model in all_models:
            # Try to find HF ID from OpenRouter data
            hf_id = hf_id_map.get(model.model_id) or hf_id_map.get(model.base_model_id)
            
            if hf_id:
                if model.hugging_face_id != hf_id:
                    old_val = model.hugging_face_id or '(none)'
                    model.hugging_face_id = hf_id
                    print(f"[OK] {model.canonical_slug}: {old_val} -> {hf_id}")
                    updated += 1
                else:
                    print(f"[SKIP] {model.canonical_slug}: already has correct HF ID")
                    skipped += 1
            else:
                print(f"[WARN] {model.canonical_slug}: no HF ID found (model_id: {model.model_id})")
                skipped += 1
        
        if updated > 0:
            db.session.commit()
            print(f"\n[OK] Updated {updated} models")
        else:
            print("\n[SKIP] No updates needed")
        
        print(f"[SKIP] Skipped {skipped} models (already correct or no HF ID available)")

if __name__ == '__main__':
    backfill_hugging_face_ids()
