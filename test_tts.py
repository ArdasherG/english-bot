"""
Тест Edge TTS.
Запуск: python test_tts.py
Создаёт файл test_output.mp3 — открой и послушай.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


async def test_basic():
    from api.services.tts import synthesize

    print("=" * 50)
    print("🔊 ТЕСТ 1: Базовый синтез речи")
    print("=" * 50)

    text = "Yesterday I went to the store and bought some milk. No mistakes this time!"
    print(f"📝 Текст: \"{text}\"\n")

    audio = await synthesize(text)

    output_path = "test_output.mp3"
    with open(output_path, "wb") as f:
        f.write(audio)

    size_kb = len(audio) / 1024
    print(f"✅ Аудио сгенерировано: {size_kb:.1f} KB")
    print(f"📁 Сохранено в: {output_path}")
    print(f"   Открой файл и послушай!")
    return True


async def test_correction():
    from api.services.tts import synthesize

    print("\n" + "=" * 50)
    print("🔊 ТЕСТ 2: Синтез исправленной фразы")
    print("=" * 50)

    text = "The correct way to say it is: I went to the store and bought some milk."
    print(f"📝 Текст: \"{text}\"\n")

    audio = await synthesize(text)

    output_path = "test_output_correction.mp3"
    with open(output_path, "wb") as f:
        f.write(audio)

    size_kb = len(audio) / 1024
    print(f"✅ Аудио сгенерировано: {size_kb:.1f} KB")
    print(f"📁 Сохранено в: {output_path}")
    return True


async def list_voices():
    from api.services.tts import list_voices

    print("\n" + "=" * 50)
    print("🎙️  Доступные английские голоса")
    print("=" * 50)

    voices = await list_voices()
    for v in voices:
        print(f"  {v['name']:<35} {v['gender']:<8} {v['locale']}")

    print(f"\nТекущий голос в .env: ", end="")
    from config.settings import settings
    print(settings.EDGE_TTS_VOICE)


async def main():
    print("\n🚀 Тестируем Edge TTS...\n")

    try:
        await test_basic()
        await test_correction()
        await list_voices()

        print("\n" + "=" * 50)
        print("🎉 Edge TTS работает!")
        print("   Если голос не нравится — смени EDGE_TTS_VOICE в .env")
        print("   Можно двигаться к Фазе 4 (Telegram Bot)")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("\nПроверь:")
        print("  1. pip install edge-tts")
        print("  2. Интернет соединение (Edge TTS требует сеть)")


asyncio.run(main())
