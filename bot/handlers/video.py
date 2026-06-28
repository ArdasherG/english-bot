"""
Обработка YouTube ссылок.
Флоу: ссылка → субтитры → саммари + слова → тап на слово → объяснение → викторина
"""

import re
import json
import logging
import httpx
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from api.services.database import get_user
from config.settings import settings

router = Router()
logger = logging.getLogger(__name__)


def escape_md(text: str) -> str:
    """Экранирует спецсимволы Markdown v1 для Telegram."""
    for ch in ["*", "_", "`", "[", "]"]:
        text = text.replace(ch, f"\{ch}")
    return text


YOUTUBE_PATTERN = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_-]{11}"
)


class VideoStates(StatesGroup):
    quiz_active = State()


def words_keyboard(words: list[dict], video_id: str) -> InlineKeyboardMarkup:
    """Кнопка для каждого слова."""
    buttons = []
    for i, w in enumerate(words):
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📌 {w['word']}",
                    callback_data=f"word:{video_id}:{i}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🎯 Начать викторину",
                callback_data=f"quiz:start:{video_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def quiz_keyboard(video_id: str, q_idx: int, options: dict) -> InlineKeyboardMarkup:
    """Кнопки вариантов ответа викторины."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"A: {options.get('A', '')}",
                    callback_data=f"quiz:answer:{video_id}:{q_idx}:A",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"B: {options.get('B', '')}",
                    callback_data=f"quiz:answer:{video_id}:{q_idx}:B",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"C: {options.get('C', '')}",
                    callback_data=f"quiz:answer:{video_id}:{q_idx}:C",
                )
            ],
        ]
    )


# Обработка YouTube ссылки


@router.message(F.text & F.text.regexp(YOUTUBE_PATTERN))
async def handle_youtube_link(message: Message, state: FSMContext):
    user_id = message.from_user.id
    url = message.text.strip()

    profile = await get_user(user_id)
    lang = profile.get("interface_lang", "ru") if profile else "ru"

    # Прогресс — три шага
    steps = (
        [
            "⏳ Загружаем субтитры...",
            "🔍 Анализируем видео...",
            "📝 Подбираем слова для тебя...",
        ]
        if lang == "ru"
        else [
            "⏳ Loading subtitles...",
            "🔍 Analyzing video...",
            "📝 Picking words for you...",
        ]
    )

    progress_msg = await message.answer(steps[0])

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            await progress_msg.edit_text(steps[1])

            response = await client.post(
                f"{settings.BACKEND_URL}/media/analyze",
                json={
                    "url": url,
                    "profile": profile,
                    "interface_lang": lang,
                },
            )
            response.raise_for_status()
            data = response.json()

    except httpx.TimeoutException:
        err = (
            "⏱ Слишком долго. Попробуй более короткое видео (до 30 минут)."
            if lang == "ru"
            else "⏱ Timed out. Try a shorter video (under 30 minutes)."
        )
        await progress_msg.edit_text(err)
        return
    except httpx.HTTPStatusError as e:
        body = e.response.text if e.response else ""
        if "subtitle" in body.lower() or "caption" in body.lower():
            err = (
                "😕 У этого видео нет английских субтитров. Попробуй другое."
                if lang == "ru"
                else "😕 This video has no English subtitles. Try another one."
            )
        elif "language" in body.lower():
            err = (
                "🌍 Похоже это видео не на английском языке."
                if lang == "ru"
                else "🌍 This video doesn't seem to be in English."
            )
        else:
            err = (
                "⚠️ Что-то пошло не так. Попробуй другое видео."
                if lang == "ru"
                else "⚠️ Something went wrong. Try another video."
            )
        await progress_msg.edit_text(err)
        return
    except Exception as e:
        logger.error(f"Video handler error for user {user_id}: {e}", exc_info=True)
        err = (
            "⚠️ Ошибка. Попробуй ещё раз."
            if lang == "ru"
            else "⚠️ Error. Please try again."
        )
        await progress_msg.edit_text(err)
        return

    await progress_msg.edit_text(steps[2])

    # Сохраняем данные видео в FSM для викторины
    await state.update_data(
        video_id=data["video_id"],
        video_title=data["title"],
        words=data["words"],
        interface_lang=lang,
    )

    # Саммари
    cache_note = " _(из кэша)_" if data.get("from_cache") else ""
    header = f"📹 *{data['title']}*{cache_note}\n\n" f"📝 {data['summary']}\n\n"

    if lang == "ru":
        header += "🎯 *Слова для изучения* — нажми на любое:"
    else:
        header += "🎯 *Words to learn* — tap any to explore:"

    await progress_msg.edit_text(header, parse_mode="Markdown")
    await message.answer(
        "👇",
        reply_markup=words_keyboard(data["words"], data["video_id"]),
    )


# Тап на слово — объяснение


@router.callback_query(F.data.startswith("word:"))
async def cb_word(cb: CallbackQuery, state: FSMContext):
    _, video_id, idx_str = cb.data.split(":", 2)
    idx = int(idx_str)

    fsm_data = await state.get_data()
    words = fsm_data.get("words", [])
    lang = fsm_data.get("interface_lang", "ru")

    if idx >= len(words):
        await cb.answer("Слово не найдено" if lang == "ru" else "Word not found")
        return

    w = words[idx]

    if lang == "ru":
        text = (
            f"📌 *{w['word']}*\n\n"
            f"💡 _{w['hint']}_\n\n"
            f"📖 *Пример из видео:*\n_{w['example']}_"
        )
    else:
        text = (
            f"📌 *{w['word']}*\n\n"
            f"💡 _{w['hint']}_\n\n"
            f"📖 *Example from the video:*\n_{w['example']}_"
        )

    await cb.message.answer(text, parse_mode="Markdown")
    await cb.answer()


# Викторина 


@router.callback_query(F.data.startswith("quiz:start:"))
async def cb_quiz_start(cb: CallbackQuery, state: FSMContext):
    fsm_data = await state.get_data()
    words = fsm_data.get("words", [])
    lang = fsm_data.get("interface_lang", "ru")

    if not words:
        await cb.answer(
            "Нет слов для викторины" if lang == "ru" else "No words for quiz"
        )
        return

    await state.update_data(quiz_index=0, quiz_score=0)
    await state.set_state(VideoStates.quiz_active)

    intro = (
        f"🎯 *Викторина по видео!*\n_{len(words)} вопросов — поехали!_"
        if lang == "ru"
        else f"🎯 *Video Quiz!*\n_{len(words)} questions — let's go!_"
    )
    await cb.message.answer(intro, parse_mode="Markdown")
    await _send_quiz_question(cb.message, state, 0, words, lang)
    await cb.answer()


async def _send_quiz_question(message, state, idx, words, lang):
    """Отправляет вопрос викторины для слова с индексом idx."""
    w = words[idx]

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.BACKEND_URL}/media/quiz",
            json={"word": w["word"], "example": w["example"], "interface_lang": lang},
        )
        response.raise_for_status()
        q = response.json()

    # Сохраняем вопрос в FSM
    await state.update_data(current_question=q)

    num = f"{idx + 1}/{len(words)}"
    text = f"❓ {num}\n\n{escape_md(q['question'])}"

    await message.answer(
        text,
        reply_markup=quiz_keyboard(
            (await state.get_data()).get("video_id", ""),
            idx,
            q["options"],
        ),
    )


@router.callback_query(F.data.startswith("quiz:answer:"))
async def cb_quiz_answer(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    # quiz:answer:VIDEO_ID:Q_IDX:ANSWER
    q_idx = int(parts[3])
    user_answer = parts[4]

    fsm_data = await state.get_data()
    words = fsm_data.get("words", [])
    lang = fsm_data.get("interface_lang", "ru")
    q = fsm_data.get("current_question", {})
    score = fsm_data.get("quiz_score", 0)

    correct = q.get("correct", "A")
    is_correct = user_answer == correct

    if is_correct:
        score += 1
        await state.update_data(quiz_score=score)
        result_text = "✅ Правильно!" if lang == "ru" else "✅ Correct!"
    else:
        correct_text = escape_md(q["options"].get(correct, ""))
        if lang == "ru":
            result_text = f"❌ Неправильно.\nПравильный ответ: {correct_text}"
        else:
            result_text = f"❌ Wrong.\nCorrect answer: {correct_text}"
        if q.get("explanation"):
            result_text += f"\n\n💡 {escape_md(q['explanation'])}"

    await cb.message.answer(result_text)
    await cb.answer("✅" if is_correct else "❌")

    # Следующий вопрос или финал
    next_idx = q_idx + 1
    if next_idx < len(words):
        await state.update_data(quiz_index=next_idx)
        await _send_quiz_question(cb.message, state, next_idx, words, lang)
    else:
        # Финал викторины
        await state.set_state(None)
        pct = round(score / len(words) * 100)
        if lang == "ru":
            final = (
                f"🏁 *Викторина завершена!*\n\n"
                f"Результат: *{score}/{len(words)}* ({pct}%)\n\n"
                + (
                    "🎉 Отлично! Ты хорошо знаешь эти слова."
                    if pct >= 80
                    else (
                        "💪 Неплохо! Повтори слова которые не вспомнил."
                        if pct >= 50
                        else "📚 Есть над чем поработать — попробуй снова!"
                    )
                )
            )
        else:
            final = (
                f"🏁 *Quiz complete!*\n\n"
                f"Score: *{score}/{len(words)}* ({pct}%)\n\n"
                + (
                    "🎉 Excellent! You know these words well."
                    if pct >= 80
                    else (
                        "💪 Not bad! Review the words you missed."
                        if pct >= 50
                        else "📚 Keep practicing — try again!"
                    )
                )
            )
        await cb.message.answer(final, parse_mode="Markdown")
