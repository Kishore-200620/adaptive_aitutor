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
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_concise_narration(narration: str) -> str:
    """Extracts a pedagogical, concise narration (1-3 sentences, approx 20-50 words)."""
    if not narration:
        return ""
    
    clean = strip_markdown_for_tts(narration)
    sentences = re.split(r'(?<=[.!?])\s+', clean.strip())
    
    concise = []
    word_count = 0
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        concise.append(s)
        word_count += len(s.split())
        # Stop if we hit 3 sentences or roughly 40 words
        if word_count >= 40 or len(concise) >= 3:
            break
            
    return " ".join(concise)

class TTSService:
    VOICES = {
        "English": "en-US-AndrewNeural",
        "Tamil": "ta-IN-ValluvarNeural",
        "Hindi": "hi-IN-MadhurNeural",
    }

    def __init__(self, output_dir: str = "storage/audio"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.job_status: dict[str, str] = {}

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

        self.job_status[filename] = "pending"
        temp_output_path = output_path.with_suffix(".mp3.tmp")
        
        max_attempts = 3
        
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"TTS_ATTEMPT attempt={attempt}/{max_attempts}")
                
                communicate = edge_tts.Communicate(
                    text=clean_text,
                    voice=voice,
                    connect_timeout=2,
                )
                
                if temp_output_path.exists():
                    temp_output_path.unlink(missing_ok=True)

                # edge_tts can occasionally hang indefinitely, but real generation can take longer than 10s
                await asyncio.wait_for(communicate.save(str(temp_output_path)), timeout=60.0)
                
                if temp_output_path.exists():
                    temp_output_path.replace(output_path)
                    
                self.job_status[filename] = "ready"
                print(f"TTS_SUCCESS attempt={attempt}/{max_attempts}")
                return str(output_path)
                
            except asyncio.CancelledError:
                print(f"TTS_CANCELLED attempt={attempt}/{max_attempts}")
                self.job_status[filename] = "failed"
                if temp_output_path.exists():
                    try:
                        temp_output_path.unlink()
                    except OSError:
                        pass
                raise  # Preserve cancellation semantics

            except Exception as e:
                print(f"TTS_ATTEMPT_FAILED attempt={attempt}/{max_attempts} error={type(e).__name__}: {str(e)}")
                if temp_output_path.exists():
                    try:
                        temp_output_path.unlink()
                    except OSError:
                        pass
                
                if attempt == max_attempts:
                    self.job_status[filename] = "failed"
                    import traceback
                    error_msg = f"TTS_FAILED attempts={max_attempts} error={type(e).__name__}: {str(e)}\nVoice: {voice}\nLanguage: {language}\nException Type: {type(e)}\nException Message: {str(e)}\n"
                    error_msg += traceback.format_exc()
                    with open("tts_error.log", "a") as f:
                        f.write(error_msg + "\n")
                    print(f"TTS_FAILED attempts={max_attempts} error={type(e).__name__}: {str(e)}")
                    return None
                
                # Exponential backoff
                delay = 0.5 * attempt
                print(f"TTS_RETRY attempt={attempt+1}/{max_attempts} delay={delay}s")
                await asyncio.sleep(delay)



# Module-level singleton
tts_service = TTSService()

# Module-level strong-reference set to prevent Python GC from killing background tasks
active_tts_tasks = set()

def start_background_speech(text: str, language: str, filename: str):
    """
    Creates an asyncio task for TTS generation, adds it to a strong reference set,
    and sets a done callback to remove it and observe any exceptions.
    """
    # Use the shared instance
    tts_service.job_status[filename] = "pending"
    task = asyncio.create_task(tts_service.generate_speech(
        text=text,
        language=language,
        filename=filename,
    ))
    active_tts_tasks.add(task)
    
    def on_task_done(t):
        active_tts_tasks.discard(t)
        try:
            t.result()
        except BaseException as e:
            print(f"[TTS Task Manager] Unhandled exception in background task for {filename}: {e}")
            import traceback
            traceback.print_exc()

    task.add_done_callback(on_task_done)
    return task