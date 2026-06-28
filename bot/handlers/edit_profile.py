"""
Редактирование профиля через inline-кнопки.
Одна команда /edit — всё остальное через callback.
"""
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from api.services.database import get_user, update_user

router = Router()


class EditStates(StatesGroup):
    editing_level     = State()
    editing_lang      = State()
    editing_interests = State()
    editing_goal      = State()


def edit_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🌱 Уровень",    callback_data="edit:level"),
                InlineKeyboardButton(text="🌐 Язык",       callback_data="edit:lang"),
            ],
            [
                InlineKeyboardButton(text="❤️ Интересы",  callback_data="edit:interests"),
                InlineKeyboardButton(text="🎯 Цель",       callback_data="edit:goal"),
            ],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🌱 Level",      callback_data="edit:level"),
                InlineKeyboardButton(text="🌐 Language",   callback_data="edit:lang"),
            ],
            [
                InlineKeyboardButton(text="❤️ Interests",  callback_data="edit:interests"),
                InlineKeyboardButton(text="🎯 Goal",       callback_data="edit:goal"),
            ],
        ])


def level_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌱 Beginner")],
            [KeyboardButton(text="📚 Intermediate")],
            [KeyboardButton(text="🚀 Advanced")],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )


def lang_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 На русском")],
            [KeyboardButton(text="🇬🇧 In English")],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )


async def _lang(user_id: int) -> str:
    profile = await get_user(user_id)
    return profile.get("interface_lang", "ru") if profile else "ru"


# ─── /edit — открывает меню ───────────────────────────────────────────────────

@router.message(Command("edit"))
async def cmd_edit(message: Message, state: FSMContext):
    await state.clear()
    lang = await _lang(message.from_user.id)
    prompt = "Что хочешь изменить?" if lang == "ru" else "What would you like to change?"
    await message.answer(prompt, reply_markup=edit_menu_keyboard(lang))


# ─── Callbacks от inline-кнопок ───────────────────────────────────────────────

@router.callback_query(F.data == "edit:level")
async def cb_edit_level(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(cb.from_user.id)
    prompt = "Выбери новый уровень:" if lang == "ru" else "Choose your new level:"
    await cb.message.answer(prompt, reply_markup=level_keyboard())
    await state.set_state(EditStates.editing_level)
    await cb.answer()


@router.callback_query(F.data == "edit:lang")
async def cb_edit_lang(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(cb.from_user.id)
    prompt = "Выбери язык интерфейса:" if lang == "ru" else "Choose interface language:"
    await cb.message.answer(prompt, reply_markup=lang_keyboard())
    await state.set_state(EditStates.editing_lang)
    await cb.answer()


@router.callback_query(F.data == "edit:interests")
async def cb_edit_interests(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(cb.from_user.id)
    if lang == "ru":
        await cb.message.answer(
            "Напиши интересы через запятую:\n_Например: аниме, футбол, кино_",
            parse_mode="Markdown",
        )
    else:
        await cb.message.answer(
            "Write your interests separated by commas:\n_E.g: anime, football, movies_",
            parse_mode="Markdown",
        )
    await state.set_state(EditStates.editing_interests)
    await cb.answer()


@router.callback_query(F.data == "edit:goal")
async def cb_edit_goal(cb: CallbackQuery, state: FSMContext):
    lang = await _lang(cb.from_user.id)
    if lang == "ru":
        await cb.message.answer(
            "Напиши свою новую цель:\n_Например: смотреть сериалы без субтитров_",
            parse_mode="Markdown",
        )
    else:
        await cb.message.answer(
            "Write your new goal:\n_E.g: watch series without subtitles_",
            parse_mode="Markdown",
        )
    await state.set_state(EditStates.editing_goal)
    await cb.answer()


# ─── FSM обработчики ввода ────────────────────────────────────────────────────

@router.message(EditStates.editing_level)
async def process_level(message: Message, state: FSMContext):
    text = message.text or ""
    if "Beginner" in text:       level = "beginner"
    elif "Intermediate" in text: level = "intermediate"
    else:                        level = "advanced"
    await update_user(message.from_user.id, level=level)
    await state.clear()
    lang = await _lang(message.from_user.id)
    msg = "✅ Уровень обновлён!" if lang == "ru" else "✅ Level updated!"
    await message.answer(msg, reply_markup=ReplyKeyboardRemove())


@router.message(EditStates.editing_lang)
async def process_lang(message: Message, state: FSMContext):
    new_lang = "ru" if "русском" in (message.text or "") else "en"
    await update_user(message.from_user.id, interface_lang=new_lang)
    await state.clear()
    if new_lang == "ru":
        await message.answer("✅ Язык изменён на русский!", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("✅ Language changed to English!", reply_markup=ReplyKeyboardRemove())


@router.message(EditStates.editing_interests)
async def process_interests(message: Message, state: FSMContext):
    interests = [i.strip() for i in (message.text or "").split(",") if i.strip()]
    await update_user(message.from_user.id, interests=interests)
    await state.clear()
    lang = await _lang(message.from_user.id)
    msg = "✅ Интересы обновлены!" if lang == "ru" else "✅ Interests updated!"
    await message.answer(msg, reply_markup=ReplyKeyboardRemove())


@router.message(EditStates.editing_goal)
async def process_goal(message: Message, state: FSMContext):
    await update_user(message.from_user.id, goal=message.text or "")
    await state.clear()
    lang = await _lang(message.from_user.id)
    msg = "✅ Цель обновлена!" if lang == "ru" else "✅ Goal updated!"
    await message.answer(msg, reply_markup=ReplyKeyboardRemove())
