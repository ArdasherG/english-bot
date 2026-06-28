"""
Тест локального Whisper.
Запуск: python test_whisper.py
        python test_whisper.py my_audio.mp3
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


async def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "test_audio.ogg"

    if not os.path.exists(path):
        print(f"❌ Файл '{path}' не найден.")
        print("   Положи .ogg/.mp3 рядом со скриптом и переименуй в test_audio.ogg")
        print("   Или: python test_whisper.py /path/to/file.mp3")
        return

    from api.services.whisper import transcribe

    print(f"🎧 Транскрибируем '{path}'...")
    print("   (первый запуск загружает модель — подожди немного)\n")

    with open(path, "rb") as f:
        audio_bytes = f.read()

    try:
        text = await transcribe(audio_bytes, filename=path)
        print(f"✅ Готово!")
        print(f"📝 Результат: \"{text}\"")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("\nПроверь что установлен ffmpeg:")
        print("  macOS:   brew install ffmpeg")
        print("  Ubuntu:  sudo apt install ffmpeg")
        print("  Windows: https://ffmpeg.org/download.html")


asyncio.run(main())
