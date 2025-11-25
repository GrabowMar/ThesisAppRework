import os
import re
from dataclasses import dataclass
from typing import List, Dict, Optional

from flask import current_app


@dataclass
class DocItem:
    title: str
    filename: str
    relpath: str  # relative to docs root
    category: str


@dataclass
class DocSection:
    name: str
    slug: str
    items: List[DocItem]


class DocsService:
    """Aggregates markdown files in /docs into knowledge base sections."""

    # Only expose this curated set in the UI to consolidate documentation
    # ALLOWED_DOCS = {
    #     "README.md",
    #     "QUICKSTART.md",
    #     "ARCHITECTURE.md",
    #     "OPERATIONS.md",
    #     "DEVELOPMENT_GUIDE.md",
    #     "SIMPLE_GENERATION_SYSTEM.md",
    # }

    CATEGORY_RULES: List[tuple] = [
        (r"^OPENROUTER_", "OpenRouter"),
        (r"^DOCKER_", "Docker"),
        (r"^CONTAINER_", "Container Management"),
        (r"^AUTHENTICATION_", "Authentication"),
        (r"^SECURITY_", "Security"),
        (r"^DASHBOARD_", "Dashboard"),
        (r"^SAMPLE_GENERATOR_|^SIMPLE_GENERATION_", "Generator"),
        (r"^ANALYZER_", "Analyzer"),
        (r"^RESEARCH_", "Research"),
        (r"^PRODUCTION_|^OVH_", "Deployment"),
        (r"^GETTING_STARTED|^QUICK_REF|^QUICK_START", "Quick Start"),
        (r"^MODELS_", "Models"),
        (r"^METADATA_", "Metadata"),
    ]

    @classmethod
    def _docs_root(cls) -> str:
        # src/app -> project root is two levels up
        return os.path.join(current_app.root_path, "..", "..", "docs")

    @classmethod
    def _slugify(cls, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip()).strip("-").lower()
        return slug

    @classmethod
    def _infer_category(cls, filename: str) -> str:
        base = os.path.basename(filename)
        for pattern, category in cls.CATEGORY_RULES:
            if re.match(pattern, base):
                return category
        return "General"

    @classmethod
    def list_docs(cls) -> List[DocItem]:
        root = cls._docs_root()
        items: List[DocItem] = []
        if not os.path.exists(root):
            return items

        for entry in os.listdir(root):
            full = os.path.join(root, entry)
            if os.path.isdir(full):
                # include nested docs (one level)
                for sub in os.listdir(full):
                    if sub.endswith(".md"):
                        # skip duplicates like "XYZ copy.md"
                        if os.path.splitext(sub)[0].strip().lower().endswith(" copy"):
                            continue
                        rel = os.path.join(entry, sub).replace("\\", "/")
                        items.append(
                            DocItem(
                                title=os.path.splitext(sub)[0].replace("_", " ").title(),
                                filename=sub,
                                relpath=rel,
                                category=entry.title(),
                            )
                        )
            elif entry.endswith(".md"):
                # skip duplicates like "XYZ copy.md"
                if os.path.splitext(entry)[0].strip().lower().endswith(" copy"):
                    continue
                items.append(
                    DocItem(
                        title=os.path.splitext(entry)[0].replace("_", " ").title(),
                        filename=entry,
                        relpath=entry,
                        category=cls._infer_category(entry),
                    )
                )
        # Filter down to the curated allowlist
        # items = [
        #     it for it in items
        #     if os.path.basename(it.relpath) in cls.ALLOWED_DOCS
        # ]
        # stable sort by title
        items.sort(key=lambda i: (i.category, i.title))
        return items

    @classmethod
    def build_sections(cls) -> List[DocSection]:
        items = cls.list_docs()
        by_cat: Dict[str, List[DocItem]] = {}
        for it in items:
            by_cat.setdefault(it.category, []).append(it)
        sections: List[DocSection] = []
        for cat, cat_items in sorted(by_cat.items(), key=lambda kv: kv[0].lower()):
            sections.append(DocSection(name=cat, slug=cls._slugify(cat), items=cat_items))
        return sections

    @classmethod
    def search(cls, query: Optional[str]) -> List[DocItem]:
        if not query:
            return []
        q = query.strip().lower()
        # search only within curated docs
        results = [
            it for it in cls.list_docs()
            if q in it.title.lower() or q in it.filename.lower() or q in it.category.lower()
        ]
        # limit to avoid overloading UI
        return results[:50]
