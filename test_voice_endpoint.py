"""
Тест полного voice pipeline через FastAPI endpoint.
Бэкенд должен быть запущен: uvicorn api.main:app --reload --port 8000
Запуск: python test_voice_endpoint.py test_audio.ogg
"""
import asyncio
import sys
import os
import base64
import httpx

sys.path.insert(0, os.path.dirname(__file__))


async def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "test_audio.ogg"

    if not os.path.exists(path):
        print(f"❌ Файл '{path}' не найден.")
        print("   Используй тот же файл что тестировал в Фазе 1")
        print("   python test_voice_endpoint.py my_audio.ogg")
        return

    backend_url = "http://localhost:8000"

    print(f"🚀 Отправляем '{path}' на {backend_url}/voice/process ...")
    print("   (Whisper → Groq → Edge TTS — займёт несколько секунд)\n")

    async with httpx.AsyncClient(timeout=60) as client:
        # Проверяем что бэкенд живой
        try:
            health = await client.get(f"{backend_url}/health")
            health.raise_for_status()
        except Exception:
            print("❌ Бэкенд не отвечает!")
            print(f"   Запусти: uvicorn api.main:app --reload --port 8000")
            return

        # Отправляем аудио
        with open(path, "rb") as f:
            response = await client.post(
                f"{backend_url}/voice/process",
                files={"audio": (os.path.basename(path), f, "audio/ogg")},
            )

        if response.status_code != 200:
            print(f"❌ Ошибка {response.status_code}: {response.text}")
            return

        data = response.json()

    print("✅ Ответ получен!\n")
    print(f"🗣  Ты сказал:    \"{data['user_text']}\"")
    print(f"💬 Ответ:        \"{data['reply']}\"")
    print(f"✏️  Коррекция:    {data['correction']}")
    print(f"✅ Улучшено:     {data['improved']}")

    # Сохраняем аудио ответ
    if data.get("audio_base64"):
        audio_bytes = base64.b64decode(data["audio_base64"])
        out_path = "test_voice_reply.mp3"
        with open(out_path, "wb") as f:
            f.write(audio_bytes)
        print(f"\n🔊 Голосовой ответ сохранён: {out_path}")
        print("   Открой и послушай!")

    print("\n🎉 Полный pipeline работает! Можно подключать Telegram бот.")


asyncio.run(main())
