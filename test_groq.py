"""
Тест Groq API — оба промпта (voice + explain).
Запуск: python test_groq.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


async def test_voice():
    from api.services.gpt import process_voice_input

    print("=" * 50)
    print("🎤 ТЕСТ 1: Voice промпт (с ошибкой)")
    print("=" * 50)

    # Фраза с типичными ошибками
    test_phrase = "Yesterday I go to the store and buyed some milk."
    print(f"📝 Входная фраза: \"{test_phrase}\"\n")

    result = await process_voice_input(test_phrase)

    print(f"💬 REPLY:      {result['reply']}")
    print(f"✏️  CORRECTION: {result['correction']}")
    print(f"✅ IMPROVED:   {result['improved']}")

    # Проверяем что все поля заполнены
    ok = all(result.values())
    print(f"\n{'✅ Промпт парсится корректно' if ok else '⚠️  Некоторые поля пустые — проверь промпт'}")
    return ok


async def test_explain():
    from api.services.gpt import explain_word

    print("\n" + "=" * 50)
    print("📖 ТЕСТ 2: Explain промпт")
    print("=" * 50)

    test_phrase = "I'm broke"
    print(f"📝 Фраза: \"{test_phrase}\"\n")

    result = await explain_word(test_phrase)

    print(f"📖 MEANING:  {result['meaning']}")
    print(f"🎭 TONE:     {result['tone']}")
    print(f"💡 EXAMPLES:")
    for ex in result["examples"]:
        print(f"   • {ex}")

    ok = result["meaning"] and result["tone"] and len(result["examples"]) >= 1
    print(f"\n{'✅ Промпт парсится корректно' if ok else '⚠️  Некоторые поля пустые — проверь промпт'}")
    return ok


async def test_no_mistakes():
    from api.services.gpt import process_voice_input

    print("\n" + "=" * 50)
    print("🎤 ТЕСТ 3: Voice промпт (без ошибок)")
    print("=" * 50)

    test_phrase = "I went to the store yesterday and bought some milk."
    print(f"📝 Входная фраза: \"{test_phrase}\"\n")

    result = await process_voice_input(test_phrase)

    print(f"💬 REPLY:      {result['reply']}")
    print(f"✏️  CORRECTION: {result['correction']}")
    print(f"✅ IMPROVED:   {result['improved']}")
    return True


async def main():
    print("\n🚀 Тестируем Groq API...\n")

    try:
        r1 = await test_voice()
        r2 = await test_explain()
        r3 = await test_no_mistakes()

        print("\n" + "=" * 50)
        if r1 and r2 and r3:
            print("🎉 Все тесты прошли! Groq готов к работе.")
            print("   Можно двигаться к Фазе 3 (Edge TTS)")
        else:
            print("⚠️  Часть тестов не прошла — проверь промпты в gpt.py")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("\nПроверь:")
        print("  1. GROQ_API_KEY в .env файле")
        print("  2. Формат ключа: gsk_...")
        print("  3. pip install groq")


asyncio.run(main())
