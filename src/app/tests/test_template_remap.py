import pytest
from app.utils.template_paths import remap_template, _load_mapping

LEGACY_CASES = [
    ("partials/realtime_dashboard.html", "ui/elements/misc/realtime_dashboard.html"),
    ("fragments/api/model-grid.html", "ui/elements/misc/model-grid.html"),
    ("partials/statistics/top_models_table.html", "pages/statistics/partials/top_models_table.html"),
    ("partials/dashboard/_dashboard_stats_inner.html", "ui/elements/dashboard/_dashboard_stats_inner.html"),
    ("partials/apps_grid/model_apps_inline.html", "ui/elements/misc/model_apps_inline.html"),
]

@pytest.mark.parametrize("legacy,new", LEGACY_CASES)
def test_remap_known_legacy_templates(legacy, new):
    mapping = _load_mapping()
    # sanity check mapping contains entry
    assert legacy in mapping, f"Mapping missing legacy path {legacy}"
    assert remap_template(legacy) == new


def test_remap_passthrough_when_unknown():
    unknown = "pages/does/not_exist.html"
    assert remap_template(unknown) == unknown
