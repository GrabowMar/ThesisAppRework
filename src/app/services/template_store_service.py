"""Template Store Service
=========================
Centralized management for:
- Code scaffolding templates (in CODE_TEMPLATES_DIR)
- App templates (prompt/enrichment templates) (in APP_TEMPLATES_DIR)
- Scaffolding profiles (stored as JSON under PROFILES_DIR)
- Versioned history for edits (stored under HISTORY_DIR/<category>/<relpath>/*.timestamp.ext)

Features:
- CRUD operations
- Versioning (automatic backup on save with timestamp)
- Listing & searching
- Profile management (grouping templates + arbitrary metadata)
- Legacy migration: detects deprecated nested code_templates/code_templates and flags or removes
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional, Any
import json
import shutil
import time
import logging

from app.paths import CODE_TEMPLATES_DIR, APP_TEMPLATES_DIR, PROFILES_DIR, HISTORY_DIR

logger = logging.getLogger(__name__)

@dataclass
class TemplateMeta:
    category: str  # 'code' | 'app'
    relative_path: str
    size: int
    modified: float
    versions: int = 0
    placeholders: List[str] | None = None

@dataclass
class Profile:
    name: str
    description: str | None
    templates: List[str]  # list of relative paths across categories
    config: Optional[Dict[str, Any]] = None  # arbitrary additional configuration

class TemplateStoreService:
    CODE_CATEGORY = 'code'
    APP_CATEGORY = 'app'

    def __init__(self, auto_migrate: bool = True):
        self.code_dir = CODE_TEMPLATES_DIR
        self.app_dir = APP_TEMPLATES_DIR
        self.profiles_dir = PROFILES_DIR
        self.history_dir = HISTORY_DIR
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        if auto_migrate:
            self._check_legacy_layout()

    # ---------------- Legacy / Migration ----------------
    def _check_legacy_layout(self):
        legacy = self.code_dir / 'code_templates'
        if legacy.exists():
            logger.warning("Legacy nested code_templates directory detected: %s", legacy)
            try:
                # Move files up if any not present
                for src in legacy.rglob('*'):
                    if src.is_file():
                        rel = src.relative_to(legacy)
                        dest = self.code_dir / rel
                        if not dest.exists():
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dest)
                shutil.rmtree(legacy)
                logger.info("Legacy nested directory removed after migration")
            except Exception as e:  # noqa: BLE001
                logger.error("Failed migrating legacy templates: %s", e)

    # ---------------- Utility ----------------
    def _resolve(self, category: str, relative_path: str) -> Path:
        base = self.code_dir if category == self.CODE_CATEGORY else self.app_dir
        return base / relative_path

    def _history_dir_for(self, category: str, relative_path: str) -> Path:
        return self.history_dir / category / relative_path

    def _scan_placeholders(self, content: str) -> List[str]:
        import re
        return sorted(set(re.findall(r"{{\s*([a-zA-Z0-9_]+)\s*}}", content)))

    # ---------------- Listing ----------------
    def list(self, category: Optional[str] = None) -> List[TemplateMeta]:
        metas: List[TemplateMeta] = []
        targets: List[tuple[str, Path]] = []
        if category:
            if category == self.CODE_CATEGORY:
                targets.append((self.CODE_CATEGORY, self.code_dir))
            elif category == self.APP_CATEGORY:
                targets.append((self.APP_CATEGORY, self.app_dir))
        else:
            targets.extend([(self.CODE_CATEGORY, self.code_dir), (self.APP_CATEGORY, self.app_dir)])
        for cat, base in targets:
            if not base.exists():
                continue
            for p in base.rglob('*'):
                if p.is_file():
                    rel = p.relative_to(base).as_posix()
                    hist = self._history_dir_for(cat, rel)
                    versions = len(list(hist.glob('*'))) if hist.exists() else 0
                    metas.append(TemplateMeta(
                        category=cat,
                        relative_path=rel,
                        size=p.stat().st_size,
                        modified=p.stat().st_mtime,
                        versions=versions,
                    ))
        return metas

    # ---------------- Read ----------------
    def read(self, category: str, relative_path: str) -> Dict[str, Any]:
        path = self._resolve(category, relative_path)
        if not path.exists():
            raise FileNotFoundError(relative_path)
        content = path.read_text(encoding='utf-8', errors='ignore')
        return {
            'category': category,
            'relative_path': relative_path,
            'content': content,
            'placeholders': self._scan_placeholders(content)
        }

    # ---------------- Create / Update ----------------
    def save(self, category: str, relative_path: str, content: str) -> Dict[str, Any]:
        path = self._resolve(category, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Backup existing
        if path.exists():
            hist_dir = self._history_dir_for(category, relative_path)
            hist_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            backup = hist_dir / f"{ts}.bak"
            try:
                shutil.copy2(path, backup)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to create backup for %s: %s", relative_path, e)
        path.write_text(content, encoding='utf-8')
        meta = self.read(category, relative_path)
        return meta

    # ---------------- Delete ----------------
    def delete(self, category: str, relative_path: str) -> bool:
        path = self._resolve(category, relative_path)
        if not path.exists():
            return False
        path.unlink()
        return True

    # ---------------- Profiles ----------------
    def list_profiles(self) -> List[Profile]:
        profiles: List[Profile] = []
        for p in self.profiles_dir.glob('*.json'):
            try:
                data = json.loads(p.read_text(encoding='utf-8', errors='ignore'))
                profiles.append(Profile(**data))
            except Exception:  # noqa: BLE001
                logger.warning("Invalid profile file skipped: %s", p)
        return profiles

    def save_profile(self, profile: Profile) -> Profile:
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        path = self.profiles_dir / f"{profile.name}.json"
        path.write_text(json.dumps(asdict(profile), indent=2), encoding='utf-8')
        return profile

    def delete_profile(self, name: str) -> bool:
        path = self.profiles_dir / f"{name}.json"
        if path.exists():
            path.unlink()
            return True
        return False

# Singleton accessor
_template_store: Optional[TemplateStoreService] = None

def get_template_store_service() -> TemplateStoreService:
    global _template_store
    if _template_store is None:
        _template_store = TemplateStoreService()
    return _template_store
