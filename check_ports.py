#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import PortConfiguration

app = create_app('default')
with app.app_context():
    # Note: PortConfiguration uses 'model' and 'app_num' (not 'model_slug' and 'app_number')
    configs = PortConfiguration.query.filter_by(model='openai_codex-mini', app_num=1).all()
    if configs:
        for c in configs:
            print(f"Model: {c.model}, App: {c.app_num}, Backend: {c.backend_port}, Frontend: {c.frontend_port}")
    else:
        print("No port configuration found in database for openai_codex-mini app 1")
        
    # Show all configs
    print("\nAll port configurations:")
    all_configs = PortConfiguration.query.all()
    for c in all_configs:
        print(f"  {c.model} app{c.app_num}: backend={c.backend_port}, frontend={c.frontend_port}")
