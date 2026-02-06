"""Tests for DependencyHealer healing order and missing-dep detection.

Verifies that ``_heal_backend`` runs ``_normalize_requirements`` before
the missing-dependency scan, so corrected names (e.g. ``jwt`` → ``PyJWT``)
are not re-flagged as missing.
"""

import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_healer() -> "DependencyHealer":
    from app.services.dependency_healer import DependencyHealer
    return DependencyHealer(auto_fix=True)


def _make_result() -> "HealingResult":
    from app.services.dependency_healer import HealingResult
    return HealingResult(success=True, app_path="/tmp/test")


def _setup_backend(tmp_path: Path, requirements: str, app_py: str) -> Path:
    """Create a minimal backend directory with requirements.txt and app.py."""
    backend = tmp_path / "backend"
    backend.mkdir(parents=True)
    (backend / "requirements.txt").write_text(
        textwrap.dedent(requirements), encoding="utf-8"
    )
    (backend / "app.py").write_text(
        textwrap.dedent(app_py), encoding="utf-8"
    )
    return backend


# =========================================================================
# Healing order tests
# =========================================================================


@pytest.mark.unit
class TestHealingOrder:
    """Verify normalization-before-scan ordering in _heal_backend."""

    def test_jwt_normalized_not_reflagged(self, tmp_path: Path) -> None:
        """``jwt`` in requirements should be corrected to ``PyJWT`` and NOT
        flagged as a missing dependency afterwards."""
        backend = _setup_backend(
            tmp_path,
            requirements="flask\njwt\n",
            app_py=(
                "from flask import Flask\n"
                "import jwt\n"
                "app = Flask(__name__)\n"
            ),
        )
        healer = _make_healer()
        result = _make_result()
        healer._heal_backend(backend, result)

        reqs = (backend / "requirements.txt").read_text()
        assert "PyJWT" in reqs
        # jwt should NOT appear as a missing dep that got appended
        assert reqs.count("PyJWT") == 1
        # No "Auto-added by DependencyHealer" section for jwt
        assert "Auto-added" not in reqs

    def test_truly_missing_dep_detected_and_added(self, tmp_path: Path) -> None:
        """A dependency imported in code but absent from requirements.txt
        should be detected and added."""
        backend = _setup_backend(
            tmp_path,
            requirements="flask\n",
            app_py=(
                "from flask import Flask\n"
                "import requests\n"
                "app = Flask(__name__)\n"
            ),
        )
        healer = _make_healer()
        result = _make_result()
        healer._heal_backend(backend, result)

        reqs = (backend / "requirements.txt").read_text()
        assert "requests" in reqs
        assert result.issues_found >= 1

    def test_no_issues_when_all_deps_present(self, tmp_path: Path) -> None:
        """No issues reported when requirements already list all imports."""
        backend = _setup_backend(
            tmp_path,
            requirements="Flask==3.0.0\nPyJWT==2.8.0\n",
            app_py=(
                "from flask import Flask\n"
                "import jwt\n"
                "app = Flask(__name__)\n"
            ),
        )
        healer = _make_healer()
        result = _make_result()
        healer._heal_backend(backend, result)

        reqs = (backend / "requirements.txt").read_text()
        # No additions
        assert "Auto-added" not in reqs
