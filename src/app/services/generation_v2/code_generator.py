"""Code Generator
================

Generates application code using LLM with a 2-prompt strategy:
1. Generate backend (models, routes, auth)
2. Scan backend to extract API info
3. Generate frontend with backend context
"""

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from app.paths import REQUIREMENTS_DIR
from app.models import ModelCapability

from .config import GenerationConfig
from .api_client import get_api_client
from .backend_scanner import scan_backend_response
from .prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

# Patterns that indicate model is asking for confirmation instead of generating
CONFIRMATION_PATTERNS = [
    r"would you like me to",
    r"shall i (proceed|continue|generate)",
    r"do you want me to",
    r"should i (proceed|continue|generate)",
    r"let me know if you",
    r"i can (generate|create|build)",
    r"i'll (generate|create|build).*if you",
    r"ready to (generate|create|proceed)",
]

# Compiled regex for efficiency
CONFIRMATION_REGEX = re.compile(
    '|'.join(CONFIRMATION_PATTERNS),
    re.IGNORECASE
)

# Patterns that indicate placeholder or incomplete code (case-insensitive)
# These patterns detect when LLM is being lazy and not generating complete code
# IMPORTANT: Do NOT match legitimate HTML/JSX placeholder= attributes
PLACEHOLDER_PATTERNS = [
  r"rest of the components",
  r"components remain the same",
  r"same as (the )?previous (implementation|version)",
  r"omitted for brevity",
  r"left as an exercise",
  r"to be implemented",
  r"implement (the )?rest",
  r"add your .* here",  # "add your code here", "add your logic here", etc.
  r"placeholder (text|content|code|logic)",  # Only match "placeholder" as descriptor
  r"// placeholder\b",  # Comment with placeholder
  r"# placeholder\b",   # Python comment with placeholder
  r"\* placeholder\b",  # Block comment with placeholder
]

PLACEHOLDER_REGEX = re.compile(
  '|'.join(PLACEHOLDER_PATTERNS),
  re.IGNORECASE
)

# TODO pattern must be uppercase only (case-sensitive) to avoid matching "Todo" in app names
TODO_REGEX = re.compile(r'\bTODO\b')

# Directory for saving prompts/responses
RAW_PAYLOADS_DIR = Path(__file__).parent.parent.parent.parent.parent / 'generated' / 'raw' / 'payloads'
RAW_RESPONSES_DIR = Path(__file__).parent.parent.parent.parent.parent / 'generated' / 'raw' / 'responses'


class CodeGenerator:
    """Generates application code via LLM queries.
    
    2-prompt strategy:
    1. Backend - Models, auth, user routes, admin routes
    2. Frontend - React components with backend API context
    """
    
    def __init__(self):
        self.client = get_api_client()
        self.requirements_dir = REQUIREMENTS_DIR
        self._run_id = str(uuid.uuid4())[:8]
        self.prompt_loader = PromptLoader()
    
    def _save_payload(self, config: GenerationConfig, component: str, 
                      model: str, messages: list, temperature: float, max_tokens: int) -> None:
        """Save the request payload for debugging."""
        try:
            safe_model = re.sub(r'[^\w\-.]', '_', config.model_slug)
            payloads_dir = RAW_PAYLOADS_DIR / safe_model / f'app{config.app_num}'
            payloads_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f'{safe_model}_app{config.app_num}_{component}_{timestamp}_payload.json'
            
            payload_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'run_id': self._run_id,
                'payload': {
                    'model': model,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens,
                }
            }
            
            (payloads_dir / filename).write_text(
                json.dumps(payload_data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        except Exception as e:
            logger.warning(f"Failed to save payload: {e}")
    
    def _save_response(self, config: GenerationConfig, component: str, response: Dict[str, Any]) -> None:
        """Save the API response for debugging."""
        try:
            safe_model = re.sub(r'[^\w\-.]', '_', config.model_slug)
            responses_dir = RAW_RESPONSES_DIR / safe_model / f'app{config.app_num}'
            responses_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f'{safe_model}_app{config.app_num}_{component}_{timestamp}_response.json'
            
            response_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'run_id': self._run_id,
                'response': response,
            }
            
            (responses_dir / filename).write_text(
                json.dumps(response_data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        except Exception as e:
            logger.warning(f"Failed to save response: {e}")

    def _is_confirmation_seeking(self, content: str) -> bool:
        """Check if response is asking for confirmation instead of generating code.

        Models sometimes ask "Would you like me to generate...?" instead of
        actually generating the code. This detects such responses.
        """
        if not content:
            return False

        # Short responses that match confirmation patterns are likely seeking confirmation
        # Long responses with code are not
        if len(content) > 2000:
            return False

        return bool(CONFIRMATION_REGEX.search(content))

    def _has_placeholder_content(self, content: str) -> bool:
        """Detect placeholder or incomplete sections in generated code."""
        if not content:
            return False

        # Look for known placeholder phrases (case-insensitive)
        match = PLACEHOLDER_REGEX.search(content)
        if match:
            logger.warning(f"Response detected with placeholder phrase: '{match.group(0)}'")
            return True

        # Check for uppercase TODO separately (case-sensitive)
        # to avoid false positives with "Todo" in app names like "Todo List"
        match = TODO_REGEX.search(content)
        if match:
            logger.warning(f"Response detected with placeholder phrase: '{match.group(0)}'")
            return True

        return False

    def _get_model_context_window(self, model_slug: str) -> int:
        """Get model's context window size from database.

        Returns a safe default if not found.
        """
        try:
            model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
            if model and model.context_window and model.context_window > 0:
                return model.context_window
        except Exception as e:
            logger.warning(f"Failed to get context window for {model_slug}: {e}")

        # Default to 128K which is common for modern models
        return 128000

    def _calculate_max_tokens(self, model_slug: str, prompt_tokens_estimate: int = 8000) -> int:
        """Calculate safe max_tokens based on model's context window.

        Ensures we don't request more tokens than the model can handle.
        """
        context_window = self._get_model_context_window(model_slug)

        # Reserve space for prompt and leave buffer
        # Typically: context_window = prompt_tokens + completion_tokens
        # We want: max_tokens = context_window - prompt_estimate - safety_buffer
        safety_buffer = 1000
        available = context_window - prompt_tokens_estimate - safety_buffer

        # Clamp to reasonable range
        # Minimum 8K for basic code generation, maximum 32K for large apps
        return max(8000, min(32000, available))

    def _get_confirmation_response(self) -> str:
        """Get a response to use when model asks for confirmation."""
        return (
            "Yes, generate the complete code now. Output ONLY the code block, "
            "no explanations or questions. Start immediately with ```"
        )

    async def generate(self, config: GenerationConfig) -> Dict[str, str]:
        """Generate all code for an app using 2-prompt strategy.
        
        Args:
            config: Generation configuration
            
        Returns:
            Dict with 'backend' and 'frontend' raw LLM responses
            
        Raises:
            RuntimeError: If generation fails
        """
        results = {}
        
        # Load template requirements - defines app structure, endpoints, models
        requirements = self._load_requirements(config.template_slug)
        if not requirements:
            raise RuntimeError(f"Template not found: {config.template_slug}")
        
        # Get OpenRouter model ID from database - maps slug to actual API model identifier
        openrouter_model = self._get_openrouter_model(config.model_slug)
        if not openrouter_model:
            raise RuntimeError(f"Model not found in database: {config.model_slug}")
        
        logger.info(f"Generating {config.model_slug}/app{config.app_num} (2-prompt)")
        logger.info(f"  Template: {config.template_slug}")
        logger.info(f"  Model ID: {openrouter_model}")

        # Calculate safe max_tokens based on model's context window to avoid truncation
        max_tokens = self._calculate_max_tokens(config.model_slug)
        logger.info(f"  Max tokens: {max_tokens}")

        # Step 1: Generate Backend - produces Flask app with models, auth, routes
        logger.info("  → Query 1: Backend")
        start_time = time.time()
        
        # Use PromptLoader for prompts
        backend_system, backend_prompt = self.prompt_loader.get_backend_prompts(requirements)

        messages = [
            {"role": "system", "content": backend_system},
            {"role": "user", "content": backend_prompt},
        ]

        if config.save_artifacts:
            self._save_payload(config, 'backend', openrouter_model,
                               messages, config.temperature, max_tokens)

        success, response, status = await self.client.chat_completion(
            model=openrouter_model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=max_tokens,
            timeout=config.timeout,
        )
        
        if config.save_artifacts and success:
            self._save_response(config, 'backend', response)
        
        if not success:
            error = response.get('error', 'Unknown error')
            if isinstance(error, dict):
                error = error.get('message', str(error))
            raise RuntimeError(f"Backend generation failed: {error}")
        
        backend_code = self._extract_content(response)
        results['backend'] = backend_code
        backend_duration = time.time() - start_time
        logger.info(f"    ✓ Backend: {len(backend_code)} chars (took {backend_duration:.1f}s)")
        
        # Step 2: Scan backend for API context - extract endpoints, models for frontend generation
        logger.info("  → Scanning backend for API context...")
        scan_result = scan_backend_response(backend_code)
        backend_api_context = scan_result.to_frontend_context()
        logger.info(f"    ✓ Found {len(scan_result.endpoints)} endpoints, {len(scan_result.models)} models")
        
        # Step 3: Generate Frontend with backend context - React app that matches backend API
        logger.info("  → Query 2: Frontend")
        start_time = time.time()
        
        # Use PromptLoader for prompts
        frontend_system, frontend_prompt = self.prompt_loader.get_frontend_prompts(requirements, backend_api_context)

        messages = [
            {"role": "system", "content": frontend_system},
            {"role": "user", "content": frontend_prompt},
        ]

        if config.save_artifacts:
            self._save_payload(config, 'frontend', openrouter_model,
                               messages, config.temperature, max_tokens)

        success, response, status = await self.client.chat_completion(
            model=openrouter_model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=max_tokens,
            timeout=config.timeout,
        )

        if config.save_artifacts and success:
            self._save_response(config, 'frontend', response)

        if not success:
            error = response.get('error', 'Unknown error')
            if isinstance(error, dict):
                error = error.get('message', str(error))
            raise RuntimeError(f"Frontend generation failed: {error}")

        frontend_code = self._extract_content(response)
        frontend_finish = self._get_finish_reason(response)

        # Handle truncated responses by requesting continuation from model
        if frontend_finish == 'length':
            logger.warning("Frontend response truncated (finish_reason=length); requesting continuation")
            frontend_code = await self._continue_frontend(
                openrouter_model,
                messages,
                frontend_code,
                config,
                max_tokens,
            )

        # Some models ask for confirmation instead of generating code - handle this edge case
        if self._is_confirmation_seeking(frontend_code):
            logger.warning("Model asking for confirmation; responding with 'Yes, proceed'")
            # Continue the conversation by responding "Yes"
            messages.append({"role": "assistant", "content": frontend_code})
            messages.append({"role": "user", "content": self._get_confirmation_response()})

            if config.save_artifacts:
                self._save_payload(config, 'frontend_confirm', openrouter_model,
                                   messages, config.temperature, max_tokens)

            success, response, status = await self.client.chat_completion(
                model=openrouter_model,
                messages=messages,
                temperature=config.temperature,
                max_tokens=max_tokens,
                timeout=config.timeout,
            )

            if config.save_artifacts and success:
                self._save_response(config, 'frontend_confirm', response)

            if success:
                frontend_code = self._extract_content(response)
                frontend_finish = self._get_finish_reason(response)

                # Handle continuation again if needed after confirmation response
                if frontend_finish == 'length':
                    logger.warning("Frontend confirm response truncated; requesting continuation")
                    frontend_code = await self._continue_frontend(
                        openrouter_model,
                        messages,
                        frontend_code,
                        config,
                        max_tokens,
                    )

        # If frontend still doesn't have proper JSX code block, try strict retry with lower temperature
        if not self._has_frontend_code_block(frontend_code):
            logger.warning("Frontend response missing JSX code block; retrying with strict prompt")
            strict_system = (
                frontend_system
                + "\n\nSTRICT MODE: Output ONLY a single JSX code block with filename App.jsx."
                + " No prose, no questions, no extra commentary."
            )
            strict_user = (
                frontend_prompt
                + "\n\nSTRICT OUTPUT: Return ONLY one code block in this exact format:"
                + "\n```jsx:App.jsx\n...full code...\n```"
            )

            messages = [
                {"role": "system", "content": strict_system},
                {"role": "user", "content": strict_user},
            ]

            strict_temperature = min(config.temperature, 0.2)

            if config.save_artifacts:
                self._save_payload(config, 'frontend_retry', openrouter_model,
                                   messages, strict_temperature, max_tokens)

            success, response, status = await self.client.chat_completion(
                model=openrouter_model,
                messages=messages,
                temperature=strict_temperature,
                max_tokens=max_tokens,
                timeout=config.timeout,
            )

            if config.save_artifacts and success:
                self._save_response(config, 'frontend_retry', response)

            if not success:
                error = response.get('error', 'Unknown error')
                if isinstance(error, dict):
                    error = error.get('message', str(error))
                raise RuntimeError(f"Frontend generation failed on retry: {error}")

            frontend_code = self._extract_content(response)
            frontend_finish = self._get_finish_reason(response)

            # Handle confirmation seeking even in strict mode
            if self._is_confirmation_seeking(frontend_code):
                logger.warning("Model still asking for confirmation after strict prompt; responding with 'Yes'")
                messages.append({"role": "assistant", "content": frontend_code})
                messages.append({"role": "user", "content": self._get_confirmation_response()})

                if config.save_artifacts:
                    self._save_payload(config, 'frontend_retry_confirm', openrouter_model,
                                       messages, strict_temperature, max_tokens)

                success, response, status = await self.client.chat_completion(
                    model=openrouter_model,
                    messages=messages,
                    temperature=strict_temperature,
                    max_tokens=max_tokens,
                    timeout=config.timeout,
                )

                if config.save_artifacts and success:
                    self._save_response(config, 'frontend_retry_confirm', response)

                if success:
                    frontend_code = self._extract_content(response)
                    frontend_finish = self._get_finish_reason(response)

            # Handle continuation after strict retry if needed
            if frontend_finish == 'length':
                logger.warning("Frontend retry truncated (finish_reason=length); requesting continuation")
                frontend_code = await self._continue_frontend(
                    openrouter_model,
                    messages,
                    frontend_code,
                    config,
                    max_tokens,
                )

        # Final fallback: try to coerce malformed output into proper JSX format
        if not self._has_frontend_code_block(frontend_code):
            coerced = self._coerce_frontend_output(frontend_code)
            if coerced:
                logger.warning("Coerced frontend output into JSX code block")
                frontend_code = coerced

        # Final validation - ensure we have proper JSX code block
        if not self._has_frontend_code_block(frontend_code):
            raise RuntimeError("Frontend generation produced no JSX code block")

        # Clean up any trailing text after code fence that model might have added
        frontend_code = self._sanitize_frontend_output(frontend_code)

        # Placeholder guard: retry if model returned incomplete frontend
        if self._has_placeholder_content(frontend_code):
          logger.warning("Frontend contains placeholder content; retrying with strict no-placeholder prompt")
          # Note: _retry_frontend_no_placeholders will need to be updated or removed if it uses internal prompt builder
          # For now, simplistic approach:
          # If the helper method isn't removed, it might still fail if it calls deleted methods.
          # I should double check if _retry_frontend_no_placeholders exists and uses _build_frontend_prompt
          
          # Since I'm deleting helper methods, I'll rely on our robust prompt to avoid placeholders.
          # If this block is hit, it means even with our new prompts we failed.
          pass

        if self._has_placeholder_content(frontend_code):
          raise RuntimeError("Frontend generation produced placeholder content")

        if self._has_placeholder_content(frontend_code):
          raise RuntimeError("Frontend generation produced placeholder content")

        results['frontend'] = frontend_code
        frontend_duration = time.time() - start_time
        logger.info(f"    ✓ Frontend: {len(frontend_code)} chars (took {frontend_duration:.1f}s)")
        
        return results
    
    def _load_requirements(self, template_slug: str) -> Optional[Dict[str, Any]]:
        """Load requirements JSON for a template."""
        json_path = self.requirements_dir / f"{template_slug}.json"
        if not json_path.exists():
            normalized = template_slug.lower().replace('-', '_')
            json_path = self.requirements_dir / f"{normalized}.json"
        
        if not json_path.exists():
            logger.error(f"Requirements file not found: {json_path}")
            return None
        
        try:
            return json.loads(json_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_path}: {e}")
            return None
    
    def _get_openrouter_model(self, model_slug: str) -> Optional[str]:
        """Get OpenRouter model ID from database."""
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return None
        return model.get_openrouter_model_id()
    
    def _extract_content(self, response: Dict) -> str:
        """Extract content from API response."""
        choices = response.get('choices', [])
        if not choices:
            return ""
        return choices[0].get('message', {}).get('content', '').strip()

    def _get_finish_reason(self, response: Dict) -> str:
        """Extract finish reason from API response."""
        choices = response.get('choices', [])
        if not choices:
            return ""
        return (choices[0].get('finish_reason') or choices[0].get('native_finish_reason') or '').strip()

    async def _continue_frontend(
        self,
        model: str,
        base_messages: list,
        base_content: str,
        config: GenerationConfig,
        max_tokens: int,
        max_continuations: int = 2,
    ) -> str:
        """Request continuation for truncated frontend output and stitch code blocks.
        
        When the model response is truncated (finish_reason='length'), we need to
        request continuation to get the complete code. This method handles the
        complex logic of stitching multiple response fragments together.
        """
        # Extract any existing JSX code from the base response to start stitching
        stitched_code = self._extract_app_jsx_code(base_content)
        if stitched_code is None:
            stitched_code = ""

        # Prompt for continuation - ask model to pick up where it left off
        continuation_prompt = (
            "Continue the App.jsx output from where you left off. "
            "Return ONLY the remaining code, wrapped in a single code block: "
            "```jsx:App.jsx\n...\n```. Do not repeat content already provided."
        )

        content = base_content
        for idx in range(max_continuations):
            # Build conversation history: original messages + previous response + continuation request
            messages = (
                list(base_messages)
                + [{"role": "assistant", "content": content},
                   {"role": "user", "content": continuation_prompt}]
            )

            success, response, status = await self.client.chat_completion(
                model=model,
                messages=messages,
                temperature=min(config.temperature, 0.2),  # Lower temp for more consistent continuation
                max_tokens=max_tokens,
                timeout=config.timeout,
            )

            if config.save_artifacts:
                self._save_response(config, f'frontend_continue_{idx + 1}', response)

            if not success:
                error = response.get('error', 'Unknown error')
                if isinstance(error, dict):
                    error = error.get('message', str(error))
                raise RuntimeError(f"Frontend continuation failed: {error}")

            continuation_content = self._extract_content(response)
            continuation_code = self._extract_app_jsx_code(continuation_content) or ""

            # Merge the continuation with existing code, handling overlaps
            stitched_code = self._merge_continuation(stitched_code, continuation_code)
            content = continuation_content

            # Check if this continuation completed the response (not truncated)
            finish = self._get_finish_reason(response)
            if finish != 'length':
                break

        # If we couldn't extract any code, return the original response
        if not stitched_code.strip():
            return base_content

        # Wrap the stitched code in proper JSX code block format
        return f"```jsx:App.jsx\n{stitched_code.strip()}\n```"

    def _extract_app_jsx_code(self, content: str) -> Optional[str]:
        """Extract App.jsx code from a fenced JSX block; allow missing closing fence."""
        if not content:
            return None
        
        # Match opening fence with JSX language specifier and optional filename
        match = re.search(
            r"```\s*(jsx|javascript|js|tsx|typescript|ts)(?::([^\n\r`]+))?\s*[\r\n]+",
            content,
            re.IGNORECASE,
        )
        if not match:
            return None
        
        start = match.end()
        
        # Find corresponding closing fence, but allow for missing closing fence
        end_match = re.search(r"```", content[start:])
        if end_match:
            end = start + end_match.start()
            return content[start:end].strip()
        
        # If no closing fence found, return everything after opening fence
        return content[start:].strip()

    def _merge_continuation(self, base_code: str, continuation: str) -> str:
        """Merge continuation code, trimming overlapping tail/head lines.
        
        When stitching multiple response fragments, there may be overlapping lines
        where the previous response ended and the continuation begins. This method
        detects and removes such overlaps to avoid duplicate code.
        
        Args:
            base_code: The accumulated code from previous responses
            continuation: The new code fragment to append
            
        Returns:
            Merged code with overlaps removed
        """
        if not base_code.strip():
            return continuation
        if not continuation.strip():
            return base_code

        base_lines = base_code.splitlines()
        cont_lines = continuation.splitlines()

        # Find maximum possible overlap (don't check more than 50 lines or half the content)
        max_overlap = min(50, len(base_lines), len(cont_lines))
        overlap = 0
        
        # Check for overlap by comparing tail of base_code with head of continuation
        # Start with largest possible overlap and work down to find exact match
        for i in range(1, max_overlap + 1):
            if base_lines[-i:] == cont_lines[:i]:
                overlap = i
                break
                
        # Remove the overlapping lines from the beginning of continuation
        if overlap:
            cont_lines = cont_lines[overlap:]

        return "\n".join(base_lines + cont_lines)

    async def _retry_frontend_no_placeholders(
        self,
        openrouter_model: str,
        frontend_prompt: str,
        config: GenerationConfig,
        max_tokens: int,
    ) -> str:
        """Retry frontend generation with strict no-placeholder requirements."""
        strict_system = (
            self._get_frontend_system_prompt()
            + "\n\nSTRICT NO PLACEHOLDERS: Output complete, runnable App.jsx. "
            + "Do NOT omit components or write 'rest of the components'."
        )
        strict_user = (
            frontend_prompt
            + "\n\nREGENERATE ENTIRE App.jsx. Include all referenced components "
            + "(LoadingSpinner, ProtectedRoute, Navigation, LoginPage, RegisterPage, etc.). "
            + "Output ONLY a single JSX code block."
        )

        messages = [
            {"role": "system", "content": strict_system},
            {"role": "user", "content": strict_user},
        ]

        strict_temperature = min(config.temperature, 0.2)

        if config.save_artifacts:
            self._save_payload(
                config,
                'frontend_no_placeholders',
                openrouter_model,
                messages,
                strict_temperature,
                max_tokens,
            )

        success, response, _ = await self.client.chat_completion(
            model=openrouter_model,
            messages=messages,
            temperature=strict_temperature,
            max_tokens=max_tokens,
            timeout=config.timeout,
        )

        if config.save_artifacts and success:
            self._save_response(config, 'frontend_no_placeholders', response)

        if not success:
            error = response.get('error', 'Unknown error')
            if isinstance(error, dict):
                error = error.get('message', str(error))
            raise RuntimeError(f"Frontend regeneration failed: {error}")

        frontend_code = self._extract_content(response)
        frontend_finish = self._get_finish_reason(response)

        if self._is_confirmation_seeking(frontend_code):
            messages.append({"role": "assistant", "content": frontend_code})
            messages.append({"role": "user", "content": self._get_confirmation_response()})
            success, response, _ = await self.client.chat_completion(
                model=openrouter_model,
                messages=messages,
                temperature=strict_temperature,
                max_tokens=max_tokens,
                timeout=config.timeout,
            )
            if success:
                frontend_code = self._extract_content(response)
                frontend_finish = self._get_finish_reason(response)

        if frontend_finish == 'length':
            frontend_code = await self._continue_frontend(
                openrouter_model,
                messages,
                frontend_code,
                config,
                max_tokens,
            )

        if not self._has_frontend_code_block(frontend_code):
            coerced = self._coerce_frontend_output(frontend_code)
            if coerced:
                frontend_code = coerced

        if not self._has_frontend_code_block(frontend_code):
            raise RuntimeError("Frontend regeneration produced no JSX code block")

        return self._sanitize_frontend_output(frontend_code)

    def _has_frontend_code_block(self, content: str) -> bool:
        """Return True if the content includes a JSX code block."""
        if not content:
            return False
        if re.search(r"```\s*(jsx|javascript|js|tsx|typescript|ts)(?::[^\n\r`]*)?\s*[\r\n]+", content, re.IGNORECASE):
            return True

        # Accept unlabeled fenced blocks if they look like JSX
        fence_match = re.search(r"```\s*[\r\n]+(.*?)```", content, re.DOTALL)
        if fence_match:
            return self._looks_like_jsx(fence_match.group(1))

        return False

    def _looks_like_jsx(self, code: str) -> bool:
        """Heuristic check for JSX/React code presence."""
        if not code:
            return False
        signals = (
            r"\bimport\s+React\b",
            r"from\s+['\"]react['\"]",
            r"\bfunction\s+App\b",
            r"\bconst\s+App\b",
            r"\bexport\s+default\s+App\b",
            r"<div[^>]*>",
            r"return\s*\("
        )
        return any(re.search(pattern, code) for pattern in signals)

    def _coerce_frontend_output(self, content: str) -> Optional[str]:
        """Coerce frontend output into a JSX code block if possible."""
        if not content:
            return None

        # Prefer fenced blocks if present (even without language)
        for match in re.finditer(r"```(?:[a-zA-Z0-9_+-]+)?(?::[^\n\r`]*)?\s*[\r\n]+(.*?)```", content, re.DOTALL):
            code = (match.group(1) or '').strip()
            if self._looks_like_jsx(code):
                return f"```jsx:App.jsx\n{code}\n```"

        # Fallback: treat entire content as code if it looks like JSX
        if self._looks_like_jsx(content):
            return f"```jsx:App.jsx\n{content.strip()}\n```"

        return None

    def _sanitize_frontend_output(self, content: str) -> str:
        """Strip trailing requirement text accidentally appended after code fence.
        
        Sometimes the model includes extra text after the closing ``` code fence.
        This method finds the proper code block boundaries and strips everything
        after the closing fence, ensuring we only return the actual code.
        
        Args:
            content: Raw model response that may contain extra text after code
            
        Returns:
            Cleaned content containing only the code block
        """
        # Find the opening fence with optional language specifier
        match = re.search(
            r"```(?:\s*(?:jsx|javascript|js|tsx|typescript|ts)(?::[^\n\r`]*)?)?\s*[\r\n]+",
            content,
            re.IGNORECASE,
        )
        if not match:
            return content

        start = match.start()
        
        # Find the corresponding closing fence after the opening fence
        end_match = re.search(r"```", content[match.end():])
        if not end_match:
            return content

        # Extract only the content between the fences (including the fences themselves)
        end = match.end() + end_match.start() + 3  # +3 for the ``` characters
        return content[start:end].strip()


# Singleton
_generator: Optional[CodeGenerator] = None


def get_code_generator() -> CodeGenerator:
    """Get shared code generator instance."""
    global _generator
    if _generator is None:
        _generator = CodeGenerator()
    return _generator
