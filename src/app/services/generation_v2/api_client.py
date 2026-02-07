"""API Client for OpenRouter
============================

Clean, minimal API client for OpenRouter chat completions.
Uses single circuit breaker from app.utils.circuit_breaker.

Features:
- Simple async HTTP calls with aiohttp
- Single retry with exponential backoff
- Circuit breaker integration (uses shared instance)
- Clean error handling
"""

import aiohttp
import asyncio
import logging
import os
import time
import uuid
from typing import Dict, Any, Tuple, Optional

from app.utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.services.rate_limiter import get_openrouter_rate_limiter

logger = logging.getLogger(__name__)

# Shared circuit breaker for OpenRouter API
_openrouter_breaker: Optional[CircuitBreaker] = None


def get_openrouter_breaker() -> CircuitBreaker:
    """Get the shared OpenRouter circuit breaker."""
    global _openrouter_breaker
    if _openrouter_breaker is None:
        _openrouter_breaker = CircuitBreaker(
            name="openrouter-v2",
            config=CircuitBreakerConfig(
                failure_threshold=3,  # Open after 3 failures
                recovery_timeout=60.0,  # Wait 60s before retry
                success_threshold=2,  # Need 2 successes to close
            )
        )
    return _openrouter_breaker


class OpenRouterClient:
    """Minimal client for OpenRouter chat completions.
    
    Usage:
        client = OpenRouterClient()
        success, response, status = await client.chat_completion(
            model="anthropic/claude-3-haiku",
            messages=[{"role": "user", "content": "Hello"}],
        )
    """
    
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY', '')
        self.site_url = os.getenv("OPENROUTER_SITE_URL", "https://thesis-app.local")
        self.site_name = os.getenv("OPENROUTER_SITE_NAME", "Thesis App")
        self.allow_fallbacks = os.getenv("OPENROUTER_ALLOW_FALLBACKS", "true").lower() == "true"
        
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set")
    
    def _headers(self) -> Dict[str, str]:
        """Build request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
            "Content-Type": "application/json",
            "X-Request-ID": str(uuid.uuid4()),
        }
    
    def _payload(self, model: str, messages: list, temperature: float, max_tokens: int) -> Dict[str, Any]:
        """Build request payload."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": min(max_tokens, 32000),
        }
        if self.allow_fallbacks:
            payload["provider"] = {
                "allow_fallbacks": True,
                "data_collection": "allow",
            }
        return payload
    
    async def chat_completion(
        self,
        model: str,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 32000,
        timeout: int = 300,
        max_retries: int = 2,
    ) -> Tuple[bool, Dict[str, Any], int]:
        """Make a chat completion request.
        
        Args:
            model: OpenRouter model ID (e.g., 'anthropic/claude-3-haiku')
            messages: Chat messages
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum output tokens
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts (default 1)
        
        Returns:
            Tuple of (success, response_data, status_code)
        """
        if not self.api_key:
            return False, {"error": "API key not configured"}, 401
        
        # Check circuit breaker
        breaker = get_openrouter_breaker()
        if not breaker.allow_request():
            status = breaker.get_status()
            return False, {
                "error": f"Circuit breaker open, retry after {status.get('last_failure', 'unknown')}",
                "circuit_open": True,
            }, 503

        limiter = get_openrouter_rate_limiter()
        if not await limiter.acquire(timeout=timeout):
            return False, {"error": "Rate limiter blocked request"}, 429
        
        headers = self._headers()
        payload = self._payload(model, messages, temperature, max_tokens)
        short_model = model.split('/')[-1] if '/' in model else model
        
        last_error = None
        start_time = time.time()
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"🤖 API call → {short_model} (attempt {attempt + 1}/{max_retries + 1})")
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.API_URL,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                    ) as response:
                        status_code = response.status
                        
                        # Parse response
                        content_type = response.headers.get('Content-Type', '')
                        if 'application/json' in content_type:
                            try:
                                data = await response.json()
                            except Exception:
                                text = await response.text()
                                data = {"error": f"Invalid JSON: {text[:200]}"}
                        else:
                            text = await response.text()
                            data = {"error": f"Non-JSON response: {text[:200]}"}
                        
                        if status_code == 200:
                            # Validate response structure
                            if 'choices' not in data:
                                error_msg = data.get('error', {})
                                if isinstance(error_msg, dict):
                                    error_msg = error_msg.get('message', 'Missing choices')
                                logger.error(f"Malformed 200 response: {error_msg}")
                                breaker.record_failure()
                                limiter.release(success=False, error=error_msg, duration=time.time() - start_time)
                                return False, {"error": error_msg}, status_code
                            
                            # Success!
                            elapsed = time.time() - start_time
                            usage = data.get('usage', {})
                            logger.info(
                                f"✅ {short_model} in {elapsed:.1f}s "
                                f"({usage.get('prompt_tokens', 0)}→{usage.get('completion_tokens', 0)} tokens)"
                            )
                            breaker.record_success()
                            limiter.release(success=True, duration=elapsed)
                            return True, data, status_code
                        
                        # Error response
                        error_obj = data.get('error', {})
                        if isinstance(error_obj, dict):
                            error_msg = error_obj.get('message', str(data))
                        else:
                            error_msg = str(error_obj)

                        try:
                            logger.warning(
                                "API error %s (%s): %s",
                                status_code,
                                short_model,
                                error_msg,
                            )
                            logger.error(
                                "API error payload (%s): %s",
                                status_code,
                                json.dumps(data, ensure_ascii=False)[:4000],
                            )
                        except Exception:
                            logger.warning(f"API error {status_code}: {error_msg}")
                        
                        # Retry on 5xx errors
                        if status_code in (408, 409, 429, 500, 502, 503, 504) and attempt < max_retries:
                            backoff = 2 ** attempt * 2
                            logger.info(f"Retrying in {backoff}s...")
                            await asyncio.sleep(backoff)
                            continue
                        
                        if status_code >= 500:
                            breaker.record_failure()
                        limiter.release(success=False, error=error_msg, duration=time.time() - start_time)
                        return False, data, status_code
                        
            except aiohttp.ClientError as e:
                last_error = str(e)
                logger.warning(f"Network error: {e}")
                if attempt < max_retries:
                    backoff = 2 ** attempt * 2
                    await asyncio.sleep(backoff)
                    continue
            except asyncio.TimeoutError:
                last_error = "Request timeout"
                logger.warning(f"Timeout after {timeout}s")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error: {e}")
                break
        
        # All retries failed
        breaker.record_failure()
        limiter.release(success=False, error=last_error or "Unknown error", duration=time.time() - start_time)
        return False, {"error": last_error or "Unknown error"}, 503


# Singleton instance
_client: Optional[OpenRouterClient] = None


def get_api_client() -> OpenRouterClient:
    """Get shared API client instance."""
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client
