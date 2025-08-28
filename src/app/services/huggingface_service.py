"""Hugging Face Service (Deprecated)
=================================

The former HuggingFaceService has been removed. Model metadata should be
retrieved via direct API client utilities or cached during batch import
phases. This module remains only to prevent ImportError for legacy imports.
"""

from __future__ import annotations

from .service_base import deprecation_warning

DEPRECATED = True


class HuggingFaceService:  # pragma: no cover - deprecated shim
	def __init__(self, *_, **__):
		deprecation_warning(
			"HuggingFaceService is deprecated. Use direct API utilities instead.")

	def fetch_model_card(self, *_, **__):  # compatibility placeholder
		deprecation_warning("fetch_model_card deprecated – no implementation.")
		raise NotImplementedError("HuggingFaceService deprecated.")


__all__ = ["HuggingFaceService", "DEPRECATED"]
