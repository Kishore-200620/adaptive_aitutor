from groq import Groq, AsyncGroq
import asyncio
import time
import logging

from app.core.config import settings

logger = logging.getLogger("eduva.stream")

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0  # seconds


class GroqService:
    DEFAULT_MODEL = "openai/gpt-oss-120b"
    FALLBACK_MODEL = "openai/gpt-oss-20b"

    def __init__(self):
        self.client = Groq(
            api_key=settings.groq_api_key
        )
        self.async_client = AsyncGroq(
            api_key=settings.groq_api_key
        )

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
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
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                logger.warning(f"[EDUVA][Groq] generate attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_BASE * (attempt + 1))

        logger.error(f"[EDUVA][Groq] generate failed after {MAX_RETRIES} attempts: {last_error}")
        raise last_error

    async def generate_stream(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
    ):
        """Async streaming generator with retry on network drop."""
        selected_model = model or self.DEFAULT_MODEL

        for attempt in range(MAX_RETRIES):
            start_time = time.time()
            first_token = True
            collected: list[str] = []

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
                        collected.append(token)
                        yield token

                # Stream completed successfully
                return

            except Exception as e:
                logger.warning(f"[EDUVA][Groq] Stream attempt {attempt + 1} failed after {len(collected)} tokens: {e}")
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY_BASE * (attempt + 1)
                    logger.info(f"[EDUVA][Groq] Retrying stream in {delay:.1f}s ...")
                    await asyncio.sleep(delay)
                    # If we already got some tokens, don't retry — yield what we have
                    if collected:
                        logger.warning("[EDUVA][Groq] Partial stream received; not retrying mid-stream")
                        return
                else:
                    logger.error(f"[EDUVA][Groq] Stream failed after {MAX_RETRIES} attempts: {e}")
                    raise


groq_service = GroqService()