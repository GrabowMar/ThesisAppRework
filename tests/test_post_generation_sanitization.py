"""Tests for post-generation code sanitization.

Covers:
- JSX HTML entity decoding in CodeMerger
- Backend port normalization in CodeMerger
- Requirements.txt package name correction & deduplication in DependencyHealer
"""

import re
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers – import the methods under test without needing the full app context
# ---------------------------------------------------------------------------

# We instantiate the classes with minimal setup, pointing at a tmp directory.


def _make_merger(tmp_path: Path) -> "CodeMerger":
    """Create a CodeMerger whose app_dir is a temporary directory."""
    from app.services.generation_v2.code_merger import CodeMerger

    app_dir = tmp_path / "app"
    (app_dir / "backend").mkdir(parents=True)
    (app_dir / "frontend" / "src").mkdir(parents=True)
    return CodeMerger(app_dir)


def _make_healer() -> "DependencyHealer":
    from app.services.dependency_healer import DependencyHealer

    return DependencyHealer(auto_fix=True)


# =========================================================================
# JSX HTML Entity Sanitization
# =========================================================================


class TestJsxHtmlEntitySanitization:
    """Tests for CodeMerger._sanitize_jsx_html_entities()."""

    def test_numeric_entities_decoded(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = 'placeholder="line1&#10;line2&#10;line3"'
        result = merger._sanitize_jsx_html_entities(code)
        assert result == 'placeholder="line1\nline2\nline3"'

    def test_named_entities_decoded(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = 'title="Tom &amp; Jerry &lt;3"'
        result = merger._sanitize_jsx_html_entities(code)
        assert result == 'title="Tom & Jerry <3"'

    def test_hex_entities_decoded(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = 'value="A&#x20;B"'
        result = merger._sanitize_jsx_html_entities(code)
        assert result == 'value="A B"'

    def test_single_quoted_attributes(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "label='one&#10;two'"
        result = merger._sanitize_jsx_html_entities(code)
        assert result == "label='one\ntwo'"

    def test_no_entities_unchanged(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = 'placeholder="normal text"'
        result = merger._sanitize_jsx_html_entities(code)
        assert result == code

    def test_entities_in_assignment_also_decoded(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        # The regex matches any `= "..."` pattern, so JS assignments are
        # also decoded.  This is harmless and actually beneficial.
        code = 'const x = "hello &amp; world";'
        result = merger._sanitize_jsx_html_entities(code)
        assert result == 'const x = "hello & world";'

    def test_standalone_string_unchanged(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        # No = prefix, so standalone strings are left alone
        code = 'console.log("hello &amp; world");'
        result = merger._sanitize_jsx_html_entities(code)
        assert result == code

    def test_quot_entity_decoded(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = 'aria-label="say &quot;hello&quot;"'
        result = merger._sanitize_jsx_html_entities(code)
        assert result == 'aria-label="say "hello""'

    def test_mixed_entities(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = 'placeholder="a&#10;b&amp;c&#x41;"'
        result = merger._sanitize_jsx_html_entities(code)
        assert result == 'placeholder="a\nb&cA"'


# =========================================================================
# Backend Port Normalization
# =========================================================================


class TestBackendPortNormalization:
    """Tests for CodeMerger._fix_backend_port()."""

    def test_simple_port_replacement(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "import os\napp.run(debug=True, host='0.0.0.0', port=5000)"
        result = merger._fix_backend_port(code)
        assert 'port=int(os.environ.get("FLASK_RUN_PORT", 5000))' in result
        assert "port=5000" not in result

    def test_non_default_port(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "import os\napp.run(port=8080)"
        result = merger._fix_backend_port(code)
        assert 'port=int(os.environ.get("FLASK_RUN_PORT", 5000))' in result
        assert "port=8080" not in result

    def test_os_import_added_when_missing(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "from flask import Flask\napp = Flask(__name__)\napp.run(port=5000)"
        result = merger._fix_backend_port(code)
        assert result.startswith("import os\n")
        assert 'os.environ.get("FLASK_RUN_PORT"' in result

    def test_os_import_not_duplicated(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "import os\nfrom flask import Flask\napp.run(port=5000)"
        result = merger._fix_backend_port(code)
        assert result.count("import os") == 1

    def test_no_port_arg_unchanged(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "app.run(debug=True, host='0.0.0.0')"
        result = merger._fix_backend_port(code)
        assert result == code

    def test_port_with_extra_args(self, tmp_path: Path) -> None:
        merger = _make_merger(tmp_path)
        code = "import os\napp.run(debug=True, port=3000, host='0.0.0.0')"
        result = merger._fix_backend_port(code)
        assert 'port=int(os.environ.get("FLASK_RUN_PORT", 5000))' in result
        assert "debug=True" in result
        assert "host='0.0.0.0'" in result


# =========================================================================
# Requirements.txt Normalization
# =========================================================================


class TestRequirementsNormalization:
    """Tests for DependencyHealer._normalize_requirements()."""

    def _write_requirements(self, tmp_path: Path, content: str) -> Path:
        req = tmp_path / "requirements.txt"
        req.write_text(textwrap.dedent(content), encoding="utf-8")
        return req

    def _make_result(self) -> "HealingResult":
        from app.services.dependency_healer import HealingResult

        return HealingResult(success=True, app_path="/tmp/test")

    def test_corrects_jwt_to_pyjwt(self, tmp_path: Path) -> None:
        req = self._write_requirements(tmp_path, "flask\njwt\n")
        healer = _make_healer()
        result = self._make_result()
        healer._normalize_requirements(req, result)
        content = req.read_text()
        assert "PyJWT" in content
        assert "\njwt\n" not in content
        assert result.issues_fixed >= 1

    def test_corrects_dotenv(self, tmp_path: Path) -> None:
        req = self._write_requirements(tmp_path, "dotenv==1.0\n")
        healer = _make_healer()
        result = self._make_result()
        healer._normalize_requirements(req, result)
        content = req.read_text()
        assert "python-dotenv==1.0" in content
        assert content.startswith("python-dotenv")

    def test_preserves_version_specifier(self, tmp_path: Path) -> None:
        req = self._write_requirements(tmp_path, "PIL>=9.0\n")
        healer = _make_healer()
        result = self._make_result()
        healer._normalize_requirements(req, result)
        content = req.read_text()
        assert "Pillow>=9.0" in content

    def test_deduplicates_after_correction(self, tmp_path: Path) -> None:
        """If both 'jwt' and 'PyJWT' are listed, after correction only one PyJWT remains."""
        req = self._write_requirements(tmp_path, "jwt\nPyJWT\nflask\n")
        healer = _make_healer()
        result = self._make_result()
        healer._normalize_requirements(req, result)
        content = req.read_text()
        # Should only have PyJWT once
        assert content.lower().count("pyjwt") == 1
        assert "flask" in content

    def test_deduplicates_case_insensitive(self, tmp_path: Path) -> None:
        req = self._write_requirements(tmp_path, "Flask\nflask\n")
        healer = _make_healer()
        result = self._make_result()
        healer._normalize_requirements(req, result)
        content = req.read_text()
        lines = [l for l in content.splitlines() if l.strip() and not l.startswith('#')]
        assert len(lines) == 1

    def test_preserves_comments(self, tmp_path: Path) -> None:
        req = self._write_requirements(tmp_path, "# web deps\nflask\njwt\n")
        healer = _make_healer()
        result = self._make_result()
        healer._normalize_requirements(req, result)
        content = req.read_text()
        assert "# web deps" in content

    def test_no_changes_when_correct(self, tmp_path: Path) -> None:
        req = self._write_requirements(tmp_path, "Flask\nPyJWT\npython-dotenv\n")
        healer = _make_healer()
        result = self._make_result()
        healer._normalize_requirements(req, result)
        assert result.issues_found == 0
        assert result.issues_fixed == 0

    def test_nonexistent_file_is_noop(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        healer = _make_healer()
        result = self._make_result()
        healer._normalize_requirements(req, result)
        assert result.issues_found == 0

    def test_multiple_corrections(self, tmp_path: Path) -> None:
        req = self._write_requirements(tmp_path, "jwt\ndotenv\nyaml\nflask\n")
        healer = _make_healer()
        result = self._make_result()
        healer._normalize_requirements(req, result)
        content = req.read_text()
        assert "PyJWT" in content
        assert "python-dotenv" in content
        assert "PyYAML" in content
        assert "flask" in content
        assert result.issues_fixed == 3
