import os
import hashlib
import httpx
import logging
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger("eduva.image_service")

class ImageGenerationService:
    def __init__(self):
        self.api_key = os.getenv("POLLINATIONS_API_KEY")
        self.base_url = "https://image.pollinations.ai/prompt"
        self.images_dir = Path("static/images")
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def _generate_cache_key(self, prompt: str) -> str:
        # Create a deterministic cache key based on the prompt
        return hashlib.md5(prompt.encode("utf-8")).hexdigest()

    async def generate_image(self, prompt: str) -> str | None:
        if not self.api_key:
            logger.info("[EDUVA][Visuals] No POLLINATIONS_API_KEY found. Skipping image generation.")
            return None

        # Educational grounding prefix
        safe_prompt = f"Educational illustration, documentary style, clear, clean background: {prompt}"
        cache_key = self._generate_cache_key(safe_prompt)
        filename = f"{cache_key}.jpg"
        filepath = self.images_dir / filename
        file_url = f"/static/images/{filename}"

        if filepath.exists():
            logger.info(f"[EDUVA][Visuals] Returning cached image: {filename}")
            return file_url

        url = f"{self.base_url}/{quote(safe_prompt)}"
        
        # Optional: Add authentication parameters as required by Pollinations if needed.
        # Currently their authenticated API might require headers or query params depending on their contract.
        
        try:
            logger.info(f"[EDUVA][Visuals] Generating image for prompt: {safe_prompt}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(response.content)
                    return file_url
                else:
                    logger.error(f"[EDUVA][Visuals] Pollinations API returned {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"[EDUVA][Visuals] Failed to generate image: {e}")
            return None
