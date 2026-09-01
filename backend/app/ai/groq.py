from groq import Groq

from app.core.config import settings


class GroqService:
    DEFAULT_MODEL = "openai/gpt-oss-120b"
    FALLBACK_MODEL = "openai/gpt-oss-20b"

    def __init__(self):
        self.client = Groq(
            api_key=settings.groq_api_key
        )

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
    ) -> str:

        selected_model = model or self.DEFAULT_MODEL

        response = self.client.chat.completions.create(
            model=selected_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=temperature,
        )

        return response.choices[0].message.content


groq_service = GroqService()