"""
OpenRouter Chat Completion Service
==================================

A dedicated, reusable service for making chat completion requests to the OpenRouter API.
This service encapsulates the logic for handling authentication, headers, payload construction,
and the research-mode provider override.

Features:
- Circuit breaker pattern for failure detection (non-blocking)
- Exponential backoff with jitter for retries
- Automatic recovery after API stabilization

NOTE: Rate limiting is handled at the pipeline orchestration level, not here.
This service focuses on making individual API calls reliably.
"""

import aiohttp
import asyncio
import json
import logging
import os
import time
import threading
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class SimpleCircuitBreaker:
    """Thread-safe, non-blocking circuit breaker for API calls.
    
    This is a simplified version that works correctly with ThreadPoolExecutor.
    """
    
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"  # closed, open, half_open
        self._lock = threading.Lock()
        logger.info(f"SimpleCircuitBreaker '{name}' initialized (threshold={failure_threshold}, recovery={recovery_timeout}s)")
    
    def can_execute(self) -> Tuple[bool, float]:
        """Check if request can proceed. Returns (allowed, retry_after_seconds)."""
        with self._lock:
            if self._state == "closed":
                return True, 0
            
            if self._state == "open":
                # Check if recovery timeout has elapsed
                if self._last_failure_time:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.recovery_timeout:
                        self._state = "half_open"
                        logger.info(f"CircuitBreaker '{self.name}' → HALF_OPEN (testing recovery)")
                        return True, 0
                    return False, self.recovery_timeout - elapsed
                return False, self.recovery_timeout
            
            # half_open - allow one test request
            return True, 0
    
    def record_success(self) -> None:
        """Record successful call."""
        with self._lock:
            if self._state == "half_open":
                logger.info(f"CircuitBreaker '{self.name}' → CLOSED (recovered)")
            self._state = "closed"
            self._failures = 0
    
    def record_failure(self, error: str = "") -> None:
        """Record failed call."""
        with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()
            
            if self._state == "half_open":
                self._state = "open"
                logger.warning(f"CircuitBreaker '{self.name}' → OPEN (recovery failed: {error})")
            elif self._failures >= self.failure_threshold:
                self._state = "open"
                logger.warning(
                    f"CircuitBreaker '{self.name}' → OPEN after {self._failures} failures. "
                    f"Recovery in {self.recovery_timeout}s"
                )
    
    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        with self._lock:
            retry_after = 0
            if self._state == "open" and self._last_failure_time:
                retry_after = max(0, self.recovery_timeout - (time.time() - self._last_failure_time))
            return {
                "state": self._state,
                "failures": self._failures,
                "retry_after": retry_after
            }


# Global circuit breaker instance
_circuit_breaker: Optional[SimpleCircuitBreaker] = None
_circuit_lock = threading.Lock()


def get_circuit_breaker() -> SimpleCircuitBreaker:
    """Get the global OpenRouter circuit breaker."""
    global _circuit_breaker
    with _circuit_lock:
        if _circuit_breaker is None:
            _circuit_breaker = SimpleCircuitBreaker(
                name="openrouter",
                failure_threshold=3,  # Open after 3 consecutive failures
                recovery_timeout=90.0  # Wait 90 seconds before retry
            )
    return _circuit_breaker


class OpenRouterChatService:
    """
    Service for making chat completion requests to the OpenRouter API.
    
    Uses a non-blocking circuit breaker to detect API instability.
    Rate limiting is handled at the orchestration layer (pipeline service).
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
        max_tokens: int = 16000,
        max_retries: int = 2,
        skip_rate_limiting: bool = False
    ) -> Tuple[bool, Dict[str, Any], int]:
        """
        Makes a chat completion request to the OpenRouter API with retry logic.

        Uses a non-blocking circuit breaker for failure detection.

        Args:
            model: The OpenRouter model ID.
            messages: A list of message objects for the chat history.
            temperature: The sampling temperature.
            max_tokens: The maximum number of tokens to generate.
            max_retries: Number of retries for network errors (default: 2).
            skip_rate_limiting: Ignored (rate limiting moved to orchestration layer).

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

        # Compact logging: model + max_tokens for context
        short_model = model.split('/')[-1] if '/' in model else model
        
        # ========== CIRCUIT BREAKER CHECK (non-blocking) ==========
        circuit = get_circuit_breaker()
        can_proceed, retry_after = circuit.can_execute()
        
        if not can_proceed:
            error_msg = f"Circuit breaker OPEN - API temporarily unavailable. Retry in {retry_after:.0f}s"
            logger.warning(f"🔴 {short_model}: {error_msg}")
            return False, {"error": error_msg, "circuit_open": True, "retry_after": retry_after}, 503
        
        logger.info(f"🤖 API call → {short_model} (max_tokens={max_tokens})")
        logger.debug(f"Request URL: {self.api_url}")
        logger.debug(f"Payload model field: {payload.get('model')}")

        last_error = None
        request_start = time.time()
        
        for attempt in range(max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.api_url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=300)
                    ) as response:
                        status_code = response.status
                        
                        # Check if response is JSON before parsing
                        content_type = response.headers.get('Content-Type', '')
                        if 'application/json' in content_type:
                            try:
                                response_data = await response.json()
                            except Exception as e:
                                logger.error(f"Failed to parse JSON response: {e}")
                                response_text = await response.text()
                                response_data = {"error": {"message": f"Invalid JSON: {response_text[:500]}"}}
                        else:
                            # Non-JSON response (HTML error page, etc.)
                            response_text = await response.text()
                            logger.warning(f"Non-JSON response (type: {content_type}): {response_text[:500]}")
                            response_data = {"error": {"message": f"Non-JSON response: {response_text[:200]}"}}
                        
                        if status_code == 200:
                            # Validate response has expected OpenAI schema structure
                            if not isinstance(response_data, dict) or 'choices' not in response_data:
                                error_msg = "API returned 200 but response missing 'choices' field"
                                if isinstance(response_data, dict) and 'error' in response_data:
                                    error_obj = response_data.get('error', {})
                                    if isinstance(error_obj, dict):
                                        error_msg = error_obj.get('message', error_msg)
                                    elif isinstance(error_obj, str):
                                        error_msg = error_obj
                                logger.error(f"{error_msg} (Model: {model})")
                                logger.error(f"Malformed 200 response: {response_data}")
                                circuit.record_failure(error_msg)
                                return False, {"error": {"message": error_msg}}, status_code
                            
                            # Calculate timing and extract usage info
                            elapsed = time.time() - request_start
                            usage = response_data.get('usage', {})
                            prompt_tokens = usage.get('prompt_tokens', 0)
                            completion_tokens = usage.get('completion_tokens', 0)
                            total_tokens = usage.get('total_tokens', prompt_tokens + completion_tokens)
                            
                            logger.info(
                                f"✅ {short_model} responded in {elapsed:.1f}s "
                                f"({prompt_tokens}→{completion_tokens} tokens, total={total_tokens})"
                            )
                            circuit.record_success()
                            return True, response_data, status_code
                        else:
                            # Handle error responses - extract message safely
                            if isinstance(response_data, dict):
                                error_obj = response_data.get("error", {})
                                if isinstance(error_obj, dict):
                                    error_message = error_obj.get("message", "Unknown API error")
                                elif isinstance(error_obj, str):
                                    error_message = error_obj
                                else:
                                    error_message = str(response_data)
                            elif isinstance(response_data, str):
                                error_message = response_data
                            else:
                                error_message = "Unknown error format"
                            
                            logger.error(f"OpenRouter API error (Status: {status_code}, Model: {model}): {error_message}")
                            
                            # For 5xx errors, allow retry with backoff
                            if status_code >= 500 and attempt < max_retries:
                                backoff = 2 ** attempt + (attempt * 2)  # Longer backoff for server errors
                                logger.warning(f"Server error {status_code}, backing off {backoff}s before retry...")
                                await asyncio.sleep(backoff)
                                continue
                            
                            # Record failure for non-retriable errors or final retry
                            if status_code >= 500:
                                circuit.record_failure(error_message)
                            
                            return False, response_data if isinstance(response_data, dict) else {"error": error_message}, status_code

            except aiohttp.ClientConnectorError as e:
                last_error = e
                logger.warning(f"Network error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    backoff = 2 ** attempt + 1  # Extra second for network issues
                    await asyncio.sleep(backoff)
                    continue
            except aiohttp.ServerTimeoutError as e:
                last_error = e
                logger.warning(f"Timeout (attempt {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except (aiohttp.ServerDisconnectedError, aiohttp.ClientPayloadError) as e:
                # These are the specific errors from the logs
                error_type = type(e).__name__
                last_error = e
                logger.error(f"Connection error (attempt {attempt + 1}/{max_retries + 1}): {error_type}: {e}")
                if attempt < max_retries:
                    # Longer backoff for connection drops - API may be overloaded
                    backoff = (2 ** attempt) * 3
                    logger.info(f"Connection dropped, backing off {backoff}s before retry...")
                    await asyncio.sleep(backoff)
                    continue
            except Exception as e:
                # Handle TransferEncodingError and other aiohttp errors
                error_type = type(e).__name__
                last_error = e
                logger.error(f"Unexpected error (attempt {attempt + 1}/{max_retries + 1}): {error_type}: {e}")
                if attempt < max_retries and ('Transfer' in error_type or 'Payload' in error_type):
                    await asyncio.sleep(2 ** attempt)
                    continue
                break
        
        # All retries exhausted
        error_msg = f"Failed after {max_retries + 1} attempts: {last_error}"
        logger.error(error_msg)
        circuit.record_failure(error_msg)
        return False, {"error": error_msg}, 503

# Singleton instance
_chat_service = None

def get_openrouter_chat_service() -> "OpenRouterChatService":
    """Returns a singleton instance of the OpenRouterChatService."""
    global _chat_service
    if _chat_service is None:
        _chat_service = OpenRouterChatService()
    return _chat_service
