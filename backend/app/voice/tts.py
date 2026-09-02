from pathlib import Path
import edge_tts


class TTSService:
    VOICES = {
        "English": "en-US-AndrewNeural",
        "Tamil": "ta-IN-ValluvarNeural",
        "Hindi": "hi-IN-MadhurNeural",
    }

    def __init__(self, output_dir: str = "storage/audio"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_voice(self, language: str) -> str:
        return self.VOICES.get(language, self.VOICES["English"])

    async def generate_speech(
        self,
        text: str,
        language: str = "English",
        filename: str = "speech.mp3",
    ) -> str:
        voice = self.get_voice(language)

        output_path = self.output_dir / filename

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
        )

        await communicate.save(str(output_path))

        return str(output_path)