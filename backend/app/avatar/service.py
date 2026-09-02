from app.avatar.simli import SimliAvatarService
from app.core.config import settings


class AvatarService:

    def __init__(self):
        provider = settings.avatar_provider.lower()

        if provider == "simli":

            self.provider = SimliAvatarService(
                api_key=settings.simli_api_key,
                face_id=settings.avatar_model_id,
                output_dir=settings.avatar_output_dir,
            )

        else:
            raise ValueError(
                f"Unsupported avatar provider: {provider}"
            )

    @property
    def configured(self) -> bool:
        return self.provider.configured

    async def generate_video(
        self,
        audio_path: str,
        filename: str = "teacher.mp4",
    ) -> str:

        return await self.provider.generate_video(
            audio_path=audio_path,
            filename=filename,
        )