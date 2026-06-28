"""
Свободный диалог /chat — общение с носителем английского.
Выход: /stop или 15 минут неактивности.
"""
import asyncio
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from groq import AsyncGroq
from api.services.database import get_user, save_message, get_history
from api.services.language import detect_language
from config.settings import settings

router = Router()
client = AsyncGroq(api_key=settings.GROQ_API_KEY)

# Таймер неактивности: {user_id: asyncio.Task}
_timers: dict[int, asyncio.Task] = {}

TIMEOUT_SECONDS = 15 * 60  # 15 минут


class ChatStates(StatesGroup):
    active = State()


def chat_system(interface_lang: str, profile: dict | None) -> str:
    """Промпт для свободного диалога."""
    interests = ""
    if profile and profile.get("interests"):
        interests = f"User interests: {', '.join(profile['interests'])}. Use these as conversation topics when natural."

    if interface_lang == "ru":
        correction_instruction = (
            "If the user makes a real grammar mistake (not just style):\n"
            "- First give your natural reply in English as if nothing happened\n"
            "- Then on a NEW LINE add: ✏️ <corrected sentence in English> — <very short explanation in Russian>\n"
            "Example of correction line: ✏️ What movie did you see? — \'did you see\' вместо \'видели\'\n"
            "NEVER mix Russian into your English reply. Correction is always on a separate line."
        )
    else:
        correction_instruction = (
            "If the user makes a real grammar mistake (not just style):\n"
            "- First give your natural reply in English as if nothing happened\n"
            "- Then on a NEW LINE add: ✏️ <corrected sentence> — <one short reason why>\n"
            "Example: ✏️ What movie did you see? — use past simple \'did you see\', not \'видели\'\n"
            "NEVER interrupt your reply mid-sentence to correct. Correction is always on a separate line."
        )

    return (
        "You are a friendly native English speaker having a casual conversation.\n"
        "Rules:\n"
        "1. Always reply in English — short, natural, 1-3 sentences max.\n"
        f"2. {correction_instruction}\n"
        "3. Only ONE correction per message. If there are multiple mistakes, fix the worst one only.\n"
        "4. Keep the conversation going — end with a follow-up question when natural.\n"
        "5. Match the energy and topic the user brings. Be warm, not formal.\n"
        + (f"\n{interests}" if interests else "")
    )


async def _timeout_task(user_id: int, state: FSMContext, bot):
    """Автоматически завершает чат после 15 минут тишины."""
    await asyncio.sleep(TIMEOUT_SECONDS)
    current = await state.get_state()
    if current == ChatStates.active.state:
        await state.clear()
        profile = await get_user(user_id)
        lang = profile.get("interface_lang", "ru") if profile else "ru"
        msg = (
            "⏰ Чат завершён — 15 минут без активности. Напиши /chat чтобы начать снова!"
            if lang == "ru"
            else "⏰ Chat ended — 15 minutes of inactivity. Type /chat to start again!"
        )
        await bot.send_message(user_id, msg)


def _reset_timer(user_id: int, state: FSMContext, bot):
    """Сбрасывает таймер неактивности."""
    if user_id in _timers:
        _timers[user_id].cancel()
    _timers[user_id] = asyncio.create_task(
        _timeout_task(user_id, state, bot)
    )


@router.message(Command("chat"))
async def cmd_chat(message: Message, state: FSMContext):
    current = await state.get_state()
    if current == ChatStates.active.state:
        await message.answer("💬 Мы уже в режиме диалога! Напиши /stop чтобы выйти.")
        return

    profile = await get_user(message.from_user.id)
    lang = profile.get("interface_lang", "ru") if profile else "ru"

    await state.set_state(ChatStates.active)
    _reset_timer(message.from_user.id, state, message.bot)

    if lang == "ru":
        await message.answer(
            "💬 *Режим свободного диалога*\n\n"
            "Я буду говорить по-английски как носитель.\n"
            "Если допустишь ошибку — мягко поправлю по-русски прямо в ответе.\n\n"
            "Напиши */stop* чтобы выйти.\n\n"
            "—\n\n"
            "Hey! What's on your mind today? 😊",
            parse_mode="Markdown",
        )
    else:
        await message.answer(
            "💬 *Free conversation mode*\n\n"
            "I'll chat with you like a native speaker.\n"
            "If you make a mistake, I'll gently correct it in parentheses.\n\n"
            "Type */stop* to exit.\n\n"
            "—\n\n"
            "Hey! What's on your mind today? 😊",
            parse_mode="Markdown",
        )


@router.message(Command("stop"))
async def cmd_stop(message: Message, state: FSMContext):
    current = await state.get_state()
    if current != ChatStates.active.state:
        await message.answer("Ты сейчас не в режиме диалога.")
        return

    await state.clear()
    if message.from_user.id in _timers:
        _timers[message.from_user.id].cancel()
        del _timers[message.from_user.id]

    profile = await get_user(message.from_user.id)
    lang = profile.get("interface_lang", "ru") if profile else "ru"

    if lang == "ru":
        await message.answer(
            "👋 Диалог завершён! Хорошая практика.\n\n"
            "🎤 Голосовое — практика произношения\n"
            "📖 *Что значит X?* — объяснение слова\n"
            "💬 */chat* — начать снова",
            parse_mode="Markdown",
        )
    else:
        await message.answer(
            "👋 Chat ended! Good practice.\n\n"
            "🎤 Voice message — pronunciation practice\n"
            "📖 *What does X mean?* — word explanation\n"
            "💬 */chat* — start again",
            parse_mode="Markdown",
        )


@router.message(ChatStates.active, F.text)
async def handle_chat_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_text = message.text or ""

    # Сбрасываем таймер при каждом сообщении
    _reset_timer(user_id, state, message.bot)

    await message.bot.send_chat_action(message.chat.id, "typing")

    profile = await get_user(user_id)
    interface_lang = profile.get("interface_lang", "ru") if profile else "ru"

    # Загружаем историю и добавляем новое сообщение
    history = await get_history(user_id, limit=10)
    history.append({"role": "user", "content": user_text})

    # Запрос к Groq с полной историей
    response = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": chat_system(interface_lang, profile)},
            *history,
        ],
        temperature=0.8,
    )
    reply = response.choices[0].message.content.strip()

    # Сохраняем оба сообщения в историю
    await save_message(user_id, "user", user_text)
    await save_message(user_id, "assistant", reply)

    await message.answer(reply)
