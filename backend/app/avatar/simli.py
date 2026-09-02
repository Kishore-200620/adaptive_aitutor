import base64
from pathlib import Path
import asyncio
import httpx


class SimliAvatarService:

    API_URL = "https://api.simli.ai/static/audio"

    def __init__(
        self,
        api_key: str,
        face_id: str,
        output_dir: str = "storage/video",
    ):
        self.api_key = api_key
        self.face_id = face_id

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    @property
    def configured(self) -> bool:
        return bool(
            self.api_key
            and self.face_id
        )

    async def generate_video(
        self,
        audio_path: str,
        filename: str = "teacher.mp4",
    ) -> str:

        if not self.configured:
            raise RuntimeError(
                "Simli avatar is not configured. "
                "Set SIMLI_API_KEY and AVATAR_MODEL_ID."
            )

        audio_file = Path(audio_path)

        if not audio_file.exists():
            raise FileNotFoundError(
                f"Audio file not found: {audio_file}"
            )

        audio_bytes = audio_file.read_bytes()

        audio_base64 = base64.b64encode(
            audio_bytes
        ).decode("utf-8")

        payload = {
            "faceId": self.face_id,
            "audioBase64": audio_base64,
            "audioFormat": "mp3",
            "audioSampleRate": 16000,
            "audioChannelCount": 1,
            "videoStartingFrame": 0,
        }

        headers = {
            "Content-Type": "application/json",
            "x-simli-api-key": self.api_key,
        }

        async with httpx.AsyncClient(
            timeout=120.0
        ) as client:

            response = await client.post(
                self.API_URL,
                json=payload,
                headers=headers,
            )

            if response.status_code >= 400:
                print("SIMLI STATUS:", response.status_code)
                print("SIMLI RESPONSE:", response.text)

            response.raise_for_status()

            data = response.json()
            print("SIMLI SUCCESS RESPONSE:", data)
        mp4_url = data.get("mp4_url")

        if not mp4_url:
            raise RuntimeError(
                f"Simli did not return an MP4 URL: {data}"
            )

        
        output_path = self.output_dir / filename

        # Simli currently documents the MP4 endpoint as
        # /static/mp4/{destination}/{file}.
        # Some responses still return the legacy /mp4/... URL.
        static_mp4_url = mp4_url.replace(
            "https://api.simli.ai/mp4/",
            "https://api.simli.ai/static/mp4/",
            1,
        )

        print(
            "SIMLI MP4 URL:",
            static_mp4_url,
        )

        max_attempts = 12
        wait_seconds = 10

        async with httpx.AsyncClient(
            timeout=120.0
        ) as client:

            for attempt in range(1, max_attempts + 1):

                print(
                    f"SIMLI MP4 CHECK {attempt}/{max_attempts}"
                )

                try:
                    async with client.stream(
                        "GET",
                        static_mp4_url,
                    ) as video_response:

                        print(
                            "SIMLI MP4 STATUS:",
                            video_response.status_code,
                        )

                        if video_response.status_code == 200:

                            video_content = await video_response.aread()

                            output_path.write_bytes(
                                video_content
                            )

                            print(
                                "SIMLI VIDEO DOWNLOADED:",
                                output_path,
                            )

                            return str(output_path)

                except httpx.HTTPError as exc:

                    print(
                        "SIMLI MP4 REQUEST ERROR:",
                        exc,
                    )

                if attempt < max_attempts:

                    print(
                        f"Waiting {wait_seconds} seconds..."
                    )

                    await asyncio.sleep(
                        wait_seconds
                    )

        raise RuntimeError(
            "Simli video was generated but MP4 "
            "was not available within the expected time."
        )