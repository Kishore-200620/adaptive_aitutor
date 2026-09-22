import os
import hashlib
import httpx
import logging
import asyncio
from pathlib import Path
from urllib.parse import quote
from PIL import Image, UnidentifiedImageError
from app.core.config import settings

logger = logging.getLogger("eduva.image_service")

class ImageGenerationService:
    def __init__(self):
        self.api_key = settings.pollinations_api_key or os.getenv("POLLINATIONS_API_KEY")
        self.model = settings.pollinations_image_model
        self.base_url = "https://image.pollinations.ai/prompt"
        self.images_dir = Path("static/images")
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def _generate_cache_key(self, prompt: str, model: str) -> str:
        # Create a deterministic cache key based on the prompt AND the explicit model
        cache_data = f"{model}:{prompt}"
        return hashlib.md5(cache_data.encode("utf-8")).hexdigest()

    def _validate_image(self, filepath: Path) -> bool:
        try:
            with Image.open(filepath) as img:
                img.verify()
            return True
        except (UnidentifiedImageError, IOError, SyntaxError) as e:
            logger.error(f"[EDUVA][Visuals] Image validation failed for {filepath}: {e}")
            return False
        except Exception as e:
            logger.error(f"[EDUVA][Visuals] Unexpected error validating image {filepath}: {e}")
            return False

    async def generate_image(self, prompt: str) -> str | None:
        if not self.api_key:
            logger.info("[EDUVA][Visuals] No POLLINATIONS_API_KEY found. Skipping image generation.")
            return None

        # The prompt is now fully formed by the orchestrator.
        cache_key = self._generate_cache_key(prompt, self.model)
        filename = f"{cache_key}.jpg"
        filepath = self.images_dir / filename
        file_url = f"/static/images/{filename}"

        if filepath.exists():
            if self._validate_image(filepath):
                logger.info(f"[EDUVA][Visuals] Returning cached image: {filename}")
                return file_url
            else:
                logger.warning(f"[EDUVA][Visuals] Cached image {filename} is invalid, deleting and regenerating.")
                filepath.unlink(missing_ok=True)

        url = f"{self.base_url}/{quote(prompt)}?model={self.model}&nologo=true"
        logger.info(f"[EDUVA][Visuals] Pollinations URL length: {len(url)}")
        
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"[EDUVA][Visuals] Pollinations attempt {attempt}/{max_attempts}")
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        with open(filepath, "wb") as f:
                            f.write(response.content)
                        
                        if self._validate_image(filepath):
                            logger.info("[EDUVA][Visuals] Provider: Pollinations")
                            logger.info(f"[EDUVA][Visuals] Requested model: {self.model}")
                            logger.info("[EDUVA][Visuals] HTTP status: 200")
                            logger.info("[EDUVA][Visuals] Generated image validation: PASS")
                            return file_url
                        else:
                            logger.error(f"[EDUVA][Visuals] Generated image {filename} failed validation.")
                            filepath.unlink(missing_ok=True)
                            return None
                    elif response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 2))
                        # Cap retry_after so provider cannot stall lesson indefinitely
                        delay = min(retry_after, 3)
                        logger.warning(f"[EDUVA][Visuals] Pollinations attempt {attempt} failed: 429. Retrying in {delay}s...")
                        if attempt < max_attempts:
                            await asyncio.sleep(delay)
                    else:
                        logger.error(f"[EDUVA][Visuals] Pollinations attempt {attempt} failed: {response.status_code}")
                        if attempt < max_attempts:
                            await asyncio.sleep(1.5)
            except Exception as e:
                logger.error(f"[EDUVA][Visuals] Pollinations attempt {attempt} failed with exception: {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(1.5)

        logger.error("[EDUVA][Visuals] Pollinations failed")
        return None

