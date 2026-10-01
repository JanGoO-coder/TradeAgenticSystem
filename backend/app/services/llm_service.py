"""
LM Studio native REST LLM Service with rate limiting.

Uses LM Studio's local `/api/v1/*` endpoints for chat generation.
Embeddings are not provided by this service and fall back to zero vectors.
"""
import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator, Literal, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from aiolimiter import AsyncLimiter

from app.core.config import get_settings


class LLMService:
    """LM Studio-backed LLM service with retry and rate limiting."""

    def __init__(self):
        settings = get_settings()

        self.base_url = settings.lmstudio_base_url.rstrip("/")
        self.api_token = settings.lmstudio_api_token
        self.model = settings.lmstudio_model
        self.context_length = settings.lmstudio_context_length
        self.reasoning = settings.lmstudio_reasoning
        self.auto_load_model = settings.lmstudio_auto_load_model

        # Rate limiting
        self.rpm_limit = settings.llm_rpm_limit
        self.limiter = AsyncLimiter(max_rate=settings.llm_burst_size, time_period=1.0)
        self.retry_attempts = settings.llm_retry_attempts
        self.retry_base_delay = 1.0

        # Monitoring
        self._request_count = 0
        self._last_reset = datetime.now()

        # Lazy model loading guard
        self._model_ready = False
        self._model_load_lock = asyncio.Lock()

    def _build_headers(self) -> dict[str, str]:
        """Build headers for LM Studio API requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def _build_url(self, path: str) -> str:
        """Build absolute request URL from endpoint path."""
        return f"{self.base_url}{path}"

    def _request_json(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        """Send a JSON request to LM Studio and return JSON response."""
        body = json.dumps(payload).encode("utf-8") if payload is not None else None

        req = urllib_request.Request(
            url=self._build_url(path),
            data=body,
            headers=self._build_headers(),
            method=method,
        )

        try:
            with urllib_request.urlopen(req, timeout=120) as response:
                raw = response.read()
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
        except urllib_error.HTTPError as exc:
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = str(exc)
            raise RuntimeError(
                f"LM Studio API {method} {path} failed ({exc.code}): {err_body}"
            ) from exc
        except urllib_error.URLError as exc:
            raise RuntimeError(
                f"Cannot reach LM Studio at {self.base_url}. Start the local server and verify the URL."
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError(f"LM Studio request timed out: {method} {path}") from exc
        except Exception as exc:
            raise RuntimeError(f"LM Studio API {method} {path} failed: {exc}") from exc

    async def _request_json_async(
        self, method: str, path: str, payload: Optional[dict] = None
    ) -> dict:
        """Async wrapper for synchronous HTTP request helper."""
        return await asyncio.to_thread(self._request_json, method, path, payload)

    async def _ensure_model_loaded(self):
        """Ensure the configured model is available and loaded in LM Studio."""
        if self._model_ready:
            return

        if not self.auto_load_model:
            self._model_ready = True
            return

        async with self._model_load_lock:
            if self._model_ready:
                return

            models_response = await self._request_json_async("GET", "/api/v1/models")
            models = models_response.get("models", [])

            model_info = next(
                (m for m in models if m.get("type") == "llm" and m.get("key") == self.model),
                None,
            )
            if model_info is None:
                available = [m.get("key") for m in models if m.get("type") == "llm" and m.get("key")]
                available_preview = ", ".join(available[:10]) if available else "none"
                raise RuntimeError(
                    f"LM Studio model '{self.model}' was not found. Available local LLMs: {available_preview}"
                )

            loaded_instances = model_info.get("loaded_instances", [])
            is_loaded = len(loaded_instances) > 0

            if not is_loaded:
                load_payload: dict[str, object] = {"model": self.model}
                if self.context_length:
                    load_payload["context_length"] = self.context_length
                await self._request_json_async("POST", "/api/v1/models/load", load_payload)

            self._model_ready = True

    def _build_chat_payload(
        self,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        max_tokens: int,
        stream: bool = False,
    ) -> dict:
        """Build payload for LM Studio `/api/v1/chat`."""
        payload: dict[str, object] = {
            "model": self.model,
            "input": prompt,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "top_p": 1,
            "stream": stream,
        }

        if system_instruction:
            payload["system_prompt"] = system_instruction
        if self.context_length:
            payload["context_length"] = self.context_length
        if self.reasoning:
            payload["reasoning"] = self.reasoning

        return payload

    def _is_retryable_error(self, error_text: str) -> bool:
        """Return True if the error should trigger a retry."""
        lowered = error_text.lower()
        retry_markers = [
            "429",
            "rate",
            "quota",
            "timeout",
            "temporarily",
            "connection reset",
            "connection aborted",
            "refused",
            "503",
        ]
        return any(marker in lowered for marker in retry_markers)

    def _extract_response_error(self, response: dict) -> Optional[str]:
        """Extract API error message from LM Studio response body."""
        if not isinstance(response, dict):
            return None

        err = response.get("error")
        if isinstance(err, dict):
            message = err.get("message")
            if message:
                return str(message)
        return None

    def _extract_output_text(self, response: dict) -> str:
        """Extract final assistant text from LM Studio chat output array."""
        output = response.get("output", [])
        if not isinstance(output, list):
            return ""

        chunks = [
            item.get("content", "")
            for item in output
            if isinstance(item, dict)
            and item.get("type") == "message"
            and isinstance(item.get("content"), str)
        ]
        return "\n".join(c.strip() for c in chunks if c.strip()).strip()

    def _extract_usage(self, response: dict) -> dict:
        """Extract token usage from LM Studio response stats."""
        stats = response.get("stats", {}) if isinstance(response, dict) else {}
        if not isinstance(stats, dict):
            stats = {}

        prompt_tokens = int(stats.get("input_tokens", 0) or 0)
        completion_tokens = int(stats.get("total_output_tokens", 0) or 0)
        reasoning_tokens = int(stats.get("reasoning_output_tokens", 0) or 0)

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "reasoning_tokens": reasoning_tokens,
        }

    async def generate(
        self,
        prompt: str,
        mode: Literal["concise", "verbose"] = "concise",
        system_instruction: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 8192,
    ) -> dict:
        """Generate a response with optional JSON parsing for concise mode."""
        if mode == "concise":
            full_prompt = self._build_concise_prompt(prompt)
        else:
            full_prompt = self._build_verbose_prompt(prompt)

        async with self.limiter:
            response = await self._generate_with_retry(
                prompt=full_prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        self._request_count += 1
        content = self._extract_output_text(response)

        parsed = None
        if mode == "concise":
            parsed = self._extract_json(content)

        return {
            "content": content,
            "parsed": parsed,
            "usage": self._extract_usage(response),
        }

    async def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 1.0,
    ) -> AsyncGenerator[str, None]:
        """Generate response chunks (single chunk fallback for LM Studio native API)."""
        async with self.limiter:
            response = await self._generate_with_retry(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=8192,
            )

        self._request_count += 1
        content = self._extract_output_text(response)
        if content:
            yield content

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return zero vectors because embeddings are not configured."""
        return [[0.0] * 3072 for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        """Return a zero vector because embeddings are not configured."""
        return [0.0] * 3072

    async def _generate_with_retry(
        self,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Generate with exponential backoff retry on transient failures."""
        last_error = None
        await self._ensure_model_loaded()

        payload = self._build_chat_payload(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        for attempt in range(self.retry_attempts):
            try:
                response = await self._request_json_async("POST", "/api/v1/chat", payload)
                response_error = self._extract_response_error(response)
                if response_error:
                    raise RuntimeError(f"LM Studio chat error: {response_error}")
                return response
            except Exception as exc:
                last_error = exc
                if self._is_retryable_error(str(exc)) and attempt < self.retry_attempts - 1:
                    delay = self.retry_base_delay * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("LM Studio generation failed without a captured error")

    def _build_concise_prompt(self, prompt: str) -> str:
        """Build prompt for concise JSON output."""
        json_instruction = """
You must respond ONLY with valid JSON. No markdown, no explanation, no code blocks.
Use this exact format:

{"decision": "WAIT", "confidence": 0.7, "rule_citations": ["1.1", "1.2"], "setup": null, "brief_reason": "Waiting for candle close to confirm break"}

Fields:
- decision: Must be exactly "TRADE", "WAIT", or "NO_TRADE"
- confidence: Number between 0.0 and 1.0
- rule_citations: Array of rule IDs like ["1.1", "1.2", "1.3"] - use numbers only, not prices
- setup: null OR {"direction": "LONG" or "SHORT", "entry": number, "stop_loss": number, "take_profit": number}
- brief_reason: Short explanation string

Important: rule_citations should be rule numbers from the strategy (e.g., "1.1", "1.2", "1.3"), NOT price levels.
"""
        parts = [json_instruction, prompt]
        return "\n\n".join(parts)

    def _build_verbose_prompt(self, prompt: str) -> str:
        """Build prompt for verbose output."""
        cot_instruction = """
Think through this step by step:

1. 5-Minute Candle Analysis: Check the current and previous 5-minute candle
2. Breakout Check: Did the current candle break the previous candle's high or low?
3. Session Context: Is this a valid trading session (London/New York)? Asian session is invalid.
4. Entry Direction: Break of high = SHORT, Break of low = LONG
5. Decision: Based on the above, what is the trading decision?

After your reasoning, provide a summary in this JSON format:
{
    "decision": "TRADE" | "WAIT" | "NO_TRADE",
    "confidence": 0.0 to 1.0,
    "rule_citations": ["rule_id", ...],
    "setup": {...} | null,
    "brief_reason": "One sentence summary of why this decision was made"
}

Important: rule_citations should be rule numbers from the strategy (e.g., "1.1", "1.2", "1.3"), NOT price levels.
"""
        parts = [cot_instruction, prompt]
        return "\n\n".join(parts)

    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON from response text."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        import re

        json_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        matches = re.finditer(json_pattern, text)

        for match in matches:
            content = match.group(1).strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                continue

        first_brace = text.find("{")
        last_brace = text.rfind("}")

        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_str = text[first_brace : last_brace + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        return None

    def get_rate_limit_status(self) -> dict:
        """Get current rate limiting status for monitoring."""
        burst_size = int(self.limiter.max_rate)
        return {
            "requests_made": self._request_count,
            "calls_last_minute": self._request_count,
            "last_reset": self._last_reset.isoformat(),
            "rpm_limit": self.rpm_limit,
            "burst_size": burst_size,
            "available_tokens": burst_size,
            "limiter_max_rate": self.limiter.max_rate,
            "limiter_time_period": self.limiter.time_period,
            "provider": "lm_studio",
            "model": self.model,
            "base_url": self.base_url,
        }

    def reset_counters(self):
        """Reset request counters."""
        self._request_count = 0
        self._last_reset = datetime.now()


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


# Provider aliases
LMStudioService = LLMService
get_lmstudio_service = get_llm_service
