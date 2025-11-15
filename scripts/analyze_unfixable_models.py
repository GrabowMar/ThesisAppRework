import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from app.factory import create_app
from app.models import ModelCapability
from app.services.model_validator import get_validator

app = create_app()
validator = get_validator()

print("="*80)
print("Unfixable Models Analysis")
print("="*80)
print()

# Refresh catalog
print("Fetching OpenRouter catalog...")
if not validator.refresh_catalog(force=True):
    print("Failed to fetch catalog")
    sys.exit(1)

print(f"Catalog contains {len(validator._catalog_by_id)} models\n")

with app.app_context():
    # Get all models
    all_models = ModelCapability.query.all()
    
    # Categorize
    valid = []
    fixable = []
    unfixable = []
    
    for model in all_models:
        model_id = model.hugging_face_id or model.base_model_id or model.model_id
        
        if validator.is_valid_model_id(model_id):
            valid.append(model)
        else:
            suggestion = validator.suggest_correction(model_id, model.provider)
            if suggestion:
                fixable.append((model, suggestion))
            else:
                unfixable.append(model)
    
    print(f"Total: {len(all_models)} models")
    print(f"  Valid: {len(valid)}")
    print(f"  Fixable: {len(fixable)}")
    print(f"  Unfixable: {len(unfixable)}")
    print()
    
    # Group unfixable by provider
    by_provider = {}
    for model in unfixable:
        provider = model.provider
        if provider not in by_provider:
            by_provider[provider] = []
        by_provider[provider].append(model)
    
    print("="*80)
    print("Unfixable Models by Provider")
    print("="*80)
    print()
    
    for provider in sorted(by_provider.keys()):
        models = by_provider[provider]
        print(f"{provider.upper()} ({len(models)} models)")
        print("-" * 40)
        for model in models:
            model_id = model.hugging_face_id or model.base_model_id or model.model_id
            print(f"  • {model.canonical_slug}")
            print(f"    ID: {model_id}")
            
            # Check if provider exists in catalog at all
            provider_models = [m for m in validator._catalog_by_id.keys() if m.startswith(provider + '/')]
            if provider_models:
                print(f"    Note: Provider exists in catalog ({len(provider_models)} models)")
            else:
                print(f"    Note: Provider NOT in catalog - may be deprecated or renamed")
        print()
    
    print("="*80)
    print("Recommendations")
    print("="*80)
    print()
    print("1. Models from providers NOT in catalog:")
    print("   → Likely deprecated/renamed - consider removing from database")
    print()
    print("2. Models from providers IN catalog:")
    print("   → Model may be:")
    print("      - New and not yet in catalog")
    print("      - Experimental/preview version")
    print("      - Requires manual ID mapping")
    print()
    print("3. Next steps:")
    print("   → Review OpenRouter docs for each provider")
    print("   → Check if model names have changed")
    print("   → Update manually or mark as unavailable")
