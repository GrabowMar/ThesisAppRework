"""Tests for CodeMerger fix methods.

Covers:
- _fix_api_urls: localhost URL removal for Docker networking
- _fix_icon_imports: FA hallucination correction, heroicons stripping
- fixes_applied property: accumulation and isolation
"""

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_merger(tmp_path: Path) -> "CodeMerger":
    """Create a CodeMerger whose app_dir is a temporary directory."""
    from app.services.generation_v2.code_merger import CodeMerger

    app_dir = tmp_path / "app"
    (app_dir / "backend").mkdir(parents=True)
    (app_dir / "frontend" / "src").mkdir(parents=True)
    return CodeMerger(app_dir)


# =========================================================================
# _fix_api_urls
# =========================================================================


@pytest.mark.unit
class TestFixApiUrls:
    """Tests for CodeMerger._fix_api_urls()."""

    def test_removes_localhost_5000(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = 'const API = "http://localhost:5000/api/items";'
        result = merger._fix_api_urls(code)
        assert "localhost:5000" not in result
        assert '"/api/items"' in result

    def test_removes_localhost_5001(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "fetch('http://localhost:5001/api/data')"
        result = merger._fix_api_urls(code)
        assert "localhost:5001" not in result
        assert "'/api/data'" in result

    def test_preserves_other_localhost_ports(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = 'const WS = "http://localhost:3000/ws";'
        result = merger._fix_api_urls(code)
        assert result == code

    def test_tracks_fix_in_fixes_applied(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        merger._fix_api_urls('fetch("http://localhost:5000/api")')
        assert any("API URLs" in f for f in merger.fixes_applied)

    def test_noop_when_no_localhost(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = 'fetch("/api/items")'
        result = merger._fix_api_urls(code)
        assert result == code
        assert merger.fixes_applied == []

    def test_removes_multiple_occurrences(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = (
            'const a = "http://localhost:5000/api/a";\n'
            'const b = "http://localhost:5001/api/b";'
        )
        result = merger._fix_api_urls(code)
        assert "localhost:5000" not in result
        assert "localhost:5001" not in result
        assert '"/api/a"' in result
        assert '"/api/b"' in result

    def test_guard_is_case_sensitive(self, tmp_path: Path) -> None:
        """The guard condition uses plain ``in`` — mixed-case bypasses it."""
        merger = _make_merger(tmp_path)
        code = 'fetch("http://Localhost:5000/api")'
        result = merger._fix_api_urls(code)
        # re.sub has IGNORECASE, but the guard `'localhost:5000' in code` is
        # case-sensitive, so mixed-case won't trigger the substitution.
        assert result == code


# =========================================================================
# _fix_icon_imports
# =========================================================================


@pytest.mark.unit
class TestFixIconImports:
    """Tests for CodeMerger._fix_icon_imports()."""

    def test_corrects_fa_alert_circle(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "import { faAlertCircle } from '@fortawesome/free-solid-svg-icons';"
        result = merger._fix_icon_imports(code)
        assert "faCircleExclamation" in result
        assert "faAlertCircle" not in result

    def test_corrects_fa_tasks(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "<FontAwesomeIcon icon={faTasks} />"
        result = merger._fix_icon_imports(code)
        assert "faListCheck" in result
        assert "faTasks" not in result

    def test_corrects_multiple_fa_icons_in_one_pass(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = (
            "import { faBarChart, faDotCircle, faShield } "
            "from '@fortawesome/free-solid-svg-icons';"
        )
        result = merger._fix_icon_imports(code)
        assert "faChartBar" in result
        assert "faCircleDot" in result
        assert "faShieldHalved" in result
        # Originals gone
        assert "faBarChart" not in result
        assert "faDotCircle" not in result
        assert "faShield}" not in result  # faShield replaced with faShieldHalved

    def test_strips_heroicons_import(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = (
            "import { CheckIcon, XIcon } from '@heroicons/react/24/outline';\n"
            "function App() { return <div />; }\n"
        )
        result = merger._fix_icon_imports(code)
        assert "@heroicons/react" not in result
        assert "auto-removed" in result
        assert "function App" in result

    def test_leaves_valid_fa_names_untouched(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "import { faCoffee, faUser } from '@fortawesome/free-solid-svg-icons';"
        result = merger._fix_icon_imports(code)
        assert result == code

    def test_tracks_fa_fixes_in_fixes_applied(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        merger._fix_icon_imports("<FontAwesomeIcon icon={faZap} />")
        fixes = merger.fixes_applied
        assert len(fixes) == 1
        assert "faZap" in fixes[0]
        assert "faBolt" in fixes[0]

    def test_tracks_heroicons_in_fixes_applied(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        merger._fix_icon_imports(
            "import { CheckIcon } from '@heroicons/react/24/solid';"
        )
        fixes = merger.fixes_applied
        assert any("heroicons" in f for f in fixes)

    def test_noop_when_no_icon_issues(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "const x = 1;"
        result = merger._fix_icon_imports(code)
        assert result == code
        assert merger.fixes_applied == []


# =========================================================================
# fixes_applied property
# =========================================================================


@pytest.mark.unit
class TestFixesAppliedProperty:
    """Tests for the CodeMerger.fixes_applied property."""

    def test_empty_on_fresh_merger(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        assert merger.fixes_applied == []

    def test_returns_copy_not_reference(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        merger._fix_api_urls('fetch("http://localhost:5000/api")')
        first = merger.fixes_applied
        first.append("rogue entry")
        assert "rogue entry" not in merger.fixes_applied

    def test_accumulates_across_fix_methods(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        merger._fix_api_urls('fetch("http://localhost:5000/api")')
        merger._fix_icon_imports("<FontAwesomeIcon icon={faZap} />")
        merger._fix_backend_port("app.run(port=5000)")
        fixes = merger.fixes_applied
        assert len(fixes) == 3
        assert any("API URLs" in f for f in fixes)
        assert any("icon" in f.lower() for f in fixes)
        assert any("port" in f.lower() or "FLASK_RUN_PORT" in f for f in fixes)

    def test_jsx_entity_sanitization_contributes(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        merger._sanitize_jsx_html_entities('placeholder="a&#10;b"')
        fixes = merger.fixes_applied
        assert len(fixes) == 1
        assert any("HTML entities" in f or "entities" in f.lower() for f in fixes)
