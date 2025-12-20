#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')
from app.factory import create_app
from app.models.container_action import ContainerAction, ContainerActionStatus

app = create_app()
with app.app_context():
    # Recent actions
    recent = ContainerAction.query.order_by(ContainerAction.id.desc()).limit(15).all()
    print("\n=== RECENT CONTAINER ACTIONS ===")
    for a in recent:
        err = (a.error_message or "OK")[:50]
        print(f"  {a.action_type.value:7} app{a.target_app_number}: {a.status.value:10} | {err}")
    
    # Count by status
    print("\n=== STATUS COUNTS ===")
    for status in ContainerActionStatus:
        count = ContainerAction.query.filter_by(status=status).count()
        if count > 0:
            print(f"  {status.value}: {count}")
