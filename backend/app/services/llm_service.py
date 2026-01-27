"""
Groq LLM Service with Rate Limiting.

Provides async generation and embedding capabilities with token bucket
rate limiting to prevent 429 errors during batch backtesting.
"""
import asyncio
import json
import hashlib
from typing import Optional, Literal, AsyncGenerator
from datetime import datetime
from groq import Groq
from aiolimiter import AsyncLimiter

from app.core.config import get_settings


class GroqService:
    """
    Groq LLM service with rate limiting and retry logic.

    Features:
    - Token bucket rate limiting (configurable RPM)
    - Automatic retry with exponential backoff on 429
    - Streaming support for verbose reasoning
    - Embedding generation for RAG (via Gemini fallback)
    """

    def __init__(self):
        settings = get_settings()

        # Configure Groq API
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        
        # Gemini for embeddings (optional)
        self.embedding_model = settings.gemini_embedding_model
        self._gemini_configured = False
        api_key = settings.gemini_api_key or settings.google_api_key
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self._gemini_configured = True
                self._genai = genai
            except ImportError:
                pass

        # Rate limiting
        self.limiter = AsyncLimiter(
            max_rate=settings.llm_burst_size,
            time_period=1.0
        )

        self.retry_attempts = settings.llm_retry_attempts
        self.retry_base_delay = 1.0  # seconds

        # Track usage for monitoring
        self._request_count = 0
        self._last_reset = datetime.now()

    async def generate(
        self,
        prompt: str,
        mode: Literal["concise", "verbose"] = "concise",
        system_instruction: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 8192
    ) -> dict:
        """
        Generate a response from Groq with rate limiting.

        Args:
            prompt: The user prompt
            mode: "concise" for structured JSON, "verbose" for chain-of-thought
            system_instruction: Optional system prompt
            temperature: Generation temperature (0.0-2.0)
            max_tokens: Maximum output tokens

        Returns:
            {
                "content": str,  # The generated text
                "parsed": dict | None,  # Parsed JSON if applicable
                "usage": {"prompt_tokens": int, "completion_tokens": int}
            }
        """
        # Build the full prompt based on mode
        if mode == "concise":
            full_prompt = self._build_concise_prompt(prompt, system_instruction)
        else:
            full_prompt = self._build_verbose_prompt(prompt, system_instruction)

        # Build messages
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": full_prompt})

        # Apply rate limiting
        async with self.limiter:
            response = await self._generate_with_retry(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

        self._request_count += 1

        # Parse response
        content = response.choices[0].message.content if response.choices else ""
        parsed = None

        if mode == "concise":
            # Try to extract JSON from response
            parsed = self._extract_json(content)

        return {
            "content": content,
            "parsed": parsed,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else 0
            }
        }

    async def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 1.0
    ) -> AsyncGenerator[str, None]:
        """
        Stream a response from Groq for real-time UI updates.

        Yields chunks of text as they arrive.
        """
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        async with self.limiter:
            # Run streaming in thread
            def stream_sync():
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_completion_tokens=8192,
                    top_p=1,
                    stream=True,
                    stop=None
                )
            
            completion = await asyncio.to_thread(stream_sync)
            
            for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        self._request_count += 1

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts using Gemini.

        Args:
            texts: List of strings to embed

        Returns:
            List of embedding vectors
        """
        if not self._gemini_configured:
            print("Warning: Gemini not configured for embeddings")
            return [[0.0] * 3072 for _ in texts]
            
        embeddings = []

        for text in texts:
            async with self.limiter:
                try:
                    result = await asyncio.to_thread(
                        self._genai.embed_content,
                        model=self.embedding_model,
                        content=text
                    )
                    embeddings.append(result['embedding'])
                except Exception as e:
                    print(f"Embedding error: {e}")
                    # Return zero vector as fallback
                    embeddings.append([0.0] * 3072)

        return embeddings

    async def embed_query(self, text: str) -> list[float]:
        """
        Generate embedding for a query text using Gemini.
        """
        if not self._gemini_configured:
            print("Warning: Gemini not configured for embeddings")
            return [0.0] * 3072
            
        async with self.limiter:
            try:
                result = await asyncio.to_thread(
                    self._genai.embed_content,
                    model=self.embedding_model,
                    content=text
                )
                return result['embedding']
            except Exception as e:
                print(f"Query embedding error: {e}")
                return [0.0] * 3072

    async def _generate_with_retry(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int
    ):
        """Generate with exponential backoff retry on rate limits."""
        last_error = None

        for attempt in range(self.retry_attempts):
            try:
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_completion_tokens=max_tokens,
                    top_p=1,
                    stream=False,
                    stop=None
                )
                return response

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if rate limited (429)
                if "429" in error_str or "rate" in error_str:
                    delay = self.retry_base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue

                # For other errors, raise immediately
                raise

        # All retries exhausted
        raise last_error

    def _build_concise_prompt(self, prompt: str, system_instruction: Optional[str]) -> str:
        """Build prompt for concise JSON output."""
        json_instruction = """
You must respond ONLY with valid JSON. No markdown, no explanation, no code blocks.
Use this exact format:

{"decision": "WAIT", "confidence": 0.7, "rule_citations": ["1.1", "6.5"], "setup": null, "brief_reason": "Waiting for liquidity sweep"}

Fields:
- decision: Must be exactly "TRADE", "WAIT", or "NO_TRADE"
- confidence: Number between 0.0 and 1.0
- rule_citations: Array of rule IDs like ["1.1", "6.5", "8.1"] - use numbers only, not prices
- setup: null OR {"direction": "LONG" or "SHORT", "entry": number, "stop_loss": number, "take_profit": number}
- brief_reason: Short explanation string

Important: rule_citations should be ICT rule numbers (e.g., "1.1", "6.5", "8.1"), NOT price levels.
"""
        parts = []
        if system_instruction:
            parts.append(system_instruction)
        parts.append(json_instruction)
        parts.append(prompt)

        return "\n\n".join(parts)

    def _build_verbose_prompt(self, prompt: str, system_instruction: Optional[str]) -> str:
        """Build prompt for verbose chain-of-thought output."""
        cot_instruction = """
Think through this step by step:

1. **Market Structure Analysis**: What is the current structure telling us?
2. **Liquidity Assessment**: Where has liquidity been taken or is resting?
3. **PD Array Alignment**: Are we in premium or discount for the bias?
4. **Session Context**: Is this a valid trading window?
5. **Strategy Match**: Which strategy rules apply here?
6. **Decision**: Based on the above, what is the trading decision?

After your reasoning, provide a summary in this JSON format:
```json
{
    "decision": "TRADE" | "WAIT" | "NO_TRADE",
    "confidence": 0.0 to 1.0,
    "rule_citations": ["rule_id", ...],
    "setup": {...} | null,
    "brief_reason": "One sentence summary of why this decision was made"
}
```

Important: rule_citations should be ICT rule numbers (e.g., "1.1", "6.5", "8.1"), NOT price levels.
"""
        parts = []
        if system_instruction:
            parts.append(system_instruction)
        parts.append(cot_instruction)
        parts.append(prompt)

        return "\n\n".join(parts)

    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract JSON from response text."""
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON block in markdown
        import re
        # More robust pattern to capture content between ```json and ```
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        matches = re.finditer(json_pattern, text) # Use finditer

        for match in matches:
            content = match.group(1).strip()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                continue

        # Try to find raw JSON object (fallback)
        # Find first { and last }
        first_brace = text.find('{')
        last_brace = text.rfind('}')

        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_str = text[first_brace:last_brace+1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        return None

        return None

    def get_rate_limit_status(self) -> dict:
        """Get current rate limiting status for monitoring."""
        return {
            "requests_made": self._request_count,
            "last_reset": self._last_reset.isoformat(),
            "limiter_max_rate": self.limiter.max_rate,
            "limiter_time_period": self.limiter.time_period
        }

    def reset_counters(self):
        """Reset request counters."""
        self._request_count = 0
        self._last_reset = datetime.now()


# Singleton instance
_groq_service: Optional[GroqService] = None


def get_groq_service() -> GroqService:
    """Get or create the Groq service singleton."""
    global _groq_service
    if _groq_service is None:
        _groq_service = GroqService()
    return _groq_service


# Alias for backward compatibility
GeminiService = GroqService
get_gemini_service = get_groq_service
