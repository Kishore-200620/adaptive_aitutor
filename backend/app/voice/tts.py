import asyncio
import re
from pathlib import Path
import edge_tts


def strip_markdown_for_tts(text: str) -> str:
    """Removes common markdown formatting that trips up edge_tts."""
    if not text:
        return ""
    # Remove headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    # Remove backticks (code)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    # Clean up excessive newlines/spaces
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


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
    ) -> str | None:
        voice = self.get_voice(language)

        output_path = self.output_dir / filename
        
        clean_text = strip_markdown_for_tts(text)
        if not clean_text:
            return None

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=voice,
        )

        try:
            # edge_tts can occasionally hang indefinitely, but real generation can take longer than 10s
            await asyncio.wait_for(communicate.save(str(output_path)), timeout=60.0)
            return str(output_path)
        except Exception as e:
            import traceback
            print(f"[TTS] Error generating speech:")
            print(f"      Voice: {voice}")
            print(f"      Language: {language}")
            print(f"      Text length: {len(clean_text)}")
            print(f"      Exception Type: {type(e)}")
            print(f"      Exception Message: {str(e)}")
            traceback.print_exc()
            return None