import tempfile
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import whisper
from config.settings import settings

_model = None
_executor = ThreadPoolExecutor(max_workers=2)  # максимум 2 одновременных транскрипции


def get_model():
    global _model
    if _model is None:
        print(f"⏳ Загружаем Whisper модель '{settings.WHISPER_MODEL_SIZE}'...")
        _model = whisper.load_model(settings.WHISPER_MODEL_SIZE)
        print("✅ Whisper модель загружена")
    return _model


async def transcribe(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    """Транскрибирует аудио. Бросает RuntimeError если что-то пошло не так."""
    if not audio_bytes:
        raise ValueError("Пустой аудио файл")

    suffix = Path(filename).suffix or ".ogg"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                _executor,
                lambda: get_model().transcribe(tmp_path, language="en")
            ),
            timeout=60.0,  # максимум 60 секунд на транскрипцию
        )
        text = result["text"].strip()
        if not text:
            raise RuntimeError("Whisper не смог распознать речь — попробуй ещё раз")
        return text
    except asyncio.TimeoutError:
        raise RuntimeError("Транскрипция заняла слишком долго — попробуй более короткое сообщение")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
