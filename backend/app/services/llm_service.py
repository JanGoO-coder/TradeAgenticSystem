"""
Multi-LLM Service with Rate Limiting.

Supports Groq, DeepSeek, and Gemini backends with automatic fallback.
Provides async generation and embedding capabilities with token bucket
rate limiting to prevent 429 errors during batch backtesting.
"""
import asyncio
import json
import hashlib
from typing import Optional, Literal, AsyncGenerator
from datetime import datetime
from aiolimiter import AsyncLimiter

from app.core.config import get_settings


class GeminiResponseWrapper:
    """Wrapper to make Gemini responses compatible with OpenAI response format."""
    
    def __init__(self, gemini_response):
        self._response = gemini_response
        self.choices = [self._Choice(gemini_response)]
        self.usage = self._Usage(gemini_response)
    
    class _Choice:
        def __init__(self, response):
            self.message = self._Message(response)
        
        class _Message:
            def __init__(self, response):
                try:
                    self.content = response.text if hasattr(response, 'text') else ""
                except Exception:
                    self.content = ""
    
    class _Usage:
        def __init__(self, response):
            try:
                usage = getattr(response, 'usage_metadata', None)
                self.prompt_tokens = getattr(usage, 'prompt_token_count', 0) if usage else 0
                self.completion_tokens = getattr(usage, 'candidates_token_count', 0) if usage else 0
            except Exception:
                self.prompt_tokens = 0
                self.completion_tokens = 0


class LLMService:
    """
    Multi-LLM service with rate limiting and retry logic.

    Supports (in priority order):
    1. Groq - Fast inference with Llama models
    2. DeepSeek - OpenAI-compatible API with DeepSeek models
    3. Gemini - Google's Gemini models (also used for embeddings)

    Features:
    - Token bucket rate limiting (configurable RPM)
    - Automatic retry with exponential backoff on 429
    - Streaming support for verbose reasoning
    - Embedding generation for RAG (via Gemini)
    """

    def __init__(self):
        settings = get_settings()
        
        # Track which backend we're using
        self._backend = None  # "groq", "deepseek", or "gemini"
        self._backend_model = None
        self._backend_api_key = None
        
        # Initialize clients
        self._groq_client = None
        self._deepseek_client = None
        self._gemini_model = None
        self._genai = None
        self._gemini_configured = False
        
        # Try Groq first
        if settings.groq_api_key:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=settings.groq_api_key)
                self._backend = "groq"
                self._backend_model = settings.groq_model
                self._backend_api_key = settings.groq_api_key
            except Exception as e:
                print(f"⚠️  Failed to initialize Groq: {e}")
        
        # Try DeepSeek second
        if not self._backend and settings.deepseek_api_key:
            try:
                from openai import OpenAI
                self._deepseek_client = OpenAI(
                    api_key=settings.deepseek_api_key,
                    base_url=settings.deepseek_base_url
                )
                self._backend = "deepseek"
                self._backend_model = settings.deepseek_model
                self._backend_api_key = settings.deepseek_api_key
            except Exception as e:
                print(f"⚠️  Failed to initialize DeepSeek: {e}")
        
        # Try Gemini third (always configure for embeddings too)
        api_key = settings.gemini_api_key or settings.google_api_key
        print(f"🔍 Checking Gemini: gemini_api_key={'set' if settings.gemini_api_key else 'not set'}, google_api_key={'set' if settings.google_api_key else 'not set'}")
        if api_key:
            try:
                import google.generativeai as genai
                print(f"🔍 Configuring Gemini with model: {settings.gemini_model}")
                genai.configure(api_key=api_key)
                self._gemini_configured = True
                self._genai = genai
                self._gemini_model = genai.GenerativeModel(settings.gemini_model)
                
                if not self._backend:
                    self._backend = "gemini"
                    self._backend_model = settings.gemini_model
                    self._backend_api_key = api_key
                    print(f"✅ Gemini configured as primary backend")
            except ImportError:
                print("⚠️  google-generativeai package not installed")
            except Exception as e:
                print(f"⚠️  Failed to initialize Gemini: {e}")
        else:
            print("⚠️  No Gemini API key found in settings")
        
        # Ensure at least one LLM is configured
        if not self._backend:
            print(f"❌ No backend configured. Groq: {settings.groq_api_key is not None}, DeepSeek: {settings.deepseek_api_key is not None}, Gemini: {api_key is not None}")
            raise ValueError(
                "No LLM configured. Please set one of: GROQ_API_KEY, DEEPSEEK_API_KEY, or GOOGLE_API_KEY"
            )
        
        # Log which LLM backend is active
        masked_key = self._mask_key(self._backend_api_key)
        print(f"🤖 LLM Service initialized: Using {self._backend.upper()} ({self._backend_model})")
        print(f"   API Key: {masked_key}")
        
        # Embedding model (Gemini only)
        self.embedding_model = settings.gemini_embedding_model
        
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
    
    def _mask_key(self, key: str | None) -> str:
        """Mask API key for logging."""
        if not key or len(key) <= 12:
            return "***"
        return f"{key[:8]}...{key[-4:]}"



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
                if self._backend == "groq" and self._groq_client:
                    # Use Groq
                    response = await asyncio.to_thread(
                        self._groq_client.chat.completions.create,
                        model=self._backend_model,
                        messages=messages,
                        temperature=temperature,
                        max_completion_tokens=max_tokens,
                        top_p=1,
                        stream=False,
                        stop=None
                    )
                    return response
                elif self._backend == "deepseek" and self._deepseek_client:
                    # Use DeepSeek (OpenAI-compatible)
                    response = await self._generate_with_deepseek(messages, temperature, max_tokens)
                    return response
                elif self._backend == "gemini" and self._gemini_model:
                    # Use Gemini
                    response = await self._generate_with_gemini(messages, temperature, max_tokens)
                    return response
                else:
                    raise ValueError(f"No LLM backend available (backend={self._backend})")

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if rate limited (429)
                if "429" in error_str or "rate" in error_str or "quota" in error_str:
                    delay = self.retry_base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue

                # For other errors, raise immediately
                raise

        # All retries exhausted
        raise last_error

    async def _generate_with_deepseek(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int
    ):
        """Generate using DeepSeek API (OpenAI-compatible)."""
        response = await asyncio.to_thread(
            self._deepseek_client.chat.completions.create,
            model=self._backend_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1,
            stream=False
        )
        return response

    async def _generate_with_gemini(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int
    ):
        """Generate using Gemini API with response wrapper for compatibility."""
        # Convert messages to Gemini format
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System Instructions:\n{content}")
            else:
                prompt_parts.append(content)
        
        full_prompt = "\n\n".join(prompt_parts)
        
        # Generate with Gemini
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "top_p": 1,
        }
        
        response = await asyncio.to_thread(
            self._gemini_model.generate_content,
            full_prompt,
            generation_config=generation_config
        )
        
        # Wrap response in compatible format
        return GeminiResponseWrapper(response)

    def _build_concise_prompt(self, prompt: str, system_instruction: Optional[str]) -> str:
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

1. **5-Minute Candle Analysis**: Check the current and previous 5-minute candle
2. **Breakout Check**: Did the current candle break the previous candle's high or low?
3. **Session Context**: Is this a valid trading session (London/New York)? Asian session is invalid.
4. **Entry Direction**: Break of high = SHORT, Break of low = LONG
5. **Decision**: Based on the above, what is the trading decision?

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

Important: rule_citations should be rule numbers from the strategy (e.g., "1.1", "1.2", "1.3"), NOT price levels.
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
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


# Aliases for backward compatibility
GroqService = LLMService
GeminiService = LLMService
get_groq_service = get_llm_service
get_gemini_service = get_llm_service

