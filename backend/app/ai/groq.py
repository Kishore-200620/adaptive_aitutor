from groq import Groq, AsyncGroq
import groq
import httpx
import asyncio
import time
import logging
import random
import json

from app.core.config import settings

logger = logging.getLogger("eduva.stream")

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0  # seconds
MAX_RETRY_DELAY = 10.0  # seconds

class LLMReliabilityError(Exception):
    """Raised when an LLM operation fails permanently or exhausts retries."""
    pass

class GroqService:
    DEFAULT_MODEL = "openai/gpt-oss-120b"
    FALLBACK_MODEL = "openai/gpt-oss-20b"

    def __init__(self):
        # Configure strict timeouts to prevent hanging
        timeout_config = httpx.Timeout(
            15.0, connect=5.0, read=15.0, write=5.0
        )
        self.client = Groq(
            api_key=settings.groq_api_key,
            timeout=timeout_config,
            max_retries=0, # We handle retries manually for fine-grained control
        )
        self.async_client = AsyncGroq(
            api_key=settings.groq_api_key,
            timeout=timeout_config,
            max_retries=0,
        )

    def _classify_error(self, e: Exception) -> bool:
        """Return True if retryable, False otherwise."""
        if isinstance(e, groq.RateLimitError):
            return True
        if isinstance(e, groq.InternalServerError):
            return True
        if isinstance(e, groq.APIConnectionError):
            return True
        if isinstance(e, groq.APITimeoutError):
            return True
        if isinstance(e, groq.APIStatusError):
            status = e.status_code
            if status in (429, 500, 502, 503, 504):
                return True
            return False # 400, 401, 403, 404 etc are not retryable
        
        # httpx network exceptions (if they leak)
        if isinstance(e, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.ReadError)):
            return True
            
        return False

    def _get_retry_delay(self, attempt: int, e: Exception) -> float:
        """Calculate bounded exponential backoff with jitter, respecting Retry-After."""
        if isinstance(e, groq.RateLimitError):
            # Check for Retry-After header
            retry_after = e.response.headers.get("retry-after")
            if retry_after:
                try:
                    delay = float(retry_after)
                    return min(delay, MAX_RETRY_DELAY)
                except ValueError:
                    pass

        # Exponential backoff: 1, 2, 4 seconds
        delay = RETRY_DELAY_BASE * (2 ** attempt)
        # Add jitter
        delay += random.uniform(0, 1.0)
        return min(delay, MAX_RETRY_DELAY)

    def _validate_structured_output(self, content: str, expected_format: str | None = None) -> bool:
        """Validate the response isn't empty or totally malformed."""
        if not content or not content.strip():
            return False
            
        if expected_format == "json":
            try:
                json.loads(content)
                return True
            except json.JSONDecodeError:
                return False
                
        if expected_format == "evaluator":
            if "CORRECTNESS:" not in content or "SCORE:" not in content:
                return False
                
        return True

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
        expected_format: str | None = None,
    ) -> str:
        selected_model = model or self.DEFAULT_MODEL
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=selected_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                
                content = response.choices[0].message.content
                if self._validate_structured_output(content, expected_format):
                    if attempt > 0:
                        logger.info(f"[EDUVA][Groq] generate retry {attempt} succeeded.")
                    return content
                else:
                    raise LLMReliabilityError("Malformed structured output")
                    
            except Exception as e:
                last_error = e
                retryable = self._classify_error(e) or isinstance(e, LLMReliabilityError)
                
                if not retryable:
                    logger.error(f"[EDUVA][Groq] generate non-retryable error: {type(e).__name__} - {e}")
                    raise LLMReliabilityError(f"Non-retryable failure: {e}") from e
                    
                if attempt < MAX_RETRIES - 1:
                    delay = self._get_retry_delay(attempt, e)
                    logger.warning(f"[EDUVA][Groq] generate attempt {attempt + 1} failed ({type(e).__name__}). Retrying in {delay:.1f}s...")
                    time.sleep(delay)

        logger.error(f"[EDUVA][Groq] generate exhausted {MAX_RETRIES} attempts.")
        raise LLMReliabilityError("Max retries exhausted") from last_error

    async def async_generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
        expected_format: str | None = None,
    ) -> str:
        selected_model = model or self.DEFAULT_MODEL
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.async_client.chat.completions.create(
                    model=selected_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                
                content = response.choices[0].message.content
                if self._validate_structured_output(content, expected_format):
                    if attempt > 0:
                        logger.info(f"[EDUVA][Groq] async_generate retry {attempt} succeeded.")
                    return content
                else:
                    raise LLMReliabilityError("Malformed structured output")
                    
            except Exception as e:
                last_error = e
                retryable = self._classify_error(e) or isinstance(e, LLMReliabilityError)
                
                if not retryable:
                    logger.error(f"[EDUVA][Groq] async_generate non-retryable error: {type(e).__name__} - {e}")
                    raise LLMReliabilityError(f"Non-retryable failure: {e}") from e
                    
                if attempt < MAX_RETRIES - 1:
                    delay = self._get_retry_delay(attempt, e)
                    logger.warning(f"[EDUVA][Groq] async_generate attempt {attempt + 1} failed ({type(e).__name__}). Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)

        logger.error(f"[EDUVA][Groq] async_generate exhausted {MAX_RETRIES} attempts.")
        raise LLMReliabilityError("Max retries exhausted") from last_error

    async def generate_stream(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
    ):
        """Async streaming generator with bounded retry for pre-stream failures and safe termination for mid-stream interruptions."""
        selected_model = model or self.DEFAULT_MODEL

        for attempt in range(MAX_RETRIES):
            start_time = time.time()
            first_token = True
            collected = 0

            try:
                response = await self.async_client.chat.completions.create(
                    model=selected_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    stream=True,
                )

                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        token = chunk.choices[0].delta.content
                        if first_token:
                            elapsed = time.time() - start_time
                            logger.info(f"[EDUVA][Groq] First token latency: {elapsed:.2f}s (attempt {attempt + 1})")
                            first_token = False
                        
                        collected += 1
                        yield {"type": "token", "content": token}

                # Stream completed successfully
                return

            except Exception as e:
                if collected > 0:
                    # Stream was interrupted MID-WAY after delivering partial output to the student
                    # NEVER restart the stream, emit a semantic event and exit cleanly.
                    logger.warning(f"[EDUVA][Groq] Stream interrupted mid-way after {collected} tokens. Terminating stream safely. Error: {e}")
                    yield {"type": "interruption", "content": "teaching_stream_interrupted"}
                    return
                
                # Pre-stream failure (no chunks delivered yet)
                last_error = e
                retryable = self._classify_error(e)
                
                if not retryable:
                    logger.error(f"[EDUVA][Groq] Stream non-retryable error: {type(e).__name__} - {e}")
                    raise LLMReliabilityError(f"Non-retryable failure: {e}") from e
                    
                if attempt < MAX_RETRIES - 1:
                    delay = self._get_retry_delay(attempt, e)
                    logger.warning(f"[EDUVA][Groq] Stream attempt {attempt + 1} failed before first chunk ({type(e).__name__}). Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue

        logger.error(f"[EDUVA][Groq] Stream exhausted {MAX_RETRIES} attempts before delivering output.")
        raise LLMReliabilityError("Max retries exhausted") from last_error

groq_service = GroqService()