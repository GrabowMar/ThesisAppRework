# Business Logic Services - Shared service functions
# This file contains business logic used by both user and admin routes
from models import db
from datetime import datetime

# ============================================================================
# SERVICE FUNCTIONS - Implement business logic here
# ============================================================================
#
# Services encapsulate business logic that can be reused across routes.
# Keep routes thin - they should only handle HTTP request/response.
#
# Example service pattern:
#
# def get_all_items(include_inactive=False):
#     """Get all items, optionally including inactive ones."""
#     query = Item.query
#     if not include_inactive:
#         query = query.filter_by(is_active=True)
#     return query.order_by(Item.created_at.desc()).all()
#
# def create_item(data):
#     """Create a new item with validation."""
#     if not data.get('name'):
#         raise ValueError("Name is required")
#     item = Item(name=data['name'], description=data.get('description'))
#     db.session.add(item)
#     db.session.commit()
#     return item
#
# def get_statistics():
#     """Get aggregate statistics for admin dashboard."""
#     return {
#         'total_items': Item.query.count(),
#         'active_items': Item.query.filter_by(is_active=True).count(),
#     }
#
# IMPLEMENT YOUR SERVICES BELOW:
# ============================================================================

