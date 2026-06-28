import asyncio
import logging
from pathlib import Path
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ErrorEvent
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from config.settings import settings
from api.services.database import init_db, get_user, cleanup_old_history
from bot.handlers import voice, word, onboarding, chat, edit_profile, video
from bot.handlers.edit_profile import edit_menu_keyboard

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FSM_DB_PATH = Path(__file__).parent.parent / "data" / "fsm_storage.db"


def get_storage():
    try:
        from aiogram_sqlite_storage.sqlitestore import SQLStorage
        FSM_DB_PATH.parent.mkdir(exist_ok=True)
        logger.info(f"✅ FSM storage: SQLite ({FSM_DB_PATH})")
        return SQLStorage(str(FSM_DB_PATH))
    except ImportError:
        logger.warning("⚠️  aiogram-sqlite-storage не установлен — используется MemoryStorage")
        return MemoryStorage()


async def main():
    await init_db()
    logger.info("✅ Database initialized")

    deleted = await cleanup_old_history(days=30)
    if deleted:
        logger.info(f"🧹 Cleaned {deleted} old chat history records")

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        session=AiohttpSession(timeout=120),
    )
    dp = Dispatcher(storage=get_storage())

    # ─── Глобальный error handler ─────────────────────────────────────────────
    @dp.errors()
    async def global_error_handler(event: ErrorEvent):
        logger.error(f"Unhandled error: {event.exception}", exc_info=event.exception)
        try:
            update = event.update
            msg = (
                update.message
                or (update.callback_query.message if update.callback_query else None)
            )
            if msg:
                user = await get_user(msg.from_user.id)
                lang = user.get("interface_lang", "ru") if user else "ru"
                text = (
                    "⚠️ Что-то пошло не так. Попробуй ещё раз или напиши /menu."
                    if lang == "ru"
                    else "⚠️ Something went wrong. Try again or type /menu."
                )
                await msg.answer(text)
        except Exception as e:
            logger.error(f"Error handler itself failed: {e}")

    # ─── Роутеры ──────────────────────────────────────────────────────────────
    dp.include_router(onboarding.router)
    dp.include_router(edit_profile.router)
    dp.include_router(chat.router)
    dp.include_router(video.router)
    dp.include_router(voice.router)
    dp.include_router(word.router)

    # ─── /start ───────────────────────────────────────────────────────────────
    @dp.message(CommandStart())
    async def cmd_start(message: Message, state):
        user = await get_user(message.from_user.id)
        if user and user.get("onboarded"):
            lang = user.get("interface_lang", "ru")
            name = message.from_user.first_name or ""
            if lang == "ru":
                await message.answer(
                    f"👋 С возвращением, *{name}*!\n\n"
                    "🎤 Голосовое — практика разговора\n"
                    "📖 *Что значит X?* — объяснение слова\n"
                    "💬 */chat* — свободный диалог\n"
                    "👤 */profile* — твой профиль\n"
                    "✏️ */edit* — изменить профиль\n\n"
                    "_Хочешь начать заново? Напиши_ */reset*",
                    parse_mode="Markdown",
                )
            else:
                await message.answer(
                    f"👋 Welcome back, *{name}*!\n\n"
                    "🎤 Voice message — speaking practice\n"
                    "📖 *What does X mean?* — word explanation\n"
                    "💬 */chat* — free conversation\n"
                    "👤 */profile* — your profile\n"
                    "✏️ */edit* — edit profile\n\n"
                    "_Want to start over? Type_ */reset*",
                    parse_mode="Markdown",
                )
        else:
            await onboarding.start_onboarding(message, state)

    # ─── /reset ───────────────────────────────────────────────────────────────
    @dp.message(Command("reset"))
    async def cmd_reset(message: Message, state):
        await onboarding.start_onboarding(message, state)

    # ─── /menu ────────────────────────────────────────────────────────────────
    @dp.message(Command("menu"))
    async def cmd_menu(message: Message):
        user = await get_user(message.from_user.id)
        lang = user.get("interface_lang", "ru") if user else "ru"
        name = message.from_user.first_name or ""
        if lang == "ru":
            await message.answer(
                f"👋 Привет, *{name}*!\n\n"
                "🎤 *Голосовое* — практика разговора\n"
                "📖 *Что значит X?* — объяснение слова\n"
                "💬 */chat* — свободный диалог с носителем\n"
                "👤 */profile* — твой профиль\n"
                "✏️ */edit* — изменить профиль",
                parse_mode="Markdown",
            )
        else:
            await message.answer(
                f"👋 Hey, *{name}*!\n\n"
                "🎤 *Voice message* — speaking practice\n"
                "📖 *What does X mean?* — word explanation\n"
                "💬 */chat* — free conversation\n"
                "👤 */profile* — your profile\n"
                "✏️ */edit* — edit profile",
                parse_mode="Markdown",
            )

    # ─── /profile ─────────────────────────────────────────────────────────────
    @dp.message(Command("profile"))
    async def cmd_profile(message: Message):
        profile = await get_user(message.from_user.id)
        if not profile or not profile.get("onboarded"):
            await message.answer(
                "Профиля ещё нет — напиши /start чтобы зарегистрироваться.\n"
                "No profile yet — type /start to register."
            )
            return

        lang = profile.get("interface_lang", "ru")
        interests = profile.get("interests") or []
        level_emoji = {"beginner": "🌱", "intermediate": "📚", "advanced": "🚀"}.get(
            profile.get("level", ""), "📊"
        )

        if lang == "ru":
            interests_str = ", ".join(interests) if interests else "не указано"
            await message.answer(
                f"👤 *Твой профиль*\n\n"
                f"{level_emoji} Уровень: *{profile.get('level', '—')}*\n"
                f"💼 Профессия: *{profile.get('profession', '—')}*\n"
                f"❤️ Интересы: *{interests_str}*\n"
                f"🎯 Цель: *{profile.get('goal', '—')}*\n"
                f"🌐 Язык: *🇷🇺 Русский*",
                parse_mode="Markdown",
            )
        else:
            interests_str = ", ".join(interests) if interests else "not specified"
            await message.answer(
                f"👤 *Your profile*\n\n"
                f"{level_emoji} Level: *{profile.get('level', '—')}*\n"
                f"💼 Profession: *{profile.get('profession', '—')}*\n"
                f"❤️ Interests: *{interests_str}*\n"
                f"🎯 Goal: *{profile.get('goal', '—')}*\n"
                f"🌐 Language: *🇬🇧 English*",
                parse_mode="Markdown",
            )

        prompt = "✏️ Что изменить?" if lang == "ru" else "✏️ What to change?"
        await message.answer(prompt, reply_markup=edit_menu_keyboard(lang))

    logger.info("🤖 Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
