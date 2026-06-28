from groq import AsyncGroq
from config.settings import settings

client = AsyncGroq(api_key=settings.GROQ_API_KEY)


# Профиль пользователя

def build_user_context(profile: dict | None) -> str:
    if not profile or not profile.get("onboarded"):
        return ""
    interests = profile.get("interests") or []
    interests_str = ", ".join(interests) if interests else "not specified"
    return (
        f"\n\nUSER PROFILE:\n"
        f"- English level: {profile.get('level', 'unknown')}\n"
        f"- Profession: {profile.get('profession', 'not specified')}\n"
        f"- Interests: {interests_str}\n"
        f"- Goal: {profile.get('goal', 'not specified')}\n\n"
        "Use this profile to personalize examples. "
        "Match vocabulary complexity to their level. "
        "Use examples from their field and interests when possible."
    )


# Промпты — английский


def voice_system_en(profile: dict | None) -> str:
    return (
        "You are an English tutor inside a Telegram bot.\n"
        "The user has just spoken a sentence. Your job:\n"
        "1. Reply naturally to what they said (1-2 sentences max).\n"
        "2. If there are grammar/vocabulary mistakes, point them out briefly.\n"
        "3. Show an improved sentence if needed.\n\n"
        "Format your response exactly like this:\n"
        "REPLY: <your natural reply>\n"
        "CORRECTION: <what was wrong, or 'No mistakes!'>\n"
        "IMPROVED: <corrected sentence, or '-'>" + build_user_context(profile)
    )


def explain_system_en(profile: dict | None) -> str:
    return (
        "You are an English tutor. The user wants to understand a word or phrase.\n"
        "Explain it clearly and concisely:\n"
        "1. Meaning in simple English.\n"
        "2. Tone/register (formal, informal, slang, rude, etc.).\n"
        "3. Two short example sentences relevant to the user's profile.\n\n"
        "Format:\n"
        "MEANING: <explanation>\n"
        "TONE: <tone/register>\n"
        "EXAMPLES:\n"
        "- <example 1>\n"
        "- <example 2>" + build_user_context(profile)
    )


#  Промпты — русский

def voice_system_ru(profile: dict | None) -> str:
    return (
        "Ты — репетитор по английскому языку в Telegram боте.\n"
        "Пользователь только что произнёс фразу на английском. Твоя задача:\n"
        "1. Естественно ответить на его фразу (1-2 предложения максимум).\n"
        "2. Если есть грамматические или лексические ошибки — кратко укажи на них на русском.\n"
        "3. Покажи исправленный вариант.\n\n"
        "Отвечай строго в таком формате:\n"
        "REPLY: <твой естественный ответ на английском>\n"
        "CORRECTION: <что было не так — объясни по-русски, или напиши 'Ошибок нет!'>\n"
        "IMPROVED: <исправленное предложение, или '-'>" + build_user_context(profile)
    )


def explain_system_ru(profile: dict | None) -> str:
    return (
        "Ты — репетитор по английскому языку. Пользователь спрашивает про слово или фразу — "
        "она может быть как на английском, так и на русском.\n\n"
        "Твоя задача:\n"
        "1. Если фраза на русском — найди её английский эквивалент.\n"
        "2. Объясни значение и стиль по-русски.\n"
        "3. Дай два примера на английском с русским переводом.\n\n"
        "Отвечай СТРОГО по этому шаблону:\n\n"
        "ENGLISH: <английский эквивалент или оригинальная английская фраза>\n"
        "MEANING: <английская фраза> — <значение по-русски кратко>\n"
        "TONE: <стиль: формальный / разговорный / сленг / нейтральный>\n"
        "EXAMPLES:\n"
        "- <пример на английском> — <перевод на русском>\n"
        "- <пример на английском> — <перевод на русском>\n\n"
        "Правила:\n"
        "- ENGLISH — всегда первая строка\n"
        "- Примеры ВСЕГДА начинаются с английского предложения\n"
        "- Не пиши примеры только на русском" + build_user_context(profile)
    )


# Публичные функции

async def process_voice_input(
    user_text: str,
    profile: dict | None = None,
    lang: str = "en",
) -> dict:
    system = voice_system_ru(profile) if lang == "ru" else voice_system_en(profile)

    response = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        temperature=0.7,
    )
    return _parse_voice_response(response.choices[0].message.content)


async def explain_word(
    phrase: str,
    profile: dict | None = None,
    lang: str = "en",
) -> dict:
    system = explain_system_ru(profile) if lang == "ru" else explain_system_en(profile)

    response = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": phrase},
        ],
        temperature=0.5,
    )
    return _parse_explain_response(response.choices[0].message.content)


# Парсеры


def _parse_voice_response(raw: str) -> dict:
    result = {"reply": "", "correction": "", "improved": ""}
    for line in raw.splitlines():
        if line.startswith("REPLY:"):
            result["reply"] = line.removeprefix("REPLY:").strip()
        elif line.startswith("CORRECTION:"):
            result["correction"] = line.removeprefix("CORRECTION:").strip()
        elif line.startswith("IMPROVED:"):
            result["improved"] = line.removeprefix("IMPROVED:").strip()
    return result


def _parse_explain_response(raw: str) -> dict:
    result = {"english": "", "meaning": "", "tone": "", "examples": []}
    in_examples = False
    for line in raw.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("ENGLISH:"):
            result["english"] = stripped[len("ENGLISH:") :].strip()
        elif upper.startswith("MEANING:"):
            result["meaning"] = stripped[len("MEANING:") :].strip()
        elif upper.startswith("TONE:"):
            result["tone"] = stripped[len("TONE:") :].strip()
        elif upper.startswith("EXAMPLES:") or upper.startswith("ПРИМЕРЫ:"):
            in_examples = True
        elif in_examples and stripped.startswith("-"):
            val = stripped.lstrip("-").strip()
            if val:
                result["examples"].append(val)
    # Фолбэк: если парсер не нашёл ничего — вернуть raw как meaning
    if not result["meaning"] and not result["tone"]:
        result["meaning"] = raw.strip()
    return result


# Анализ субтитров


async def analyze_subtitles(
    title: str,
    text: str,
    profile: dict | None = None,
    interface_lang: str = "ru",
) -> dict:
    """
    Один запрос к GPT — саммари + список слов для изучения.
    Возвращает {summary, words: [{word, context}]}
    """
    level = profile.get("level", "intermediate") if profile else "intermediate"
    interests = ", ".join(profile.get("interests") or []) if profile else ""
    profession = profile.get("profession", "") if profile else ""

    if interface_lang == "ru":
        summary_lang = "Russian"
        word_explain_lang = "Give a one-line hint in Russian after each word."
    else:
        summary_lang = "English"
        word_explain_lang = "Give a one-line hint in English after each word."

    system = (
        f"You are an English tutor analyzing a YouTube video for a student.\n"
        f"Student level: {level}\n"
        f"Profession: {profession or 'not specified'}\n"
        f"Interests: {interests or 'not specified'}\n\n"
        f"Your task — analyze the subtitles and respond in this EXACT format:\n\n"
        f"SUMMARY: <2-3 sentence summary of the video in {summary_lang}>\n"
        f"WORDS:\n"
        f"- <word or phrase>|<short example sentence from the video context>|<hint>\n"
        f"- <word or phrase>|<short example sentence from the video context>|<hint>\n"
        f"(5 to 7 words total)\n\n"
        f"Rules:\n"
        f"- Choose words/phrases that are useful for this student's level and interests\n"
        f"- For beginner: basic vocabulary they might not know\n"
        f"- For intermediate/advanced: idioms, collocations, formal phrases\n"
        f"- Example sentences should come from the video context, not invented\n"
        f"- {word_explain_lang}\n"
        f"- No extra text outside the format"
    )

    # Обрезаем субтитры до разумного размера для GPT
    words = text.split()
    if len(words) > 2000:
        text = " ".join(words[:2000])

    response = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Video title: {title}\n\nSubtitles:\n{text}"},
        ],
        temperature=0.4,
    )
    raw = response.choices[0].message.content
    return _parse_subtitles_response(raw)


def _parse_subtitles_response(raw: str) -> dict:
    result = {"summary": "", "words": []}
    in_words = False

    for line in raw.splitlines():
        line = line.strip()
        if line.upper().startswith("SUMMARY:"):
            result["summary"] = line[len("SUMMARY:") :].strip()
        elif line.upper().startswith("WORDS:"):
            in_words = True
        elif in_words and line.startswith("-"):
            parts = line.lstrip("- ").split("|")
            if len(parts) >= 2:
                result["words"].append(
                    {
                        "word": parts[0].strip(),
                        "example": parts[1].strip() if len(parts) > 1 else "",
                        "hint": parts[2].strip() if len(parts) > 2 else "",
                    }
                )

    return result


async def generate_quiz_question(
    word: str,
    example: str,
    interface_lang: str = "ru",
) -> dict:
    """Генерирует вопрос викторины для одного слова."""
    lang_instruction = (
        "Write the question and options in English. Explanation in Russian."
        if interface_lang == "ru"
        else "Write everything in English."
    )

    system = (
        f"Generate a fill-in-the-blank quiz question for the word/phrase: '{word}'\n"
        f"Use this example as a base: '{example}'\n"
        f"Format EXACTLY:\n"
        f"QUESTION: <sentence with ___ instead of the word>\n"
        f"A: {word} (always the correct answer)\n"
        f"B: <a plausible but wrong word>\n"
        f"C: <another plausible but wrong word>\n"
        f"CORRECT: A\n"
        f"EXPLANATION: <what '{word}' means in one sentence, NO mention of 'answer A' or 'option A'>\n"
        f"{lang_instruction}\n"
        f"IMPORTANT: EXPLANATION must explain the word meaning only, never say 'correct answer is A'"
    )

    response = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": system}],
        temperature=0.5,
    )
    return _parse_quiz_response(response.choices[0].message.content)


def _parse_quiz_response(raw: str) -> dict:
    result = {"question": "", "options": {}, "correct": "A", "explanation": ""}
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("QUESTION:"):
            result["question"] = line[len("QUESTION:") :].strip()
        elif line.startswith("A:"):
            result["options"]["A"] = line[2:].strip()
        elif line.startswith("B:"):
            result["options"]["B"] = line[2:].strip()
        elif line.startswith("C:"):
            result["options"]["C"] = line[2:].strip()
        elif line.startswith("CORRECT:"):
            result["correct"] = line[len("CORRECT:") :].strip()
        elif line.startswith("EXPLANATION:"):
            result["explanation"] = line[len("EXPLANATION:") :].strip()
    return result