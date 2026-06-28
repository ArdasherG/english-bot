"""
Сервис для работы с субтитрами YouTube через yt-dlp.
Кэширует субтитры в SQLite чтобы не скачивать одно видео дважды.
"""
import re
import json
import asyncio
import tempfile
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import aiosqlite
from api.services.database import DB_PATH

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2)

MAX_WORDS = 4000  # ~30 минут видео


# ─── Кэш субтитров ───────────────────────────────────────────────────────────

async def init_subtitles_cache():
    """Создаёт таблицу кэша если нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subtitles_cache (
                video_id   TEXT PRIMARY KEY,
                title      TEXT,
                subtitles  TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def get_cached(video_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM subtitles_cache WHERE video_id = ?", (video_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def save_cache(video_id: str, title: str, subtitles: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO subtitles_cache (video_id, title, subtitles) VALUES (?, ?, ?)",
            (video_id, title, subtitles),
        )
        await db.commit()


# ─── Утилиты ─────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str | None:
    """Извлекает video_id из YouTube URL."""
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _clean_vtt(vtt_text: str) -> str:
    """Очищает VTT субтитры — убирает теги, метки времени, дубли."""
    lines = vtt_text.split("\n")
    seen = set()
    result = []

    for line in lines:
        line = line.strip()
        # Пропускаем служебные строки
        if not line or line.startswith("WEBVTT") or "-->" in line:
            continue
        if re.match(r"^\d+$", line):
            continue
        # Убираем HTML теги
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"&amp;", "&", line)
        line = re.sub(r"&quot;", '"', line)
        # Убираем дубли подряд
        if line and line not in seen:
            seen.add(line)
            result.append(line)

    text = " ".join(result)
    # Обрезаем до MAX_WORDS
    words = text.split()
    if len(words) > MAX_WORDS:
        text = " ".join(words[:MAX_WORDS])
        logger.info(f"Subtitles truncated to {MAX_WORDS} words")

    return text


def _download_subtitles(video_id: str) -> dict:
    """
    Синхронная функция — запускается в executor.
    Скачивает субтитры через yt-dlp, возвращает {title, text}.
    """
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
            "subtitlesformat": "vtt",
            "outtmpl": f"{tmpdir}/%(id)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Unknown")
            language = info.get("language") or ""
            # Проверяем что видео на английском
            if language and not language.startswith("en"):
                raise ValueError(f"Video language is '{language}', not English")

        # Ищем скачанный файл субтитров
        vtt_files = list(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            raise FileNotFoundError(
                "No English subtitles found. "
                "Try a video with English subtitles or auto-captions."
            )

        vtt_text = vtt_files[0].read_text(encoding="utf-8")
        clean_text = _clean_vtt(vtt_text)

        if not clean_text.strip():
            raise ValueError("Subtitles are empty after processing")

        return {"title": title, "text": clean_text}


# ─── Публичный API ────────────────────────────────────────────────────────────

async def get_subtitles(url: str) -> dict:
    """
    Основная функция. Возвращает {video_id, title, text}.
    Использует кэш если видео уже скачивалось.
    Бросает ValueError / FileNotFoundError с понятным сообщением.
    """
    await init_subtitles_cache()

    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Не удалось определить ID видео. Проверь ссылку.")

    # Проверяем кэш
    cached = await get_cached(video_id)
    if cached:
        logger.info(f"Subtitles cache hit for {video_id}")
        return {
            "video_id": video_id,
            "title": cached["title"],
            "text": cached["subtitles"],
            "from_cache": True,
        }

    # Скачиваем в executor чтобы не блокировать event loop
    logger.info(f"Downloading subtitles for {video_id}")
    loop = asyncio.get_event_loop()
    result = await asyncio.wait_for(
        loop.run_in_executor(_executor, _download_subtitles, video_id),
        timeout=30.0,
    )

    # Сохраняем в кэш
    await save_cache(video_id, result["title"], result["text"])

    return {
        "video_id": video_id,
        "title": result["title"],
        "text": result["text"],
        "from_cache": False,
    }
