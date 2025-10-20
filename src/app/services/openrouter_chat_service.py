"""
OpenRouter Chat Completion Service
==================================

A dedicated, reusable service for making chat completion requests to the OpenRouter API.
This service encapsulates the logic for handling authentication, headers, payload construction,
and the research-mode provider override.
"""

import aiohttp
import json
import logging
import os
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class OpenRouterChatService:
    """
    Service for making chat completion requests to the OpenRouter API.
    """

    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY', '')
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.site_url = os.getenv("OPENROUTER_SITE_URL", "https://thesis-research-platform.local")
        self.site_name = os.getenv("OPENROUTER_SITE_NAME", "Thesis Research Platform")
        self.allow_all_providers = os.getenv("OPENROUTER_ALLOW_ALL_PROVIDERS", "true").lower() == "true"

        if not self.api_key:
            logger.warning("OpenRouter API key is not configured. Set OPENROUTER_API_KEY in .env")
        
        if self.allow_all_providers:
            logger.info("OpenRouterChatService initialized in research mode (provider override enabled).")
        else:
            logger.info("OpenRouterChatService initialized in standard mode (respecting account data policies).")

    def _get_headers(self) -> Dict[str, str]:
        """Constructs the required headers for an OpenRouter API request."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
            "Content-Type": "application/json"
        }

    def _build_payload(self, model: str, messages: list, temperature: float, max_tokens: int) -> Dict[str, Any]:
        """Constructs the payload for the chat completion request."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        if self.allow_all_providers:
            payload["provider"] = {
                "allow_fallbacks": True,
                "data_collection": "allow"
            }
        return payload

    async def generate_chat_completion(
        self, 
        model: str, 
        messages: list, 
        temperature: float = 0.3, 
        max_tokens: int = 16000
    ) -> Tuple[bool, Dict[str, Any], int]:
        """
        Makes a chat completion request to the OpenRouter API.

        Args:
            model: The OpenRouter model ID.
            messages: A list of message objects for the chat history.
            temperature: The sampling temperature.
            max_tokens: The maximum number of tokens to generate.

        Returns:
            A tuple containing:
            - bool: Success status.
            - dict: The JSON response from the API or an error dictionary.
            - int: The HTTP status code.
        """
        if not self.api_key:
            return False, {"error": "OpenRouter API key not set"}, 401

        headers = self._get_headers()
        payload = self._build_payload(model, messages, temperature, max_tokens)

        logger.info(f"Sending chat completion request to model: {model}")
        logger.debug(f"Request URL: {self.api_url}")
        logger.debug(f"Payload model field: {payload.get('model')}")
        logger.debug(f"Full payload: {json.dumps(payload, indent=2)}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    response_data = await response.json()
                    if response.status == 200:
                        logger.info(f"Successfully received chat completion from {model}.")
                        return True, response_data, response.status
                    else:
                        error_message = response_data.get("error", {}).get("message", "Unknown API error")
                        logger.error(f"OpenRouter API error (Status: {response.status}, Model: {model}): {error_message}")
                        return False, response_data, response.status

        except aiohttp.ClientConnectorError as e:
            logger.error(f"Network connection error to OpenRouter: {e}")
            return False, {"error": f"Network error: {e}"}, 503
        except Exception as e:
            logger.error(f"An unexpected error occurred during chat completion: {e}")
            return False, {"error": f"Unexpected error: {e}"}, 500

# Singleton instance
_chat_service = None

def get_openrouter_chat_service() -> "OpenRouterChatService":
    """Returns a singleton instance of the OpenRouterChatService."""
    global _chat_service
    if _chat_service is None:
        _chat_service = OpenRouterChatService()
    return _chat_service
