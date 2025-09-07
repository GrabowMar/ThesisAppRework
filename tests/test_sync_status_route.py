import json
from app.extensions import db
from app.models import ModelCapability, GeneratedApplication


def create_model_and_apps(app_ctx, slug="test_model_sync", apps=3):
    with app_ctx.app_context():
        m = ModelCapability(
            model_id=slug,
            canonical_slug=slug,
            provider="test_provider",
            model_name="Test Model Sync"
        )
        db.session.add(m)
        db.session.commit()
        for i in range(1, apps+1):
            ga = GeneratedApplication(
                model_slug=slug,
                app_number=i,
                app_type="web_app",
                provider="test_provider",
                container_status="running" if i % 2 == 0 else "stopped",
                has_docker_compose=True if i == 1 else False
            )
            db.session.add(ga)
        db.session.commit()
        return slug


def test_sync_status_json(client, app):
    slug = create_model_and_apps(app)
    resp = client.post(f"/api/model/{slug}/containers/sync-status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["model_slug"] == slug
    assert data["data"]["count"] == 3
    statuses = {a["app_number"]: a["status"] for a in data["data"]["applications"]}
    assert statuses[1] == "stopped"
    assert statuses[2] == "running"


def test_sync_status_html_fragment_cards(client, app):
    slug = create_model_and_apps(app, slug="test_model_cards")
    # Simulate HTMX fragment request for cards (grid variant) by specifying format=html
    resp = client.post(f"/api/model/{slug}/containers/sync-status?format=html", headers={"HX-Request": "true", "HX-Target": "model-foo .model-apps"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Should contain card markup and app numbers
    assert "card" in body
    assert f"#{1}" in body
    assert f"#{2}" in body


def test_sync_status_html_fragment_table_rows(client, app):
    slug = create_model_and_apps(app, slug="test_model_rows")
    # Simulate table variant by HTMX target containing model-apps-table-body
    resp = client.post(f"/api/model/{slug}/containers/sync-status?format=html", headers={"HX-Request": "true", "HX-Target": "acc-x .model-apps-table-body"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Expect table rows (<tr>) without full page markup
    assert "<tr" in body
    assert "card" not in body  # ensure we didn't render the cards variant
    assert f"#{1}" in body
    assert f"#{2}" in body
