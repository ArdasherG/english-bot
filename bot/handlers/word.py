import re
import httpx
from aiogram import Router, F
from aiogram.types import Message
from api.services.database import get_user
from api.services.language import detect_language
from config.settings import settings

router = Router()

# Паттерны на английском
EXPLAIN_PATTERNS_EN = [
    r"what does ['\"]?(.+?)['\"]? mean",
    r"what is ['\"]?(.+?)['\"]?",
    r"explain ['\"]?(.+?)['\"]?",
    r"what['']s ['\"]?(.+?)['\"]?",
]

# Паттерны на русском
# Два варианта каждого паттерна: с кавычками (точный) и без (жадный до конца строки)
EXPLAIN_PATTERNS_RU = [
    r"что значит ['\"](.+?)['\"]",
    r"что значит (.+)$",
    r"что такое ['\"](.+?)['\"]",
    r"что такое (.+)$",
    r"объясни ['\"](.+?)['\"]",
    r"объясни (.+)$",
    r"как переводится ['\"](.+?)['\"]",
    r"как переводится (.+)$",
    r"что означает ['\"](.+?)['\"]",
    r"что означает (.+)$",
]


def extract_phrase(text: str) -> tuple[str | None, str]:
    """Возвращает (фраза, язык_вопроса)."""
    lower = text.lower().strip()

    for pattern in EXPLAIN_PATTERNS_RU:
        match = re.search(pattern, lower)
        if match:
            return match.group(1).strip(" '\"?"), "ru"

    for pattern in EXPLAIN_PATTERNS_EN:
        match = re.search(pattern, lower)
        if match:
            return match.group(1).strip(" '\"?"), "en"

    return None, detect_language(text)


@router.message(F.text)
async def handle_text(message: Message):
    phrase, lang = extract_phrase(message.text)

    if not phrase:
        # Подсказка на двух языках
        await message.answer(
            "💡 Попробуй спросить:\n"
            "• *Что значит 'I'm broke'?*\n"
            "• *What does 'hit the sack' mean?*\n"
            "• *Объясни 'under the weather'*\n\n"
            "Или отправь 🎤 *голосовое* — попрактикуемся в разговоре!",
            parse_mode="Markdown",
        )
        return

    await message.bot.send_chat_action(message.chat.id, "typing")

    searching_text = "🔍 Ищу..." if lang == "ru" else f"🔍 Looking up *{phrase}*..."
    await message.answer(searching_text, parse_mode="Markdown")

    profile = await get_user(message.from_user.id)

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.BACKEND_URL}/explain/word",
            json={"phrase": phrase, "profile": profile, "lang": lang},
        )
        response.raise_for_status()
        data = response.json()

    # Объяснение
    if lang == "ru":
        english = data.get("english", "")
        # Заголовок: если был русский запрос — показываем английский эквивалент
        if english and english.lower() != data["phrase"].lower():
            text = f"📖 *{english}*\n🔤 _{data['phrase']}_\n\n"
        else:
            text = f"📖 *{english or data['phrase']}*\n\n"
        text += f"*Значение:* {data['meaning']}\n\n"
        text += f"*Стиль:* {data['tone']}\n\n"
        if data.get("examples"):
            text += "*Примеры:*\n"
            for ex in data["examples"]:
                # GPT даёт формат: "I have no money (У меня нет денег)"
                # или "I have no money — У меня нет денег"
                # Нормализуем к виду: английский (перевод)
                if " (" in ex and ex.endswith(")"):
                    # Уже в нужном формате
                    paren_idx = ex.index(" (")
                    en_part = ex[:paren_idx].strip()
                    ru_part = ex[paren_idx+2:-1].strip()
                    text += f"  • *{en_part}* _({ru_part})_\n"
                elif " — " in ex:
                    en_part, ru_part = ex.split(" — ", 1)
                    text += f"  • *{en_part.strip()}* _({ru_part.strip()})_\n"
                elif " - " in ex:
                    en_part, ru_part = ex.split(" - ", 1)
                    text += f"  • *{en_part.strip()}* _({ru_part.strip()})_\n"
                else:
                    text += f"  • _{ex}_\n"
    else:
        text = f"📖 *{data['phrase']}*\n\n"
        text += f"*Meaning:* {data['meaning']}\n\n"
        text += f"*Tone:* {data['tone']}\n\n"
        if data.get("examples"):
            text += "*Examples:*\n"
            for ex in data["examples"]:
                text += f"  • _{ex}_\n"

    await message.answer(text, parse_mode="Markdown")

    # YouGlish
    hear_text = "Послушай как это звучит от носителей" if lang == "ru" else "Hear it from native speakers"
    caption = "Точные моменты где произносится эта фраза" if lang == "ru" else "Real moments where this phrase is spoken"

    # YouGlish использует английский эквивалент если он есть
    english_for_youglish = data.get("english") or data["phrase"]
    from api.services.youtube import get_youglish_url
    youglish_url = get_youglish_url(english_for_youglish)

    await message.answer(
        f"🎬 *{hear_text}:*\n\n"
        f"🔊 [YouGlish]({youglish_url})\n"
        f"_{caption}_",
        parse_mode="Markdown",
        disable_web_page_preview=False,
    )
