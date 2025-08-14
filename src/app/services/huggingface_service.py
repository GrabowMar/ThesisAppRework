"""
Hugging Face Service
====================

Fetch model metadata from Hugging Face Hub public REST API with light caching.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class HuggingFaceService:
    """Service to retrieve model info from Hugging Face Hub.

    Notes:
        - Uses public endpoints; token is optional but recommended for higher limits.
        - Provides simple in-memory caching to avoid excessive calls.
    """

    def __init__(self) -> None:
        self.api_base = "https://huggingface.co/api"
        self.token = os.getenv("HUGGINGFACE_TOKEN")
        self._cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self.ttl = int(os.getenv("HF_CACHE_TTL_SECONDS", "600"))  # 10 minutes

        if not self.token:
            logger.info("HF token not set. Using unauthenticated requests to public API.")

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_cached(self, key: str) -> Optional[Any]:
        exp = self._cache_expiry.get(key)
        if not exp:
            return None
        if datetime.now(timezone.utc) < exp:
            return self._cache.get(key)
        # expired
        self._cache.pop(key, None)
        self._cache_expiry.pop(key, None)
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        self._cache[key] = value
        self._cache_expiry[key] = datetime.now(timezone.utc) + timedelta(seconds=self.ttl)

    def search_models(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search Hub models by free-text query."""
        key = f"search:{query}:{limit}"
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        try:
            resp = requests.get(
                f"{self.api_base}/models",
                headers=self._headers(),
                params={"search": query, "limit": limit},
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    self._set_cached(key, data)
                    return data
            logger.warning("HF search failed %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.error("HF search error: %s", e)
        return []

    def get_model_info(self, repo_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed model info for a specific repo id (e.g., meta-llama/Llama-3-8B)."""
        key = f"model:{repo_id}"
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        try:
            resp = requests.get(
                f"{self.api_base}/models/{repo_id}", headers=self._headers(), timeout=20
            )
            if resp.status_code == 200:
                data = resp.json()
                self._set_cached(key, data)
                return data
            logger.info("HF model not found %s (%s)", repo_id, resp.status_code)
        except Exception as e:
            logger.error("HF get_model_info error: %s", e)
        return None

    def enrich_model_data(self, provider: str, model_name: str) -> Dict[str, Any]:
        """Attempt to enrich with HF data using a simple search heuristic.

        We query by model_name first; if ambiguous, return top result.
        """
        result: Dict[str, Any] = {}
        query = model_name
        # Some providers add helpful context to the search
        if provider:
            query = f"{provider} {model_name}"

        matches = self.search_models(query, limit=1)
        if not matches:
            return result
        top = matches[0]
        repo_id = top.get("id") or top.get("modelId")
        if not repo_id:
            return result

        info = self.get_model_info(repo_id) or top
        # Extract useful fields
        result.update(
            {
                "hf_repo_id": repo_id,
                "hf_likes": info.get("likes"),
                "hf_downloads": info.get("downloads"),
                "hf_license": (info.get("cardData") or {}).get("license") or info.get("license"),
                "hf_tags": info.get("tags"),
                "hf_pipeline_tag": info.get("pipeline_tag") or (info.get("transformersInfo") or {}).get("pipeline_tag"),
                "hf_last_modified": info.get("lastModified") or info.get("createdAt"),
                "huggingface_data": info,
            }
        )
        return result
