import tempfile
import asyncio
from pathlib import Path
from gtts import gTTS
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=2)


def _synthesize_sync(text: str, path: str):
    tts = gTTS(text=text, lang='en', slow=False)
    tts.save(path)


async def synthesize(text: str) -> bytes:
    """Принимает текст, возвращает mp3-байты через gTTS."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, _synthesize_sync, text, tmp_path)

        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
